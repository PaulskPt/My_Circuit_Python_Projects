# TR_COWBELL_readme_buttons_and_controls.md
# by @PaulskPt (Github)
# 2023-08-20
# --------------------------------------------
# NOTE:
# Near the top of the script is a declaration of the global variable "my_debug".
# If my_debug is True then most of the print commands in the script will be executed.
# If my_debug is False these print commands will be inhibited
# Only error situations will be printed to the REPL
#
# There are several other global variables (flags)
# use_midi
# use_ssd1306 (for the OLED 128x64 that came with the kit v1.2) (either this flag or use_sh1107 can have value True)
# use_sh1107 (for the Adafruit OLED 128x128 display)
#
# D-Pad buttons functions:
# Middle button: switches between states:
# - If normal press:
#   -- If state.mode = "selecting_file":
#      If state.selected file is None:
#           --- prints "saving";
#           --- tries to open file "saved_loops.json";
#           --- reads contents of to "saved_loops";
#           --- closes the file
#           If "loops" not in saved_loops.keys(), sets saved_loops["loops"] to [];
#           --- inserts into saved_loops["loops"] an entry containing the keys: "notes" and "selected_indes"
#           --- tries to open file "saved_loops.json";
#           --- saves contents of variable saved_loops;
#           --- In case the storage filesystem is "readonly" (see file boot_pico.py) the data cannot be saved.
#           --- This will generate an OSError which will be handled by the script. This fact will not crash the script.
#           --- closes the file
#      else:
#           --- sets state.mode to "selecting_index"
# - "selecting_note" and
# - "selecting_index"
# - If long pressed:
#   -- switches state.mode to the next mode: "selecting_file", "selecting_note" or "selecting_index".
#   -- I state-mode is "selecting_file":
#   -- tries to open file "saved_loops.json";
#   -- reads content of "loops" into object.item "state.saved_loops"
#
# Up button:
# - In state.mode "selecting_note", if one or more buttons is activated: increases the note frequency
# - In state.mode "selecting_index" saves ... to file ...
# - In state.mode "selecting_file" ...
# Down button:
# - In state.mode "selecting_note", if one or more buttons is activated: decreases the note frequency
# - In state.mode "selecting_index" ...
# - In state.mode "selecting_file" ...
# Left button:
# - In state.mode "selecting_note, if one or more buttons is activated: decreases note frequency
# Right button
# - In state.mode "selecting_note, if one or more buttons is activated: increases note frequency
# ---------------------------------------------
# Rotary encoder: has 1 control and 1 switch
# - the variable for the control is: encoder
# - the variable for the switch is: encoder_btn
# -- The switch, when pressed, switches the mode between "selecting_file, "selecting_note", "selecting_index" and "selecting_midi_channel"
# -- in mode "selecting_file" the rotary encoder has no function.
# -- in mode "selecting_index" turning the rotary encoder control clockwise will increase the selected_index value to the next selected note.
# -- in mode "selecting_index" turning the rotary encoder control counter clockwise will decrease the selected index value to the previous selected note.
# -- In the mode "selecting_note", if one or more buttons is activated, turning the rotary encoder control clockwise will increase the note of the selected_index.
# -- In the mode "selecting_note", if one or more buttons is activated, turning the rotary encoder control counter clockwise will decrease the note of the selected_index.
# -- In the mode "selecting_midi_channel, turning the rotary encoder control clockwise will increase the midi channel. Currently the maximum channel number is 2 (default).
# -- In the mode "selecting_midi_channel, turning the rotary encoder control coounter clockwise will decrease the midi channel. Currently the minimum channel number is 1.
# ----------------------------------------------
