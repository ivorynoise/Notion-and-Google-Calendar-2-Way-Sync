import logging

import configparser

from utils import Singleton


log = logging.getLogger(__name__)


class ConfigParser(metaclass=Singleton):
    def __init__(self):
        self._initialized = False

        self.NOTION_TOKEN = ""
        self.TASK_DATABASE_ID = ""
        self.SECRET_DIR = ""
        self.DEFAULT_EVENT_LENGTH = ""
        self.DEFAULT_START_TIME = ""
        self._calendars = {}

    def initialize(self, fp):
        config = configparser.ConfigParser()

        log.info('Reading configuration file % s' % fp)
        config.read(fp)

        notion_cfg = config['NOTION']
        self.NOTION_TOKEN = notion_cfg['NOTION_TOKEN']
        self.TASK_DATABASE_ID = notion_cfg['TASK_DATABASE_ID']

        google_cfg = config['GOOGLE']
        self.SECRET_DIR = google_cfg['SECRET_DIR']
        self.DEFAULT_EVENT_LENGTH = google_cfg['DEFAULT_EVENT_LENGTH']
        self.DEFAULT_START_TIME = google_cfg['DEFAULT_START_TIME']

        calendars_cfg = config['GOOGLE\\CALENDARS']
        self._calendars = {
            "default": calendars_cfg['DEFAULT_GCALENDAR_ID'],
            "completed": calendars_cfg['COMPLETED_GCALENDAR_ID']
        }

        self._initialized = True

    @property
    def initialized(self):
        return self._initialized

    def validate(self):
        pass

    @property
    def notion_token(self):
        # use decorator to check for self.initialised
        return self.NOTION_TOKEN

    @property
    def secret_dir(self):
        return self.SECRET_DIR

    @property
    def task_database_id(self):
        return self.TASK_DATABASE_ID

    @property
    def default_start_time(self):
        return self.DEFAULT_START_TIME

    @property
    def calendars(self):
        return self._calendars
