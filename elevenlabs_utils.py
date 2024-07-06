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
    print(session_data['voice'])
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

    print(f"Model: {model}")
    print(f"Stability: {stability}")
    print(f"Similarity Boost: {similarity_boost}")
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
    # Normalize attribute values to a consistent format
    normalized = attribute.lower().replace(' ', '-')
    return normalized.capitalize()


def find_voice(session_data):
    tone = session_data['mood']
    print("Looking for: ", tone)
    voices = get_slim_voice_data()
    from text_to_text import generic_query
    import json
    import random
    messages = [{
        "role": "system",
        "content": "You are the assistant. Your job is to select the THREE best voices to narrate a video."
                   "You will base your decision on the specified tone of the voice as well as the "
                   "overall topic of the video. Your response will be parsed by a script and should consist ONLY "
                   "of a comma-separated list of voice names.  For example: Brian,Russell,Janine "
                   "If the specified tone is 'ai', then use your judgement to select the appropriate voice. "
                   "A list of voices and their characteristics can be found below. "
    }, {
        "role": "user",
        "content": "Tone: " + tone
    }, {
        "role": "user",
        "content": "Overall Topic of the Video: " + session_data['topic']
    }, {
        "role": "user",
        "content": "Here is the voice data: \n" + json.dumps(voices)
    }, {
        "role": "user",
        "content": "Respond ONLY with names of the THREE best voices as a comma-separated list. "
                   "ONLY provide the list. NO extra characters or formatting. "
    }]

    voice_names = generic_query(session_data['clients']['text_to_text'], messages).split(',')
    voice_name = random.choice(voice_names)
    voice = [v for v in voices if v['name'] == voice_name][0]
    voice_info = {
        "voice_id": voice['id'],
        "name": voice['name'],
        "model": voice['model'],
        "speed": voice['speed']
    }

    return voice_info

