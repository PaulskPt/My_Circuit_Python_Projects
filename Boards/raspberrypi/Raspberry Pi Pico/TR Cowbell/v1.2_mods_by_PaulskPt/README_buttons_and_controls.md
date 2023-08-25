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
# NOTE: At startup all the note sets are loaded into memory. Then the last note set in the list of sets is loaded. This set has all nots with value 0.
#       and no key buttons selected. By pressing the Up button or the Down button one can load a next or a previous notes set.
#
# D-Pad buttons functions:
#
# Middle button:
# - If normal press:
#   -- In modes "index" or "note"
#      --- changes mode to "file", so one can: 
#          a) load all saved note sets (aka: saved loops) using a Middle button long press;
#          b) next: read a next or previous notes set using the Up or Down button
#   -- In mode = "file":
#       --- if the filesystem is "Writeable":
#       --- tries to open file "saved_loops.json";
#       --- saves contents of variable saved_loops;
#       --- In case the storage filesystem is "readonly" (see file boot_pico.py) the data cannot be saved.
#       --- This will generate an OSError which will be handled by the script. This fact will not crash the script.
#       --- closes the file
#    else:
#        --- Writes an error message that the filesystem is readonly. Cannot save note sets to file.
# - If long pressed:
#   -- If state-mode is "file":
#   -- tries to open file "saved_loops.json";
#   -- reads all the previously saved note sets (aka: "loops") into memory (state class: object.item "state.saved_loops)"
#
# Up button:
# - In mode "index" or "file" this button loads the next notes set from memory
# - In mode "note", if one or more buttons is activated: increases the note frequency
# Down button:
# - In mode "index" or "file" this button loads the previous notes set from memory
# - In mode "note", if one or more buttons is activated: decreases the note frequency
# Left button:
# - In mode "index" if more than one button is activated, this button changes the selected index to the previous available index
# - In mode "note, if one or more buttons is activated: decreases note frequency
# Right button
# - In mode "index" if more than one button is activated, this button changes the selected index to the next available index
# - In mode "note, if one or more buttons is activated: increases note frequency
#
# ---------------------------------------------
#
# Rotary encoder: has 1 control and 1 switch
# - the variable for the control is: encoder
# - the variable for the switch is: encoder_btn
#
# -- The switch, when pressed, switches between the modes: "index", "note", "file" and "midi_channel".
#
# -- in mode "index" turning the rotary encoder control clockwise will increase the selected_index value to the next selected note.
# -- in mode "index" turning the rotary encoder control counter clockwise will decrease the selected index value to the previous selected note.
# -- In mode "note", if one or more buttons is activated, turning the rotary encoder control clockwise will increase the note of the selected_index.
# -- In mode "note", if one or more buttons is activated, turning the rotary encoder control counter clockwise will decrease the note of the selected_index.
# -- in mode "file" the rotary encoder has no function.
# -- In mode "midi_channel, turning the rotary encoder control clockwise will increase the midi channel. Currently the maximum channel number is 2 (default).
# -- In mode "midi_channel, turning the rotary encoder control coounter clockwise will decrease the midi channel. Currently the minimum channel number is 1.
#
# NOTE: It is advised to use the D-Pad (middle, Up and Down keys) to perform file actions.
# ----------------------------------------------
