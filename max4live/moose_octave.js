// moose_octave.js
// Max for Live MIDI effect logic: adds an octave (+12) to notes in a key range,
// switched on/off by MIDI Program Change (e.g. from a Tech 21 MIDI Moose).
//
// Inlet 0:   raw MIDI bytes from [midiin]
//            messages: "octave 0|1", "low <note>", "high <note>", "panic"
// Outlet 0:  raw MIDI messages (lists of bytes) to [midiout]
// Outlet 1:  octave state (0/1), for the on-device toggle
// Outlet 2:  last Program Change number received (raw, 0-127)

autowatch = 1;
inlets = 1;
outlets = 3;

// ---- settings --------------------------------------------------------------
var PGM_ON = 0;       // Program Change that turns the octave ON
var PGM_OFF = 1;      // Program Change that turns the octave OFF
var PGM_TOGGLE = 2;   // Program Change that flips the octave (single-button use)
var SHIFT = 12;       // semitones to add

var lowNote = 60;     // C3 in Live's note naming (middle C = C3 = 60)
var highNote = 127;   // G8 in Live's note naming

// ---- state -----------------------------------------------------------------
var octaveOn = 0;
var held = [];        // [ch*128+pitch] 1 while that key is physically held
var doubled = [];     // [ch*128+pitch] 1 while that held key has an octave sounding
var outCount = [];    // [ch*128+pitch] how many sources are holding that output note

// MIDI byte parser state
var runStatus = 0;
var dataBytes = [];
var needed = 0;
var inSysex = 0;

clearState();
post("Moose Octave: script loaded\n");

function clearState() {
    for (var i = 0; i < 16 * 128; i++) {
        held[i] = 0;
        doubled[i] = 0;
        outCount[i] = 0;
    }
}

// [midiout] expects one byte per int, so send messages byte by byte
function sendMidi(bytes) {
    if (typeof bytes === "number") bytes = [bytes];
    for (var i = 0; i < bytes.length; i++) outlet(0, bytes[i]);
}

// ---- incoming raw MIDI bytes ------------------------------------------------
function msg_int(b) {
    b = b & 0xFF;

    if (b >= 0xF8) {            // realtime: pass through, doesn't disturb parsing
        sendMidi(b);
        return;
    }

    if (inSysex) {
        if (b < 0x80 || b === 0xF7) {
            sendMidi(b);
            if (b === 0xF7) inSysex = 0;
            return;
        }
        inSysex = 0;            // any other status byte ends sysex; handle it below
    }

    if (b === 0xF0) {
        inSysex = 1;
        runStatus = 0;
        sendMidi(b);
        return;
    }

    if (b >= 0x80) {            // status byte
        dataBytes = [];
        if (b >= 0xF0) {        // system common: pass through untouched
            runStatus = 0;
            sendMidi(b);
            return;
        }
        runStatus = b;
        var type = b & 0xF0;
        needed = (type === 0xC0 || type === 0xD0) ? 1 : 2;
        return;
    }

    // data byte
    if (runStatus === 0) {      // data of a system common message: pass through
        sendMidi(b);
        return;
    }
    dataBytes.push(b);
    if (dataBytes.length === needed) {
        handleMessage(runStatus, dataBytes);
        dataBytes = [];         // keep runStatus for running status
    }
}

function handleMessage(status, d) {
    var type = status & 0xF0;
    var ch = status & 0x0F;

    if (type === 0x90 && d[1] > 0) {
        noteOn(ch, d[0], d[1]);
    } else if (type === 0x80 || type === 0x90) {
        noteOff(status, ch, d[0], d[1]);
    } else if (type === 0xC0) {
        programChange(status, d[0]);
    } else if (type === 0xB0 && (d[0] === 120 || d[0] === 123)) {
        // All Sound Off / All Notes Off: pass through and forget held notes
        sendMidi([status, d[0], d[1]]);
        clearState();
    } else {
        sendMidi([status].concat(d));
    }
}

// ---- notes -----------------------------------------------------------------
function noteOn(ch, pitch, vel) {
    var key = ch * 128 + pitch;
    var on = 0x90 | ch;

    if (!held[key]) {
        held[key] = 1;
        outCount[key]++;
    }
    sendMidi([on, pitch, vel]);

    var up = pitch + SHIFT;
    post("Moose Octave: note " + pitch + ", octave " + (octaveOn ? "on" : "off") +
         ", range " + lowNote + "-" + highNote + "\n");
    if (octaveOn && pitch >= lowNote && pitch <= highNote && up <= 127) {
        var upKey = ch * 128 + up;
        if (!doubled[key]) {
            doubled[key] = 1;
            outCount[upKey]++;
        }
        sendMidi([on, up, vel]);
    }
}

function noteOff(status, ch, pitch, vel) {
    var key = ch * 128 + pitch;

    if (held[key]) {
        held[key] = 0;
        release(status, key, vel);
    } else if (outCount[key] === 0) {
        // a note we never saw start (e.g. held before the device loaded)
        sendMidi([status, pitch, vel]);
    }

    if (doubled[key]) {
        doubled[key] = 0;
        release(status, key + SHIFT, vel);
    }
}

// Send a note-off only when nothing else is still holding this output note
// (e.g. you play E4 while E3's octave E4 is sounding).
function release(status, outKey, vel) {
    if (outCount[outKey] > 0) outCount[outKey]--;
    if (outCount[outKey] === 0) {
        sendMidi([status, outKey % 128, vel]);
    }
}

// ---- octave switching --------------------------------------------------------
function programChange(status, pgm) {
    post("Moose Octave: PGM " + pgm + " on channel " + ((status & 0x0F) + 1) + "\n");
    outlet(2, pgm);
    if (pgm === PGM_ON) setOctave(1);
    else if (pgm === PGM_OFF) setOctave(0);
    else if (pgm === PGM_TOGGLE) setOctave(octaveOn ? 0 : 1);
    else sendMidi([status, pgm]);  // other program changes pass through
}

function setOctave(on) {
    on = on ? 1 : 0;
    if (on === octaveOn) {
        outlet(1, octaveOn);
        return;
    }
    octaveOn = on;
    post("Moose Octave: octave " + (octaveOn ? "ON" : "OFF") + "\n");

    if (!octaveOn) {
        // turn off any octave notes still sounding under held keys
        for (var key = 0; key < 16 * 128; key++) {
            if (doubled[key]) {
                doubled[key] = 0;
                release(0x80 | Math.floor(key / 128), key + SHIFT, 0);
            }
        }
    }
    outlet(1, octaveOn);
}

// ---- messages from the device UI --------------------------------------------
function octave(v) {
    setOctave(Number(v) >= 0.5);
}

function low(v) {
    lowNote = clampNote(v);
    post("Moose Octave: low note " + lowNote + "\n");
}

function high(v) {
    highNote = clampNote(v);
    post("Moose Octave: high note " + highNote + "\n");
}

function clampNote(v) {
    v = Math.round(Number(v));
    return v < 0 ? 0 : (v > 127 ? 127 : v);
}

function panic() {
    for (var key = 0; key < 16 * 128; key++) {
        if (outCount[key] > 0) {
            sendMidi([0x80 | Math.floor(key / 128), key % 128, 0]);
        }
    }
    for (var ch = 0; ch < 16; ch++) {
        sendMidi([0xB0 | ch, 123, 0]);
    }
    clearState();
}
