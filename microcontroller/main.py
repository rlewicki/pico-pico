import time
from machine import Pin
from machine import Timer
import machine
import network
import ntptime
import urequests
import json
import forecast_images

from lib.color_setup import ssd
from lib.gui.core.writer import Writer
from lib.gui.core.nanogui import refresh
from lib.gui.widgets.label import Label
import lib.gui.fonts.arial10 as arial10
import lib.gui.fonts.courier20 as courier20

from lib.extended_gui import PicoLabel

AGENDA_SCREEN = 2
AGENDA_FAILED = 3
AGENDA_UPDATING = 4
WEATHER_SCREEN = 1
WEATHER_UPDATING = 5
WEATHER_FAILED = 8
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
        self.start_day = -1
        self.start_month = -1
        self.start_year = -1
        self.start_time = None
        self.end_day = -1
        self.end_month = -1
        self.end_year = -1
        self.is_whole_day_event = False
        self.description_lines = []


class AgendaPage:
    def __init__(self) -> None:
        self.agendaEntries = []


class Globals:
    def __init__(self) -> None:
        self.app_state = INITIALIZING
        self.caldav_username = ""
        self.caldav_password = ""
        self.backend_name = ""
        self.backend_port = ""
        self.backend_full_uri = ""
        self.open_meteo_uri = ""
        self.agenda: list[AgendaEntry] = []
        self.agenda_pages: list[AgendaPage] = []
        self.current_agenda_page = 0
        self.weather_info: list[WeatherEntry] = []
        self.last_button_press_time = time.ticks_ms()
        self.last_button_release_time = time.ticks_ms()
        self.white_led_value = 0
        self.led_counter = 0
        self.led_timer = Timer()
        self.wri_small_font = None
        self.wri_big_font = None
        self.button_single_press = False
        self.button_double_press = False
        self.button_long_press = False
        self.button_single_press_timer = Timer()
        self.button_long_press_timer = Timer()
        self.was_long_press_triggered = False
        self.was_double_press_triggered = False
        self.wlan = network.WLAN(network.STA_IF)
        self.wifi_ssid = ""
        self.wifi_password = ""


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

g = Globals()
button = Pin(3, Pin.IN, Pin.PULL_DOWN)
white_led = Pin(2, Pin.OUT)
white_led.value(0)


def toggle_led(source):
    if g.white_led_value == 1:
        g.white_led_value = 0
    else:
        g.white_led_value = 1
    white_led.value(g.white_led_value)


def start_led_flashing():
    if g.led_counter == 0:
        g.led_timer.init(period=500, mode=Timer.PERIODIC, callback=toggle_led)
    g.led_counter += 1


def stop_led_flashing():
    g.led_counter -= 1
    if g.led_counter == 0:
        g.led_timer.deinit()
        g.white_led_value = 0
        white_led.value(0)


def disconnect_from_wifi():
    print("disconnecting from wifi...")
    g.wlan.disconnect()
    g.wlan.active(False)
    network.WLAN(network.STA_IF).deinit()


def connect_to_wifi():
    print("connecting to wifi...")
    g.wlan.active(True)
    g.wlan.config(pm=0xa11140)
    g.wlan.connect(g.wifi_ssid, g.wifi_password)
    while not g.wlan.isconnected():
        print("waiting for Internet connection...")
        time.sleep_ms(1000)
    print(g.wlan.ifconfig())


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
    g.wifi_ssid = data[0]
    g.wifi_password = data[1]


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
    print("HTTP request to ", url)
    try:
        response = urequests.get(url)
        print("Response: ", response)
        return True, response.text
    except Exception as e:
        print("HTTP request failed:", type(e), e.args, e)
        return False, ""


def get_quote_of_the_day():
    request_uri = g.backend_full_uri + "/quote"
    succeeded, response = http_get_request(request_uri)
    if succeeded:
        quote_info = json.loads(response)
        return quote_info["author"], quote_info["quote"]
    else:
        return "", ""


def justify_text(text: str, font, max_width) -> list[str]:
    result: list[str] = []
    white_space_width = font.stringlen(" ")
    words = text.split(" ")
    current_width = 0
    current_text_line = ""
    for word in words:
        word_width = font.stringlen(word)
        if current_width + word_width > max_width:
            result.append(current_text_line)
            current_width = 0
            current_text_line = ""
        current_text_line += word
        current_width += word_width
        if current_width + white_space_width > max_width:
            current_width = 0
            current_text_line = ""
        else:
            current_text_line += " "
    return result


