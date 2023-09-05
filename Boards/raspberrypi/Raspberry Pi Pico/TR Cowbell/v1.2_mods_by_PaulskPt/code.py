# Based on TR-Cowbell Hardware Test by @DJDevon3
# 2023/03/03 - Neradoc & DJDevon3
# Based on PicoStepSeq by @todbot Tod Kurt
# https://github.com/todbot/picostepseq/
# This file contains changes, additions by @PaulskPt (Github)
# Partly also based on TR_Cowbell_Sequencer_Software repo by @Foamyguy
# 2023-08-20
# More info about buttons and controls, see file: README_buttons_and_controls.md (work-in-progress)
# For list of changes see file: changes_log.md 
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
import os, gc
# Global flags
my_debug = False
# --- DISPLAY DRTIVER selection flags ---+
use_ssd1306 = False  #                   |
use_sh1107 = True  #                     |
# ---------------------------------------+
use_wifi = True
use_TAG = False

if use_wifi:
    import wifi
    import ipaddress
    import socketpool
    import adafruit_ntp
    import rtc
    pool = socketpool.SocketPool(wifi.radio)
    ntp = adafruit_ntp.NTP(pool, tz_offset=1)  # tz_offset utc+1
    rtc.RTC().datetime = ntp.datetime
else:
    wifi = None
    ipaddress = None
    socketpool = None
    pool = None
    ntp = None
    rtc = None

import json
import struct
import storage
from io import BytesIO
import msgpack
from adafruit_midi.note_off import NoteOff
from adafruit_midi.note_on import NoteOn
# PitchBend is a special MIDI message, with a range of 0 to 16383. 
# Since pitch can be bent up or down, the midpoint (no pitch bend) is 8192.
from adafruit_midi.pitch_bend import PitchBend

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
MODE_T = 7 # tempo (or BPM)
MODE_G = 8 # global flags change mode
MODE_MIN = MODE_I # Don't show MODE_C
MODE_MAX = MODE_G


# mode_lst = ["mode_change", "index", "note", "file", "midi_channel", "disp_fifths", "note_key", "tempo (bpm)", "glob_flag_change"]
mode_klst = [MODE_C, MODE_I, MODE_N, MODE_F, MODE_M, MODE_D, MODE_K,MODE_T, MODE_G]

mode_dict = {
    MODE_C : "mode_change",
    MODE_I : "index",
    MODE_N : "note",
    MODE_F : "file",
    MODE_M : "midi_channel",
    MODE_D : "fifths",   # Display as Fifths or 'Normal' number values
    MODE_K : "note_key",  # When displaying as Fifths, display in Key C Major or C Minor
    MODE_T : "tempo (bpm)",
    MODE_G : "glob_flag_change"  # For change of global flags: my_debug, use_TAG and use_wifi
    }

mode_short_dict = {
    MODE_C : "mchg",
    MODE_I : "indx",
    MODE_N : "note",
    MODE_F : "file",
    MODE_M : "midi",
    MODE_D : "fift",
    MODE_K : "nkey",
    MODE_T : "tmpo",
    MODE_G : "flag"
    }

mode_rv_dict = {
    "mode_change" : MODE_C,
    "index" : MODE_I,
    "note" : MODE_N,
    "file" : MODE_F,
    "midi_channel" : MODE_M,
    "fifths" : MODE_D,
    "note_key" : MODE_K,
    "tempo (bpm)" : MODE_T,
    "glob_flag_change" : MODE_G
    }

from midi_note_nrs import * # import the midi_notes_dict
# To check the import:
# print(f"MIDI_NOTE= {MIDI_NOTE}, MIDI_ORGAN= {MIDI_ORGAN}, MIDI_PIANO= {MIDI_PIANO}, MIDI_FREQ= {MIDI_FREQ}")




midi_channel_min = 1
midi_channel_max = 2
encoder = rotaryio.IncrementalEncoder(board.GP18, board.GP19)

encoder_btn_pin = digitalio.DigitalInOut(board.GP20)
encoder_btn_pin.direction = digitalio.Direction.INPUT
encoder_btn_pin.pull = digitalio.Pull.UP
encoder_btn = Debouncer(encoder_btn_pin)
encoder_dbl_btn = Button(encoder_btn_pin)

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
TEMPO_DELTA = 10
BPM = TEMPO / 60 / 16
pb_max = 16383 # bend up value
pb_default = 8192 # bend center value
pb_min = 0 # bend down value
pb_change_rate = 100 # interval for pitch bend, lower number is slower
pb_return_rate = 100 # interval for pitch bend release

