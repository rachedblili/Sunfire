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

def generate_unique_filename(prefix=""):

  timestamp = int(time.time())
  random_string = ''.join(random.choices(string.ascii_lowercase, k=5))
  return f"{prefix}{timestamp}_{random_string}"


# Initialize S3 client
s3 = boto3.client('s3')

def generate_filter_complex(images, total_duration):
  """
  Generates ffmpeg filter_complex string for transitions between images.

  Args:
      images: List of dictionaries containing image information.
      total_duration: Total duration of the final video (seconds).
      fps: Frames per second for the output video.

  Returns:
      String containing the filter_complex command.
  """
  filters = []
  duration_per_image = total_duration / len(images)  # Calculate duration per image

  # Scale and prepare each image for transition
  for i, image in enumerate(images):
    filter_name = f"v{i}"
    filters.append(f"[{i}:v]scale=in_w:-1,setsar=1[{filter_name}]")

  # Add transitions between images
  for i in range(len(images) - 1):
    current_filter = f"[v{i}]"
    next_filter = f"[v{i+1}]"
    transition_filter = f"{current_filter}[{next_filter}]xfade=transition=slide:duration={duration_per_image}[vout{i+1}]"
    filters.append(transition_filter)

  # Use the last processed image as the final output
  final_filter = f"[v{len(images)-1}]"
  return ";".join(filters + [final_filter])
  
def process_images_and_generate_video(images, total_duration, fps, aspect_ratio, output_bucket):
    try:
        # Calculate duration per image
        num_images = len(images)
        duration_per_image = total_duration / num_images

        # Check if FFmpeg is available
        if not shutil.which("ffmpeg"):
            print("FFmpeg is not installed or not in the system PATH.")
            return None

        # Create a temporary directory for local files
        with tempfile.TemporaryDirectory() as tmp_dir:
            local_files = []
            for image in images:
                bucket = image['bucket']
                key = image['key']
                local_path = os.path.join(tmp_dir, os.path.basename(key))

                try:
                    # Download image from S3
                    s3.download_file(bucket, key, local_path)
                except ClientError as e:
                    print(f"Error downloading file {key} from bucket {bucket}: {e}")
                    continue

                local_files.append(local_path)

            if not local_files:
                print("No files were downloaded.")
                return None


            filter_complex = generate_filter_complex(images, total_duration)
            
            # Output video file path
            filename = generate_unique_filename(prefix="video-")
            output_file = os.path.join(tmp_dir, f"{filename}.mp4")

            # Construct ffmpeg command
            cmd = ["ffmpeg"]
            for file in local_files:
                cmd.extend(["-i", file])
            cmd.extend([
                    "-pix_fmt", "yuv420p",
                    "-filter_complex", filter_complex,
                    "-map", f"[v{num_images - 1}]",
                    "-c:v", "libx264",
                    "-r", str(fps),
                    "-aspect", aspect_ratio,
                    output_file
            ])
            # Print the ffmpeg command for debugging
            print("FFmpeg command:", ' '.join(cmd))
            
            # Execute ffmpeg command
            result = subprocess.run(cmd, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            # Log stdout and stderr from ffmpeg
            print("FFmpeg stdout:", result.stdout)
            print("FFmpeg stderr:", result.stderr)

            if result.returncode != 0:
                print("FFmpeg failed with return code:", result.returncode)
                return None
            # Upload the generated video to S3
            output_key = f"generated/{filename}.mp4"
            try:
                s3.upload_file(output_file, output_bucket, output_key)
            except ClientError as e:
                print(f"Error uploading file to S3 bucket {output_bucket}: {e}")
                return None

            # Return the URL to the generated video
            #video_url = f"https://{output_bucket}.s3.amazonaws.com/{output_key}"
            video_url = s3.generate_presigned_url(
                'get_object',
                Params={'Bucket': output_bucket, 'Key': output_key},
                ExpiresIn=3600  # URL expires in 1 hour
            ) 
            print(video_url)
            return video_url

    except Exception as e:
        print(f"An error occurred: {e}")
        return None

def lambda_handler(event, context):
    try:
        # Extract body from event
        body = event.get('body')
        if body:
            data = json.loads(body)
            s3_objects = data.get('s3_objects')
            duration = data.get('duration')  # Total duration of the video
            fps = data.get('fps', 24)  # Default 24 frames per second
            aspect_ratio = data.get('aspect_ratio', '16:9')  # Default aspect ratio 16:9
            output_bucket = data.get('output_bucket')
            
            if not s3_objects or not duration:
                return {'statusCode': 400, 'body': json.dumps({'message': 'S3 objects and duration must be provided'})}
            
            # Process S3 objects and generate video
            video_url = process_images_and_generate_video(s3_objects, duration, fps, aspect_ratio, output_bucket)
            
            return {
                'statusCode': 200,
                'body': json.dumps({'video_url': video_url})
            }
        else:
            return {'statusCode': 400, 'body': json.dumps({'message': 'Invalid request body'})}
    except Exception as e:
        return {
            'statusCode': 500,
            'body': json.dumps({'message': str(e)})
        }

