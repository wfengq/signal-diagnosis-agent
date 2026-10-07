# D051 real-data check on EGFxSet (validation appendix)

Date: 2026-10-07. Deterministic only: no model call, no planner, no rule or
threshold change. This appendix records how the D051 paired-reference scan and
the existing clipping checks behave on real hardware-processed audio. It is not
an accuracy study and does not replace any recorded result; the accepted V0.2
79/80 is unaffected.

## Data

EGFxSet: Pedroza, H., Meza, G., and Roman, I. R., "EGFxSet: Electric guitar
tones processed through real effects of distortion, modulation, delay and
reverb", ISMIR 2022 late-breaking demo, doi:10.5281/zenodo.7044411, licensed
CC BY 4.0. No audio is committed.

Fixed sample: neck pickup, strings 1–6 at frets 0 and 12 (12 notes), in six
versions: `Clean` (the reference), three distortion pedals at full gain
(`TubeScreamer`, `RAT`, `BluesDriver`), and two effects that do not distort
(`Chorus`, `Phaser`) as controls. 72 files, mono 24-bit 48 kHz, 5 s each.

- `sample_manifest.json`: zip, member path, SHA-256 and size of every file.
- `tools/fetch.py` (with `tools/rangezip.py`): downloads exactly these members
  with HTTP range requests, without the full archives.
- `tools/analyze.py`: produces `results.json` from the product code.

Reproduce: `python3 -I tools/fetch.py <data_dir>`, then
`PYTHONPATH=src python tools/analyze.py <data_dir> results.json`.

## Per pair

For each effect version against the clean version of the same note:

- **scan:** `localize_faults` in `paired_reference` with a diagnosis that
  supports harmonic distortion, so every reference-growth window is shown;
- **withheld:** the same with no harmonic diagnosis (§27.1);
- **whole file:** the product's whole-file paired gate on the full files;
- **single file:** `localize_faults` in `single_signal` on the effect file.

## Results (11 analyzable notes per version)

| Version | Scan: notes with a harmonic interval | Whole file: harmonic growth | Whole file: not comparable | Single file: notes with a clipping interval |
|---|---|---|---|---|
| Clean (identical pair) | 0 | 0 | 7 | 11 |
| TubeScreamer | 4 | 0 | 8 | 8 |
| RAT | 10 | 2 | 9 | 8 |
| BluesDriver | 4 | 1 | 7 | 11 |
| Chorus (control) | 3 | 0 | 8 | 11 |
| Phaser (control) | 5 | 0 | 7 | 10 |

With no harmonic diagnosis, no paired harmonic interval is shown for any pair.

## Findings

1. **Per-window reference growth is fooled by time-varying filtering.** Chorus
   and phaser change the relative level of each harmonic over time. In a single
   0.25 s window this looks like even-harmonic growth: 3 of 11 chorus notes and
   5 of 11 phaser notes produce harmonic intervals (up to 1.75 s). The
   whole-file judgment, which averages over the file, flags none of them. This
   is why D051 shows paired harmonic intervals only when the diagnosis supports
   harmonic distortion, and otherwise reports only the number of windows.
2. **The scan finds more of the real distortion than the whole-file judgment.**
   RAT is found on 10 of 11 notes by the scan and 2 by the whole file. Most
   whole-file comparisons are not comparable (finding 3). Because the shown
   intervals now depend on the diagnosis, the benefit applies only when the
   diagnosis adopts harmonic distortion. How often the live planner does so on
   such pairs is not measured here; that needs a real-model run.
3. **Peak-normalized recordings trip the full-scale clipping check.** The
   files peak at 0.88–1.00 of full scale. With the demonstration threshold of
   0.99, single-file clipping intervals appear on all 11 clean notes, and a
   clean reference judged as clipping makes the whole-file paired gate fail.
   This is an existing product limitation, not specific to D051 (OQ-025).
4. **One WAV is rejected.** `Clean/Neck/1-0.wav` has a `data` chunk one byte
   longer than a whole number of 3-byte frames; the decoder rejects it, so note
   1-0 is excluded for every version (OQ-026).

These are guitar notes through effects, not the S1 setting of a test signal
through a device, so they are a stress test rather than a measure of product
accuracy.
