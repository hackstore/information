import os
from flask import Flask, request, redirect, url_for, render_template
from werkzeug.utils import secure_filename
import pandas as pd
from database import db
from models import File, Row

UPLOAD_FOLDER = os.path.join(os.path.dirname(__file__), 'uploads')
ALLOWED_EXTENSIONS = {'xlsx'}

def create_app():
    app = Flask(__name__)
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///sme_search.db'
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
    app.config['SECRET_KEY'] = os.getenv('FLASK_SECRET_KEY', 'dev-secret-123')

    db.init_app(app)
    with app.app_context():
        db.create_all()

    def allowed_file(filename):
        return '.' in filename and \
            filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

    @app.route('/', methods=['GET', 'POST'])
    def upload():
        if request.method == 'POST':
            file = request.files.get('file')
            if file and allowed_file(file.filename):
                filename = secure_filename(file.filename)
                filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
                os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
                file.save(filepath)

                try:
                    df = pd.read_excel(filepath, header=2, dtype=str)
                    df.columns = [
                        'branch_code', 'branch_name', 'province', 'cnic_passport', 'name',
                        'address', 'nature_of_deposit', 'account_number', 'account_type',
                        'applicant_name', 'instrument_type', 'instrument_number',
                        'date_of_issue', 'federal_provincial', 'currency', 'rate_type',
                        'fcs_contract_no', 'pkr_conversion_rate', 'rate_applied_date',
                        'amount_outstanding', 'eqv_pkr_surrendered', 'last_transaction_date',
                        'remarks'
                    ]
                    df.fillna('', inplace=True)

                    new_file = File(filename=filename)
                    db.session.add(new_file)
                    db.session.flush()

                    for _, row in df.iterrows():
                        new_row = Row(
                            file_id=new_file.id,
                            branch_code=row.get('branch_code', ''),
                            name=row.get('name', '').strip(),
                            cnic_passport=row.get('cnic_passport', ''),
                            account_number=row.get('account_number', ''),
                            instrument_number=row.get('instrument_number', ''),
                            amount=row.get('amount_outstanding', ''),
                            address=row.get('address', ''),
                            last_transaction_date=row.get('last_transaction_date', ''),
                            data=row.to_dict()
                        )
                        db.session.add(new_row)
                    
                    db.session.commit()
                    return redirect(url_for('search'))
                
                except Exception as e:
                    db.session.rollback()
                    return f"Error processing file: {str(e)}", 500

        return render_template('upload.html')

    @app.route('/search', methods=['GET', 'POST'])
    def search():
        results = []
        query = ''
        if request.method == 'POST':
            query = request.form.get('query', '').strip()
            if query:
                search_filter = (
                    Row.name.ilike(f"%{query}%") |
                    Row.cnic_passport.ilike(f"%{query}%") |
                    Row.account_number.ilike(f"%{query}%") |
                    Row.branch_code.ilike(f"%{query}%") |
                    Row.instrument_number.ilike(f"%{query}%") |
                    Row.amount.ilike(f"%{query}%")
                )
                results = Row.query.filter(search_filter).order_by(Row.name).all()
        
        return render_template('search.html', results=results, query=query)

    return app

if __name__ == '__main__':
    app = create_app()
    app.run(host='0.0.0.0', port=5000, debug=True)
