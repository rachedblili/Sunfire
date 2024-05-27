from flask import current_app
from pydub import AudioSegment


def fit_clip_length(clip, local_dir, desired_duration):
    audio = AudioSegment.from_file(local_dir+clip['filename'])

    current_duration = len(audio) / 1000.0  # In seconds
    speed_factor = desired_duration / current_duration

    # Adjust tempo
    new_audio = audio.speedup(playback_speed=speed_factor)

    # Save the result
    dir_name = local_dir
    filename = f"adjusted_{clip['filename']}"
    new_audio.export(dir_name+filename, format="mp3")
    clip['filename'] = filename
    return clip


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


def trim_and_fade(session_data, clip):
    local_dir = session_data['audio']['local_dir']
    trimmed_clip = trim_clip(clip, local_dir)
    faded_clip = fade_out_audio(trimmed_clip, local_dir)
    return faded_clip


def combine_audio_clips(session_data):
    audio_data = session_data['audio']
    save_dir = session_data['audio']['local_dir']
    narration_clip = None
    music_clip = None

    # Identify and load the narration and music clips
    for clip in audio_data['clips']:
        current_app.logger.debug("CLIP:", clip)
        if clip['type'] == 'narration':
            current_app.logger.debug("Found Clip 1")
            narration_clip = AudioSegment.from_file(clip['file_path'])
        elif clip['type'] == 'music':
            current_app.logger.debug("Found Clip 2")
            music_clip = AudioSegment.from_file(clip['file_path'])

    # Check and adjust loudness
    if narration_clip and music_clip:
        # Measure the loudness of each clip
        narration_dbfs = narration_clip.dBFS
        music_dbfs = music_clip.dBFS

        # Calculate the adjustment factor for the music clip to be 75% as loud as the narration clip
        desired_music_dbfs = narration_dbfs - 2

        # Adjust the music clip's volume
        change_in_dbfs = desired_music_dbfs - music_dbfs
        music_clip = music_clip + change_in_dbfs

        # Combine the clips
        combined_clip = narration_clip.overlay(music_clip)

        # Save the resulting file
        file_name = f"{session_data['company_name']}_combined_audio.mp3"
        combined_clip.export(f"{save_dir}/{file_name}", format="mp3")

        # Return information about the new file
        return {"filename": file_name, "type": "combined"}

    else:
        # If one of the clips is missing, handle the error appropriately
        raise FileNotFoundError("One or both audio clips could not be found.")
