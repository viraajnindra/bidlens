"""Download official demo PDFs, verify hashes, and preserve page-numbered text."""

import hashlib
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from backend.ingest import download, parse_pdf
from backend.models import ROOT


def main():
    fixture = json.loads((ROOT / "data/demo.json").read_text())
    folder = ROOT / "data/sources"
    folder.mkdir(parents=True, exist_ok=True)
    for doc in fixture["documents"]:
        path = folder / (doc["id"] + ".pdf")
        if path.exists() and hashlib.sha256(path.read_bytes()).hexdigest() == doc["sha256"]:
            print(f"Already verified: {doc['name']}")
        else:
            temporary = path.with_suffix(".download")
            try:
                download(doc["url"], temporary)
                if hashlib.sha256(temporary.read_bytes()).hexdigest() != doc["sha256"]:
                    raise ValueError(
                        f"{doc['name']} changed upstream. Keeping the reviewed snapshot intact; inspect the new source before updating the fixture."
                    )
                temporary.replace(path)
            finally:
                temporary.unlink(missing_ok=True)
            print(f"Downloaded and verified: {doc['name']}")
        pages = parse_pdf(path)
        path.with_suffix(".json").write_text(json.dumps(pages, ensure_ascii=False, indent=2) + "\n")
        print(f"  {len(pages)} pages, SHA-256 {doc['sha256'][:16]}…")


if __name__ == "__main__":
    main()
