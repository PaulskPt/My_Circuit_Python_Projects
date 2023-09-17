 File: ```changes_log.md```
 This file contains changes made to ```code.py``` by @PaulskPt (non exhaustive list).

 To choose your ```display driver```: set the global flags ```use_ssd1306``` and ```use_sh1107``` (only one can be "True")
 If you want to use WiFi, set the ```use_wifi``` flag to "True" and fill in your ```CIRCUITPY_WIFI_SSID``` and ```CIRCUITPY_WIFI_PASSWORD``` in the file ```settings.toml```-
 A global flag ```my_debug``` has been added to control the majority of print statements in this script.
 Added global flag ```use_TAG```. This flag controls if in calls to function ```tag_adj()``` tags received will be printed or not.
 On a small display no function names (variable TAG) in print statements make the display more readable.

 Twentfour functions added that are not found in the other repos for the TR-Cowbell board:
 ```
 count_btns_active(), 
 clr_events(), 
 clr_scrn(), 
 pr_state(), 
 pr_msg(), 
 pr_dt(), 
 load_all_note_sets(), 
 load_note_set(),
 key_change():
 tempo_change(), 
 mode_change(), 
 glob_flag_change(), 
 fnd_empty_loop(), 
 id_change(), 
 send_bend(), 
 wr_to_fi(),
 reset_encoder(),
 send_midi_panic(),
 extr_midi_note(),
 tag_adj(), 
 do_connect(), 
 dt_update(), 
 wifi_is_connected(),
 setup().
```
 2023-08-22 with clarification/help by Tim (@Foamyguy), changing the name of file ```boot_pico.py``` into ```boot.py```.
 and resetting the PicoW booted the PicoW with a Storage filesystem in ```Writeable``` mode.
 See the opening text:
```
 TR-COWBELL test
 board ID: "raspberry_
 pi_pico_w"
 Storage filesystem is
 : Writeable                  <<<=== Filesystem is in mode "Writeable"
 OLED driver: SH1107
 --------------------
```
 NOTE: that, when the filesystem is in ```Writeable``` mode, one only can bring the filesystem back to ```Readonly``` state,
 by issuing the following two commands in REPL (of an IDE like mu-editor):
 ```
 > import os
 > os.remove("7boot.py")
```
 then reboot the PicoW by pressing the ```reset``` button on the TR-COWBELL board (near the PicoW).
 The next boot the filesystem will be back in the default state: ```Readonly```.

 2023-08-26 added functionality to change the notes representation to ```Fifths```, keys ```Major``` and ```Minor```:

```
 |---- Mode -----|
      indx 1   
      note 2 
      file 3   
      midi 4   
   >> fift 5 <<   <<<=== fift (= mode "fifths")
      nkey 6   
      tmpo 7   
      flag 8
 | Exit=>Enc Btn |
```

