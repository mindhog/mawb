
# MAWB - Modular Audio Workbench

This is the "Modular Audio Workbench."  It is currently a jumbled bundle of
tools used by its author to do random things to make music, but the idea is to
have a complete component management system geared towards music performance.

MAWB was written for Linux systems using ALSA and jack.  You may be able to
get this system working under other operating systems, and portions of the
system are usable indepdendantly.

# isokbd - Isomorphic Keyboard Controller

Included in this package are the beginnings of isokbd.py, a script which lets
you emulate hexagonal isomorphic keyboard controllers from a standard US
layout computer keyboard.

The layouts currently supported are:
-   [Wicki-Hayden](https://en.wikipedia.org/wiki/Wicki%E2%80%93Hayden_note_layout)
-   [Harmonic](https://en.wikipedia.org/wiki/Harmonic_table_note_layout)
-   [Jankó](https://en.wikipedia.org/wiki/Jank%C3%B3_keyboard)
-   "Thirds" (in which the key to the right is always a half step up and the
    key above and to the left is a major third up from the current note).
    [This layout was inspired by this article on the similar guitar
    tuning.](http://www.migo.info/music/major_third_guitar_tuning.xhtml_en.html)
-   "Alt Thirds" is a different orientation on the "Thirds" layout.  The key
    to the right is a major third and the key above and to the left is a
    half-step below the current note.

If you run `isokbd.py`, you'll get a window displaying a hexagonal
representation of a standard computer keyboard labeled with the keyboard key
and the note that it will play.  The program will bind to a new alsa midi
client named "isokbd".  You should be able to connect the solitary output
port of this client to your software or attached hardware of choice and play
music from the keyboard.

You can specify the keyboard layout with the first argument.  For example, to
use Jankó:

    $ isokbd.py janko

Supported type names are: "janko" (for Jankó), "wicki" (for Wicki-Hayden),
"harm" (for Harmonic), "thirds" (for the Thirds layout) and "altthirds" for
the alt-thirds layout.  The default layout is Wicki-Hayden.

# midiedit - Midi piano-roll editor

Also included in this package is a stand-alone midi piano roll editor,
`midiedit.py`.  It's still very much a work in progress.  To run it:

    $ midiedit.py <filename.mid>

The filename is optional, if unspecified the editor will save to a unique
filename of the form "unnamed<n>.mid".

You'll want to connect the midi port of the editor to a synth of some sort so
you can hear what you're doing.

To operate the editor:

-   Click on a location to place a quarter-note there.
-   Click and drag notes around to different positions.
-   Shift-click and drag to lengthen or shorten notes.
-   Space to play the piece.
-   Left/right keys to move the playhead back and forth single notes
-   F2 to save your midi file.

There's a lot that's missing from the editor at this point, notably velocity
editing, channel control, deletes, selection... As stated initially, it's a
work in progress.

# Installation

To do a complete installation, follow the instructions in INSTALL (a virtual
env should not strictly be necessary).

For `isokbd.py` and `midiedit.py` you should only need swig, tkinter and the
alsa libaries and headers ("swig", "python3-tk" and "libasound2-dev" on
debian-derivatives) and you can install like so:

    python3 setup.py build
    sudo python3 setup.py install

# LICENSE

MAWB is released under the Apache License, version 2.0.  Portions of this code
(as indiciated in the header) are also released under a much lighter license
that is fully described the header.

Unless otherwise noted, all files are Copyright Michael A. Muller.