from flask import Flask, request, jsonify
import os
from moviepy.editor import ImageClip, CompositeVideoClip, clips_array, concatenate_videoclips

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = 'uploads/'
app.config['VIDEOS_FOLDER'] = 'videos/'

def generate_video_from_images(image_files):

    # Check if there are any image files
    if not image_files:
        return None

    # Calculate the duration for each image
    duration = 10 / len(image_files)

    clips = []
    # Create a clip from each image file
    for image in image_files:
        filename = os.path.join(app.config['UPLOAD_FOLDER'], image.filename)
        clip = ImageClip(filename, duration=duration)
        clips.append(clip)

    # Concatenate clips with a crossfade effect
    # Note: MoviePy's concatenate_videoclips function can be used with a method for transitions
    final_clip = concatenate_videoclips(clips, method="compose")
    final_clip.fps=24

    # Write the final video to a file
    output_file = os.path.join(app.config['VIDEOS_FOLDER'],'output_video.mp4')
    final_clip.write_videofile(output_file)
    print(output_file)
    return(output_file)

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
    print("Image Files:",image_files)
    # Save the uploaded images to the upload folder
    for image_file in image_files:
        image_file.save(os.path.join(app.config['UPLOAD_FOLDER'], image_file.filename))

    # Generate the video from the uploaded images
    output_file = generate_video_from_images(image_files)

    if output_file:
        # Return the video file path as a response
        return jsonify({'video_url': f'{output_file}'})
    else:
        # Return an error response if no images were provided
        return jsonify({'error': 'No images provided'}), 400

if __name__ == '__main__':
    app.run(debug=True)
