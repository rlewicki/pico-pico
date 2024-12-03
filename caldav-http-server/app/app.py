from flask import Flask
from flask import request
import caldav
import json
from datetime import datetime
from datetime import timedelta
import os
from unidecode import unidecode

def fill_event(component, calendar) -> dict[str, str]:
    cur = {}
    cur["calendar"] = unidecode(f"{calendar}")
    cur["summary"] = unidecode(component.get("summary"))
    description = component.get("description")
    if description is not None:
        cur["description"] = unidecode(description)
    cur["start"] = component.get("dtstart").dt.strftime("%m/%d/%Y %H:%M")
    endDate = component.get("dtend")
    if endDate and endDate.dt:
        cur["end"] = endDate.dt.strftime("%m/%d/%Y %H:%M")
    cur["datestamp"] = component.get("dtstamp").dt.strftime("%m/%d/%Y %H:%M")
    return cur

caldav_url = os.environ.get("CALDAV_SERVER_URI")

app = Flask(__name__)

@app.route('/agenda')
def agenda():
    caldev_username = request.args.get('username')
    caldev_password = request.args.get('password')
    if caldev_username == None or caldev_password == None:
        return "failed to provide username or password", 400
    caldav_client = caldav.DAVClient(
        url=caldav_url,
        username=caldev_username,
        password=caldev_password)
    if not caldav_client:
        return "failed to create caldav client", 400
    principal = caldav_client.principal()
    calendars = principal.calendars()
    events = []
    for calendar in calendars:
        events_fetched = calendar.search(
            start=datetime.now(),
            end=datetime.now() + timedelta(days=7),
            event=True,
        )
        for event in events_fetched:
            for component in event.icalendar_instance.walk():
                if component.name != "VEVENT":
                    continue
                events.append(fill_event(component, calendar))
    return json.dumps(events, indent=2, ensure_ascii=False)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8000)
