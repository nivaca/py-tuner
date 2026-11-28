# Changelog

All notable changes to py-tuner. The releases, with the RPM, the AppImage,
the wheel and the source, are on
[Codeberg](https://codeberg.org/nivaca/py-tuner/releases) and
[GitHub](https://github.com/nivaca/py-tuner/releases).

## Unreleased

Low notes through a weak microphone.

- Low notes heard through a microphone that cuts the low end, as a
  phone's or a laptop's does, such as the low E of a bass, are read at
  once after the pluck and are no longer lost while they fade. The
  fundamental of such a string comes weak, and its sharp upper partials
  made the sound look less periodic than it is: the clarity is now also
  judged on the lower partials of the pitch found. The level that the
  noise gate compares is measured only in the band of the notes, where
  the room's noise is lower. On a synthetic bass E1 through a high-pass
  at 200 Hz, with noise 20 dB down, the first reading came after 0.1 s
  instead of 0.6, and the note was shown 98 % of the time instead of
  64 %. On the real guitar recordings nothing got worse.
- The level bar shows that level in the band of the notes, which in a
  noisy room is some decibels under the former one.

## 0.4.0 — 2026-11-27

A steady response for the double bass.

- A steady response for the double bass (`--response steady`, `r` in the
  terminal, Response in the settings): the first half second of each
  pluck is left out while the note stays shown, the reading averages at
  least 1.5 s, the needle moves more slowly, and with an instrument's
  strings the faint tail is still read. On synthetic double bass strings
  the reading moved 2 cents within a pluck instead of 11, and 1.2 instead
  of 3.5 on a bowed note. The normal response is unchanged.

## 0.3.0 — 2026-11-27

The room's noise, a spectrum, and a finer needle.

- The window no longer crashes as it closes (SIGBUS or SIGABRT at exit):
  it is deleted while Qt is still whole.
- The noise of the room, learned while nothing plays: what doesn't stand
  10 dB over it is ignored (it can be turned off). On the guitar
  recordings, no false note left in guitar mode.
- The spectrum, with its clearest peaks named and the harmonics of the note
  sought marked, in the window and in the terminal (`f`).
- A fine scale for the needle, where the last 5 cents take half of each
  side (`--needle fine`, `g` in the terminal).

## 0.2.0 — 2026-11-27

The right note on real strings, and a real strobe.

- Fewer wrong notes on real strings: an octave and twelfth decision by the
  harmonics of each candidate, a new note without a pluck waits (longer if
  it is a harmonic or an undertone of the note sounding), and with strings
  the search stays near them. On eleven guitar recordings, one false note
  where there were fifteen. The note or string held is kept until 10 cents
  past halfway to the next.
- A real strobe: each band follows the phase of a partial, in vernier mode
  (the clearest partial at three speeds) or harmonics mode (partials 1, 2
  and 3), and fades when the partial is lost in the noise.
- The history of the deviation, in the window and the terminal.
- Note offsets, the names transposed, a capo, and a reference tone
  (`py-tuner tone`, the Tone button, `p` in the terminal).
- Credits to the tuners these ideas come from: Strobie, Entropy Piano
  Tuner, Tuneo and pianito (docs/THIRD-PARTY.md).
- `--once` waits for a reading of at least 0.3 seconds of sound before it
  takes it as steady (with one or two frames, a wrong one could pass, as on
  a slow machine), and a frame shorter than the analysis needs, or whose
  harmonics disagree with its period, gives no reading instead of a poor
  one.
- Pictures of the terminal interface and of the command line, in the
  READMEs and the manuals (tools/terminal_images.py).

## 0.1.0 — 2026-11-27

The first version.

- A tuner for guitar, bass, double bass and violin, with their usual
  tunings and others, and a chromatic mode; tunings of one's own in the
  settings.
- The pitch from all the harmonics of the string, with their
  inharmonicity: within a few hundredths of a cent on a steady string.
- A reference A from 380 to 480 Hz, in tenths of a hertz.
- A needle and a strobe, in a window (PySide6), in a full-screen terminal
  (curses) and on the command line, which also measures a WAV recording
  note by note.
- Note names in English, Latin or German, with sharps, flats or both
  (F♯/G♭); the interface in English or Spanish.
