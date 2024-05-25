from flask import Flask, request, jsonify, Response
import os
from dotenv import load_dotenv
from s3_utils import get_s3_client, upload_images_from_disk_to_s3, upload_audio_from_disk_to_s3
from openai_utils import get_openai_client, describe_and_recommend, create_narration
import requests
from PIL import Image
from image_utils import modify_image, compatible_image_format, convert_image_to_png, get_platform_specs
from messaging_utils import message_manager, logger
from elevenlabs_utils import get_elevenlabs_client, get_voice_tone_data, find_voices, text_to_speech
app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = 'uploads/'
app.config['VIDEOS_FOLDER'] = 'videos/'
app.config['AUDIO_FOLDER'] = 'audio/'

# Set up environment
load_dotenv()

SOURCE_BUCKET_NAME = 'sunfire-source-bucket'
DESTINATION_BUCKET_NAME = 'sunfire-destination-bucket'
API_GATEWAY_URL = 'https://0h8a50ruye.execute-api.us-east-1.amazonaws.com/sunfire-generate-video-from-images'


def call_api_gateway(session_data):
    # scheme = request.headers.get('X-Forwarded-Proto', request.scheme)
    # host = request.headers.get('Host', request.host)
    callback_url = "http://54.166.183.35/api/video-callback"
    session_data['callback_url'] = callback_url
    print("CALLBACK: ", callback_url)
    payload = session_data
    response = requests.post(API_GATEWAY_URL, json=payload)
    print(response)
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


@app.route('/api/generate-video', methods=['POST'])
def generate_video():
    #######################################################################
    #                          INITIALIZATION                             #
    #######################################################################
    # region Initialization

    # Initialize S3 client
    s3 = get_s3_client()

    # Initialize OpenAI client
    openai = get_openai_client()
    print('Data Received.  Examining data...')
    logger('log', 'Data Received.  Examining data...')
    session_data = {
        'company_name': request.form.get('company-name'),
        'company_url': request.form.get('company-url'),
        'topic': request.form.get('press-release'),
        'tone_age_gender': request.form.get('tone_age_gender'),
        'mood': request.form.get('mood'),
        'platform': request.form.get('platform')
    }
    (session_data['target_width'],
     session_data['target_height'],
     aspect_ratio) = (get_platform_specs(session_data['platform']))

    # Get the uploaded images from the request
    image_files = request.files.getlist('images')
    print("Image Files:", image_files)
    # endregion

    #######################################################################
    #                         IMAGE PROCESSING                            #
    #######################################################################
    # region Image Processing

    for image_file in image_files:
        image_path = os.path.join(app.config['UPLOAD_FOLDER'], image_file.filename)
        image_file.save(image_path)
        if not compatible_image_format(image_path):
            with Image.open(image_path) as img:
                img = convert_image_to_png(img)
                new_filename = os.path.splitext(image_file.filename)[0] + '.png'
                file_path = os.path.join(app.config['UPLOAD_FOLDER'], new_filename)
                img.save(file_path, format='PNG')
                image_file.filename = new_filename

    # Keep track of image attributes
    images = []
    for image_file in image_files:
        images.append(
            {'filename': image_file.filename,
             'local_dir': app.config['UPLOAD_FOLDER'],
             'bucket': SOURCE_BUCKET_NAME})

    # Upload images to S3
    images = upload_images_from_disk_to_s3(s3, images)
    print("S3 Keys:", [item["s3_key"] for item in images])

    # Analyze our images
    logger('log', 'Launching Image Analysis...')
    images = describe_and_recommend(openai, images, s3.generate_presigned_url)

    for image in images:
        print(f"Image: {image['filename']}")
        print(f"S3: {image['s3_key']}")
        print(f"Description: {image['description']}")

    # Modify the images according to the AI suggestions
    logger('log', 'Modifying Images...')
    modified_images = modify_images(session_data, images)

    logger('log', 'Uploading Images to the cloud...')
    # Upload images to S3
    modified_images = upload_images_from_disk_to_s3(s3, modified_images)

    s3_keys = []
    for item in modified_images:
        s3_keys.append({'bucket': item['bucket'], 'key': item['s3_key']})

    # Define video parameters
    video_data = {
        'duration': 30,
        'fps': 24,
        'aspect_ratio': aspect_ratio,
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

    # Generate the narrative for the video
    logger('log', 'Generating the narration script...')
    narration_script = create_narration(openai, session_data)
    print("Script: ",narration_script)
    session_data['narration_script'] = narration_script

    logger('log', 'Choosing a voice...')
    tone, age_gender = session_data['tone_age_gender'].split(':')
    age, gender = age_gender.split()
    voice = find_voices(tone, age, gender)[0]
    logger('log', f'Your narrator is: {voice['name']}')
    session_data['voice'] = voice
    elevenlabs = get_elevenlabs_client()
    session_data['audio'] = {
        'clips': [],
        'bucket': SOURCE_BUCKET_NAME,
        'local_dir': app.config['AUDIO_FOLDER']
    }
    logger('log', f'Generating audio narration...')
    new_audio_clip = text_to_speech(elevenlabs, session_data)
    session_data['audio']['clips'].append(new_audio_clip)

    logger('log', 'Uploading Images to the cloud...')
    session_data['audio'] = upload_audio_from_disk_to_s3(s3, session_data['audio'])
    # endregion

    return jsonify({'message': 'Video generation initiated'}), 200

    #######################################################################
    #                           MUSIC SECTION                             #
    #######################################################################
    # region Music Section
    # endregion

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
    # endregion


@app.route('/api/video-callback', methods=['POST'])
def video_callback():
    print("Got a call back!")
    # Retrieve the video URL from the callback data
    # video_url = request.get_json().get('video_url')
    print(f"Headers: {request.headers}")
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
