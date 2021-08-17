import logging

from typing import Dict, List
from glom import  glom

from config_parser import ConfigParser
from client import GoogleClient, NotionClient

from tasks import Event, Task

log = logging.getLogger(__name__)


class GCal:
    date_fmt = "%Y-%m-%dT%H:%M:%S"

    def __init__(self, cal_id, timezone):
        self.cal_id = cal_id
        self.cal_tz = None
        self.cal_name = None
        self.idToEvent: Dict[str, Event] = {}

    def bootstrap(self):
        log.info(f"bootstraping GCal")
        metajson = GoogleClient().get_cal_info(self.cal_id)
        self.cal_name = glom(metajson, "summary")
        self.cal_tz = glom(metajson, "timeZone")

        events = self.get_events()
        self.idToEvent = {evnt._id: evnt for evnt in events}
        return self

    def get_events(self, **kwargs):
        json = GoogleClient().get_events(self.cal_id)
        log.debug(f'google client, updates received, cal:{json["summary"]}, events:{len(json.get("items", []))}')
        results = [Event(event, self.cal_id, self.cal_tz) for event in json.get('items', [])]
        return results

    def notion_tasks(self):
        """Returns events that are created by notion"""
        return [e for e in self.idToEvent.values() if e.src_url]

    def create_events(self, ntasks: List[Task]):
        events: List[Event] = []
        for tsk in ntasks:
            json = GoogleClient().create_event(self.cal_id, tsk)
            event = Event(json, self.cal_id, self.cal_tz, cal_name=self.cal_name)
            self.idToEvent[event._id] = event
            events.append(event)
        return events

    def delete_events(self, events:List[Event]):
        events_deleted = []
        for e in events:
            json = GoogleClient().delete_event(self.cal_id, e)
            del self.idToEvent[e._id]
            events_deleted.append(e)
        return events_deleted

    def update_events(self, events: List[Event]):
        events_updated = []
        for e in events:
            json = GoogleClient().update_event(self.cal_id, e)
            events_updated.append(e)
        return events_updated

    def create_tasks_for_events(self):
        new_events = []
        for e in self.idToEvent.values():
            if not e.src_url:
                new_events.append(e)
        log.info(f'manual events created:cal:{self.cal_name}, {len(new_events)}')

        events = []
        tasks = ndb.create_tasks(new_events)
        log.info(f"Tasks created, {len(tasks)}")
        for task in tasks:
            self.idToEvent[task.gevnt_id].src_url = task.src_url
            events.append(self.idToEvent[task.gevnt_id])

        log.info(f"events to update in calendar, {len(tasks)}")
        events = self.update_events(events)
        log.info(f"events updated, {len(events)}")

    def delete_tasks_for_events(self):
        # TODO:P1 Move this method to NotionDB
        del_tasks = []
        for t in ndb.scheduled_tasks():
            if t.gevnt_id not in self.idToEvent:
                del_tasks.append(t)
        log.info(f"Tasks to delete, {len(del_tasks)}")
        del_tasks = ndb.delete_tasks(del_tasks)
        log.info(f"Tasks deleted, {len(del_tasks)}")

    def update_events_for_tasks(self):
        updated_tasks = []
        for t in ndb.scheduled_tasks():
            t = self.idToEvent[t.gevnt_id].compare(t)
            if t is not None:
                updated_tasks.append(t)
        log.info(f"Tasks to update, {len(updated_tasks)}")

        updated_tasks = ndb.update_tasks(updated_tasks)
        log.info(f"Tasks updated, {len(updated_tasks)}")

