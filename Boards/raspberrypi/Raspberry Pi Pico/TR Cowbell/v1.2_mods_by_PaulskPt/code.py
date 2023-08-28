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
# Fourteen functions added that are not found in the other repos for the TR-Cowbell board:
#   count_btns_active(), clr_events(), clr_scrn(), pr_state(), pr_msg(), load_all_note_sets(), load_note_set(),
#   fifths_change(), key_change(), mode_change() tag_adj(), do_connect(), wifi_is_connected() and setup().
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
use_wifi = False
use_TAG = False

if use_wifi:
    import wifi
    import ipaddress
    import socketpool

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

MODE_C = 0 # mchg  # mode change
MODE_I = 1 # index
MODE_N = 2 # note
MODE_F = 3 # file
MODE_M = 4 # midi_channel
MODE_D = 5 # fifths (circle of fifths) flag choose
MODE_K = 6 # key of the notes: Major or Minor
MODE_MIN = MODE_C
MODE_MAX = MODE_K


mode_lst = ["mode_change", "index", "note", "file", "midi_channel", "disp_fifths", "note_key"]

mode_dict = {
    MODE_C : "mode_change",
    MODE_I : "index",
    MODE_N : "note",
    MODE_F : "file",
    MODE_M : "midi_channel",
    MODE_D : "fifths",   # Display as Fifths or 'Normal' number values
    MODE_K : "note_key"  # When displaying as Fifths, display in Key C Major or C Minor
    }

mode_short_dict = {
    MODE_C : "mchg",
    MODE_I : "indx",
    MODE_N : "note",
    MODE_F : "file",
    MODE_M : "midi",
    MODE_D : "fift",
    MODE_K : "nkey"
    }

mode_rv_dict = {
    "mode_change" : MODE_C,
    "index" : MODE_I,
    "note" : MODE_N,
    "file" : MODE_F,
    "midi_channel" : MODE_M,
    "fifths" : MODE_D,
    "note_key" : MODE_K
    }

notes_C_dict = {
    12 : "C0",
    24 : "C1",
    36 : "C2",
    48 : "C3",
    60 : "C4",
    72 : "C5",
    84 : "C6",
    96 : "C7"
    }

# See https://en.wikipedia.org/wiki/Circle_of_fifths
# Circle of fifths is a way of organizing the 12 chromatic pitches
# as a sequence of perfect fifths.
# Key of C Major:
notes_major_dict = {
    60 : "C",
    61 : "G",
    62 : "D",
    63 : "A",
    64 : "E",
    65 : "B/Cb",
    66 : "F#/Gb",
    67 : "C#/Db",
    68 : "Ab",
    69 : "Eb",
    70 : "Bb",
    71 : "F"
    }

# Key of C Minor
notes_minor_dict = {
    60 : "a",
    61 : "e",
    62 : "b",
    63 : "f#",
    64 : "c#",
    65 : "g#",
    66 : "d#/cb",
    67 : "bb",
    68 : "f",
    69 : "c",
    70 : "g",
    71 : "d"
    }

midi_channel_min = 1
midi_channel_max = 2
encoder = rotaryio.IncrementalEncoder(board.GP18, board.GP19)
encoder_btn_pin = digitalio.DigitalInOut(board.GP20)
encoder_btn_pin.direction = digitalio.Direction.INPUT
encoder_btn_pin.pull = digitalio.Pull.UP
encoder_btn = Debouncer(encoder_btn_pin)

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
# state.btn_event flag is set in read_buttons() and read_encoder().
# See: state.btn_event
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

class State:
    def __init__(self, saved_state_json=None):
        self.selected_index = -1
        self.notes_lst = [0] * 16
        self.latches = [False] * 16
        self.last_position = encoder.position
        self.mode = mode_dict[MODE_C] # was: MODE_I  (indx)
        self.send_off = True
        self.received_ack = True
        self.selected_file = None
        self.saved_loops = None
        self.read_msg_shown = False  # See read_buttons()
        self.write_msg_shown = True  # idem
        self.fn = "saved_loops.json"
        self.btn_event = False
        self.longpress_event = False
        self.midi_channel = 2
        self.midi_ch_chg_event = False # Midi channel change event. See read_encoder() and play_note()
        self.enc_sw_cnt = 0  # mode_lst[0] = index
        self.display_fifths = False # "Normal" (number values) display
        self.key_major = True  # If False, the key is Minor
        self.encoder_btn_cnt = 0  # Counter for double press

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

