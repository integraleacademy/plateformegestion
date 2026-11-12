"""Printable monthly calendar with a complete, untruncated event appendix."""
import calendar
from datetime import date
from io import BytesIO
from pathlib import Path
import re

import reportlab
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas
from pypdf import PdfReader, PdfWriter

MONTHS = ("", "Janvier", "Février", "Mars", "Avril", "Mai", "Juin", "Juillet", "Août", "Septembre", "Octobre", "Novembre", "Décembre")
STATUS = {"pending": "À RÉSERVER", "booked": "RÉSERVÉ", "needs_change": "À MODIFIER", "not_needed": "PAS NÉCESSAIRE"}
COLORS = {"louise": "#c66e99", "boarding": "#c78244", "transport": "#4b9b9e", "restaurant": "#bd6c55", "location": "#7c65bc", "personal": "#8674b9", "professional": "#647a9a", "training_start": "#4b929e", "training_onsite": "#6575bd", "training_end": "#6b9a71", "training_exam": "#bc8f37", "task": "#82914c"}
PLACES = {"paris": "#7c65bc", "puget": "#c09240", "cantal": "#4e987c", "away": "#5b8fb3"}
INK = colors.HexColor("#242936")
MUTED = colors.HexColor("#6e6878")
SSIAP_RED = "#c62828"
SCOPE_LABELS = {"all": "Tout le planning", "louise": "Avec Louise", "location": "Voyages et séjours", "boarding": "Pension chien", "transport": "Transports", "restaurant": "Restaurants", "training": "Formations", "personal": "Rendez-vous personnels", "professional": "Rendez-vous professionnels", "task": "À faire"}


def is_ssiap(record):
    return record.get("ssiap") is True or bool(re.search(r"SSIAP", str(record.get("formation", "")) + " " + str(record.get("title", "")), re.I))


def event_color(record):
    return SSIAP_RED if is_ssiap(record) else COLORS.get(record["kind"], "#8674b9")


def event_title(record):
    title = record["title"]
    if record["kind"] == "restaurant":
        title = {"lunch": "Midi", "dinner": "Soir", "other": "Restaurant"}.get(record.get("meal"), "Restaurant") + " · " + title
    if record["kind"] == "boarding":
        venue = {"itana": "Itana", "lafeuillade": "Lafeuillade"}.get(record.get("boarding_location"))
        if venue and venue not in title:
            title += " · " + venue
    return ("IMPORTANT · " if record.get("important") else "") + title


def owner_name(owner):
    return {"both": "Clément & Elsa", "clement": "Clément", "elsa": "Elsa"}.get(owner, "Clément & Elsa")


def font_setup():
    # Vera is shipped with ReportLab, so production needs no system fonts.
    font_dir = Path(reportlab.__file__).parent / "fonts"
    for name, file in (("PlannerSans", "Vera.ttf"), ("PlannerBold", "VeraBd.ttf")):
        if name not in pdfmetrics.getRegisteredFontNames():
            pdfmetrics.registerFont(TTFont(name, str(font_dir / file)))


def printable(value):
    # Vera has French accents but no arrow glyph; keep route directions readable.
    return str(value).replace("→", "vers").replace("←", "depuis")


def fit(text, width, size=7, font="PlannerSans"):
    text = " ".join(printable(text).split())
    if pdfmetrics.stringWidth(text, font, size) <= width:
        return text
    while text and pdfmetrics.stringWidth(text + "…", font, size) > width:
        text = text[:-1]
    return text + "…"


def wrap(text, width, size=9, font="PlannerSans"):
    words = printable(text).split()
    lines, line = [], ""
    for word in words:
        if line and pdfmetrics.stringWidth(line + " " + word, font, size) > width:
            lines.append(line)
            line = ""
        # Long single tokens (references, URLs) must wrap too.
        while pdfmetrics.stringWidth(word, font, size) > width:
            chunk = word
            while pdfmetrics.stringWidth(chunk, font, size) > width:
                chunk = chunk[:-1]
            if line:
                lines.append(line)
                line = ""
            lines.append(chunk)
            word = word[len(chunk):]
        line = (line + " " + word).strip()
    if line:
        lines.append(line)
    return lines or [""]


def sort_priority(record):
    return (0 if record["kind"] == "transport" else 1 if record["kind"] == "boarding" else 2,
            record.get("start_time", ""), record["title"])


