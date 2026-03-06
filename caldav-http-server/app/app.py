from pprint import pprint

from flask import Flask
from flask import request
from caldav import get_davclient
import json
from datetime import datetime
from datetime import timedelta
import os
from unidecode import unidecode

def fill_event(component, calendar) -> dict[str, str]:
    cur = {}
    cur["summary"] = unidecode(component.get("summary"))
    description = component.get("description")
    if description is not None:
        cur["description"] = unidecode(description)
    start_date = component.get("dtstart")
    cur["start_date"] = start_date.dt.strftime("%m/%d/%Y %H:%M")
    cur["whole_day_event"] = False
    if "value" in start_date.params:
        cur["whole_day_event"] = True
    endDate = component.get("dtend")
    if endDate and endDate.dt:
        cur["end"] = endDate.dt.strftime("%m/%d/%Y %H:%M")
    return cur

caldav_url = os.environ.get("CALDAV_URL")

app = Flask(__name__)

@app.route('/agenda')
def agenda():
    caldav_username = request.args.get('username')
    caldav_password = request.args.get('password')
    days = int(request.args.get('days'))
    if caldav_username == None or caldav_password == None:
        return "failed to provide username or password", 400
    
    with get_davclient(url=caldav_url, username=caldav_username, password=caldav_password) as client:
        client.ssl_verify_cert = False
        principal = client.principal()
        calendars = principal.calendars()
        events = []
        for calendar in calendars:
            events_fetched = calendar.search(
                start=datetime.now(),
                end=datetime.now() + timedelta(days=days),
                event=True,
            )
            for event in events_fetched:
                for component in event.icalendar_instance.walk():
                    if component.name != "VEVENT":
                        continue
                    events.append(fill_event(component, calendar))
        return json.dumps(events, indent=2, ensure_ascii=False)
    return "failed to create caldav client", 400

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8000)