def count_btns_active(state):
    TAG = tag_adj("count_btns_active(): ")
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

def clr_events(state):
    state.btn_event = False

def clr_scrn():
    for i in range(9):
        print()

# Called from blink_the_leds()
def pr_state(state):
    global lStart
    TAG = tag_adj("pr_state(): ")
    # clr_scrn()
    if state.selected_file is None:
        ns = "?"
    else:
        ns = state.selected_file+1
    if state.btn_event or lStart:
        org_cnt = count_btns_active(state)
        # print(f"btns active: {cnt}")
        if org_cnt == 0:
            my_lst = state.notes_lst
            if len(my_lst) == 0:
                my_lst = [0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0]
                cnt = len(my_lst)
        #if cnt > 0:
        btn = "button" if org_cnt in [0, 1] else "buttons"
        print(TAG+f"\n{org_cnt} {btn} active")
        print("-"*18)
        grp = 0
        if not state.display_fifths:
            for i in range(len(state.notes_lst)):
                if i == 0 or i == 8:
                    print(f"{grp}/ ", end='')
                    grp += 1
                if i == 4 or i == 12:
                    print("\n   ", end='')
                #if i > 0 and i % 4 == 0:
                #    print("\n   ", end='')
                sn = state.notes_lst[i]
                if sn in notes_C_dict.keys():
                    sn = notes_C_dict[sn]
                    print("{:>3s} ".format(sn), end='')
                else:
                    print("{:>3d} ".format(sn), end='')
                if i == 7:
                    print()
            print("\n"+"-"*18)
        else:
            for i in range(len(state.notes_lst)):
                if i == 0 or i == 8:
                    grp += 1
                if i == 4 or i == 12:
                    print("\n", end='')
                #if i > 0 and i % 4 == 0:
                #    print("\n   ", end='')

                n = state.notes_lst[i] % 12
                idx = 60 + n # Value 60 represents the "Central C" or C4
                if state.key_major:
                    if idx in notes_major_dict.keys():
                        sn = notes_major_dict[idx]
                    else:
                        sn = state.notes_lst[i]
                        if sn == 60:
                            sn = notes_C_dict[sn]
                else:
                    if idx in notes_minor_dict.keys():
                        sn = notes_minor_dict[idx]
                    else:
                        sn = state.notes_lst[i]
                        if sn == 60:
                            sn = notes_C_dict[sn]
                le = len(sn)
                if le > 5:
                    sn = sn[:5]
                print("{:s} ".format(sn), end='')
                #else:
                #    print("{:>3d} ".format(state.notes_lst[i]), end='')
                if i == 7:
                    print()
            print("\n"+"-"*18)
        if state.mode == mode_dict[MODE_M]:  # "midi_channel"
            print(TAG+f"midi channel: {state.midi_channel}")
        else:
            if org_cnt > 0:
                print(TAG+f"selected idx: {state.selected_index+1}")

        if org_cnt == 0:
            nba1 = "No buttons active"
            nba2 = nba1 if lStart else nba1
            print(TAG+f"{nba2}")
        print(TAG+f"mode:{mode_short_dict[mode_rv_dict[state.mode]]}.NoteSet:{ns}", end = '')

        if lStart: lStart = False
        clr_events(state)  # Clear events
        if state.longpress_event:
            state.longpress_event = False

def pr_msg(state, msg_lst=None):
    TAG = tag_adj("pr_msg(): ")
    if msg_lst is None:
        msg_lst = ["pr_msg", "test message", "param rcvd:", "None"]
    le = len(msg_lst)
    max_lines = 9
    nr_lines = max_lines if le >= max_lines else le
    clr_scrn()
    if le > 0:
        for i in range(nr_lines):
            print(TAG+f"{msg_lst[i]}")
        if le < max_lines:
            for j in range((max_lines-le)-1):
                print()
        time.sleep(3)

