from s3_utils import get_s3_client, upload_images_from_disk_to_s3, upload_audio_from_disk_to_s3


def get_cloud_storage_client(*args, **kwargs):
    return "s3"


def upload_images_from_disk_to_cloud(*args, **kwargs):
    return upload_images_from_disk_to_s3(*args, **kwargs)


def upload_audio_from_disk_to_cloud(*args, **kwargs):
    return upload_audio_from_disk_to_s3(*args, **kwargs)

