from flask import Flask, request, redirect, url_for, render_template
from werkzeug.utils import secure_filename
import os

app = Flask(__name__)
UPLOAD_FOLDER = "static/uploads"
app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER

@app.route("/", methods=["GET"])
def home():
    images = os.listdir(UPLOAD_FOLDER)
    return render_template("index.html", images=images)

@app.route("/upload", methods=["POST"])
def upload():
    if "file" not in request.files:
        return "No file"
    file = request.files["file"]
    if file.filename == "":
        return "No filename"
    filename = secure_filename(file.filename)
    file.save(os.path.join(app.config["UPLOAD_FOLDER"], filename))
    return redirect(url_for("home"))

if __name__ == "__main__":
    os.makedirs(UPLOAD_FOLDER, exist_ok=True)
    app.run(debug=True)
