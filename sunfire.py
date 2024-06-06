import traceback
from flask import Flask, request, jsonify, Response, copy_current_request_context
from flask_executor import Executor
import os
import uuid
from dotenv import load_dotenv
from audio_utils import trim_and_fade, combine_audio_clips
from s3_utils import get_s3_client, upload_images_from_disk_to_s3, upload_audio_from_disk_to_s3
from openai_utils import get_openai_client, describe_and_recommend, create_narration, generate_music_prompt
import requests
from PIL import Image
from image_utils import modify_image, compatible_image_format, convert_image_to_png, get_platform_specs
from messaging_utils import message_manager, logger
from elevenlabs_utils import get_elevenlabs_client, get_voice_tone_data, find_voice, generate_audio_narration
from suno_utils import make_music


app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = 'uploads/'
app.config['VIDEOS_FOLDER'] = 'videos/'
app.config['AUDIO_FOLDER'] = 'audio/'
executor = Executor(app)


# Set up environment
load_dotenv()

SOURCE_BUCKET_NAME = 'sunfire-source-bucket'
DESTINATION_BUCKET_NAME = 'sunfire-destination-bucket'
API_GATEWAY_URL = 'https://0h8a50ruye.execute-api.us-east-1.amazonaws.com/sunfire-generate-video-from-images'


def generate_unique_prefix():
    return str(uuid.uuid4())


def call_api_gateway(session_data):
    # scheme = request.headers.get('X-Forwarded-Proto', request.scheme)
    # host = request.headers.get('Host', request.host)
    callback_url = "http://54.166.183.35/api/video-callback"
    session_data['callback_url'] = callback_url
    payload = session_data
    response = requests.post(API_GATEWAY_URL, json=payload)
    if response.status_code == 200:
        return response
    else:
        return None


def modify_images(session_data, images):
    modified_images = images
    for image in modified_images:
        original_name = image['filename']
        local_dir = image['local_dir']
        new_name = "modified"+original_name
        pad_color = image['color']
        modify_image(local_dir+original_name,
                     session_data['target_width'],
                     session_data['target_height'],
                     pad_color,
                     local_dir+new_name)
        image['filename'] = new_name
    return modified_images


def initialize_clients():
    session_data = {'clients': {}}

    try:
        s3 = get_s3_client()
        if not s3:
            raise RuntimeError("S3 client initialization returned an invalid object")
        session_data['clients']['s3'] = s3
    except Exception as e:
        raise RuntimeError(f"Failed to initialize S3 client: {e}")

    try:
        openai = get_openai_client()
        if not openai:
            raise RuntimeError("OpenAI client initialization returned an invalid object")
        session_data['clients']['openai'] = openai
    except Exception as e:
        raise RuntimeError(f"Failed to initialize OpenAI client: {e}")

    try:
        elevenlabs = get_elevenlabs_client()
        if not elevenlabs:
            raise RuntimeError("Voice Generation client initialization returned an invalid object")
        session_data['clients']['elevenlabs'] = elevenlabs
    except Exception as e:
        raise RuntimeError(f"Failed to initialize Voice Generation client: {e}")

    return session_data


def process_images(session_data, images):
    s3 = session_data['clients']['s3']
    openai = session_data['clients']['openai']
    try:
        images = upload_images_from_disk_to_s3(s3, images, session_data['unique_prefix'])
        logger(session_data['unique_prefix'], 'log', 'Launching Image Analysis...')
        images = describe_and_recommend(session_data['unique_prefix'], openai, images, s3.generate_presigned_url)

        for image in images:
            print(f"Image: {image['filename']}")
            print(f"Description: {image['description']}")

        logger(session_data['unique_prefix'], 'log', 'Modifying Images...')
        modified_images = modify_images(session_data, images)

        logger(session_data['unique_prefix'], 'log', 'Uploading Images to the cloud...')
        modified_images = upload_images_from_disk_to_s3(s3, modified_images, session_data['unique_prefix'])

        s3_keys = [{'bucket': item['bucket'], 'key': item['s3_key']} for item in modified_images]

        video_data = {'duration': 30, 'fps': 24, 'aspect_ratio': session_data['video']['aspect_ratio']}
        session_data['video'] = video_data
        session_data['images'] = modified_images
        session_data['s3_objects'] = s3_keys
        session_data['write_bucket'] = DESTINATION_BUCKET_NAME

        return session_data
    except Exception as e:
        raise RuntimeError(f"Error in image processing: {e}")