class State:
    def __init__(self, saved_state_json=None):
        self.selected_index = -1
        self.notes_lst = [0] * 16
        self.latches = [False] * 16
        self.last_position = encoder.position
        self.mode = MODE_I
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
        self.enc_sw_cnt = MODE_I  # mode_klst[1] = index
        self.display_fifths = False # "Normal" (number values) display
        self.key_major = True  # If False, the key is Minor
        self.rtc_is_set = False
        self.ntp_datetime = None
        self.dt_str_usa = True
        self.tempo_default = 120
        self.tempo = self.tempo_default
        self.tempo_shown = self.tempo_default
        self.tempo_delta = 10
        self.bpm = self.tempo / 60 / 16  # 120 / 60 / 16 = 0.125
        self.tempo_reset = False


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
                if sn >= 21 and  sn < len(midi_notes_dict) and sn in midi_notes_dict.keys():  # 21 = A0
                    sn = midi_notes_dict[sn][MIDI_NOTE] 
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

                n = state.notes_lst[i] % 12 # index for notes_major_minor_dict
                idx = 60 + n # Value 60 represents the "Central C" or C4

                n2 = FIFTHS_NOTES_MAJOR if state.key_major else FIFTHS_NOTES_MINOR
                if idx in notes_major_minor_dict.keys():
                    sn = notes_major_minor_dict[idx][n2]
                else:
                    sn = state.notes_lst[i]
                    if sn == 60:
                        sn = notes_C_dict[sn]
                le = len(sn)
                if le > 7:
                    sn = sn[:7]  # was [:5]
                print("{:s} ".format(sn), end='')
                #else:
                #    print("{:>3d} ".format(state.notes_lst[i]), end='')
                if i == 7:
                    print()
            print("\n"+"-"*18)
        if state.mode == MODE_M:  # "midi_channel"
            print(TAG+f"midi channel: {state.midi_channel}")
        elif state.mode == MODE_T: # "tempo"
            if org_cnt > 0:
                s_bpm = "tempo:{:3d},dly:{:5.3f}".format(state.tempo_shown, float(round(state.bpm, 3)))
                print(TAG+f"{s_bpm}")
        else:
            if org_cnt > 0:
                print(TAG+f"selected idx: {state.selected_index+1}")

        if org_cnt == 0:
            nba1 = "No buttons active"
            nba2 = nba1 if lStart else nba1
            print(TAG+f"{nba2}")
        print(TAG+f"mode:{mode_short_dict[state.mode]}.NoteSet:{ns}", end = '')

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

def pr_loops(state):  # called from load_all_note_sets()
    s = "-"*16
    ln = "+----+----+"+s+"+"+s+"+"+s+"+"+s+"+"
    TAG = tag_adj("pr_loops(): ")
    print(ln)
    print("| id |sIdx| notes red      |     yellow     |      blue      |     white      |")
    print(ln)
    for i in state.saved_loops['loops']:
        s = "| {:2d} | {:2d} |".format(i['id'], i['selected_index'])
        print(TAG+f"{s}", end='')
        le = len(i['notes'])
        for j in range(le):
            if j > 0 and j % 4 == 0:
                print("|", end='')
            print("{:3d} ".format( i['notes'][j] ), end='')
        print("|", end='\n')
        print(ln)

def pr_dt(state, short, choice):
    TAG = tag_adj("pr_dt(): ")
    DT_DATE_L = 0
    DT_DATE_S = 1
    DT_TIME = 2
    DT_ALL  = 3

    if short is None:
        short = False

    if choice is None:
        choice2 = DT_ALL

    if choice == 0:
        choice2 = DT_DATE_L  # With weekday
    elif choice == 1:
        choice2 = DT_DATE_S  # Without weekday
    elif choice == 2:
        choice2 = DT_TIME
    elif choice == 3:
        choice2 = DT_ALL

    now = time.localtime()
    yy = now[0]
    mm = now[1]
    dd = now[2]
    hh = now[3]
    mi = now[4]
    ss = now[5]
    wd = now[6]
    yd = now[7]
    dst = now[8]

    dow = {0: 'Sunday',
           1: 'Monday',
           2: 'Tuesday',
           3: 'Wednesday',
           4: 'Thursday',
           5: 'Friday',
           6: 'Saturday'
           }

    swd = dow[wd][:3] if short else dow[wd]

    dt0 = "{:s}".format(swd)
    if my_debug:
        print(TAG+f"state.dt_str_usa: {state.dt_str_usa}")
    if state.dt_str_usa:
        if hh >= 12:
            hh -= 12
            ampm = "PM"
        else:
            ampm = "AM"

        if hh == 0:
            hh = 12

        dt1 = "{:d}/{:02d}/{:02d}".format(mm, dd, yy)
        dt2 = "{:02d}:{:02d}:{:02d} {:s}".format(hh, mi, ss, ampm)
    else:
        dt1 = "{:d}-{:02d}-{:02d}".format(yy, mm, dd)
        dt2 = "{:02d}:{:02d}:{:02d}".format(hh, mi, ss)


    if choice2 == DT_ALL:
        ret = dt0 + " " + dt1 + ", "+ dt2
    if choice2 == DT_DATE_L:
        ret = dt0 + " " + dt1
    if choice2 == DT_DATE_S:
        ret = dt0 + " " + dt1
    if choice == DT_TIME:
        ret = dt2

    if my_debug:
        print(TAG+f"{ret}")

    return ret

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
    state.mode = MODE_F # "file"
    ret = True
    f = None
    try:
        f = open(state.fn, "r")
        sl = json.loads(f.read()) # ["loops"]
        f.close()
        state.saved_loops = sl
        if my_debug:
            print(TAG+f"\nread fm file: {sl}")

        if "loops" not in sl.keys():
            sl["loops"] = []
        # Check for an empty note set.
        # If not found, add one
        le = len(sl['loops'])
        # print(TAG+f"sets: {sl['loops']}")
        set_nr = fnd_empty_loop(state)
        # print(f"set_nr = {set_nr}")
        if set_nr < 0:
            # No empty notes set found. We're going to add one
            ne = {"id": le, "selected_index": -1, "notes": [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0] }
            sl['loops'].insert(set_nr, ne)
        state.saved_loops = sl  # update
        if my_debug:
            # Show result
            print(TAG+f"state.saved_loops after adding empty note set: {state.saved_loops}")
        set_nr = fnd_empty_loop(state)  # Check again
        if set_nr > -1:
            state.selected_file = set_nr # Select empty note set found
        else:
            state.selected_file = len(state.saved_loops)-1 # Select last note set (0,0,0,...)
        state.selected_index = -1
        if use_warnings:
            if my_debug:
                print(TAG+state.fn)
                print(TAG+f"saved_loops: {state.saved_loops}\nloaded successfully")
            msg = [TAG, "note sets", "have been", "read from file", state.fn, "successfully"]
            pr_msg(state, msg)
            if my_debug:
                pr_loops(state)
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

    # All notes zero (to prevent a "hang" between switching key  )
    # Prevent a "hang" of the last send note when calling this load_note_set() function
    send_midi_panic()
    if dir_up is None:
        dir_up = True
    if state.selected_file is None:
        state.selected_file = -1
        state.selected_index = -1
    else:
        if dir_up:
            state.selected_file += 1
            if state.selected_file >= len(state.saved_loops['loops']):
                state.selected_file = 0 # wrap to first
        else:
            state.selected_file -= 1
            if state.selected_file < 0:
                state.selected_file = len(state.saved_loops['loops'])-1 # wrap to last
        if use_warnings:
            if my_debug:
                print(TAG+f"loading notes set nr: {state.selected_file+1} (from memory) successful")
            msg = [TAG, "loading:", "from", "notes set nr: "+str(state.selected_file+1)]
            pr_msg(state, msg)
        #print(TAG+f"loading: {state.selected_file}")
    state.load_state_obj(state.saved_loops['loops'][state.selected_file])
    state.mode = MODE_I # Change mode to "index"

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
    
