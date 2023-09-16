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
MODE_K = 5 # key of the notes: Major or Minor
MODE_T = 6 # tempo (or BPM)
MODE_G = 7 # global flags change mode
MODE_MIN = MODE_I # Don't show MODE_C
MODE_MAX = MODE_G

mode_klst = [MODE_C, MODE_I, MODE_N, MODE_F, MODE_M, MODE_K,MODE_T, MODE_G]

mode_dict = {
    MODE_C : "mode_change",
    MODE_I : "index",
    MODE_N : "note",
    MODE_F : "file",
    MODE_M : "midi_channel",
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
    "note_key" : MODE_K,
    "tempo (bpm)" : MODE_T,
    "glob_flag_change" : MODE_G
    }

from midi_note_nrs import * # import the octaves_major_lst, octaves_dict

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
pb_max = 16383 # bend up value
pb_default = 8192 # bend center value
pb_min = 0 # bend down value
pb_change_rate = 100 # interval for pitch bend, lower number is slower
pb_return_rate = 100 # interval for pitch bend release

class State:
    def __init__(self, saved_state_json=None):
        self.selected_index = -1
        self.notes_lst = [0] * 16
        self.notes_txt_lst = ["0"] * 16  # text equivalent of self.notes_list
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
        self.key_minor = False  # If True, the key is Minor
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
    latches_cnt = 0
    for i in range(16):
        if state.latches[i]:
            latches_cnt += 1
    if my_debug:
        if latches_cnt < 2:
            ltch = "latch"
        else:
            ltch = "latches"
        print(f"\ncount_btns_active(): {latches_cnt} button {ltch} active")
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
    extr_midi_notes(state)
    gc.collect()
    if state.selected_file is None:
        ns = "?"
    else:
        ns = state.selected_file+1
    if state.btn_event or lStart:
        org_cnt = count_btns_active(state)
        if org_cnt == 0:
            my_lst = state.notes_lst
            if len(my_lst) == 0:
                my_lst = [0] * 16
                cnt = len(my_lst)
        btn = "button" if org_cnt in [0, 1] else "buttons"
        print(TAG+"\n{:2d} {:s} active".format(org_cnt, btn))
        print("-"*18)
        grp = 0
        for i in range(len(state.notes_txt_lst)):
            if not state.key_minor:
                if i % 4 == 0:
                    print("{:2d} ".format(i+1), end='')
            sn2 = state.notes_txt_lst[i][:3]
            gc.collect()
            if i == state.selected_index:
                print(">{:>2s}<".format(sn2), end='')
            else:
                print("{:>3s} ".format(sn2), end='')

            if i in [3, 7, 11]:
                print()
        print("\n"+"-"*18)

        if state.mode == MODE_M:
            print(TAG+f"midi channel: {state.midi_channel}")
        elif state.mode == MODE_T:
            if org_cnt > 0:
                s_bpm = "tempo:{:3d},dly:{:5.3f}".format(state.tempo_shown, float(round(state.bpm, 3)))
                print(TAG+f"{s_bpm}")
        else:
            if org_cnt > 0:
                print(TAG+f"selected note: {state.selected_index+1}")

        if org_cnt == 0:
            nba1 = "No buttons active"
            nba2 = nba1 if lStart else nba1
            print(TAG+f"{nba2}")
        print(TAG+f"mode:{mode_short_dict[state.mode]}.NoteSet:{ns}", end = '')

        if lStart: lStart = False
        clr_events(state)
        if state.longpress_event:
            state.longpress_event = False

