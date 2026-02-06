#!/usr/bin/env python3
"""
E-Mail-Analyse: Posteingang vs. Postausgang prüfen, Threads matchen (Message-ID / In-Reply-To),
Wissen als Frage-Antwort-Paare extrahieren und in eine Textdatei schreiben.
"""

import email
import re
import os
from pathlib import Path
from email import policy
from email.parser import BytesParser
from email.utils import parsedate_to_datetime
from collections import defaultdict

# Pfade (Defaults für Standalone-Lauf)
BASE = Path(__file__).resolve().parent
POSTEINGANG = BASE / "Posteingang 01.01.25-30.06.25 Reiseteam"
POSTAUSGANG = BASE / "Postausgang 01.01.25-30.06.25 Reiseteam"
OUTPUT_KNOWLEDGE_141 = BASE / "Wissensbasis_Reiseteam_141_Paare.txt"
OUTPUT_KNOWLEDGE_FULL = BASE / "Wissensbasis_Reiseteam_vollstaendig.txt"
OUTPUT_REPORT = BASE / "Analyse_Bericht.txt"

REISETEAM_DOMAIN = "unyflygroup.com"


def run_with_paths(
    posteingang_dir: Path,
    postausgang_dir: Path,
    output_paare: Path,
    output_report: Path,
    support_domain: str | None = None,
) -> int:
    """Führt E-Mail-Pairing aus und schreibt paare.txt + Report. Gibt Anzahl der Paare zurück."""
    domain = (support_domain or REISETEAM_DOMAIN).lower()
    inbox_by_id, inbox_no_id = load_all_emails(posteingang_dir)
    outbox_by_id, outbox_no_id = load_all_emails(postausgang_dir)
    n_inbox = len(inbox_by_id) + len(inbox_no_id)
    n_outbox = len(outbox_by_id) + len(outbox_no_id)

    def is_support(data: dict) -> bool:
        return domain in (data.get("from") or "").lower()

    matched_pairs = []
    outbox_matched = set()
    inbox_matched = set()
    for mid, out_data in outbox_by_id.items():
        if not is_support(out_data):
            continue
        in_reply = parse_message_ids(get_header(out_data["msg"], "In-Reply-To"))
        refs = parse_message_ids(get_header(out_data["msg"], "References"))
        all_refs = list(dict.fromkeys(in_reply + refs))
        found_inbox = None
        for ref_id in all_refs:
            if ref_id in inbox_by_id:
                found_inbox = inbox_by_id[ref_id]
                break
        if found_inbox:
            matched_pairs.append((found_inbox, out_data))
            outbox_matched.add(mid)
            inbox_matched.add(normalize_message_id(get_header(found_inbox["msg"], "Message-ID")))

    report_lines = [
        "=== E-Mail-Analyse: Posteingang vs. Postausgang ===\n",
        f"Posteingang: {n_inbox} E-Mails",
        f"Postausgang: {n_outbox} E-Mails",
        f"Zugeordnete Paare (Support-Antwort auf Kundenanfrage): {len(matched_pairs)}",
        "",
    ]
    output_report.parent.mkdir(parents=True, exist_ok=True)
    output_report.write_text("\n".join(report_lines), encoding="utf-8")

    output_paare.parent.mkdir(parents=True, exist_ok=True)
    with open(output_paare, "w", encoding="utf-8") as out:
        out.write("WISSENSBASIS – KUNDENDIENST-PAARE\n")
        out.write("(Posteingang + Postausgang, zugeordnet per Message-ID/In-Reply-To)\n")
        out.write("=" * 80 + "\n\n")
        for i, (in_data, out_data) in enumerate(matched_pairs, 1):
            out.write(f"--- Paar {i} ---\n")
            out.write(f"Betreff: {in_data['subject']}\n")
            out.write(f"Datum (Eingang): {in_data['date']} | Von: {in_data['from']}\n")
            out.write(f"Datum (Antwort): {out_data['date']}\n")
            out.write("\n[ Anfrage / Kunde ]\n")
            out.write((in_data["body"] or "(kein Text)")[:8000])
            if len(in_data["body"] or "") > 8000:
                out.write("\n... (gekürzt)")
            out.write("\n\n[ Antwort / Reiseteam ]\n")
            out.write((out_data["body"] or "(kein Text)")[:8000])
            if len(out_data["body"] or "") > 8000:
                out.write("\n... (gekürzt)")
            out.write("\n\n")
    print(f"E-Mail-Pairing: {len(matched_pairs)} Paare → {output_paare}")
    return len(matched_pairs)


