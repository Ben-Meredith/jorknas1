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

def load_users():
    if os.path.exists(USERS_FILE):
        with open(USERS_FILE, 'r') as f:
            try:
                data = json.load(f)
            except json.JSONDecodeError:
                data = {}
    else:
        data = {}
    # Normalize legacy values (string passwords) to dicts with profile_pic
    normalized = {}
    for uname, val in data.items():
        if isinstance(val, str):
            normalized[uname] = {"password": val, "profile_pic": None}
        elif isinstance(val, dict):
            normalized[uname] = {
                "password": val.get("password", ""),
                "profile_pic": val.get("profile_pic")
            }
        else:
            normalized[uname] = {"password": "", "profile_pic": None}
    return normalized

users = load_users()

def save_users():
    with open(USERS_FILE, 'w') as f:
        json.dump(users, f)

# Maps each filename to the username who uploaded it
uploaders = {}

# Map each filename to its S3 URL
image_urls = {}

# ----------------------------
# AWS S3 CONFIGURATION
# ----------------------------
AWS_BUCKET_NAME = "jorknas-images"
AWS_REGION = "us-east-2"

# Boto3 will automatically read AWS_ACCESS_KEY_ID and AWS_SECRET_ACCESS_KEY from environment variables
s3 = boto3.client("s3", region_name=AWS_REGION)

# ----------------------------
# Upload file to S3 function (added)
# ----------------------------
def upload_file_to_s3(file):
    filename = secure_filename(file.filename)
    s3.upload_fileobj(
        file,
        AWS_BUCKET_NAME,
        filename
    )
    url = f"https://{AWS_BUCKET_NAME}.s3.{AWS_REGION}.amazonaws.com/{filename}"
    return url

# ----------------------------
# Load old posts from posts.json
# ----------------------------
POSTS_FILE = 'posts.json'
posts_data = {}

if os.path.exists(POSTS_FILE):
    try:
        with open(POSTS_FILE, 'r') as f:
            posts_data = json.load(f)
    except json.JSONDecodeError:
        # File exists but is empty or malformed, start fresh
        posts_data = {}

# Populate image_urls, uploaders, likes_dict
for filename, info in posts_data.items():
    image_urls[filename] = f"https://{AWS_BUCKET_NAME}.s3.{AWS_REGION}.amazonaws.com/{filename}"
    
    uploader_name = info.get('uploader', 'Unknown')
    if uploader_name not in users:
        users[uploader_name] = {"password": "", "profile_pic": None}
    
    uploaders[filename] = uploader_name
    likes_dict[filename] = info.get('likes', 0)

# ----------------------------
# Load existing images from S3 on startup
# ----------------------------
def load_existing_images_from_s3():
    global image_urls, uploaders, likes_dict
    try:
        response = s3.list_objects_v2(Bucket=AWS_BUCKET_NAME)
        if 'Contents' in response:
            for obj in response['Contents']:
                filename = obj['Key']
                image_urls[filename] = f"https://{AWS_BUCKET_NAME}.s3.{AWS_REGION}.amazonaws.com/{filename}"
                # Set a default uploader if unknown
                if filename not in uploaders:
                    uploaders[filename] = "Unknown"
                # Initialize likes if not present
                if filename not in likes_dict:
                    likes_dict[filename] = 0
    except Exception as e:
        print("Error loading existing images from S3:", e)

# Call the function to populate existing images
load_existing_images_from_s3()

# ----------------------------
# Login route
# ----------------------------
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        u = users.get(username)
        # Support both legacy (string) and new (dict) formats
        stored_pw = u if isinstance(u, str) else (u.get('password') if u else None)
        if stored_pw and stored_pw == password:
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
        # Add user with new dict shape and save to JSON file
        users[username] = {"password": password, "profile_pic": None}
        save_users()
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

    # Build a mapping from each post to the uploader's profile pic
    profile_pics = {}
    for user, data in users.items():
        profile_pics[user] = data.get("profile_pic", None)

    # Pass S3 URLs and profile pics correctly to the template
    return render_template(
        'index.html',
        images=list(image_urls.keys()),  # pass filenames
        likes_dict=likes_dict,
        uploaders=uploaders,
        image_urls=image_urls,          # S3 URLs
        profile_pics=profile_pics,      # profile pics
        current_user=session['username']
    )

# ... rest of your code remains unchanged ...
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
        # Save uploader info and likes to posts.json
        posts_data[file.filename] = {
            "uploader": session['username'],
            "likes": 0
        }
        with open(POSTS_FILE, 'w') as f:
            json.dump(posts_data, f)

            return redirect(url_for('index'))

# ----------------------------
# Upload profile picture route
# ----------------------------
@app.route('/upload_profile_pic', methods=['POST'])
def upload_profile_pic():
    if 'username' not in session:
        return redirect(url_for('login'))

    if 'file' not in request.files:
        return redirect(url_for('index'))
    file = request.files['file']
    if file.filename == '':
        return redirect(url_for('index'))
    if file:
        # Upload to S3
        profile_pic_url = upload_file_to_s3(file)
        username = session['username']

        # Ensure user entry is a dict to avoid KeyError
        if username not in users or isinstance(users[username], str):
            users[username] = {"password": users.get(username, ""), "profile_pic": None}

        # Save profile pic
        users[username]['profile_pic'] = profile_pic_url
        save_users()

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
