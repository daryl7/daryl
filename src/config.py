import yaml

class Config:
    @staticmethod
    def get_applog_level():
        with open('config.yml', 'r') as yml:
            config = yaml.load(yml)
            return config["log"]["applog"]["level"]

    @staticmethod
    def get_applog_filepath():
        with open('config.yml', 'r') as yml:
            config = yaml.load(yml)
            return config["log"]["applog"]["filepath"]