```
 8 buttons active 
 ------------------
 0/  69  74  77   0 
      0  67   0  67 
 1/   0   0   0  79 
     76  69   0   0 
 ------------------
 selected idx: 14
 mode:fift.NoteSet:1   <<<=== After pressing Encoder switch a 4th time
                              mode changed to "fift" (= "fifths")

 Display fifths   <<<=== After turning the Encoder control clockwise (CW) or counter clockwise (CCW)
 changed to:             changes the value between "Display fifths" True (ON) or False (OFF) (= False (OFF) is the default display)
 True

 8 buttons active
 ------------------
 Eb D B/Cb C            <<<=== Display with the "Fifths" flag active (True)
 C C/Db C C/Db 
 C C C C/Db 
 E Eb C C 
 ------------------
 selected idx: 14
 mode:fift.NoteSet:1


 |---- Mode -----|   
      indx 1   
      note 2   
      file 3   
      midi 4   
      fift 5
   >> nkey 6 <<   <<<=== nkey (= mode "note key" = MODE_K)
      tmpo 7 
      flag 8
 | Exit=>Enc Btn |

 8 buttons active
 ------------------
 Eb D B/Cb C 
 C C/Db C C/Db 
 C C C C/Db 
 E Eb C C 
 ------------------
 selected idx: 14
 mode:nkey.NoteSet:1   <<<=== After pressing Encoder switch mode changed to "nkey" (= "note key")
                              In this mode the key of the notes can be changed between "Major" or "Minor"


 The key	             <<<=== After turning the Encoder rotary control clockwise (CW) or counter clockwise (CCW)
 of the notes                the key of the notes is changed to "Minor"
 changed to:
 Minor


 8 buttons active
 ------------------
 c b g a 			<<<=== Representation of the notes in key Minor
 a bb a bb 
 a a a bb 
 c c a a 
 ------------------
 selected idx: 14
 mode:nkey.NoteSet:1
 
 The key	             <<<=== After turning the Encoder rotary control clockwise (CW) or counter clockwise (CCW)
 of the notes                the key of the notes is changed back to "Major" (default)
 changed to:
 Major

 8 buttons active
 ------------------
 Eb D B/Cb C  			<<<=== Representation of the notes in key Major
 C C/Db C C/Db 
 C C C C/Db 
 E Eb C C 
 ------------------
 selected idx: 14
 mode:nkey.NoteSet:1
 

  2023-08-30 added functionality to change global flag. See the menu below. 

 |---Glob Flag---|    <<<=== This menu appears (created by function glob_flag_change() )
   >>  none 0 <<
      debug 0   
        TAG 0   
       wifi 1   
       dtUS 0   
 | Exit=>Enc Btn |

 The flag "dtUS" is not a global flag but an attribute flag in class state.
 If dtUS is True then date time will be shown as (example):
 NTP date:
 Tue 8/30/2023
 07:25:30 PM

 If dtUS is False the date time will be shown as (example):
 NTP date:
 Tue 2023-08-30
 19:25:30
```

 If flag ```use_wifi``` is False then ```dtUS``` will not be shown in the ```Glob Flag``` menu because the date and time is taken
 from an NTP source and a WiFi connection is needed to get it.

 2023-08-31 to optimize code: reversed the use of ```state.mode```. Before it contained the string of the mode, e.g.: "index".
   Now it contains an integer, representing the mode, e.g.: state.mode = ```MODE_I```  (= 1). For this ```mode_klst``` was created
   and mode_lst was removed. In many places (52 ?) the code of this script has been changed accordingly.

 2023-09-01 In this version added ```encoder_dbl_btn```. I managed a reliable catch of an encoder button doubble press. 
   Achieved by beside importing ```Debouncer```, also importing ```Button``` (```from adafruit_debouncer import Debouncer, Button```) and
   and besides creating a Debouncer object: ```encoder_btn = Debouncer(encoder_btn_pin)```
   also creating a Button object: ```encoder_dbl_btn = Button(encoder_btn_pin)```

   Then, in function ```read_encoder()``` a double press of the encoder button is catched as follows:
   ```
        encoder_dbl_btn.update()

        if encoder_dbl_btn.short_count >=2 :  # We have an encoder button double press
            send_midi_panic()
            mode_change(state)
 ```

 2023-09-03 Thanks advice @DJDevon3 added and use function ```send_midi_panic()``` to silence unwanted sound blocking during calls to ```load_note_set()``` and other actions.

 2023-09-03 Added functionality to alter tempo: added ```MODE_T```. Added functions ```tempo_change()```, ```send_bend()```.
 
```
 |---- Mode -----|     <<<<=== This menu shown after an encoder button double-click (TODO: because added mode "tmpo" this top line is scrolled off-screen)
      indx 1   
      note 2   
      file 3   
      midi 4   
      fift 5   
      nkey 6   
   >> tmpo 7 <<
      flag 8   
 | Exit=>Enc Btn |


  8 buttons active       <<<=== default screen in "mode tempo"
  ------------------
  0/  69  74  77   0 
       0  67   0  67 
  1/   0   0   0  79 
      76  69   0   0 
  ------------------
  tempo:120,dly:0.125     <<<=== Mode "tempo" status line 1 showing default tempo 120  (state.tempo) and showing "delay" (written as "dly" (= state.bpm) )
  mode:tmpo.NoteSet:1     <<<=== Mode "tempo" status line 2 showing "mode:tmpo" (=  MODE_T or "mode tempo")
```
  Using D-pad BUTTON 2 (right_btn) increases the tempo. Using BUTTON 4 (left_btn) decreases the tempo.

   To enable this functionality made appropriate changes in the state class (added attributes). Made changes in functions ```read_button()``` and ```pr_state()```.
   Also made appropriate changes in file: ```README_buttons_and_controls.md```.
   Created an updated image of the ```script outline``` made using MS VSCode. See folder/file: ```Pictures_mod_PaulskPt/IMG_09.png```. Added pictures: ```IMG_18.png``` and ```IMG_19.png```.

 2023-09-03
 Modified function ```mode_change()```
 in such a way that the list of mode items will scroll between the ```heading line``` and the ```bottom line```. Each moment there will fit only 7 mode items on the screen
 between heading line and bottom line.
 See the images below:

