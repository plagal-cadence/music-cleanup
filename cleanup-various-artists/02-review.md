python.exe .\03-apply.py --apply

Where the medium and review rows are

Open 02-artist_proposals.xlsx (or the .csv twin) and use the autofilter on the confidence column — every one of the 452 tracks is a row there, tagged high, medium, or review.

medium (29) — a proposed artist is filled in and the evidence column says why, but Spotify couldn't fully confirm it. The apply column is deliberately blank; type yes on the ones you accept, or run 03-apply.py --include-medium --apply to take all 29.
review (206) — proposed_artist is empty and the tag stays Various. Look at the candidates column: it lists what Spotify returned so you can judge, and notes says why nothing was trusted.

Time-Life Orchestral Blockbusters A+B	10	4
Romantic Clarinet for Lovers	6	–
Reader's Digest 100 Most Beautiful Melodies	5	3
Great Melodies from the Classics	2	14
Melody and Medley (Durham Cathedral organ)	2	17
Most Beautiful Melodies	–	33
Rejoice / CBS Christmas Album	–	20 each
Voyager Italian Mandolins, Joy To The World, Romantic Piano for Lovers	–	15 each
Smooth Africa, Pops In Love, Come Let Us Adore Him, Heart of Christmas Jazz Piano	–	10–12 each



11 albums, all of them entirely missing — no album is partly converted, so this isn't a matching failure. Every one comes from the same source root: M:\MusicFromCDsRussFlac\_Classical.

`Reader's Digest-100 World's Most Beautiful Melodies` Album tag changed to `Reader's Digest 100 World's Most Beautiful Melodies (Disc 1)`
`Most Beautiful Melodies` Album tag changed to `Reader's Digest 100 World's Most Beautiful Melodies (Disc 2)`
`Great Melodies from the Classics`
`Time-Life Library of  Classical Favorites - Orchestral Blockbusters Disk A` need to remove the double space characters in Album and the file names
`Time-Life Library of  Classical Favorites - Orchestral Blockbusters Disk B` need to remove the double space characters in Album and the file names
`Time-Life Library of  Classical Favorites - Romantic Piano Concertos, Disc 1` need to remove the double space characters in Album and the file names
`Time-Life Library of  Classical Favorites - Romantic Piano Concertos, Disc 2` need to remove the double space characters in Album and the file names
`Pops In Love`
`Romantic Clarinet for Lovers`
`Romantic Piano for Lovers`

That's the whole 168-track shortfall.

The wider cause: the Russ classical root has never really been converted. Of its 49 album folders, exactly 1 has a counterpart in M:\Music\Classical\MusicFromCDsFromFlac — the other 48 don't (Bolero/Daphnis, the Three Tenors, the Mozart Collection discs, Classics Up To Date 4 & 5, the Virtuoso Violin discs, Zamfir Disc 2, and so on). 

Tellingly, Time-Life Library of Classical Favorites Disc A is in the destination while Disc B isn't — Disc A came from the other classical source, M:\MusicFlacSource\Classical\MusicFromCDs, and all 38 of that root's albums converted fine.

So the FLAC tags for these 11 will still be corrected on the coming apply run; the MP3 side simply has nothing to write to yet. When you next convert that root, the MP3s will inherit the fixed Artist tags from the FLACs — no second pass needed. If you'd rather they pick up MP3s later anyway, re-running 01-scan.py then 03-apply.py after the conversion will fill them in (already-correct FLACs are skipped as already_set).