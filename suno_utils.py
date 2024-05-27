# Get setup instructions here: https://github.com/gcui-art/suno-api
from flask import current_app
import time
import requests

# replace your vercel domain
base_url = 'http://127.0.0.1:3000'


def custom_generate_audio(payload):
    url = f"{base_url}/api/custom_generate"
    response = requests.post(url, json=payload, headers={'Content-Type': 'application/json'})
    return response.json()


def generate_audio_by_prompt(payload):
    url = f"{base_url}/api/generate"
    response = requests.post(url, json=payload, headers={'Content-Type': 'application/json'})
    return response.json()


def get_audio_information(audio_ids):
    url = f"{base_url}/api/get?ids={audio_ids}"
    response = requests.get(url)
    return response.json()


def get_quota_information():
    url = f"{base_url}/api/get_limit"
    response = requests.get(url)
    return response.json()


def get_clip(clip_id):
    url = f"{base_url}/api/clip?id={clip_id}"
    response = requests.get(url)
    return response.json()


def generate_whole_song(clip_id):
    payload = {"clip_id": clip_id}
    url = f"{base_url}/api/concat"
    response = requests.post(url, json=payload)
    return response.json()


def make_music(session_data, prompt):
    filename = f'{session_data['company_name']}_{session_data['voice']['name']}_music.mp3'
    dir_name = session_data['audio']['local_dir']
    data = generate_audio_by_prompt({
            "prompt": prompt,
            "make_instrumental": True,
            "wait_audio": False
    })
    ids = f"{data[0]['id']},{data[1]['id']}"
    current_app.logger.debug(f"ids: {ids}")
    for _ in range(60):
        data = get_audio_information(ids)
        if data[0]["status"] == 'streaming':
            current_app.logger.debug(f"{data[0]['id']} ==> {data[0]['audio_url']}")
            current_app.logger.debug(f"{data[1]['id']} ==> {data[1]['audio_url']}")
            break
        # sleep 5s
        time.sleep(5)
    ids = f"{data[0]['id']},{data[1]['id']}"
    current_app.logger.debug(f"ids: {ids}")
    response = requests.get(data[0]['audio_url'])
    response.raise_for_status()
    with open(dir_name+filename, 'wb') as out_file:
        out_file.write(response.content)

    clip = {"filename": filename, "type": "music"}
    return clip
