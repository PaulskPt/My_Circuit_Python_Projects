# SPDX-FileCopyrightText: 2022 DJDevon3 for Adafruit Industries
# SPDX-License-Identifier: MIT
"""DJDevon3 UM ESP32 Feather S3 Online Weatherstation"""
import gc
import time
import board
import feathers3
import displayio
import terminalio
from adafruit_display_text import label
from adafruit_bitmap_font import bitmap_font
import adafruit_imageload
import ssl
import wifi
import socketpool
import adafruit_requests
from adafruit_bme280 import basic as adafruit_bme280
from adafruit_hx8357 import HX8357

# 3.5" TFT Featherwing is 480x320
displayio.release_displays()
DISPLAY_WIDTH = 480
DISPLAY_HEIGHT = 320
sleep_time = 3600  # Time between weather updates

# Initialize TFT Display
spi = board.SPI()
tft_cs = board.IO1
tft_dc = board.IO3
display_bus = displayio.FourWire(spi,
                                 command=tft_dc,
                                 chip_select=tft_cs,
                                 baudrate=50000000,
                                 phase=0,
                                 polarity=0)
display = HX8357(display_bus, width=DISPLAY_WIDTH, height=DISPLAY_HEIGHT)

# Initialize BME280 Sensor
i2c = board.I2C()  # uses board.SCL and board.SDA
bme280 = adafruit_bme280.Adafruit_BME280_I2C(i2c)

Bat_S3 = feathers3.get_battery_voltage()
# print(Bat_S3)

try:
    from secrets import secrets
except ImportError:
    print("Secrets File Import Error")
    raise

if (sleep_time) < 60:
    sleep_time_conversion = "seconds"
    sleep_int = sleep_time
elif (sleep_time) >= 60 and (sleep_time) < 3600:
    sleep_int = sleep_time / 60
    sleep_time_conversion = "minutes"
elif (sleep_time) >= 3600:
    sleep_int = sleep_time / 60 / 60
    sleep_time_conversion = "hours"

# Quick Colors for Labels
text_black = 0x000000
text_blue = 0x0000FF
text_cyan = 0x00FFFF
text_gray = 0x8B8B8B
text_green = 0x00FF00
text_lightblue = 0x90C7FF
text_magenta = 0xFF00FF
text_orange = 0xFFA500
text_purple = 0x800080
text_red = 0xFF0000
text_white = 0xFFFFFF
text_yellow = 0xFFFF00

# Fonts are optional
medium_font = bitmap_font.load_font("/fonts/Arial-16.bdf")
huge_font = bitmap_font.load_font("/fonts/GoodTimesRg-Regular-121.bdf")

# Fill OpenWeather 2.5 API with token data
# OpenWeather free account & token are required
timezone = secrets['timezone']
tz_offset_seconds = int(secrets['timezone_offset'])

# OpenWeather 2.5 Free API
MAP_SOURCE = "https://tile.openweathermap.org/map"
MAP_SOURCE += "/precipitation_new"
MAP_SOURCE += "/9"
MAP_SOURCE += "/"+secrets['openweather_lat']
MAP_SOURCE += "/"+secrets['openweather_lon']
MAP_SOURCE += "/.png"
MAP_SOURCE += "&appid="+secrets['openweather_token']

DATA_SOURCE = "https://api.openweathermap.org/data/2.5/onecall?"
DATA_SOURCE += "lat="+secrets['openweather_lat']
DATA_SOURCE += "&lon="+secrets['openweather_lon']
DATA_SOURCE += "&timezone="+timezone
DATA_SOURCE += "&timezone_offset="+str(tz_offset_seconds)
DATA_SOURCE += "&exclude=hourly,daily"
DATA_SOURCE += "&appid="+secrets['openweather_token']
DATA_SOURCE += "&units=imperial"

def _format_datetime(datetime):
    return "{:02}/{:02}/{} {:02}:{:02}:{:02}".format(
        datetime.tm_mon,
        datetime.tm_mday,
        datetime.tm_year,
        datetime.tm_hour,
        datetime.tm_min,
        datetime.tm_sec,
    )

