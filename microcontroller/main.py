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

import forecast_images

class WeatherEntry:
    def __init__(self) -> None:
        self.date = -1
        self.temp_min = -1
        self.temp_max = -1
        self.precipitation = -1
        self.weather_code = -1

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

weather_code_to_icon = {
    0: forecast_images.clear_sky,
    1: forecast_images.cloudy_light,
    2: forecast_images.cloudy_medium,
    3: forecast_images.cloudy_heavy,
    45: forecast_images.fog,
    48: forecast_images.fog,
    51: forecast_images.sprinkle,
    53: forecast_images.sprinkle,
    55: forecast_images.sprinkle,
    56: forecast_images.rain_mix,
    57: forecast_images.rain_mix,
    61: forecast_images.showers,
    63: forecast_images.hail,
    65: forecast_images.hail,
    71: forecast_images.snow,
    73: forecast_images.snow,
    75: forecast_images.snow,
    77: forecast_images.snow,
    80: forecast_images.showers,
    81: forecast_images.showers,
    82: forecast_images.showers,
    85: forecast_images.snow,
    86: forecast_images.snow,
    95: forecast_images.thunderstorm,
    96: forecast_images.thunderstorm,
    99: forecast_images.thunderstorm
}

led_pin = machine.Pin('LED', Pin.OUT)
caldav_username = ""
caldav_password = ""
caldav_uri = ""
caldav_port = ""
open_meteo_uri = ""
agenda = []
weather_info = []

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

def get_open_meteo_uri():
    f = open('open-meteo.txt', 'r')
    uri = f.read()
    return uri

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


def fetch_weather_info(uri):
    Label(wri_big_font, int(ssd.height / 2 - wri_big_font.height / 2), 8, "updating forecast")
    refresh(ssd)
    ssd.wait_until_ready()
    response = http_get_request(uri)
    forecast = json.loads(response)
    current = WeatherEntry()
    current.date = forecast["daily"]["time"][0]
    current.temp_min = forecast["current"]["temperature_2m"]
    current.temp_max = current.temp_min
    current.precipitation = forecast["current"]["precipitation"]
    current.weather_code = forecast["current"]["weather_code"]
    
    daily_data = forecast["daily"]
    tomorrow = WeatherEntry()
    tomorrow.date = daily_data["time"][1]
    tomorrow.temp_min = daily_data["temperature_2m_min"][1]
    tomorrow.temp_max = daily_data["temperature_2m_max"][1]
    tomorrow.precipitation = daily_data["precipitation_probability_max"][1]
    tomorrow.weather_code = daily_data["weather_code"][1]
    
    day_after_tomorrow = WeatherEntry()
    day_after_tomorrow.date = daily_data["time"][2]
    day_after_tomorrow.temp_min = daily_data["temperature_2m_min"][2]
    day_after_tomorrow.temp_max = daily_data["temperature_2m_max"][2]
    day_after_tomorrow.precipitation = daily_data["precipitation_probability_max"][2]
    day_after_tomorrow.weather_code = daily_data["weather_code"][2]
    
    weather_info = [
        current,
        tomorrow,
        day_after_tomorrow
    ]

    return weather_info

def display_image(pos_x, pos_y, width, height, img_data):
    for y in range(height):
        for x in range(width):
            if not img_data[y * (width // 8) + (x // 8)] & (128 >> (x % 8)):
                ssd.pixel(pos_x + x, pos_y + y, 0xff)
    
def display_weather_info(uri):
    global weather_info
    if len(weather_info) <= 0:
        refresh(ssd, True)
        ssd.wait_until_ready()
        weather_info = fetch_weather_info(uri)
    forecast_now = weather_info[0]
    forecast_tomorrow = weather_info[1]
    forecast_day_after_tomorrow = weather_info[2]
    refresh(ssd, True)
    ssd.wait_until_ready()
    Label(wri_small_font, 12, 20, "Teraz")
    Label(wri_small_font, 12, 110, "Jutro")
    Label(wri_small_font, 12, 185, "Pojutrze")
    
    temp_now_field = Label(wri_big_font, 35, 10, wri_big_font.stringlen("-99C"))
    precipitation_now_field = Label(wri_big_font, 58, 10, wri_big_font.stringlen("100%"))
    
    temp_min_tomorrow_field = Label(wri_big_font, 35, 95, wri_big_font.stringlen("-99C"))
    temp_max_tomorrow_field = Label(wri_big_font, 58, 95, wri_big_font.stringlen("-99C"))
    
    temp_min_day_after_tomorrow_field = Label(wri_big_font, 35, 175, wri_big_font.stringlen("-99C"))
    temp_max_day_after_tomorrow_field = Label(wri_big_font, 58, 175, wri_big_font.stringlen("-99C"))
    
    icons_height = 65
    icons_size = 64
    
    temp_now_field.value(f"{forecast_now.temp_min}C")
    precipitation_now_field.value(f"{int(forecast_now.precipitation)}%")
    display_image(0, icons_height, icons_size, icons_size, weather_code_to_icon[forecast_now.weather_code])
    
    temp_min_tomorrow_field.value(f"{forecast_tomorrow.temp_min}C")
    temp_max_tomorrow_field.value(f"{forecast_tomorrow.temp_max}C")
    display_image(85, icons_height, icons_size, icons_size, weather_code_to_icon[forecast_tomorrow.weather_code])
    
    temp_min_day_after_tomorrow_field.value(f"{forecast_day_after_tomorrow.temp_min}C")
    temp_max_day_after_tomorrow_field.value(f"{forecast_day_after_tomorrow.temp_max}C")
    display_image(160, icons_height, icons_size, icons_size, weather_code_to_icon[forecast_day_after_tomorrow.weather_code])

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

open_meteo_uri = get_open_meteo_uri()
print(f"open meteo uri: {open_meteo_uri}")

print("initializing display...")
wri_small_font = Writer(ssd, arial10, verbose=False)
wri_small_font.set_clip(True, True, False)

wri_big_font = Writer(ssd, courier20, verbose=False)
wri_big_font.set_clip(True, True, False)

refresh(ssd, True)
ssd.wait_until_ready()

caldav_username, caldav_password, caldav_uri, caldav_port = read_caldav_credentials()
# success = update_agenda()
# if success:
#     display_agenda()
display_weather_info(open_meteo_uri)

def loop():
    current_date = get_current_date()
    led_pin.toggle()
    time.sleep(1)

while True:
    loop()
