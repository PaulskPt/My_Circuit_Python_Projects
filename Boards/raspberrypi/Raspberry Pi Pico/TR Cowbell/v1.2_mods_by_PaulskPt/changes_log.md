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
 pr_loops(), 
 pr_dt(), 
 load_all_note_sets(), 
 load_note_set(),
 fifths_change():
 key_change(), 
 tempo_change(), 
 mode_change(), 
 glob_flag_change(), 
 fnd_empty_loop(), 
 id_change(), 
 send_bend(), 
 wr_to_fi(), 
 send_midi_panic(), 
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
 changed to:             changes the value between "Display fifths" ON or OFF (= OFF is the default display)
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
 |---- Mode -----|
  >> indx 1 <<       <<<=== Start position of the index pointer.
     note 2   
     file 3   
     midi 4   
     fift 5   
     nkey 6   
     tmpo 7   
 | Exit=>Enc Btn |

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

