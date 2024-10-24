import traceback
from flask import Flask, request, jsonify, Response, copy_current_request_context, session
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
import hashlib

# noinspection PyUnresolvedReferences
import pillow_avif
from config_utils import get_config
from image_utils import modify_image, compatible_image_format, convert_image_to_png, get_platform_specs
from messaging_utils import message_manager, logger
from cloud_storage import get_cloud_storage_client, upload_images_from_disk_to_cloud, upload_audio_from_disk_to_cloud
from text_to_text import get_text_to_text_client, describe_and_recommend, create_narration, generate_music_prompt
from text_to_voice import get_text_to_voice_client, get_voice_tone_data, find_voice, generate_audio_narration
from text_to_music import get_text_to_music_client, make_music

app = Flask(__name__)
app.secret_key = os.urandom(24)  # Secret key for session encryption

# Load the YAML file
config = get_config()

app.config['UPLOAD_FOLDER'] = config['uploads_folder']
app.config['VIDEOS_FOLDER'] = config['videos_folder']
app.config['AUDIO_FOLDER'] = config['audio_folder']
executor = Executor(app)

# Limiter for rate limiting API usage
limiter = Limiter(
    get_remote_address,
    app=app,
    default_limits=["10 per day"],  # 10 requests per user per day
)

# Set up environment
load_dotenv()

SOURCE_BUCKET_NAME = config['source_bucket_name']
DESTINATION_BUCKET_NAME = config['destination_bucket_name']
API_GATEWAY_URL = config['api_gateway_url']
SERVER_ADDR = config['server_addr']

# Thread-safe results storage
video_urls = {}
video_urls_lock = threading.Lock()

# User data tracking: {user_id: {date: last_access_date, count: number_of_videos_generated}}
user_data = {}

def generate_unique_prefix():
    return str(uuid.uuid4())

def get_user_id():
    """
    Generates a unique user ID based on the requester's IP address.
    In a production environment, this could be extended to include other data.
    """
    user_ip = get_remote_address()
    user_agent = request.headers.get('User-Agent', '')
    raw_string = f"{user_ip}-{user_agent}"
    user_id = hashlib.sha256(raw_string.encode()).hexdigest()
    return user_id

def update_user_session():
    """
    Tracks the number of video generations per user.
    Resets the count if the user comes the next day.
    """
    user_id = get_user_id()
    today = datetime.now().date()

    if user_id not in user_data:
        user_data[user_id] = {'date': today, 'count': 0}

    user_session = user_data[user_id]

    # Reset count if it's a new day
    if user_session['date'] != today:
        user_session['date'] = today
        user_session['count'] = 0

    if user_session['count'] >= 10:
        return False, "Limit reached. You have generated 10 videos today. Come back tomorrow."
    
    user_session['count'] += 1
    return True, f"You have generated {user_session['count']} videos today."

def call_api_gateway(session_data):
    """
    Calls the API gateway with the given session data.
    """
    callback_url = f"http://{SERVER_ADDR}/api/video-callback"
    session_data['callback_url'] = callback_url
    payload = session_data
    response = requests.post(API_GATEWAY_URL, json=payload)
    if response.status_code == 200:
        return response
    else:
        return None

def modify_images(target_width, target_height, images):
    """
    Modifies the images in the list of images.
    """
    modified_images = images
    for image in modified_images:
        original_name = image['filename']
        local_dir = image['local_dir']
        new_name = "modified" + original_name
        pad_color = image['color']
        modify_image(local_dir + original_name,
                     target_width,
                     target_height,
                     pad_color,
                     local_dir + new_name)
        image['filename'] = new_name
    return modified_images

def initialize_clients():
    """
    Initializes the clients for the API gateway.
    """
    clients = {}

    # Initialize S3 client
    try:
        cloud_storage = get_cloud_storage_client()
        if not cloud_storage:
            raise RuntimeError("cloud_storage client initialization returned an invalid object")
        clients['cloud_storage'] = cloud_storage
    except Exception as e:
        raise RuntimeError(f"Failed to initialize cloud_storage client: {e}")

    # Initialize OpenAI client
    try:
        text_to_text = get_text_to_text_client()
        if not text_to_text:
            raise RuntimeError("text_to_text client initialization returned an invalid object")
        clients['text_to_text'] = text_to_text
    except Exception as e:
        raise RuntimeError(f"Failed to initialize text_to_text client: {e}")

    # Initialize Voice Generation client
    try:
        text_to_voice = get_text_to_voice_client()
        if not text_to_voice:
            raise RuntimeError("Voice Generation client initialization returned an invalid object")
        clients['text_to_voice'] = text_to_voice
    except Exception as e:
        raise RuntimeError(f"Failed to initialize Voice Generation client: {e}")

    # Initialize Music Generation client
    try:
        text_to_music = get_text_to_music_client()
        if not text_to_music:
            raise RuntimeError("Music Generation client initialization returned an invalid object")
        clients['text_to_music'] = text_to_music
    except Exception as e:
        raise RuntimeError(f"Failed to initialize Music Generation client: {e}")

    return clients