def tempo_change(state, rl):
    TAG = tag_adj("tempo_change(): ")
    global TEMPO, TEMPO_DELTA, BPM
    # print(TAG+f"rl: {rl}, type(rl): {type(rl)}")
    state.tempo_shown = state.tempo_default
    if rl is not None and isinstance(rl, bool):
        # rl stands for right or left
        if state.tempo_reset:
            state.tempo = state.tempo_default
            state.bpm = state.tempo / 60 / 16
            state.tempo_shown = state.tempo 
        else:
            if rl:  # button right pressed. Increase tempo
                state.tempo -= state.tempo_delta # Beats Per Minute (approximation)
            else: # button left pressed. Decrease tempo
                state.tempo += state.tempo_delta

            state.bpm = state.tempo / 60 / 16
            
            if state.tempo < state.tempo_default:
                diff = state.tempo_default - state.tempo
                state.tempo_shown = state.tempo + (diff * 2)
            elif state.tempo > state.tempo_default:
                diff = state.tempo - state.tempo_default
                state.tempo_shown = state.tempo - (diff * 2)
            else:
                state.tempo_shown = state.tempo
                
        if state.tempo_reset:
            state.tempo_reset = False
        else:
            send_midi_panic()
            if rl:
                send_bend(pb_default, pb_min, state.tempo, 0) # was: pb_change_rate, 0)
            else:
                send_bend(pb_default, pb_max, state.tempo, 1)  # was: pb_change_rate, 1)
    
            # s = "Tempo {}creased (bpm delay {:s}creased to {:f})".format("in" if rl else "de", "de" if rl else "in", state.bpm)
            # print(TAG+f"{s}")
            #msg = [TAG, s]
            #pr_msg(state, msg)

def mode_change(state):
    TAG = tag_adj("mode_change(): ")
    state.btn_event = True
    m_idx = state.mode # was: MODE_I
    msg_shown = False
    scrolled = False
    nr_items = len(mode_short_dict)-1  # Number of mode items (except MODE_C (mchg) between heading and bottom lines
    scrn_lst = []
    scrn_lst.append(TAG+"\n|---- Mode -----|")
    for k, v in mode_short_dict.items():
        if k == MODE_C:  # don't show mode mchg 0
            continue
        scrn_lst.append("     "+v+" "+str(k)+"   ")
    scrn_lst.append(TAG+"| Exit=>Enc Btn |")
    le = len(scrn_lst)
    if my_debug:
        print(TAG+f"scrn_lst: {scrn_lst}")
        print(TAG+f"len(scrn_lst): {len(scrn_lst)}")
    n = -1
    show_hdg = True
    # The next loop displays a heading line and a bottom line
    # In between a scrolling list if the number of mode items
    # don't fit (max 7 mode items)
    while True:
        if not msg_shown:
            scrolled = False if (m_idx < (le - 3)) else True
            n_stop = (le-1) if scrolled else le-2
            n_start = n_stop - (nr_items-1)
            # print(TAG+f"\nnr_items: {nr_items}, n_start: {n_start}, n_stop: {n_stop}")
            print(scrn_lst[0])  # print heading line
            
            for i in range(n_start, n_stop): 
                t = (scrn_lst[i])
                t2 = t.rstrip()[-1] # extract the MODE value
                n = int(t2) if t2.isdigit() else -1  # 0-9 ? Yes, convert to integer else -1
                if n == m_idx:
                    s = "  >> "+scrn_lst[i][5:-3]+ " << "
                    print(s)  # print indexed mode item
                else:
                    print(scrn_lst[i]) # print normal, not indexed mode item
                
            print(scrn_lst[le-1], end='')  # print the bottom line

            msg_shown = True
        
        enc_pos = encoder.position
        # print(TAG+f"state.lp: {state.last_position}, enc pos: {enc_pos}") 
        if state.last_position < enc_pos:  # Rotary control turned CW
            state.last_position = enc_pos
            m_idx += 1
            if m_idx > MODE_MAX:
                m_idx = MODE_MIN  # roll to first mode item
            msg_shown = False
        elif enc_pos < state.last_position:   # Rotary control turned CCW
            state.last_position = enc_pos
            m_idx -= 1
            if m_idx < MODE_MIN:
                m_idx = MODE_MAX  # roll to last mode item
            msg_shown = False
        else:
            pass

        encoder_btn.update()

        if encoder_btn.fell:
            if my_debug:
                print(TAG+f"\nsaving mode as: {mode_dict[m_idx]}")
            state.enc_sw_cnt = m_idx
            state.mode = m_idx
            state.last_position = enc_pos
            break
        time.sleep(0.05)

