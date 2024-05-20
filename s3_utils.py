import boto3

def get_s3_client():
    return(boto3.client('s3'))

def upload_images_to_s3(s3,image_files):
    s3_keys = []
    for image_file in image_files:
        filename = image_file.filename
        s3_key = f'uploads/{filename}'
        s3.upload_fileobj(image_file, SOURCE_BUCKET_NAME, s3_key)
        s3_keys.append(s3_key)
    return s3_keys

# Expects:  a list containing information about images to upload
# images : [
#           {
#               'filename' : 'file.jpg',
#               'local_dir' : '/some/path/to/a/dir',
#               'bucket' :  'some-s3-bucket-name'
#           },
#          ]
def upload_images_from_disk_to_s3(s3,images):
    for image in images:
        s3_key = f'uploads/{image["filename"]}'
        with open(image['local_dir']+image['filename'], 'rb') as image_file:
            s3.upload_fileobj(image_file, image['bucket'], s3_key)
        image['s3_key'] = s3_key
    return images