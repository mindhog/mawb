
# MAWB - Modular Audio Workbench

This is the "Modular Audio Workbench."  It is currently a jumbled bundle of
tools used by its author to do random things to make music, but the idea is to
have a complete component management system geared towards music performance.

MAWB was written for Linux systems using ALSA and jack.  You may be able to
get this system working under other operating systems, and portions of the
system are usable indepdendantly.

# isokbd - Isomorphic Keyboard Controller

Included in this package are the beginnings of isokbd.py, a script which lets
you emulate hexagonal isomorphic keyboard controllers (currently only the
[Wicki-Hayden](https://en.wikipedia.org/wiki/Wicki%E2%80%93Hayden_note_layout)
layout) from a normal computer keyboard.

If you run `isokbd.py`, you'll get a window displaying a hexagonal
representation of a standard computer keyboard.  The program will bind to a
new alsa midi client named "isokbd".  You should be able to connect the
solitary output port of this client to your software or attached hardware of
choice and play music from the keyboard.

# Installation

To do a complete installation, follow the instructions in INSTALL (a virtual
env should not strictly be necessary.

For `isokbd.py` you can just do this.

    python3 setup.py build
    sudo python3 setup.py install



# LICENSE

MAWB is released under the Apache License, version 2.0.  Portions of this code
(as indiciated in the header) are also released under a much lighter license
that is fully described the header.

Unless otherwise noted, all files are Copyright Michael A. Muller.