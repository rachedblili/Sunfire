import os
import tempfile
import boto3
import subprocess
import shutil
import json
from botocore.exceptions import ClientError
import time
import string
import random
import urllib3
from lambda_video_functions import process_images_and_generate_video




###################################################################################################################
#                                          OUTBOUND TO API GATEWAY                                                #
###################################################################################################################
def return_final_results():
    # Upload the generated video to S3
    output_key = f"generated/{filename}.mp4"
    try:
        s3.upload_file(output_file, output_bucket, output_key)
    except ClientError as e:
        print(f"Error uploading file to S3 bucket {output_bucket}: {e}")
        return None

    # Return the URL to the generated video
    # video_url = f"https://{output_bucket}.s3.amazonaws.com/{output_key}"
    video_url = s3.generate_presigned_url(
        'get_object',
        Params={'Bucket': output_bucket, 'Key': output_key},
        ExpiresIn=3600  # URL expires in 1 hour
    )
    print(video_url)
    # Add the video URL to session data and POST to the callback URL
    session_data['video_url'] = video_url
    if callback_url:
        http = urllib3.PoolManager()
        headers = {'Content-Type': 'application/json'}
        payload = {"session_data": session_data}
        response = http.request(
            "POST",
            callback_url,
            body=json.dumps(payload),
            headers=headers
        )
        print(f"Callback response status: {str(response.status)}, response text: {response.data.decode('utf-8')}")
    return response.status


###################################################################################################################
#                                     MAIN ORCHESTRATION HAPPENS HERE                                             #
###################################################################################################################

def generate_content(session_data):
    # Initialize S3 client
    s3 = boto3.client('s3')

    try:
        # Generate Initial Video
        video_data = process_images_and_generate_video(s3, session_data)
        session_data['video'] = video_data

        print("Video created successfully.  Moving on to audio...")
        # Mix Audio Tracks
    except Exception as e:
        print("BARFED:", str(e))
        raise

    # Mix Audio Tracks
    # Combine Video and Audio
    # Return Final Result

###################################################################################################################
#                                         LAMBDA INVOCATION BELOW                                                 #
###################################################################################################################
def lambda_handler(event, context):
    try:
        if event.get('async'):
            # Asynchronous invocation
            print("ASYNCH EXECUTION")
            session_data = event

            generate_content(session_data)
            return {'statusCode': 200}

        else:
            # Synchronous invocation
            print("INITIAL REQUEST")
            body = event.get('body')
            if body:
                session_data = json.loads(body)
                s3_objects = session_data.get('s3_objects')
                video_data = session_data.get('video')
                duration = video_data.get('duration')
                output_bucket = session_data.get('write_bucket')
                callback_url = session_data.get('callback_url')

                if not s3_objects or not duration or not output_bucket or not callback_url:
                    return {'statusCode': 400,
                            'body': json.dumps({'message': 'S3 objects, duration, output bucket, and callback URL must be provided'})}

                # Return success immediately after validation
                response = {
                    'statusCode': 200,
                    'body': json.dumps({'message': 'Job accepted and processing will continue'})
                }

                # Continue processing asynchronously
                session_data['async'] = True
                boto3.client('lambda').invoke(
                    FunctionName=context.invoked_function_arn,
                    InvocationType='Event',
                    Payload=json.dumps(session_data)
                )

                return response
            else:
                return {'statusCode': 400, 'body': json.dumps({'message': 'Invalid request body'})}

    except Exception as e:
        print("BARFED:", str(e))
        return {
            'statusCode': 500,
            'body': json.dumps({'message': str(e)})
        }