def generate_narrative(session_data):
    openai = session_data['clients']['openai']
    elevenlabs = session_data['clients']['elevenlabs']
    try:
        session_data['audio'] = {
            'clips': {'voice': None, 'music': None, 'combined': None},
            'bucket': SOURCE_BUCKET_NAME,
            'narration_script': "",
            'local_dir': session_data['audio']['local_dir']
        }

        logger(session_data['unique_prefix'], 'log', 'Generating the narration script...')
        narration_script = create_narration(openai, session_data)
        print("Script: ", narration_script)
        session_data['audio']['narration_script'] = narration_script

        logger(session_data['unique_prefix'], 'log', 'Choosing a voice...')
        tone, age_gender = session_data['tone_age_gender'].split(':')
        age, gender = age_gender.split()
        voice = find_voice(tone, age, gender)
        logger(session_data['unique_prefix'], 'log', f"Your narrator is: {voice['name']}")
        session_data['voice'] = voice

        logger(session_data['unique_prefix'], 'log', 'Generating audio narration...')
        new_audio_clip = generate_audio_narration(elevenlabs, session_data)
        session_data['audio']['clips']['voice'] = new_audio_clip

        return session_data
    except Exception as e:
        raise RuntimeError(f"Error in narrative section: {e}")


def generate_music(session_data):
    openai = session_data['clients']['openai']
    try:
        logger(session_data['unique_prefix'], 'log', 'Designing Music...')
        music_prompt = generate_music_prompt(openai, session_data)
        logger(session_data['unique_prefix'], 'log', music_prompt)

        logger(session_data['unique_prefix'], 'log', 'Generating Music...')
        clip = make_music(session_data, music_prompt)

        logger(session_data['unique_prefix'], 'log', 'Making Adjustments...')
        clip = trim_and_fade(session_data, clip)
        session_data['audio']['clips']['music'] = clip

        return session_data
    except Exception as e:
        raise RuntimeError(f"Error in music section: {e}")


def combine_audio(session_data):
    s3 = session_data['clients']['s3']
    try:
        logger(session_data['unique_prefix'], 'log', 'Mixing Audio...')
        combined_clips = combine_audio_clips(session_data)
        session_data['audio']['clips']['combined'] = combined_clips
        logger(session_data['unique_prefix'], 'log', 'Audio Mixing Complete')

        logger(session_data['unique_prefix'], 'log', 'Uploading Audio to the cloud...')
        session_data['audio'] = upload_audio_from_disk_to_s3(s3, session_data['audio'], session_data['unique_prefix'])

        return session_data
    except Exception as e:
        raise RuntimeError(f"Error combining or uploading audio: {e}")


def handoff_to_lambda(session_data):
    try:
        logger(session_data['unique_prefix'], 'log', 'Generating the video...')
        api_response = call_api_gateway(session_data)
        if api_response:
            return jsonify({'message': 'Video generation initiated'}), 200
        else:
            return jsonify({'error': 'Video generation failed'}), 500
    except Exception as e:
        raise RuntimeError(f"Error in hand-off to Lambda: {e}")