def normalize_message_id(raw: str) -> str:
    """Message-ID bereinigen für zuverlässiges Matching."""
    if not raw or not raw.strip():
        return ""
    s = raw.strip()
    if s.startswith("<") and s.endswith(">"):
        s = s[1:-1]
    return s.strip()


def parse_message_ids(header_value: str) -> list[str]:
    """In-Reply-To oder References: alle Message-IDs als Liste extrahieren."""
    if not header_value:
        return []
    ids = []
    # Mehrere IDs können in <> stehen, durch Whitespace getrennt
    for part in re.findall(r"<[^>]+>", header_value):
        ids.append(normalize_message_id(part))
    return [x for x in ids if x]


def get_body_text(msg: email.message.Message) -> str:
    """E-Mail-Body als Plain-Text extrahieren (Text/Plain bevorzugt, sonst HTML gestrippt)."""
    text_parts = []
    html_parts = []

    def walk(part):
        if part.get_content_maintype() == "multipart":
            for sub in part.get_payload():
                if sub is not None:
                    walk(sub)
            return
        ct = part.get_content_type()
        try:
            payload = part.get_payload(decode=True)
            if payload is None:
                return
            charset = part.get_content_charset() or "utf-8"
            if isinstance(charset, bytes):
                charset = charset.decode("utf-8", errors="replace")
            try:
                decoded = payload.decode(charset, errors="replace")
            except LookupError:
                decoded = payload.decode("utf-8", errors="replace")
            if ct == "text/plain":
                text_parts.append(decoded)
            elif ct == "text/html":
                html_parts.append(decoded)
        except Exception:
            pass

    walk(msg)
    if text_parts:
        return "\n".join(text_parts).strip()
    if html_parts:
        return strip_html("\n".join(html_parts)).strip()
    return ""


