import boto3


def get_s3_client():
    return boto3.client('s3')


# Expects:  a list containing information about images to upload
# images : [
#           {
#               'filename' : 'file.jpg',
#               'local_dir' : '/some/path/to/a/dir',
#               'bucket' :  'some-s3-bucket-name'
#           },
#          ]
def upload_images_from_disk_to_s3(s3, images):
    for image in images:
        s3_key = f'uploads/{image["filename"]}'
        with open(image['local_dir']+image['filename'], 'rb') as image_file:
            s3.upload_fileobj(image_file, image['bucket'], s3_key)
        image['s3_key'] = s3_key
    return images


def upload_audio_from_disk_to_s3(s3, audio_data):

    local_dir = audio_data.get('local_dir')
    clips = audio_data.get('clips')
    filename = clips['combined']['filename']
    s3_key = f'uploads/{filename}'
    with open(local_dir+filename, 'rb') as clip_file:
        s3.upload_fileobj(clip_file, audio_data.get('bucket'), s3_key)
    clips['combined']['s3_key'] = s3_key
    return audio_data
