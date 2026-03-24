from flask import Flask
from flask import request
from caldav import get_davclient
import json
from datetime import datetime
from datetime import timedelta
import os
from unidecode import unidecode
import random

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
        cur["end_date"] = endDate.dt.strftime("%m/%d/%Y %H:%M")
    return cur

caldav_url = os.environ.get("CALDAV_URI")

app = Flask(__name__)

@app.route('/agenda')
def agenda():
    caldav_username = request.args.get('username')
    caldav_password = request.args.get('password')
    days = int(request.args.get('days'))
    if caldav_username is None or caldav_password is None:
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


@app.route('/quote')
def quote():
    quotes = []
    with open("quotes.txt") as f:
        for line in f:
            quote_author_pair = line.split("$")
            quotes.append(quote_author_pair)
    selected_quote = random.randint(0, len(quotes) - 1)
    a = quotes[selected_quote][1].replace('\n', '')
    q = quotes[selected_quote][0].replace('\n', '')
    response = {
        "author": a,
        "quote": q 
    }
    return response, 200


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8000)