def pr_msg(msg_lst=None, delay=3):
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
            for _ in range((max_lines-le)-1):
                print()
        time.sleep(delay)

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
    # yd = now[7]
    # dst = now[8]

    dow = {
           0: 'Monday',
           1: 'Tuesday',
           2: 'Wednesday',
           3: 'Thursday',
           4: 'Friday',
           5: 'Saturday',
           6: 'Sunday',
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

        for (x, y) in led_pins:
            if not get_latch(x, y, state):
                led_pins_per_chip[x][y].value = True
                await asyncio.sleep(0.001)
                led_pins_per_chip[x][y].value = False
                await asyncio.sleep(delay)
            else:
                led_pins_per_chip[x][y].value = False
                idx = x * 8 + y
                await play_note(state, idx, delay)
                led_pins_per_chip[x][y].value = True
        pr_state(state)
        gc.collect()

async def blink_selected(state, delay=0.05):
    while True:
        if state.selected_index >= 0:
            _selected_chip_and_index = index_to_chip_and_index(state.selected_index)
            if state.notes_lst[state.selected_index] is not None:
                led_pins_per_chip[_selected_chip_and_index[0]][_selected_chip_and_index[1]].value = False
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
    state.mode = MODE_F
    ret = True
    f = None
    nr_note_sets_removed = 0
    ns = "note sets"
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
        # Max 10 note lists
        nr_note_sets_removed = 0
        while True:
            le = len(sl['loops'])
            if le > 9:
                del sl['loops'][le-1]
                nr_note_sets_removed += 1
            else:
                break
        set_nr = fnd_empty_loop(state)
        if set_nr < 0:
            ne = {"id": le, "selected_index": -1, "notes": [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0] }
            sl['loops'].insert(set_nr, ne)
        state.saved_loops = sl  # update
        if my_debug:
            # Show result
            print(TAG+f"state.saved_loops after adding empty note set: {state.saved_loops}")
        set_nr = fnd_empty_loop(state)  # Check again
        if set_nr > -1:
            state.selected_file = set_nr
        else:
            state.selected_file = len(state.saved_loops)-1
        state.selected_index = -1
        if use_warnings:
            if my_debug:
                print(TAG+state.fn)
                print(TAG+f"saved_loops: {state.saved_loops}\nloaded successfully")
            msg = [TAG, ns, "have been", "read from file", state.fn, "successfully"]
            if nr_note_sets_removed > 0:
                s = "nr (ultimate) "+ns+" not loaded: {:d}".format(nr_note_sets_removed)
                msg.append(s)
                msg.append("only 10 "+ns+" can be loaded")
            pr_msg(msg)

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
                pr_msg(msg)
            return

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
            s = "notes set nr: "
            if my_debug:
                print(TAG+f"\nloading {s}{state.selected_file+1} (from memory) successful")
            msg = [TAG, "loading:", "from", s+str(state.selected_file+1)]
            pr_msg(msg)
    state.load_state_obj(state.saved_loops['loops'][state.selected_file])
    state.mode = MODE_I

def key_change(state):
    TAG = tag_adj("key_changer(): ")
    msg_shown = False
    old_key = state.key_minor
    reset_encoder(state)
    while True:
        if not msg_shown:
            clr_scrn()
            s1 = "The key "
            s2 = "of the notes: {:s}".format("Minor" if state.key_minor else "Major")
            msg = [TAG, s1, s2," ","Turn encoder control to change"," ","Exit=>Enc Btn"]
            pr_msg(msg, 1)
            msg_shown = True

        cur_position = encoder.position
        if state.last_position != cur_position:  
            state.last_position = cur_position
            if state.key_minor:
                state.key_minor = False
            else:
                state.key_minor = True
            reset_encoder(state)
            msg_shown = False
        
        encoder_btn.update()
        time.sleep(0.05)
        if encoder_btn.fell:
            break
    if old_key != state.key_minor:
        extr_midi_notes(state) # reread
    state.mode = MODE_I

def tempo_change(state, rl):
    TAG = tag_adj("tempo_change(): ")
    diff = None
    tempo_old = state.tempo
    state.tempo_shown = state.tempo_default
    if rl is not None and isinstance(rl, bool):
        # rl stands for right or left
        if state.tempo_reset:
            state.tempo = state.tempo_default
            state.bpm = state.tempo / 60 / 16
            state.tempo_shown = state.tempo
        else:
            if rl:  # Incr tempo
                state.tempo -= state.tempo_delta # Beats Per Minute (approximation)
            else: # Decr tempo
                state.tempo += state.tempo_delta

            state.bpm = state.tempo / 60 / 16
            if my_debug:
                print(TAG+f"tempo old: {tempo_old}. Tempo new: {state.tempo}")
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
                send_bend(pb_default, pb_min, state.tempo, 0)
            else:
                send_bend(pb_default, pb_max, state.tempo, 1)
    gc.collect()

def mode_change(state):
    TAG = tag_adj("mode_change(): ")
    i = None
    le = None
    k = None
    m_idx = state.mode # was: MODE_I
    msg_shown = False
    n = None
    n_start = None
    n_stop = None
    nr_items = len(mode_short_dict)-1  # Number of mode items (except MODE_C (mchg) between heading and bottom lines
    scrn_lst = []
    scrn_lst.append(TAG+"\n|---- Mode -----|")
    scrolled = False
    s = None
    t = None
    t2 = None
    v = None

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
            print(scrn_lst[0])

            for i in range(n_start, n_stop):
                t = (scrn_lst[i])
                t2 = t.rstrip()[-1]
                n = int(t2) if t2.isdigit() else -1  # 0-9 ?
                if n == m_idx:
                    s = "  >> "+scrn_lst[i][5:-3]+ " << "
                    print(s)
                else:
                    print(scrn_lst[i])
            print(scrn_lst[le-1], end='')
            msg_shown = True
        enc_pos = encoder.position
        if state.last_position < enc_pos:  # CW
            state.last_position = enc_pos
            m_idx += 1
            if m_idx > MODE_MAX:
                m_idx = MODE_MIN
            msg_shown = False
        elif enc_pos < state.last_position:   # CCW
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
            state.mode = m_idx
            state.last_position = enc_pos
            break
        time.sleep(0.05)
    gc.collect()

def glob_flag_change(state):  # Global flag change
    global my_debug, use_TAG, use_wifi
    TAG = tag_adj("gl_flag_change(): ")
    d = None
    enc_pos = None
    flags_dict = None
    flag_chg_dict = None
    F_MIN = None
    F_MAX = None
    i = None
    k = None
    k2 = None
    m_idx = None
    msg = None
    msg_shown = None
    no_chg_flg = False
    old_pos = state.last_position
    old_enc_pos = state.enc_sw_cnt
    v = None

    flags_dict = {0 : {'none' : no_chg_flg}, 1 : {'debug': my_debug}, 2: {'TAG': use_TAG}, 3: {'wifi' : use_wifi}}
    le = len(flags_dict)
    if use_wifi:
        flags_dict[le] = {'dtUS' : state.dt_str_usa} # add a key and item
    F_MIN = 0
    F_MAX = len(flags_dict)-1
    m_idx = F_MIN
    flag_chg_dict = {'none': False, 'debug': False, 'TAG': False, 'wifi' : False}
    if use_wifi:
        flag_chg_dict['dtUS'] = False

    msg_shown = False
    while True:
        if not msg_shown:
            print("\n")
            print(TAG+"\n|---Glob Flag---|")

            for k in flags_dict.items():
                d = k[1]
                for k2, v in d.items():
                    if m_idx == k[0]:
                        print(TAG+"  >> {:>5s} {:d} <<".format(k2, v))
                    else:
                        print(TAG+"     {:>5s} {:d}   ".format(k2, v ))
            print(TAG+"| Exit=>Enc Btn |", end= '\n')
            msg_shown = True

        enc_pos = encoder.position

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
            state.btn_event = True

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
            break
        time.sleep(0.05)
    # Restore
    state.enc_sw_cnt = old_enc_pos
    state.mode = MODE_I
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
                if use_wifi:
                    do_connect(state)
        if use_wifi:
            if i == 4:
                if flag_chg_dict['dtUS']:
                    state.dt_str_usa = flags_dict[i]['dtUS']
                    # check if it worked
                    msg = [TAG, 'NTP date:', pr_dt(state, True, 0), pr_dt(state, True, 2)]
                    pr_msg(msg)

    if my_debug:
        print(TAG+f"\ndebug: {my_debug}, TAG: {use_TAG}, wifi: {use_wifi}")
    gc.collect()

def id_change(lps, ne, s, le):  # Called from read_buttons()
    lps2 = lps
    if 'id' in ne.keys():
        ne['id'] = le
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
                        n = id_found[i]
        else:
            n = id_found[0]
        if my_debug:
            print(TAG+f"zeros count= {cnt}. id\'s found= {id_found}")
            print(TAG+f"lowest id= {n}")
        ret = n
    gc.collect()
    return ret

def send_bend(bend_start, bend_val, rate, bend_dir):
    TAG = tag_adj("send_bend(): ")
    b = bend_start
    if bend_dir == 0:
        while b > bend_val + rate:
            b = b - rate
            midi.send(PitchBend(b))

    if bend_dir == 1:
        while b < bend_val - rate:
            b = b + rate
            midi.send(PitchBend(b))

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
            pr_msg(msg)
            f_lst2 = os.listdir("/")
            if not fn_bak in f_lst2:
                s = "removed " + ssf
                if my_debug:
                    print(TAG+f"{sf} \"{fn_bak}\" {s}")
                msg = [TAG, sf, fn_bak, s]
                pr_msg(msg)
            f_lst2 = None
        except OSError as e:
            print(TAG+f"OSError while trying to remove file \"{fn_bak}\". Error: {e}")
    else:
        nf = "not found"
        if my_debug:
            print(TAG+f"{sf} \"{fn_bak}\" {nf}")
        msg = [TAG, sf, fn_bak, nf]
        pr_msg(msg)
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
                pr_msg(msg)
            else:
                s = "failed rename file:"
                t = "to:"
                if my_debug:
                    print(TAG+f"{s} \"{state.fn}\" {t} \"{fn_bak}\"")
                msg = [TAG, s, state.fn, t, fn_bak]
                pr_msg(msg)
        except OSError as e:
            print(TAG+f"OSError while trying to rename file \"{state.fn}\" to \"{fn_bak}\". Error: {e}")
    try:
        # save the current file
        s = "saving"
        s2 = "note sets (loops)"
        if my_debug:
            print(TAG+f"{s} {s2} to: \"{state.fn}\"")
        msg = [TAG, s, s2, "to file:", state.fn]
        pr_msg(msg)
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
            lps[s].pop(set_nr)  # delete the empty notes list
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
            pr_msg(msg)
            state.write_msg_shown = True
    except OSError as e:
        print(TAG+f"OSError while trying to save note sets to file. Error: {e}")
    # Cleanup
    gc.collect()

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
            gc.collect()
            await asyncio.sleep(0)

        # d-pad
        up_btn.update()
        down_btn.update()
        right_btn.update()
        left_btn.update()
        middle_btn.update()

        if state.mode != MODE_M:
            if state.btn_event == False:

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
                    elif state.mode in [MODE_I, MODE_F]:
                        dir_up = True if ud else False
                        use_warnings = True
                        load_note_set(state, dir_up, use_warnings)
                        extr_midi_notes(state) # reload

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
                    elif state.mode ==  MODE_T:
                        if btns_active >0:
                            tempo_change(state, rl)
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
                        state.mode = MODE_F
                    elif state.mode == MODE_F:
                        send_midi_panic()
                        if ro_state == "Writeable":
                            wrt_to_fi(state)
                        else:
                            if my_debug:
                                print("Filesystem is readonly. Cannot save note sets to file")
                            msg = [TAG, "Filesystem is", "readonly.", "Unable to save", "note sets","to file:", state.fn]
                            pr_msg(msg)
                    elif state.mode == MODE_T:
                        state.tempo_reset = True
                        tempo_change(state, rl)
        # slow down the loop a little bit, can be adjusted
        gc.collect()
        await asyncio.sleep(0.15)

def reset_encoder(state):
    global encoder
    encoder.position = 0  # This works OK!
    state.last_position = 0 # Also reset the last position.
    state.enc_sw_cnt = 0
    for _ in range(5):
        encoder_btn.update()
        time.sleep(0.005)

async def read_encoder(state):
    TAG = tag_adj("read_encoder(): ")
    # print("\n"+TAG+f"mode: {mode_dict[state.mode]}")
    pr_state(state)
    gc.collect()

    state.enc_sw_cnt = state.mode  # line-up

    if my_debug:
            print(TAG+f"mode_rv_dict[\"{mode_dict[state.mode]}\"]= {mode_rv_dict[mode_dict[state.mode]]}")

    tm_interval = 10
    tm_start = int(time.monotonic())

    while True:
        # ----------------------------------
        #  Read the encoder button (switch)
        # ----------------------------------

        if state.mode == MODE_G:
            send_midi_panic()
            glob_flag_change(state)
        elif state.mode == MODE_K:
            send_midi_panic()
            gc.collect()
            key_change(state)

        encoder_dbl_btn.update()

        if encoder_dbl_btn.short_count >=2 :  # We have an encoder button double press
            send_midi_panic()
            state.mode = MODE_I
            mode_change(state)
        else:
            encoder_btn.update()
            if encoder_btn.fell:
                state.btn_event = True
                state.enc_sw_cnt += 1
                if state.enc_sw_cnt > MODE_MAX-1:  # Do not allow to go to MODE_G (glob_flag_change) from this location (only from mode_change())
                    state.enc_sw_cnt = MODE_MIN
                if my_debug:
                    print(TAG+f"len(mode_klst): {len(mode_klst)}. New enc_sw_cnt: {state.enc_sw_cnt}")
                state.mode = state.enc_sw_cnt  # mode_lst[state.enc_sw_cnt]
                if my_debug:
                    print(TAG+"Encoder sw. pressed")
                    print(TAG+f"new mode:\n\"{mode_dict[state.mode]}\"")

        # state.last_position = cur_position
        state.enc_sw_cnt = state.mode  # line-up
        if my_debug:
            print(TAG+f"mode_rv_dict[\"{mode_dict[state.mode]}\"]= {mode_rv_dict[mode_dict[state.mode]]}")
        await asyncio.sleep(0.02)

        # ---------------------------------
        #  Read the encoder rotary control
        # ---------------------------------

        cur_position = encoder.position
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
            cur_position = encoder.position # re-read
            if my_debug:
                print(TAG+f"encoder_btn re-initiated. cur_position= {cur_position}")
        if state.last_position < cur_position:   # turned CW
            state.last_position = cur_position
            state.btn_event = True
            if my_debug:
                print("\n"+TAG+"Encoder turned CW")
            if state.mode == MODE_C:  # "chgm"
                pass # mode_change(state)
            elif state.mode == MODE_I:
                increment_selected(state)
            elif state.mode == MODE_N:
                if state.selected_index != -1:
                    n = state.notes_lst[state.selected_index] + cur_position
                    if my_debug:
                        print(TAG+f"\nstate.notes_lst[state.selected_index] = {state.notes_lst[state.selected_index]}")
                        print(TAG+f"n= {n}, Encoder rotary control last pos: {state.last_position} -> curr pos: {cur_position}")
                    if n >= octaves_dict[0][0] and n < octaves_dict[len(octaves_dict)-1][1]:
                        state.notes_lst[state.selected_index] += cur_position # make big note value changes possible
                    else:
                        n = state.notes_lst[state.selected_index] + 1
                        if n >= octaves_dict[0][0] and n < octaves_dict[len(octaves_dict)-1][1]:
                            state.notes_lst[state.selected_index] += 1
            elif state.mode == MODE_M:
                state.midi_channel += 1
                state.midi_ch_chg_event = True
                if state.midi_channel > midi_channel_max:
                    state.midi_channel = midi_channel_min
                if my_debug:
                    print(f"new midi channel: {state.midi_channel}")
                s = "new midi channel {:d}".format(state.midi_channel)
                msg = [TAG, s]
                pr_msg(msg)
                s = None
            elif state.mode == MODE_F:
                if state.selected_file is None:
                    state.selected_file = 0
                else:
                    state.selected_file += 1
                if my_debug:
                    print(TAG+f"state.selected_file= {state.selected_file}")
        elif cur_position < state.last_position:   # CCW
            state.last_position = cur_position
            state.btn_event = True
            if my_debug:
                print("\n"+TAG+"Encoder turned CCW")
            if state.mode == MODE_C:  # "chgm"
                pass # mode_change(state)
            elif state.mode == MODE_I:
                decrement_selected(state)
            elif state.mode == MODE_N:
                if state.selected_index != -1:
                    if cur_position < 0:
                        n = state.notes_lst[state.selected_index] + cur_position  # add a negative value
                    else:
                        n = state.notes_lst[state.selected_index] - cur_position  # subtract a positive value
                    if my_debug:
                        print(TAG+f"\nstate.notes_lst[state.selected_index] = {state.notes_lst[state.selected_index]}")
                        print(TAG+f"n= {n}, Encoder rotary control last pos: {state.last_position} -> curr pos: {cur_position}")
                    if n >= octaves_dict[0][0] and n < octaves_dict[len(octaves_dict)-1][1]:
                        if cur_position < 0:
                            state.notes_lst[state.selected_index] += cur_position  # add a negative value. Make big note value changes possible
                        else:
                            state.notes_lst[state.selected_index] -= cur_position  # subtract a positive value. Make big note value changes possible
                    else:
                        n = state.notes_lst[state.selected_index] - 1
                        if n >= octaves_dict[0][0] and n < octaves_dict[len(octaves_dict)-1][1]:
                            state.notes_lst[state.selected_index] -= 1
            elif state.mode == MODE_M:
                state.midi_channel -= 1
                state.midi_ch_chg_event = True
                if state.midi_channel < midi_channel_min:
                    state.midi_channel = midi_channel_max
                if my_debug:
                    print(f"new midi channel: {state.midi_channel}")
                s = "new midi channel {:d}".format(state.midi_channel)
                msg = [TAG, s]
                pr_msg(msg)
            elif state.mode == MODE_F:  # "file"
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
        gc.collect()

def extr_midi_notes(state):
    
    if state.notes_lst == [0] * 16:
        state.notes_txt_lst = ["0"] * 16
        return
    
    i = -1
    j = -1
    k = -1
    tipe = -1
    state.notes_txt_lst = []
    for _ in range(len(state.notes_lst)):
        note = state.notes_lst[_]
        for n in range(len(octaves_dict)):
            if note >= octaves_dict[n][0] and note <= octaves_dict[n][1]:
                i = octaves_dict[n][0]
                j = octaves_dict[n][1]
                k = n
                break
        
        if k >= 0:
            le = (j - i) + 1
            if le == 3:
                tipe = 0
            elif le == 12:
                tipe = 1
            elif le == 8:
                tipe = 2
                
            n = note % le
            
            if state.key_minor:
                s2 = octaves_minor_lst[n]
            else:
                if tipe >= 0:
                    if tipe == 0:
                        le1 = (j - i)
                        le2 = len(octaves_major_lst) -1
                        lst = octaves_major_lst[le2-le1:]
                        s = lst[n]
                        le1 = None
                        le2 = None
                        lst = None
                    elif tipe == 1:
                        s = octaves_major_lst[n]
                    elif tipe == 2:
                        lst = octaves_major_lst[:le]
                        s = lst[n]
                        lst = None
                    gc.collect()
                    
                    le3 = len(s)
                    if le3 == 1:
                        s2 = s + str(k)
                    elif le3 == 5:
                        s2 = s[:2] + str(k) + s[2:]+ str(k)
                    else:
                        s2 = "0"
            state.notes_txt_lst.append(s2)

async def play_note(state, idx, delay):
    TAG = tag_adj("play_note(): ")
    try:
        if idx >= 0 and idx < len(state.notes_lst):
            note = state.notes_lst[idx]
            sn = state.notes_txt_lst[idx]
            if state.midi_ch_chg_event:
                state.midi_ch_chg_event = False
            if (note > 0 and note < 128 ):
                gc.collect()
                if my_debug:
                    print(TAG+f"\nnote to play: {note} = {sn}")
                if not state.send_off:
                    midi.send(NoteOff(note, 0))
                    note_on = NoteOn(note, 127)
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
def send_midi_panic():
    for x in range(128):
        midi.send(NoteOff(x, 0))
        midi.send(NoteOff(x, 0))

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
            ret = ""+t+"{0:>{1:d}s}".format("",spc)
        return ret
    return ""

def do_connect(state):
    global ip, s_ip, pool, ntp, rtc
    TAG = tag_adj("do_connect(): ")
    cnt = 0
    timeout_cnt = 5
    dc_ip = None
    while dc_ip is None or dc_ip == '0.0.0.0':
        try:
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
            print(TAG+f"connected to {os.getenv('CIRCUITPY_WIFI_SSID')}")
            print(TAG+"IP address is", ip)
            msg = [TAG, "connected to", os.getenv('CIRCUITPY_WIFI_SSID'), "IP Address is:", ip,
                   'NTP date:', pr_dt(state, True, 0), pr_dt(state, True, 2)]
            pr_msg(msg)
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
    gc.collect()

def dt_update(state):
    state.ntp_datetime = ntp.datetime
    state.rtc_is_set = True

def wifi_is_connected():
    return True if s_ip is not None and s_ip != '0.0.0.0' else False

def setup(state):
    TAG = tag_adj("setup(): ")
    send_midi_panic() # switch off any notes
    s = "{}".format(os.getenv('CIRCUITPY_WIFI_SSID'))
    s2 = "Connecting WiFi to {:s}".format(s) if not wifi_is_connected() else "WiFi is connected to {:s}".format(s)
    if use_wifi:
        print(TAG+s2)
        if not wifi_is_connected():
            do_connect(state)
        dt_update(state)
    s = None
    s2 = None
    load_all_note_sets(state, True) # Use warnings
    gc.collect()

async def main():
    test_state_json = []
    state = State()
    setup(state)
    await asyncio.gather(
        asyncio.create_task(blink_the_leds(state, delay=0.125)),
        asyncio.create_task(read_buttons(state)),
        asyncio.create_task(blink_selected(state)),
        asyncio.create_task(read_encoder(state))
    )
    gc.collect()

asyncio.run(main())
