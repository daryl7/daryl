import logging
from config import Config
import os


def init(filepath):
    logging.basicConfig(
        level = Config.get_applog_level(),
        filename = filepath,
        filemode = 'a',
        format='%(asctime)s %(levelname)s %(message)s')

def error(message):
    print("ERR:  " + str(message))
    logging.error(message)

def warning(message):
    print("WARN: " + str(message))
    logging.warning(message)

def info(message):
    print("INFO: " + str(message))
    logging.info(message)
