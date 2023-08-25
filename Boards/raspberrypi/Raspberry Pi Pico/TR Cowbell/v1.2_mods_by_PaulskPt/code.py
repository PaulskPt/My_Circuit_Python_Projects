# Based on TR-Cowbell Hardware Test by @DJDevon3
# 2023/03/03 - Neradoc & DJDevon3
# Based on PicoStepSeq by @todbot Tod Kurt
# https://github.com/todbot/picostepseq/
# This file contains changes, additions by @PaulskPt (Github)
# Partly also based on TR_Cowbell_Sequencer_Software repo by @Foamyguy
# 2023-08-20
# More info about buttons and controls, see file: README_buttons_and_controls.md (work-in-progress)
# To choose your display driver: set the global flags "use_ssd1306" and "use_sh1107" (only one can be "True")
# If you want to use WiFi set the "use_wifi" flag to "True" and fill in your WiFi SSID and Password in the file "settings.toml"
# A global flag "my_debug" has been added to control the majority of print statements in this script.
# Added global flag "use_TAG". This flag controls if in calls to function tag_adj() tags received will be printed or not.
# On a small display no function names (variable TAG) in print statements make the display more readable.
# Functions added that are not found in the other repos: count_btns_active(), clr_scrn(), pr_state(), pr_msg(), tag_adj(), do_connect(), wifi_is_connected(), setup().
import asyncio
import time
import board
import busio
import displayio
#import terminalio
from supervisor import ticks_ms
#from digitalio import Direction
from adafruit_mcp230xx.mcp23017 import MCP23017
from mcp23017_scanner import McpKeysScanner
from multi_macropad import MultiKeypad
from adafruit_display_text import label
import os
# Global flags
my_debug = False
# --- DISPLAY DRTIVER selection flags ---+
use_ssd1306 = False  #                   |
use_sh1107 = True  #                     |
# ---------------------------------------+
use_midi = True
use_wifi = False
use_TAG = False

if use_wifi:
    import wifi
    import ipaddress
    import socketpool

if use_midi:
    import json
    import struct
    import storage
    from io import BytesIO
    import msgpack
    from adafruit_midi.note_off import NoteOff
    from adafruit_midi.note_on import NoteOn
    import adafruit_midi
    import usb_midi
    import rotaryio
    from adafruit_debouncer import Debouncer, Button
    import digitalio as digitalio
    from digitalio import Direction

displayio.release_displays()

# Initialize 2 Separate Physical I2C buses
i2c0 = busio.I2C(board.GP13, board.GP12)  # Bus I2C0
i2c1 = busio.I2C(board.GP27, board.GP26)  # Bus I2C1 STEMMA

if use_ssd1306:
    import adafruit_displayio_ssd1306
    WIDTH = 128
    HEIGHT = 64  # Change to 64 if needed
    BORDER = 5
    display_bus = displayio.I2CDisplay(i2c1, device_address=0x3C)
    display = adafruit_displayio_ssd1306.SSD1306(display_bus, width=WIDTH, height=HEIGHT)

if use_sh1107:
    # Addition by @PaulskPt (Github)
    # code for Adafruit OLED 128x128 SH1107
    from adafruit_displayio_sh1107 import SH1107, DISPLAY_OFFSET_ADAFRUIT_128x128_OLED_5297
    # Width, height and rotation for Monochrome 1.12" 128x128 OLED
    WIDTH = 128
    HEIGHT = 128
    ROTATION = 0 # Was: 90

    # Border width
    BORDER = 2

    display_bus = displayio.I2CDisplay(i2c1, device_address=0x3D)

    display = SH1107(
    display_bus,
    width=WIDTH,
    height=HEIGHT,
    display_offset=DISPLAY_OFFSET_ADAFRUIT_128x128_OLED_5297,
    rotation=ROTATION,
    )

# -------------------------------------------------------------------+
# Switch off the Circuitpython logo and the Circuitpython status bar |
# -------------------------------------------------------------------+
import supervisor
display.root_group[0].hidden = False
display.root_group[1].hidden = True # logo
display.root_group[2].hidden = True # status bar
supervisor.reset_terminal(WIDTH, HEIGHT)
display.root_group[0].y = 0
#print("OSC")
while True:
    print("\x1b[2J", end="")
    break
# --------------------------------------------------------------------

