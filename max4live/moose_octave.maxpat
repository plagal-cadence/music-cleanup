{
 "patcher": {
  "fileversion": 1,
  "appversion": {
   "major": 8,
   "minor": 6,
   "revision": 0,
   "architecture": "x64",
   "modernui": 1
  },
  "classnamespace": "box",
  "rect": [
   100,
   100,
   900,
   420
  ],
  "openinpresentation": 0,
  "default_fontsize": 10.0,
  "default_fontname": "Arial Bold",
  "gridsize": [
   8.0,
   8.0
  ],
  "boxes": [
   {
    "box": {
     "id": "obj-midiin",
     "maxclass": "newobj",
     "text": "midiin",
     "numinlets": 1,
     "numoutlets": 1,
     "outlettype": [
      "int"
     ],
     "patching_rect": [
      30,
      30,
      50,
      22
     ]
    }
   },
   {
    "box": {
     "id": "obj-js",
     "maxclass": "newobj",
     "text": "js moose_octave.js",
     "numinlets": 1,
     "numoutlets": 3,
     "outlettype": [
      "",
      "",
      ""
     ],
     "patching_rect": [
      30,
      260,
      180,
      22
     ],
     "saved_object_attributes": {
      "filename": "moose_octave.js",
      "parameter_enable": 0
     }
    }
   },
   {
    "box": {
     "id": "obj-midiout",
     "maxclass": "newobj",
     "text": "midiout",
     "numinlets": 1,
     "numoutlets": 0,
     "outlettype": [],
     "patching_rect": [
      30,
      330,
      60,
      22
     ]
    }
   },
   {
    "box": {
     "id": "obj-toggle",
     "maxclass": "live.toggle",
     "numinlets": 1,
     "numoutlets": 1,
     "outlettype": [
      ""
     ],
     "parameter_enable": 1,
     "varname": "Octave",
     "patching_rect": [
      250,
      30,
      40,
      40
     ],
     "presentation": 1,
     "presentation_rect": [
      10,
      30,
      44,
      44
     ],
     "saved_attribute_attributes": {
      "valueof": {
       "parameter_longname": "Octave",
       "parameter_shortname": "Octave",
       "parameter_type": 2,
       "parameter_mmin": 0,
       "parameter_mmax": 1,
       "parameter_initial_enable": 1,
       "parameter_initial": [
        0
       ],
       "parameter_enum": [
        "off",
        "on"
       ]
      }
     }
    }
   },
   {
    "box": {
     "id": "obj-prep-oct",
     "maxclass": "newobj",
     "text": "prepend octave",
     "numinlets": 1,
     "numoutlets": 1,
     "outlettype": [
      ""
     ],
     "patching_rect": [
      250,
      90,
      95,
      22
     ]
    }
   },
   {
    "box": {
     "id": "obj-set",
     "maxclass": "message",
     "text": "set $1",
     "numinlets": 2,
     "numoutlets": 1,
     "outlettype": [
      ""
     ],
     "patching_rect": [
      230,
      320,
      50,
      22
     ]
    }
   },
   {
    "box": {
     "id": "obj-low",
     "maxclass": "live.numbox",
     "numinlets": 1,
     "numoutlets": 2,
     "outlettype": [
      "",
      "float"
     ],
     "parameter_enable": 1,
     "varname": "Low",
     "patching_rect": [
      370,
      30,
      50,
      15
     ],
     "presentation": 1,
     "presentation_rect": [
      80,
      40,
      44,
      15
     ],
     "saved_attribute_attributes": {
      "valueof": {
       "parameter_longname": "Low Note",
       "parameter_shortname": "Low",
       "parameter_type": 1,
       "parameter_mmin": 0,
       "parameter_mmax": 127,
       "parameter_initial_enable": 1,
       "parameter_initial": [
        60
       ],
       "parameter_unitstyle": 8
      }
     }
    }
   },
   {
    "box": {
     "id": "obj-high",
     "maxclass": "live.numbox",
     "numinlets": 1,
     "numoutlets": 2,
     "outlettype": [
      "",
      "float"
     ],
     "parameter_enable": 1,
     "varname": "High",
     "patching_rect": [
      450,
      30,
      50,
      15
     ],
     "presentation": 1,
     "presentation_rect": [
      80,
      80,
      44,
      15
     ],
     "saved_attribute_attributes": {
      "valueof": {
       "parameter_longname": "High Note",
       "parameter_shortname": "High",
       "parameter_type": 1,
       "parameter_mmin": 0,
       "parameter_mmax": 127,
       "parameter_initial_enable": 1,
       "parameter_initial": [
        127
       ],
       "parameter_unitstyle": 8
      }
     }
    }
   },
   {
    "box": {
     "id": "obj-prep-low",
     "maxclass": "newobj",
     "text": "prepend low",
     "numinlets": 1,
     "numoutlets": 1,
     "outlettype": [
      ""
     ],
     "patching_rect": [
      370,
      90,
      75,
      22
     ]
    }
   },
   {
    "box": {
     "id": "obj-prep-high",
     "maxclass": "newobj",
     "text": "prepend high",
     "numinlets": 1,
     "numoutlets": 1,
     "outlettype": [
      ""
     ],
     "patching_rect": [
      450,
      90,
      80,
      22
     ]
    }
   },
   {
    "box": {
     "id": "obj-panic",
     "maxclass": "live.text",
     "text": "Panic",
     "texton": "Panic",
     "mode": 0,
     "numinlets": 1,
     "numoutlets": 2,
     "outlettype": [
      "",
      ""
     ],
     "parameter_enable": 1,
     "varname": "Panic",
     "patching_rect": [
      560,
      30,
      50,
      18
     ],
     "presentation": 1,
     "presentation_rect": [
      145,
      80,
      50,
      18
     ],
     "saved_attribute_attributes": {
      "valueof": {
       "parameter_longname": "Panic",
       "parameter_shortname": "Panic",
       "parameter_type": 2,
       "parameter_mmin": 0,
       "parameter_mmax": 1,
       "parameter_initial_enable": 1,
       "parameter_initial": [
        0
       ],
       "parameter_enum": [
        "off",
        "on"
       ]
      }
     }
    }
   },
   {
    "box": {
     "id": "obj-sel",
     "maxclass": "newobj",
     "text": "sel 1",
     "numinlets": 2,
     "numoutlets": 2,
     "outlettype": [
      "bang",
      ""
     ],
     "patching_rect": [
      560,
      90,
      40,
      22
     ]
    }
   },
   {
    "box": {
     "id": "obj-panicmsg",
     "maxclass": "message",
     "text": "panic",
     "numinlets": 2,
     "numoutlets": 1,
     "outlettype": [
      ""
     ],
     "patching_rect": [
      560,
      130,
      45,
      22
     ]
    }
   },
   {
    "box": {
     "id": "obj-pgm",
     "maxclass": "number",
     "numinlets": 1,
     "numoutlets": 2,
     "outlettype": [
      "",
      "bang"
     ],
     "parameter_enable": 0,
     "ignoreclick": 1,
     "patching_rect": [
      130,
      320,
      50,
      22
     ],
     "presentation": 1,
     "presentation_rect": [
      145,
      40,
      50,
      20
     ]
    }
   },
   {
    "box": {
     "id": "lbl-title",
     "maxclass": "live.comment",
     "text": "Moose Octave",
     "numinlets": 1,
     "numoutlets": 0,
     "patching_rect": [
      650,
      30,
      100,
      18
     ],
     "presentation": 1,
     "presentation_rect": [
      8,
      4,
      120,
      18
     ]
    }
   },
   {
    "box": {
     "id": "lbl-oct",
     "maxclass": "live.comment",
     "text": "Octave",
     "numinlets": 1,
     "numoutlets": 0,
     "patching_rect": [
      650,
      50,
      100,
      18
     ],
     "presentation": 1,
     "presentation_rect": [
      10,
      76,
      50,
      18
     ]
    }
   },
   {
    "box": {
     "id": "lbl-low",
     "maxclass": "live.comment",
     "text": "Low",
     "numinlets": 1,
     "numoutlets": 0,
     "patching_rect": [
      650,
      70,
      100,
      18
     ],
     "presentation": 1,
     "presentation_rect": [
      80,
      24,
      44,
      18
     ]
    }
   },
   {
    "box": {
     "id": "lbl-high",
     "maxclass": "live.comment",
     "text": "High",
     "numinlets": 1,
     "numoutlets": 0,
     "patching_rect": [
      650,
      90,
      100,
      18
     ],
     "presentation": 1,
     "presentation_rect": [
      80,
      64,
      44,
      18
     ]
    }
   },
   {
    "box": {
     "id": "lbl-pgm",
     "maxclass": "live.comment",
     "text": "Last PGM",
     "numinlets": 1,
     "numoutlets": 0,
     "patching_rect": [
      650,
      110,
      100,
      18
     ],
     "presentation": 1,
     "presentation_rect": [
      145,
      24,
      60,
      18
     ]
    }
   },
   {
    "box": {
     "id": "lbl-help",
     "maxclass": "live.comment",
     "text": "PGM 0 = on   PGM 1 = off   PGM 2 = toggle",
     "numinlets": 1,
     "numoutlets": 0,
     "patching_rect": [
      650,
      130,
      240,
      18
     ],
     "presentation": 1,
     "presentation_rect": [
      8,
      140,
      250,
      18
     ]
    }
   }
  ],
  "lines": [
   {
    "patchline": {
     "source": [
      "obj-midiin",
      0
     ],
     "destination": [
      "obj-js",
      0
     ]
    }
   },
   {
    "patchline": {
     "source": [
      "obj-js",
      0
     ],
     "destination": [
      "obj-midiout",
      0
     ]
    }
   },
   {
    "patchline": {
     "source": [
      "obj-toggle",
      0
     ],
     "destination": [
      "obj-prep-oct",
      0
     ]
    }
   },
   {
    "patchline": {
     "source": [
      "obj-prep-oct",
      0
     ],
     "destination": [
      "obj-js",
      0
     ]
    }
   },
   {
    "patchline": {
     "source": [
      "obj-js",
      1
     ],
     "destination": [
      "obj-set",
      0
     ]
    }
   },
   {
    "patchline": {
     "source": [
      "obj-set",
      0
     ],
     "destination": [
      "obj-toggle",
      0
     ]
    }
   },
   {
    "patchline": {
     "source": [
      "obj-low",
      0
     ],
     "destination": [
      "obj-prep-low",
      0
     ]
    }
   },
   {
    "patchline": {
     "source": [
      "obj-prep-low",
      0
     ],
     "destination": [
      "obj-js",
      0
     ]
    }
   },
   {
    "patchline": {
     "source": [
      "obj-high",
      0
     ],
     "destination": [
      "obj-prep-high",
      0
     ]
    }
   },
   {
    "patchline": {
     "source": [
      "obj-prep-high",
      0
     ],
     "destination": [
      "obj-js",
      0
     ]
    }
   },
   {
    "patchline": {
     "source": [
      "obj-panic",
      0
     ],
     "destination": [
      "obj-sel",
      0
     ]
    }
   },
   {
    "patchline": {
     "source": [
      "obj-sel",
      0
     ],
     "destination": [
      "obj-panicmsg",
      0
     ]
    }
   },
   {
    "patchline": {
     "source": [
      "obj-panicmsg",
      0
     ],
     "destination": [
      "obj-js",
      0
     ]
    }
   },
   {
    "patchline": {
     "source": [
      "obj-js",
      2
     ],
     "destination": [
      "obj-pgm",
      0
     ]
    }
   }
  ],
  "dependency_cache": [
   {
    "name": "moose_octave.js",
    "bootpath": ".",
    "type": "TEXT",
    "implicit": 1
   }
  ],
  "autosave": 0
 }
}