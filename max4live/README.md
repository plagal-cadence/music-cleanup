# Moose Octave — Max for Live MIDI Effect

Adds an octave (+12 semitones) above notes from C3 to G8. A Tech 21 MIDI Moose switches it with Program Change messages.

| Moose footswitch (first group) | Moose display | Incoming PGM | Action |
| --- | --- | --- | --- |
| 1/6 | 1 | 0 | Octave ON |
| 2/7 | 2 | 1 | Octave OFF (any octave notes you're holding are released) |
| 3/8 | 3 | 2 | Toggle: press once for on, again for off |
| others | 4+ | other | Passed through to the instrument |

The Moose numbers its programs from 1, so its display is always one higher than the PGM the device receives (shown in **Last PGM**). The Moose sends the program again when you press the same footswitch twice, so **3/8** works as a single on/off button.

The device passes your original notes through unchanged. It also keeps each note's velocity and MIDI channel. CC, pitch bend, aftertouch and sysex pass through untouched.

## Files

- `moose_octave.maxpat`: the device patch (UI and wiring)
- `moose_octave.js`: the note logic. Keep it in the **same folder** as the saved device.

## Load the device

`Moose Octave.amxd` in this folder is ready to use:

1. Drag it from this folder (or from Live's browser, after adding this folder under **Places**) onto **Track 1**, to the **left** of the Instrument Rack.
The device is **frozen**: `moose_octave.js` is embedded inside it, so it works from any folder. A copy is in the User Library at `N:\Ableton\User Library\User Library\MIDI Tools\`.

If you change `moose_octave.js`, unfreeze the device (click **Edit**, then the snowflake). Check that the Max Console shows "Moose Octave: script loaded", then freeze and save again.

## Rebuild the device from the .maxpat (only if needed)

1. In Live, open the browser and go to **Max for Live → Max MIDI Effect**. Drag it onto **Track 1**, to the **left** of the Instrument Rack.
2. Click the device's **Edit** button. The Max editor opens.
3. In Max, choose **File → Open** and open `moose_octave.maxpat`. It opens in a second window.
4. In that window, make sure Presentation mode is **off** (**View → Presentation** unchecked). Otherwise Ctrl+A only selects the on-screen controls and leaves out the script and the wiring. Press **Ctrl+E** to unlock it and **Ctrl+A** to select everything. Then press **Ctrl+C**.
5. Switch to the device's editor window. Delete the default `midiin`/`midiout` objects, then press **Ctrl+V**.
6. Choose **View → Presentation** to check the layout, then turn on **Open in Presentation** in the patcher inspector.
7. Choose **File → Save As**. Save it as `Moose Octave.amxd` in this folder (next to `moose_octave.js`). Close the editor.
8. Optional: click the **Freeze** (snowflake) button in the editor toolbar, then save again. This embeds the `.js` file in the `.amxd`, so you can move the device anywhere.

## Set up the track

- **Remove the Chord device** from the C3–G8 chain. Moose Octave now adds the octave.
- Octave notes from C3 and up are all C4 or higher, so they still land in the C3–G8 chain. You can keep both chains or merge them into one.
- **Track 1 input:** both the keyboard and the Moose must reach the track. Set **MIDI From** to **All Ins**, channel **All Channels**. If both devices plug into one MIDI interface, choosing that port also works.
- **Settings → Link, Tempo & MIDI:** turn on **Track** for the Moose's input port.
- Arm or monitor Track 1 as usual.

## Using it

- **Octave** toggle: switches by hand for testing. It also lights up when the Moose switches the octave.
- **Last PGM**: shows the raw program number the device received. Press a Moose button: if it reads 0 or 1, everything is working. If it reads some other number, the Moose is sending a different program number (some units count from 1). Either set the Moose to send 0 and 1, or change `PGM_ON` / `PGM_OFF` near the top of `moose_octave.js`.
- **Low / High**: the range that gets doubled (default C3–G8).
- **Panic**: sends note-off for everything and clears the device's record of held notes.

### Notes

- G8 is MIDI note 127, the highest note MIDI has. Notes from **G#7 to G8** have no note an octave up, so they play once, without the octave.
- If you switch the octave **on** while holding keys, the held keys are not doubled. Only keys you play after that are doubled.
- If Last PGM never changes when you press the Moose, work through the checklist below.

### If Last PGM never changes

The Moose sends only program changes. Live's MIDI Map mode can't learn program changes, so this device has to receive them from the track's MIDI input.

1. **Check that Live receives the Moose at all.** Open **Settings → Link, Tempo & MIDI**. Turn on **Track** for the Moose's input port. Press a Moose button and watch the MIDI indicator in the top-right corner of Live's window.
   - If it doesn't blink, the problem is the cable, the MIDI interface or the Windows driver, not Live.
2. **Check the track input.** Track 1's **MIDI From** must include the Moose's port: choose **All Ins** or that specific port, with **All Channels**.
   - Track 1 must also be armed, or have Monitor set to **In**.
3. **Last resort: convert program changes to notes outside Live.** Some setups never pass program changes to the track. For those:
   1. Install **loopMIDI** (free), which creates a virtual MIDI port.
   2. Use **Bome MIDI Translator** or **MIDI-OX** to translate Moose PGM 0/1 into two notes. Pick notes you never play, e.g. C-2 and C#-2.
   3. Send the result to the loopMIDI port and select that port as Track 1's input.
   4. Ask me to add "note triggers" to the device, so those two notes switch the octave instead of being played.
