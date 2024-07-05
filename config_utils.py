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


def get_voice_data(data_file):
    with open(data_file, 'r') as file:
        try:
            voices = []
            data = file.readlines()
            headers = data[0].strip().split('\t')
            for line in data[1:]:
                voice = {}
                entries = line.strip().split('\t')
                for header, value in zip(headers, entries):
                    voice[header] = value
                voices.append(voice)

            return voices
        except yaml.YAMLError as exc:
            print(exc)