import os
from flask_admin import Admin
from flask_admin.contrib.sqla import ModelView
from flask_admin.form.upload import FileUploadField
from models import File, db
from flask import flash

admin = Admin(template_mode="bootstrap3")

class FileView(ModelView):
    form_extra_fields = {
        "file": FileUploadField("File", base_path="uploads")
    }

    def on_model_change(self, form, model, is_created):
        file_data = form.file.data
        if file_data:
            filename = file_data.filename
            file_path = os.path.join("uploads", filename)

            if os.path.exists(file_path):
                flash("File already exists. Please rename your file.", "warning")

            model.filename = filename

    def on_model_delete(self, model):
        print(model.file)
        if model.file:
            os.remove(f"uploads/{model.file}")

admin.add_view(FileView(File, db.session))
