How py-tuner was made
=====================

py-tuner is a tuner for guitar, bass, double bass and violin, with a
chromatic mode for any other instrument.  Nicolas Vaughan made it in
November 2026.  Its starting point was the study of FMIT (Free Music
Instrument Tuner), the C++ and Qt tuner that Gilles Degottex wrote from
2004; nothing of its code was copied, but reading it showed what a tuner
needs and where its precision is lost.  Here I explain how it was made, in
nine stages.

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

6. In Spanish, and packaged
---------------------------

My other programs speak English and Spanish, and this one had to as well.
Every text of the interface goes through one function, `tr()`, which looks
it up in `locale/es.xml`, as in py-slowdown; a test checks that every text
of the program is in that file, and nothing else.  The language follows
the system's unless the settings say otherwise, and in Spanish the numbers
take a decimal comma, in the window, the terminal and the command line
alike.  The notes can now also be written with both accidentals at once
(F♯/G♭), and the program starts in chromatic mode, which serves any
instrument, until another is chosen.

Then came what all my programs have: an icon, drawn as an SVG and turned
into every size by Inkscape; a menu entry and the AppStream metadata;
manual pages in both languages, made from the program's own help, so that
they cannot say anything it does not; user manuals in LaTeX, in both
languages, with pictures of the window drawn by a script from fixed
readings; an RPM, built and tested with Fedora's own packages and signed,
for Copr; and an AppImage with its own Python.  The AppImage needed one
thing more.  sounddevice, on Linux, does not bring PortAudio, and Fedora's
needs a glibc too new for older systems; so PortAudio is compiled for
glibc 2.28 with zig's compiler, from its source checked by its SHA-256,
and `audio.py` points sounddevice at the copy inside the package when there
is one.  Every file of a release is signed with my key, and each signature
is checked with only the published public key before anything is
published.

7. Lessons from other tuners
----------------------------

After the first release I read four other free tuners: Tuneo, by Braulio
Ríos, a phone app for the guitar; Strobie, by Davorin Šego, a strobe tuner;
pianito, by Axel Stevens, a piano tuner for the terminal; and Entropy Piano
Tuner, by Haye Hinrichsen and Christoph Wick.  Their sources were read, not
copied, and each is credited in [THIRD-PARTY.md](THIRD-PARTY.md) for what it
taught.

The most useful thing in Tuneo was not its code but eleven recordings of
guitar strings, from a phone.  py-tuner had only been measured on synthetic
strings, and those recordings showed what the synthetic ones never did:
notes that were not there, an octave or a twelfth under the real one (the
period shared by two partials of strings ringing in sympathy, or the thump
of the pluck), and octave errors upwards on steel strings whose fundamental
the phone hardly picked up.  To measure them I wrote `tools/evaluate.py`.
It counts the notes that are more than 120 cents from any string the file
should hold, and it borrows a trick from Strobie: the same recording,
declared at another sample rate, sounds as many cents higher or lower as
one wants, so the readings of the shifted copy must move by exactly that
much, and what does not is error, without knowing how the guitar was tuned.
In guitar mode py-tuner 0.1.0 heard 15 false notes, 9.1 seconds of them; in
chromatic mode, 26.

Four changes brought them to one (0.4 s) and two (0.7 s).  An octave
decision scores the candidates around the coarse pitch (a third, a half,
the pitch itself, twice and three times it) by how far their harmonics stand
over the spectrum's local background, as Strobie's harmonic stack does,
less what stands at their half-harmonics, as the negative weights of Entropy
Piano Tuner's key recognizer; a candidate above the period is only taken if
the sound also repeats at its lag.  The note sounding is preferred while it
decays, as Tuneo narrows its search.  A new note without a pluck must hold
for 0.3 s, or 0.6 s if it is a harmonic or an undertone of the note sounding
or of one that has just ended; a pluck is the level rising 1.5 times over
its envelope, as in Strobie.  And with an instrument's strings the search
goes only from a fourth below the lowest to a fifth above the highest, as
pianito and Tuneo clamp it.  The first version of the octave decision made
things worse in one way: it flipped between candidates in the tails, and the
shifted copies disagreed three times as often; the periodicity check and the
continuity put that right, and in the end 95% of the shifted readings agree
within 0.23 cents.

The strobe became a real one.  Each band demodulates the sound at a partial
of the target, as Entropy Piano Tuner's stroboscope does, and its stripes
move with the phase of that partial, scaled so that a cent is a stripe per
second, and fade when the partial does not stand over the noise between
partials, as in Strobie.  A single average let the neighbouring partials
leak in and the phase trembled by a degree; two averages in cascade made it
steady.  The partials are looked for where the string's measured
inharmonicity puts them, so on a stiff string in tune every band stands
still.  Then came what the others offered and py-tuner lacked: a trace of
the deviation over the last seconds, offsets of a few cents for each note,
the transposition of the names, a capo, and a reference tone that sounds
through the computer, as pianito plays one.

8. Three more ideas
-------------------

