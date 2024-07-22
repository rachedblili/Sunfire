import traceback
from flask import Flask, request, jsonify, Response, copy_current_request_context
from flask_executor import Executor
import os
import uuid
import hashlib
from pathlib import Path
from dotenv import load_dotenv
from audio_utils import trim_and_fade, combine_audio_clips
import requests
from PIL import Image
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
# Load the YAML file
config = get_config()

app.config['UPLOAD_FOLDER'] = config['uploads_folder']
app.config['VIDEOS_FOLDER'] = config['videos_folder']
app.config['AUDIO_FOLDER'] = config['audio_folder']
executor = Executor(app)


# Set up environment
load_dotenv()

SOURCE_BUCKET_NAME = config['source_bucket_name']
DESTINATION_BUCKET_NAME = config['destination_bucket_name']
API_GATEWAY_URL = config['api_gateway_url']
SERVER_ADDR = config['server_addr']


def generate_unique_prefix():
    return str(uuid.uuid4())


def call_api_gateway(session_data):
    """
    Calls the API gateway with the given session data.

    Args:
        session_data (dict): The data to be sent to the API gateway.

    Returns:
        requests.Response: The response object if the request is successful (status code 200),
        None: If the request is unsuccessful.
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

    Args:
        target_width (int): The target width of the images.
        target_height (int): The target height of the images.
        images (list): The list of images to modify.

    Returns:
        list: The list of modified images.
    """
    modified_images = images
    for image in modified_images:
        original_name = image['filename']
        local_dir = image['local_dir']
        new_name = "modified"+original_name
        pad_color = image['color']
        modify_image(local_dir+original_name,
                     target_width,
                     target_height,
                     pad_color,
                     local_dir+new_name)
        image['filename'] = new_name
    return modified_images


def initialize_clients():
    """
    Initializes the clients for the API gateway.

    Returns:
        dict: A dictionary containing the initialized clients.
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

    Args:
        session_id (str): The ID of the session.
        clients (dict): A dictionary containing the initialized clients.
        target_width (int): The target width of the images.
        target_height (int): The target height of the images.
        aspect_ratio (float): The aspect ratio of the images.
        images (list): The list of images to process.

    Returns:
        tuple: A tuple containing the video data, the modified images, and the destination bucket name.
    """
    cloud_storage = clients['cloud_storage']
    text_to_text = clients['text_to_text']
    try:
        images = upload_images_from_disk_to_cloud(cloud_storage, images, session_id)
        logger(session_id, 'log', 'Launching Image Analysis...')
        images = describe_and_recommend(session_id, text_to_text, images, cloud_storage.generate_presigned_url)

        for image in images:
            print(f"Image: {image['filename']}")
            print(f"Description: {image['description']}")

        logger(session_id, 'log', 'Modifying Images...')
        modified_images = modify_images(target_width, target_height, images)

        logger(session_id, 'log', 'Uploading Images to the cloud...')
        modified_images = upload_images_from_disk_to_cloud(cloud_storage, modified_images, session_id)

        video_data = {'duration': 30, 'fps': 24, 'aspect_ratio': aspect_ratio}

        return video_data, modified_images, DESTINATION_BUCKET_NAME
    except Exception as e:
        raise RuntimeError(f"Error in image processing: {e}")


def generate_narrative(session_data):
    """
    Generates the narrative for the session.

    Args:
        session_data (dict): The session data.

    Returns:
        dict: The updated session data.
    """
    session_id = session_data['unique_prefix']
    text_to_text = session_data['clients']['text_to_text']
    text_to_voice = session_data['clients']['text_to_voice']
    try:
        session_data['audio'] = {
            'clips': {'voice': None, 'music': None, 'combined': None},
            'bucket': SOURCE_BUCKET_NAME,
            'narration_script': "",
            'local_dir': session_data['audio']['local_dir']
        }

        logger(session_id, 'log', 'Choosing a voice...')
        voice = find_voice(text_to_text, session_data['mood'], session_data['topic'])
        logger(session_id, 'log', f"Your narrator is: {voice['name']}")
        session_data['voice'] = voice

        logger(session_id, 'log', 'Generating the narration script...')
        narration_script = create_narration(text_to_text, session_data)
        print("Script: ", narration_script)
        session_data['audio']['narration_script'] = narration_script

        logger(session_id, 'log', 'Generating audio narration...')
        new_audio_clip = generate_audio_narration(text_to_voice, session_data['audio']['local_dir'],
                                                  session_data['voice'], session_data['audio']['narration_script'],
                                                  session_data['video']['duration'])
        session_data['audio']['clips']['voice'] = new_audio_clip

        return session_data
    except Exception as e:
        raise RuntimeError(f"Error in narrative section: {e}")


def generate_music(session_id, clients, mood, topic, audio_data):
    """
    Generates the music for the video.

    Args:
        session_id (str): The ID of the video.
        clients (dict): A dictionary containing the initialized clients.
        mood (str): The mood of the video.
        topic (str): The topic of the video.
        audio_data (dict): The audio data.

    Returns:
        dict: The updated audio data.
    """
    text_to_text = clients['text_to_text']
    save_dir = audio_data['local_dir']
    try:
        logger(session_id, 'log', 'Designing Music...')
        music_prompt = generate_music_prompt(text_to_text, mood, topic)
        logger(session_id, 'log', music_prompt)

        logger(session_id, 'log', 'Generating Music...')
        clip = make_music(clients, save_dir, music_prompt)

        logger(session_id, 'log', 'Making Adjustments...')
        clip = trim_and_fade(save_dir, clip)
        audio_data['clips']['music'] = clip

        return audio_data
    except Exception as e:
        raise RuntimeError(f"Error in music section: {e}")


