from flask import Flask, request, redirect, url_for, render_template, jsonify, session
import os
import json  # Added for persistent users

app = Flask(__name__)
app.secret_key = 'supersecretkey'  # Needed for sessions

UPLOAD_FOLDER = 'static/uploads'
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

# Global likes dictionary
likes_dict = {}

# ----------------------------
# Persistent users
# ----------------------------
USERS_FILE = 'users.json'

if os.path.exists(USERS_FILE):
    with open(USERS_FILE, 'r') as f:
        users = json.load(f)
else:
    users = {}

# Maps each filename to the username who uploaded it
uploaders = {}

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
# Upload route
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
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], file.filename)
        file.save(filepath)
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
    app.run(debug=True)