def glob_flag_change(state):  # Global flag change
    global my_debug, use_TAG, use_wifi
    TAG = tag_adj("gl_flag_change(): ")
    old_pos = state.last_position
    old_enc_pos = state.enc_sw_cnt
    no_chg_flg = False
    if use_wifi:
        flags_dict = {0 : {'none' : no_chg_flg}, 1 : {'debug': my_debug}, 2: {'TAG': use_TAG}, 3: {'wifi' : use_wifi}, 4: {'dtUS' : state.dt_str_usa}}
    else:
        flags_dict = {0 : {'none' : no_chg_flg}, 1 : {'debug': my_debug}, 2: {'TAG': use_TAG}, 3: {'wifi' : use_wifi}}
    F_MIN = 0
    F_MAX = len(flags_dict)-1
    m_idx = F_MIN
    if use_wifi:
        flag_chg_dict = {'none': False, 'debug': False, 'TAG': False, 'wifi' : False, 'dtUS' : False}
        flag_idx_dict = { 0: 'none', 1: 'debug', 2: 'TAG', 3: 'wifi', 4: 'dtUS'}
    else:
        flag_chg_dict = {'none': False, 'debug': False, 'TAG': False, 'wifi' : False}
        flag_idx_dict = {0: 'none', 1: 'debug', 2: 'TAG', 3: 'wifi'}
    msg_shown = False
    while True:
        if not msg_shown:
            print("\n")
            # print(flags_dict.items())
            # print(list(flag_chg_dict.items()))
            print(TAG+"\n|---Glob Flag---|")

            for k in flags_dict.items():
                # print(f"k = {k}")
                d = k[1]
                for k2, v in d.items():
                    if m_idx == k[0]:
                        print(TAG+"  >> {:>5s} {:d} <<".format(k2, v))
                    else:
                        print(TAG+"     {:>5s} {:d}   ".format(k2, v ))
            print(TAG+"| Exit=>Enc Btn |", end= '\n')
            msg_shown = True

        enc_pos = encoder.position
        # print(TAG+f"state.lp: {state.last_position}, enc pos: {enc_pos}")

        if state.last_position < enc_pos:
            state.last_position = enc_pos
            m_idx += 1
            if m_idx > F_MAX:
                m_idx = F_MIN
            msg_shown = False
        elif enc_pos < state.last_position:
            state.last_position = enc_pos
            m_idx -= 1
            if m_idx < F_MIN:
                m_idx = F_MAX
            msg_shown = False
        else:
            pass

        encoder_btn.update()

        if encoder_btn.fell:
            state.btn_event = True  # So the pr_stat() screen will be shown after leaving this function

            if m_idx == 0:
                flags_dict[m_idx]['none'] = False if no_chg_flg == True else True
                flag_chg_dict['none'] = True
            elif m_idx == 1:
                flags_dict[m_idx]['debug'] = False if my_debug == True else True
                flag_chg_dict['debug'] = True
            elif m_idx == 2:
                flags_dict[m_idx]['TAG'] = False if use_TAG == True else True
                flag_chg_dict['TAG'] = True
            elif m_idx == 3:
                flags_dict[m_idx]['wifi'] = False if use_wifi == True else True
                flag_chg_dict['wifi'] = True

            if use_wifi:
                if m_idx == 4:
                    flags_dict[m_idx]['dtUS'] = False if state.dt_str_usa == True else True
                    flag_chg_dict['dtUS'] = True

                #if my_debug:
                #    print(TAG+f"\nsaving global flag as: {flags_dict[m_idx]}")

            break

        time.sleep(0.05)
    # Restore
    state.enc_sw_cnt = old_enc_pos
    state.mode = MODE_I # return to mode "index"
    state.last_position = old_pos
    for i in range(len(flags_dict)):
        if i == 0:
            if flag_chg_dict['none']:
                pass
        if i == 1:
            if flag_chg_dict['debug']:
                my_debug = flags_dict[i]['debug']
        if i == 2:
            if flag_chg_dict['TAG']:
                use_TAG = flags_dict[i]['TAG']
        if i == 3:
            if flag_chg_dict['wifi']:
                use_wifi = flags_dict[i]['wifi']
                # print(f"state of global wifi flag: {'True' if use_wifi else 'False'}")
                if use_wifi:
                    do_connect(state)
        if use_wifi:
            if i == 4:
                if flag_chg_dict['dtUS']:
                    # print(TAG+f"changing state.dt_str_USA to: {flags_dict[i]['dtUS']}")
                    state.dt_str_usa = flags_dict[i]['dtUS']
                    # check if it worked
                    msg = [TAG, 'NTP date:', pr_dt(state, True, 0), pr_dt(state, True, 2)]
                    pr_msg(state, msg)

    if my_debug:
        print(TAG+f"\ndebug: {my_debug}, TAG: {use_TAG}, wifi: {use_wifi}")

        
def id_change(lps, ne, s, le):  # Called from read_buttons()
    lps2 = lps
    if 'id' in ne.keys():
        ne['id'] = le  # update the id value
        lps2[s].insert(
        le,
        ne
        )
    return lps2

