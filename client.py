import os.path
import logging
from glom import  glom
from googleapiclient.discovery import build, Resource
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from notion_client import Client as NClient

from utils import Singleton
from config_parser import ConfigParser
from tasks import Event, Task

log = logging.getLogger(__name__)


class Client:
    def auth(self):
        raise NotImplementedError


class GoogleClient(Client, metaclass=Singleton):
    def __init__(self):
        self._SCOPES = ['https://www.googleapis.com/auth/calendar']
        self._service: Resource = None

    def auth(self):
        creds = None
        creds_fp = os.path.join(ConfigParser().secret_dir, 'client_secret.json')
        token_fp = os.path.join(ConfigParser().secret_dir, 'token.json')

        assert ConfigParser.initialized, "ConfigParser uninitialised."
        assert os.path.exists(creds_fp), f"{creds_fp} unavailable."

        if os.path.exists(token_fp):
            creds = Credentials.from_authorized_user_file(token_fp, self._SCOPES)
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
            else:
                flow = InstalledAppFlow.from_client_secrets_file(creds_fp, self._SCOPES)
                creds = flow.run_local_server(port=0)
            with open(token_fp, 'w') as token:
                log.info('Writing to %s' % token_fp)
                token.write(creds.to_json())
        if creds:
            log.info(f'Google Calendar authenticated successfully.')
            self._service = build('calendar', 'v3', credentials=creds)

    def get_cal_info(self, cal_id: str):
        return self._service.calendars().get(calendarId=cal_id).execute()

    def get_events(self, cal_id: str):
        return self._service.events().list(calendarId=cal_id).execute()

    def create_event(self, cal_id, task: Task):
        log.debug(f"Creating new event cal_id:{cal_id}, summary:{task.title}")
        return self._service.events().insert(calendarId=cal_id,
                                             body=task.to_event(cal_id)).execute()

    def update_event(self, cal_id, event: Event):
        log.debug(f"Updating event cal_id:{cal_id}, summary:{event.title}")
        return self._service.events().patch(calendarId=cal_id, eventId=event._id,
                                            body=event.to_json()).execute()

    def delete_event(self, cal_id, event: Event):
        log.debug(f"deleting event cal_id:{cal_id}, summary:{event.title}")
        self._service.events().delete(calendarId=cal_id, eventId=event._id).execute()

    def move_event(self, event: Event, src_calid, dest_calid):
        log.debug(f"moving event cal_id:{src_calid} -> {dest_calid}, summary:{event.title}")
        self._service.events().move(calendarId=src_calid, eventId=event._id, destination=dest_calid).execute()


class NotionClient(Client, metaclass=Singleton):
    def __init__(self):
        self._service: NClient = None

    def auth(self):
        self._service = NClient(auth=ConfigParser().notion_token)

    def get_tasks(self, db_id) -> []:
        # first page
        json = self._service.databases.query(
            database_id=db_id,
        )
        next_cursor = glom(json, 'next_cursor', default=None)
        while next_cursor is not None:
            next_json = self._service.databases.query(database_id=db_id, start_cursor=next_cursor)
            json["results"].extend(next_json["results"])
            next_cursor = glom(next_json, 'next_cursor', default=None)
        return json

    def get_updated_tasks(self, db_id):
        json = self._service.databases.query(
            database_id=db_id,
            **{
                "filter": {
                    "and": [
                        {
                            "property": "Last Edited Time",
                            "date": {
                                "after": "2021-08-11T09:53:00.000Z"
                            }
                        }
                    ]
                }
            })

        log.info(f"Notion update response: {len(json.get('results', []))}")
        # if json.get('results', []):
        #     # results = [NTask(res) for res in json.get('results', [])]
        #     return results
        # else:
        #     return []

    def create_task(self, db_id, event):
        json = self._service.pages.create(properties=event.to_task(), parent={"database_id": db_id})
        log.debug(f"created new notion task, {event.title}")
        return json

    def update_task(self, task):
        json = self._service.pages.update(task._id, properties=task.to_json())
        log.debug(f"updated notion task, {task.title}")
        return json

    def delete_page(self, task):
        """Technically Archive tasks"""
        json = self._service.pages.update(task._id, properties=task.to_json(), archived=True)
        log.debug(f"updated notion task, {task.title}")
        return json


if __name__ == '__main__':
    logging.basicConfig(format='%(asctime)s %(name)s:%(lineno)s\t %(message)s',
                        datefmt='%m/%d/%Y %I:%M:%S %p', level=logging.INFO)

    ConfigParser().initialize("config.ini")

    nc = NotionClient()
    nc.auth()
    vals = nc.get_tasks(db_id="0a7c2dacda8b421697894a57239c549f")
    log.debug(vals)
    nc.update_task()

    # gc = GoogleClient()
    # gc.auth()
    # gc.get_events()
