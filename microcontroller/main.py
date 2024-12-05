import time
from machine import Pin
import network
import ntptime
import urequests
import json

from color_setup import ssd
from gui.core.writer import Writer
from gui.core.nanogui import refresh
from gui.widgets.label import Label
import gui.fonts.arial10 as arial10
import gui.fonts.courier20 as courier20

class AgendaEntry:
    def __init__(self) -> None:
        self.day = -1
        self.month = -1
        self.year = -1
        self.time = None
        self.description = None

month_names = [
    "Styczen",
    "Luty",
    "Marzec",
    "Kwiecien",
    "Maj",
    "Czerwiec",
    "Lipiec",
    "Sierpien",
    "Wrzesien",
    "Pazdziernik",
    "Listopad",
    "Grudzien"
]

led_pin = machine.Pin('LED', Pin.OUT)
caldav_username = ""
caldav_password = ""
caldav_uri = ""
caldav_port = ""
agenda = []

def connect_to_wifi(ssid, password):
    wlan = network.WLAN(network.STA_IF)
    wlan.active(True)
    wlan.connect(ssid, password)
    while not wlan.isconnected():
        print("waiting for Internet connection...")
        time.sleep(1)
    print(wlan.ifconfig())
    
def set_current_time():
    ntptime.settime()
    current_time = time.localtime()
    print("{}:{}:{}, {}/{}/{}".format(
        current_time[3] + 1, 
        current_time[4], 
        current_time[5], 
        current_time[2], 
        current_time[1], 
        current_time[0]))
    
def read_wifi_credentials():
    f = open("wifi.txt", "r")
    data = f.read().splitlines()
    if len(data) < 2:
        print("failed to find wifi credentials")
        exit(1)
    ssid = data[0]
    password = data[1]
    return ssid, password

def read_caldav_credentials():
    f = open("caldav.txt", "r")
    data = f.read().splitlines()
    if len(data) < 4:
        print("failed to read caldav credentials")
        exit(1)
    username = data[0]
    password = data[1]
    uri = data[2]
    port = data[3]
    return username, password, uri, port

def http_get_request(url):
    response = urequests.get(url)
    return response.text

def get_agenda_data(caldav_url):
    response = http_get_request(caldav_url)
    events = json.loads(response)
    agenda = []
    for event in events:
        new_entry = AgendaEntry()
        date = event['start'].split()
        date_components = date[0].split('/')
        new_entry.day = int(date_components[1])
        new_entry.month = int(date_components[0])
        new_entry.year = int(date_components[2])
        new_entry.time = date[1]
        new_entry.description = event['summary']
        agenda.append(new_entry)
    return agenda
        
def get_current_date():
    current_time = time.localtime()
    current_time = "{}:{}:{}".format(current_time[3] + 1, current_time[4], current_time[5])
    return current_time;

def update_agenda():
    # Obviously passing username and password as URL parameters is not safe but this is all supposed to stay within
    # local network so I don't really care about anyone seeing this.
    global agenda
    caldav_request_uri = "http://" + caldav_uri + ":" + caldav_port + "/agenda?username=" + caldav_username + "&password=" + caldav_password
    print("fetching agenda from calendar...")
    try:
        agenda = get_agenda_data(caldav_request_uri)
        agenda.sort(key=lambda x: (x.year, x.month, x.day, x.time))
        return True
    except:
        print("failed to fetch new agenda")
        return False
    
def display_agenda():
    print(f"displaying {len(agenda)} agenda items...")
    refresh(ssd, True)
    ssd.wait_until_ready()
    row = 6
    for entry in agenda:
        Label(wri_small_font, row, 0, f"{entry.day} {month_names[entry.month - 1]} {entry.year} {entry.time}")
        row += arial10.height()
        Label(wri_big_font, row, 0, entry.description)
        row += courier20.height()
        if row + arial10.height() > ssd.height:
            break
    refresh(ssd)
    ssd.wait_until_ready()
    ssd.sleep()
    
def boot_sequence():
    print("booting up...")
    time.sleep(0.33)
    print("reading config files...")
    wifi_ssid, wifi_password = read_wifi_credentials()
    print("connecting to wifi network...")
    connect_to_wifi(wifi_ssid, wifi_password)
    set_current_time()

boot_sequence()
print("initializing display...")
wri_small_font = Writer(ssd, arial10, verbose=False)
wri_small_font.set_clip(False, False, False)

wri_big_font = Writer(ssd, courier20, verbose=False)
wri_big_font.set_clip(False, False, False)

refresh(ssd, True)
ssd.wait_until_ready()

caldav_username, caldav_password, caldav_uri, caldav_port = read_caldav_credentials()
success = update_agenda()
if success:
    display_agenda()

def loop():
    current_date = get_current_date()
    led_pin.toggle()
    time.sleep(1)

while True:
    loop()
