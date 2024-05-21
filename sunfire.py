from flask import Flask, request, jsonify, Response
import os
#import boto3
from s3_utils import get_s3_client, upload_images_to_s3, upload_images_from_disk_to_s3
from openai_utils import get_openai_client, describe_and_recommend, logger as openai_logger
import requests
import json
app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = 'uploads/'
app.config['VIDEOS_FOLDER'] = 'videos/'
from image_utils import modify_image

# Initialize message queue
message_queue = []

# Initialize S3 client
s3 = get_s3_client()
SOURCE_BUCKET_NAME = 'sunfire-source-bucket'
DESTINATION_BUCKET_NAME = 'sunfire-destination-bucket'
API_GATEWAY_URL = 'https://0h8a50ruye.execute-api.us-east-1.amazonaws.com/sunfire-generate-video-from-images'

client = get_openai_client()


def call_api_gateway(s3_keys, total_duration, fps, aspect_ratio, bucket):
    #callback_url = request.url_root + 'api/video-callback'
    scheme = request.headers.get('X-Forwarded-Proto', request.scheme)
    host = request.headers.get('Host', request.host)
    callback_url = "http://54.166.183.35/api/video-callback"
    print("CALLBACK: ",callback_url)
    payload = {
        's3_objects': s3_keys,
        'duration': total_duration,
        'fps': fps,
        'aspect_ratio': aspect_ratio,
        'output_bucket': bucket,
        'callback_url' : callback_url
    }
    response = requests.post(API_GATEWAY_URL, json=payload)
    print(response)
    if response.status_code == 200:
        return response
    else:
        return None


def modify_images(images):
    modified_images = images
    for image in modified_images:
        original_name = image['filename']
        local_dir = image['local_dir']
        new_name = "modified"+original_name
        full_spec = image['strategy']
        modify_image(local_dir+original_name,full_spec,local_dir+new_name)
        image['filename'] = new_name
    return(modified_images)

@app.route('/api/generate-video', methods=['POST'])
def generate_video():

    # Log headers
    print("Headers:", request.headers)

    # Attempt to log form data
    print("Form Data:", request.form)

    # Log files data
    print("Files Received:", request.files)
    # For JSON data (if you were sending JSON):
    if request.is_json:
        print("JSON Received:", request.get_json())

    # For non-JSON body contents (e.g., for form-data, which includes files)
    if request.data:
        print("Raw Data Received:", request.data)
    print("Generating a Video")
    # Get the uploaded images from the request
    image_files = request.files.getlist('images')
    print("Image Files:", image_files)

    for image_file in image_files:
        image_file.save(os.path.join(app.config['UPLOAD_FOLDER'], image_file.filename))

    # Keep track of image attributes
    images = []
    for image in image_files:
        images.append(
            {'filename' : image.filename, 
             'local_dir' : app.config['UPLOAD_FOLDER'],
             'bucket' : SOURCE_BUCKET_NAME})

    # Upload images to S3
    images = upload_images_from_disk_to_s3(s3,images)
    print("S3 Keys:",[item["s3_key"] for item in images])    


    # Analyze our images
    print("Launching Image Analysis...")
    images = describe_and_recommend(client, images,s3.generate_presigned_url)

    for image in images:
        print(f"Image: {image['filename']}")
        print(f"S3: {image['s3_key']}")
        print(f"Description: {image['description']}")
        print(f"Strategy: {image['strategy']}")

    # Modify the images according to the AI suggestions
    print("Modifying Images...")
    modified_images = modify_images(images)

    # Upload images to S3
    modified_images = upload_images_from_disk_to_s3(s3,modified_images)

    s3_keys = []
    for item in modified_images:
        s3_keys.append({'bucket': item['bucket'], 'key': item['s3_key']})

    print("FINAL S3 Keys:",s3_keys)    

    # Define video parameters
    total_duration = 10  # Total duration of the video
    fps = 24  # Frames per second
    aspect_ratio = '16:9'  # Aspect ratio of the video
    # Call the API Gateway to process the video
    api_response = call_api_gateway(
            s3_keys, total_duration, fps, 
            aspect_ratio, DESTINATION_BUCKET_NAME)
    if api_response['statusCode'] == 200:
        return jsonify({'message': 'Video generation initiated'}), 200
    else:
        # Return an error response if the video generation failed
        return jsonify({'error': 'Video generation failed'}), 500

@app.route('/api/video-callback', methods=['POST'])
def video_callback():
    print("Got a call back!")
    # Retrieve the video URL from the callback data
    #video_url = request.get_json().get('video_url')
    print(f"Headers: {request.headers}")
    print(f"Body: {request.data}")

    if not request.is_json:
        return jsonify({"error": "Invalid content type"}), 400

    data = request.get_json()
    print(f"JSON data: {data}")
    video_url = data.get('video_url')

    if video_url:
        # Emit the video URL to all connected clients
        socketio.emit('video_url', {'url': video_url},room='broadcast')
    # Process the data here
    return jsonify({"message": "Callback received", "data": data}), 200

def message_manager():
    """Generator function to yield progress messages."""
    while True:
        if message_queue:
            (facility,message) = message_queue.pop(0)
            yield f"data: {facility} : {message}\n\n"
        time.sleep(1)

def logger(facility,message):
    message_queue.append((facility,message))
@app.route('/api/messages')
def stream_messages():
    return(Response(message_manager(),mimetype='text/event-stream'))

if __name__ == '__main__':
    app.run(debug=True)

