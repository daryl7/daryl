import logging
from config import Config
import os


def init(logname):
    logging.basicConfig(
        level = Config.get_applog_level(),
        filename = Config.get_log_dir() + "/" + logname + ".log",
        filemode = 'a',
        format='%(asctime)s %(levelname)s %(message)s')

def error(message):
    print(message)
    logging.error(message)

def warning(message):
    print(message)
    logging.warning(message)

def info(message):
    print(message)
    logging.info(message)