class NDb:
    def __init__(self, db_id):
        self.db_id = db_id
        self.idToTask: Dict[str, Task] = {}
        self.gidToTask: Dict[str, Task] = {}

        self._to_update = set()

    def bootstrap(self):
        log.info(f"bootstraping Notion DB")
        self.idToTask = {tsk._id: tsk for tsk in self.get_tasks()}
        return self

    def get_tasks(self):
        json = NotionClient().get_tasks(self.db_id)
        results = [Task(task, self.db_id) for task in json.get('results', [])]
        return results

    def scheduled_tasks(self) -> List[Task]:
        """Returns tasks which are scheduled on GCalendar"""
        return [t for t in self.idToTask.values() if t.scheduled and t.gevnt_id]

    def create_events_for_tasks(self):
        tasks_created = []
        for tsk in self.idToTask.values():
            if tsk.scheduled and not tsk.gevnt_id:
                tasks_created.append(tsk)
        log.info(f"Events to create, {len(tasks_created)}")

        events = gcal.create_events(tasks_created)
        log.info(f"Events created, {len(events)}")
        for evnt in events:
            self.idToTask[evnt.notion_id].gevnt_id = evnt._id

        log.info(f"tasks to update in notion, {len(tasks_created)}")
        self._commit(tasks_created)
        return self

    def delete_events_for_tasks(self):
        del_events = []
        tasks_updated = []
        for event in gcal.notion_tasks():
            if event.notion_id not in self.idToTask:
                del_events.append(event)
            elif self.idToTask[event.notion_id].scheduled is False:
                del_events.append(event)
                tasks_updated.append(self.idToTask[event.notion_id])
        log.info(f"Events to delete, {len(del_events)}")

        events = gcal.delete_events(del_events)
        log.info(f"Events deleted, {len(del_events)}")

        for t in tasks_updated:
            t.gevnt_id = ""
        log.info(f"tasks to update in notion, {len(tasks_updated)}")
        self._commit(tasks_updated)
        return self

    def update_events_for_tasks(self):
        update_events = []
        for event in gcal.notion_tasks():
            event = self.idToTask[event.notion_id].compare(event)
            if event is not None:
                update_events.append(event)
        log.info(f"Events to update, {len(update_events)}")

        updated_events = gcal.update_events(update_events)
        log.info(f"Events updated, {len(updated_events)}")

    def _commit(self, tsks):
        for tsk in tsks:
            self._to_update.add(tsk)

    def push(self):
        log.info(f"tasks updated in notion db, {len(self._to_update)}")
        for tsk in self._to_update:
            NotionClient().update_task(tsk)
        self._to_update.clear()

    def create_tasks(self, events: List[Event]):
        tasks: List[Task] = []
        for event in events:
            json = NotionClient().create_task(self.db_id, event)
            task = Task(json, self.db_id)
            self.idToTask[task._id] = task
            tasks.append(task)
        return tasks

    def delete_tasks(self, tasks:List[Task]):
        tasks_deleted = []
        for t in tasks:
            json = NotionClient().delete_page(t)
            del self.idToTask[t._id]
            tasks_deleted.append(t)
        return tasks_deleted

    def update_tasks(self, tasks: List[Task]):
        tasks_updated = []
        for t in tasks:
            json = NotionClient().update_task(t)
            tasks_updated.append(t)
        return tasks_updated


if __name__ == '__main__':
    logging.basicConfig(format='%(asctime)s %(name)s:%(lineno)s\t %(message)s', datefmt='%m/%d/%Y %I:%M:%S %p', level=logging.INFO)
    ConfigParser().initialize("config.ini")

    gc = GoogleClient()
    gc.auth()
    gcal = GCal(ConfigParser().default_gcal_id, ConfigParser().timezone).bootstrap()
    nc = NotionClient()
    nc.auth()
    ndb = NDb(db_id=ConfigParser().task_database_id).bootstrap()

    log.info("***************syncing from gcal to notion************")
    ndb.create_events_for_tasks().push()
    ndb.delete_events_for_tasks().push()
    ndb.update_events_for_tasks()
    log.info("*****************syncing from notion to gcal**********")
    gcal.create_tasks_for_events()
    gcal.delete_tasks_for_events()
    gcal.update_events_for_tasks()