```
 |---- Mode -----|   <<<=== Heading line
  >> indx 1 <<       <<<=== Start position of the index pointer.
     note 2   
     file 3   
     midi 4   
     fift 5   
     nkey 6   
     tmpo 7   
 | Exit=>Enc Btn |  <<<=== Bottom line

 |---- Mode -----|
      indx 1   
   >> note 2 <<     <<<=== Situation after the encoder rotary control has been turned clockwise one notch
      file 3   
      midi 4   
      fift 5   
      nkey 6   
      tmpo 7   
 | Exit=>Enc Btn |

 |---- Mode -----|
      indx 1   
      note 2   
   >> file 3 <<      <<<=== Situation after the encoder rotary control has been turned clockwise one notch a second time
      midi 4   
      fift 5   
      nkey 6   
      tmpo 7   
 | Exit=>Enc Btn |

 |---- Mode -----|
      indx 1   
      note 2   
      file 3   
   >> midi 4 <<      <<<=== Situation after the encoder rotary control has been turned clockwise one notch a third time
      fift 5   
      nkey 6   
      tmpo 7   
 | Exit=>Enc Btn |

 |---- Mode -----|
      indx 1   
      note 2   
      file 3   
      midi 4   
   >> fift 5 <<      <<<=== Situation after the encoder rotary control has been turned clockwise one notch a fourth time
      nkey 6   
      tmpo 7   
 | Exit=>Enc Btn |

 |---- Mode -----|
      indx 1   
      note 2   
      file 3   
      midi 4   
      fift 5   
   >> nkey 6 <<      <<<=== Situation after the encoder control has been turned clockwise one notch a fifth time
      tmpo 7   
 | Exit=>Enc Btn |

 |---- Mode -----|
      note 2   
      file 3   
      midi 4   
      fift 5   
      nkey 6   
   >> tmpo 7 <<       <<<=== When the index pointer arrives here (after turning the encoder rotary control on notch a sixth time)
      flag 8                 the displayed list of mode items is scrolled up
 | Exit=>Enc Btn |


 |---- Mode -----|
      note 2   
      file 3   
      midi 4   
      fift 5   
      nkey 6   
      tmpo 7  
   >> flag 8  <<      <<<=== If, with the index pointer at this point (last mode item in the list), the encoder control is turned clockwise one more notch,
 | Exit=>Enc Btn |           the index pointer will roll to the first mode item in the list ("indx 1") (see next image below)

 |---- Mode -----|    
  >> indx 1 <<       <<<=== If, with the index pointer at this point (first mode item in the list), the encoder control is turned counter clockwise one notch,
     note 2                 the index pointer will roll to the last item in the list ("flag 8") (situation see previous image)
     file 3   
     midi 4   
     fift 5   
     nkey 6   
     tmpo 7   
 | Exit=>Enc Btn |
```

2023-09-04. 
- Moved various textual information from the top of the script code.py to this file
- Created file: ```midi_note_nrs.py```. In it I created a dictionary called: ```midi_notes_dict``` containing 128 keys,
- e.g.: ``` 96: ("C7", 61, 76, 2093.00),       # Midi Organ starts here```. The first element of the tuple is the note representation for the key value.
- the second element is the note value for an ```Organ```. The third element is the note value for a ```Piano```. The fourth element is the frequency of the tone.
- I moved the ```notes_C_dict``` and the ```notes_major_minor_dict``` from the script ```code.py``` to the file ```midi_note_nrs.py```
- I applied changes to functions pr_state(), read_encoder(), play_note(). I created the function encoder_reset(), to reset the encoder.position to 0 whenever its
- position value exceeds + or - 127.
- In ```read_encoder()``` added functionality to add ```encoder.position``` value instead in/decrementing with just 1 unit. This needs limit checking. It also lead to the
- creation of the function ```encoder_reset()```. Also added an ```elapsed time``` calculation. After passing ```tm_interval``` (currently: 10) the ```encoder.position``` 
- will be reset to 0 as well as- ```state.last_position```. This prevents that the ```encoder.position``` reach too high values.
- 
- 2023-09-05.
- In function pr_state() changed to present the selected note by chevrons " >  <".

- 202-09-06
- In function pr_state() changed the "/1" and "/2" in the left column to " 1", "5", "9" and "13" (See image below).
- Replaced IMG_09.png with images IMG_08a.jpg and IMG_08b.jpg which show the new situation.

```
  8 buttons active
 ------------------
  1 >A4< D5  F5   0
  5   0  64   0  64
  9   0   0   0  65
 13  E5  A4   0   0
 --------------------
 selected idx: 1
 mode:indx.NoteSet:1
```