print("\n\nTR-COWBELL test")
print(f"Board:\n{board.board_id}")
vfsfat = storage.getmount('/')
ro_state = "Readonly" if (vfsfat.readonly == True) else "Writeable"
print(f"Filesystem:{ro_state}")

if use_ssd1306:
    sd = "SSD1306"
if use_sh1107:
    sd = "SH1107"
print(f"OLED driver: {sd}")
sd = None
print("-"*20)
time.sleep(5)
#print()

# Initialize MCP Chip 1 Step Switches 0-7
mcp1 = MCP23017(i2c0, address=0x21)
# Initalize MCP Chip 2 Step Switches 8-15
mcp2 = MCP23017(i2c0, address=0x20)

PINS1 = [0, 1, 2, 3, 4, 5, 6, 7]
PINS2 = [0, 1, 2, 3, 4, 5, 6, 7]

# MCP scanner and multikeypad
scanner1 = McpKeysScanner(mcp1, PINS1)
scanner2 = McpKeysScanner(mcp2, PINS2)
all_scanner = MultiKeypad(scanner1, scanner2)

# LED pins on ports B
mcp1_led_pins = [mcp1.get_pin(pin) for pin in range(8, 16)]
mcp2_led_pins = [mcp2.get_pin(pin) for pin in range(8, 16)]

# all the LED pins organized per MCP chip
led_pins_per_chip = (mcp1_led_pins, mcp2_led_pins)

# ordered list of led coordinates
led_pins = [(a, b) for a in range(2) for b in range(8)]

# Set all LED pins to output
for (m, x) in led_pins:
    led_pins_per_chip[m][x].direction = Direction.OUTPUT

MODE_I = 0 # index
MODE_N = 1 # note
MODE_F = 2 # file
MODE_M = 3 # midi_channel


mode_lst = ["index", "note", "file", "midi_channel"]

mode_dict = {
    MODE_I : "index",
    MODE_N : "note",
    MODE_M : "midi_channel",
    MODE_F : "file"
    }

mode_rv_dict = {
    "index" : MODE_I,
    "note" : MODE_N,
    "midi_channel" : MODE_M,
    "file" : MODE_F
    }

if use_midi:
    min_midi_channel = 1
    max_midi_channel = 2
    midi_channel = max_midi_channel  # Default channel = 2
    midi_ch_chg_event = False # Midi channel change event. See read_encoder()
    max_note_files = None
    encoder = rotaryio.IncrementalEncoder(board.GP18, board.GP19)
    encoder_btn_pin = digitalio.DigitalInOut(board.GP20)
    encoder_btn_pin.direction = digitalio.Direction.INPUT
    encoder_btn_pin.pull = digitalio.Pull.UP
    encoder_btn = Debouncer(encoder_btn_pin)
    enc_sw_cnt = 0 # mode_lst[1] = index

    up_btn_pin = digitalio.DigitalInOut(board.GP21)  # BUTTON 1
    up_btn_pin.direction = digitalio.Direction.INPUT
    up_btn_pin.pull = digitalio.Pull.UP
    up_btn = Button(up_btn_pin)

    down_btn_pin = digitalio.DigitalInOut(board.GP28) # BUTTON 3
    down_btn_pin.direction = digitalio.Direction.INPUT
    down_btn_pin.pull = digitalio.Pull.UP
    down_btn = Button(down_btn_pin)

    right_btn_pin = digitalio.DigitalInOut(board.GP22) # BUTTON 2
    right_btn_pin.direction = digitalio.Direction.INPUT
    right_btn_pin.pull = digitalio.Pull.UP
    right_btn = Button(right_btn_pin)

    left_btn_pin = digitalio.DigitalInOut(board.GP15)  # BUTTON 4
    left_btn_pin.direction = digitalio.Direction.INPUT
    left_btn_pin.pull = digitalio.Pull.UP
    left_btn = Button(left_btn_pin)

    middle_btn_pin = digitalio.DigitalInOut(board.GP14)  # BUTTON 5
    middle_btn_pin.direction = digitalio.Direction.INPUT
    middle_btn_pin.pull = digitalio.Pull.UP
    middle_btn = Button(middle_btn_pin)

    # midi setup
    midi_tx_pin, midi_rx_pin = board.GP16, board.GP17
    midi_timeout = 0.01
    display_uart = busio.UART(tx=midi_tx_pin, rx=midi_rx_pin,
        baudrate=31250, timeout=midi_timeout) # Was: uart = ...
    #display_uart = busio.UART(board.GP0, board.GP1, baudrate=19200)
    midi = adafruit_midi.MIDI(
        midi_in=usb_midi.ports[0], in_channel=0,
        midi_out=usb_midi.ports[1], out_channel=0  # was: out_channel=1
    )

