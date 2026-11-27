How py-tuner was made
=====================

py-tuner is a tuner for guitar, bass, double bass and violin, with a
chromatic mode for any other instrument.  Nicolas Vaughan made it in
November 2026.  Its starting point was the study of FMIT (Free Music
Instrument Tuner), the C++ and Qt tuner that Gilles Degottex wrote from
2004; nothing of its code was copied, but reading it showed what a tuner
needs and where its precision is lost.  Here I explain how it was made, in
five stages.

py-tuner is free software, under the GNU General Public License, version 3
or later.  It uses numpy (BSD licence) for the analysis, sounddevice (MIT
licence) with PortAudio (an MIT-style licence) for the sound card, and
PySide6, the Qt bindings for Python, under the GNU Lesser General Public
License, version 3, for the window; the terminal interface uses Python's
curses module and ncurses (an MIT-style licence), and Python itself is
under the Python Software Foundation License.

Nicolas Vaughan is Associate Professor of Literature at the School of Arts
and Humanities of the Universidad de los Andes, Bogotá, Colombia.

1. Reading FMIT
---------------

FMIT finds the fundamental in three steps.  A Fourier transform of a Hann
window gives the strongest peak of the spectrum, and a second transform of
the magnitudes (a "comb") decides which harmonic that peak is, so that the
fundamental is the peak divided by its number.  Then the result is refined,
either by averaging f_n/n over the first harmonics or by measuring the
distance between zero crossings of the wave.  Finally a "quantizer" keeps
the estimates of the last 125 ms, groups them by the nearest note and shows
the mean of the largest group, in hertz.

Each of these steps leaves something on the table.  The average of f_n/n
gives a weak, noisy eighth harmonic the same weight as the fundamental,
and it ignores that a real string is inharmonic: its partials are at
n·f0·√(1+B·n²), so the upper ones are sharp, and on a guitar's sixth string
the eighth partial is already several cents above eight times the
fundamental.  The average comes out sharp.  Zero crossings are easily
displaced by strong harmonics and by noise.  And the averaging was done in
hertz, with no rejection of single wrong values.  There was also no test
that measured the error against a known frequency, which is the only way to
say that a tuner is accurate.

I decided to keep the general shape (a coarse estimate that cannot be
wrong by an octave, followed by a fine one) and to change each part, and to
measure everything against synthetic strings of known pitch from the
beginning.  Of what FMIT offers, I left out the historical temperaments
and the Scala scales: the instruments in question are tuned in equal
temperament, and what a player of them needs to change is the reference A.

2. The pitch engine
-------------------

The coarse step is McLeod's method: the normalized square difference
function of the signal, computed with the Fourier transform, whose first
high peak (not the highest one) is the period.  Taking the first peak whose
height reaches nine tenths of the highest avoids picking twice the period,
and the height itself says how periodic the sound is, which serves to
reject noise.

The fine step works on a longer frame, sixteen periods of the note found,
with a four-term Blackman-Harris window, whose side lobes are 92 dB down,
so a neighbouring harmonic hardly moves the peak of another.  Instead of
interpolating between the bins of a Fourier transform, which has a bias of
its own, each harmonic is located at the exact maximum of the transform of
the windowed frame, evaluated at any frequency: Newton's method on
|X(f)|², with the first and second derivatives computed in the same pass,
for all the harmonics at once.  The low harmonics are found first; from
them come a first f0 and B, which predict where the upper ones are.  Then
f0 and B are fitted by weighted least squares, with weights (n·A_n)²,
which follow how the variance of each estimate falls, and the reading is
the first partial, f0·√(1+B).

