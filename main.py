import time
from datetime import datetime, timedelta, date

import logging

from config_parser import ConfigParser
from client import GoogleClient
from client import NotionClient
from tasks import  Event, Task

logging.basicConfig(format='%(asctime)s %(message)s', datefmt='%m/%d/%Y %I:%M:%S %p', level=logging.INFO)
log = logging.getLogger(__name__)




if __name__ == '__main__':
    ConfigParser().initialize("config.ini")

    gc = GoogleClient()
    nc = NotionClient()
    gc.auth()
    nc.auth()

    while(True):
        gupdates = gc.get_updates()
        nupdates = nc.get_updates()
        (gstore, nstore) = TaskStore().sync(gupdates, nupdates)
        gc.update(gstore)
        nc.update(nstore)
        time.sleep(5)