# Global variables, needed for pr_state()
# lStart is needed to pass the print statements in pr_state() at the start of this script.
# new_event flag is set in read_buttons() and read_encoder().
new_event = False
lStart = True

if use_wifi:
    ip = None
    s_ip = '0.0.0.0'
    pool = None

tag_le_max = 18  # see tag_adj()

# status of the button latches
latches = [False] * 16
#
notes_lst = [None] * 16
#
SELECTED_INDEX = -1

TEMPO = 120 # Beats Per Minute (approximation)
BPM = TEMPO / 60 / 16

def toggle_latch(mcp, pin, state):
    # print(mcp, pin)

    state.latches[mcp * 8 + pin] = not state.latches[mcp * 8 + pin]
    if state.latches[mcp * 8 + pin]:
        state.selected_index = mcp * 8 + pin
        state.notes_lst[mcp * 8 + pin] = 60
    else:
        state.notes_lst[mcp * 8 + pin] = 0

def get_latch(mcp, pin, state):
    return state.latches[mcp * 8 + pin]

class State:
    def __init__(self, saved_state_json=None):
        self.selected_index = -1
        self.notes_lst = [0] * 16
        self.latches = [False] * 16
        self.last_position = encoder.position
        self.mode = mode_dict[MODE_I] # was: "index"
        self.send_off = True
        self.received_ack = True
        self.selected_file = None
        self.saved_loops = None
        self.read_msg_shown = False  # See read_buttons()
        self.write_msg_shown = True  # idem

        if saved_state_json:
            saved_state_obj = json.loads(saved_state_json)
            for i, note in enumerate(saved_state_obj['notes']):
                print(f"note= {note}")
                self.notes_lst[i] = note
                if note != 0:
                    self.latches[i] = True
            self.selected_index = saved_state_obj['selected_index']

    def load_state_json(self, saved_state_json):
        saved_state_obj = json.loads(saved_state_json)
        self.load_state_obj(saved_state_obj)

    def load_state_obj(self, saved_state_obj):
        self.notes_lst = saved_state_obj['notes']
        self.selected_index = saved_state_obj['selected_index']
        for i, note in enumerate(self.notes_lst):
            if note != 0:
                self.latches[i] = True
            else:
                self.latches[i] = False

def increment_selected(state):
    _checked = 0
    _checking_index = (state.selected_index + 1) % 16
    while _checked < 16:
        if state.notes_lst[_checking_index] is not 0:
            state.selected_index = _checking_index
            break
        else:
            _checked += 1
            _checking_index = (_checking_index + 1) % 16

    if _checked >= 16:
        state.selected_index = -1

def decrement_selected(state):
    _checked = 0
    _checking_index = (state.selected_index - 1) % 16
    while _checked < 16:
        if state.notes_lst[_checking_index] is not 0:
            state.selected_index = _checking_index
            break
        else:
            _checked += 1
            _checking_index = (_checking_index - 1) % 16

    if _checked >= 16:
        state.selected_index = -1

# NOTE: it is assumed that key number x (port A) on MCP number y matches
# the LED number x (port B) on the same MCP number y
# if not, a conversion function could be used to translate:
# (key_x, key_y) -> (led_x, led_y)

def index_to_chip_and_index(index):
    return index // 8, index % 8

def chip_and_index_to_index(chip, index):
    return chip * 8 + index

async def count_btns_active(state):
    TAG = await tag_adj("count_btns_active(): ")
    #cnt = 0
    latches_cnt = 0
    for i in range(16):
        #if (state.notes_lst[i] is not None) and (state.notes_lst[i] != 0):
        #    cnt += 1
        if state.latches[i]:
            latches_cnt += 1
    if my_debug:
        if latches_cnt < 2:
            ltch = "latch"
        else:
            ltch = "latches"
        print(f"\ncount_btns_active(): {latches_cnt} button {ltch} active")
        #print(f"\ncount_btns_active(): {cnt} button(s) active and {latches_cnt} latches active")
    # return cnt
    return latches_cnt

async def clr_scrn():
    for i in range(9):
        print()