def get_agenda_data(caldav_url) -> list[AgendaEntry]:
    agenda: list[AgendaEntry] = []
    succeeded, response = http_get_request(caldav_url)
    if not succeeded:
        print("failed to fetch agenda from the server")
        return agenda
    events = json.loads(response)
    for event in events:
        new_entry = AgendaEntry()
        start_date = event['start_date'].split()
        start_date_components = start_date[0].split('/')
        new_entry.start_day = int(start_date_components[1])
        new_entry.start_month = int(start_date_components[0])
        new_entry.start_year = int(start_date_components[2])
        new_entry.is_whole_day_event = bool(event['whole_day_event'])
        if not new_entry.is_whole_day_event:
            new_entry.start_time = start_date[1]
        end_date = event['end_date'].split()
        end_date_components = end_date[0].split('/')
        new_entry.end_day = int(end_date_components[1])
        new_entry.end_month = int(end_date_components[0])
        new_entry.end_year = int(end_date_components[2])
        summary = event['summary'].split(" ")
        new_entry.description_lines = justify_text(summary, g.wri_big_font, ssd.width)
        agenda.append(new_entry)
    return agenda


def get_current_date():
    current_time = time.localtime()
    current_time = "{}:{}:{}".format(
        current_time[3] + 1, current_time[4], current_time[5])
    return current_time


def get_open_meteo_uri():
    f = open('open-meteo.txt', 'r')
    uri = f.read()
    return uri


def update_agenda():
    # Obviously passing username and password as URL parameters is not safe but since entire network traffic is happening
    # within a local network I'm not too worried about this
    g.app_state = AGENDA_UPDATING
    g.current_agenda_page = 0
    caldav_request_uri = g.backend_full_uri + \
        "/agenda?username=" + g.caldav_username + \
        "&password=" + g.caldav_password + "&days=60"
    print("fetching agenda from calendar...")
    try:
        g.agenda = get_agenda_data(caldav_request_uri)
        g.agenda.sort(key=lambda x: (
            x.start_year, x.start_month, x.start_day, x.start_time))
        update_agenda_paging()
        display_agenda(g.current_agenda_page)
        g.app_state = AGENDA_SCREEN
    except Exception as e:
        print("failed to fetch new agenda:", type(e), e.args, e)
        refresh(ssd, True)
        ssd.wait_until_ready()
        PicoLabel(g.wri_small_font, "Failed to fetch the agenda.", 4, 10)
        PicoLabel(g.wri_small_font, "Press the button to retry.", 4, 20)
        refresh(ssd)
        ssd.wait_until_ready()
        g.app_state = AGENDA_FAILED


def update_agenda_paging():
    g.agenda_pages = []
    row = 6
    new_agenda_page = AgendaPage()
    print("paging agenda events...")
    for entry in g.agenda:
        row += g.wri_small_font.height
        row += (len(entry.description_lines) * g.wri_big_font.height)
        if row >= ssd.height:
            g.agenda_pages.append(new_agenda_page)
            new_agenda_page = AgendaPage()
            row = 6
        new_agenda_page.agendaEntries.append(entry)
    g.agenda_pages.append(new_agenda_page)
    print(f"Num of agenda pages created: {len(g.agenda_pages)}")


def display_agenda(pageIndex):
    if pageIndex < 0 or pageIndex >= len(g.agenda_pages):
        print(f"invalid page index ({pageIndex})")
        return

    refresh(ssd, True)
    ssd.wait_until_ready()
    row = 6
    agenda_page = g.agenda_pages[pageIndex]
    print(f"displaying {len(agenda_page.agendaEntries)} agenda items...")
    for entry in agenda_page.agendaEntries:
        Label(g.wri_small_font,
              row,
              0,
              f"{entry.start_day} {month_names[entry.start_month - 1]} {entry.start_year} {entry.start_time}")
        row += arial10.height()
        for desc_line in entry.description_lines:
            Label(g.wri_big_font, row, 0, desc_line)
            row += courier20.height()
    page_label = f"{g.current_agenda_page + 1} / {len(g.agenda_pages)}"
    page_label_width = g.wri_small_font.stringlen(page_label)
    Label(g.wri_small_font, 6, 250 - page_label_width, page_label)
    refresh(ssd)
    ssd.wait_until_ready()


