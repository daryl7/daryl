import logging
from config import Config

logging.basicConfig(
    level = Config.get_applog_level(),
    filename = Config.get_applog_filepath(),
    filemode = 'a',
    format='%(asctime)s %(levelname)s %(message)s')

def applog_error(message):
    print(message)
    logging.error(message)

def applog_warning(message):
    print(message)
    logging.warning(message)

def applog_info(message):
    print(message)
    logging.info(message)
