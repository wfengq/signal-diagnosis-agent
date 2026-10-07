"""Fetch a fixed EGFxSet sample (CC BY 4.0, doi:10.5281/zenodo.7044411) by range requests."""
import hashlib, json, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from rangezip import open_zip  # noqa: E402

EFFECTS = ("Clean", "TubeScreamer", "RAT", "BluesDriver", "Chorus", "Phaser")
NOTES = [f"{string}-{fret}" for string in range(1, 7) for fret in (0, 12)]
PICKUP = "Neck"

out = Path(sys.argv[1]); out.mkdir(parents=True, exist_ok=True)
manifest = []
for effect in EFFECTS:
    z = open_zip(f"{effect}.zip")
    names = set(z.namelist())
    for note in NOTES:
        member = next(n for n in names if n.endswith(f"/{PICKUP}/{note}.wav"))
        target = out / effect / f"{note}.wav"
        data = target.read_bytes() if target.exists() else z.read(member)
        target.parent.mkdir(exist_ok=True)
        target.write_bytes(data)
        manifest.append({"zip": f"{effect}.zip", "member": member, "sha256": hashlib.sha256(data).hexdigest(), "bytes": len(data)})
    print(effect, "done", flush=True)
(out / "sample_manifest.json").write_text(json.dumps(manifest, indent=1) + "\n")
