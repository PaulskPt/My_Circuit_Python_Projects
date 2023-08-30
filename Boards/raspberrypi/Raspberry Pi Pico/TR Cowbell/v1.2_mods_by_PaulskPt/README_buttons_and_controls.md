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
# use_ssd1306 (for the OLED 128x64 that came with the kit v1.2) (either this flag or use_sh1107 can have value True)
# use_sh1107 (for the Adafruit OLED 128x128 display)
# other flags are inside the state class object
#
# NOTE: 
# At startup all the note sets (from file 'saved_loops.json') are loaded into memory.
# A 'sero notes set' will be displayed at startup (state.notes_lst is defaulted to: '[0] * 16')
# The script expects a 'zero notes set' to be at the end of the 'saved_loops.json' file.
# If no 'zero note set' is in the saved_loops.json file, when saving them to the file, a 'zero notes set' will be added
# to the end of the file.
#
# By pressing the Up button or the Down button one can load a next or a previous notes set.
#
# D-Pad buttons functions:
#
# Middle button:
# - If normal press:
#   -- In modes "indx" or "note"   ("indx" stands for "index". Due to small display we decided to display only 4 characters for the mode status)
#      --- changes mode to "file", so one can: 
#          a) load all saved note sets (aka: saved loops) using a Middle button long press;
#          b) next: read a next or previous notes set using the Up or Down button
#   -- In mode = "file":
#      If the filesystem is "Writeable":
#       --- The following six actions will be performed:
#       --- 1) if file 'saved_loops.bak' exists, this file will be deleted (os.remove);
#       --- 2) The file 'saved_loops.json' will be renamed to: 'saved_loops.bak';
#       --- 3) if exists an empty notes list (all sixteen notes value 0) in state.staved_loops, this empty set will be copied to memory and deleted from state.saved_loops;
#       --- 4) The current note set (loop) (state.notes_lst) will be added to state.saved_loops;
#       --- 5) if exists a 'zero notes set', it will be added to the end of state.saved_loops.
#       ---    if no 'zero notes set' exists, a 'zero notes set' will be created. This set will be added to state.saved_loops.
#       --- 6) the contents of state.saved_loops will be written to file 'saved_loops.json'.
#       --- closes the file 'saved_loops.json'.
#      else:
#        --- Writes an error message that the filesystem is readonly. Cannot save note sets to file.
# - If long pressed:
#   -- If state-mode is "file":
#   -- tries to open file "saved_loops.json";
#   -- reads all the previously saved note sets (aka: "loops") into memory (state class: object.item "state.saved_loops)"
#
# Up button:
# - In mode "indx" or "file" this button loads the next notes set from memory
# - In mode "note", if one or more buttons is activated: increases the note frequency
# Down button:
# - In mode "indx" or "file" this button loads the previous notes set from memory
# - In mode "note", if one or more buttons is activated: decreases the note frequency
# Left button:
# - In mode "indx" or in mode "note" if more than one button is activated, 
#   this button changes the selected index to the previous available index
# Right button
# - In mode "indx" or in mode "note" if more than one button is activated, 
#   this button changes the selected index to the next available index
#
# ---------------------------------------------
#
# Rotary encoder: has 1 control and 1 button (switch)
#
# -- After a double press of the encoder button, the menu below appears:
```
   |---- Mode ----|
     >> indx 1 <<
        note 2
        file 3
        midi 4
        fift 5
        nkey 6
        flag 7
   | Exit=> Enc Btn |
```
# turning the rotary encoder control clockwise moves the selector indicator down to the next mode in the list.
# turning the rotary encoder control counter clockwise moves the selector indicator up to the previous mode in the list.
# To exit with the selected mode press the encoder button once again.

# In the table below the available modes and their abbreviations:

```
   +--------------------+---------------+
   | Mode               |  Displayed as |
   +--------------------+---------------+
   ! "mode_change"      |   "mchg"      |   Note: this mode is not shown in the mode change menu
   | "index"            |   "indx"      |
   | "note"             |   "note"      |
   | "file"             |   "file"      |
   | "midi_channel"     |   "midi"      |
   | "display_fifths"   |   "fift"      |
   | "note_key"         |   "nkey"      |
   | "glob_flag_change" |   "flag"      |
   +--------------------+---------------+
```
# -- mode "mchg" (see above) not shown
# -- in mode "indx" turning the rotary encoder control clockwise will increase the selected index value to the next selected note.
# -- in mode "indx" turning the rotary encoder control counter clockwise will decrease the selected index value to the previous selected note.
# -- In mode "note", if one or more buttons is activated, 
#    turning the rotary encoder control clockwise will increase the note of the selected index.
# -- In mode "note", if one or more buttons is activated, 
#    turning the rotary encoder control counter clockwise will decrease the note of the selected index.
# -- in mode "file" the rotary encoder has no function.
# -- In mode "midi", (i.e.: "midi_channel", turning the rotary encoder control clockwise will increase the midi channel. 
#    Currently the maximum channel number is 2 (default).
# -- In mode "midi", turning the rotary encoder control coounter clockwise will decrease the midi channel. 
#    Currently the minimum channel number is 1.
# -- In mode "fift", turning the rotary encoder control clockwise or coounter clockwise will change the display of fifths ON or OFF
#    (normal number values)
# -- In mode "nkey", turning the rotary encoder control clockwise or coounter clockwise will change the key of the notes display between
#    Major and Minor
# -- When menu item 'flag' is chosen, followed by an encoder button click, the "Glob Flag" menu will appear.
#    In case the use_wifi flag is True, the following menu appears:
```
   |---Glob Flag---|
     >> debug 0 <<
          TAG 0
         wifi 1
         dtUS 1
         none 0
   | Exit=> Enc Btn |
```

# In case the use_wifi flag is False, the dtUS (date and time in USA format flag) flag will not be shown 
# because the built-in realtime clock (RTC) will only be updated from an NTP server when wifi is active.
# If dtUS is True the date will be shown as (example): "Tue 8/30/2023". The time will be shown as (example): "07:25:30 PM"
# If dtUS is False the date will be shown as (example): "Tue 2023-08-30". The time will be shown as (example): "19:25:30"
# dtUS is not really a global variable but is part of the state class (state.dt_str_usa).

```
   |---Glob Flag---|
     >> debug 0 <<
          TAG 0
         wifi 0
         none 0
   | Exit=> Enc Btn |
```

# When you select 'none' and press the encoder control button, the global flag menu will be left without 
# changing any of the shown flags.
#
#
# NOTE: At startup the flag for "display of fifths" is set to False. The flag for the Key of notes is set to True (Major)
# NOTE: It is advised to use the D-Pad (middle, Up and Down keys) to perform file actions.
# ----------------------------------------------
