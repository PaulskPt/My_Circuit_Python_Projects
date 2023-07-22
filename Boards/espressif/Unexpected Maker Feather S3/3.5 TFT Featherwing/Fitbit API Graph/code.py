# SPDX-FileCopyrightText: 2023 DJDevon3
# SPDX-License-Identifier: MIT
# Coded for Circuit Python 8.2
# Unexpected Maker FeatherS3 with 3.5" TFT Featherwing

import os
import board
import time
import array
import displayio
import digitalio
import terminalio
import ssl
import wifi
import socketpool
import adafruit_imageload
import adafruit_sdcard
from adafruit_bitmapsaver import save_pixels
import storage
from adafruit_hx8357 import HX8357
from adafruit_display_text import label
from adafruit_displayio_layout.widgets.cartesian import Cartesian
import adafruit_requests

displayio.release_displays()

# Initialize WiFi Pool (There can be only 1 pool & top of script)
pool = socketpool.SocketPool(wifi.radio)

# 4.0" ST7796S Aliexpress Display
DISPLAY_WIDTH = 480
DISPLAY_HEIGHT = 320

# Initialize TFT Display
spi = board.SPI()
tft_cs = board.D9
tft_dc = board.D10
display_bus = displayio.FourWire(spi, command=tft_dc, chip_select=tft_cs)
display = HX8357(display_bus, width=DISPLAY_WIDTH, height=DISPLAY_HEIGHT)
display.auto_refresh = False

# --- Fitbit Developer Account & oAuth App Required: ---
# Step 1: Create a personal app here: https://dev.fitbit.com
# Step 2: Use their Tutorial to get the Token and first Refresh Token
# Fitbit's Tutorial Step 4 is as far as you need to go.
# https://dev.fitbit.com/build/reference/web-api/troubleshooting-guide/oauth2-tutorial/

# Ensure these are in settings.toml
# Fitbit_ClientID = "YourAppClientID"
# Fitbit_Token = "Long 256 character string (SHA-256)"
# Fitbit_First_Refresh_Token = "40 character string"
# Fitbit_UserID = "UserID authorizing the ClientID"

Fitbit_ClientID = os.getenv("Fitbit_ClientID")
Fitbit_Token = os.getenv("Fitbit_Token")
Fitbit_First_Refresh_Token = os.getenv("Fitbit_First_Refresh_Token")
Fitbit_UserID = os.getenv("Fitbit_UserID")

wifi_ssid = os.getenv("CIRCUITPY_WIFI_SSID")
wifi_pw = os.getenv("CIRCUITPY_WIFI_PASSWORD")

# Time between API refreshes
# 300 = 5 mins, 900 = 15 mins, 1800 = 30 mins, 3600 = 1 hour
sleep_time = 900

# Converts seconds in minutes/hours/days
def time_calc(input_time):
    if input_time < 60:
        sleep_int = input_time
        time_output = f"{sleep_int:.0f} seconds"
    elif 60 <= input_time < 3600:
        sleep_int = input_time / 60
        time_output = f"{sleep_int:.0f} minutes"
    elif 3600 <= input_time < 86400:
        sleep_int = input_time / 60 / 60
        time_output = f"{sleep_int:.0f} hours"
    else:
        sleep_int = input_time / 60 / 60 / 24
        time_output = f"{sleep_int:.1f} days"
    return time_output

# Quick Colors for Labels
TEXT_BLACK = 0x000000
TEXT_BLUE = 0x0000FF
TEXT_CYAN = 0x00FFFF
TEXT_GRAY = 0x8B8B8B
TEXT_GREEN = 0x00FF00
TEXT_LIGHTBLUE = 0x90C7FF
TEXT_MAGENTA = 0xFF00FF
TEXT_ORANGE = 0xFFA500
TEXT_PINK = 0XFFC0CB
TEXT_PURPLE = 0x800080
TEXT_RED = 0xFF0000
TEXT_WHITE = 0xFFFFFF
TEXT_YELLOW = 0xFFFF00

def bar_color(heart_rate):
    if heart_rate < 60:
        heart_rate_color = TEXT_PURPLE
    elif 60 <= heart_rate < 75:
        heart_rate_color = TEXT_BLUE
    elif 75 <= heart_rate < 85:
        heart_rate_color = TEXT_LIGHTBLUE
    elif 85 <= heart_rate < 100:
        heart_rate_color = TEXT_YELLOW
    elif 100 <= heart_rate < 110:
        heart_rate_color = TEXT_ORANGE
    elif 110 <= heart_rate < 120:
        heart_rate_color = TEXT_ORANGE
    else:
        heart_rate_color = TEXT_RED
    return heart_rate_color