def strip_html(html: str) -> str:
    """Einfaches Entfernen von HTML-Tags und Decodierung von Entities."""
    text = re.sub(r"<script[^>]*>[\s\S]*?</script>", " ", html, flags=re.I)
    text = re.sub(r"<style[^>]*>[\s\S]*?</style>", " ", text, flags=re.I)
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"&nbsp;", " ", text)
    text = re.sub(r"&amp;", "&", text)
    text = re.sub(r"&lt;", "<", text)
    text = re.sub(r"&gt;", ">", text)
    text = re.sub(r"&quot;", '"', text)
    text = re.sub(r"&#(\d+);", lambda m: chr(int(m.group(1))), text)
    text = re.sub(r"&([a-zA-Z]+);", " ", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def parse_eml(path: Path) -> email.message.EmailMessage | None:
    """Eine .eml-Datei parsen."""
    try:
        with open(path, "rb") as f:
            return BytesParser(policy=policy.default).parse(f)
    except Exception:
        return None


def get_header(msg: email.message.Message, name: str) -> str:
    v = msg.get(name)
    return (v or "").strip()


def get_date_str(msg: email.message.Message) -> str:
    d = get_header(msg, "Date")
    if not d:
        return ""
    try:
        dt = parsedate_to_datetime(d)
        return dt.strftime("%Y-%m-%d %H:%M")
    except Exception:
        return d


def load_all_emails(folder: Path) -> tuple[dict[str, dict], list[tuple[Path, dict]]]:
    """
    Lädt alle .eml aus folder.
    Returns: (msg_id -> {path, msg, from, to, date, subject, body}, list of (path, data) ohne Message-ID)
    """
    by_id = {}
    no_id = []
    for f in folder.glob("*.eml"):
        msg = parse_eml(f)
        if msg is None:
            continue
        mid = normalize_message_id(get_header(msg, "Message-ID"))
        body = get_body_text(msg)
        data = {
            "path": f,
            "msg": msg,
            "from": get_header(msg, "From"),
            "to": get_header(msg, "To"),
            "date": get_date_str(msg),
            "subject": get_header(msg, "Subject"),
            "body": body,
        }
        if mid:
            by_id[mid] = data
        else:
            no_id.append((f, data))
    return by_id, no_id


def is_from_reiseteam(data: dict) -> bool:
    return REISETEAM_DOMAIN.lower() in (data.get("from") or "").lower()


def main():
    print("Lade Posteingang...")
    inbox_by_id, inbox_no_id = load_all_emails(POSTEINGANG)
    print("Lade Postausgang...")
    outbox_by_id, outbox_no_id = load_all_emails(POSTAUSGANG)

    # Statistik
    n_inbox = len(inbox_by_id) + len(inbox_no_id)
    n_outbox = len(outbox_by_id) + len(outbox_no_id)

    # Match: Für jede Postausgang-Mail die referenzierte Posteingang-Mail finden
    # (Antwort des Reiseteams bezieht sich auf Kundenmail per In-Reply-To / References)
    matched_pairs = []  # [(inbox_data, outbox_data), ...]
    outbox_matched = set()  # outbox Message-IDs die schon zugeordnet
    inbox_matched = set()   # inbox Message-IDs die schon zugeordnet

    for mid, out_data in outbox_by_id.items():
        in_reply = parse_message_ids(get_header(out_data["msg"], "In-Reply-To"))
        refs = parse_message_ids(get_header(out_data["msg"], "References"))
        all_refs = list(dict.fromkeys(in_reply + refs))
        found_inbox = None
        for ref_id in all_refs:
            if ref_id in inbox_by_id:
                found_inbox = inbox_by_id[ref_id]
                break
        if found_inbox:
            matched_pairs.append((found_inbox, out_data))
            outbox_matched.add(mid)
            inbox_matched.add(normalize_message_id(get_header(found_inbox["msg"], "Message-ID")))

    # Auch: Posteingang-Mails die auf andere Posteingang-Mails antworten (Kunde antwortet) – optional
    # Wir fokussieren auf: Kunde fragt (Posteingang) -> Reiseteam antwortet (Postausgang)

    report_lines = [
        "=== Analyse: Posteingang vs. Postausgang (Reiseteam 01.01.25–30.06.25) ===\n",
        f"Posteingang: {n_inbox} E-Mails ({len(inbox_by_id)} mit Message-ID, {len(inbox_no_id)} ohne)",
        f"Postausgang: {n_outbox} E-Mails ({len(outbox_by_id)} mit Message-ID, {len(outbox_no_id)} ohne)",
        "",
        "Trennung: Ja – Posteingang = eingehende Mails (an reiseteam@…), Postausgang = gesendete Mails (von reiseteam@…).",
        "",
        "Fokus: Kundendienstleistungen (zugeordnete Paare)",
        f"  – {len(matched_pairs)} Paare: Kundenanfrage (Posteingang) + Reiseteam-Antwort (Postausgang)",
        f"  – Diese Paare = Wissensbasis für Support/Rack (Datei: Wissensbasis_Reiseteam_141_Paare.txt)",
        "",
        "Weitere Statistik:",
        f"  – Postausgang ohne zugeordnete Posteingang-Mail: {n_outbox - len(outbox_matched)}",
        f"  – Posteingang mit gefundener Antwort: {len(inbox_matched)}",
        "",
    ]

    with open(OUTPUT_REPORT, "w", encoding="utf-8") as f:
        f.write("\n".join(report_lines))

    print("\n".join(report_lines))

    # Wissensbasis: Fokus nur auf die 141 Kundendienstleistungs-Paare (für Support/Rack)
    with open(OUTPUT_KNOWLEDGE_141, "w", encoding="utf-8") as out:
        out.write("WISSENSBASIS REISETEAM – 141 KUNDENDIENSTLEISTUNGS-PAARE\n")
        out.write("(E-Mails 01.01.25–30.06.25 | Posteingang + Postausgang, zugeordnet per Message-ID/In-Reply-To)\n")
        out.write("=" * 80 + "\n\n")

        for i, (in_data, out_data) in enumerate(matched_pairs, 1):
            out.write(f"--- Paar {i} ---\n")
            out.write(f"Betreff: {in_data['subject']}\n")
            out.write(f"Datum (Eingang): {in_data['date']} | Von: {in_data['from']}\n")
            out.write(f"Datum (Antwort): {out_data['date']}\n")
            out.write("\n[ Anfrage / Kunde ]\n")
            out.write((in_data["body"] or "(kein Text)")[:8000])
            if len(in_data["body"] or "") > 8000:
                out.write("\n... (gekürzt)")
            out.write("\n\n[ Antwort / Reiseteam ]\n")
            out.write((out_data["body"] or "(kein Text)")[:8000])
            if len(out_data["body"] or "") > 8000:
                out.write("\n... (gekürzt)")
            out.write("\n\n")

    # Optional: vollständige Wissensbasis (inkl. ungematchte Mails)
    with open(OUTPUT_KNOWLEDGE_FULL, "w", encoding="utf-8") as out:
        out.write("WISSENSBASIS REISETEAM – VOLLSTÄNDIG (alle Bereiche)\n")
        out.write("=" * 80 + "\n\n")
        for i, (in_data, out_data) in enumerate(matched_pairs, 1):
            out.write(f"--- Paar {i} ---\n")
            out.write(f"Betreff: {in_data['subject']}\n")
            out.write(f"Datum (Eingang): {in_data['date']} | Von: {in_data['from']}\n")
            out.write(f"Datum (Antwort): {out_data['date']}\n")
            out.write("\n[ Anfrage / Kunde ]\n")
            out.write((in_data["body"] or "(kein Text)")[:8000])
            if len(in_data["body"] or "") > 8000:
                out.write("\n... (gekürzt)")
            out.write("\n\n[ Antwort / Reiseteam ]\n")
            out.write((out_data["body"] or "(kein Text)")[:8000])
            if len(out_data["body"] or "") > 8000:
                out.write("\n... (gekürzt)")
            out.write("\n\n")
        out.write("\n" + "=" * 80 + "\n")
        out.write("POSTAUSGANG OHNE ZUGEORDNETE EINGANGSMAIL\n")
        out.write("=" * 80 + "\n\n")
        for mid, out_data in outbox_by_id.items():
            if mid in outbox_matched:
                continue
            out.write(f"--- Betreff: {out_data['subject']} | {out_data['date']} ---\n")
            out.write((out_data["body"] or "(kein Text)")[:4000])
            if len(out_data["body"] or "") > 4000:
                out.write("\n... (gekürzt)")
            out.write("\n\n")
        out.write("\n" + "=" * 80 + "\n")
        out.write("POSTEINGANG OHNE GEFUNDENE ANTWORT IM POSTAUSGANG\n")
        out.write("=" * 80 + "\n\n")
        for mid, in_data in inbox_by_id.items():
            if mid in inbox_matched:
                continue
            out.write(f"--- Betreff: {in_data['subject']} | {in_data['date']} | Von: {in_data['from']} ---\n")
            out.write((in_data["body"] or "(kein Text)")[:4000])
            if len(in_data["body"] or "") > 4000:
                out.write("\n... (gekürzt)")
            out.write("\n\n")
        for path, in_data in inbox_no_id:
            out.write(f"--- [ohne Message-ID] Betreff: {in_data['subject']} | {in_data['date']} ---\n")
            out.write((in_data["body"] or "(kein Text)")[:4000])
            if len(in_data["body"] or "") > 4000:
                out.write("\n... (gekürzt)")
            out.write("\n\n")

    print(f"\nWissensbasis (141 Paare, Fokus): {OUTPUT_KNOWLEDGE_141}")
    print(f"Wissensbasis (vollständig):      {OUTPUT_KNOWLEDGE_FULL}")
    print(f"Bericht:                        {OUTPUT_REPORT}")


if __name__ == "__main__":
    import argparse
    p = argparse.ArgumentParser(description="E-Mail-Pairing: Posteingang + Postausgang → Paare")
    p.add_argument("--posteingang", type=Path, help="Ordner mit eingehenden .eml")
    p.add_argument("--postausgang", type=Path, help="Ordner mit ausgehenden .eml")
    p.add_argument("--output-dir", type=Path, help="Ordner für paare.txt und Bericht")
    p.add_argument("--support-domain", type=str, default="", help="E-Mail-Domain des Supports (z.B. unyflygroup.com)")
    args = p.parse_args()
    if args.output_dir and args.posteingang and args.postausgang:
        run_with_paths(
            args.posteingang,
            args.postausgang,
            args.output_dir / "paare.txt",
            args.output_dir / "Analyse_Bericht.txt",
            support_domain=args.support_domain or None,
        )
    else:
        main()