def fnd_empty_loop(state):
    TAG = tag_adj("fnd_empty_loop(): ")
    lps = state.saved_loops
    k1 = 'loops'
    k2 = 'notes'
    cnt = 0
    ret = -1
    id = 0
    id_found = []
    # print(TAG+f"type(lps)= {type(lps)}")
    if isinstance(lps, dict):
        le = len(lps['loops'])
        if my_debug:
            print(TAG)
        for i in range(le):
            en = lps['loops'][i]['notes']
            le2 = len(en)
            if my_debug:
                print(TAG+f"checking set: {en}")
            cnt = 0
            for j in range(le2):
                if en[j] == 0:
                    cnt += 1
                if cnt == 16:
                    id = lps['loops'][i]['id']
                    id_found.append(id)
                    if my_debug:
                        print(TAG+f"id of an empty notes set found: {id}")
        le = len(id_found)
        n = -1
        if le > 1:
            for i in range(le):
                if i == 0:
                    n = id_found[i]
                elif i > 0:
                    if id_found[i] < n:
                        n = id_found[i]  # take the lowest value
        else:
            n = id_found[0]
        if my_debug:
            print(TAG+f"zeros count= {cnt}. id\'s found= {id_found}")
            print(TAG+f"lowest id= {n}")
        ret = n
    # print(TAG+f"ret= {ret}")
    return ret
        
def send_bend(bend_start, bend_val, rate, bend_dir):
    TAG = tag_adj("send_bend(): ")
    b = bend_start
    if bend_dir == 0:
        while b > bend_val + rate:
            # print(b)
            b = b - rate
            midi.send(PitchBend(b))
            # midi_serial.send(PitchBend(b))
            
    if bend_dir == 1:
        while b < bend_val - rate:
            # print(b)
            b = b + rate
            midi.send(PitchBend(b))
            # midi_serial.send(PitchBend(b))

