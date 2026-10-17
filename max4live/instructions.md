I have a Tech 21 NYC MIDI Moose footswitch contoller, Ableton Live 12 on Windows 11. 
I need to play Strings and many of the treble clef notes are octaves.
My desire is to be able to press a Moose button and add an octave in the treble range and either press the button again to remove the octave or press another button to remove the octave. 

I have a Strings instrument in an Instrument Rack in Track 1 in two Chains. 
One chain is in key zone C3 thru G8 and has a Chord Max for Live device to add an octave to the notes. 
The second chain is in key zone C-2 thru B2 with no additional devices.

Create a Max for Live device (or a .maxpat that I can import into Max for Live) that:

PGM 0 → octave ON
PGM 1 → octave OFF
Passes your original MIDI notes through unchanged
Adds +12 semitones to notes from C3 through G8 (so that the Chord device isn't needed)
Notes below C3 or above G8 aren't doubled
When switching the octave off while notes are being held, it sends octave note-offs to prevent hanging notes
Includes a manual toggle for testing
proper note-on/note-off tracking 
velocity preserved 
MIDI channel preserved

Keyboard
   │
   ▼
┌──────────────────────────────┐
│  Moose Octave M4L Device     │
│                              │
│ PGM 0 → OCTAVE ON            │
│ PGM 1 → OCTAVE OFF           │
│                              │
│ C3–G8 → original + octave    │
└──────────────────────────────┘
   │
   ▼
Strings Instrument
