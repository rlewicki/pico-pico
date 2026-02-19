import time
from machine import Pin
from machine import Timer
import network
import ntptime
import urequests
import json

from color_setup import ssd
from gui.core.writer import Writer
from gui.core.nanogui import refresh
from gui.widgets.label import Label
from gui.widgets.label import ALIGN_CENTER
from gui.widgets.label import ALIGN_LEFT
from gui.widgets.label import ALIGN_RIGHT
import gui.fonts.arial10 as arial10
import gui.fonts.courier20 as courier20

import forecast_images

from extended_gui import PicoLabel

WEATHER_FORECAST_SCREEN = 1
AGENDA_SCREEN = 2
FAILED_INITIALIZATION = 3   
FETCHING_AGENDA = 4
FETCHING_WEATHER = 5
REFRESHING_AGENDA = 6
INITIALIZING = 7

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
        self.description_lines = []

class AgendaPage:
    def __init__(self) -> None:
        self.agendaEntries = []

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

caldav_username = ""
caldav_password = ""
caldav_uri = ""
caldav_port = ""
open_meteo_uri = ""
agenda = []
agenda_pages = []
weather_info = []

button = Pin(3, Pin.IN, Pin.PULL_DOWN)
last_button_press_time = time.ticks_ms()
current_agenda_page = 0
requested_agenda_page = 0

white_led = Pin(2, Pin.OUT)
current_led_value = 1
white_led.value(current_led_value)
led_timer = None

program_state = INITIALIZING

def toggle_led(source):
    global current_led_value
    if current_led_value == 1:
        current_led_value = 0
    else:
        current_led_value = 1
    white_led.value(current_led_value)


def start_led_flashing():
    global led_timer
    led_timer = Timer(period=500, mode=Timer.PERIODIC, callback = toggle_led)
    

def stop_led_flashing():
    global led_timer
    led_timer.deinit()


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
        description_words = event['summary'].split(" ")
        description_lines = []
        sentence = ""
        sentence_width = 0
        for word in description_words:
            word_width = wri_big_font.stringlen(word)
            if sentence_width + word_width > ssd.width:
                description_lines.append(sentence)
                sentence = ""
                sentence_width = 0
            sentence += word + " "
            sentence_width += word_width + wri_big_font.stringlen(" ")
        if sentence_width > 0:
            description_lines.append(sentence[:-1])
        new_entry.description_lines = description_lines
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
    caldav_request_uri = "http://" + caldav_uri + ":" + caldav_port + "/agenda?username=" + caldav_username + "&password=" + caldav_password + "&days=60"
    print("fetching agenda from calendar...")
    try:
        agenda = get_agenda_data(caldav_request_uri)
    except:
        stop_led_flashing()
        print("failed to fetch new agenda")
        return False
    agenda.sort(key=lambda x: (x.year, x.month, x.day, x.time))
    update_agenda_paging()
    return True


def update_agenda_paging():
    global agenda_pages
    agenda_pages = []
    row = 6
    new_agenda_page = AgendaPage()
    print("paging agenda events...")
    for entry in agenda:
        row += wri_small_font.height
        row += (len(entry.description_lines) * wri_big_font.height)
        if row >= ssd.height:
            agenda_pages.append(new_agenda_page)
            new_agenda_page = AgendaPage()
            row = 6
        new_agenda_page.agendaEntries.append(entry)
    agenda_pages.append(new_agenda_page)
    print(f"Num of agenda pages created: {len(agenda_pages)}")


