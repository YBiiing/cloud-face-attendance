"""Explicitly download official research weights. Runtime never downloads models."""
import hashlib
import json
import os
from pathlib import Path
import urllib.request
import zipfile

URL = "https://github.com/deepinsight/insightface/releases/download/v0.7/buffalo_l.zip"
FILES = ("det_10g.onnx", "w600k_r50.onnx")


def main():
    root = Path(os.getenv("MODEL_DIR", "models"))
    target = root / "buffalo_l"
    target.mkdir(parents=True, exist_ok=True)
    archive = root / "buffalo_l.download.zip"
    if not all((target / name).is_file() for name in FILES):
        print("Downloading official buffalo_l weights (non-commercial research use).", flush=True)
        with urllib.request.urlopen(URL, timeout=60) as response, archive.open("wb") as output:
            while chunk := response.read(1024 * 1024):
                output.write(chunk)
        with zipfile.ZipFile(archive) as bundle:
            for name in FILES:
                matches = [info for info in bundle.infolist() if Path(info.filename).name == name]
                if len(matches) != 1 or matches[0].file_size > 512 * 1024 * 1024:
                    raise RuntimeError("Unexpected model archive contents")
                with bundle.open(matches[0]) as source, (target / name).open("wb") as output:
                    while chunk := source.read(1024 * 1024):
                        output.write(chunk)
        archive.unlink()
    manifest = {"source": URL, "license": "non-commercial research only",
                "sha256": {name: hashlib.file_digest((target / name).open('rb'), 'sha256').hexdigest() for name in FILES}}
    (target / "manifest.json").write_text(json.dumps(manifest, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(manifest, indent=2))


if __name__ == "__main__":
    main()
