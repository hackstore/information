from database import db

class File(db.Model):
    __tablename__ = 'files'
    id = db.Column(db.Integer, primary_key=True)
    filename = db.Column(db.String, nullable=False)
    rows = db.relationship('Row', back_populates='file', cascade='all, delete')

class Row(db.Model):
    __tablename__ = 'rows'
    id = db.Column(db.Integer, primary_key=True)
    file_id = db.Column(db.Integer, db.ForeignKey('files.id'), nullable=False)
    file = db.relationship('File', back_populates='rows')
    
    # Core searchable fields
    name = db.Column(db.String, index=True)
    cnic_passport = db.Column(db.String, index=True)
    account_number = db.Column(db.String, index=True)
    branch_code = db.Column(db.String, index=True)
    
    # Additional important fields
    instrument_number = db.Column(db.String)
    amount = db.Column(db.String)
    address = db.Column(db.String)
    last_transaction_date = db.Column(db.String)
    
    # Store full data for reference
    data = db.Column(db.JSON)