def process_images(session_id, clients, target_width, target_height, aspect_ratio, images):
    """
    Processes the images in the list of images.
    """
    cloud_storage = clients['cloud_storage']
    text_to_text = clients['text_to_text']
    try:
        images = upload_images_from_disk_to_cloud(cloud_storage, images, session_id)
        logger(session_id, 'log', 'Launching Image Analysis...')
        images = describe_and_recommend(session_id, text_to_text, images, cloud_storage.generate_presigned_url)

        logger(session_id, 'log', 'Modifying Images...')
        modified_images = modify_images(target_width, target_height, images)

        logger(session_id, 'log', 'Uploading Images to the cloud...')
        modified_images = upload_images_from_disk_to_cloud(cloud_storage, modified_images, session_id)

        video_data = {'duration': 30, 'fps': 24, 'aspect_ratio': aspect_ratio}

        return video_data, modified_images, DESTINATION_BUCKET_NAME
    except Exception as e:
        raise RuntimeError(f"Error in image processing: {e}")

def generate_video(session_data, images):
    """
    Generates a video based on the given session data and images.
    """
    with (app.app_context()):
        try:
            session_data['clients'] = initialize_clients()

            session_data['video'], session_data['images'], session_data['write_bucket'] = process_images(
                session_data['unique_prefix'], session_data['clients'],
                session_data['target_width'], session_data['target_height'],
                session_data['video']['aspect_ratio'], images)

            session_data = generate_narrative(session_data)
            session_data['audio'] = generate_music(session_data['unique_prefix'], session_data['clients'],
                                                   session_data['mood'], session_data['topic'], session_data['audio'])
            session_data['audio'] = combine_audio(session_data['unique_prefix'],
                                                  session_data['clients']['cloud_storage'], session_data['audio'])

            session_data['clients'] = {}  # Clear out clients before handing off to Lambda
            return handoff_to_lambda(session_data)

        except Exception as e:
            print(f"Error in generate_video: {str(e)}")
            print(traceback.format_exc())
            logger(session_data['unique_prefix'], 'error', 'video generation failed - ' + str(e))

@app.route('/api/generate-video', methods=['POST'])
@limiter.limit("10/day")
def generate_video_route():
    """
    Route for generating a video based on the provided data.
    """
    success, message = update_user_session()
    if not success:
        return jsonify({'error': message}), 403

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

    session_data['target_width'], session_data['target_height'], session_data['video']['aspect_ratio'] = get_platform_specs(
        session_data['platform'])

    upload_folder = os.path.join(app.config['UPLOAD_FOLDER'], session_data['unique_prefix']) + '/'
    os.makedirs(upload_folder, exist_ok=True)
    videos_folder = os.path.join(app.config['VIDEOS_FOLDER'], session_data['unique_prefix']) + '/'
    os.makedirs(videos_folder, exist_ok=True)
    audio_folder = os.path.join(app.config['AUDIO_FOLDER'], session_data['unique_prefix']) + '/'
    os.makedirs(audio_folder, exist_ok=True)
    session_data['audio']['local_dir'] = audio_folder

    image_files = request.files.getlist('images')
    images = []
    for image_file in image_files:
        stem = Path(image_file.filename).stem
        ext = Path(image_file.filename).suffix
        safe_stem = hashlib.sha256(stem.encode()).hexdigest()[:20]
        safe_filename = safe_stem + ext
        image_file.filename = safe_filename

        image_path = os.path.join(upload_folder, image_file.filename)
        image_file.save(image_path)
        if not compatible_image_format(image_path):
            try:
                with Image.open(image_path) as img:
                    img = convert_image_to_png(img)
                    new_filename = os.path.splitext(image_file.filename)[0] + '.png'
                    file_path = os.path.join(upload_folder, new_filename)
                    img.save(file_path, format='PNG')
                    image_file.filename = new_filename
            except Exception as e:
                print(f"Error converting image: {str(e)}")
                continue

        images.append({'filename': image_file.filename, 'local_dir': upload_folder, 'bucket': SOURCE_BUCKET_NAME})

    @copy_current_request_context
    def task():
        return generate_video(session_data, images)

    future = executor.submit(task)
    app.logger.debug('Task submitted: %s', future)
    return jsonify({'status': 'Task started', 'session_id': session_data['unique_prefix'], 'message': message}), 202


if __name__ == '__main__':
    app.run(debug=True)
