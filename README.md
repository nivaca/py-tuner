py-tuner
========

An accurate tuner for guitar, bass, double bass and violin, with a chromatic
mode for anything else. It shows a needle and a strobe, and it runs in a
window, in a full-screen terminal or as a single line on the command line.

On a steady string, a single analysis frame is within a few hundredths of a
cent of the true pitch; with noise 20 dB below the signal, the shown reading
(which averages half a second) still stays within about a tenth of a cent.
The fundamental is found from all the harmonics of the string, with their
inharmonicity, so it works even when a small microphone barely picks up the
fundamental of a low string.


Install and run
---------------

py-tuner needs Python 3.14 or later, and PortAudio for the sound card
(`dnf install portaudio` on Fedora). From the source folder, with
[uv](https://docs.astral.sh/uv/):

    uv run py-tuner              # the window
    uv run py-tuner tui          # the terminal
    uv run py-tuner cli          # one line of text
    uv run py-tuner devices      # list the inputs
    uv run py-tuner instruments  # list the instruments and tunings

Common options, for all three modes:

    -a, --a4 HZ          reference A4, 380 to 480 Hz (default 440)
    -i, --instrument     guitar, bass, double-bass, violin or chromatic
    -t, --tuning NAME    e.g. "Drop D", "5-string", "Solo"
    -s, --string N|auto  tune against string N (1 = the lowest) only
    --names              english, latin (Do Re Mi) or german (H, B)
    --flats, --sharps    how to write accidentals
    -d, --device DEV     input device, by number or part of its name
    -f, --file WAV       read a WAV file instead of the sound card
    --save               keep the options given as the new settings

`py-tuner cli --file recording.wav` analyses a recording at once and prints
one line for each note heard in it, with its frequency and its deviation in
cents. `py-tuner cli --once` waits for the first steady reading, prints it
and exits.

In the terminal, the arrow keys change A4 (left and right by 0.1 Hz, up and
down by 1 Hz), `0` puts it back to 440, `i` changes the instrument, `t` the
tuning, `s` locks a string, `n` the note names, `b` flats or sharps, `v` the
view, and `q` quits. In the window, a click on a string button locks that
string, and a second click unlocks it.


Instruments
-----------

| Instrument  | Tunings                                                        |
|-------------|----------------------------------------------------------------|
| Guitar      | Standard, Drop D, half and whole step down, Drop C, DADGAD, Open D, G, E and C, 7-string |
| Bass        | Standard, Drop D, half step down, 5-string, 5-string high C, 6-string |
| Double bass | Orchestral, Solo, 5-string with low B or low C, fifths          |
| Violin      | Standard, cross tuning (AEAE), GDGD                            |

Your own tunings can be added in the settings file (see below), as entries
of `custom_tunings`:

    {"instrument": "guitar", "name": "Nashville", "strings": "E3 A3 D4 G4 B3 E4"}


Settings
--------

The settings are kept in `~/.config/py-tuner/settings.json` (or under
`$XDG_CONFIG_HOME`), and every change made in the window or the terminal is
saved there at once. Besides the ones above: `tolerance` (cents within which
a note counts as in tune, default 1), `min_level` (sounds quieter than this,
in dBFS, are ignored), `smoothing` (seconds the reading averages) and
`periods` (the length of each analysis frame, in periods of the note: more
is steadier, fewer reacts faster).


Tests
-----

    uv run python tools/test.py

runs the tests, each file in a process of its own, all at once.


License
-------

py-tuner is free software, under the GNU General Public License, version 3
or later (see `LICENSE`). Author: Nicolas Vaughan
<nicolasvaughan@proton.me>.
