#!/usr/bin/env python3
"""
Schritt 3 der systematischen KI-Analyse:
Baut den finalen Wissenstext aus den Wissens-Kandidaten (JSON).
- Filtert fallbezogene und interne Aussagen
- Dedupliziert über Themen hinweg
- Formatiert als reines Wissen (generalisiert) für den Support-Agenten
"""

import re
import json
from pathlib import Path
from collections import OrderedDict

BASE = Path(__file__).resolve().parent
INPUT_JSON = BASE / "Wissens_Kandidaten_pro_Thema.json"
OUTPUT_TXT = BASE / "Wissenstext_Support_Agent_Systematisch.txt"

# Aussagen, die nicht ins Wissen (fallbezogen, intern, Kundenzitat)
FILTER_PATTERNS = [
    r"hallo angela|hallo frau |hallo herr [a-z]|moin hakan|moin,?\s*bitte",
    r"118596|buchungsnummer \d+|kundennr\.?\s*\d+",
    r"bitte sagt mir|muss diese im system stornieren",
    r"aus dubai eine rechnung|1800€|900€ der flug|1000€ für hotel",
    r"christa munker|familie mietzner|frau busch|frau ropeter|frau dreßen|mandantin",
    r"ich fordere|ich bitte|selbstverständlich sofort als spam|woher sie meine",
    r"landingpage aber was anderes steht",
    r"549€ kosten|türk\.|riviera.*sterne",
    r"1290,20€|599,-€|summe von.*zahlungsverzug",
    r"^ich bin |^ich habe |^ansonsten behalte ich|^desweiteren bitte ich|frank stephan|friedlander straße",
    r"diese e-mail ist eine automatisierte|keine beantwortung ihrer e-mail dar",
    r"hallo liebe reisefreundin|hallo lieber reisefreund",
    r"bei einem/zwei/drei anrufen|wird einem nicht geholfen|unterlage am freitag abgeschickt",
    r"familie aschrich|frau borutta|01\.06\.2025|11\.11\.2024",
    r"nur zur versendung.*eingerichtet|keine eingehenden e-mails empfangen",
    r"persönlichen daten per telefon.*bestätigen wir.*reiseantrages",
    r"mai 2025, 11:26|mai 2025, 17:13",
    r"ihrer frau mutter|ihrer frau Mutter",
    r"295€ gesunken|ausflüge in paris.*4 bis 6 wochen",
    r"^und freuen uns|^oder sind sie vielleicht",
    r"nachdrücklich.*unterstellungen verwahren",
    r"reise nach pommern für den 09\.11|frau borutta",
]

# Reihenfolge der Themen im Wissenstext + Kurztitel
THEMEN_REIHENFOLGE = [
    ("Kontakt_Öffnungszeiten", "UNTERNEHMEN & KONTAKT"),
    ("Gutschein_Partner", "GUTSCHEINE & PARTNER"),
    ("Werbung_Datenschutz", "WERBUNG & DATENSCHUTZ"),
    ("Stornierung_Rücktritt", "STORNIERUNG & RÜCKTRITT"),
    ("Reiseunterlagen_Abholzeit", "REISEUNTERLAGEN & ABHOLZEIT"),
    ("Zahlung_Rückerstattung", "ZAHLUNG & RÜCKERSTATTUNG"),
    ("Versicherung", "VERSICHERUNG"),
    ("Sonstiges_Recht_Adresse", "SONSTIGES (RECHT, ADRESSE)"),
]