# Called from blink_the_leds()
async def pr_state(state):
    global lStart, new_event
    TAG = await tag_adj("pr_state(): ")

    if new_event or lStart:
        cnt = await count_btns_active(state)
        # print(f"btns active: {cnt}")
        if cnt > 0:
            btn = "button" if cnt == 1 else "buttons"
            print(TAG+f"\n{cnt} {btn} active")
            print("-"*18)
            grp = 0
            for i in range(len(state.notes_lst)):
                if i == 0 or i == 8:
                    print(f"{grp}/ ", end='')
                    grp += 1
                if i == 4 or i == 12:
                    print("\n   ", end='')
                #if i > 0 and i % 4 == 0:
                #    print("\n   ", end='')
                print("{:>3d} ".format(state.notes_lst[i]), end='')
                if i == 7:
                    print()
            print("\n"+"-"*18)
            if state.mode == "midi_channel":
                print(TAG+f"midi channel: {midi_channel}")
            else:
                print(TAG+f"selected idx: {state.selected_index+1}")
        else:
            nba1 = "No buttons active"
            nba2 = nba1 if lStart else "\n"+nba1
            print(TAG+f"{nba2}")
        print(TAG+f"mode: {state.mode}", end = '')

        lStart = False
        new_event = False

async def pr_msg(state, msg_lst=None):
    TAG = await tag_adj("pr_msg(): ")
    if msg_lst is None:
        msg_lst = ["pr_msg", "test message", "param rcvd:", "None"]
    le = len(msg_lst)
    max_lines = 9
    nr_lines = max_lines if le >= max_lines else le
    await clr_scrn()
    if le > 0:
        for i in range(nr_lines):
            print(TAG+f"{msg_lst[i]}")
        if le < max_lines:
            for j in range((max_lines-le)-1):
                print()
        # await asyncio.sleep(5)
        time.sleep(3)

async def blink_the_leds(state, delay=0.125):
    TAG = await tag_adj("blink_the_leds(): ")
    while True:
        await pr_state(state)
        # blink all the LEDs together
        for (x, y) in led_pins:
            if not get_latch(x, y, state):
                led_pins_per_chip[x][y].value = True
                # time.sleep(0.001)
                await asyncio.sleep(0.001)
                led_pins_per_chip[x][y].value = False
                await asyncio.sleep(delay)
            else:
                #if my_debug:
                    #print(TAG+"getlatch was true")
                    #print(TAG+f"index: {x}, {y} - {x * 8 + y}")
                led_pins_per_chip[x][y].value = False
                #---------- PLAY A NOTE ------------- (added by @PaulskPt -- seeing @Foamyguys stream of dec 2022
                await play_note(state.notes_lst[x * 8 + y], delay, state)
                # time.sleep(0.001)
                led_pins_per_chip[x][y].value = True

async def blink_selected(state, delay=0.05):
    while True:
        if state.selected_index >= 0:
            _selected_chip_and_index = index_to_chip_and_index(state.selected_index)
            # print(led_pins_per_chip[_selected_chip_and_index[0]][_selected_chip_and_index[1]].value)
            if state.notes_lst[state.selected_index] is not None:
                led_pins_per_chip[_selected_chip_and_index[0]][_selected_chip_and_index[1]].value = False
                # time.sleep(delay)
                await asyncio.sleep(delay)
                led_pins_per_chip[_selected_chip_and_index[0]][_selected_chip_and_index[1]].value = True

            else:
                if led_pins_per_chip[_selected_chip_and_index[0]][_selected_chip_and_index[1]].value:
                    led_pins_per_chip[_selected_chip_and_index[0]][_selected_chip_and_index[1]].value = False
                await asyncio.sleep(delay)
        else:
            for i in range(16):
                chip_num, index = index_to_chip_and_index(i)
                led_pins_per_chip[chip_num][index].value = False
            await asyncio.sleep(delay)

