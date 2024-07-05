import elevenlabs_utils
import audio_utils
from config_utils import get_config

config = get_config()


def get_text_to_voice_client():
    return elevenlabs_utils.get_elevenlabs_client()


def get_voice_tone_data():
    return elevenlabs_utils.get_voice_tone_data()


def find_voice(session_data):
    if config['voice-list'] == 'elevenlabs':
        return elevenlabs_utils.find_voice(session_data)
    elif config['voice-list'] == 'sunfire':
        return audio_utils.find_voice(session_data)
    else:
        raise ValueError(f"Invalid find-voice value: {config['find-voice']}")


def generate_audio_narration(*args, **kwargs):
    return elevenlabs_utils.generate_audio_narration(*args, **kwargs)
