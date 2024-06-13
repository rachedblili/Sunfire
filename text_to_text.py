import openai_utils


def get_text_to_text_client():
    return openai_utils.get_openai_client()


def describe_and_recommend(*args, **kwargs):
    return openai_utils.describe_and_recommend(*args, **kwargs)


def create_narration(*args, **kwargs):
    return openai_utils.create_narration(*args, **kwargs)


def generate_music_prompt(*args, **kwargs):
    return openai_utils.generate_music_prompt(*args, **kwargs)