def fetch_weather_info(uri) -> list[WeatherEntry]:
    Label(g.wri_big_font, int(ssd.height / 2 -
          g.wri_big_font.height / 2), 8, "updating forecast")
    refresh(ssd, True)
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


def update_weather():
    g.app_state = WEATHER_UPDATING

    # We should not only check if the data is empty, but also the last time we
    # updated. Otherwise we will only ever update the weather on demand rather
    # than periodically without any user input.
    if len(g.weather_info) <= 0:
        try:
            g.weather_info = fetch_weather_info(g.open_meteo_uri)
        except Exception as e:
            print("failed to fetch weather update:", e)
            refresh(ssd, True)
            ssd.wait_until_ready()
            PicoLabel(g.wri_small_font,
                      "Failed to fetch the weather update.", 4, 10)
            PicoLabel(g.wri_small_font, "Press the button to retry.", 4, 20)
            refresh(ssd)
            ssd.wait_until_ready()
            g.app_state = WEATHER_FAILED
            stop_led_flashing()
            return

    forecast_now = g.weather_info[0]
    forecast_tomorrow = g.weather_info[1]
    forecast_day_after_tomorrow = g.weather_info[2]
    refresh(ssd, True)
    ssd.wait_until_ready()

    label_width = ssd.width // 3
    first_row_height = 8
    second_row_height = 25
    third_row_height = 45
    icons_height = 60
    icons_size = 64

    PicoLabel(g.wri_small_font, "Now", 0, first_row_height, label_width)
    # Replace Tomorrow and DaT with actual names of the days
    PicoLabel(g.wri_small_font, "Tomorrow", label_width,
              first_row_height, label_width)
    PicoLabel(g.wri_small_font, "DaT", label_width *
              2, first_row_height, label_width)

    PicoLabel(g.wri_big_font, f"{forecast_now.temp_min}C",
              0, second_row_height, label_width)
    PicoLabel(g.wri_big_font,
              f"{int(forecast_now.precipitation)}%",
              0,
              third_row_height,
              label_width)
    display_image(9, icons_height, icons_size, icons_size,
                  weather_code_to_icon[forecast_now.weather_code])

    PicoLabel(g.wri_big_font, f"{forecast_tomorrow.temp_min}C",
              label_width, second_row_height, label_width)
    PicoLabel(g.wri_big_font, f"{forecast_tomorrow.temp_max}C",
              label_width, third_row_height, label_width)
    display_image(93, icons_height, icons_size, icons_size,
                  weather_code_to_icon[forecast_tomorrow.weather_code])

    PicoLabel(g.wri_big_font, f"{forecast_day_after_tomorrow.temp_min}C",
              label_width * 2, second_row_height, label_width)
    PicoLabel(g.wri_big_font, f"{forecast_day_after_tomorrow.temp_max}C",
              label_width * 2, third_row_height, label_width)
    display_image(176, icons_height, icons_size, icons_size,
                  weather_code_to_icon[forecast_day_after_tomorrow.weather_code])

    ssd.vline(label_width, 0, ssd.height, 1)
    ssd.vline(label_width * 2, 0, ssd.height, 1)

    refresh(ssd)
    ssd.wait_until_ready()
    g.app_state = WEATHER_SCREEN


def button_single_press_callback(source):
    print("single button press detected")
    g.button_single_press = True


def button_long_press_callback(source):
    print("long button press detected")
    g.was_long_press_triggered = True
    g.button_long_press = True