def generate_video(session_data, images):
    from flask import current_app
    with app.app_context():
        try:
            print('Executing the background')

            session_data = initialize_clients()

            print('Processing Images...')
            session_data = process_images(session_data, images)
            session_data = generate_narrative(session_data)
            session_data = generate_music(session_data)
            session_data = combine_audio(session_data)

            return handoff_to_lambda(session_data)

        except Exception as e:
            print(f"Error in generate_video: {str(e)}")
            print(traceback.format_exc())
            logger(session_data['unique_prefix'], 'log', 'ERROR: video generation failed')
            # endregion

#############################################################################################################
#############################################################################################################
#############################################################################################################


@app.route('/api/generate-video', methods=['POST'])
def generate_video_route():
    print('Data Received.  Examining data...')
    unique_prefix = generate_unique_prefix()
    logger(unique_prefix, 'log', 'Data Received.  Examining data...')
    session_data = {
        'unique_prefix': unique_prefix,
        'company_name': request.form.get('company-name'),
        'company_url': request.form.get('company-url'),
        'topic': request.form.get('press-release'),
        'tone_age_gender': request.form.get('tone_age_gender'),
        'mood': request.form.get('mood'),
        'platform': request.form.get('platform'),
        'audio': {},
        'video': {}
    }
    (session_data['target_width'],
     session_data['target_height'],
     session_data['video']['aspect_ratio']) = (get_platform_specs(session_data['platform']))

    # Create session-dependant directories
    upload_folder = os.path.join(app.config['UPLOAD_FOLDER'], session_data['unique_prefix']) + '/'
    os.makedirs(upload_folder, exist_ok=True)
    videos_folder = os.path.join(app.config['VIDEOS_FOLDER'], session_data['unique_prefix']) + '/'
    os.makedirs(videos_folder, exist_ok=True)
    audio_folder = os.path.join(app.config['AUDIO_FOLDER'], session_data['unique_prefix']) + '/'
    os.makedirs(audio_folder, exist_ok=True)
    session_data['audio']['local_dir'] = audio_folder

    # Get the uploaded images from the request
    image_files = request.files.getlist('images')
    print("Image Files:", image_files)
    for image_file in image_files:
        image_path = os.path.join(upload_folder, image_file.filename)
        image_file.save(image_path)
        if not compatible_image_format(image_path):
            with Image.open(image_path) as img:
                img = convert_image_to_png(img)
                new_filename = os.path.splitext(image_file.filename)[0] + '.png'
                file_path = os.path.join(upload_folder, new_filename)
                img.save(file_path, format='PNG')
                image_file.filename = new_filename

    # Keep track of image attributes
    images = []
    for image_file in image_files:
        images.append(
            {'filename': image_file.filename,
             'local_dir': upload_folder,
             'bucket': SOURCE_BUCKET_NAME})

    @copy_current_request_context
    def task():
        return generate_video(session_data, images)

    future = executor.submit(task)
    app.logger.debug('Task submitted: %s', future)
    return jsonify({'status': 'Task started', 'session_id': session_data['unique_prefix']}), 202


@app.route('/api/video-callback', methods=['POST'])
def video_callback():
    print("Got a call back!")
    # Retrieve the video URL from the callback data
    # video_url = request.get_json().get('video_url')
    print(f"Body: {request.data}")

    if not request.is_json:
        return jsonify({"error": "Invalid content type"}), 400

    data = request.get_json()
    print(f"JSON data: {data}")
    session_data = data.get('session_data')
    video_url = session_data.get('video_url')

    if video_url:
        # Emit the video URL to all connected clients
        logger(session_data['unique_prefix'], 'video', video_url)
    # Process the data here
    return jsonify({"message": "Callback received", "data": data}), 200


@app.route('/api/get_tones_data', methods=['GET'])
def get_tones_data():
    voice_tone_data = get_voice_tone_data()
    return jsonify(voice_tone_data)


@app.route('/api/messages')
def stream_messages():
    return Response(message_manager(), mimetype='text/event-stream')


if __name__ == '__main__':
    app.run(debug=True)
