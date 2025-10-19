from flask_wtf import FlaskForm
from wtforms import StringField, FileField, SubmitField, validators

class UploadForm(FlaskForm):
    file = FileField('Upload File', [validators.DataRequired()])
    submit = SubmitField('Upload')
