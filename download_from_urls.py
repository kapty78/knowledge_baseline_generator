#!/usr/bin/env python3
"""
Dateien von URLs herunterladen (z. B. Supabase Storage).

Ablauf beim User:
  - User lädt im Frontend Dateien hoch → landen in einem Supabase-Bucket.
  - Frontend ruft unser Backend mit den Links (Supabase-URLs) auf.
  - Backend lädt die Dateien von Supabase herunter und verarbeitet sie
    (z. B. convert_to_png → Gemini → Wissenstext-PDF).

Unterstützt:
  - Öffentliche Supabase-URLs: .../object/public/<bucket>/<path>
  - Signed URLs (temporäre Links für private Buckets)
  - Beliebige andere HTTP(S)-URLs
"""

from __future__ import annotations

import re
import tempfile
from pathlib import Path
from urllib.parse import unquote, urlparse

try:
    import httpx
except ImportError:
    httpx = None


def filename_from_url(url: str, content_disposition: str | None = None) -> str:
    """Versucht einen sicheren Dateinamen aus URL oder Content-Disposition zu gewinnen."""
    if content_disposition:
        # Content-Disposition: attachment; filename="document.pdf"
        m = re.search(r'filename\*?=(?:UTF-8\')?["\']?([^"\';\n]+)["\']?', content_disposition, re.I)
        if m:
            name = m.group(1).strip().strip('"\'')
            name = unquote(name)
            if name and not name.startswith("."):
                base = Path(name).name
                if base:
                    return base
    path = urlparse(url).path.rstrip("/")
    if path:
        name = path.split("/")[-1]
        name = unquote(name)
        if name and "?" not in name:
            return name
    return "download"


def download_file(
    url: str,
    dest_dir: Path,
    *,
    timeout: float = 60.0,
    headers: dict | None = None,
) -> Path | None:
    """
    Lädt eine Datei von url herunter und speichert sie in dest_dir.
    Dateiname aus URL oder Content-Disposition.
    Returns: Pfad zur gespeicherten Datei oder None bei Fehler.
    """
    if not httpx:
        return None
    dest_dir = Path(dest_dir)
    dest_dir.mkdir(parents=True, exist_ok=True)
    try:
        with httpx.Client(timeout=timeout, follow_redirects=True) as client:
            r = client.get(url, headers=headers or {})
            r.raise_for_status()
            name = filename_from_url(url, r.headers.get("content-disposition"))
            # Nur sichere Zeichen im Dateinamen
            name = re.sub(r'[^\w\s\-\.]', '_', name)[:200]
            if not name or name in (".", ".."):
                name = "download"
            path = dest_dir / name
            # Duplikate: datei.pdf → datei_1.pdf
            if path.exists():
                stem, suf = path.stem, path.suffix
                for i in range(1, 100):
                    path = dest_dir / f"{stem}_{i}{suf}"
                    if not path.exists():
                        break
            path.write_bytes(r.content)
            return path
    except Exception:
        return None


def download_from_urls(
    urls: list[str],
    dest_dir: Path | None = None,
    *,
    timeout: float = 60.0,
    headers: dict | None = None,
) -> tuple[Path, list[Path]]:
    """
    Lädt alle Dateien von den angegebenen URLs in ein Verzeichnis.

    Args:
        urls: Liste von URLs (z. B. Supabase Storage – public oder signed).
        dest_dir: Zielordner; wenn None, wird ein temporärer Ordner angelegt.
        timeout: Timeout pro Request in Sekunden.
        headers: Optionale HTTP-Header (z. B. für Auth).

    Returns:
        (ordner_path, list_of_downloaded_file_paths)
        Der Ordner kann an die Pipeline übergeben werden (alle Dateien darin verarbeiten).
    """
    if dest_dir is None:
        dest_dir = Path(tempfile.mkdtemp(prefix="wissenstext_"))
    else:
        dest_dir = Path(dest_dir)
    dest_dir.mkdir(parents=True, exist_ok=True)
    downloaded = []
    for url in urls:
        url = (url or "").strip()
        if not url.startswith(("http://", "https://")):
            continue
        path = download_file(url, dest_dir, timeout=timeout, headers=headers)
        if path is not None:
            downloaded.append(path)
    return dest_dir, downloaded


if __name__ == "__main__":
    import sys
    if len(sys.argv) < 2:
        print("Verwendung: python download_from_urls.py <url1> [url2 ...]")
        print("  Lädt die Dateien in einen temporären Ordner und gibt die Pfade aus.")
        sys.exit(0)
    urls = sys.argv[1:]
    folder, paths = download_from_urls(urls)
    print(f"Ordner: {folder}")
    for p in paths:
        print(f"  {p.name} ({p.stat().st_size} bytes)")
