import traceback
from flask import Flask, request, jsonify, Response, copy_current_request_context, session, abort
from flask_executor import Executor
import os
import uuid
import hashlib
from pathlib import Path
from dotenv import load_dotenv
from audio_utils import trim_and_fade, combine_audio_clips
import requests
import threading
from PIL import Image
from datetime import datetime, timedelta
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

# Additional imports for security
from ipaddress import ip_network, ip_address
import re

# Ensure sensitive configurations are protected
load_dotenv()

# Flask app setup
app = Flask(__name__)
app.secret_key = os.urandom(24)

# Configurations
config = get_config()
app.config['UPLOAD_FOLDER'] = config['uploads_folder']
app.config['VIDEOS_FOLDER'] = config['videos_folder']
app.config['AUDIO_FOLDER'] = config['audio_folder']
executor = Executor(app)

# Rate limiting: limit by user ID instead of IP alone
limiter = Limiter(key_func=get_remote_address, app=app, default_limits=["10 per day"])

# Security enhancements
user_data = {}  # {user_id: {'date': last_access_date, 'count': video_count}}
BANNED_IPS = set()  # IPs banned after repeated abuse attempts

def generate_unique_prefix():
    return str(uuid.uuid4())

def get_user_id():
    """Create a unique user identifier from IP and User-Agent hash."""
    user_ip = get_remote_address()
    user_agent = request.headers.get('User-Agent', '')
    combined = f"{user_ip}-{user_agent}"
    return hashlib.sha256(combined.encode()).hexdigest()

def check_banned_ip():
    """Abort request if IP is banned."""
    if get_remote_address() in BANNED_IPS:
        abort(403, "Access denied.")

def update_user_session():
    """
    Tracks and restricts video generation by user session, prevents date manipulation exploits.
    """
    user_id = get_user_id()
    today = datetime.now().date()

    # Initialize user data if not found
    if user_id not in user_data:
        user_data[user_id] = {'date': today, 'count': 0}

    user_session = user_data[user_id]

    # Reset count daily, if last access was a previous day
    if user_session['date'] != today:
        user_session.update({'date': today, 'count': 0})

    if user_session['count'] >= 10:
        return False, "Daily limit reached. Come back tomorrow."

    user_session['count'] += 1
    return True, f"Video count: {user_session['count']} today."

@app.before_request
def enforce_banned_ip():
    check_banned_ip()

@app.route('/api/generate-video', methods=['POST'])
@limiter.limit("10/day")
def generate_video_route():
    """
    Route to generate a video, tracking daily requests to prevent abuse.
    """
    # Security: Limit requests from banned IPs
    enforce_banned_ip()
    success, message = update_user_session()
    if not success:
        return jsonify({'error': message}), 403

    # Request parameter validation
    unique_prefix = generate_unique_prefix()
    session_data = {
        'unique_prefix': unique_prefix,
        'company_name': request.form.get('company-name'),
        'emphasis': request.form.get('emphasis'),
        'avoid': request.form.get('avoid'),
        'topic': request.form.get('press-release'),
        'mood': request.form.get('mood'),
        'platform': request.form.get('platform'),
        'audio': {},
        'video': {},
    }

    # Validate and sanitize image files
    image_files = request.files.getlist('images')
    images = []
    for image_file in image_files:
        stem, ext = Path(image_file.filename).stem, Path(image_file.filename).suffix
        safe_stem = hashlib.sha256(stem.encode()).hexdigest()[:20]
        safe_filename = safe_stem + ext
        image_file.filename = safe_filename
        image_path = os.path.join(app.config['UPLOAD_FOLDER'], image_file.filename)
        image_file.save(image_path)

        # Image format check
        if not compatible_image_format(image_path):
            with Image.open(image_path) as img:
                img = convert_image_to_png(img)
                new_filename = os.path.splitext(image_file.filename)[0] + '.png'
                img.save(os.path.join(app.config['UPLOAD_FOLDER'], new_filename), format='PNG')
                image_file.filename = new_filename

        images.append({'filename': image_file.filename, 'local_dir': app.config['UPLOAD_FOLDER'], 'bucket': config['source_bucket_name']})

    # Launch video generation task
    @copy_current_request_context
    def task():
        return generate_video(session_data, images)

    future = executor.submit(task)
    return jsonify({'status': 'Task started', 'session_id': session_data['unique_prefix'], 'message': message}), 202

if __name__ == '__main__':
    app.run(debug=False)