async def blink_the_leds(state, delay=0.125):
    TAG = tag_adj("blink_the_leds(): ")
    while True:
        #pr_state(state)
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
                await play_note(state, state.notes_lst[x * 8 + y], delay)
                # time.sleep(0.001)
                led_pins_per_chip[x][y].value = True
        pr_state(state)

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

def load_all_note_sets(state, use_warnings):
    TAG = tag_adj("load_all_note_sets(): ")
    state.selected_file = None
    original_mode = state.mode
    #if state.mode != "file":
    state.mode = mode_dict[MODE_F] # "file"
    ret = True
    f = None
    try:
        f = open(state.fn, "r")
        #state.saved_loops = json.loads(f.read())["loops"]
        sl = json.loads(f.read()) # ["loops"]
        f.close()
        if my_debug:
            print(TAG+f"\nread fm file: {sl}")

        if "loops" not in sl.keys():
            sl["loops"] = []

        state.saved_loops = sl

        state.selected_file = len(state.saved_loops)-1 # Select last note set (0,0,0,...)
        state.selected_index = -1
        if use_warnings:
            if my_debug:
                print(TAG+state.fn)
                print(TAG+f"note sets: {state.saved_loops}\nloaded successfully")
            msg = [TAG, "note sets", "have been", "read from file", state.fn, "successfully"]
            pr_msg(state, msg)
    except (OSError, KeyError) as e:
        print(TAG+f"Error occurred while reading from file {f}: {e}")
        state.saved_loops = []
        ret = False
    state.mode = original_mode # restore mode
    return ret

def load_note_set(state, dir_up, use_warnings):
    TAG = tag_adj("load_note_set(): ")
    ret = None
    if state.saved_loops is None:
        ret = load_all_note_sets(state, use_warnings) # Try to load all note sets
        if not ret:
            # failed to load
            if use_warnings:
                msg = [TAG, "Please", "long press", "middle button", "to load note sets", "from file"]
                pr_msg(state, msg)
            return

    if dir_up is None:
        dir_up = True

    if state.selected_file is None:
        state.selected_file = -1
        state.selected_index = -1
    else:
        if dir_up:
            state.selected_file += 1
            if state.selected_file >= len(state.saved_loops):
                state.selected_file = 0 # wrap to first
        else:
            state.selected_file -= 1
            if state.selected_file < 0:
                state.selected_file = len(state.saved_loops)-1 # wrap to last
        if use_warnings:
            if my_debug:
                print(TAG+f"loading notes set nr: {state.selected_file+1} (from memory) successful")
            msg = [TAG, "loading:", "from", "notes set nr: "+str(state.selected_file+1)]
            pr_msg(state, msg)
        #print(TAG+f"loading: {state.selected_file}")
    state.load_state_obj(state.saved_loops[state.selected_file])
    state.mode = mode_dict[MODE_I] # Change mode to "index"
    #pr_state(state)


def fifths_change(state):
    TAG = tag_adj("fifths_change(): ")
    if state.display_fifths:
        state.display_fifths = False  # negate the flag
    else:
        state.display_fifths = True
    msg = [TAG, "Display fifths", "changed to:", state.display_fifths]
    pr_msg(state, msg)

def key_change(state):
    TAG = tag_adj("key_change(): ")
    if state.key_major:
        state.key_major = False  # negate the flag
    else:
        state.key_major = True
    k = "{:s}".format("Major" if state.key_major else "Minor")
    msg = [TAG, "The key", "of the notes", "changed to:", k]
    pr_msg(state, msg)