2023-09-11.
- In function load_all_note_sets() added functionality to limit the number of note sets to be loaded to 10.
- In case more than 10 note sets are found in the file "saved_loops.json", the following two (ultimate) lines
- will be added to the displayed message:
```
note sets
have been
read from file
saved_loops.json
successfully
nr (ultimate) note sets not loaded: 2
only 10 note sets can be loaded
```

- Added folder "Docs_mods_PaulskPt".
- Moved all "REPL...md" files and this file to the new folder.
- Updated the file "README_buttons_and_controls.md".

2923-09-15.
- Because of Memory Allocation errors, I made the following changes:
- In file ```midi_note_nrs.py``` I removed the large midi_notes_dict. I created a new, short, ```octaves_dict``` and an ```octaves_base_lst```.
- In file ```code.py``` I created a new function ```extr_midi_note()```. 
- I combined the functions: ```fifth_change()``` and ```key_change()``` into a new function ```fk_change()```.
  
- Below the display output of the new fk_change(state, True) call:
```
Display notes as
fifths: False
 
Turn encoder control to change
 
Exit=>Enc Btn
```

Below the display output of the new fk_change(state, False) call:

```
The key 
of the notes: Major
 
Turn encoder control to change
 
Exit=>Enc Btn
```

2023-09-16.
- Since the normal screen contains notes represented in the "Major" key format, decided to remove the ```state.display_fifths``` flag, removed ```MODE_D```. Renamed flag ```state.key_major``` into  ```state.key_minor``` (default: False). Renamed function ```fk_change()``` into ```key_change```. In Class State added the list: ```state.notes_txt_lst```.
- Changed functions ```extr_midi_notes()```, ```read_buttons()```, ```play_note()```..
- In file ```midi_note_nrs.py``` removed the dictionary: ```notes_major_minor_dict```, removed the definitions: ```FIFTHS_NOTES_MAJOR``` and 
```FIFTHS_NOTES_MINOR```. Renamed the ```octaves_base_lst``` to ```octaves_major_lst```. Added a similar ```octaves_minor_lst```.

The screen when flag ```state.key_minor``` is False:

```
 8 buttons active
------------------
 1 >A#4<A#0   0  C4 
 5   0   0  C4   0 
 9   0  C4 C#9   0 
13  C4   0   0  D3 
------------------
selected note: 1
mode:indx.NoteSet:7
```

Screen when flag ```state.key_minor``` is True:

```
 8 buttons active
------------------
 1 >gm<a#m   0  cm 
 5   0   0  cm   0 
 9   0  cm a#m   0 
13  cm   0   0  bm 
------------------
selected note: 1
mode:indx.NoteSet:7
```

2023-09-17

I changed function ``´blink_the_leds()`` in an attempt to not blink active buttons (latches). I managed to do this. This change makes viewing the 16 leds more calm and indicates better which are active. Only the active selected led kept blinking. I managed to stop the blinking of the active selected by 
changing the function ```blink_selected()```.

I added the flag ```blink_selected```in Class State. Its default value is ```True```. This flag can be changed from within function ```glob_flag_change()```. The state of this flag is used in function ```blink_selected```. In this way the user can activate or de-activate this flag and thus control the blinking (or not) of the active selected.
I favor for not blinking the active selected because in the screen the selected is marked by the chevrons: ">   <" and by the first text line below the set of notes, e.g.: "selected note: 14". For me a more "calm" behaviour of the sixteen leds is more important than the necessity having the selected blink.
However, blinking the selected is more in line with the original version by @Foamyguy et al.

Because there occurred an OSError in line 40 of code.py: ```40 rtc.RTC().datetime = ntp.datetime```, I put this line inside a try...except block that will
catch future occurrances of this error.

To improve the reaction of the encoder button double press, in Class State I added the flag ```enc_double_press```. In function ```read_encoder()``` this flag will be set True as soon as a double press of the encoder button has been registrated. At the start of function ```pr_state()``` I added the line:
```   if state.enc_double_press: return``` so that the main screen will not be created (and no time used for it). The flag ```state.enc_double_press``` will be cleared in the end of function ```mode_change()```. The line ``` if state.enc_double_press: return``` I also added at the start of function ```key_change()``` because it happened that after a "missed" double press of the encoder button the function key_change() was called (unintended).
I tested the addition of the state.enc_double_press flag and the changes for it in the code. It improved the response to a double press of the encoder button.

Note that the double press action of the encoder button has to be performed quickly otherwise it will not be "served". This is caused by the execution of the async system.


