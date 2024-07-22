import yaml


def get_config():
    """
    Reads and returns the configuration data from the 'sunfire-config.yaml' file.

    This function opens the 'sunfire-config.yaml' file located in the 'config' directory and reads its contents using
    the `yaml.safe_load()` function. If the file cannot be loaded, it prints the exception and returns `None`.

    Returns:
        dict or None: The configuration data as a dictionary if the file is successfully loaded, otherwise `None`.
    """
    with open('config/sunfire-config.yaml', 'r') as file:
        try:
            return yaml.safe_load(file)
        except yaml.YAMLError as exc:
            print(exc)
            return


def get_music_data(data_file):
    """
    Reads and returns the music data from the specified data file.

    Parameters:
        data_file (str): The path to the file containing the music data.

    Returns:
        dict: The music data loaded from the file using `yaml.safe_load()`.
    """
    with open(data_file, 'r') as file:
        try:
            return yaml.safe_load(file)
        except yaml.YAMLError as exc:
            print(exc)


def get_voice_data(data_file):
    """
    Reads and returns the voice data from the specified data file.

    Parameters:
        data_file (str): The path to the file containing the voice data.

    Returns:
        list: A list of dictionaries, where each dictionary represents a voice and contains the voice data.

    Raises:
        yaml.YAMLError: If there is an error parsing the YAML file.

    """
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