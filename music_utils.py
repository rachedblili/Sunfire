import os
import shutil
import json
from text_to_text import generic_query
from config_utils import get_config, get_music_data
config = get_config()
music_data = get_music_data(config['music-data'])


def get_text_to_music_client():
    return "sunfire"


def make_music(text_to_text, dir_name, prompt):
    messages = [{
        "role": "system",
        "content": "You are the assistant. Your job is to select an appropriate piece of music based on a "
                   "prompt and a JSON file containing music data. Your response will be parsed by a script and should "
                   "have no formatting characters or extraneous artifacts.  Reply only with the value associated with "
                   "the 'Filename' of the song.  IMPORTANT: Though the prompt is asking you to generate a song, "
                   "the the task is to look through the music data and select an appropriate song.  "
    }, {
        "role": "user",
        "content": prompt
    }, {
        "role": "user",
        "content": "Here is my music data: \n" + json.dumps(music_data['Songs'])
    }]

    song = generic_query(text_to_text, messages)
    song_library = music_data['Data Directory']
    if not os.path.exists(song_library + song):
        raise FileNotFoundError(f"Song not found in library: {song_library}{song}")
    filename = "music.mp3"
    print("Saving Music to Disk...")
    try:
        shutil.copy(song_library + song, dir_name + filename)
    except FileNotFoundError:
        raise FileNotFoundError(f"Song not found in library: {song_library}{song}")

    clip = {"filename": filename, "type": "music"}
    return clip