def _format_date(datetime):
    return "{:02}/{:02}/{:02}".format(
        datetime.tm_year,
        datetime.tm_mon,
        datetime.tm_mday,
    )

def _format_time(datetime):
    return "{:02}:{:02}".format(
        datetime.tm_hour,
        datetime.tm_min,
        # datetime.tm_sec,
    )

# Individual customizable position labels
# https://learn.adafruit.com/circuitpython-display-support-using-displayio/text
date_label = label.Label(medium_font)
# Anchor point bottom center of text
date_label.anchor_point = (0.0, 0.0)
# Display width divided in half for center of display (x,y)
date_label.anchored_position = (5, 5)
date_label.scale = 1
date_label.color = text_lightblue

time_label = label.Label(medium_font)
# Anchor point bottom center of text
time_label.anchor_point = (0.0, 0.0)
# Display width divided in half for center of display (x,y)
time_label.anchored_position = (5, 25)
time_label.scale = 2
time_label.color = text_lightblue

temp_label = label.Label(medium_font)
temp_label.anchor_point = (1.0, 1.0)
temp_label.anchored_position = (475, 145)
temp_label.scale = 2
temp_label.color = text_white

temp_data_label = label.Label(huge_font)
temp_data_label.anchor_point = (0.5, 1.0)
temp_data_label.anchored_position = (DISPLAY_WIDTH / 2, 200)
temp_data_label.scale = 1
temp_data_label.color = text_orange

temp_data_shadow = label.Label(huge_font)
temp_data_shadow.anchor_point = (0.5, 1.0)
temp_data_shadow.anchored_position = (DISPLAY_WIDTH / 2 + 2, 200 + 2)
temp_data_shadow.scale = 1
temp_data_shadow.color = text_black

owm_temp_data_label = label.Label(medium_font)
owm_temp_data_label.anchor_point = (0.5, 1.0)
owm_temp_data_label.anchored_position = (DISPLAY_WIDTH / 2, 100)
owm_temp_data_label.scale = 2
owm_temp_data_label.color = text_lightblue

owm_temp_data_shadow = label.Label(medium_font)
owm_temp_data_shadow.anchor_point = (0.5, 1.0)
owm_temp_data_shadow.anchored_position = (DISPLAY_WIDTH / 2 + 2, 100 + 2)
owm_temp_data_shadow.scale = 2
owm_temp_data_shadow.color = text_black

humidity_label = label.Label(medium_font)
humidity_label.anchor_point = (0.0, 1.0)
humidity_label.anchored_position = (5, DISPLAY_HEIGHT - 23)
humidity_label.scale = 1
humidity_label.color = text_gray

humidity_data_label = label.Label(medium_font)
humidity_data_label.anchor_point = (0.0, 1.0)
humidity_data_label.anchored_position = (5, DISPLAY_HEIGHT)
humidity_data_label.scale = 1
humidity_data_label.color = text_orange

owm_humidity_data_label = label.Label(medium_font)
owm_humidity_data_label.anchor_point = (0.0, 1.0)
owm_humidity_data_label.anchored_position = (5, DISPLAY_HEIGHT - 55)
owm_humidity_data_label.scale = 1
owm_humidity_data_label.color = text_lightblue

barometric_label = label.Label(medium_font)
barometric_label.anchor_point = (1.0, 1.0)
barometric_label.anchored_position = (470, DISPLAY_HEIGHT - 27)
barometric_label.scale = 1
barometric_label.color = text_gray

barometric_data_label = label.Label(medium_font)
barometric_data_label.anchor_point = (1.0, 1.0)
barometric_data_label.anchored_position = (470, DISPLAY_HEIGHT)
barometric_data_label.scale = 1
barometric_data_label.color = text_orange

