#!/usr/bin/env python3
"""
Wissenstext (Markdown mit ##-Abschnitten) in ein PDF umwandeln.
Jeder Abschnitt, der mit „## “ beginnt, startet auf einer eigenen Seite.

Eingabe: Wissenstext_Support_Agent_LLM.txt
Ausgabe: Wissenstext_Support_Agent_LLM.pdf

Voraussetzung: pip install reportlab
  Ausführen: python wissenstext_zu_pdf.py
"""

import re
from pathlib import Path

from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, PageBreak
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

BASE = Path(__file__).resolve().parent
INPUT_TXT = BASE / "Wissenstext_Support_Agent_LLM.txt"
OUTPUT_PDF = BASE / "Wissenstext_Support_Agent_LLM.pdf"


def split_into_sections(text: str) -> list[tuple[str, str]]:
    """Zerlegt den Text in Abschnitte: (Überschrift, Inhalt). Überschrift ohne '## '."""
    sections = []
    # Alle Zeilen, die mit "## " beginnen, als Trennpunkt
    pattern = re.compile(r"^## (.+)$", re.MULTILINE)
    matches = list(pattern.finditer(text))
    if not matches:
        # Kein ## gefunden: ganzer Text als ein Abschnitt
        title = "Wissenstext"
        body = text.strip()
        if body:
            sections.append((title, body))
        return sections

    for i, m in enumerate(matches):
        title = m.group(1).strip()
        start = m.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        body = text[start:end].strip()
        sections.append((title, body))
    return sections


def build_pdf(input_path: Path, output_path: Path) -> None:
    text = input_path.read_text(encoding="utf-8")
    sections = split_into_sections(text)
    if not sections:
        raise SystemExit("Keine Abschnitte gefunden.")

    doc = SimpleDocTemplate(
        str(output_path),
        pagesize=A4,
        leftMargin=2 * cm,
        rightMargin=2 * cm,
        topMargin=2 * cm,
        bottomMargin=2 * cm,
    )
    styles = getSampleStyleSheet()
    # Eigenen Stil für Überschriften (größer, Abstand)
    title_style = ParagraphStyle(
        name="SectionTitle",
        parent=styles["Heading1"],
        fontName="Helvetica-Bold",
        fontSize=14,
        spaceAfter=12,
    )
    body_style = ParagraphStyle(
        name="Body",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=10,
        leading=14,
        spaceAfter=6,
    )
    bullet_style = ParagraphStyle(
        name="Bullet",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=10,
        leading=14,
        leftIndent=20,
        spaceAfter=4,
    )

    story = []
    for i, (title, body) in enumerate(sections):
        if i > 0:
            story.append(PageBreak())
        story.append(Paragraph(escape_html(title), title_style))
        story.append(Spacer(1, 0.5 * cm))
        for line in body.splitlines():
            line = line.strip()
            if not line:
                continue
            if line.startswith("- "):
                content = escape_html(line[2:].strip())
                story.append(Paragraph(f"• {content}", bullet_style))
            else:
                story.append(Paragraph(escape_html(line), body_style))
        story.append(Spacer(1, 1 * cm))

    doc.build(story)
    print(f"PDF erstellt: {output_path} ({len(sections)} Seiten)")


def escape_html(s: str) -> str:
    """Einfaches Escaping für ReportLab-Paragraphs."""
    return (
        s.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


def main() -> None:
    if not INPUT_TXT.exists():
        raise SystemExit(f"Eingabedatei fehlt: {INPUT_TXT}")
    build_pdf(INPUT_TXT, OUTPUT_PDF)


if __name__ == "__main__":
    import argparse
    p = argparse.ArgumentParser(description="Wissenstext (##-Abschnitte) → PDF, je Abschnitt eine Seite")
    p.add_argument("--input", type=Path, default=INPUT_TXT)
    p.add_argument("--output", type=Path, default=OUTPUT_PDF)
    args = p.parse_args()
    if args.input != INPUT_TXT or args.output != OUTPUT_PDF:
        if not args.input.exists():
            raise SystemExit(f"Eingabedatei fehlt: {args.input}")
        build_pdf(args.input, args.output)
    else:
        main()