async def read_buttons(state):
    global new_event, ro_state
    TAG = await tag_adj("read_buttons(): ")
    btns_active = await count_btns_active(state)
    incn = "Increasing note" if btns_active >0 else ""
    decn = "Decreasing note" if btns_active >0 else ""
    fn = "saved_loops.json"
    state.read_msg_shown = False
    state.write_msg_shown = False
    while True:
        # scan the buttons
        scanner1.update()
        scanner2.update()
        # treat the events
        while event := all_scanner.next_event():
            mcp_number = event.pad_number
            key_number = event.key_number
            if event.pressed:
                new_event = True
                if my_debug:
                    print(TAG+f"Key pressed : {mcp_number} / {key_number}")
                # key pressed, find the matching LED
                led_pin = led_pins_per_chip[mcp_number][key_number]
                # invert the latch value (independently of the LED)
                toggle_latch(mcp_number, key_number, state)
                # change the LED value to match the latch
                _new_latch_state = get_latch(mcp_number, key_number, state)
                if my_debug:
                    print(TAG+f"setting led to: {_new_latch_state}")
                led_pin.value = get_latch(mcp_number, key_number, state)

                if not _new_latch_state:
                    if state.selected_index == chip_and_index_to_index(mcp_number, key_number):
                        increment_selected(state)

            # make sure to yield during the reading of the buttons
            await asyncio.sleep(0)

        # d-pad
        up_btn.update()
        down_btn.update()
        right_btn.update()
        left_btn.update()
        middle_btn.update()
        # if down_btn.long_press:
        #     print("down longpress")
        # if not down_btn.value:
        #     print(down_btn.current_duration)

        if state.mode == "midi_channel": # Only change midi channel with Rotary Encoder control
            break  # return

        if up_btn.fell:
            new_event = True
            btns_active = await count_btns_active(state)
            incn = "Increasing note" if btns_active >0 else ""
            if my_debug:
                print(TAG+f"BUTTON 1 (UP) is pressed: {up_btn.pressed}.")
            if state.mode == "index":
                if btns_active >0:
                    increment_selected(state)
            elif state.mode == "note":
                if my_debug:
                    print(TAG+f"{incn}")
                    print(TAG+f"mode: \"{state.mode}\".")
                if btns_active>0:
                    state.notes_lst[state.selected_index] += 1
                    # print(f"state.notes_lst[{state.selected_index}]= {state.notes_lst[state.selected_index]}")
            elif state.mode == "file":
                if state.selected_file is None:
                    state.selected_file = 0
                if state.saved_loops is None:
                    msg = [TAG, "Please", "long press", "middle button", "to load note sets", "from file"]
                    await pr_msg(state, msg)
                else:
                    state.selected_file += 1
                    if state.selected_file >= len(state.saved_loops):
                        state.selected_file = 0
                    if my_debug:
                        print(TAG+f"loading from state.saved_loops, notes set nr: {state.selected_file}")
                    msg = [TAG, "loading:", "from", "notes set nr: "+str(state.selected_file)]
                    await pr_msg(state, msg)
                    #print(TAG+f"loading: {state.selected_file}")
                    state.load_state_obj(state.saved_loops[state.selected_file])
                    state.mode = mode_dict[MODE_I] # Change mode to "index"

        if down_btn.fell:
            new_event = True
            btns_active = await count_btns_active(state)
            decn = "Decreasing note" if btns_active >0 else ""
            if my_debug:
                    print(TAG+f"BUTTON 3 (DOWN) is pressed: {down_btn.pressed}")
            if state.mode == "index":
                if btns_active >0:
                    decrement_selected(state)
            elif state.mode == "note":
                if my_debug:
                    print(TAG+f"{decn}")
                    print(TAG+f"mode: \"{state.mode}\".")
                if btns_active>0:
                    state.notes_lst[state.selected_index] -= 1
                    # print(f"state.notes_lst[{state.selected_index}]= {state.notes_lst[state.selected_index]}")
            elif state.mode == "file":
                if state.selected_file is None:
                    state.selected_file = 0
                if state.saved_loops is None:
                    msg = [TAG, "Please", "long press", "middle button", "to load note sets", "from file"]
                    await pr_msg(state, msg)
                else:
                    state.selected_file -= 1
                    if state.selected_file < 0:
                        state.selected_file = len(state.saved_loops) - 1
                    if my_debug:
                        print(TAG+f"loading from state.saved_loops, notes set nr: {state.selected_file}")
                    msg = [TAG, "loading:", "from", "notes set nr: "+str(state.selected_file)]
                    await pr_msg(state, msg)
                    #print(TAG+f"loading: {state.selected_file}")
                    state.load_state_obj(state.saved_loops[state.selected_file])
                    state.mode = mode_dict[MODE_I] # Change mode to "index"

        if right_btn.fell:
            new_event = True
            btns_active = await count_btns_active(state)
            incn = "Increasing note" if state.mode == "note" and btns_active >0 else ""
            if my_debug:
                    print(TAG+f"BUTTON 2 (RIGHT) is pressed: {right_btn.pressed}.")
            if state.mode == "index":
                if btns_active >0:
                    increment_selected(state)
            elif state.mode == "note":
                if my_debug:
                    print(TAG+f"{incn}")
                    print(TAG+f"mode: \"{state.mode}\".")
                if btns_active>0:
                    state.notes_lst[state.selected_index] += 1
                    # print(f"state.notes_lst[{state.selected_index}]= {state.notes_lst[state.selected_index]}")
            elif state.mode == "file":
                if my_debug:
                    print(TAG+"BUTTON 2 (RIGHT) doing nothing")
            # state.send_off = not state.send_off
            # print(f"send off: {state.send_off}")

        if left_btn.fell:
            new_event = True
            btns_active = await count_btns_active(state)
            decn = "Decreasing note" if state.mode == "note" and btns_active >0 else ""
            if my_debug:
                    print(TAG+f"BUTTON 4 (LEFT) is pressed: {left_btn.pressed}.")
            if state.mode == "index":
                if btns_active >0:
                    decrement_selected(state)
            elif state.mode == "note":
                if my_debug:
                    print(TAG+f"{decn}")
                    print(TAG+f"mode: \"{state.mode}\".")
                if btns_active >0:
                    state.notes_lst[state.selected_index] -= 1
                    # print(f"state.notes_lst[{state.selected_index}]= {state.notes_lst[state.selected_index]}")
                else:
                    print("no buttons active")
            elif state.mode == "file":
                if my_debug:
                    print(TAG+"BUTTON 4 (LEFT) doing nothing")

        if middle_btn.long_press:
            new_event = True
            if my_debug:
                print(TAG+f"BUTTON 5 (MIDDLE) is long pressed: {middle_btn.long_press}")
            state.selected_file = None
            if state.mode == "file":
                try:
                    f = open(fn, "r")
                    state.saved_loops = json.loads(f.read())["loops"]
                    f.close()
                    if my_debug:
                        print(TAG+fn)
                    msg = [TAG, "saved note sets", "have been", "read from file", fn, "successfully"]
                    print(TAG+f"saved note set (loop): {state.saved_loops}")
                    await pr_msg(state, msg)
                except (OSError, KeyError) as e:
                    print(TAG+f"Error occurred: {e}")
                    state.saved_loops = []
            else:
                if my_debug:
                    print("For reading note sets, saved to files, set mode to \"file\"")
                msg = [TAG,"For reading","note sets","saved to file","set mode to:", "\"file\""]
                await pr_msg(state, msg)

        if middle_btn.fell:
            new_event = True
            if my_debug:
                print(TAG+f"BUTTON 5 (MIDDLE) is pressed: {middle_btn.pressed}")
            if state.mode == "index" or state.mode == "note":
                state.mode = mode_dict[MODE_F] # Change mode to "file"
            elif state.mode == "file":
                if ro_state == "Writeable":
                    # save the current file
                    if my_debug:
                        print(TAG+"saving")
                    try:  # This try...except block added by @PaulskPt
                        f = open("saved_loops.json", "w")
                        f.write(json.dumps(state.saved_loops))
                        f.close()
                        if not state.write_msg_shown:
                            if my_debug:
                                print(TAG+"save complete")
                            msg = [TAG, "note sets", "saved to file", fn, "successfully"]
                            await pr_msg(state, msg)
                            state.write_msg_shown = True
                    except OSError as e:
                        print(TAG+f"OSError while trying to save note sets to file. Error: {e}")
                else:
                    if my_debug:
                        print("Filesystem is readonly. Cannot save note sets to file")
                    msg = [TAG, "Filesystem is", "readonly.", "Unable to save", "note sets","to file:", fn]
                    await pr_msg(state, msg)
                #else:
                #    pass
                #    # go to playback / selecting index mode
                #    #state.mode = "index"
            #else:
            #    state.mode = "note" if state.mode == "index" else "index"
            #    if my_debug:
            #        print(TAG+f"new mode: {state.mode}")
        else:
            # same
            pass

        # slow down the loop a little bit, can be adjusted
        await asyncio.sleep(0.15)  # Was: 0.05 or BPM -- has to be longer to avoid double hit

