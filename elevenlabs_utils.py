import os
from elevenlabs import save, VoiceSettings
from elevenlabs.client import ElevenLabs
import requests
import json
from io import BytesIO
from audio_utils import fit_clip_length


def get_elevenlabs_client():
    client = ElevenLabs(api_key=os.getenv("ELEVENLABS_API_KEY"))
    return client


def get_voice_data():
    """
    Retrieves voice data from the Eleven Labs API.

    This function sends a GET request to the Eleven Labs API endpoint
    "https://api.elevenlabs.io/v1/voices" to retrieve information about
    available voices. The response is parsed as JSON and the list of voices
    is returned.

    Returns:
        list: A list of dictionaries representing the available voices. Each
        dictionary contains information about a specific voice, including
        its name, gender, language, and other details.

    Raises:
        JSONDecodeError: If the response from the API cannot be parsed as JSON.
        requests.exceptions.RequestException: If an error occurs during the
        request to the API.
    """
    url = "https://api.elevenlabs.io/v1/voices"
    response = requests.request("GET", url)
    d = json.loads(response.text)
    return d['voices']


def text_to_speech(client, dir_name, voice, narration_script):
    """
    Converts the given `narration_script` to speech using the specified `voice` and `client`.

    Args:
        client: The client used to convert text to speech.
        dir_name: The directory name where the generated audio file will be saved.
        voice: The voice settings including the model, stability, and similarity boost.
        narration_script: The script to be converted to speech.

    Returns:
        dict: A dictionary containing the filename of the generated audio file.

    Raises:
        KeyError: If the 'model' key is missing in the `voice` settings.
    """
    filename = f'{voice['name']}_narration.mp3'
    # Voice data might contain model settings.  Check for that and apply defaults if needed
    print(voice)
    if 'model' not in voice:
        voice['model'] = 'Eleven Turbo v2 - 60% stab - 80% sim'

    models = {
        'Eleven Turbo v2 English': 'eleven_turbo_v2',
        'Eleven Turbo v2': 'eleven_turbo_v2',
        'Eleven English v1': 'eleven_monolingual_v1',
        'Eleven English v2': 'eleven_monolingual_v2',
        'Eleven Multilingual v2': 'eleven_multilingual_v2',
        'Eleven Multilingual v1': 'eleven_multilingual_v1',
        'Eleven Multi v2': 'eleven_multilingual_v2',
        'Eleven Multi v1': 'eleven_multilingual_v1',
    }
    # Grab settings for model and set defaults if needed
    parts = voice['model'].split(' - ')
    if len(parts) < 3:
        parts.append('60% stab')
        parts.append('80% sim')

    model = models[parts[0]]
    stability = float(parts[1].split('%')[0]) / 100
    similarity_boost = float(parts[2].split('%')[0]) / 100

    print(f"Model: {model}")
    print(f"Stability: {stability}")
    print(f"Similarity Boost: {similarity_boost}")
    # Perform the text-to-speech conversion
    response = client.text_to_speech.convert(
        voice_id=voice['voice_id'],
        optimize_streaming_latency="0",
        output_format="mp3_22050_32",
        text=f' ... {narration_script} ... ',
        model_id=model,
        voice_settings=VoiceSettings(
            stability=stability,
            similarity_boost=similarity_boost,
            style=0.0,
            use_speaker_boost=True,
        ),
    )

    # Create a BytesIO object to hold the audio data in memory
    audio_stream = BytesIO()

    # Write each chunk of audio data to the stream
    for chunk in response:
        if chunk:
            audio_stream.write(chunk)

    # Reset stream position to the beginning
    audio_stream.seek(0)
    save(audio_stream, f'{dir_name}/{filename}')
    return {'filename': filename}


def generate_audio_narration(client, dir_name, voice, narration_script, duration):
    """
    Generates audio narration based on the provided information.

    Args:
        client: The client for interacting with the text-to-speech service.
        dir_name: The directory name where the audio file will be saved.
        voice: The voice to be used for narration.
        narration_script: The script or text for narration.
        duration: The duration of the narration.

    Returns:
        A clip containing the generated audio for the narration.
    """
    # Generate the actual audio first
    clip = text_to_speech(client, dir_name, voice, narration_script)
    clip = fit_clip_length(clip, dir_name, duration)
    clip['type'] = 'narration'
    return clip


