from flask import Flask, request, redirect, url_for, render_template, jsonify, session
import os
import json  # For persistent users
import boto3
from werkzeug.utils import secure_filename
from PIL import Image
import io  # Added for in-memory image processing
from datetime import datetime
import sqlite3

ADMIN_USERNAME = "goat"
app = Flask(__name__)
DATABASE = 'messages.db'  # change to your database file if different

def get_db_connection():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row  # so you can access columns by name
    return conn
def init_db():
    conn = get_db_connection()
    conn.execute('''
        CREATE TABLE IF NOT EXISTS messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            sender TEXT NOT NULL,
            receiver TEXT NOT NULL,
            content TEXT NOT NULL,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    conn.commit()
    conn.close()
    
DEFAULT_PROFILE_PIC = "https://i.pinimg.com/236x/4d/2e/0a/4d2e0a694015f3d2f840873d01aa5fd4.jpg"

app = Flask(__name__)
# Use environment variable for secret key, fallback to hardcoded if not set
app.secret_key = os.environ.get('SECRET_KEY', 'supersecretkey')

UPLOAD_FOLDER = 'static/uploads'
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

# Global likes dictionary
likes_dict = {}

# Persistent users
USERS_FILE = 'users.json'

# ----------------------------
# Fixed load_users() and save_users()
# ----------------------------
def load_users():
    if os.path.exists(USERS_FILE):
        with open(USERS_FILE, 'r') as f:
            try:
                data = json.load(f)
            except json.JSONDecodeError:
                data = {}
    else:
        data = {}

    # Make sure every entry is a proper dict with password and profile_pic
    for uname, val in data.items():
        if isinstance(val, str):  # legacy password-only format
            data[uname] = {"password": val, "profile_pic": None}
        elif isinstance(val, dict):
            data[uname]["password"] = val.get("password", "")
            data[uname]["profile_pic"] = val.get("profile_pic", None)
        else:
            data[uname] = {"password": "", "profile_pic": None}

    return data

users = load_users()

def save_users():
    # Always read the latest users before writing
    if os.path.exists(USERS_FILE):
        try:
            with open(USERS_FILE, 'r') as f:
                existing = json.load(f)
        except:
            existing = {}
    else:
        existing = {}

    # Merge in-memory `users` into existing to prevent overwriting
    for uname, info in users.items():
        existing[uname] = info

    with open(USERS_FILE, 'w') as f:
        json.dump(existing, f, indent=4)

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
# Load old posts from posts.json safely
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
    # Only set uploader to Unknown if username is missing in users
    if uploader_name not in users:
        uploader_name = "Unknown"
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
# Corrected delete_post route
# ----------------------------
@app.route('/delete_post/<filename>', methods=['POST'])
def delete_post(filename):
    if 'username' not in session:
        return redirect(url_for('login'))

    # Only allow admin to delete
    if session['username'] != ADMIN_USERNAME:
        return "Unauthorized", 403

    # Remove post from memory
    likes_dict.pop(filename, None)
    uploaders.pop(filename, None)
    image_urls.pop(filename, None)
    posts_data.pop(filename, None)

    # Update posts.json
    with open(POSTS_FILE, 'w') as f:
        json.dump(posts_data, f, indent=4)

    # Delete from S3
    try:
        s3.delete_object(Bucket=AWS_BUCKET_NAME, Key=filename)
    except Exception as e:
        print("Error deleting from S3:", e)

    return redirect(url_for('index'))

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
        profile_pics[user] = data.get("profile_pic") if data.get("profile_pic") else DEFAULT_PROFILE_PIC

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
# Upload profile picture route (with auto square crop)
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
        # Open the uploaded image
        img = Image.open(file)

        # Make it square
        width, height = img.size
        min_side = min(width, height)
        left = (width - min_side) / 2
        top = (height - min_side) / 2
        right = (width + min_side) / 2
        bottom = (height + min_side) / 2
        img = img.crop((left, top, right, bottom))

        # Optional: resize to a standard size, e.g., 128x128
        img = img.resize((128, 128))

        # Save to in-memory file
        img_bytes = io.BytesIO()
        img.save(img_bytes, format='PNG')
        img_bytes.seek(0)

        # Upload to S3
        filename = secure_filename(file.filename)
        s3.upload_fileobj(img_bytes, AWS_BUCKET_NAME, filename)
        profile_pic_url = f"https://{AWS_BUCKET_NAME}.s3.{AWS_REGION}.amazonaws.com/{filename}"

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

@app.route('/messages')
def messages_menu():
    if 'username' not in session:
        return redirect(url_for('login'))

    current_user = session['username']
    # List all users except current user
    other_users = [u for u in users.keys() if u != current_user]

    return render_template("messages_menu.html", other_users=other_users)

# ✅ Send a message
@app.route('/send_message', methods=['POST'])
def send_message():
    if 'username' not in session:
        return redirect(url_for('login'))

    sender = session['username']  # logged-in user
    receiver = request.form['receiver']  # who to send to
    content = request.form['content']    # the message

    conn = get_db_connection()
    conn.execute(
        "INSERT INTO messages (sender, receiver, content) VALUES (?, ?, ?)",
        (sender, receiver, content)
    )
    conn.commit()
    conn.close()

    return redirect(url_for('view_messages', username=receiver))


# ✅ View messages with a specific user
@app.route('/messages/<username>')
def view_messages(username):
    if 'username' not in session:
        return redirect(url_for('login'))

    current_user = session['username']

    conn = get_db_connection()
    messages = conn.execute(
        "SELECT * FROM messages WHERE (sender = ? AND receiver = ?) OR (sender = ? AND receiver = ?) ORDER BY timestamp",
        (current_user, username, username, current_user)
    ).fetchall()
    conn.close()

    return render_template("messages.html", messages=messages, other_user=username)

# ----------------------------
# Run app
# ----------------------------
if __name__ == '__main__':
    init_db()
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=True)
