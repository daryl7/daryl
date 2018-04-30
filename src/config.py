import yaml

class Config:
    @staticmethod
    def get_applog_level():
        with open('config.yml', 'r') as yml:
            config = yaml.load(yml)
            return config["log"]["applog"]["level"]

    @staticmethod
    def get_log_dir():
        with open('config.yml', 'r') as yml:
            config = yaml.load(yml)
            return config["log"]["applog"]["logdir"]

    @staticmethod
    def get_triangular_asset():
        with open('config.yml', 'r') as yml:
            config = yaml.load(yml)
            return config["triangular"]["asset"]