def mode_change(state):
    TAG = tag_adj("mode_change(): ")
    state.btn_event = True
    m_idx = MODE_I
    msg_shown = False
    while True:
        if not msg_shown:
            print(TAG+"\n|---- Mode -----|")
            for k, v in mode_short_dict.items():
                if m_idx == k:
                    print(TAG+f"  >> {v} {k+1} <<")
                else:
                    print(TAG+f"     {v} {k+1}   ")
            print(TAG+"| Exit=>Enc Btn |", end= '')
            msg_shown = True

        enc_pos = encoder.position
        # print(TAG+f"state.lp: {state.last_position}, enc pos: {enc_pos}")

        if state.last_position < enc_pos:
            state.last_position = enc_pos
            m_idx += 1
            if m_idx > MODE_MAX:
                m_idx = MODE_MIN
            msg_shown = False
        elif enc_pos < state.last_position:
            state.last_position = enc_pos
            m_idx -= 1
            if m_idx < MODE_MIN:
                m_idx = MODE_MAX
            msg_shown = False
        else:
            pass

        encoder_btn.update()

        if encoder_btn.fell:
            if my_debug:
                print(TAG+f"\nsaving mode as: {mode_dict[m_idx]}")
            state.enc_sw_cnt = m_idx
            state.mode = mode_dict[m_idx]
            state.last_position = enc_pos
            break
        time.sleep(0.05)

