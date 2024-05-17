from flask import Flask, request, jsonify
import os
import boto3
import requests
from openai import OpenAI
import json
OPENAI_API_KEY = os.environ.get('OPENAI_KEY')
app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = 'uploads/'
app.config['VIDEOS_FOLDER'] = 'videos/'
from image_utils import modify_image

# Initialize S3 client
s3 = boto3.client('s3')
SOURCE_BUCKET_NAME = 'sunfire-source-bucket'
DESTINATION_BUCKET_NAME = 'sunfire-destination-bucket'
API_GATEWAY_URL = 'https://0h8a50ruye.execute-api.us-east-1.amazonaws.com/sunfire-generate-video-from-images'

def upload_images_to_s3(image_files):
    s3_keys = []
    for image_file in image_files:
        filename = image_file.filename
        s3_key = f'uploads/{filename}'
        s3.upload_fileobj(image_file, SOURCE_BUCKET_NAME, s3_key)
        s3_keys.append(s3_key)
    return s3_keys

def call_api_gateway(s3_keys, total_duration, fps, aspect_ratio, bucket):
    payload = {
        's3_objects': s3_keys,
        'duration': total_duration,
        'fps': fps,
        'aspect_ratio': aspect_ratio,
        'output_bucket': bucket
    }
    response = requests.post(API_GATEWAY_URL, json=payload)
    if response.status_code == 200:
        return response.json().get('video_url')
    else:
        return None

import base64

def file_storage_to_base64_data_url(file_storage):
    """
    Converts a FileStorage object to a base64-encoded data URL.

    Args:
        file_storage (werkzeug.datastructures.FileStorage): The FileStorage object representing the uploaded file.

    Returns:
        str: The base64-encoded data URL in the format 'data:image/png;base64,aW1nIGJ5dGVzIGhlcmU='.
    """
    file_data = file_storage.read()
    mime_type = file_storage.content_type

    base64_bytes = base64.b64encode(file_data)
    base64_string = base64_bytes.decode('utf-8')

    return f"data:{mime_type};base64,{base64_string}"

client = OpenAI(api_key = OPENAI_API_KEY)
def describe_and_recommend(images,url_maker):
    for image in images:
        print(f"Image: {image['original_file']}")
        print(f"S3: {image['s3_key']}")
        # Create pre-signed URL to the S3 objects
        image_url = url_maker(
                'get_object',
                Params={'Bucket': image['bucket'], 'Key': image['s3_key']},
                ExpiresIn=120  # URL expires in 2 minutes
            )
        print(f"URL: {image_url}")
        describe_response = client.chat.completions.create(
            model='gpt-4o',
            messages=[
                {
                    "role": "system", 
                    "content": "You are the assistant. You only answer in pure JSON. Your response will be parsed by a script and should have no formatting characters or extraneous artifacts. This includes newlines and other formatting."
                },
                {
                    "role": "system", 
                    "content": "EXPLICIT REQUIREMENT: You only answer in pure JSON. No formatting characters."
                },
                {
                    "role": "system", 
                    "content": "EXPLICIT REQUIREMENT: Legal output key names: color, dimensions, height, width, content"
                },
                {
                    "role": "user",
                    "content": "Examine the given image and describe the dominant colour, the dimensions, and content."
                },
                {
                    "role": "assistant", 
                    "content": '{"color" : "#DDFFE1", "dimensions" : {"height" : 100, "width" : 200} , "content" : "A beautiful Oak tree in a green field on a sunny day"}'
                },
                {
                    "role": "user",
                    "content": "Examine the given image and describe the dominant colour, the dimensions, and content."
                },
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": image_url
                            }
                        },
                    ],
                }
            ],
            max_tokens=1500
        )
        descr = json.loads(describe_response.choices[0].message.content)
        image['color'] = descr['color']
        image['height'] = descr['dimensions']['height']
        image['width'] = descr['dimensions']['width']
        image['description'] = descr['content']
        strategy_response = client.chat.completions.create(
            model="gpt-4o",
            messages=[
                    {
                        "role": "system",
                        "content": "You are the assistant. Respond in pure JSON with no formatting characters or extraneous artifacts. Legal output key names: crop, color, x, y, height, width, scale, pad. Ensure the proportions of the original image are preserved using symmetrical scaling, cropping, and padding to achieve the desired dimensions. Return the operations (crop, pad, scale) in the correct order."
                    },
                    {
                        "role": "user",
                        "content": "I have an image with height 530px and width 800px and the dominant color is #32DF34. I need to fit this image into a video with a 16:9 aspect ratio. Please provide a cropping, scaling (while maintaining aspect ratio), and padding recommendation that balances image quality and screen coverage without losing important content."
                    },
                    {
                        "role": "assistant",
                        "content": '[{"crop": {"x": 0, "y": 0, "width": 800, "height": 450}}, {"scale": {"width": 1600, "height": 900}}, {"pad": {"width": 1920, "height": 1080, "color": "#32DF34"}}]'
                    },
                    {
                        "role": "user",
                        "content": f"I have an image with height {image['height']} and width {image['width']} and the dominant color is {image['color']}. I need to fit this image into a video with a 16:9 aspect ratio. Please provide a cropping, scaling (while maintaining aspect ratio), and padding recommendation that balances image quality and screen coverage without losing important content."
                    }
            ],
            max_tokens=800
        )
        image['strategy'] = json.loads(strategy_response.choices[0].message.content)

    return(images)

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

    images = []
    # Get the uploaded images from the request
    image_files = request.files.getlist('images')
    print("Image Files:", image_files)

    for image_file in image_files:
        image_file.save(os.path.join(app.config['UPLOAD_FOLDER'], image_file.filename))

    # Upload images to S3
    s3_keys = upload_images_to_s3(image_files)
    print("S3 Keys:",s3_keys)    

    # Keep track of image attributes
    i = 0
    for image in image_files:
        images.append(
            {'original_file' : image, 
             'local_dir' : app.config['UPLOAD_FOLDER'],
             's3_key' : s3_keys[i],
             'bucket' : SOURCE_BUCKET_NAME})
        i += 1

    # Analyze our images
    print("Launching Image Analysis...")
    images = describe_and_recommend(images,s3.generate_presigned_url)    

    for image in images:
        print(f"Image: {image['original_file']}")
        print(f"S3: {image['s3_key']}")
        print(f"Description: {image['description']}")
        print(f"Strategy: {image['strategy']}")
    return jsonify({'error': 'Video generation failed'}), 500

    # Define video parameters
    total_duration = 10  # Total duration of the video
    fps = 24  # Frames per second
    aspect_ratio = '16:9'  # Aspect ratio of the video

    # Call the API Gateway to process the video
    video_url = call_api_gateway(
            s3_keys, total_duration, fps, 
            aspect_ratio, DESTINATION_BUCKET_NAME)

    if video_url:
        # Return the video URL as a response
        print("GOT URL:",video_url)
        return jsonify({'video_url': video_url})
    else:
        # Return an error response if the video generation failed
        return jsonify({'error': 'Video generation failed'}), 500

if __name__ == '__main__':
    app.run(debug=True)

