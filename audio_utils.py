from pydub import AudioSegment
import subprocess
import os
import math
from config_utils import get_config, get_voice_data

config = get_config()


# Used when the voice catalog is maintained by the Sunfire team
def find_voice(client, tone, topic):
    voices = get_voice_data(config['voice-data'])
    from text_to_text import get_matching_voice

    voice = get_matching_voice(client, tone, voices, topic)

    voice_info = {
        "voice_id": voice['id'],
        "name": voice['name'],
        "model": voice['model'],
        "speed": voice['speed']
    }

    return voice_info


# Use this to change the length without changing the content
def fit_clip_length(clip, local_dir, desired_duration):
    audio = AudioSegment.from_file(local_dir+clip['filename'])

    current_duration = len(audio) / 1000.0  # In seconds
    speed_factor = current_duration / desired_duration
    # Limit the speed_factor to be between 0.85 and 1.2
    speed_factor = max(0.85, min(speed_factor, 1.2))
    print("Speed Factor: " + str(speed_factor))
    input_file = clip['filename']
    output_file = f"adjusted_{input_file}"
    # Construct the ffmpeg command
    cmd = ["ffmpeg", "-y", "-i",
           local_dir + input_file,
           "-filter:a", f"atempo={speed_factor}",
           local_dir + output_file]

    # Execute the command
    subprocess.run(cmd, check=True)

    # Due to limits we have set, the length might be too short.  If so, pad
    # it with silence
    audio = AudioSegment.from_file(local_dir+output_file)
    current_duration = len(audio) / 1000.0  # In seconds
    if current_duration < desired_duration:
        padding = desired_duration - current_duration
        if padding > 0.1:  # If it's less than 0.1 seconds, don't bother
            audio = audio.append(AudioSegment.silent(duration=padding*1000))
            audio.export(local_dir+output_file, format="mp3")

    clip['filename'] = output_file
    return clip


# This is intended to be used with the music.  It just cuts the end off.
def trim_clip(clip, local_dir):
    clip_length = 30 * 1000  # in ms
    audio = AudioSegment.from_file(local_dir+clip['filename'])

    # Trim the audio to the target length if it's long enough
    if len(audio) > clip_length:

        trimmed_audio = audio[:clip_length]
        filename = "trimmed_"+clip['filename']
        # Export the trimmed audio file
        trimmed_audio.export(local_dir+filename, format="mp3")
        clip['filename'] = filename
        return clip
    else:
        raise ValueError("Audio is shorter than the target length.")


# Intended for use with the music
def fade_out_audio(clip, local_dir):
    fade_duration = 2000
    audio = AudioSegment.from_file(local_dir+clip['filename'])

    # Apply a fade out over the last `fade_duration` milliseconds
    faded_audio = audio.fade_out(fade_duration)
    filename = "faded_"+clip['filename']
    # Export the modified audio file
    faded_audio.export(local_dir+filename, format="mp3")
    clip['filename'] = filename
    return clip


# Intended for use with the music
def trim_and_fade(local_dir, clip):
    trimmed_clip = trim_clip(clip, local_dir)
    faded_clip = fade_out_audio(trimmed_clip, local_dir)
    return faded_clip


def modify_volume(clip, factor, local_dir):
    new_file = f'volume_change_{clip['filename']}'
    # Construct the ffmpeg com0and
    cmd = ["ffmpeg", "-y",
           "-i", local_dir + clip['filename'],
           "-filter:a",
           f"volume={factor}",
           local_dir+new_file]
    # Execute the command
    subprocess.run(cmd, check=True)
    if os.path.isfile(local_dir+new_file):
        clip['filename'] = new_file
    else:
        print("Volume Adjustment FAILED")
    return clip


def combine_audio_clips(audio_data):
    save_dir = audio_data['local_dir']
    narration_clip = AudioSegment.from_file(save_dir+audio_data['clips']['voice']['filename'])
    music_clip = AudioSegment.from_file(save_dir+audio_data['clips']['music']['filename'])

    # Check and adjust loudness
    if narration_clip and music_clip:
        print("Checking Loudness")
        # Measure the loudness of each clip
        narration_rms = narration_clip.rms
        music_rms = music_clip.rms

        print("Narration RMS:", narration_rms)
        print("Music RMS:", music_rms)

        # Calculate the desired RMS for the music based on the desired_ratio
        desired_music_rms = narration_rms * 0.35  # 0.35 = 35% as loud as the voice

        # Calculate the required change in volume in dB
        change_in_volume_db = 20 * math.log10(desired_music_rms / music_rms) if music_rms != 0 else 0
        # Adjust the music clip's volume
        adjusted_music_clip = music_clip + change_in_volume_db
        volume_factor = (adjusted_music_clip.rms / music_rms)
        print("Changing Music Volume by factor: ", str(volume_factor))
        volume_adjusted_clip = modify_volume(audio_data['clips']['music'], volume_factor, save_dir)
        # Construct the ffmpeg command

        output_filename = "combined_audio.mp3"
        cmd = ["ffmpeg", "-y", "-i",
               save_dir+audio_data['clips']['voice']['filename'],
               "-i", save_dir + volume_adjusted_clip['filename'],
               "-filter_complex", "amerge=inputs=2", save_dir + output_filename]
        # Execute the command
        subprocess.run(cmd, check=True)
        if os.path.isfile(save_dir + output_filename):
            file_name = output_filename
        else:
            print("Volume Adjustment FAILED")

        # Return information about the new file
        return {"filename": file_name, "type": "combined"}

    else:
        # If one of the clips is missing, handle the error appropriately
        print("Weird: Couldn't find both clips.")
        raise FileNotFoundError("One or both audio clips could not be found.")
