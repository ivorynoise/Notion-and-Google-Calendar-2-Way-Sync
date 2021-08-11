import logging

import configparser

from utils import Singleton


log = logging.getLogger(__name__)


class ConfigParser(metaclass=Singleton):
    def __init__(self):
        self._initialized = False

        self.NOTION_TOKEN = ""
        self.TASK_DATABASE_ID = ""
        self.URL_ROOT = ""
        self.SECRET_DIR = ""
        self.TIMEZONE = ""
        self.DEFAULT_EVENT_LENGTH = ""
        self.DEFAULT_START_TIME = ""
        self.ALL_DAY_EVENT = ""
        self.DELETE_OPTION = ""
        self.DEFAULT_GCALENDAR_ID =""
        self.DEFAULT_GCALENDAR_NAME =""

    def initialize(self, fp):
        config = configparser.ConfigParser()

        log.info('Reading configuration file % s' % fp)
        config.read(fp)

        notion_cfg = config['NOTION']
        self.NOTION_TOKEN = notion_cfg['NOTION_TOKEN']
        self.TASK_DATABASE_ID = notion_cfg['TASK_DATABASE_ID']
        self.URL_ROOT = notion_cfg['URL_ROOT']

        google_cfg = config['GOOGLE']
        self.SECRET_DIR = google_cfg['SECRET_DIR']

        other_cfg = config['OTHERS']
        self.TIMEZONE = other_cfg['TIMEZONE']
        self.DEFAULT_EVENT_LENGTH = other_cfg['DEFAULT_EVENT_LENGTH']
        self.DEFAULT_START_TIME = other_cfg['DEFAULT_START_TIME']
        self.ALL_DAY_EVENT = other_cfg['ALL_DAY_EVENT']
        self.DELETE_OPTION = other_cfg['DELETE_OPTION']
        self.DEFAULT_GCALENDAR_ID = other_cfg['DEFAULT_GCALENDAR_ID']
        self.DEFAULT_GCALENDAR_NAME = other_cfg['DEFAULT_GCALENDAR_NAME']

        self._initialized = True

    @property
    def initialized(self):
        return self._initialized

    def validate(self):
        pass

    @property
    def notion_token(self):
        return self.NOTION_TOKEN

    @property
    def secret_dir(self):
        return self.SECRET_DIR

    @property
    def task_database_id(self):
        return self.TASK_DATABASE_ID

    @property
    def url_root(self):
        return self.URL_ROOT

    @property
    def timezone(self):
        return self.TIMEZONE

    @property
    def default_event_length(self):
        return self.DEFAULT_EVENT_LENGTH

    @property
    def default_start_time(self):
        return self.DEFAULT_START_TIME

    @property
    def all_day_event(self):
        return self.ALL_DAY_EVENT

    @property
    def delete_option(self):
        return self.DELETE_OPTION

    @property
    def default_gcal_id(self):
        return self.DEFAULT_GCALENDAR_ID

    @property
    def default_gcal_name(self):
        return self.DEFAULT_GCALENDAR_NAME
