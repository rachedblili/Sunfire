from config_utils import get_config

config = get_config()


def get_text_to_music_client():
    return config['text-to-music']


def make_music(*args, **kwargs):
    if config['text-to-music'] == 'sunfire':
        import music_utils
        return music_utils.make_music(*args, **kwargs)
    elif config['text-to-music'] == 'suno':
        import suno_utils
        return suno_utils.make_music(*args, **kwargs)
    else:
        raise ValueError(f"Invalid text-to-music value: {config['text-to-music']}")

