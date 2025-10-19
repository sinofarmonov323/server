from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()

class File(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    file = db.Column(db.String(128), nullable=True)