async def read_encoder(state):
    global new_event, enc_sw_cnt, midi_ch_chg_event, midi_channel
    TAG = await tag_adj("read_encoder(): ")
    # print("\n"+TAG+f"mode: {state.mode}")
    await pr_state(state)
    #if state.mode == "file":
    #    return
    while True:
        cur_position = encoder.position
        # print(cur_position)
        if state.last_position < cur_position:
            new_event = True
            if my_debug:
                print("\n"+TAG+"Encoder turned CW")
            if state.mode == "index":
                increment_selected(state)
            elif state.mode == "note":
                if state.selected_index != -1:
                    if my_debug:
                        print(TAG+f"{state.last_position} -> {cur_position}")
                    state.notes_lst[state.selected_index] += 1
            elif state.mode == "midi_channel":
                midi_ch_chg_event = True
                midi_channel += 1
                if midi_channel > max_midi_channel:
                    midi_channel = min_midi_channel
                if my_debug:
                    print(f"new midi channel: {midi_channel}")
            elif state.mode == "file":
                if state.selected_file is None:
                    state.selected_file = 0
                else:
                    state.selected_file += 1
                if my_debug:
                    print(TAG+f"state.selected_file= {state.selected_file}")

        elif cur_position < state.last_position:
            new_event = True
            if my_debug:
                print("\n"+TAG+"Encoder turned CCW")
            if state.mode == "index":
                decrement_selected(state)
            elif state.mode == "note":
                if state.selected_index != -1:
                    if my_debug:
                        print(TAG+f"{state.last_position} -> {cur_position}")
                    state.notes_lst[state.selected_index] -= 1
            elif state.mode == "midi_channel":
                midi_ch_chg_event = True
                midi_channel -= 1
                if midi_channel < min_midi_channel:
                    midi_channel = max_midi_channel
                if my_debug:
                    print(f"new midi channel: {midi_channel}")
            elif state.mode == "file":
                if state.selected_file is None:
                    state.selected_file = 0
                else:
                    state.selected_file -= 1
                    if state.selected_file < 0:
                        state.selected_file = 0
                if my_debug:
                    print(TAG+f"state.selected_file= {state.selected_file}")
        else:
            # same
            pass

        encoder_btn.update()

        if encoder_btn.fell:
            new_event = True
            enc_sw_cnt += 1
            if my_debug:
                print(TAG+f"len(mode_lst): {len(mode_lst)}")
            if enc_sw_cnt > len(mode_lst)-1:
                enc_sw_cnt = 0

            #state.mode = "note" if state.mode == "index" else "index"
            state.mode = mode_lst[enc_sw_cnt]
            if my_debug:
                print(TAG+"Encoder sw. pressed")
                print(TAG+f"new mode:\n\"{state.mode}\"")

        state.last_position = cur_position
        await asyncio.sleep(0.05)

