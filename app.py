import os
import sys
import threading
import subprocess
import signal
from flask import Flask, render_template, redirect, url_for
from forms import UploadForm
from models import db, File
from admin import admin

app = Flask(__name__)

app.secret_key = "supersecretkey!"

app.config['SQLALCHEMY_DATABASE_URI'] = "sqlite:///file.db"
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

running_processes = {}

db.init_app(app)
admin.init_app(app)

os.makedirs("uploads", exist_ok=True)

with app.app_context():
    db.create_all()

def run_script(filepath):
    """Run a Python file in background as its own process group (Linux-friendly)."""
    process = subprocess.Popen(
        ["python3", filepath],
        preexec_fn=os.setsid,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE
    )
    running_processes[os.path.basename(filepath)] = process
    print(f"Started {filepath} (pid={process.pid})")

@app.route("/")
def homepage():
    return render_template("index.html", files=File.query.all())

@app.route("/file/<int:file_id>")
def file_page(file_id):
    file = File.query.get(file_id)
    return render_template("file.html", file=file)

@app.route("/delete_file/<int:file_id>")
def delete_file(file_id):
    file = File.query.get(file_id)
    if not file:
        return redirect(url_for("homepage"))

    filename = file.file
    filepath = os.path.join("uploads", filename)

    process = running_processes.pop(filename, None)
    if process:
        try:
            os.killpg(os.getpgid(process.pid), signal.SIGTERM)
            process.wait(timeout=3)
            print(f"Killed process group for {filename}")
        except Exception as e:
            print(f"Error killing process for {filename}: {e}")

    if os.path.exists(filepath):
        os.remove(filepath)

    db.session.delete(file)
    db.session.commit()

    return redirect(url_for("homepage"))

@app.route("/upload", methods=["GET", "POST"])
def upload_page():
    form = UploadForm()
    if form.validate_on_submit():
        file = form.file.data
        filepath = os.path.join("uploads", file.filename)
        os.makedirs("uploads", exist_ok=True)
        file.save(filepath)
        new_file = File(file=file.filename)
        db.session.add(new_file)
        db.session.commit()

        run_script(filepath)
        
        return redirect(url_for("homepage"))
    return render_template("upload.html", form=form)


if __name__=="__main__":
    app.run(debug=True)
