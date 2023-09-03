# file: changes_log.md
# This file contains changes made to code.py by @PaulskPt (non exhaustive list)
#
# To choose your display driver: set the global flags "use_ssd1306" and "use_sh1107" (only one can be "True")
# If you want to use WiFi set the "use_wifi" flag to "True" and fill in your WiFi SSID and Password in the file "settings.toml"
# A global flag "my_debug" has been added to control the majority of print statements in this script.
# Added global flag "use_TAG". This flag controls if in calls to function tag_adj() tags received will be printed or not.
# On a small display no function names (variable TAG) in print statements make the display more readable.
#
# Twentfour functions added that are not found in the other repos for the TR-Cowbell board:
# count_btns_active(), 
# clr_events(), 
# clr_scrn(), 
# pr_state(), 
# pr_msg(), 
# pr_loops(), 
# pr_dt(), 
# load_all_note_sets(), 
# load_note_set(),
# fifths_change():
# key_change(), 
# tempo_change(), 
# mode_change(), 
# glob_flag_change(), 
# fnd_empty_loop(), 
# id_change(), 
# send_bend(), 
# wr_to_fi(), 
# send_midi_panic(), 
# tag_adj(), 
# do_connect(), 
# dt_update(), 
# wifi_is_connected(),
# setup().
#
# 2023-08-31 to optimize code: reversed the use of state.mode. Before it contained the string of the mode, e.g.: "index".
#   Now it contains an integer, representing the mode, e.g.: state.mode = MODE_I # (= 1). For this mode_klst was created
#   and mode_lst was removed. In many places (52 ?) the code of this script has been changed accordingly.
# 2023-09-01 In this version added encoder_dbl_btn. I managed a reliable catch of an encoder button doubble press.
# 3034-09-03 Thanks advice @DJDevon3 added and use function send_midi_panic() to silence unwanted sound blocking during calls to load_note_set() and other actions.
# 3034-09-03 Added functionality to alter tempo: added "MODE_T". Added functions tempo_change(), send_bend().
#
# |---- Mode -----|     <<<<=== This menu shown after an encoder button double-click (TODO: because added mode "tmpo" this top line is scrolled off-screen)
#      indx 1   
#      note 2   
#      file 3   
#      midi 4   
#      fift 5   
#      nkey 6   
#   >> tmpo 7 <<
#      flag 8   
# | Exit=>Enc Btn |
#
#
#  8 buttons active       <<<=== default screen in "mode tempo"
#  ------------------
#  0/  69  74  77   0 
#       0  67   0  67 
#  1/   0   0   0  79 
#      76  69   0   0 
#  ------------------
#  tempo:120,dly:0.125     <<<=== Mode "tempo" status line #1 showing default tempo 120  (state.tempo) and showing "delay" (written as "dly" (= state.bpm) )
#  mode:tmpo.NoteSet:1     <<<=== Mode "tempo" status line #2 showing "mode:tmpo" (=  MODE_T or "mode tempo")
#
#  Using D-pad BUTTON 2 (right_btn) increases the tempo. Using BUTTON 4 (left_btn) decreases the tempo.
#
#   To enable this functionality made appropriate changes in the state class (added attributes). Made changes in functions read_button() and pr_state().
#   Also made appropriate changes in file: README_buttons_and_controls.md.
#   Created an updated images of the script outline made by MS VSCode. See folder Pictures_mod_PaulskPt/IMG_09.png. Added pictures: IMG_18.png and IMG_19.png.
#
