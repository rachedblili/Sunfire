import yaml


def get_text_to_music_client():
    return "sunfire"


def get_music_data(data_file):
    with open(data_file, 'r') as file:
        try:
            return yaml.safe_load(file)
        except yaml.YAMLError as exc:
            print(exc)


def make_music(session_data, prompt):
    pass