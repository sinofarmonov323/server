import os
import subprocess
from flask import Flask, render_template, redirect, url_for
from forms import UploadForm
from models import db, File
from admin import admin

app = Flask(__name__)

app.secret_key = "supersecretkey!"

app.config['SQLALCHEMY_DATABASE_URI'] = "sqlite:///file.db"
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db.init_app(app)
admin.init_app(app)

running_processes = {}

with app.app_context():
    db.create_all()

def run_all_scripts():
    """Run all uploaded Python files"""
    files = File.query.all()
    for file in files:
        filepath = os.path.join("uploads", file.file)
        if os.path.exists(filepath):
            # Check if already running
            if filepath in running_processes and running_processes[filepath].poll() is None:
                print(f"Already running: {file.file}")
                continue
            
            try:
                # Open log file to capture output
                log_file = filepath.replace(".py", ".log")
                with open(log_file, "w") as log:
                    log.write("Working\n")
                    log.flush()
                
                process = subprocess.Popen(
                    ["python", filepath],
                    stdout=open(log_file, "a"),
                    stderr=open(log_file, "a")
                )
                running_processes[filepath] = process
                print(f"Started: {file.file} (logs: {log_file})")
            except Exception as e:
                print(f"Error running {file.file}: {e}")

@app.route("/")
def homepage():
    return render_template("index.html", files=File.query.all())

@app.route("/file/<int:file_id>")
def file_page(file_id):
    file = File.query.get(file_id)
    with open("uploads/" + file.file, "r") as f:
        file.content = f.read()
    return render_template("file.html", file=file)

@app.route("/delete_file/<int:file_id>")
def delete_file(file_id):
    file = File.query.get(file_id)
    if file:
        filepath = os.path.join("uploads", file.file)
        if filepath in running_processes:
            running_processes[filepath].terminate()
            del running_processes[filepath]
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
        
        run_all_scripts()
        
        return redirect(url_for("homepage"))
    return render_template("upload.html", form=form)


if __name__=="__main__":
    with app.app_context():
        run_all_scripts()
    app.run(debug=False)