Three problems appeared when I measured it.  The first version of the fit
used the approximation √(1+B·n²) ≈ 1 + B·n²/2, and with a very inharmonic
string (B = 5·10⁻⁴) it left a bias of a tenth of a cent; written as
(f_n/n)² = f0² + f0²·B·n², the model is exactly linear, and the bias went
away.  The second: with noise only 20 dB below the signal, the upper
harmonics were buried, Newton's method found peaks of noise there, and
their large weights pulled the fit; the median of the spectrum gives the
level of the noise, and a peak that does not rise 12 dB above it is now
left out.  The third was speed: building the matrix of complex exponentials
took 65 ms per frame for the low strings of a bass.  Built as the product
of a coarse grid and a fine one, the same matrix takes about a ninth of the
time, with errors near 10⁻¹³, and a frame of a low string now takes around
10 ms.

With synthetic strings at 40 dB of signal to noise, from B0 of a
five-string bass to E5 of the violin, single frames fall within a few
hundredths of a cent; with a fundamental at 2% of its normal level, or
with none at all, the harmonics are enough.  At 20 dB the frames scatter
by a tenth or two of a cent, but their mean has no bias.

3. Notes, instruments and the reference A
-----------------------------------------

A note is its MIDI number, and from it come its frequency, for any
reference A between 380 and 480 Hz (in tenths of a hertz), and its name,
in English, Latin (Do, Re, Mi) or German (with H and B), with sharps or
flats and the scientific octave.  Each instrument has its usual tuning and
some others: on the guitar, Drop D, DADGAD and the open tunings; on the
bass, the five- and six-string ones; on the double bass, the orchestral and
the solo tunings and the low B and low C extensions; on the violin, two
scordature.  The user can add more in the settings.  The instrument also
fixes the range where the fundamental is searched for, a little beyond its
lowest string, so that a very slack string is still found.

4. A steady reading
-------------------

A single frame has its noise, and a tuner must not tremble.  The reading
shown is the trimmed mean (the central half) of the last half second of
estimates, measured in cents: it resists an isolated wrong value and at
the same time is more precise than any single frame.  A jump of more than a
third of a semitone that repeats is a new note and empties the history; a
jump that does not repeat is discarded.  After 0.4 s without pitch the note
goes off.  The string compared against is the nearest one of the tuning,
unless the user locks one.

5. Three interfaces
-------------------

The analysis runs in a thread of its own, forty times a second, over a
ring buffer that the sound card (or a WAV file played at the pace of the
clock) keeps filling, and the three interfaces only read its last result.

The command line writes the reading in one line that rewrites itself; with
`--once` it waits for the first steady reading, prints it and exits; and
with a WAV file it analyses the whole recording and prints one line for
each note in it.  The terminal interface, with curses, shows the note in
big letters of its own font, a text needle, a strobe of three bands and the
strings, and the keys change the reference A, the instrument and the rest.
Here the arrow keys did not work in the first test: I had given the Escape
key the function of quitting, and curses, receiving an arrow sequence it
did not expect, passed on the Escape alone.  Now only `q` quits.  The
window, with PySide6, has a needle with a green zone for the tolerance, a
strobe of three bands that move at one, two and four times the speed of
the deviation, and a button for each string.  Every change in the window or
in the terminal is saved in the settings at once.

Testing
-------

The program has 114 tests, which run all at once with `tools/test.py`,
each file in a process of its own, in about four seconds.  Most of them
measure: the open strings of the four instruments must come out within a
tenth of a cent of their known pitch, with noise the mean error must stay
near zero, a weak or missing fundamental and a strongly inharmonic string
must not change the result, and noise and silence must give no note.
Others check the names and frequencies of the notes, the tunings, the
reading's response to wrong values and new notes, the settings, the WAV
files of 8 to 32 bits, the options of the command line, a whole recording
analysed note by note, the terminal interface running in a
pseudo-terminal, where the test presses keys and reads the screen, and the
window drawn off screen.  I also looked at the window and at the terminal
as a user sees them, while a WAV file of six detuned guitar strings
played, and ran the command line with the computer's microphone.  The
program has 29 files of code, around 3,500 lines.
