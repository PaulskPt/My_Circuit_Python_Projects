
# File: midi_note_nrs.py
# See: https://www.inspiredacoustics.com/en/MIDI_note_numbers_and_center_frequencies
#
# See https://en.wikipedia.org/wiki/Circle_of_fifths
# See also: # See: https://www.inspiredacoustics.com/en/MIDI_note_numbers_and_center_frequencies 
# Circle of fifths is a way of organizing the 12 chromatic pitches
# as a sequence of perfect fifths.
# Key of C Major:

# Major: C D E F G A B
# Minor: A B C D E F G

# Keys of C major and minor.

octaves_major_lst = ["C", "C#/Db",    "D",  "D#/Eb", "E",   "F",  "F#/Gb",   "G",  "G#/Ab", "A",       "A#/Bb", "B"]
octaves_minor_lst = ["cm", "a#m/bbm", "bm", "b#m",   "c#m", "dm", "d#m/cbm", "em", "fm",    "f#m/gbm", "gm",    "g#m"]

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