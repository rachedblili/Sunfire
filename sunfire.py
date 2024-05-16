from flask import Flask, request, jsonify
import os
import boto3
import requests
from openai import OpenAI
import json
OPENAI_API_KEY = os.environ.get('OPENAI_KEY')
app = Flask(__name__)

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
#        describe_prompt = f'''
#            Examine the image at {image_url} 
#            Provide a description of the image dimension and content in JSON format.
#            Example: {{"dimension" : {{"height" : 100, "width" : 200}} , "content" : "A beautiful Oak tree in a green field on a sunny day"}}
#            '''
        describe_response = client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": "You are the assistant. You only answer in JSON."},
                {"role": "user", "content": [
                    {"type": "text", "text": "Examine this image and describe the dimensions and content"},
                    {"type": "image_url", "image_url": {"url": "http://www.someplace.com/image.jpg"}}
                ]}
                {"role": "assistant", "content": "{'dimension' : {'height' : 100, 'width' : 200} , 'content' : 'A beautiful Oak tree in a green field on a sunny day'}"},
                {"role": "user", "content": [
                    {"type": "text", "text": "Examine this image and describe the dimensions and content"},
                    {"type": "image_url", "image_url": {"url": image_url}}
                ]}
            ],
            max_tokens=100
        ) 
        #image['description'] = describe_response.choices[0].text.strip()
        #image['description'] = json.dumps(json.loads(describe_response.model_dump_json()))
        image['description'] = describe_response.choices[0]

        # Recommend cropping and scaling strategy in JSON format
#        strategy_prompt = f'''
#            Given the image description '{image["description"]}', recommend a cropping and scaling strategy to fit into a 16:9 video.
#            Provide the recommendation in JSON format with fields 'crop', 'scale', and 'pad'.
#            Example: {{"crop": {{"x": 10, "y": 20, "width": 100, "height": 200}}, "scale": {{"width": 1920, "height": 1080}}, "pad": {{"width": 1920, "height": 1080, "color": "black"}}}}
#            '''
        strategy_response = client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": "You are the assistant. You only answer in JSON."},
                {"role": "user", "content": "Given the image description \"{'dimension' : {'height' : 100, 'width' : 200} , 'content' : 'A beautiful Oak tree in a green field on a sunny day'}\", recommend a cropping and scaling strategy to fit into a 16:9 video."},
                {"role": "assistant", "content": '{"crop": {"x": 10, "y": 20, "width": 100, "height": 200}, "scale": {"width": 1920, "height": 1080}, "pad": {"width": 1920, "height": 1080, "color": "black"}}'},
                {"role": "user", "content": f"Given the image description \"{image['description']}\", recommend a cropping and scaling strategy to fit into a 16:9 video."}
            ],
            max_tokens=150
        )
        image['strategy'] = json.dumps(json.loads(strategy_response.model_dump_json()))

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

    # Upload images to S3
    s3_keys = upload_images_to_s3(image_files)
    print("S3 Keys:",s3_keys)    

    # Keep track of image attributes
    i = 0
    for image in image_files:
        images.append(
            {'original_file' : image, 
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

