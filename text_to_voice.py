import elevenlabs_utils
import audio_utils
from config_utils import get_config

config = get_config()
# This module is meant to be the implementation-independent interface for the
# main script.  If other text to voice providers are desired, they can be selected here
# based on the configuration in the config file.




def get_text_to_voice_client():
    return elevenlabs_utils.get_elevenlabs_client()


def get_voice_tone_data():
    return elevenlabs_utils.get_voice_tone_data()


def find_voice(*args, **kwargs):
    if config['voice-list'] == 'elevenlabs':
        return elevenlabs_utils.find_voice(*args, **kwargs)
    elif config['voice-list'] == 'sunfire':
        return audio_utils.find_voice(*args, **kwargs)
    else:
        raise ValueError(f"Invalid find-voice value: {config['find-voice']}")


def generate_audio_narration(*args, **kwargs):
    return elevenlabs_utils.generate_audio_narration(*args, **kwargs)
