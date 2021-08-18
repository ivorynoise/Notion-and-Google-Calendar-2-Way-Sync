import logging
import  re

from abc import ABC
from glom import glom, T
from datetime import datetime
from dateutil.parser import parse
from dateutil.tz import tzlocal


log = logging.getLogger(__name__)

class Event:
    def __init__(self, json, calid, timezone, *args, **kwargs):
        # super().__init__()
        self.cal_id: str = calid
        self.cal_name = kwargs.get("cal_name", "???")
        self.timezone = timezone
        self.all_day_event = ""

        self._event_id = glom(json, "id")

        self.status = glom(json, "status")
        self.last_updated = parse(glom(json, "updated"))
        self.title = glom(json, "summary", default="")
        # google stores upto seconds but notion doesnt hence seconds info has been removed
        self.start = parse(glom(json, "start.dateTime")).replace(second=0, microsecond=0)
        self.end = parse(glom(json, "end.dateTime")).replace(second=0, microsecond=0)
        self.src_url = glom(json, "source.url", default="")
        self.previous: str = glom(json, "extendedProperties.shared.previousCalId", default=self.cal_id)

    def __repr__(self):
        return f"<GTask:{self.title}|{self.start}|{self.end}|" \
               f"{self.src_url if self.src_url else 'XXX'}>"

    @property
    def _id(self):
        return self._event_id.replace("-", "")

    @property
    def notion_id(self):
        return re.split('[/-]', self.src_url)[-1] if self.src_url else None

    def to_json(self):
        event = {
            'summary': self.title,
            'start': {
                'dateTime': self.start.isoformat('T'),
            },
            'end': {
                'dateTime': self.end.isoformat('T'),
            },
            'source': {
                'title': 'Notion Link',
                'url': self.src_url,
            },
            "extendedProperties": {
                "shared": {
                    "previousCalId": self.previous
                }
            }
        }
        return event

    def to_task(self):
        properties = {
            "On GCal?": {
                "checkbox": True
            },
            "Done?": {
                "checkbox": False
            },
            "Date": {
                "date": {
                    "start": self.start.isoformat('T'),
                    "end": self.end.isoformat('T')
                }
            },
            "GCal Event Id": {
                "rich_text": [
                    {
                        "type": "text",
                        "text": {
                            "content": self._id
                        }
                    }
                ]
            },
            "Task": {
                "title": [
                    {
                        "type": "text",
                        "text": {
                            "content": self.title
                        }
                    }
                ]
            }
        }
        return properties

    def compare(self, task):
        """Returns an new updated event if a notion task is updated manually"""
        # TODO: P2: Change update basis
        updated = (self.last_updated > task.last_updated and (
            self.title != task.title or
            self.start != task.start or
            self.end != task.end))
        if updated:
            task.title = self.title
            task.start = self.start
            task.end = self.end
            return task

        return None


class Task:
    default_date = datetime.now(tzlocal()).isoformat('T')

    def __init__(self, json, db_id):
        super().__init__()
        self.db_id = db_id
        self.task_id = glom(json, "id")
        self.last_updated = parse(glom(json, 'last_edited_time'))
        self.archived = glom(json, "archived", default=False)
        self.src_url = glom(json, "url")

        n_properties = json["properties"]
        self.title = glom(n_properties, ("Task.title", ['text.content'], T[0]), default="")
        self.scheduled = glom(n_properties, "On GCal?.checkbox", default=False)
        self.gevnt_id = glom(n_properties, ("GCal Event Id.rich_text", [T], T[0], 'plain_text'), default="")
        self.completed = glom(n_properties, "Done?.checkbox", default=False)

        self.start = glom(n_properties, "Date.date.start", default=self.default_date)
        self.end = glom(n_properties, "Date.date.end", default=self.default_date)
        if not self.start:  # can be JS null -> None
            self.start = self.default_date
        if not self.end:
            self.end = self.start
        self.start = parse(self.start).replace(second=0, microsecond=0)
        self.end = parse(self.end).replace(second=0, microsecond=0)

    def __repr__(self):
        return f"<Ntask:{self._id}|{self.title}|{self.last_updated}|{self.start}|{self.end}"

    @property
    def _id(self):
        return self.task_id.replace("-", "")

    def to_event(self, cal_id):
        event = {
            'summary': self.title,
            'start': {
                'dateTime': self.start.isoformat('T'),
            },
            'end': {
                'dateTime': self.end.isoformat('T'),
            },
            'source': {
                'title': 'Notion Link',
                'url': self.src_url,
            },
            "extendedProperties": {
                "shared": {
                    "previousCalId": cal_id
                }
            }
        }
        return event

    def to_json(self):
        properties = {
            "On GCal?": {
                "checkbox": self.scheduled
            },
            "Done?": {
                "checkbox": self.completed
            },
            "Date": {
                "date": {
                    "start": self.start.isoformat('T'),
                    "end": self.end.isoformat('T')
                }
            },
            "GCal Event Id": {
                "rich_text": [
                    {
                        "type": "text",
                        "text": {
                            "content": self.gevnt_id
                        }
                    }
                ]
            },
            "Task": {
                "title": [
                    {
                        "type": "text",
                        "text": {
                            "content": self.title
                        }
                    }
                ]
            }
        }
        return properties

    def compare(self, event: Event) -> Event:
        """Returns an new updated event if a notion task is updated manually"""
        # TODO: P2: Change update basis
        updated = (self.last_updated > event.last_updated and (
                    self.title != event.title or
                    self.start != event.start or
                    self.end != event.end))
        if updated:
            event.title = self.title
            event.start = self.start
            event.end = self.end
            return event

        return None