async def read_buttons(state):
    global ro_state

    TAG = tag_adj("read_buttons(): ")
    btns_active = count_btns_active(state)
    incn = "Increasing note" if btns_active >0 else ""
    decn = "Decreasing note" if btns_active >0 else ""
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
                state.btn_event = True

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

        #pr_state(state)  # This also clears events

        if state.mode != mode_dict[MODE_M]: # "midi_channel". Only change midi channel with Rotary Encoder control
            if state.btn_event == False:  # only if no other event is being processed

                if up_btn.fell:
                    state.btn_event = True
                    btns_active = count_btns_active(state)
                    incn = "Increasing note" if btns_active >0 else ""
                    if my_debug:
                        print(TAG+f"BUTTON 1 (UP) is pressed: {up_btn.pressed}.")
                    #if state.mode == mode_dict[MODE_I]: # "index"
                    #    if btns_active >0:
                    #        increment_selected(state)
                    if state.mode == mode_dict[MODE_N]: # "note"
                        if my_debug:
                            print(TAG+f"{incn}")
                            print(TAG+f"mode: \"{state.mode}\".")
                        if btns_active>0:
                            state.notes_lst[state.selected_index] += 1
                            # print(f"state.notes_lst[{state.selected_index}]= {state.notes_lst[state.selected_index]}")
                    elif state.mode in ["index", "file"]:
                        dir_up = True
                        use_warnings = True
                        load_note_set(state, dir_up, use_warnings)

                if down_btn.fell:
                    state.btn_event = True
                    btns_active = count_btns_active(state)
                    decn = "Decreasing note" if btns_active >0 else ""
                    if my_debug:
                            print(TAG+f"BUTTON 3 (DOWN) is pressed: {down_btn.pressed}")
                    #if state.mode == mode_dict[MODE_I]:  # "index"
                    #    if btns_active >0:
                    #        decrement_selected(state)
                    if state.mode == mode_dict[MODE_N]:  # "note"
                        if my_debug:
                            print(TAG+f"{decn}")
                            print(TAG+f"mode: \"{state.mode}\".")
                        if btns_active>0:
                            state.notes_lst[state.selected_index] -= 1
                            # print(f"state.notes_lst[{state.selected_index}]= {state.notes_lst[state.selected_index]}")
                    elif state.mode in ["index", "file"]:
                        dir_up = False
                        use_warnings = True
                        load_note_set(state, dir_up, use_warnings)

                if right_btn.fell:
                    state.btn_event = True
                    btns_active = count_btns_active(state)
                    incn = "Increasing note" if state.mode == mode_dict[MODE_N] and btns_active >0 else ""
                    if my_debug:
                            print(TAG+f"BUTTON 2 (RIGHT) is pressed: {right_btn.pressed}.")
                    if state.mode == mode_dict[MODE_I]:  # "index"
                        if btns_active >0:
                            increment_selected(state)
                    elif state.mode == mode_dict[MODE_N]:  # "note"
                        if my_debug:
                            print(TAG+f"{incn}")
                            print(TAG+f"mode: \"{state.mode}\".")
                        if btns_active>0:
                            state.notes_lst[state.selected_index] += 1
                            # print(f"state.notes_lst[{state.selected_index}]= {state.notes_lst[state.selected_index]}")
                    elif state.mode == mode_dict[MODE_F]:  # "file"
                        if my_debug:
                            print(TAG+"BUTTON 2 (RIGHT) doing nothing")
                    # state.send_off = not state.send_off
                    # print(f"send off: {state.send_off}")

                if left_btn.fell:
                    state.btn_event = True
                    btns_active = count_btns_active(state)
                    decn = "Decreasing note" if state.mode == mode_dict[MODE_N] and btns_active >0 else ""
                    if my_debug:
                            print(TAG+f"BUTTON 4 (LEFT) is pressed: {left_btn.pressed}.")
                    if state.mode == mode_dict[MODE_I]:  # "index"
                        if btns_active >0:
                            decrement_selected(state)
                    elif state.mode == mode_dict[MODE_N]:  # "note"
                        if my_debug:
                            print(TAG+f"{decn}")
                            print(TAG+f"mode: \"{state.mode}\".")
                        if btns_active >0:
                            state.notes_lst[state.selected_index] -= 1
                            # print(f"state.notes_lst[{state.selected_index}]= {state.notes_lst[state.selected_index]}")
                        else:
                            print("no buttons active")
                    elif state.mode == mode_dict[MODE_F]:  # "file"
                        if my_debug:
                            print(TAG+"BUTTON 4 (LEFT) doing nothing")

                if middle_btn.long_press:
                    state.btn_event = True
                    state.longpress_event = True
                    if my_debug:
                        print(TAG+f"BUTTON 5 (MIDDLE) is long pressed: {middle_btn.long_press}")
                    use_warnings = False
                    load_all_note_sets(state, use_warnings)

                if middle_btn.fell:
                    state.btn_event = True
                    if my_debug:
                        print(TAG+f"BUTTON 5 (MIDDLE) is pressed: {middle_btn.pressed}")
                    if state.mode  in ["index", "note"]:
                        state.mode = mode_dict[MODE_F] # Change mode to "file"
                    elif state.mode == mode_dict[MODE_F]: # "file"
                        if ro_state == "Writeable":
                            f_lst = os.listdir("/")
                            fn_bak = "/" + state.fn[:-4] + "bak"
                            if fn_bak in f_lst:
                                try:
                                    os.remove(fn_bak)  # remove the file "saved_loops.bak"
                                    print(TAG+f"removing file: \"{fn_bak}\"")
                                except OSError as e:
                                    print(TAG+f"OSError while trying to remove file \"{fn_bak}\". Error: {e}")
                            else:
                                print(TAG+f"\nfile \"{fn_bak}\" not found")
                            if state.fn in f_lst:  # rename existing saved_loops.json to saved_loops.bak
                                try:
                                    fn_ren = "/"+state.fn   # e.g. "/saved_loops.json"
                                    os.rename(fn_ren, fn_bak)
                                    print(TAG+f"file \"{fn_ren}\" renamed to \"{fn_bak}\"")
                                except OSError as e:
                                    print(TAG+f"OSError while trying to rename file \"{fn_ren}\" to \"{fn_bak}\". Error: {e}")
                            try:
                                # save the current file
                                if my_debug:
                                    print(TAG+f"saving note sets (loops) to: \"{state.fn}\"")
                                msg = [TAG, "Saving", "note sets (loops)", "to file:", state.fn]
                                pr_msg(state, msg)

                                le = len(state.saved_loops["loops"])
                                state.saved_loops["loops"].insert(le,
                                {
                                "notes": state.notes_lst,
                                "selected_index": state.selected_index
                                })

                                f = open(state.fn, "w")
                                f.write("{\"loops\": ")
                                tmp = json.dumps(state.saved_loops)
                                print(TAG+f"saving to file: \"{tmp}\"")
                                f.write(tmp)
                                f.write("}")
                                f.close()
                                if not state.write_msg_shown:
                                    print(TAG+"save complete")
                                    msg = [TAG, "note sets (loops)", "saved to file", state.fn, "successfully"]
                                    pr_msg(state, msg)
                                    state.write_msg_shown = True
                            except OSError as e:
                                print(TAG+f"OSError while trying to save note sets to file. Error: {e}")
                            # Cleanup
                            f = None
                            f_lst = None
                            fn_ren = None
                            fn_bak = None
                        else:
                            if my_debug:
                                print("Filesystem is readonly. Cannot save note sets to file")
                            msg = [TAG, "Filesystem is", "readonly.", "Unable to save", "note sets","to file:", state.fn]
                            pr_msg(state, msg)

        # slow down the loop a little bit, can be adjusted
        await asyncio.sleep(0.15)  # Was: 0.05 or BPM -- has to be longer to avoid double hit

