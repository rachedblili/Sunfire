from pydub import AudioSegment


def fit_clip_length(clip, local_dir, desired_duration):
    audio = AudioSegment.from_file(local_dir+['filename'])

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

def fade_out_audio(clip, local_dir):
    fade_duration = 2000
    audio = AudioSegment.from_file(local_dir+['filename'])

    # Apply a fade out over the last `fade_duration` milliseconds
    faded_audio = audio.fade_out(fade_duration)
    filename = "faded_"+clip['filename']
    # Export the modified audio file
    faded_audio.export(local_dir+filename, format="mp3")
    clip['filename'] = filename
    return clip