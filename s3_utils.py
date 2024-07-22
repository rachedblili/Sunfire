import boto3


def get_s3_client():
    return boto3.client('s3')


def upload_images_from_disk_to_s3(s3, images, unique_prefix):
    """
    Uploads images from disk to S3 cloud storage.

    Args:
        s3: An S3 client object.
        images: A list of dictionaries containing image information.
        unique_prefix: A unique prefix used for naming the images.

    Returns:
        The updated list of images with cloud storage keys.
    """
    for image in images:
        s3_key = f'uploads/{unique_prefix}-{image["filename"]}'
        with open(image['local_dir']+image['filename'], 'rb') as image_file:
            s3.upload_fileobj(image_file, image['bucket'], s3_key)
        image['cloud_storage_key'] = s3_key
    return images


def upload_audio_from_disk_to_s3(s3, audio_data, unique_prefix):
    """
    Uploads audio from disk to S3 cloud storage.

    Args:
        s3: An S3 client object.
        audio_data: A dictionary containing audio information.
        unique_prefix: A unique prefix used for naming the audio.

    Returns:
        The updated audio_data dictionary with cloud storage key.
    """
    local_dir = audio_data.get('local_dir')
    clips = audio_data.get('clips')
    filename = clips['combined']['filename']
    s3_key = f'uploads/{unique_prefix}-{filename}'
    with open(local_dir+filename, 'rb') as clip_file:
        s3.upload_fileobj(clip_file, audio_data.get('bucket'), s3_key)
    clips['combined']['cloud_storage_key'] = s3_key
    return audio_data