def display_agenda(pageIndex):
    if pageIndex < 0 or pageIndex >= len(agenda_pages):
        print(f"invalid page index ({pageIndex})")
        return

    ssd.init()
    ssd.wait_until_ready()
    refresh(ssd, True)
    ssd.wait_until_ready()
    row = 6
    agenda_page = agenda_pages[pageIndex]
    print(f"displaying {len(agenda_page.agendaEntries)} agenda items...")
    for entry in agenda_page.agendaEntries:
        Label(wri_small_font, row, 0, f"{entry.day} {month_names[entry.month - 1]} {entry.year} {entry.time}")
        row += arial10.height()
        for desc_line in entry.description_lines:
            Label(wri_big_font, row, 0, desc_line)
            row += courier20.height()
    page_label = f"{current_agenda_page + 1} / {len(agenda_pages)}"
    page_label_width = wri_small_font.stringlen(page_label)
    Label(wri_small_font, 6, 250 - page_label_width, page_label)
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
        weather_info = fetch_weather_info(uri)
    forecast_now = weather_info[0]
    forecast_tomorrow = weather_info[1]
    forecast_day_after_tomorrow = weather_info[2]
    refresh(ssd, True)
    ssd.wait_until_ready()
    
    label_width = ssd.width // 3
    first_row_height = 8
    second_row_height = 25
    third_row_height = 45
    icons_height = 60
    icons_size = 64
 
    PicoLabel(wri_small_font, "Teraz", 0, first_row_height, label_width)
    PicoLabel(wri_small_font, "Jutro", label_width, first_row_height, label_width)
    PicoLabel(wri_small_font, "Pojutrze", label_width * 2, first_row_height, label_width)
    
    PicoLabel(wri_big_font, f"{forecast_now.temp_min}C", 0, second_row_height, label_width)
    PicoLabel(wri_big_font, f"{int(forecast_now.precipitation)}%", 0, third_row_height, label_width)
    display_image(9, icons_height, icons_size, icons_size, weather_code_to_icon[forecast_now.weather_code])
    
    PicoLabel(wri_big_font, f"{forecast_tomorrow.temp_min}C", label_width, second_row_height, label_width)
    PicoLabel(wri_big_font, f"{forecast_tomorrow.temp_max}C", label_width, third_row_height, label_width)
    display_image(93, icons_height, icons_size, icons_size, weather_code_to_icon[forecast_tomorrow.weather_code])
    
    PicoLabel(wri_big_font, f"{forecast_day_after_tomorrow.temp_min}C", label_width * 2, second_row_height, label_width)
    PicoLabel(wri_big_font, f"{forecast_day_after_tomorrow.temp_max}C", label_width * 2, third_row_height, label_width)
    display_image(176, icons_height, icons_size, icons_size, weather_code_to_icon[forecast_day_after_tomorrow.weather_code])
    
    ssd.vline(label_width, 0, ssd.height, 1)
    ssd.vline(label_width * 2, 0, ssd.height, 1)

    refresh(ssd)
    ssd.wait_until_ready()
    ssd.sleep()


def button_handler(pin):
    global last_button_press_time
    global requested_agenda_page
    current_time = time.ticks_ms()
    time_elapsed_ms = time.ticks_diff(current_time, last_button_press_time)
    if time_elapsed_ms < 250:
        return
    last_button_press_time = time.ticks_ms()
    requested_agenda_page = (current_agenda_page + 1) % len(agenda_pages)

    
def boot_sequence():
    print("booting up...")
    time.sleep(0.33)
    print("reading config files...")
    wifi_ssid, wifi_password = read_wifi_credentials()
    print("connecting to wifi network...")
    connect_to_wifi(wifi_ssid, wifi_password)
    set_current_time()
    
    button.irq(trigger=Pin.IRQ_RISING, handler=button_handler)


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
start_led_flashing()
success = update_agenda()
if success:
    display_agenda(current_agenda_page)
else:
    PicoLabel(wri_small_font, "Failed to fetch the agenda.", 4, 10)
    PicoLabel(wri_small_font, "Press the button to retry.", 4, 20)
    refresh(ssd)
    ssd.wait_until_ready()
    ssd.sleep()
# display_weather_info(open_meteo_uri)
stop_led_flashing()

def loop():
    global current_agenda_page
    time.sleep(1)
    if requested_agenda_page != current_agenda_page:
        current_agenda_page = requested_agenda_page
        display_agenda(current_agenda_page)

while True:
    loop()
