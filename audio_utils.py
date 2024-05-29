from pydub import AudioSegment
import subprocess
import os
import math


# Use this to change the length without changing the content
def fit_clip_length(clip, local_dir, desired_duration):
    audio = AudioSegment.from_file(local_dir+clip['filename'])

    current_duration = len(audio) / 1000.0  # In seconds
    speed_factor = current_duration / desired_duration
    print("Naration speed factor: ", str(speed_factor))
    input_file = clip['filename']
    output_file = f"adjusted_{input_file}"
    # Construct the ffmpeg command
    cmd = ["ffmpeg", "-y", "-i",
           local_dir + input_file,
           "-filter:a", f"atempo={speed_factor}",
           local_dir + output_file]

    # Execute the command
    subprocess.run(cmd, check=True)
    clip['filename'] = output_file
    return clip


# This is intended to be used with the music.  It just cuts the end off.
def trim_clip(clip, local_dir):
    clip_length = 30 * 1000  # in ms
    print("TRIM CLIP")
    print("local_dir:", local_dir, "clip:", clip)
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
def trim_and_fade(session_data, clip):
    local_dir = session_data['audio']['local_dir']
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
    return(clip)


def combine_audio_clips(session_data: dict):
    audio_data = session_data['audio']
    save_dir = session_data['audio']['local_dir']
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
        desired_music_rms = narration_rms * 0.3  # 0.3 = 30% as loud as the voice

        # Calculate the required change in volume in dB
        change_in_volume_db = 20 * math.log10(desired_music_rms / music_rms) if music_rms != 0 else 0
        # Adjust the music clip's volume
        adjusted_music_clip = music_clip + change_in_volume_db
        volume_factor = (adjusted_music_clip.rms / music_rms)
        print("Changing Music Volume by factor: ", str(volume_factor))
        volume_adjusted_clip = modify_volume(audio_data['clips']['music'], volume_factor, save_dir)
        # Construct the ffmpeg command

        output_filename = f"{session_data['company-name']}_combined_audio.mp3"
        cmd = ["ffmpeg", "-y", "-i", save_dir+audio_data['clips']['voice']['filename'],
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
