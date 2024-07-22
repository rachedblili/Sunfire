from s3_utils import get_s3_client, upload_images_from_disk_to_s3, upload_audio_from_disk_to_s3
from config_utils import get_config

config = get_config()
# This module is meant to be the implementation-independent interface for the
# main script.  If other cloud storage providers are desired, they can be selected here
# based on the configuration in the config file.


def get_cloud_storage_client():
    return get_s3_client()


def upload_images_from_disk_to_cloud(*args, **kwargs):
    return upload_images_from_disk_to_s3(*args, **kwargs)


def upload_audio_from_disk_to_cloud(*args, **kwargs):
    return upload_audio_from_disk_to_s3(*args, **kwargs)