# Pro Thema: Sätze, die explizit diesem Thema zugeordnet werden (Normalform -> generalisierte Wissensformulierung)
# Wenn keine Übersetzung, wird der bereinigte Original-Satz genutzt.
GENERALISIERUNGEN = {
    "Wir haben die Sperrung der Daten, für weitere Übersendungen von Werbung und Angeboten aus unserem Unternehmen, vorgenommen.": "Die Sperrung der Daten für weitere Übersendungen von Werbung und Angeboten wird auf Wunsch vorgenommen.",
    "Die endgültige Umstellung kann aber etwa vier Wochen betragen.": "Die endgültige Umstellung kann etwa vier Wochen dauern.",
    "WIR HABEN KEINERLEI DATEN VON IHNEN.": "Bei reinen Gutschein-Empfängern (ohne Anmeldung zur Reise) hat USD keinerlei Daten von der Person.",
    "Wir sind in keiner Form mit Ihnen in Kontakt getreten.": "USD ist bei Gutschein-/Partner-Anfragen in keiner Form mit der Person in Kontakt getreten (Kontakt läuft über den Partner).",
    "Guten Tag, wir sind Reiseveranstalter von Incentivs für verschiedene Firmen und Unternehmen sind.": "USD Reisen ist Reiseveranstalter von Incentive-Reisen für verschiedene Firmen und Unternehmen.",
    "Diese Unternehmen nutzen unsere Reisen als Dankeschön für Ihre Kunden.": "Partner-Unternehmen nutzen USD-Reisen als Dankeschön für ihre Kunden (z. B. Reisegutschein, Paketbeilage).",
    "Sollten Sie einen Gutschein für eine Reise, also die Möglichkeit zur Teilnahme an einer Reise erhalten haben, so erfahren wir auch Ihre Daten erst durch Ihre persönliche Anmeldung.": "Kundendaten erhält USD erst durch die persönliche Anmeldung zur Reise (Einlösung des Gutscheins).",
    "Wenden Sie sich diesbezüglich bitte an den Absender der Nachricht Ihres Angebotes welcher Ihnen einen Reisegutschein mit einer Reise von uns zukommen lassen hat.": "Bei Gutschein-/Werbebeschwerden soll sich der Kunde an den Absender des Gutscheins bzw. der Werbung wenden (auf dem Gutschein steht die Postadresse des Ausstellers).",
    "Auf dem Gutschein sollte die Postadresse des Ausstellers stehen.": "Die Postadresse des Gutschein-Ausstellers steht in der Regel auf dem Gutschein.",
    "Der Wert der Reise kann nicht in Bar ausgezahlt werden.": "Der Wert eines Reisegutscheins kann nicht in Bar ausgezahlt werden.",
    "Wir übernehmen die Reiseabwicklung erst ab der Einlösung durch den Kunden.": "USD übernimmt die Reiseabwicklung erst ab Einlösung des Gutscheins durch den Kunden.",
    "Guten Tag, wenden Sie sich bitte an den Versender des Gutscheins, das sind nicht wir.": "USD ist nicht der Versender von Gutscheinen; Gutscheinaussteller sind die Partner.",
    "Wichtig ist, wir vom Urlaubs Service Deutschland versenden keine Gutscheine!": "USD Reisen versendet keine Gutscheine; diese kommen von Partnern.",
    "Unabhängig davon sind Reisestornierungen laut Reiserecht, niemals kostenfrei.": "Reisestornierungen sind laut Reiserecht niemals automatisch kostenfrei; es gelten die AGB.",
    "Laut den AGB des Reiseveranstalters: 6.8 Der Reiseveranstalter behält sich vor, anstelle der vorstehenden Pauschalen eine höhere, konkrete Entschädigung zu fordern, soweit der Reiseveranstalter nachweist, dass ihm wesentlich höhere Aufwendungen als die jeweils anwendbare Pauschale entstanden sind.": "Laut AGB kann der Reiseveranstalter bei Nachweis wesentlich höherer Aufwendungen eine höhere als die Pauschal-Stornierung fordern (AGB 6.8).",
    "In diesem Fall ist der Reiseveranstalter verpflichtet, die geforderte Entschädigung unter Berücksichtigung der ersparten Aufwendungen und einer etwaigen, anderweitigen Verwendung der Reiseleistungen konkret zu beziffern und zu belegen.": "Die höhere Entschädigung muss konkret beziffert und belegt werden (ersparte Aufwendungen, anderweitige Verwendung der Reiseleistungen).",
    "Wir senden Ihnen hiermit die Originalrechnung zur Einreichung bei Ihrer Versicherung zu.": "Auf Wunsch kann die Originalrechnung zur Einreichung bei der Versicherung (z. B. Rücktrittskostenversicherung) zugesandt werden; bei Rückfragen kann die Versicherung sich an USD wenden.",
    "Um auch spät buchenden Gästen den Zustieg wohnortnah zu ermöglichen, erfolgt die Detailplanung der Streckenzusammenstellung, Fahr- und Abholzeit circa 14 Tage vor Reisebeginn.": "Die Detailplanung (Strecke, Abholzeit, Haltestelle) erfolgt etwa 14 Tage vor Reisebeginn.",
    "Wir senden, wie schon bei Ihrer Reisebuchung schriftlich mitgeteilt, 7-10 Tage vor Reiseantritt den Fahrausweis und Hotel -Voucher.": "Fahrausweis und Hotel-Voucher werden 7–10 Tage vor Reiseantritt versandt (nach vollständigem Zahlungseingang).",
    "Diesem entnehmen Sie dann bitte alle weiteren Details Ihrer Busreise wie Abholzeit und Haltestelle.": "Abholzeit und Haltestelle stehen im Fahrausweis.",
    "Voraussetzung ist der pünktliche Zahlungseingang der Restzahlung.": "Voraussetzung für den Versand der Reiseunterlagen ist der pünktliche Zahlungseingang der Restzahlung.",
    "Mit Verrechnungsschecks können wir leider seit Jahren nicht mehr dienen. Bitte teilen Sie uns Ihre IBAN Verbindung mit.": "Rückerstattungen erfolgen auf ein Bankkonto (IBAN); Verrechnungsschecks werden nicht angeboten.",
}