def selected_events(records, training, bookings, first, last, owner="all", hidden=(), scope="all"):
    events = [r for r in records if r["kind"] in {"louise", "personal", "professional", "restaurant"} or scope == "location" and r["kind"] == "location"]
    events += bookings + training
    events += [dict(r, start=r["due"], end=r["due"]) for r in records if r["kind"] == "task" and r.get("due") and not r.get("done")]
    return [r for r in events if r["start"] <= last and r["end"] >= first
            and (owner == "all" or r["owner"] in {"both", owner})
            and (scope == "all" or r["kind"] == scope or scope == "training" and r["kind"].startswith("training_"))
            and not all(key in hidden for key in r.get("milestones", [r["kind"]])) and not (is_ssiap(r) and "ssiap" in hidden)
            and r.get("status") != "not_needed"]


def month_events(records, training, bookings, year, month, owner, hidden):
    return selected_events(records, training, bookings, date(year, month, 1).isoformat(), date(year, month, calendar.monthrange(year, month)[1]).isoformat(), owner, hidden)


def render_month(records, training, bookings, coverage_days, year, month, owner="all", hidden=(), *, scope="all", first=None, last=None, include_agenda=True):
    font_setup()
    first = max(first or "2000-01-01", date(year, month, 1).isoformat())
    last = min(last or "2100-12-31", date(year, month, calendar.monthrange(year, month)[1]).isoformat())
    events = selected_events(records, training, bookings, first, last, owner, hidden, scope)
    days = {d["date"]: d for d in coverage_days}
    weeks = calendar.Calendar(firstweekday=0).monthdatescalendar(year, month)
    output = BytesIO()
    c = canvas.Canvas(output, pagesize=landscape(A4), pageCompression=1)
    c.setTitle(f"Planning Clément & Elsa - {MONTHS[month]} {year}")
    c.setAuthor("Intégrale Academy")
    width, height = landscape(A4)
    margin, page = 25, 1

    def footer():
        c.setFillColor(MUTED)
        c.setFont("PlannerSans", 7)
        c.drawString(margin, 17, "Planning partagé · Dates et statuts au moment de l’export" + (" · Lieux manquants signalés" if scope in {"all", "location"} else ""))
        c.drawRightString(width - margin, 17, str(page))

    def text(x, y, value, size=8, bold=False, color=INK):
        c.setFont("PlannerBold" if bold else "PlannerSans", size)
        c.setFillColor(color)
        c.drawString(x, y, printable(value))

    text(margin, height - 35, "Clément & Elsa", 19, True)
    text(margin, height - 53, f"{MONTHS[month]} {year} · {SCOPE_LABELS[scope]} · {owner_name(owner)}", 11)
    text(margin, height - 69, "Vue mensuelle · Les événements et trajets complets figurent dans l’agenda en pages suivantes." if events else "Vue mensuelle · Aucun événement pour les filtres sélectionnés.", 7.5, color=MUTED)
    if scope in {"all", "training"}:
        text(width - 272, height - 33, "SSIAP", 8, True, colors.HexColor(SSIAP_RED))
    if scope in {"all", "boarding", "transport", "restaurant"}:
        text(width - 218, height - 33, "À RÉSERVER", 7, True, colors.HexColor("#9a5700"))
        text(width - 127, height - 33, "À MODIFIER", 7, True, colors.HexColor("#b42318"))
    if hidden:
        text(width - 272, height - 48, "Filtres du calendrier appliqués", 7, color=MUTED)
    top, bottom = height - 91, 48
    col_width = (width - 2 * margin) / 7
    row_height = (top - bottom - 21) / len(weeks)
    c.setFillColor(colors.HexColor("#f3f0f8"))
    c.rect(margin, top - 21, width - 2 * margin, 21, fill=1, stroke=0)
    for col, label in enumerate(("LUNDI", "MARDI", "MERCREDI", "JEUDI", "VENDREDI", "SAMEDI", "DIMANCHE")):
        text(margin + col * col_width + 7, top - 14, label, 7, True, MUTED)
    for row_index, week in enumerate(weeks):
        for col, day in enumerate(week):
            x, cell_top = margin + col * col_width, top - 21 - row_index * row_height
            y = cell_top - row_height
            c.setStrokeColor(colors.HexColor("#e3dfe9"))
            c.setLineWidth(.45)
            active = day.month == month and first <= day.isoformat() <= last
            marked = active and any(r["start"] <= day.isoformat() <= r["end"] for r in events)
            tint = {"louise": "#fff1f7", "boarding": "#fff7eb", "transport": "#f0f9f9", "restaurant": "#fff4ef"}.get(scope)
            c.setFillColor(colors.HexColor(tint) if marked and tint else colors.white if active else colors.HexColor("#f9f9fb"))
            c.rect(x, y, col_width, row_height, fill=1, stroke=1)
            text(x + 6, cell_top - 13, day.day, 8, True, INK if day.month == month else colors.HexColor("#b4b0bd"))
            if day.month != month or not first <= day.isoformat() <= last:
                continue
            value = day.isoformat()
            coverage = days.get(value, {})
            persons = (("clement", "elsa") if owner in {"all", "both"} else (owner,)) if scope in {"all", "location"} else ()
            pos = cell_top - 24
            for person in persons:
                place = coverage.get(person)
                label = ("C. " if person == "clement" else "E. ") + (place["title"] if place else "Lieu manquant")
                text(x + 6, pos, fit(label, col_width - 12, 6.2), 6.2,
                     color=colors.HexColor(PLACES.get((place or {}).get("place"), "#b34b4a")))
                pos -= 8
            day_events = sorted((r for r in events if r["kind"] != "location" and r["start"] <= value <= r["end"]), key=sort_priority)
            event_size, step = (8, 12) if scope != "all" else (6.4, 10)
            slots = max(0, int((pos - y - 13) // step))
            for r in day_events[:slots]:
                label = (STATUS[r["status"]] + " · " if r.get("status") else "") + (r.get("start_time", "") + " " if r.get("start_time") else "") + event_title(r)
                c.setFillColor(colors.HexColor(event_color(r)))
                c.rect(x + 5, pos - 1.5, 2, 7, fill=1, stroke=0)
                text(x + 10, pos, fit(label, col_width - 15, event_size), event_size, r.get("status") in {"pending", "needs_change"}, colors.HexColor(event_color(r)))
                pos -= step
            if len(day_events) > slots:
                text(x + 6, y + 5, f"+ {len(day_events) - slots} autres · voir agenda", 6, color=MUTED)
    footer()
    if events and include_agenda:
        def agenda_header():
            nonlocal page
            c.showPage()
            page += 1
            text(margin, height - 35, f"{MONTHS[month]} {year} · Agenda détaillé", 17, True)
            text(margin, height - 53, "Tous les événements du mois · les périodes sont inclusives · les trajets aller et retour sont séparés", 8, color=MUTED)
            return height - 79
        pos = agenda_header()
        for r in sorted(events, key=lambda r: (r["start"], sort_priority(r))):
            dates = date.fromisoformat(r["start"]).strftime("%d/%m/%Y")
            if r["end"] != r["start"]:
                dates += " au " + date.fromisoformat(r["end"]).strftime("%d/%m/%Y")
            lines = wrap(event_title(r), width - margin * 2 - 169, 9, "PlannerBold")
            details = event_details(r)
            detail_lines = wrap(details, width - margin * 2 - 169, 8)
            needed = len(lines) * 13 + len(detail_lines) * 12 + 17
            if pos - needed < 43:
                footer()
                pos = agenda_header()
            text(margin, pos, dates, 7.5, color=MUTED)
            for line in lines:
                text(margin + 169, pos, line, 9, True, colors.HexColor(event_color(r)))
                pos -= 13
            for line in detail_lines:
                text(margin + 169, pos, line, 8, color=MUTED)
                pos -= 12
            c.setStrokeColor(colors.HexColor("#eeeaf2"))
            c.line(margin, pos - 4, width - margin, pos - 4)
            pos -= 17
        footer()
    c.save()
    return output.getvalue()


def event_details(record):
    details = [owner_name(record["owner"])]
    if record.get("status"):
        details.append(STATUS[record["status"]])
    venue = {"itana": "Itana", "lafeuillade": "Lafeuillade"}.get(record.get("boarding_location"))
    if record["kind"] == "boarding":
        details.append("Pension : " + (venue or "lieu à préciser"))
    if record["kind"] == "restaurant":
        details.append({"lunch": "Midi", "dinner": "Soir", "other": "Autre moment"}.get(record.get("meal"), ""))
        if record.get("guests"):
            details.append(str(record["guests"]) + " personnes")
        if record.get("address"):
            details.append(record["address"])
    if record.get("start_time"):
        details.append(record["start_time"] + (" - " + record["end_time"] if record.get("end_time") else ""))
    if record.get("reference"):
        details.append("Réf. " + record["reference"])
    if record.get("estimated_date"):
        details.append("Date de retour prévue à confirmer")
    if record.get("important"):
        details.append("IMPORTANT")
    if record["kind"] == "location" and record.get("transport_status") != "not_needed":
        details.append("Aller : " + (record.get("transport_start") or record["start"]))
        if record.get("transport_round_trip") is not False:
            details.append("Retour : " + (record.get("transport_end") or record["end"]))
    return " · ".join(filter(None, details))


def group_transport_events(events):
    grouped, result = {}, []
    for event in events:
        if event["kind"] != "transport" or not event.get("linked"):
            result.append(event)
            continue
        group = grouped.get(event["record_id"])
        if group is None:
            group = dict(event, title="Voyage · " + event["stay"], legs=[])
            grouped[event["record_id"]] = group
            result.append(group)
        group["legs"].append(event)
        group["start"] = min(group["start"], event["start"])
        group["end"] = max(group["end"], event["end"])
    return sorted(result, key=lambda r: (r["start"], sort_priority(r)))


def render_agenda(events, first, last, scope, owner):
    font_setup()
    output = BytesIO()
    c = canvas.Canvas(output, pagesize=landscape(A4))
    c.setTitle(f"{SCOPE_LABELS[scope]} - Clément & Elsa")
    width, height = landscape(A4)
    margin, page = 28, 1

    def text(x, y, value, size=9, bold=False, color=INK):
        c.setFillColor(color)
        c.setFont("PlannerBold" if bold else "PlannerSans", size)
        c.drawString(x, y, printable(value))

    def header():
        text(margin, height - 37, SCOPE_LABELS[scope], 20, True)
        label = date.fromisoformat(first).strftime("%d/%m/%Y") + " au " + date.fromisoformat(last).strftime("%d/%m/%Y")
        text(margin, height - 56, label + " · " + owner_name(owner), 10, color=MUTED)
        text(margin, height - 73, "Clément & Elsa · Agenda détaillé · Dates inclusives", 8, color=MUTED)
        return height - 100

    def footer():
        text(margin, 18, "Planning partagé · Dates et statuts au moment de l’export", 7, color=MUTED)
        text(width - margin - 20, 18, str(page), 7, color=MUTED)

    pos = header()
    rows = group_transport_events(events)
    if not rows:
        text(margin, pos, "Aucun événement sur cette période pour cette sélection.", 11, color=MUTED)
    for r in rows:
        bounds = date.fromisoformat(r["start"]).strftime("%d/%m/%Y")
        if r["end"] != r["start"]:
            bounds += " au " + date.fromisoformat(r["end"]).strftime("%d/%m/%Y")
        content = [(line, True) for line in wrap(event_title(r), width - margin * 2 - 175, 10, "PlannerBold")]
        if r.get("legs"):
            for leg in sorted(r["legs"], key=lambda l: (l["start"], l.get("direction", ""))):
                details = date.fromisoformat(leg["start"]).strftime("%d/%m/%Y") + " · " + leg["title"] + " · " + event_details(leg)
                content.extend((line, False) for line in wrap(details, width - margin * 2 - 175, 8))
        else:
            content.extend((line, False) for line in wrap(event_details(r), width - margin * 2 - 175, 8))
        needed = len(content) * 14 + 18
        if pos - needed < 45:
            footer(); c.showPage(); page += 1; pos = header()
        text(margin, pos, bounds, 7.5, color=MUTED)
        for line, bold in content:
            text(margin + 175, pos, line, 10 if bold else 8, bold, colors.HexColor(event_color(r)) if bold else MUTED)
            pos -= 14
        c.setStrokeColor(colors.HexColor("#e9e5f0"))
        c.line(margin, pos - 3, width - margin, pos - 3)
        pos -= 18
    footer(); c.save()
    return output.getvalue()


def render_period(records, training, bookings, coverage_days, first, last, scope="all", layout="calendar", owner="all"):
    events = selected_events(records, training, bookings, first, last, owner, scope=scope)
    agenda = render_agenda(events, first, last, scope, owner)
    if layout == "list":
        return agenda
    writer = PdfWriter()
    current, end = date.fromisoformat(first).replace(day=1), date.fromisoformat(last)
    while current <= end:
        document = render_month(records, training, bookings, coverage_days, current.year, current.month, owner,
                                scope=scope, first=first, last=last, include_agenda=False)
        writer.append(PdfReader(BytesIO(document)))
        current = date(current.year + 1, 1, 1) if current.month == 12 else date(current.year, current.month + 1, 1)
    if events:
        writer.append(PdfReader(BytesIO(agenda)))
    for index, page in enumerate(writer.pages, 1):
        stamp = BytesIO()
        width, height = float(page.mediabox.width), float(page.mediabox.height)
        label = canvas.Canvas(stamp, pagesize=(width, height))
        label.setFillColor(colors.white)
        label.rect(width - 90, 10, 85, 18, fill=1, stroke=0)
        label.setFillColor(MUTED); label.setFont("Helvetica", 7)
        label.drawRightString(width - 28, 17, f"{index} / {len(writer.pages)}")
        label.save()
        page.merge_page(PdfReader(BytesIO(stamp.getvalue())).pages[0])
    writer.add_metadata({"/Title": f"Planning {SCOPE_LABELS[scope]} - {first} au {last}", "/Author": "Intégrale Academy"})
    output = BytesIO(); writer.write(output)
    return output.getvalue()
