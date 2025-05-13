import os
import asyncio
import json
import threading
from datetime import datetime
from flask import Flask, render_template_string
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler
from telegram.ext import filters, ContextTypes
from telegram.constants import ParseMode
from database import db
from models import Row

# HTML template for the status page
STATUS_PAGE_HTML = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>SME Bank Search Bot Status</title>
    <style>
        body {
            font-family: Arial, sans-serif;
            background-color: #f5f5f5;
            margin: 0;
            padding: 20px;
            display: flex;
            justify-content: center;
            align-items: center;
            height: 100vh;
        }
        .status-card {
            background-color: white;
            border-radius: 8px;
            box-shadow: 0 4px 12px rgba(0,0,0,0.1);
            padding: 30px;
            width: 300px;
            text-align: center;
        }
        .bot-name {
            font-size: 24px;
            font-weight: bold;
            margin-bottom: 20px;
            color: #0074D9;
        }
        .status-indicator {
            display: flex;
            align-items: center;
            justify-content: center;
            margin-bottom: 20px;
        }
        .status-dot {
            width: 20px;
            height: 20px;
            border-radius: 50%;
            background-color: #2ECC40;
            margin-right: 10px;
        }
        .status-text {
            font-size: 18px;
            font-weight: bold;
            color: #2ECC40;
        }
        .info {
            color: #666;
            font-size: 14px;
        }
        .uptime {
            margin-top: 20px;
            font-size: 14px;
            color: #666;
        }
    </style>
</head>
<body>
    <div class="status-card">
        <div class="bot-name">SME Bank Search Bot</div>
        <div class="status-indicator">
            <div class="status-dot"></div>
            <div class="status-text">Online</div>
        </div>
        <div class="info">Bot is actively monitoring for search requests</div>
        <div class="uptime">Running since: {{ start_time }}</div>
    </div>