def wrt_to_fi(state):
    TAG = tag_adj("wrt_to_f(): ")
    # Initiate variables
    f = None
    f_lst = os.listdir("/")
    f_lst2 = None
    f_lst3 = None
    fn_bak = state.fn[:-4] + "bak"
    fn_bak2 = "/" + fn_bak
    fn_ren = "/"+state.fn   # e.g. "/saved_loops.json"
    # le1 = None
    le2 = None
    le3 = None
    lps = None
    msg = []
    ne = None
    nf = None
    s = None
    s2 = None
    sf = "file:"
    ssf = "successfully"
    tmp = None
    print()  # make a line space
    if fn_bak in f_lst:
        try:
            s = "removing " + sf
            os.remove(fn_bak2)  # remove the file "saved_loops.bak"
            time.sleep(0.5)
            if my_debug:
                print(TAG+f"{s} \"{fn_bak}\"")
            msg = [TAG, s, fn_bak]
            pr_msg(state, msg)
            f_lst2 = os.listdir("/")
            if not fn_bak in f_lst2:
                s = "removed " + ssf
                if my_debug:
                    print(TAG+f"{sf} \"{fn_bak}\" {s}")
                msg = [TAG, sf, fn_bak, s]
                pr_msg(state, msg)
            f_lst2 = None
        except OSError as e:
            print(TAG+f"OSError while trying to remove file \"{fn_bak}\". Error: {e}")
    else:
        nf = "not found"
        if my_debug:
            print(TAG+f"{sf} \"{fn_bak}\" {nf}")
        msg = [TAG, sf, fn_bak, nf]
        pr_msg(state, msg)
    if state.fn in f_lst:  # rename existing saved_loops.json to saved_loops.bak
        try:
            os.rename(fn_ren, fn_bak2)
            time.sleep(0.5)
            f_lst3 = os.listdir("/")
            if (fn_bak in f_lst3) and (not state.fn in f_lst3):
                s = "renamed to:"
                if my_debug:
                    print(TAG+f"{sf} \"{state.fn}\" {s} \"{fn_bak}\" {ssf}")
                msg = [TAG, sf, state.fn, s, fn_bak, ssf]
                pr_msg(state, msg)
            else:
                s = "failed rename file:"
                t = "to:"
                if my_debug:
                    print(TAG+f"{s} \"{state.fn}\" {t} \"{fn_bak}\"")
                msg = [TAG, s, state.fn, t, fn_bak]
                pr_msg(state, msg)
        except OSError as e:
            print(TAG+f"OSError while trying to rename file \"{state.fn}\" to \"{fn_bak}\". Error: {e}")
    try:
        # save the current file
        s = "saving"
        s2 = "note sets (loops)"
        if my_debug:
            print(TAG+f"{s} {s2} to: \"{state.fn}\"")
        msg = [TAG, s, s2, "to file:", state.fn]
        pr_msg(state, msg)
        lps = state.saved_loops
        if my_debug:
            print(TAG+f"loops of state.saved_loops= {lps}")
        s = 'loops'  # was: "loops"
        # le1 = len(lps[s])
        set_nr = fnd_empty_loop(state)
        if set_nr > -1:
            # set with all zeroes found
            ne = lps[s][set_nr] # copy the empty notes set (the "empty" set)
            if my_debug:
                print(TAG+f"lps[\'{s}\'][{set_nr}]= {ne}")
            gc.collect()
            # 1) Delete the empty notes set from lp (it is already copied to var "ne"
            # 2) Add the new notes set
            # 3) Add the empty notes set.
            # print(TAG+f"contents of lps b4 pop: {lps}. Length: {len(lps[s])}")
            lps[s].pop(set_nr)  # delete the empty notes list
            # print(TAG+f"contents of lps after pop: {lps}. Length: {len(lps[s])}")
        else:
            # Create an empty notes set
            ne = {"id": 4, "notes": [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0], "selected_index": -1}
        # Insert the current notes set (state.notes_lst)
        le2 = len(lps[s])
        if set_nr == -1:
            set_nr = le2  # Correct in case no zero notes set was found
        lps[s].insert(set_nr,
        {
        "notes": state.notes_lst,
        "id" : set_nr,
        "selected_index": state.selected_index
        })
        le3 = len(lps[s]) # calculate the new length
        if my_debug:
            print(TAG+f"contents of lps after removing zero loop at {set_nr}")
            print(TAG+f"and insert \'state.notes_lst\' at end: {lps}. new length: {le3}")

        if set_nr < 0:
            # Add the newly created empty notes set to the end
            try:
                lps = id_change(lps, ne, s, le3)
            except KeyError as e:
                print(TAG+f"Error: {e}")
        elif set_nr > -1:
            # Add the saved empty notes set to the end
            try:
                lps = id_change(lps, ne, s, le3)
            except KeyError as e:
                print(TAG+f"Error: {e}")
        if my_debug:
            print(TAG+f"contents of lps after insert at end: {lps}. new length: {len(lps[s])}")
        gc.collect()
        state.saved_loops = lps
        if my_debug:
            print(TAG+f"state.saved_loops after change: {state.saved_loops}]")
        lps = None
        # Write the changed saved loops to file on disk
        f = open(state.fn, "w")
        tmp = json.dumps(state.saved_loops)
        if my_debug:
            print(TAG+f"saving to file: \"{tmp}\"")
        f.write(tmp)
        f.close()
        gc.collect()
        if not state.write_msg_shown:
            if my_debug:
                print(TAG+"save complete")
            msg = [TAG, "note sets (loops)", "saved to file:", state.fn, "successfully"]
            pr_msg(state, msg)
            state.write_msg_shown = True
    except OSError as e:
        print(TAG+f"OSError while trying to save note sets to file. Error: {e}")
    # Cleanup
    f = None
    f_lst = None
    f_lst2 = None
    f_lst3 = None
    fn_bak = None
    fn_bak2 = None
    fn_ren = None
    #
    le2 = None
    le3 = None
    lps = None
    msg = []
    ne = None
    nf = None
    s = None
    s2 = None
    sf = None
    ssf = None
    tmp = None

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

        if state.mode != MODE_M: # "midi_channel". Only change midi channel with Rotary Encoder control
            if state.btn_event == False:  # only if no other event is being processed

                if up_btn.fell or down_btn.fell:
                    if up_btn.fell:
                        ud = True
                    elif down_btn.fell:
                        ud = False

                    state.btn_event = True
                    btns_active = count_btns_active(state)
                    inc_dec = "{:s} note".format("increasing" if ud else "decreasing")
                    if my_debug:
                        sud = " 1 (UP)" if ud else "3 (DOWN)"
                        ud_pr = up_btn.pressed if ud else down_btn.pressed
                        print(TAG+f"BUTTON {sud} is pressed: {ud_pr}.")

                    if state.mode == MODE_N: # "note"
                        if my_debug:
                            print(TAG+f"{inc_dec}")
                            print(TAG+f"mode: \"{state.mode}\".")
                        if btns_active>0:
                            if ud:
                                state.notes_lst[state.selected_index] += 1
                            else:
                                state.notes_lst[state.selected_index] -= 1
                            # print(f"state.notes_lst[{state.selected_index}]= {state.notes_lst[state.selected_index]}")

                    elif state.mode in [MODE_I, MODE_F]:
                        dir_up = True if ud else False
                        use_warnings = True
                        load_note_set(state, dir_up, use_warnings)

                if right_btn.fell or left_btn.fell:
                    if my_debug:
                        print(TAG+f"\nstate.mode: {mode_dict[state.mode]}")
                    if right_btn.fell:
                        rl = True
                    elif left_btn.fell:
                        rl = False
                    state.btn_event = True
                    btns_active = count_btns_active(state)
                    inc_dec = "{:s} note".format("increasing" if rl else "decreasing")
                    inc_dec = inc_dec if state.mode == MODE_N and btns_active >0 else ""

                    if my_debug:
                        srl = " 2 (RIGHT)" if ud else "4 (LEFT)"
                        rl_pr = right_btn.pressed if rl else left_btn.pressed
                        print(TAG+f"BUTTON {srl} is pressed: {rl_pr}.")

                    if state.mode in [MODE_I, MODE_N]:  # "index" or "note"
                        if btns_active >0:
                            if rl:
                                increment_selected(state)
                            else:
                                decrement_selected(state)
                    elif state.mode == MODE_F:  # "file"
                        if my_debug:
                            srl = " 2 (RIGHT)" if ud else "4 (LEFT)"
                            print(TAG+f"BUTTON {srl} doing nothing")
                    elif state.mode ==  MODE_T:  # "tempo change"
                        if btns_active >0:
                            tempo_change(state, rl)

                    # state.send_off = not state.send_off
                    # print(f"send off: {state.send_off}")

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
                    if state.mode  in [MODE_I, MODE_N]:
                        state.mode = MODE_F # Change mode to "file"
                    elif state.mode == MODE_F: # "file"
                        if ro_state == "Writeable":
                            wrt_to_fi(state)
                        else:
                            if my_debug:
                                print("Filesystem is readonly. Cannot save note sets to file")
                            msg = [TAG, "Filesystem is", "readonly.", "Unable to save", "note sets","to file:", state.fn]
                            pr_msg(state, msg)
                    elif state.mode == MODE_T:  # "tempo". Reset tempo to default
                        state.tempo_reset = True
                        tempo_change(state, rl)
        # slow down the loop a little bit, can be adjusted
        await asyncio.sleep(0.15)  # Was: 0.05 or BPM -- has to be longer to avoid double hit

def reset_encoder(state):
    global encoder
    # encoder = rotaryio.IncrementalEncoder(board.GP18, board.GP19)
    
    encoder.position = 0  # This works OK!
    state.last_position = 0 # Also reset the last position.