hello_label = label.Label(terminalio.FONT)
hello_label.anchor_point = (0.5, 0.0)
hello_label.anchored_position = (DISPLAY_WIDTH/2, 5)
hello_label.scale = (1)
hello_label.color = TEXT_WHITE

date_label = label.Label(terminalio.FONT)
date_label.anchor_point = (0.0, 0.0)
date_label.anchored_position = (5, 5)
date_label.scale = (2)
date_label.color = TEXT_WHITE

time_label = label.Label(terminalio.FONT)
time_label.anchor_point = (0.0, 0.0)
time_label.anchored_position = (5, 30)
time_label.scale = (2)
time_label.color = TEXT_WHITE

pulses_today_label = label.Label(terminalio.FONT)
pulses_today_label.anchor_point = (0.5, 0.0)
pulses_today_label.anchored_position = (DISPLAY_WIDTH/2, 150)
pulses_today_label.scale = (3)
pulses_today_label.color = TEXT_WHITE

pulse_label = label.Label(terminalio.FONT)
pulse_label.anchor_point = (0.5, 0.0)
pulse_label.anchored_position = (344, 200)
pulse_label.scale = (2)
pulse_label.color = TEXT_PINK

# Create subgroups (layers)
text_group = displayio.Group()
plot_group = displayio.Group()
main_group = displayio.Group()

# Add subgroups to main group
main_group.append(plot_group)
main_group.append(text_group)

# Append labels to subgroups (sublayers)
text_group.append(hello_label)
text_group.append(date_label)
text_group.append(pulses_today_label)
text_group.append(time_label)
text_group.append(pulse_label)

# Combine and Show
display.show(main_group)

# First we use Client ID & Client Token to create a token with POST
# No user interaction is required for this type of scope (implicit grant flow)
fitbit_oauth_header = {"Content-Type": "application/x-www-form-urlencoded"}
fitbit_oauth_token = "https://api.fitbit.com/oauth2/token"

# Connect to Wi-Fi
print("\n===============================")
print("Connecting to WiFi...")
requests = adafruit_requests.Session(pool, ssl.create_default_context())
while not wifi.radio.ipv4_address:
    try:
        wifi.radio.connect(wifi_ssid, wifi_pw)
    except ConnectionError as e:
        print("Connection Error:", e)
        print("Retrying in 10 seconds")
    time.sleep(10)
print("Connected!\n")

