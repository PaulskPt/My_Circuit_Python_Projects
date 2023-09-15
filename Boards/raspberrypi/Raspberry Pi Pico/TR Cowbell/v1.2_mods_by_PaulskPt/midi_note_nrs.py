
# File: midi_note_nrs.py
# See: https://www.inspiredacoustics.com/en/MIDI_note_numbers_and_center_frequencies
#
# See https://en.wikipedia.org/wiki/Circle_of_fifths
# See also: # See: https://www.inspiredacoustics.com/en/MIDI_note_numbers_and_center_frequencies 
# Circle of fifths is a way of organizing the 12 chromatic pitches
# as a sequence of perfect fifths.
# Key of C Major:

FIFTHS_NOTES_MAJOR = 0
FIFTHS_NOTES_MINOR = 1
# Major: C D E F G A B
# Minor: A B C D E F G

# Keys of C major and minor.
notes_major_minor_dict = {
    60 : ("C4", "cm"),      # middle C  261.63 Hz
    61 : ("C4#/Db4", "a#m/bbm"),
    62 : ("D4", "bm"),
    63 : ("D#4/Eb4", "b#m"),
    64 : ("E4", "c#m"),
    65 : ("F4", "dm"),
    66 : ("F#4/Gb4", "d#m/cbm",),
    67 : ("G4", "em"),
    68 : ("G#4/Ab4", "fm"),
    69 : ("A4", "f#m/gbm"),     # concert pitch  440.00 Hz
    70 : ("A#4/Bb4", "gm"),
    71 : ("B4", "g#m"),
    }

octaves_base_lst = ["C", "C#/Db", "D", "D#/Eb", "E", "F", "F#/Gb", "G", "G#/Ab", "A", "A#/Bb", "B"]


octaves_dict = { 
    0: (21, 23),   # only 3 tones
    1: (24, 35),   # 12 tones
    2: (36, 47),   # same
    3: (48, 59),
    4: (60, 71),
    5: (72, 83),
    6: (84, 95),
    7: (96, 107),
    8: (108, 119),
    9: (120,127)   # only 8 tones
    }