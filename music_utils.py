import os
import shutil
import json
from text_to_text import generic_query
from config_utils import get_config, get_music_data
import random

config = get_config()
music_data = get_music_data(config['music-data'])


def get_text_to_music_client():
    return "sunfire"


def make_music(text_to_text, dir_name, prompt):
    """
    Retrieves an appropriate piece of music based on a given prompt and music data.
    Generates a JSON message structure, queries for the music, and saves the selected music to a specified directory.
    Parameters:
        - text_to_text: The input text to generate the music.
        - dir_name: The directory path to save the generated music file.
        - prompt: The prompt for selecting the music.
    Returns:
        A dictionary containing the filename of the saved music and its type.
    """
    messages = [{
        "role": "system",
        "content": "You are an assistant tasked with selecting the three best-matching songs from a provided list of "
                   "music."
                   "Each song has several properties including a description ('Descr'), genre, mood, tempo, "
                   "and energy level."
                   "Your task is to analyze all these properties and select the three songs that best match the "
                   "user's prompt."
                   "Return the filenames of these three songs as a comma-separated list, with no additional text or "
                   "formatting.  Example output: 'song1.mp3,song2.mp3,song3.mp3'\n"
                   "DO NOT PUT SPACES AFTER THE COMMA."
    }, {
        "role": "user",
        "content": prompt
    }, {
        "role": "user",
        "content": "Here is the music data to use for your selection:\n" + json.dumps(music_data['Songs'])
    }]

    song = random.choice(generic_query(text_to_text, messages).split(','))
    song_library = music_data['Data Directory']
    if not os.path.exists(song_library + song):
        raise FileNotFoundError(f"Song not found in library: {song_library}{song}")
    filename = song
    print("Saving Music to Disk...")
    try:
        shutil.copy(song_library + song, dir_name + filename)
    except FileNotFoundError:
        raise FileNotFoundError(f"Song not found in library: {song_library}{song}")

    clip = {"filename": filename, "type": "music"}
    return clip