def get_voice_tone_data():
    """
    Retrieves voice tone data based on the provided voice data.

    This function retrieves voice data using the `get_voice_data` function and filters it based on a set of criteria.
    It creates a dictionary of tones to use cases, with each tone having a list of voices and a set of age and gender
    combinations. The function then iterates over each voice in the voice data and checks if it meets the criteria.
    If it does, the voice information is added to the corresponding tone's list of voices and its age and gender
    combination is added to the set of age and gender combinations. Finally, the function converts the sets of age and
    gender combinations to sorted lists and returns the tones details dictionary.

    Returns:
        dict: A dictionary containing the tones details, where each tone is a key and the value is a dictionary with 'voices' and 'age_gender' keys. The 'voices' key contains a list of voice information dictionaries, and the 'age_gender' key contains a sorted list of age and gender combinations.
    """
    voice_data = get_voice_data()
    tones_to_use_cases = {
        "Friendly": ["animation", "children's stories"],
        "Professional": ["news", "audiobook", "interactive", "ground reporter", "narration"],
        "Calm": ["meditation"],
        "Energetic": ["video games", "animation", "characters", "narration"]
    }
    blacklist = ['Nicole', 'Joseph', 'Clyde', 'Adam', 'Callum']

    tones_details = {tone: {'voices': [], 'age_gender': set()} for tone in tones_to_use_cases}

    for voice in voice_data:
        if voice['name'] in blacklist:
            print(f"Ignoring blacklisted narrator: {voice['name']}")
            continue  # Some voices just suck
        voice_info = {
            "voice_id": voice['voice_id'],
            "name": voice['name'],
            "description": voice['labels'].get('description', ''),
            "accent": normalize_attribute(voice['labels'].get('accent', '')),
            "gender": normalize_attribute(voice['labels'].get('gender', '')),
            "age": normalize_attribute(voice['labels'].get('age', '')),
            "speed": 161.0
        }

        use_case = voice['labels'].get('use case')
        for tone, cases in tones_to_use_cases.items():
            if use_case in cases and voice_info['accent'] in ['American']:
                tones_details[tone]['voices'].append(voice_info)
                tones_details[tone]['age_gender'].add(f"{voice_info['age']} {voice_info['gender']}")

    # Convert age_gender sets to sorted lists
    for tone in tones_details:
        tones_details[tone]['age_gender'] = sorted(tones_details[tone]['age_gender'])

    return tones_details


def get_slim_voice_data():
    """
    Retrieves a slim version of voice data.

    Returns:
        list: A list of dictionaries containing voice information with specific attributes such as voice_id, name,
        description, use case, accent, gender, age, and speed.
    """
    voice_data = get_voice_data()
    slim_voice_data = []
    for voice in voice_data:
        voice_info = {
            "voice_id": voice['voice_id'],
            "name": voice['name'],
            "description": voice['labels'].get('description', ''),
            "use": voice['labels'].get('use case', ''),
            "accent": normalize_attribute(voice['labels'].get('accent', '')),
            "gender": normalize_attribute(voice['labels'].get('gender', '')),
            "age": normalize_attribute(voice['labels'].get('age', '')),
            "speed": 161.0
        }
        slim_voice_data.append(voice_info)
    return slim_voice_data


def normalize_attribute(attribute):
    """
    Normalizes the given attribute value to a consistent format.

    Parameters:
        attribute (str): The attribute value to be normalized.

    Returns:
        str: The normalized attribute value.
    """
    # Normalize attribute values to a consistent format
    normalized = attribute.lower().replace(' ', '-')
    return normalized.capitalize()


def find_voice(client, tone, topic):
    """
    Finds a voice that matches the given tone and topic.

    Args:
        client (object): The client object used to interact with the voice matching service.
        tone (str): The desired tone of the voice.
        topic (str): The topic or context for the voice.

    Returns:
        dict: A dictionary containing the voice information, including the voice ID, name, model, and speed.
    """
    print("Looking for: ", tone)
    voices = get_slim_voice_data()
    from text_to_text import get_matching_voice

    voice = get_matching_voice(client, tone, voices, topic)

    voice_info = {
        "voice_id": voice['id'],
        "name": voice['name'],
        "model": voice['model'],
        "speed": voice['speed']
    }

    return voice_info