Three ideas of the review were left for later, and came after 0.2.0.  The
first is Strobie's noise floor: py-tuner learns the level of the room while
nothing plays, following it when it moves and only creeping up under a
sound, and never during a note, which would otherwise become the
background; a sound must then stand 10 dB over it.  On the guitar
recordings it took away the last false note in guitar mode.  It also ends
sooner the very faint tail of a string that rings into the noise of a
phone's microphone, which is why it can be turned off.  The second is a
spectrum, as Strobie shows one: the sound on a logarithmic axis of
frequency, its clearest peaks named as notes with their cents, and the
harmonics of the note sought marked, in the window and, as a row of bars,
in the terminal.  The third is Tuneo's gauge: a fine scale for the needle,
an arctangent, on which the last five cents take half of each side and the
rest up to fifty the other half.

9. A steady response for the double bass
----------------------------------------

On my own acoustic double bass the reading was never quiet: the needle
wandered some cents while the string sounded.  The detector was not the
cause.  On a synthetic string with the same weak fundamental, the two
slightly different vibrations of a real string beating together, the
other open strings ringing in sympathy and the rumble of a room, each
frame still came within a few hundredths of a cent.  What moves is the
string itself.  A plucked low string is stretched by its own swing, so it
starts sharp, several cents if the pluck is strong, and goes down as it
fades; the bow, too, moves the pitch a little.  The reading followed all
of it faithfully, and the needle with it.

So there is now a setting, the response, normal or steady.  The steady
response leaves out the attack of each pluck, the first half second from
its first onset, and keeps the note that was sounding on the screen
meanwhile.  The onset of py-tuner stays on for about a third of a second
while its envelope catches up, so the attack had to be counted from the
first onset of a run, not from the last one.  The reading then averages
at least a second and a half, and the needle follows it with a lag of
0.3 s instead of 0.06.  With an instrument's strings, the tail of the
note is still read at a lower clarity (0.6 instead of 0.75), as the
other strings ringing with it make the sound less periodic.  In the
chromatic mode it is not: there the search goes below the lowest A, and
the lower clarity let through 24.5 Hz, the undertone that D2 and G2 share
(D2/3, G2/4) when both ring.

Two rules were needed for the lower clarity.  The grace that lets a new
string be taken quickly after a pluck now ends as soon as the pluck's own
note is taken; before that, a harmonic of the E string ringing beside an
A (its octave, a fifth above the A) could replace the A just after the
attack.  And a note that rises from silence without a pluck must last 0.3
s, as a jump between notes must; without this, the dying tail of a guitar
D string gave a false note of 0.4 s.

I measured it on sequences of four plucks of each open string, of
different strengths, with a knock at each pluck, the polarisations
beating, the other strings ringing and a room before the first note.
Within each pluck the reading moved 11 cents from end to end with the
normal response and 2 with the steady one, its drift fell from 9 to 1.4
cents per second, and it lasted as long.  On a bowed note it moved 1.2
cents instead of 3.5.  On the eleven guitar recordings the steady
response gave no false note, and its largest error over the shifted
recordings was 1.7 cents, against 4.0 with the normal one.  The normal
response is what it was.

Testing
-------

The program has 228 tests, which run all at once with `tools/test.py`,
each file in a process of its own, in about eight seconds.  Most of them
measure: the open strings of the four instruments must come out within a
tenth of a cent of their known pitch, with noise the mean error must stay
near zero, a weak or missing fundamental and a strongly inharmonic string
must not change the result, and noise and silence must give no note.
Others check the octave decision on a string whose odd partials are weak
(the period alone reads it an octave up), the waits for a new note with and
without a pluck, the strobe's bands moving one, two and four stripes per
second for each cent and standing still on a stiff string in tune, the
offsets, the capo and the transposition, the reference tone, the noise
floor (which learns the room, never a note, and lets through a tone 25 dB
over the noise but not one 5 dB over it), the spectrum's peaks, the
needle's scales, and the steady response (an attack left out from its
first onset while the note stays, a new string taken at once after it
but a fifth from a ringing string not, and a gliding double bass string
held to less than half the movement of the normal response).  Others
check the names and frequencies of the notes, the tunings, the
reading's response to wrong values and new notes, the settings, the WAV
files of 8 to 32 bits, the options of the command line, a whole recording
analysed note by note, the terminal interface running in a
pseudo-terminal, where the test presses keys and reads the screen, and the
window drawn off screen.  Others check that the Spanish file has every
text, that the versions of the program, the spec and the metadata agree,
that the manual pages are up to date, that the AppImage finds its own
PortAudio, and the signing of a release and its deposit on Zenodo, with a
key made for the test.  I also looked at the window and at the terminal
as a user sees them, in both languages, while a WAV file of six detuned
guitar strings played; ran the command line with the computer's
microphone; and ran the AppImage, which found the sound devices through its
own PortAudio.  The real recordings, which cannot be distributed with it,
measure it on this computer with `tools/evaluate.py`, with either
response.  The program has 49 files of Python, around 9,300 lines, of
which some 2,600 are tests.