def combine_audio(session_id, cloud_storage, audio_data):
    """
    Combines the audio clips into one.

    Args:
        session_id (str): The ID of the video.
        cloud_storage (dict): A dictionary containing the initialized clients.
        audio_data (dict): The audio data.

    Returns:
        dict: The updated audio data.
    """
    try:
        logger(session_id, 'log', 'Mixing Audio...')
        combined_clip = combine_audio_clips(audio_data)
        audio_data['clips']['combined'] = combined_clip
        logger(session_id, 'log', 'Audio Mixing Complete')

        logger(session_id, 'log', 'Uploading Audio to the cloud...')
        audio_data = upload_audio_from_disk_to_cloud(cloud_storage, audio_data, session_id)

        return audio_data
    except Exception as e:
        raise RuntimeError(f"Error combining or uploading audio: {e}")


def handoff_to_lambda(session_data):
    """
    Sends the session data to the Lambda function.

    Args:
        session_data (dict): The session data.

    Returns:
        tuple: A tuple containing the response and status code.
    """
    try:
        logger(session_data['unique_prefix'], 'log', 'Generating the video (please wait)...')
        api_response = call_api_gateway(session_data)
        if api_response:
            return jsonify({'message': 'Video generation initiated'}), 200
        else:
            return jsonify({'error': 'Video generation failed'}), 500
    except Exception as e:
        raise RuntimeError(f"Error in hand-off to Lambda: {e}")


def generate_video(session_data, images):
    """
    Generates a video based on the given session data and images.

    Args:
        session_data (dict): The session data containing information such as unique prefix, clients, target width, target height, video aspect ratio, and write bucket.
        images (list): The list of images to be processed.

    Returns:
        tuple: A tuple containing the response and status code. The response is a JSON object with a message indicating the status of the video generation. The status code is either 200 indicating successful video generation or 500 indicating a failure.

    Raises:
        RuntimeError: If there is an error in the video generation process, including errors in initializing clients, processing images, generating the narrative, generating music, combining audio, or handing off to Lambda.

    """
    with ((app.app_context())):
        try:
            print('Executing the background')

            session_data['clients'] = initialize_clients()

            print('Processing Images...')
            (session_data['video'],
             session_data['images'],
             session_data['write_bucket']) = process_images(session_data['unique_prefix'],
                                                            session_data['clients'],
                                                            session_data['target_width'],
                                                            session_data['target_height'],
                                                            session_data['video']['aspect_ratio'], images)
            session_data = generate_narrative(session_data)
            session_data['audio'] = generate_music(session_data['unique_prefix'],
                                                   session_data['clients'],
                                                   session_data['mood'],
                                                   session_data['topic'],
                                                   session_data['audio'])
            session_data['audio'] = combine_audio(session_data['unique_prefix'],
                                                  session_data['clients']['cloud_storage'],
                                                  session_data['audio'])

            # Before handing off to Lambda, clear out the client objects
            session_data['clients'] = {}
            # And clean up
            return handoff_to_lambda(session_data)

        except Exception as e:
            print(f"Error in generate_video: {str(e)}")
            print(traceback.format_exc())
            logger(session_data['unique_prefix'], 'error', 'video generation failed - ' + str(e))
            # endregion

#############################################################################################################
#############################################################################################################
#############################################################################################################


@app.route('/api/generate-video', methods=['POST'])
def generate_video_route():
    """
    Route for generating a video based on the provided data.

    This function is the route handler for the '/api/generate-video' endpoint. It is triggered when a POST request is made to this endpoint.

    Parameters:
    - None

    Returns:
    - A JSON response with a status message and the session ID if the task is successfully submitted.
    - A JSON response with an error message if there is an exception during the video generation process.

    Side Effects:
    - Creates session-dependent directories for storing uploaded images and audio files.
    - Saves the uploaded images to the session-dependent directories.
    - Converts any incompatible images to PNG format.
    - Keeps track of the image attributes.
    - Submits a task to generate the video using the provided session data and images.

    """
    print('Data Received.  Examining data...')
    unique_prefix = generate_unique_prefix()
    logger(unique_prefix, 'log', 'Data Received.  Examining data...')
    session_data = {
        'unique_prefix': unique_prefix,
        'company_name': request.form.get('company-name'),
        'emphasis': request.form.get('emphasis'),
        'avoid': request.form.get('avoid'),
        'topic': request.form.get('press-release'),
        # 'tone_age_gender': request.form.get('tone_age_gender'),
        'mood': request.form.get('mood'),
        'platform': request.form.get('platform'),
        'audio': {},
        'video': {},
        'text_to_text': config['text-to-text'],
        'image_to_text': config['image-to-text'],
        'text_to_voice': config['text-to-voice'],
        'text_to_music': config['text-to-music']
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
        # Clean up file names
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
                logger(unique_prefix, 'log', 'Got an incompatible image. Skipping it...')
                os.remove(image_path)
                continue

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
    """
    Handles the POST request to the '/api/video-callback' endpoint.

    This function is responsible for handling the callback from the video generation process. It retrieves the video URL from the callback data and emits it to all connected clients. The function also processes the data received in the request and returns a JSON response with a success message and the received data.

    Parameters:
    - None

    Returns:
    - A JSON response with a success message and the received data if the request is valid.
    - A JSON response with an error message and a 400 status code if the request is not in JSON format.

    """
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
    """
    Retrieves voice tone data using get_voice_tone_data function and returns it in JSON format.
    """
    voice_tone_data = get_voice_tone_data()
    return jsonify(voice_tone_data)


@app.route('/api/messages')
def stream_messages():
    """
    Defines the route '/api/messages' that streams messages to the client in text/event-stream format.
    """
    return Response(message_manager(), mimetype='text/event-stream')


if __name__ == '__main__':
    app.run(debug=True)
