import os
from elevenlabs import save, VoiceSettings
from elevenlabs.client import ElevenLabs
import requests
import json
from io import BytesIO
import random
from audio_utils import fit_clip_length


def get_elevenlabs_client():
    client = ElevenLabs(api_key=os.getenv("ELEVENLABS_API_KEY"))
    return client


def get_voice_data():
    url = "https://api.elevenlabs.io/v1/voices"
    response = requests.request("GET", url)
    d = json.loads(response.text)
    return d['voices']


def text_to_speech(client, session_data):
    filename = f'{session_data['company_name']}_{session_data['voice']['name']}_narration.mp3'
    dir_name = session_data['audio']['local_dir']
    # Voice data might contain model settings.  Check for that and apply defaults if needed
    if 'model' not in session_data['voice']:
        session_data['voice']['model'] = 'Eleven Turbo v2 - 60% stab - 80% sim'

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
    parts = session_data['voice']['model'].split(' - ')
    if len(parts) < 3:
        parts.append('60% stab')
        parts.append('80% sim')

    model = models[parts[0]]
    stability = float(parts[1].split('%')[0]) / 100
    similarity_boost = float(parts[2].split('%')[0]) / 100
    # Perform the text-to-speech conversion
    response = client.text_to_speech.convert(
        voice_id=session_data['voice']['voice_id'],
        optimize_streaming_latency="0",
        output_format="mp3_22050_32",
        text=f' ... {session_data["audio"]["narration_script"]} ... ',
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


def generate_audio_narration(client, session_data):
    # Generate the actual audio first
    clip = text_to_speech(client, session_data)
    clip = fit_clip_length(clip, session_data['audio']['local_dir'], session_data['video']['duration'])
    clip['type'] = 'narration'
    return clip


def dump_voice_stats():
    url = "https://api.elevenlabs.io/v1/voices"
    response = requests.request("GET", url)
    d = json.loads(response.text)
    voices = d['voices']
    # Extract unique values for each label category
    for gender in ['male', 'female']:
        accents = {voice['labels'].get('accent') for voice in voices if voice['labels']['gender'] == gender and voice['labels']['accent'] in ['american', 'british', 'american-southern']}
        descriptions = {voice['labels'].get('description') for voice in voices if voice['labels']['gender'] == gender and voice['labels']['accent'] in ['american', 'british', 'american-southern']}
        ages = {voice['labels'].get('age') for voice in voices if voice['labels']['gender'] == gender and voice['labels']['accent'] in ['american', 'british', 'american-southern']}
        use_cases = {voice['labels'].get('use case') for voice in voices if voice['labels']['gender'] == gender and voice['labels']['accent'] in ['american', 'british', 'american-southern']}

        # Print the lists
        print(f"========= {gender} =========")
        print("Accents:", list(accents))
        print("Descriptions:", list(descriptions))
        print("Ages:", list(ages))
        print("Use Cases:", list(use_cases))


def get_voice_tone_data():
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
            "speed": 223.0
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


def normalize_attribute(attribute):
    # Normalize attribute values to a consistent format
    normalized = attribute.lower().replace(' ', '-')
    return normalized.capitalize()


def find_voice(tone, age, gender):
    """
    Retrieve all voices matching the given tone, age, and gender.

    Args:
        tone (str): The selected tone category.
        age (str): The age group to filter by.
        gender (str): The gender to filter by.

    Returns:
        list: A list of dictionaries, each representing a voice that matches the criteria.
    """
    tone = tone.capitalize()
    print("Looking for: ", tone, age, gender)
    tones_data = get_voice_tone_data()
    # Check if the selected tone is in the data structure
    if tone not in tones_data:
        print("Couldn't find tone: ", tone)
        return ""  # Return an empty list if the tone is not found

    # Retrieve the list of all voices under the selected tone
    voices = tones_data[tone]['voices']

    # Filter voices based on the selected age and gender
    matching_voices = [
        voice for voice in voices
        if voice['age'] == age and voice['gender'] == gender
    ]
    print("Number of matches:", str(len(matching_voices)))
    return random.choice(matching_voices)
