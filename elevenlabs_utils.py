import os
import uuid
from elevenlabs import VoiceSettings
from elevenlabs.client import ElevenLabs
from typing import IO
from io import BytesIO
import requests
import json




def get_client():
    ELEVENLABS_API_KEY = os.getenv("ELEVENLABS_API_KEY")
    client = ElevenLabs(api_key=ELEVENLABS_API_KEY)
    return client


def text_to_speech_stream(text: str, voice: str) -> IO[bytes]:
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
    for gender in ['male','female']:
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