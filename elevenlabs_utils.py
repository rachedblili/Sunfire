import os
from elevenlabs import VoiceSettings
from elevenlabs.client import ElevenLabs
from typing import IO
from io import BytesIO
import requests
import json


def get_client():
    client = ElevenLabs(api_key=os.getenv("ELEVENLABS_API_KEY"))
    return client


def get_voice_data():
    url = "https://api.elevenlabs.io/v1/voices"
    response = requests.request("GET", url)
    d = json.loads(response.text)
    return d['voices']


def text_to_speech_stream(client, text: str, voice: str) -> IO[bytes]:
    # Perform the text-to-speech conversion
    response = client.text_to_speech.convert(
        # voice_id="pNInz6obpgDQGcFmaJgB", # Adam pre-made voice
        # voice_id="XrExE9yKIg1WjnnlVkGX", # Friendly American Female
        voice_id=voice,
        optimize_streaming_latency="0",
        output_format="mp3_22050_32",
        text=text,
        model_id="eleven_multilingual_v2",
        voice_settings=VoiceSettings(
            stability=0.0,
            similarity_boost=1.0,
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
    # Return the stream for further use
    return audio_stream


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
        "Friendly": ["narration", "animation", "children's stories"],
        "Professional": ["news", "audiobook", "interactive", "ground reporter"],
        "Calm": ["meditation", "narration"],
        "Energetic": ["video games", "animation", "characters"]
    }

    # Initialize use_cases dictionary based on tones_to_use_cases values
    use_cases = {use_case: [] for tone in tones_to_use_cases.values() for use_case in tone}

    for voice in voice_data:
        voice_info = {
            "voice_id": voice['voice_id'],
            "name": voice['name'],
            "description": voice['labels'].get('description', ''),
            "accent": normalize_attribute(voice['labels'].get('accent', '')),
            "gender": normalize_attribute(voice['labels'].get('gender', '')),
            "age": normalize_attribute(voice['labels'].get('age', ''))
        }

        use_case = voice['labels'].get('use case')
        if use_case in use_cases:
            use_cases[use_case].append(voice_info)

    # Replace use case names in tones_to_use_cases with references to use_cases entries
    tones_to_use_cases_refs = {
        tone: [use_cases[use_case] for use_case in use_case_list]
        for tone, use_case_list in tones_to_use_cases.items()
    }

    return tones_to_use_cases_refs


def normalize_attribute(attribute):
    # Normalize attribute values to a consistent format
    normalized = attribute.lower().replace(' ', '-')
    return normalized.capitalize()


def get_age_gender_combinations(voices):
    combinations = set()
    for voice in voices:
        combination = f"{voice['age']} {voice['gender']}"
        combinations.add(combination)
    return sorted(combinations)


def filter_voices_by_age_gender(voices, age_gender):
    age, gender = age_gender.split()
    return [voice for voice in voices if voice['age'] == age and voice['gender'] == gender]

# def search_voices():
#     # Criteria for filtering
#     criteria = {
#         "accent": "american",
#         "description": "friendly",
#         "gender": "female"
#     }
#
#     # List comprehension to filter voices
#     filtered_voices = [voice for voice in voices
#                        if all(voice.get('labels', {}).get(key) == value for key, value in criteria.items())]
#
#     # Print filtered voices
#     for voice in filtered_voices:
#         print(f"Voice ID : {voice['voice_id']}, Name: {voice['name']}, URL: {voice['preview_url']}")
#     #print(json.dumps(filtered_voices, indent=2))