def soll_rausfiltern(satz: str) -> bool:
    """True = Satz nicht ins Wissen aufnehmen."""
    s = satz.lower().strip()
    if len(s) < 30:
        return True
    for pat in FILTER_PATTERNS:
        if re.search(pat, s, re.IGNORECASE):
            return True
    return False


def generalisieren(satz: str) -> str:
    """Ersetzt bekannte Formulierungen durch generalisierte Version."""
    return GENERALISIERUNGEN.get(satz.strip(), satz.strip())


def normalize_key(s: str) -> str:
    """Normalisiert für Deduplizierung."""
    s = re.sub(r"\s+", " ", s.lower().strip())
    s = re.sub(r"[^\wäöüß\s]", "", s)
    return s[:80]


def main():
    data = json.loads(INPUT_JSON.read_text(encoding="utf-8"))
    # Globale Deduplizierung: gleiche Aussage nur einmal (erste beste Generalisierung)
    seen = set()
    themen_bullets = OrderedDict()
    for thema_key, titel in THEMEN_REIHENFOLGE:
        themen_bullets[thema_key] = []
        kandidaten = data.get(thema_key, [])
        for item in kandidaten:
            satz = (item.get("satz") or "").strip()
            if not satz or soll_rausfiltern(satz):
                continue
            norm = normalize_key(satz)
            if norm in seen:
                continue
            seen.add(norm)
            wissens_satz = generalisieren(satz)
            if soll_rausfiltern(wissens_satz):
                continue
            # Keine Duplikate durch Generalisierung
            norm2 = normalize_key(wissens_satz)
            if norm2 in seen and norm2 != norm:
                continue
            seen.add(norm2)
            themen_bullets[thema_key].append(wissens_satz)
        # Pro Thema auf ca. 15–20 zentrale Punkte begrenzen (priorisiert durch Reihenfolge im JSON = nach Vorkommen)
        themen_bullets[thema_key] = themen_bullets[thema_key][:22]

    # Feste Stammdaten (aus Korpus bekannt, immer anzeigen)
    STAMMDATEN = [
        "USD Reisen (Urlaubs Service Deutschland) ist ein Online-Reisebüro ohne stationäre Geschäfte oder Büros.",
        "Reisen sind bei der R+V gegen Insolvenz abgesichert (Reisesicherungsschein); dieser wird mit der Anmeldebestätigung mitgesendet.",
        "Telefon: 0049 (0) 4431 74 89 440. Aus Österreich/Schweiz: 0049 4431 748 9440.",
        "Öffnungszeiten (Stand Korpus): Montag–Dienstag 09:00–18:00 Uhr, Mittwoch–Freitag 09:00–12:00 Uhr (variiert, aktuelle Angaben auf der Website prüfen).",
        "Website: www.usd.reisen. AGB und Reiseinfos unter www.usd.reisen.",
        "Stornierung: ausschließlich per E-Mail an buchung@usd.reisen oder rechtssicher per Einschreiben an die Adresse des Reiseveranstalters (steht auf der Anmeldebestätigung). E-Mails an reiseteam@ werden nicht inhaltlich beantwortet.",
        "Sitz: Registergericht Oldenburg HRA 205897. USt-IdNr. § 27: DE318355174.",
    ]

    # Wissenstext schreiben
    lines = [
        "# WISSENSTEXT FÜR KI-SUPPORT-AGENT",
        "# Urlaubs Service Deutschland (USD Reisen) / Reiseteam",
        "#",
        "# Erzeugt systematisch aus KI-Analyse der 141 Kundendienst-Paare:",
        "# 1) Parser → strukturierte Daten, 2) Themen + Satzextraktion + Häufigkeit,",
        "# 3) Filter + Generalisierung → reines Wissen, keine Beispiele.",
        "",
        "=" * 72,
        "",
        "## STAMMDATEN (Kontakt, Unternehmen)",
        "",
    ]
    for s in STAMMDATEN:
        lines.append(f"- {s}")
    lines.append("")
    for thema_key, titel in THEMEN_REIHENFOLGE:
        bullets = themen_bullets.get(thema_key, [])
        if not bullets:
            continue
        lines.append(f"## {titel}")
        lines.append("")
        for b in bullets:
            lines.append(f"- {b}")
        lines.append("")
    lines.extend([
        "=" * 72,
        "",
        "Ende des Wissenstexts. Quelle: Analyse_Report_KI_Wissen.md, Wissens_Kandidaten_pro_Thema.json.",
    ])
    OUTPUT_TXT.write_text("\n".join(lines), encoding="utf-8")
    print(f"Wissenstext geschrieben: {OUTPUT_TXT}")
    for k, bullets in themen_bullets.items():
        print(f"  {k}: {len(bullets)} Punkte")


if __name__ == "__main__":
    main()
