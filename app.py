import os
import sys
import threading
import subprocess
import signal
import secrets
from pathlib import Path
from werkzeug.utils import secure_filename
from flask import Flask, render_template, redirect, url_for, flash, abort
from forms import UploadForm
from models import db, File
from admin import admin

app = Flask(__name__)

# Use environment variable for secret key
app.secret_key = "supersecretkey!@#"

# Database configuration
app.config['SQLALCHEMY_DATABASE_URI'] = "sqlite:///file.db"
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Upload configuration
UPLOAD_FOLDER = Path("uploads")

running_processes = {}
process_lock = threading.Lock()

db.init_app(app)
admin.init_app(app)

# Create uploads directory
UPLOAD_FOLDER.mkdir(exist_ok=True)

with app.app_context():
    db.create_all()

def run_script(filepath, filename):
    """Run a Python file in background as its own process group."""
    try:
        # Validate the file exists and is in uploads directory
        filepath = Path(filepath).resolve()
        if not filepath.is_relative_to(UPLOAD_FOLDER.resolve()):
            print(f"Security: Attempted to run file outside uploads directory: {filepath}")
            return False
        
        # Start process in its own process group (Linux)
        process = subprocess.Popen(
            [sys.executable, str(filepath)],
            preexec_fn=os.setsid,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            cwd=UPLOAD_FOLDER
        )
        
        with process_lock:
            running_processes[filename] = process
        
        print(f"Started {filepath} (pid={process.pid})")
        return True
    except Exception as e:
        print(f"Error starting process for {filepath}: {e}")
        return False

def stop_process(filename):
    """Safely stop a running process and its entire process group."""
    with process_lock:
        process = running_processes.pop(filename, None)
    
    if process:
        try:
            # Kill entire process group (all child processes too)
            os.killpg(os.getpgid(process.pid), signal.SIGTERM)
            process.wait(timeout=5)
            print(f"Stopped process group for {filename}")
            return True
        except subprocess.TimeoutExpired:
            # Force kill if it doesn't stop gracefully
            os.killpg(os.getpgid(process.pid), signal.SIGKILL)
            print(f"Force killed process group for {filename}")
            return True
        except Exception as e:
            print(f"Error stopping process for {filename}: {e}")
            return False
    return True

@app.route("/")
def homepage():
    files = File.query.all()
    return render_template("index.html", files=files)

@app.route("/file/<int:file_id>")
def file_page(file_id):
    file = File.query.get_or_404(file_id)
    return render_template("file.html", file=file)

@app.route("/delete_file/<int:file_id>", methods=["POST"])
def delete_file(file_id):
    """Delete a file and stop its process."""
    file = File.query.get_or_404(file_id)
    
    filename = file.file
    filepath = UPLOAD_FOLDER / filename
    
    # Stop the running process
    stop_process(filename)
    
    # Delete the file from filesystem
    try:
        if filepath.exists():
            filepath.unlink()
    except Exception as e:
        print(f"Error deleting file {filepath}: {e}")
        flash(f"Error deleting file: {e}", "error")
        return redirect(url_for("homepage"))
    
    # Delete from database
    db.session.delete(file)
    db.session.commit()
    
    flash(f"File '{filename}' deleted successfully", "success")
    return redirect(url_for("homepage"))

@app.route("/upload", methods=["GET", "POST"])
def upload_page():
    form = UploadForm()
    if form.validate_on_submit():
        file = form.file.data
        
        # Secure the filename
        filename = secure_filename(file.filename)
        if not filename:
            flash("Invalid filename", "error")
            return redirect(url_for("upload_page"))
        
        # Check for duplicate filenames
        existing_file = File.query.filter_by(file=filename).first()
        if existing_file:
            flash(f"File '{filename}' already exists", "error")
            return redirect(url_for("upload_page"))
        
        # Save file
        filepath = UPLOAD_FOLDER / filename
        try:
            file.save(str(filepath))
        except Exception as e:
            flash(f"Error saving file: {e}", "error")
            return redirect(url_for("upload_page"))
        
        # Add to database
        new_file = File(file=filename)
        db.session.add(new_file)
        db.session.commit()
        
        # Run the script
        if run_script(filepath, filename):
            flash(f"File '{filename}' uploaded and started successfully", "success")
        else:
            flash(f"File uploaded but failed to start", "warning")
        
        return redirect(url_for("homepage"))
    
    return render_template("upload.html", form=form)

@app.errorhandler(404)
def not_found(e):
    return render_template("404.html"), 404

def cleanup_processes():
    """Clean up all running processes on shutdown."""
    print("Cleaning up running processes...")
    with process_lock:
        for filename, process in list(running_processes.items()):
            try:
                os.killpg(os.getpgid(process.pid), signal.SIGTERM)
                process.wait(timeout=3)
            except Exception as e:
                print(f"Error cleaning up {filename}: {e}")
    print("Cleanup complete")

import atexit
atexit.register(cleanup_processes)

if __name__ == "__main__":
    debug_mode = os.environ.get('FLASK_DEBUG', 'False').lower() == 'true'
    app.run(debug=debug_mode, host='0.0.0.0', port=5000)
