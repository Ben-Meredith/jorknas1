from flask import Flask, request, redirect, url_for, render_template, jsonify
import os

app = Flask(__name__)
UPLOAD_FOLDER = 'static/uploads'
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

# Dictionary to store likes for each file
likes_dict = {}

@app.route('/')
def index():
    images = os.listdir(app.config['UPLOAD_FOLDER'])
    # Ensure each image has a like count
    for img in images:
        if img not in likes_dict:
            likes_dict[img] = 0
    return render_template('index.html', images=images, likes_dict=likes_dict)

@app.route('/upload', methods=['POST'])
def upload_file():
    if 'file' not in request.files:
        return redirect(url_for('index'))
    file = request.files['file']
    if file.filename == '':
        return redirect(url_for('index'))
    if file:
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], file.filename)
        file.save(filepath)
        likes_dict[file.filename] = 0  # initialize likes
    return redirect(url_for('index'))

# Route to handle likes
@app.route('/like/<filename>', methods=['POST'])
def like_image(filename):
    if filename in likes_dict:
        likes_dict[filename] += 1
        return jsonify({'likes': likes_dict[filename]})
    return jsonify({'error': 'File not found'}), 404

if __name__ == '__main__':
    app.run(debug=True)
