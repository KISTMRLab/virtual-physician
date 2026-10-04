"""Prepare explicitly selected public educational text for human review."""
from __future__ import annotations

import argparse
import json
import re
import urllib.request
from datetime import date
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urlparse


class TextParser(HTMLParser):
    def __init__(self):
        super().__init__(); self.parts = []; self.skip = 0
    def handle_starttag(self, tag, attrs):
        if tag in {"script", "style", "nav", "footer"}: self.skip += 1
        if tag in {"p", "h1", "h2", "h3", "li", "br"}: self.parts.append("\n")
    def handle_endtag(self, tag):
        if tag in {"script", "style", "nav", "footer"}: self.skip = max(0, self.skip - 1)
    def handle_data(self, data):
        if not self.skip: self.parts.append(data)


def import_source(url: str, title: str, source_id: str, reviewed_at: str,
                  out: Path, source_file: Path | None = None) -> dict:
    if urlparse(url).scheme != "https": raise ValueError("source URL must use HTTPS")
    date.fromisoformat(reviewed_at)
    if not title.strip() or not source_id.strip(): raise ValueError("title and source ID required")
    if source_file:
        raw = source_file.read_bytes()
    else:
        req = urllib.request.Request(url, headers={"User-Agent": "PaperReach selected educational source importer"})
        with urllib.request.urlopen(req, timeout=20) as response: raw = response.read(2_000_001)
        if len(raw) > 2_000_000: raise ValueError("page exceeds 2 MB")
    parser = TextParser(); parser.feed(raw.decode("utf-8-sig", errors="replace"))
    text = re.sub(r"[ \t]+", " ", "".join(parser.parts))
    text = re.sub(r"\n\s*\n+", "\n", text).strip()
    if len(text) < 50: raise ValueError("too little readable text")
    row = {"source_id": source_id, "title": title, "url": url, "reviewed_at": reviewed_at, "text": text}
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("a", encoding="utf-8") as f: f.write(json.dumps(row, ensure_ascii=False) + "\n")
    return row


def main():
    p = argparse.ArgumentParser(description="Prepare a selected public page for review and local retrieval")
    p.add_argument("url"); p.add_argument("--file", type=Path); p.add_argument("--title", required=True)
    p.add_argument("--id", required=True); p.add_argument("--reviewed-at", required=True, help="date a person checked the imported text, YYYY-MM-DD")
    p.add_argument("--out", type=Path, required=True)
    a = p.parse_args()
    row = import_source(a.url, a.title, a.id, a.reviewed_at, a.out, a.file)
    print(json.dumps({"source_id": row["source_id"], "characters": len(row["text"]), "out": str(a.out)}))
    print("Review the extracted text, its source terms, and the explanation script before serving.")


if __name__ == "__main__": main()
