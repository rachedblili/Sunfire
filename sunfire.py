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


def generate_video(session_data, images):
    from flask import current_app
    with app.app_context():
        try:
            print('Executing the background')

            #######################################################################
            #                          INITIALIZATION                             #
            #######################################################################
            # region Initialization

            # Initialize S3 client
            s3 = get_s3_client()

            # Initialize OpenAI client
            openai = get_openai_client()

            # Initialize Voice Generation client
            elevenlabs = get_elevenlabs_client()

            # endregion

            #######################################################################
            #                         IMAGE PROCESSING                            #
            #######################################################################
            # region Image Processing

            print('Processing Images...')

            # Upload images to S3
            images = upload_images_from_disk_to_s3(s3, images, session_data['unique_prefix'])

            # Analyze our images
            logger('log', 'Launching Image Analysis...')
            images = describe_and_recommend(openai, images, s3.generate_presigned_url)

            for image in images:
                print(f"Image: {image['filename']}")
                print(f"Description: {image['description']}")

            # Modify the images according to the AI suggestions
            logger('log', 'Modifying Images...')
            modified_images = modify_images(session_data, images)

            logger('log', 'Uploading Images to the cloud...')
            # Upload images to S3
            modified_images = upload_images_from_disk_to_s3(s3, modified_images, session_data['unique_prefix'])

            s3_keys = []
            for item in modified_images:
                s3_keys.append({'bucket': item['bucket'], 'key': item['s3_key']})

            # Define video parameters
            video_data = {
                'duration': 30,
                'fps': 24,
                'aspect_ratio': session_data['video']['aspect_ratio'],
            }
            session_data['video'] = video_data
            session_data['images'] = modified_images
            session_data['s3_objects'] = s3_keys
            session_data['write_bucket'] = DESTINATION_BUCKET_NAME
            # endregion

            #######################################################################
            #                       NARRATIVE SECTION                             #
            #######################################################################
            # region Narrative Section

            # Prepare the data structure that will house audio data
            session_data['audio'] = {
                'clips': {'voice': None, 'music': None, 'combined': None},
                'bucket': SOURCE_BUCKET_NAME,
                'narration_script': "",
                'local_dir': session_data['audio']['local_dir']
            }

            # Generate the narrative for the video
            logger('log', 'Generating the narration script...')
            narration_script = create_narration(openai, session_data)
            print("Script: ", narration_script)
            session_data['audio']['narration_script'] = narration_script

            logger('log', 'Choosing a voice...')
            tone, age_gender = session_data['tone_age_gender'].split(':')
            age, gender = age_gender.split()
            voice = find_voice(tone, age, gender)
            logger('log', f'Your narrator is: {voice['name']}')
            session_data['voice'] = voice

            # Time to start generating audio

            logger('log', f'Generating audio narration...')
            new_audio_clip = generate_audio_narration(elevenlabs, session_data)
            session_data['audio']['clips']['voice'] = new_audio_clip

            # endregion

            #######################################################################
            #                           MUSIC SECTION                             #
            #######################################################################
            # region Music Section

            logger('log', f'Designing Music...')

            music_prompt = generate_music_prompt(openai, session_data)
            logger('log', music_prompt)

            logger('log', f'Generating Music...')
            clip = make_music(session_data, music_prompt)

            # Who knows how long the song is.  We need to trim it down and fade the last couple of seconds to silence.
            logger('log', f'Making Adjustments...')
            clip = trim_and_fade(session_data, clip)
            session_data['audio']['clips']['music'] = clip

            # endregion

            # Combine the audio clips
            logger('log', f'Mixing Audio...')
            combined_clips = combine_audio_clips(session_data)
            session_data['audio']['clips']['combined'] = combined_clips
            logger('log', f'Audio Mixing Complete')

            logger('log', 'Uploading Audio to the cloud...')
            session_data['audio'] = upload_audio_from_disk_to_s3(s3, session_data['audio'],)

            #######################################################################
            #                        HAND-OFF TO LAMBDA                           #
            #######################################################################
            # region Hand-off to Lambda

            # Call the API Gateway to process the video
            logger('log', 'Generating the video...')
            api_response = call_api_gateway(session_data)
            if api_response:
                return jsonify({'message': 'Video generation initiated'}), 200
            else:
                # Return an error response if the video generation failed
                return jsonify({'error': 'Video generation failed'}), 500
        except Exception as e:
            print(f"Error in generate_video: {str(e)}")
            print(traceback.format_exc())
            # endregion

#############################################################################################################
#############################################################################################################
#############################################################################################################


@app.route('/api/generate-video', methods=['POST'])
def generate_video_route():
    print('Data Received.  Examining data...')
    logger('log', 'Data Received.  Examining data...')
    unique_prefix = generate_unique_prefix()
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
    return jsonify({'status': 'Task started'}), 202


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
        logger('video', video_url)
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
