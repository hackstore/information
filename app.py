import os
import subprocess
import sys
import time
from threading import Thread

def run_flask_app():
    """Run the Flask web application"""
    print("Starting Flask web application...")
    flask_process = subprocess.Popen([sys.executable, "main.py"], 
                                    stdout=subprocess.PIPE,
                                    stderr=subprocess.PIPE,
                                    text=True,
                                    bufsize=1)
    
    # Stream output
    for line in flask_process.stdout:
        print(f"[FLASK] {line.strip()}")
    
    # If the process exits, print any errors
    for line in flask_process.stderr:
        print(f"[FLASK ERROR] {line.strip()}")
    
    return flask_process

def run_telegram_bot():
    """Run the Telegram bot"""
    # Wait a bit for Flask to start up first
    time.sleep(3)
    
    print("Starting Telegram bot...")
    bot_process = subprocess.Popen([sys.executable, "bot.py"],
                                  stdout=subprocess.PIPE,
                                  stderr=subprocess.PIPE,
                                  text=True,
                                  bufsize=1)
    
    # Stream output
    for line in bot_process.stdout:
        print(f"[BOT] {line.strip()}")
    
    # If the process exits, print any errors
    for line in bot_process.stderr:
        print(f"[BOT ERROR] {line.strip()}")
    
    return bot_process

def check_environment():
    """Check that required environment variables are set"""
    required_vars = {
        'TELEGRAM_TOKEN': 'Your Telegram bot token from BotFather',
    }
    
    missing_vars = []
    for var, description in required_vars.items():
        if not os.getenv(var):
            missing_vars.append((var, description))
    
    if missing_vars:
        print("ERROR: Missing required environment variables:")
        for var, desc in missing_vars:
            print(f"  - {var}: {desc}")
        print("\nPlease set these variables before running.")
        print("Example usage:")
        print("  export TELEGRAM_TOKEN='your_token_here'")
        print("  python app.py")
        return False
    
    return True

def main():
    print("=== SME Bank Search System ===")
    
    # Check environment variables
    if not check_environment():
        return 1
    
    # Create upload directory if it doesn't exist
    upload_dir = os.path.join(os.path.dirname(__file__), 'uploads')
    os.makedirs(upload_dir, exist_ok=True)
    
    # Start Flask app in a separate thread
    flask_thread = Thread(target=run_flask_app)
    flask_thread.daemon = True
    flask_thread.start()
    
    # Start Telegram bot in the main thread
    bot_process = run_telegram_bot()
    
    # Keep the main process running
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\nShutting down...")
        return 0

if __name__ == "__main__":
    sys.exit(main())