Refresh_Token = Fitbit_First_Refresh_Token
add = 1
while True:
    hello_label.text = "Circuit Python Fitbit API"
    try:
        # STREAMER WARNING: private data will be viewable while True
        debug = False  # Set to True for full debug view

        print("\n-----Token Refresh POST Attempt -------")
        fitbit_oauth_refresh_token = (
            "&grant_type=refresh_token"
            + "&client_id="
            + str(Fitbit_ClientID)
            + "&refresh_token="
            + str(Refresh_Token)
        )

        # ----------------------------- POST FOR REFRESH TOKEN -----------------------
        if debug:
            print(f"FULL REFRESH TOKEN POST:{fitbit_oauth_token}{fitbit_oauth_refresh_token}")
            print(f"Current Refresh Token: {Refresh_Token}")
        # TOKEN REFRESH POST
        fitbit_oauth_refresh_POST = requests.post(
            url=fitbit_oauth_token,
            data=fitbit_oauth_refresh_token,
            headers=fitbit_oauth_header
        )
        try:
            fitbit_refresh_oauth_json = fitbit_oauth_refresh_POST.json()

            fitbit_new_token = fitbit_refresh_oauth_json["access_token"]
            if debug:
                print("Access Token: ", fitbit_new_token)
            fitbit_access_token = fitbit_new_token  # NEW FULL TOKEN

            # Overwrites Initial/Old Refresh Token with Next/New Refresh Token
            fitbit_new_refesh_token = fitbit_refresh_oauth_json["refresh_token"]
            Refresh_Token = fitbit_new_refesh_token

            fitbit_token_expiration = fitbit_refresh_oauth_json["expires_in"]
            fitbit_scope = fitbit_refresh_oauth_json["scope"]
            fitbit_token_type = fitbit_refresh_oauth_json["token_type"]
            fitbit_user_id = fitbit_refresh_oauth_json["user_id"]
            print("Next Refresh Token: ", Refresh_Token)
            if debug:
                print("Token Expires in: ", time_calc(fitbit_token_expiration))
                print("Scope: ", fitbit_scope)
                print("Token Type: ", fitbit_token_type)
                print("UserID: ", fitbit_user_id)

        except (KeyError) as e:
            print("Key Error:", e)
            print("Expired token, invalid permission, or (key:value) pair error.")
            time.sleep(300)
            continue

        # ----------------------------- GET DATA -------------------------------------
        # Refresh token is refreshed every time script runs :)
        # Fitbit tokens expire every 8 hours!
        # Now that we have POST refresh token we can do a GET for data
        # ----------------------------------------------------------------------------
        detail_level = "1min"  # Supported: 1sec | 1min | 5min | 15min
        requested_date = "today" # Date format yyyy-MM-dd or today
        fitbit_header = {
            "Authorization": "Bearer " + fitbit_access_token + "",
            "Client-Id": "" + Fitbit_ClientID + "",
        }
        # Heart Intraday Scope
        FITBIT_SOURCE = (
            "https://api.fitbit.com/1/user/"
            + Fitbit_UserID
            + "/activities/heart/date/today"
            + "/1d/"
            + detail_level
            + ".json"
        )

        print("\nAttempting to GET FITBIT Stats!")
        print("===============================")
        fitbit_get_response = requests.get(url=FITBIT_SOURCE, headers=fitbit_header)
        try:
            fitbit_json = fitbit_get_response.json()
        except ConnectionError as e:
            print("Connection Error:", e)
            print("Retrying in 10 seconds")

        if debug:
            print(f"Full API GET URL: {FITBIT_SOURCE}")
            print(f"Header: {fitbit_header}")
            # print(f"JSON Full Response: {fitbit_json}")
            # print(f"Intraday Full Response: {fitbit_json["activities-heart-intraday"]["dataset"]}")

        try:
            # Fitbit's sync to mobile device & server every 15 minutes in chunks.
            # Pointless to poll their API faster than 15 minute intervals.
            activities_heart_value = fitbit_json["activities-heart-intraday"]["dataset"]
            response_length = len(activities_heart_value)
            if response_length >= 5:
                activities_timestamp = fitbit_json["activities-heart"][0]["dateTime"]
                print(f"Fitbit Date: {activities_timestamp}")
                activities_latest_heart_time = fitbit_json["activities-heart-intraday"]["dataset"][response_length-1]["time"]
                print(f"Fitbit Time: {activities_latest_heart_time[0:-3]}")
                print(f"Today's Logged Pulses : {response_length}")

                # Each 1min heart rate is a 60 second average
                activities_latest_heart_value0 = fitbit_json["activities-heart-intraday"]["dataset"][response_length-1]["value"]
                activities_latest_heart_value1 = fitbit_json["activities-heart-intraday"]["dataset"][response_length-2]["value"]
                activities_latest_heart_value2 = fitbit_json["activities-heart-intraday"]["dataset"][response_length-3]["value"]
                activities_latest_heart_value3 = fitbit_json["activities-heart-intraday"]["dataset"][response_length-4]["value"]
                activities_latest_heart_value4 = fitbit_json["activities-heart-intraday"]["dataset"][response_length-5]["value"]
                activities_latest_heart_value5 = fitbit_json["activities-heart-intraday"]["dataset"][response_length-6]["value"]
                activities_latest_heart_value6 = fitbit_json["activities-heart-intraday"]["dataset"][response_length-7]["value"]
                activities_latest_heart_value7 = fitbit_json["activities-heart-intraday"]["dataset"][response_length-8]["value"]
                activities_latest_heart_value8 = fitbit_json["activities-heart-intraday"]["dataset"][response_length-9]["value"]
                activities_latest_heart_value9 = fitbit_json["activities-heart-intraday"]["dataset"][response_length-10]["value"]
                activities_latest_heart_value10 = fitbit_json["activities-heart-intraday"]["dataset"][response_length-11]["value"]
                activities_latest_heart_value11 = fitbit_json["activities-heart-intraday"]["dataset"][response_length-12]["value"]
                activities_latest_heart_value12 = fitbit_json["activities-heart-intraday"]["dataset"][response_length-13]["value"]
                activities_latest_heart_value13 = fitbit_json["activities-heart-intraday"]["dataset"][response_length-14]["value"]
                activities_latest_heart_value14 = fitbit_json["activities-heart-intraday"]["dataset"][response_length-15]["value"]
                print(f"Latest 15 Minute Averages: {activities_latest_heart_value14},{activities_latest_heart_value13},{activities_latest_heart_value12},{activities_latest_heart_value11},{activities_latest_heart_value10},{activities_latest_heart_value9},{activities_latest_heart_value8},{activities_latest_heart_value7},{activities_latest_heart_value6},{activities_latest_heart_value5},{activities_latest_heart_value4},{activities_latest_heart_value3},{activities_latest_heart_value2},{activities_latest_heart_value1},{activities_latest_heart_value0}")
                
                list_data = [activities_latest_heart_value14,activities_latest_heart_value13,activities_latest_heart_value12,activities_latest_heart_value11,activities_latest_heart_value10,activities_latest_heart_value9,activities_latest_heart_value8,activities_latest_heart_value7,activities_latest_heart_value6,activities_latest_heart_value5,activities_latest_heart_value4,activities_latest_heart_value3,activities_latest_heart_value2,activities_latest_heart_value1,activities_latest_heart_value0]
                # print(f"Data : {list_data}")
                lowest_y = sorted(list((list_data)))  # Get lowest sorted value
                highest_y = sorted(list_data,reverse=True)  # Get highest sorted value

                # Display Labels
                date_label.text = f"{activities_timestamp}"
                time_label.text = f"{activities_latest_heart_time[0:-3]}"
                my_plane = Cartesian(
                    x=30,  # x position for the plane
                    y=60,  # y plane position
                    width=DISPLAY_WIDTH-20,  # display width
                    height=DISPLAY_HEIGHT-80,  # display height
                    xrange=(0, 14),  # x range
                    yrange=(lowest_y[0], highest_y[0]),  # y range
                    axes_color=bar_color(highest_y[0]),
                    pointer_color=TEXT_PINK,
                    axes_stroke=4,
                    major_tick_stroke=2,
                    subticks=True,
                )
                plot_group.append(my_plane)
                my_plane.clear_plot_lines()
                data = [
                    (0, activities_latest_heart_value14),
                    (1, activities_latest_heart_value13),
                    (2, activities_latest_heart_value12),
                    (3, activities_latest_heart_value11),
                    (4, activities_latest_heart_value10),
                    (5, activities_latest_heart_value9),
                    (6, activities_latest_heart_value8),
                    (7, activities_latest_heart_value7),
                    (8, activities_latest_heart_value6),
                    (9, activities_latest_heart_value5),
                    (10, activities_latest_heart_value4),
                    (11, activities_latest_heart_value3),
                    (12, activities_latest_heart_value2),
                    (13, activities_latest_heart_value1),
                    (14, activities_latest_heart_value0),
                ]
                try:
                    for x, y in data:
                        my_plane.add_plot_line(x, y)
                        time.sleep(0.5)
                except (IndexError) as e:
                    print("Index Error:", e)
                    continue
            else :
                print(f"Waiting for latest sync...")
                print(f"Not enough values for today to display yet.")
        except (KeyError) as keyerror:
            print(f"Key Error: {keyerror}")
            print(f"Too Many Requests, Expired token, invalid permission, or (key:value) pair error.")
            continue

        print("Board Uptime: ", time_calc(time.monotonic()))  # Board Up-Time seconds
        print("\nFinished!")
        print("Next Update in: ", time_calc(sleep_time))
        print("===============================")

    except (ValueError, RuntimeError) as e:
        print("Failed to get data, retrying\n", e)
        time.sleep(60)
        continue

    display.refresh()
    TAKE_SCREENSHOT = False  # Set to True to take a screenshot
    if TAKE_SCREENSHOT:
        # Initialize SD Card & Mount Virtual File System
        cs = digitalio.DigitalInOut(board.D5)
        sdcard = adafruit_sdcard.SDCard(spi, cs)
        vfs = storage.VfsFat(sdcard)
        virtual_root = "/sd"  # /sd is root dir of SD Card
        storage.mount(vfs, virtual_root)

        print("Taking Screenshot... ")
        save_pixels("/sd/screenshot.bmp", display)
        print("Screenshot Saved")
        storage.umount(vfs)
        print("SD Card Unmounted")  # Do not remove SD card until unmounted

    time.sleep(sleep_time)