async def read_encoder(state):
    TAG = tag_adj("read_encoder(): ")
    # print("\n"+TAG+f"mode: {mode_dict[state.mode]}")
    pr_state(state)


    state.enc_sw_cnt = state.mode  # line-up the encoder switch count with that of the current state.mode

    if my_debug:
            print(TAG+f"mode_rv_dict[\"{mode_dict[state.mode]}\"]= {mode_rv_dict[mode_dict[state.mode]]}")

    tm_interval = 10
    tm_start = int(time.monotonic()) # Start time keeping track of last encoder rotary control action
    
    while True:

        # ---------------------------------------------------------------------------------------------------
        #  Read the encoder button (switch)
        # ---------------------------------------------------------------------------------------------------

        if state.mode == MODE_G:
            glob_flag_change(state)

        encoder_dbl_btn.update()

        if encoder_dbl_btn.short_count >=2 :  # We have an encoder button double press
            send_midi_panic()
            mode_change(state)

            #if state.mode == mode_dict[MODE_C]:  # "chgm"
            #    mode_change(state)
        else:
            encoder_btn.update()
            if encoder_btn.fell:
                state.btn_event = True
                state.enc_sw_cnt += 1
                if state.enc_sw_cnt > MODE_MAX-1:  # Do not allow to go to MODE_G (glob_flag_change) from this location (only from mode_change())
                    state.enc_sw_cnt = MODE_MIN
                if my_debug:
                    print(TAG+f"len(mode_klst): {len(mode_klst)}. New enc_sw_cnt: {state.enc_sw_cnt}")
                #state.mode = "note" if state.mode == "index" else "index"
                state.mode = state.enc_sw_cnt  # mode_lst[state.enc_sw_cnt]
                if my_debug:
                    # print(TAG+f"mode_dict[MODE_G]: {mode_dict[MODE_G]}, state.mode: {state.mode}")
                    print(TAG+"Encoder sw. pressed")
                    print(TAG+f"new mode:\n\"{mode_dict[state.mode]}\"")

        # state.last_position = cur_position
        state.enc_sw_cnt = state.mode  # line-up the encoder switch count with that of the current state.mode
        if my_debug:
            print(TAG+f"mode_rv_dict[\"{mode_dict[state.mode]}\"]= {mode_rv_dict[mode_dict[state.mode]]}")
        await asyncio.sleep(0.02)  # was 0.05

        # ---------------------------------------------------------------------------------------------------
        #  Read the encoder rotary control
        # ---------------------------------------------------------------------------------------------------

        cur_position = encoder.position  # read the rotary encoder control position
        tm_curr = int(time.monotonic())
        tm_elapsed = tm_curr - tm_start
        if my_debug:
            print(TAG+f"tm_elapsed = {tm_elapsed}")
        if (tm_elapsed >= tm_interval) or (cur_position < -127 or cur_position > 127):
            if (tm_elapsed >= tm_interval):
                tm_start = tm_curr  # reset the encoder rotary control value to 0 when passing tm_elapsed
            #                         we want to prevent that the tone value will be changed too much 
            #                         at each couple of turns of the encoder rotary control
            #                         or reset the encoder rotary control value when passing limits for note values
            reset_encoder(state)
            cur_position = encoder.position # re-read the encoder rotary control position
            if my_debug:
                print(TAG+f"encoder_btn re-initiated. cur_position= {cur_position}")
        if state.last_position < cur_position:   # turned CW
            state.last_position = cur_position
            state.btn_event = True
            if my_debug:
                print("\n"+TAG+"Encoder turned CW")
            if state.mode == MODE_C:  # "chgm"
                pass # mode_change(state)
            elif state.mode == MODE_I:  # "index"
                increment_selected(state)
            elif state.mode == MODE_N:  # "note"
                if state.selected_index != -1:
                    n = state.notes_lst[state.selected_index] + cur_position
                    if not my_debug:
                        print(TAG+f"\nstate.notes_lst[state.selected_index] = {state.notes_lst[state.selected_index]}")
                        print(TAG+f"n= {n}, Encoder rotary control last pos: {state.last_position} -> curr pos: {cur_position}")
                    if n >= 0 and n < len(midi_notes_dict):
                        state.notes_lst[state.selected_index] += cur_position # make big note value changes possible
                    else:
                        n = state.notes_lst[state.selected_index] + 1
                        if n >= 0 and n < len(midi_notes_dict):
                            state.notes_lst[state.selected_index] += 1
            elif state.mode == MODE_M:  # "midi_channel"
                state.midi_channel += 1
                state.midi_ch_chg_event = True
                if state.midi_channel > midi_channel_max:
                    state.midi_channel = midi_channel_min
                if my_debug:
                    print(f"new midi channel: {state.midi_channel}")
                s = "new midi channel {:d}".format(state.midi_channel)
                msg = [TAG, s]
                pr_msg(state, msg)
                s = None
            elif state.mode == MODE_F:  # "file"
                if state.selected_file is None:
                    state.selected_file = 0
                else:
                    state.selected_file += 1
                if my_debug:
                    print(TAG+f"state.selected_file= {state.selected_file}")
            elif state.mode == MODE_D: # "fifths"
                fifths_change(state)
            elif state.mode == MODE_K: # "note key Major or Minor
                key_change(state)
            #elif state.mode == MODE_G: # "global flag change
            #    glob_flag_change(state)
        elif cur_position < state.last_position:   # turned CCW
            state.last_position = cur_position
            state.btn_event = True
            if my_debug:
                print("\n"+TAG+"Encoder turned CCW")
            if state.mode == MODE_C:  # "chgm"
                pass # mode_change(state)
            elif state.mode == MODE_I:  # "index"
                decrement_selected(state)
            elif state.mode == MODE_N:  # "note"
                if state.selected_index != -1:
                    if cur_position < 0:
                        n = state.notes_lst[state.selected_index] + cur_position  # add a negative value
                    else:
                        n = state.notes_lst[state.selected_index] - cur_position  # subtract a positive value
                    if not my_debug:
                        print(TAG+f"\nstate.notes_lst[state.selected_index] = {state.notes_lst[state.selected_index]}")
                        print(TAG+f"n= {n}, Encoder rotary control last pos: {state.last_position} -> curr pos: {cur_position}")
                    if n >= 0 and n < len(midi_notes_dict):
                        if cur_position < 0:
                            state.notes_lst[state.selected_index] += cur_position  # add a negative value. Make big note value changes possible
                        else:
                            state.notes_lst[state.selected_index] -= cur_position  # subtract a positive value. Make big note value changes possible
                    else:
                        n = state.notes_lst[state.selected_index] - 1
                        if n >= 0 and n < len(midi_notes_dict):
                            state.notes_lst[state.selected_index] -= 1
            elif state.mode == MODE_M:  # "midi_channel"
                state.midi_channel -= 1
                state.midi_ch_chg_event = True
                if state.midi_channel < midi_channel_min:
                    state.midi_channel = midi_channel_max
                if my_debug:
                    print(f"new midi channel: {state.midi_channel}")
                s = "new midi channel {:d}".format(state.midi_channel)
                msg = [TAG, s]
                pr_msg(state, msg)
            elif state.mode == MODE_F:  # "file"
                if state.selected_file is None:
                    state.selected_file = 0
                else:
                    state.selected_file -= 1
                    if state.selected_file < 0:
                        state.selected_file = 0
                if my_debug:
                    print(TAG+f"state.selected_file= {state.selected_file}")
            elif state.mode == MODE_D: # "fifths"
                fifths_change(state)
            elif state.mode == MODE_K: # "note key Major or Minor
                key_change(state)
            #elif state.mode == MODE_G: # "global flag change
            #    glob_flag_change(state)
        else:
            # same
            pass