async def read_encoder(state):
    TAG = tag_adj("read_encoder(): ")
    # print("\n"+TAG+f"mode: {state.mode}")
    pr_state(state)
    tm_start = int(time.monotonic())
    tm_trigger = 7

    state.enc_sw_cnt = mode_rv_dict[state.mode]  # line-up the encoder switch count with that of the current state.mode
    if my_debug:
        print(TAG+f"mode_rv_dict[\"{state.mode}\"]= {mode_rv_dict[state.mode]}")

    while True:
        cur_position = encoder.position
        # print(cur_position)
        if state.last_position < cur_position:
            state.last_position = cur_position
            state.btn_event = True
            if my_debug:
                print("\n"+TAG+"Encoder turned CW")
            if state.mode == mode_dict[MODE_C]:  # "chgm"
                pass # mode_change(state)
            elif state.mode == mode_dict[MODE_I]:  # "index"
                increment_selected(state)
            elif state.mode == mode_dict[MODE_N]:  # "note"
                if state.selected_index != -1:
                    if my_debug:
                        print(TAG+f"{state.last_position} -> {cur_position}")
                    state.notes_lst[state.selected_index] += 1
            elif state.mode == mode_dict[MODE_M]:  # "midi_channel"
                state.midi_channel += 1
                state.midi_ch_chg_event = True
                if state.midi_channel > midi_channel_max:
                    state.midi_channel = midi_channel_min
                if my_debug:
                    print(f"new midi channel: {state.midi_channel}")
            elif state.mode == mode_dict[MODE_F]:  # "file"
                if state.selected_file is None:
                    state.selected_file = 0
                else:
                    state.selected_file += 1
                if my_debug:
                    print(TAG+f"state.selected_file= {state.selected_file}")
            elif state.mode == mode_dict[MODE_D]: # "fifths"
                fifths_change(state)
            elif state.mode == mode_dict[MODE_K]: # "note key Major or Minor
                key_change(state)
        elif cur_position < state.last_position:
            state.last_position = cur_position
            state.btn_event = True
            if my_debug:
                print("\n"+TAG+"Encoder turned CCW")
            if state.mode == mode_dict[MODE_C]:  # "chgm"
                pass # mode_change(state)
            elif state.mode == mode_dict[MODE_I]:  # "index"
                decrement_selected(state)
            elif state.mode == mode_dict[MODE_N]:  # "note"
                if state.selected_index != -1:
                    if my_debug:
                        print(TAG+f"{state.last_position} -> {cur_position}")
                    state.notes_lst[state.selected_index] -= 1
            elif state.mode == mode_dict[MODE_M]:  # "midi_channel"
                state.midi_channel -= 1
                state.midi_ch_chg_event = True
                if state.midi_channel < midi_channel_min:
                    state.midi_channel = midi_channel_max
                if my_debug:
                    print(f"new midi channel: {state.midi_channel}")
            elif state.mode == mode_dict[MODE_F]:  # "file"
                if state.selected_file is None:
                    state.selected_file = 0
                else:
                    state.selected_file -= 1
                    if state.selected_file < 0:
                        state.selected_file = 0
                if my_debug:
                    print(TAG+f"state.selected_file= {state.selected_file}")
            elif state.mode == mode_dict[MODE_D]: # "fifths"
                fifths_change(state)
            elif state.mode == mode_dict[MODE_K]: # "note key Major or Minor
                key_change(state)
        else:
            # same
            pass

        encoder_btn.update()

        if encoder_btn.fell:

            state.encoder_btn_cnt += 1
            tm_current = int(time.monotonic())
            tm_diff = tm_current - tm_start

            if state.encoder_btn_cnt > 1:
                if my_debug:
                    print(TAG+f"\ntm_start: {tm_start}. tm_trigger: {tm_trigger}, tm_diff: {tm_diff}")
                if tm_diff >= tm_trigger:
                    state.encoder_btn_cnt = 0
                    tm_start = tm_current
                    mode_change(state)
            #if state.mode == mode_dict[MODE_C]:  # "chgm"
            #    mode_change(state)
            else:
                state.btn_event = True
                state.enc_sw_cnt += 1
                if state.enc_sw_cnt > MODE_MAX:
                    state.enc_sw_cnt = MODE_MIN
                if my_debug:
                    print(TAG+f"len(mode_lst): {len(mode_lst)}. New enc_sw_cnt: {state.enc_sw_cnt}")

                #state.mode = "note" if state.mode == "index" else "index"
                state.mode = mode_dict[state.enc_sw_cnt]  # mode_lst[state.enc_sw_cnt]
                if my_debug:
                    print(TAG+"Encoder sw. pressed")
                    print(TAG+f"new mode:\n\"{state.mode}\"")

        # state.last_position = cur_position
        state.enc_sw_cnt = mode_rv_dict[state.mode]  # line-up the encoder switch count with that of the current state.mode
        if my_debug:
            print(TAG+f"mode_rv_dict[\"{state.mode}\"]= {mode_rv_dict[state.mode]}")
        await asyncio.sleep(0.05)


