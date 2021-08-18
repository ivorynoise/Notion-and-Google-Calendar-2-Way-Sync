import logging

from typing import Dict, List
from glom import  glom

from utils import  Singleton
from config_parser import ConfigParser
from client import GoogleClient, NotionClient

from tasks import Event, Task

log = logging.getLogger(__name__)



class GCal:
    date_fmt = "%Y-%m-%dT%H:%M:%S"

    def __init__(self, cal_id: str, label: str):
        self.cal_id = cal_id
        self.label = label
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

    def notion_events(self):
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
            if t.gevnt_id not in self.idToEvent and Calendars().exists(t.gevnt_id) is False:
                del_tasks.append(t)
        log.info(f"Tasks to delete, {len(del_tasks)}")
        del_tasks = ndb.delete_tasks(del_tasks)
        log.info(f"Tasks deleted, {len(del_tasks)}")

    def update_tasks_for_events(self):
        """Update tasks for which a manual update is triggered on Google Event"""
        updated_tasks = []
        for t in ndb.scheduled_tasks():
            e = self.idToEvent.get(t.gevnt_id, None) # task with valid event id can exist in another calendar
            if e:
                t = e.compare(t)
                if t:
                    updated_tasks.append(t)
        log.info(f"Tasks to update, {len(updated_tasks)}")

        updated_tasks = ndb.update_tasks(updated_tasks)
        log.info(f"Tasks updated, {len(updated_tasks)}")

    def moved_events(self):
        moved_events = []
        tasks_to_update = []
        for e in self.notion_events():
            if e.previous != e.cal_id:
                t = ndb.idToTask[e.notion_id]
                t.completed = False if self.label == "default" else True
                e.previous = e.cal_id
                moved_events.append(e)
                tasks_to_update.append(t)
        log.info(f'events moved: {self.cal_name}, {len(moved_events)}, tasks to update: {len(tasks_to_update)}')

        moved_events = self.update_events(moved_events)
        tasks_to_update = ndb.update_tasks(tasks_to_update)
        log.info(f"events updated, {len(moved_events)}, tasks updated:{len(tasks_to_update)}")





class Calendars(metaclass=Singleton):
    def __init__(self):
        self.nameToCalendar: Dict[str, GCal] = {}

    def bootstarp(self, calendars):
        for cal, calId in calendars.items():
            self.nameToCalendar[cal] = GCal(calId, cal).bootstrap()
        return self

    @property
    def default(self) -> GCal:
        return self.nameToCalendar["default"]

    @property
    def completed(self) -> GCal:
        return self.nameToCalendar["completed"]

    def exists(self, eventId: str) -> bool:
        for cal in self.nameToCalendar.values():
            if cal.idToEvent.get(eventId, None):
                return True
        return False

    def move_events(self):
        completed = []
        incomplete = []

        for e in self.default.notion_events():
            t = ndb.idToTask[e.notion_id]
            if t.completed:
                completed.append(e)
        for e in self.completed.notion_events():
            t = ndb.idToTask[e.notion_id]
            if t.completed is False:
                incomplete.append(e)

        for e in completed:
            GoogleClient().move_event(e, src_calid=self.default.cal_id, dest_calid=self.completed.cal_id)
            self.completed.idToEvent[e._id] = e
            del self.default.idToEvent[e._id]
            e.cal_id = self.completed.cal_id
            e.previous = self.completed.cal_id
            GoogleClient().update_event(e.cal_id, e)
        for e in incomplete:
            GoogleClient().move_event(e, src_calid=self.completed.cal_id, dest_calid=self.default.cal_id)
            self.default.idToEvent[e._id] = e
            del self.completed.idToEvent[e._id]
            e.cal_id = self.default.cal_id
            e.previous = self.default.cal_id
            GoogleClient().update_event(e.cal_id, e)
        log.info(f"events completed, {len(completed)}, moved to complete from default")
        log.info(f"events incompleted, {len(incomplete)}, moved to default from completed ")


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

        events = cals.default.create_events(tasks_created)
        log.info(f"Events created, {len(events)}")
        for evnt in events:
            self.idToTask[evnt.notion_id].gevnt_id = evnt._id

        log.info(f"tasks to update in notion, {len(tasks_created)}")
        self._commit(tasks_created)
        return self

    def delete_events_for_tasks(self):
        """Deletes event in default calendar if the corresponding task in notion is deleted"""
        del_events = []
        tasks_updated = []
        for event in cals.default.notion_events():
            if event.notion_id not in self.idToTask:
                del_events.append(event)
            elif self.idToTask[event.notion_id].scheduled is False:
                del_events.append(event)
                tasks_updated.append(self.idToTask[event.notion_id])
        log.info(f"Events to delete, {len(del_events)}")

        events = cals.default.delete_events(del_events)
        log.info(f"Events deleted, {len(del_events)}")

        for t in tasks_updated:
            t.gevnt_id = ""
        log.info(f"tasks to update in notion, {len(tasks_updated)}")
        self._commit(tasks_updated)
        return self

    def update_events_for_tasks(self):
        update_events = []
        for event in cals.default.notion_events():
            event = self.idToTask[event.notion_id].compare(event)
            if event is not None:
                update_events.append(event)
        log.info(f"Events to update, {len(update_events)}")

        updated_events = cals.default.update_events(update_events)
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
    cals = Calendars().bootstarp(ConfigParser().calendars)
    nc = NotionClient()
    nc.auth()
    ndb = NDb(db_id=ConfigParser().task_database_id).bootstrap()

    # log.info("***************syncing from gcal to notion************")
    ndb.create_events_for_tasks().push()
    ndb.delete_events_for_tasks().push()
    ndb.update_events_for_tasks()

    # log.info("*****************syncing from notion to default gcal**********")
    cals.default.create_tasks_for_events()
    cals.default.delete_tasks_for_events()
    cals.default.update_tasks_for_events()

    cals.default.moved_events()
    cals.completed.moved_events()
    Calendars().move_events()