async def play_note(state, note, delay):
    TAG = tag_adj("play_note(): ")
    try:
        if state.midi_ch_chg_event:  # was: if note == 61 and midi_ch_chg_event
            state.midi_ch_chg_event = False  # Clear event flag
        if (note > 0 and note < 128 ):
            if note >= 21 and  note < len(midi_notes_dict) and note in midi_notes_dict.keys():  # 21 = A0
                sn = midi_notes_dict[note][MIDI_NOTE]
            else:
                sn = ""
            if my_debug:
                print(TAG+f"\nnote to play: {note} = {sn}")
            if not state.send_off:
                midi.send(NoteOff(note, 0))
                note_on = NoteOn(note, 127)
                #if my_debug:
                #    print(TAG+f"playing other channel? {note_on.channel}")
                midi.send(note_on, channel=state.midi_channel)
                await asyncio.sleep(state.bpm)  # was: delay)
                if state.send_off:
                    midi.send(NoteOff(note, 0), channel=state.midi_channel)
            else:
                note_on = NoteOn(note, 127)
                midi.send(note_on)
                await asyncio.sleep(state.bpm)  # was: delay)
                if state.send_off:
                    midi.send(NoteOff(note, 0))
    except ValueError as e:
        print(TAG+f"Error {e} occurred when note value was: {note}")

# Added after suggestion of @DJDevon3
# Function found in: https://learn.adafruit.com/midi-cyber-cat-keyboard/code-the-cyber-cat-midi-keyboard
def send_midi_panic():
    for x in range(128):
        midi.send(NoteOff(x, 0))
        midi.send(NoteOff(x, 0))

async def update_display(state, delay=0.125):
    while True:
        b = BytesIO()
        msgpack.pack({"notes": state.notes_lst,
                      "selected_index": state.selected_index,
                      "mode": state.mode}, b)#  "mode": mode_rv_dict[state.mode]}, b)
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

def do_connect(state):
    global ip, s_ip, pool, ntp, rtc
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
        except NameError as e:
            import wifi
            import ipaddress
            import socketpool
            import adafruit_ntp

        if pool is None:
            pool = socketpool.SocketPool(wifi.radio)
        my_tz_offset = 1  # utc+1
        if ntp is None:
            ntp = adafruit_ntp.NTP(pool, tz_offset=my_tz_offset)
        state.ntp_datetime = ntp.datetime
        if rtc is None:
            rtc.RTC().datetime = ntp.datetime  # Set the built-in RTC
            state.rtc_is_set = True
        dt = pr_dt(state, True, 3)  # Weekday, Date and Time

        dc_ip = wifi.radio.ipv4_address
        cnt += 1
        if cnt > timeout_cnt:
            print(TAG+"WiFi connection timed-out")
            break
        time.sleep(1)
    if dc_ip:
        ip = dc_ip
        s_ip = str(ip)
    if s_ip is not None and s_ip != '0.0.0.0':
        if not my_debug:
            # print(TAG+"s_ip= \'{}\'".format(s_ip))
            print(TAG+f"connected to {os.getenv('CIRCUITPY_WIFI_SSID')}")
            print(TAG+"IP address is", ip)
            msg = [TAG, "connected to", os.getenv('CIRCUITPY_WIFI_SSID'), "IP Address is:", ip,
                   'NTP date:', pr_dt(state, True, 0), pr_dt(state, True, 2)]
            pr_msg(state, msg)
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

def dt_update(state):
    state.ntp_datetime = ntp.datetime
    state.rtc_is_set = True

def wifi_is_connected():
    return True if s_ip is not None and s_ip != '0.0.0.0' else False

def setup(state):
    global ntp
    TAG = tag_adj("setup(): ")
    send_midi_panic() # switch off any notes
    if use_wifi:
        if not wifi_is_connected():
            if my_debug:
                print(TAG+f"Connecting WiFi to {os.getenv('CIRCUITPY_WIFI_SSID')}")
            do_connect(state)
        else:
            print(TAG+f"WiFi is connected to {os.getenv('CIRCUITPY_WIFI_SSID')}")

        dt_update(state)

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
