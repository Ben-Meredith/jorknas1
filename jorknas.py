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

# Map each filename to its S3 URL
image_urls = {}

# ----------------------------
# AWS S3 CONFIGURATION
# ----------------------------
AWS_BUCKET_NAME = "jorknas-images"
AWS_REGION = "us-east-1"

# Boto3 will automatically read AWS_ACCESS_KEY_ID and AWS_SECRET_ACCESS_KEY from environment variables
s3 = boto3.client("s3", region_name=AWS_REGION)

def upload_file_to_s3(file):
    filename = secure_filename(file.filename)
    s3.upload_fileobj(
        file,
        AWS_BUCKET_NAME,
        filename
        # Removed ACL argument because bucket enforces owner
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

    # Initialize likes and uploaders for any new images
    for img in image_urls.keys():
        if img not in likes_dict:
            likes_dict[img] = 0
        if img not in uploaders:
            uploaders[img] = "Unknown"

    return render_template(
        'index.html',
        images=list(image_urls.keys()),  # pass filenames
        likes_dict=likes_dict,
        uploaders=uploaders,
        image_urls=image_urls,          # pass the S3 URLs
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
        # Upload to S3
        image_url = upload_file_to_s3(file)
        likes_dict[file.filename] = 0
        uploaders[file.filename] = session['username']
        image_urls[file.filename] = image_url  # store S3 URL

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
