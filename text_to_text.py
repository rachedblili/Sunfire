import openai_utils
from config_utils import get_config

config = get_config()
# This module is meant to be the implementation-independent interface for the
# main script.  If other text to text providers are desired, they can be selected here
# based on the configuration in the config file.


def get_text_to_text_client():
    return openai_utils.get_openai_client()


def describe_and_recommend(*args, **kwargs):
    return openai_utils.describe_and_recommend(*args, **kwargs)


def create_narration(*args, **kwargs):
    return openai_utils.create_narration(*args, **kwargs)


def generate_music_prompt(*args, **kwargs):
    return openai_utils.generate_music_prompt(*args, **kwargs)


def generic_query(*args, **kwargs):
    return openai_utils.generic_query(*args, **kwargs)


def get_matching_voice(*args, **kwargs):
    return openai_utils.get_matching_voice(*args, **kwargs)


