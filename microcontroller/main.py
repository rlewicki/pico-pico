import time
from machine import Pin
import network
import socket
import ntptime
import urequests
import ujson
import hmac
import hashlib
import json
from epaper import EPD_2in13_V4_Landscape

class AgendaEntry:
    def __init__(self) -> None:
        self.date = {}
        self.time = {}
        self.description = {}

led_pin = machine.Pin('LED', Pin.OUT)
caldav_username = ""
caldav_password = ""
caldav_uri = ""

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
        new_entry.date = date[0]
        new_entry.time = date[1]
        new_entry.description = event['summary']
        agenda.append(new_entry)
    return agenda
        
def get_current_date():
    current_time = time.localtime()
    current_time = "{}:{}:{}".format(current_time[3] + 1, current_time[4], current_time[5])
    return current_time;
    
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
display = EPD_2in13_V4_Landscape()
display.Clear()
display.fill(0xff)

# Obviously passing username and password as URL parameters is not safe but this is all supposed to stay within
# local network so I don't really care about anyone seeing this.
caldav_username, caldav_password, caldav_uri, caldav_port = read_caldav_credentials()
caldav_request_uri = "http://" + caldav_uri + ":" + caldav_port + "/agenda?username=" + caldav_username + "&password=" + caldav_password
agenda = get_agenda_data(caldav_request_uri)
for entry in agenda:
    display.text(entry.description, 0, 10, 0x00)
    display.display(display.buffer)
    display.sleep()

display.display(display.buffer)
display.sleep()

def loop():
    current_date = get_current_date()
    led_pin.toggle()
    time.sleep(1)

while True:
    loop()