</body>
</html>
"""

class TelegramBot:
    def __init__(self, token):
        self.token = token
        self.app = None
        self.user_points = {}
        self.admin_users = []
        self.points_file = "user_points.json"
        self.admin_file = "admin_users.json"
        self.max_points = 5
        self.start_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self.load_data()
        
        # Create the Flask app for the status page
        self.flask_app = Flask(__name__)
        
        # Add route for the status page
        @self.flask_app.route('/')
        def status_page():
            return render_template_string(
                STATUS_PAGE_HTML,
                start_time=self.start_time
            )

    def load_data(self):
        """Load user points and admin list from files"""
        try:
            if os.path.exists(self.points_file):
                with open(self.points_file, 'r') as f:
                    self.user_points = json.load(f)
                print(f"Loaded {len(self.user_points)} user records")

            if os.path.exists(self.admin_file):
                with open(self.admin_file, 'r') as f:
                    self.admin_users = json.load(f)
                print(f"Loaded {len(self.admin_users)} admin users")
        except Exception as e:
            print(f"Error loading user data: {e}")

    def save_data(self):
        """Save user points and admin list to files"""
        try:
            with open(self.points_file, 'w') as f:
                json.dump(self.user_points, f)

            with open(self.admin_file, 'w') as f:
                json.dump(self.admin_users, f)
        except Exception as e:
            print(f"Error saving user data: {e}")

    def is_admin(self, user_id):
        """Check if user is admin"""
        return str(user_id) in self.admin_users

    def get_points(self, user_id):
        """Get remaining points for a user"""
        user_id = str(user_id)
        if user_id not in self.user_points:
            self.user_points[user_id] = self.max_points
            self.save_data()
        return self.user_points[user_id]

    def use_point(self, user_id):
        """Use one search point"""
        user_id = str(user_id)
        if self.is_admin(user_id):
            return True  # Admins have unlimited points

        if user_id not in self.user_points:
            self.user_points[user_id] = self.max_points

        if self.user_points[user_id] > 0:
            self.user_points[user_id] -= 1
            self.save_data()
            return True
        return False

    async def start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = update.effective_user.id
        username = update.effective_user.username or update.effective_user.first_name
        is_admin = self.is_admin(user_id)
        points = self.get_points(user_id) if not is_admin else "∞"

        admin_text = " 👑 *ADMIN ACCESS*" if is_admin else ""

        await update.message.reply_text(
            f"🔍 Welcome to SME Bank Search Bot!{admin_text}\n\n"
            f"Hello {username}, you have *{points}* search points remaining.\n\n"
            f"Send any search query to find matching records.\n"
            f"You can search by:\n"
            f"- CNIC/Passport\n- Account Number\n- Name\n- Branch Code\n- Instrument Number\n- Amount",
            parse_mode=ParseMode.MARKDOWN
        )

    async def add_admin(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = update.effective_user.id

        # Only existing admins can add new admins
        if not self.is_admin(user_id) and user_id != int(os.getenv('OWNER_ID', '0')):
            await update.message.reply_text("❌ You don't have permission to use this command.")
            return

        # Get target user ID from command arguments
        if not context.args:
            await update.message.reply_text("❌ Please provide a user ID: /addadmin [user_id]")
            return

        target_id = str(context.args[0])

        if target_id in self.admin_users:
            await update.message.reply_text(f"User {target_id} is already an admin.")
            return

        self.admin_users.append(target_id)
        self.save_data()

        await update.message.reply_text(f"✅ User {target_id} has been added as admin.")

    async def add_points(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = update.effective_user.id

        # Only admins can add points
        if not self.is_admin(user_id):
            await update.message.reply_text("❌ You don't have permission to use this command.")
            return

        # Get arguments: target user ID and points
        if len(context.args) < 2:
            await update.message.reply_text("❌ Please provide: /addpoints [user_id] [points]")
            return

        try:
            target_id = str(context.args[0])
            points = int(context.args[1])

            if target_id not in self.user_points:
                self.user_points[target_id] = 0

            self.user_points[target_id] += points
            self.save_data()

            await update.message.reply_text(f"✅ Added {points} points to user {target_id}.\nThey now have {self.user_points[target_id]} points.")
        except ValueError:
            await update.message.reply_text("❌ Points must be a number.")

    async def check_points(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = update.effective_user.id
        is_admin = self.is_admin(user_id)
        points = self.get_points(user_id) if not is_admin else "∞"

        admin_text = " (ADMIN - unlimited searches)" if is_admin else ""

        await update.message.reply_text(
            f"📊 *Points Status*\n\n"
            f"User ID: `{user_id}`{admin_text}\n"
            f"Remaining Points: *{points}*",
            parse_mode=ParseMode.MARKDOWN
        )

    def format_result(self, result):
        return (
            f"🏦 *Branch {result.branch_code}*\n"
            f"👤 *Name:* {result.name}\n"
            f"🆔 *CNIC/Passport:* `{result.cnic_passport}`\n"
            f"🔢 *Account:* `{result.account_number}`\n"
            f"💰 *Amount:* PKR {result.amount}\n"
            f"📅 *Last Transaction:* {result.last_transaction_date}\n"
            f"🏠 *Address:* {result.address}"
        )

    def search_db(self, query):
        try:
            # Use a Flask app context to ensure we have a proper SQLAlchemy session
            with db.app.app_context():
                results = Row.query.filter(
                    Row.cnic_passport.ilike(f"%{query}%") |
                    Row.account_number.ilike(f"%{query}%") |
                    Row.name.ilike(f"%{query}%") |
                    Row.branch_code.ilike(f"%{query}%") |
                    Row.instrument_number.ilike(f"%{query}%") |
                    db.cast(Row.amount, db.String).ilike(f"%{query}%")
                ).order_by(Row.name).limit(10).all()

                print(f"Query: '{query}' returned {len(results)} results")
                return results
        except Exception as e:
            print(f"Database search error: {str(e)}")
            return []

    async def handle_search(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = update.effective_user.id
        query = update.message.text.strip()

        if not query:
            await update.message.reply_text("Please enter a search query.")
            return

        # Check if user has points or is admin
        is_admin = self.is_admin(user_id)
        if not is_admin and self.get_points(user_id) <= 0:
            await update.message.reply_text(
                "❌ You have no search points remaining.\n"
                "Contact an administrator to get more points.", 
                parse_mode=ParseMode.MARKDOWN
            )
            return

        # Let user know we're searching
        await update.message.reply_text("🔍 Searching database...", parse_mode=ParseMode.MARKDOWN)

        try:
            # Use to_thread to prevent blocking the event loop
            results = await asyncio.to_thread(self.search_db, query)

            if not results:
                await update.message.reply_text("❌ No matching records found.")
                return  # Don't deduct points for no results

            # Display number of results
            count_message = f"📊 Found {len(results)} matching record(s)."
            await update.message.reply_text(count_message, parse_mode=ParseMode.MARKDOWN)

            # Deduct point only for successful searches with results
            if not is_admin:
                self.use_point(user_id)
                points_left = self.get_points(user_id)
                await update.message.reply_text(
                    f"📉 Used 1 search point. You have *{points_left}* points remaining.",
                    parse_mode=ParseMode.MARKDOWN
                )

            # Send each result
            for result in results:
                try:
                    await update.message.reply_text(
                        self.format_result(result),
                        parse_mode=ParseMode.MARKDOWN
                    )
                except Exception as format_error:
                    print(f"Error formatting result: {str(format_error)}")
                    # Try sending a simplified version
                    await update.message.reply_text(
                        f"Result found: {result.name} (ID: {result.cnic_passport})"
                    )

        except Exception as e:
            await update.message.reply_text("⚠️ An error occurred during search.")
            print(f"Telegram search error: {str(e)}")
            # Don't deduct points for errors

    def setup_flask(self):
        # Setup Flask and SQLAlchemy
        flask_app = Flask(__name__)
        flask_app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///sme_search.db'
        flask_app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

        # Store the app reference in db for app_context access
        db.app = flask_app
        db.init_app(flask_app)

        # Initialize database tables
        with flask_app.app_context():
            db.create_all()

        print("Database setup complete")

    def run_flask_app(self):
        """Run the Flask app in a separate thread"""
        self.flask_app.run(host='0.0.0.0', port=5000, debug=False, use_reloader=False)

def main():
    # Get token from environment
    token = os.getenv('TELEGRAM_TOKEN')
    if not token:
        print("Error: TELEGRAM_TOKEN environment variable not set!")
        return 1

    # Create bot instance and setup database
    bot = TelegramBot(token)
    bot.setup_flask()

    # Add owner as admin if set
    owner_id = os.getenv('OWNER_ID')
    if owner_id and owner_id not in bot.admin_users:
        bot.admin_users.append(owner_id)
        bot.save_data()
        print(f"Added owner (ID: {owner_id}) as admin")

    # Start the Flask web server in a separate thread
    flask_thread = threading.Thread(target=bot.run_flask_app, daemon=True)
    flask_thread.start()
    print(f"Status page running on http://0.0.0.0:5000")

    # Build and configure application
    application = Application.builder().token(token).build()

    # Add command handlers
    application.add_handler(CommandHandler("start", bot.start))
    application.add_handler(CommandHandler("points", bot.check_points))
    application.add_handler(CommandHandler("addadmin", bot.add_admin))
    application.add_handler(CommandHandler("addpoints", bot.add_points))

    # Add message handler for searches
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, bot.handle_search))

    # Start the bot
    print("Starting Telegram bot...")
    application.run_polling(allowed_updates=Update.ALL_TYPES)

    return 0

if __name__ == '__main__':
    exit(main())