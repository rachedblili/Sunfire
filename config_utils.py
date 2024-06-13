import yaml


def get_config():
    with open('config/sunfire-config.yaml', 'r') as file:
        try:
            return yaml.safe_load(file)
        except yaml.YAMLError as exc:
            print(exc)
            return


def get_music_data(data_file):
    with open(data_file, 'r') as file:
        try:
            return yaml.safe_load(file)
        except yaml.YAMLError as exc:
            print(exc)
