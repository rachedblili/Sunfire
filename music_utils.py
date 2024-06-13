import os
import shutil
from text_to_text import generic_query
from config_utils import get_config, get_music_data
config = get_config()
music_data = get_music_data(config['music-data'])


def get_text_to_music_client():
    return "sunfire"


def make_music(session_data, prompt):
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
        "content": "Here is my music data: \n" + music_data['Songs']
    }]

    song = generic_query(session_data['client']['text-to-text'], messages)
    song_library = music_data['Song Library']
    if not os.path.exists(song_library + song):
        raise FileNotFoundError(f"Song not found in library: {song_library}{song}")
    filename = session_data['company_name'] + "_" + session_data['mood'] + "_music.mp3"
    print("Saving Music to Disk...")
    song_library = music_data['Song Library']
    dir_name = session_data['audio']['local_dir']
    try:
        shutil.copy(song_library + song, dir_name + filename)
    except FileNotFoundError:
        raise FileNotFoundError(f"Song not found in library: {song_library}{song}")

    clip = {"filename": filename, "type": "music"}
    return clip