owm_barometric_data_label = label.Label(medium_font)
owm_barometric_data_label.anchor_point = (1.0, 1.0)
owm_barometric_data_label.anchored_position = (470, DISPLAY_HEIGHT - 55)
owm_barometric_data_label.scale = 1
owm_barometric_data_label.color = text_lightblue

vbat_label = label.Label(medium_font)
vbat_label.anchor_point = (1.0, 1.0)
vbat_label.anchored_position = (DISPLAY_WIDTH-15, 20)
vbat_label.scale = (1)

plugbmp_label = label.Label(terminalio.FONT)
plugbmp_label.anchor_point = (1.0, 1.0)
plugbmp_label.scale = (1)

greenbmp_label = label.Label(terminalio.FONT)
greenbmp_label.anchor_point = (1.0, 1.0)
greenbmp_label.scale = (1)

bluebmp_label = label.Label(terminalio.FONT)
bluebmp_label.anchor_point = (1.0, 1.0)
bluebmp_label.scale = (1)

yellowbmp_label = label.Label(terminalio.FONT)
yellowbmp_label.anchor_point = (1.0, 1.0)
yellowbmp_label.scale = (1)

orangebmp_label = label.Label(terminalio.FONT)
orangebmp_label.anchor_point = (1.0, 1.0)
orangebmp_label.scale = (1)

redbmp_label = label.Label(terminalio.FONT)
redbmp_label.anchor_point = (1.0, 1.0)
redbmp_label.scale = (1)

# Load Bitmap to tile grid first (Background layer)
DiskBMP = displayio.OnDiskBitmap("/images/Astral_Fruit_8bit.bmp")
tile_grid = displayio.TileGrid(
    DiskBMP,
    pixel_shader=DiskBMP.pixel_shader,
    width=1,
    height=1,
    tile_width=DISPLAY_WIDTH,
    tile_height=DISPLAY_HEIGHT)

# Load battery voltage icons (from 1 sprite sheet image)
sprite_sheet, palette = adafruit_imageload.load("/icons/vbat_spritesheet.bmp",
                                                bitmap=displayio.Bitmap,
                                                palette=displayio.Palette)
sprite = displayio.TileGrid(sprite_sheet, pixel_shader=palette,
                            width=1,
                            height=1,
                            tile_width=11,
                            tile_height=20)
sprite_group = displayio.Group(scale=1)
sprite_group.append(sprite)
sprite_group.x = 470
sprite_group.y = 0

# Create subgroups
text_group = displayio.Group()
text_group.append(tile_grid)
temp_group = displayio.Group()
main_group = displayio.Group()

# Add subgroups to main display group
main_group.append(text_group)
main_group.append(temp_group)
main_group.append(sprite_group)

# Label Display Group (foreground layer)
text_group.append(date_label)
text_group.append(time_label)
temp_group.append(temp_label)
temp_group.append(temp_data_shadow)
temp_group.append(temp_data_label)
temp_group.append(owm_temp_data_shadow)
temp_group.append(owm_temp_data_label)
text_group.append(humidity_label)
text_group.append(humidity_data_label)
text_group.append(owm_humidity_data_label)
text_group.append(barometric_label)
text_group.append(barometric_data_label)
text_group.append(owm_barometric_data_label)
text_group.append(vbat_label)
text_group.append(plugbmp_label)
text_group.append(greenbmp_label)
text_group.append(bluebmp_label)
text_group.append(yellowbmp_label)
text_group.append(orangebmp_label)
text_group.append(redbmp_label)
display.show(main_group)

# Connect to WiFi
print("\n===============================")
print("Connecting to WiFi...")
pool = socketpool.SocketPool(wifi.radio)
requests = adafruit_requests.Session(pool, ssl.create_default_context())
# Retry loop if SSID not connecting
while not wifi.radio.ipv4_address:
    try:
        wifi.radio.connect(secrets['ssid'], secrets['password'])
    except (ConnectionError) as e:
        print("Connection Error:", e)
        print("Retrying in 10 seconds")
    time.sleep(10)
print("Connected!\n")