def button_state_changed(pin):
    LONG_PRESS_TIME = 3000
    DOUBLE_PRESS_TIME = 200
    DEBOUNCE_TIME = 125
    current_time = time.ticks_ms()
    if pin.value() == 0:
        time_elapsed_since_release_ms = time.ticks_diff(
            current_time, g.last_button_release_time)
        if time_elapsed_since_release_ms < DEBOUNCE_TIME:
            return
        time_elapsed_since_last_press_ms = time.ticks_diff(
            current_time, g.last_button_press_time)
        print("registering button release. time_elapsed_since_last_press_ms =",
              time_elapsed_since_last_press_ms)
        g.button_long_press_timer.deinit()
        g.last_button_release_time = current_time
        if g.was_long_press_triggered or g.was_double_press_triggered:
            g.was_long_press_triggered = False
            g.was_double_press_triggered = False
        else:
            g.button_single_press_timer.init(
                period=DOUBLE_PRESS_TIME, mode=Timer.ONE_SHOT, callback=button_single_press_callback)
    else:
        time_elapsed_since_press_ms = time.ticks_diff(
            current_time, g.last_button_press_time)
        if time_elapsed_since_press_ms < DEBOUNCE_TIME:
            return
        g.last_button_press_time = current_time
        time_elapsed_since_release_ms = time.ticks_diff(
            current_time, g.last_button_release_time)
        print("registering button press. time_since_last_release_ms = ",
              time_elapsed_since_release_ms)
        if time_elapsed_since_release_ms < DOUBLE_PRESS_TIME:
            print("double press detected")
            g.button_single_press_timer.deinit()
            g.was_double_press_triggered = True
            g.button_double_press = True
        else:
            g.button_long_press_timer.init(
                period=LONG_PRESS_TIME, mode=Timer.ONE_SHOT, callback=button_long_press_callback)


def boot_sequence():
    print("booting up...")
    time.sleep_ms(330)
    print("reading config files...")
    read_wifi_credentials()
    print("connecting to wifi network...")
    connect_to_wifi()
    print("setting current time...")
    set_current_time()

    print("initializing button handler...")
    button.irq(trigger=Pin.IRQ_RISING | Pin.IRQ_FALLING,
               handler=button_state_changed)

    print("reading open meteo API uri...")
    g.open_meteo_uri = get_open_meteo_uri()
    print(f"open meteo uri: {g.open_meteo_uri}")

    print("reading caldav credentials...")
    g.caldav_username, g.caldav_password, g.backend_name, g.backend_port = read_caldav_credentials()
    g.backend_full_uri = "http://" + g.backend_name + ":" + g.backend_port

    print("initializing display...")
    g.wri_small_font = Writer(ssd, arial10, verbose=False)
    g.wri_small_font.set_clip(True, True, False)
    g.wri_big_font = Writer(ssd, courier20, verbose=False)
    g.wri_big_font.set_clip(True, True, False)

    ssd.init()
    refresh(ssd, True)
    ssd.wait_until_ready()


def any_button_pressed():
    return g.button_single_press or g.button_double_press or g.button_long_press


def loop():
    if g.wlan.isconnected():
        disconnect_from_wifi()

    # This is small time buffor to make sure everything that was called moments before calling
    # sleep is being flushed and do not cause a wake up. One example is printing a message which
    # gets flushed a bit later and is causing a wake up because of UART communication.
    print("going into lightsleep...")
    time.sleep_ms(1000)
    machine.lightsleep(1000 * 60 * 60)
    print("waking up...")

    # Give the device a bit of time after waking up to update its state. This allows to avoid the race condition
    # between button release triggering the wake up, and updating the program's state.
    time.sleep_ms(500)

    if not any_button_pressed():
        print("no input registered, skipping update loop...")
        return

    start_led_flashing()
    connect_to_wifi()
    ssd.init()
    print("running update loop...")
    if g.button_long_press:
        refresh(ssd, True)
        ssd.wait_until_ready()
        author, quote = get_quote_of_the_day()
        justified_quote = justify_text(quote, g.wri_small_font, ssd.width)
        carriage_height = 6
        for line in justified_quote:
            Label(g.wri_small_font, carriage_height, 0, line)
            carriage_height += 10
        refresh(ssd)
        ssd.wait_until_ready()
    elif g.app_state == AGENDA_FAILED:
        if g.button_single_press:
            update_agenda()
        else:
            update_weather()
    elif g.app_state == AGENDA_SCREEN:
        if g.button_single_press:
            g.current_agenda_page = (
                g.current_agenda_page + 1) % len(g.agenda_pages)
            display_agenda(g.current_agenda_page)
        elif g.button_double_press:
            update_weather()
    elif g.app_state == WEATHER_FAILED or g.app_state == WEATHER_SCREEN:
        if g.button_single_press:
            update_weather()
        elif g.button_double_press:
            update_agenda()
    else:
        print("button press not handled in current state")
    g.button_single_press = False
    g.button_long_press = False
    g.button_double_press = False
    stop_led_flashing()


start_led_flashing()
boot_sequence()
update_agenda()
stop_led_flashing()
while True:
    loop()