async def play_note(state, note, delay):
    TAG = tag_adj("play_note(): ")
    if state.midi_ch_chg_event:  # was: if note == 61 and midi_ch_chg_event
        state.midi_ch_chg_event = False  # Clear event flag
    if (note != 0):
        if not state.send_off:
            midi.send(NoteOff(note, 0))
            note_on = NoteOn(note, 127)
            #if my_debug:
            #    print(TAG+f"playing other channel? {note_on.channel}")
            midi.send(note_on, channel=state.midi_channel)
            await asyncio.sleep(delay)

            if state.send_off:
                midi.send(NoteOff(note, 0), channel=state.midi_channel)
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
def tag_adj(t):
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

def do_connect():
    global ip, s_ip, pool
    TAG = tag_adj("do_connect(): ")
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
        print(TAG+f"s_ip= {s_ip}. Resetting this \'{wifi.radio.hostname}\' device...")
        time.sleep(2)  # wait a bit to show the user the message
        #import microcontroller
        #microcontroller.reset()

def wifi_is_connected():
    return True if s_ip is not None and s_ip != '0.0.0.0' else False

def setup(state):
    TAG = tag_adj("setup(): ")

    if use_wifi:
        if not wifi_is_connected():
            if my_debug:
                print(TAG+f"Connecting WiFi to {os.getenv('CIRCUITPY_WIFI_SSID')}")
            do_connect()
        else:
            print(TAG+f"WiFi is connected to {os.getenv('CIRCUITPY_WIFI_SSID')}")

    use_warnings = True
    load_all_note_sets(state, use_warnings)

async def main():
    # state = State(saved_loops.LOOP1)
    test_state_json = []
    state = State()
    setup(state)
    await asyncio.gather(
        asyncio.create_task(blink_the_leds(state, delay=0.125)),
        asyncio.create_task(read_buttons(state)),
        asyncio.create_task(blink_selected(state)),
        asyncio.create_task(update_display(state, delay=0.125)),
        asyncio.create_task(read_encoder(state))
    )

asyncio.run(main())
