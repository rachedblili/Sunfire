# Get setup instructions here: https://github.com/gcui-art/suno-api

import time
import requests

# replace your vercel domain
base_url = 'http://54.166.183.35:3000'


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


def make_music(prompt):
    data = generate_audio_by_prompt({
            "prompt": prompt,
            "make_instrumental": True,
            "wait_audio": False
    })
    ids = f"{data[0]['id']},{data[1]['id']}"
    print(f"ids: {ids}")
    for _ in range(60):
        data = get_audio_information(ids)
        if data[0]["status"] == 'streaming':
            print(f"{data[0]['id']} ==> {data[0]['audio_url']}")
            print(f"{data[1]['id']} ==> {data[1]['audio_url']}")
            return data[0]['audio_url']
        # sleep 5s
        time.sleep(5)
    ids = f"{data[0]['id']},{data[1]['id']}"
    print(f"ids: {ids}")
    return ""