async def play_note(note, delay, state):
    global midi_ch_chg_event
    TAG = await tag_adj("play_note(): ")
    if (note != 0):
        if not state.send_off:
            midi.send(NoteOff(note, 0))
        if note == 61 and midi_ch_chg_event:
            midi_ch_chg_event = False  # Clear event flag
            note_on = NoteOn(note, 127)
            #if my_debug:
            #    print(TAG+f"playing other channel? {note_on.channel}")
            midi.send(note_on, channel=midi_channel)
            await asyncio.sleep(delay)

            if state.send_off:
                midi.send(NoteOff(note, 0), channel=midi_channel)
        else:
            note_on = NoteOn(note, 127)
            midi.send(note_on)

            await asyncio.sleep(delay)

            if state.send_off:
                midi.send(NoteOff(note, 0))

async def update_display(state, delay=0.125):
    while True:
        b = BytesIO()
        msgpack.pack({"notes": state.notes_lst,
                      "selected_index": state.selected_index,
                      "mode": state.mode}, b)
        b.seek(0)
        # print(b.read())
        # b.seek(0)
        display_uart.write(b.read())
        display_uart.write(b"\n")
        # display_uart.write(struct.pack("b"*len(state.notes_lst),*state.notes_lst))

        await asyncio.sleep(delay)

        # if state.received_ack:
        #     #display_uart.write(bytes(state.notes_lst))
        #     b = BytesIO()
        #     msgpack.pack({"notes": state.notes_lst, "selected_index": state.selected_index}, b)
        #     b.seek(0)
        #     print(b.read())
        #     b.seek(0)
        #     display_uart.write(b.read())
        #     display_uart.write(b"\n")
        #     state.received_ack = False
        #     #display_uart.write(struct.pack("b"*len(state.notes_lst),*state.notes_lst))
        #
        # else:
        #     data = display_uart.readline()
        #     if data is not None:
        #         print(f"received: {data}")
        #
        # await asyncio.sleep(delay)

