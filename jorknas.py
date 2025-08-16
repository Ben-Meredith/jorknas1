from flask import Flask, request, redirect, url_for, render_template, jsonify, session
import os
import json  # For persistent users
import boto3
from werkzeug.utils import secure_filename

app = Flask(__name__)
# Use environment variable for secret key, fallback to hardcoded if not set
app.secret_key = os.environ.get('SECRET_KEY', 'supersecretkey')

UPLOAD_FOLDER = 'static/uploads'
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

# Global likes dictionary
likes_dict = {}

# Persistent users
USERS_FILE = 'users.json'

if os.path.exists(USERS_FILE):
    with open(USERS_FILE, 'r') as f:
        try:
            users = json.load(f)
        except json.JSONDecodeError:
            users = {}
else:
    users = {}

# Maps each filename to the username who uploaded it
uploaders = {}

# ----------------------------
# AWS S3 CONFIGURATION
# ----------------------------
AWS_ACCESS_KEY_ID = "YOUR_ACCESS_KEY_ID"
AWS_SECRET_ACCESS_KEY = "YOUR_SECRET_ACCESS_KEY"
AWS_BUCKET_NAME = "jorknas-images"
AWS_REGION = "us-east-1"

s3 = boto3.client(
    "s3",
    aws_access_key_id=AWS_ACCESS_KEY_ID,
    aws_secret_access_key=AWS_SECRET_ACCESS_KEY,
    region_name=AWS_REGION
)

def upload_file_to_s3(file):
    filename = secure_filename(file.filename)
    s3.upload_fileobj(
        file,
        AWS_BUCKET_NAME,
        filename,
        ExtraArgs={"ACL": "public-read"}
    )
    url = f"https://{AWS_BUCKET_NAME}.s3.{AWS_REGION}.amazonaws.com/{filename}"
    return url

# ----------------------------
# Login route
# ----------------------------
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        if username in users and users[username] == password:
            session['username'] = username
            return redirect(url_for('index'))
        else:
            return render_template('login.html', error="Invalid username or password")
    return render_template('login.html')

# ----------------------------
# Signup route (auto-login preserved)
# ----------------------------
@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        if username in users:
            return render_template('signup.html', error="Username already exists")
        # Add user and save to JSON file
        users[username] = password
        with open(USERS_FILE, 'w') as f:
            json.dump(users, f)
        # Auto-login
        session['username'] = username
        return redirect(url_for('index'))
    return render_template('signup.html')

# ----------------------------
# Home route
# ----------------------------
@app.route('/')
def index():
    if 'username' not in session:
        return redirect(url_for('login'))

    images = os.listdir(app.config['UPLOAD_FOLDER'])
    for img in images:
        if img not in likes_dict:
            likes_dict[img] = 0
        if img not in uploaders:
            uploaders[img] = "Unknown"

    return render_template(
        'index.html',
        images=images,
        likes_dict=likes_dict,
        uploaders=uploaders,
        current_user=session['username']
    )

# ----------------------------
# Upload route (AWS S3)
# ----------------------------
@app.route('/upload', methods=['POST'])
def upload_file():
    if 'username' not in session:
        return redirect(url_for('login'))

    if 'file' not in request.files:
        return redirect(url_for('index'))
    file = request.files['file']
    if file.filename == '':
        return redirect(url_for('index'))
    if file:
        # Upload to S3 instead of local folder
        image_url = upload_file_to_s3(file)
        likes_dict[file.filename] = 0
        uploaders[file.filename] = session['username']
    return redirect(url_for('index'))

# ----------------------------
# Like route
# ----------------------------
@app.route('/like/<filename>', methods=['POST'])
def like_image(filename):
    if filename in likes_dict:
        likes_dict[filename] += 1
        return jsonify({'likes': likes_dict[filename]})
    return jsonify({'error': 'File not found'}), 404

# ----------------------------
# Logout route
# ----------------------------
@app.route('/logout')
def logout():
    session.pop('username', None)
    return redirect(url_for('login'))

# ----------------------------
# Run app
# ----------------------------
if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=True)