vbat_label.text = "{:.2f}".format(Bat_S3)
# source_index = 0

while True:
    gc.collect()

    # Changes battery voltage color depending on charge level
    if vbat_label.text >= "4.23":
        vbat_label.color = text_white
        sprite[0] = 3
    elif vbat_label.text >= "4.10" and vbat_label.text <= "4.22":
        vbat_label.color = text_green
        sprite[0] = 1
    elif vbat_label.text >= "4.00" and vbat_label.text <= "4.09":
        vbat_label.color = text_lightblue
        sprite[0]
    elif vbat_label.text >= "3.90" and vbat_label.text <= "3.99":
        vbat_label.color = text_yellow
        sprite[0] = 5
    elif vbat_label.text >= "3.80" and vbat_label.text <= "3.89":
        vbat_label.color = text_orange
        sprite[0] = 2
    elif vbat_label.text <= "3.79":
        vbat_label.color = text_red
        sprite[0] = 4
    else:
        vbat_label.color = text_white

    # tile_grid[0] = source_index % 21
    # source_index += 1

    vbat_label.text

    temp_label.text = "°F"
    temperature = "{:.1f}".format(bme280.temperature * 1.8 + 32)
    temp_data_shadow.text = temperature
    temp_data_label.text = temperature
    humidity_label.text = "Humidity"
    humidity_data_label.text = "{:.1f} %".format(bme280.relative_humidity)
    barometric_label.text = "Pressure"
    barometric_data_label.text = "{:.1f}".format(bme280.pressure)

    try:
        print("Attempting to GET Weather!")
        # Uncomment line below to print API URL with all data filled in
        #print("Full API GET URL: ", DATA_SOURCE)
        print("\n===============================")
        response = requests.get(DATA_SOURCE).json()

        # uncomment the 2 lines below to see full json response
        # dump_object = json.dumps(response)
        # print("JSON Dump: ", dump_object)

        get_timestamp = int(response['current']['dt'] + tz_offset_seconds)
        current_unix_time = time.localtime(get_timestamp)
        current_struct_time = time.struct_time(current_unix_time)
        current_date = "{}".format(_format_date(current_struct_time))
        current_time = "{}".format(_format_time(current_struct_time))

        sunrise = int(response['current']['sunrise'] + tz_offset_seconds)
        sunrise_unix_time = time.localtime(sunrise)
        sunrise_struct_time = time.struct_time(sunrise_unix_time)
        sunrise_time = "{}".format(_format_time(sunrise_struct_time))

        sunset = int(response['current']['sunset'] + tz_offset_seconds)
        sunset_unix_time = time.localtime(sunset)
        sunset_struct_time = time.struct_time(sunset_unix_time)
        sunset_time = "{}".format(_format_time(sunset_struct_time))

        owm_temp = response['current']['temp']
        owm_pressure = response['current']['pressure']
        owm_humidity = response['current']['humidity']
        weather_type = response['current']['weather'][0]['main']

        print("Timestamp:", current_date + " " + current_time)
        print("Sunrise:", sunrise_time)
        print("Sunset:", sunset_time)
        print("Temp:", owm_temp)
        print("Pressure:", owm_pressure)
        print("Humidity:", owm_humidity)
        print("Weather Type:", weather_type)

        print("\nNext Update in %s %s" % (int(sleep_int), sleep_time_conversion))
        print("===============================")

        gc.collect()
        date_label.text = current_date
        time_label.text = current_time
        owm_temp_data_shadow.text = "{:.1f}".format(owm_temp)
        owm_temp_data_label.text = "{:.1f}".format(owm_temp)
        owm_humidity_data_label.text = "{:.1f} %".format(owm_humidity)
        owm_barometric_data_label.text = "{:.1f}".format(owm_pressure)

    except (ValueError, RuntimeError) as e:
        print("Failed to get data, retrying\n", e)
        wifi.reset()
        time.sleep(60)
        continue
    response = None
    time.sleep(sleep_time)