"""
    Function tag_adj()

    :param  str
    :return str

    This function fills param t with trailing spaces up to the value of global variable tag_le_max
"""
async def tag_adj(t):
    global tag_le_max

    if use_TAG:
        le = 0
        spc = 0
        ret = t

        if isinstance(t, str):
            le = len(t)
        if le >0:
            spc = tag_le_max - le
            #print(f"spc= {spc}")
            ret = ""+t+"{0:>{1:d}s}".format("",spc)
            #print(f"s=\'{s}\'")
        return ret
    return ""

async def do_connect():
    global ip, s_ip, pool
    TAG = await tag_adj("do_connect(): ")
    # if my_debug:
    #    print(TAG+"wifi.radio.enabled=", wifi.radio.enabled)
    cnt = 0
    timeout_cnt = 5
    dc_ip = None
    #s_ip = None

    # print(TAG+f"dc_ip= {dc_ip}. type(dc_ip)= {type(dc_ip)}")
    while dc_ip is None or dc_ip == '0.0.0.0':
        # print(TAG+f"cnt= {cnt}")
        try:
            # wifi.radio.connect(secrets["ssid"], secrets["password"])
            wifi.radio.connect(os.getenv("CIRCUITPY_WIFI_SSID"), os.getenv("CIRCUITPY_WIFI_PASSWORD"))
        except ConnectionError as e:
            if cnt == 0:
                print(TAG+"WiFi connection try: {:2d}. Error: \'{}\'\n\tTrying max {} times.".format(cnt+1, e, timeout_cnt))
        dc_ip = wifi.radio.ipv4_address
        pool = socketpool.SocketPool(wifi.radio)
        cnt += 1
        if cnt > timeout_cnt:
            print(TAG+"WiFi connection timed-out")
            break
        time.sleep(1)

    if dc_ip:
        ip = dc_ip
        s_ip = str(ip)

    if s_ip is not None and s_ip != '0.0.0.0':
        # led.value = True
        if my_debug:
            # print(TAG+"s_ip= \'{}\'".format(s_ip))
            print(TAG+f"connected to {os.getenv('CIRCUITPY_WIFI_SSID')}")
            print(TAG+"IP address is", ip)

        addr_idx = 0
        addr_dict = {0:'LAN gateway', 1:'google.com'}

        info = pool.getaddrinfo(addr_dict[1], 80)
        addr = info[0][4][0]
        if my_debug:
            print(TAG+f"resolved {addr_dict[1][:-4]} as {addr}")
        ipv4 = ipaddress.ip_address(addr)

        for _ in range(10):
            result = wifi.radio.ping(ipv4)
            if result:
                if my_debug:
                    print(TAG+f"Ping {addr}: {result*1000} ms")
                break
            else:
                print(TAG+"no response")
            time.sleep(0.5)
    elif s_ip == '0.0.0.0':
        #led.value = False
        print(TAG+f"s_ip= {s_ip}. Resetting this \'{wifi.radio.hostname}\' device...")
        time.sleep(2)  # wait a bit to show the user the message
        #import microcontroller
        #microcontroller.reset()

async def wifi_is_connected():
    return True if s_ip is not None and s_ip != '0.0.0.0' else False

async def setup():
    TAG = await tag_adj("setup(): ")

    if use_wifi:
        if not await wifi_is_connected():
            if my_debug:
                print(TAG+f"Connecting WiFi to {os.getenv('CIRCUITPY_WIFI_SSID')}")
            await do_connect()
        else:
            print(TAG+f"WiFi is connected to {os.getenv('CIRCUITPY_WIFI_SSID')}")

async def main():
    # state = State(saved_loops.LOOP1)
    test_state_json = []
    state = State()
    await asyncio.gather(
        asyncio.create_task(setup()),
        asyncio.create_task(blink_the_leds(state, delay=0.125)),
        asyncio.create_task(read_buttons(state)),
        asyncio.create_task(blink_selected(state)),
        asyncio.create_task(update_display(state, delay=0.125)),
        asyncio.create_task(read_encoder(state))
    )

asyncio.run(main())
