"""Convention de mise à disposition avec tampon et signature du centre.

Modèle fourni par Intégrale Academy (31/10/2025). Les images du centre déjà
utilisées sur la plateforme sont apposées au PDF ; seul le stagiaire signe via Yousign.
"""
import hashlib
import json
import os
import re
from datetime import date
from decimal import Decimal, InvalidOperation
from html import escape

DEFAULTS = {
    "adresse": "", "telephone": "", "date_fin": "",
    "formation": "Brevet de Technicien Supérieur Management Opérationnel de la Sécurité",
    "modele_ipad": "iPad Apple Wi-Fi 256 Go silver", "chargeur": True,
    "penalite_ipad": "400.00", "penalite_chargeur": "20.00", "penalite_badge": "20.00",
}
TEXT_LIMITS = {
    "nom": 80, "prenom": 80, "email": 254, "telephone": 25, "adresse": 350,
    "formation": 250, "modele_ipad": 150, "ipad": 100, "badge": 100,
    "date_remise": 10, "date_fin": 10,
}
FIELDS = tuple(TEXT_LIMITS) + ("chargeur", "penalite_ipad", "penalite_chargeur", "penalite_badge")
GENERATOR_VERSION = "dotation-center-signature-v2"
SIGNATURE_FIELDS = {
    "stagiaire": {"page": 3, "x": 50, "y": 650, "width": 205, "height": 75},
}
CENTER_SIGNATURE_AREA = {"page": 3, "x": 335, "y": 650, "width": 205, "height": 75}


def contract_values(dotation):
    values = {**DEFAULTS, **{key: dotation.get(key, "") for key in ("nom", "prenom", "email", "ipad", "badge", "date_remise")}}
    values.update({key: dotation[key] for key in DEFAULTS if key in dotation})
    return values


def read_contract_form(form):
    values = {key: " ".join(form.get(key, "").split()) for key in TEXT_LIMITS}
    values["chargeur"] = form.get("chargeur") == "1"
    for key in ("penalite_ipad", "penalite_chargeur", "penalite_badge"):
        raw = form.get(key, "").strip().replace(",", ".")
        try:
            amount = Decimal(raw)
            if not amount.is_finite() or amount < 0 or amount > 100000 or amount.as_tuple().exponent < -2:
                raise InvalidOperation
            values[key] = str(amount.quantize(Decimal("0.01")))
        except InvalidOperation:
            raise ValueError("Les pénalités doivent être des montants positifs ou nuls, avec deux décimales maximum.")
    validate_contract(values)
    return values


def validate_contract(values):
    for key, label in (("nom", "le nom"), ("prenom", "le prénom"), ("adresse", "l'adresse postale"),
                       ("formation", "la formation"), ("date_remise", "la date de remise"), ("date_fin", "la date de fin")):
        if not str(values.get(key) or "").strip():
            raise ValueError(f"Veuillez renseigner {label}.")
    for key, limit in TEXT_LIMITS.items():
        if len(str(values.get(key) or "")) > limit:
            raise ValueError(f"Le champ {key.replace('_', ' ')} est trop long (maximum {limit} caractères).")
    if not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", values.get("email") or ""):
        raise ValueError("Veuillez renseigner une adresse e-mail valide pour le stagiaire.")
    try:
        start, end = date.fromisoformat(values["date_remise"]), date.fromisoformat(values["date_fin"])
    except (ValueError, TypeError):
        raise ValueError("Veuillez renseigner des dates valides.")
    if end < start:
        raise ValueError("La fin de la convention doit être postérieure ou égale à la date de remise.")
    if values.get("ipad") and not values.get("modele_ipad"):
        raise ValueError("Veuillez préciser le modèle de l'iPad.")
    if not inventory(values):
        raise ValueError("Veuillez renseigner au moins un matériel mis à disposition.")


def inventory(values):
    items = []
    if values.get("ipad"):
        items.append((values.get("modele_ipad") or "iPad Apple", values["ipad"], values.get("penalite_ipad", "400.00")))
    if values.get("chargeur"):
        items.append(("Chargeur d'iPad avec son cordon", "", values.get("penalite_chargeur", "20.00")))
    if values.get("badge"):
        items.append(("Badge pour le distributeur de boissons et snacks", values["badge"], values.get("penalite_badge", "20.00")))
    return items


def fingerprint(values):
    return hashlib.sha256(json.dumps({key: values.get(key) for key in FIELDS}, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


def french_date(value):
    day = date.fromisoformat(value)
    months = ("janvier", "février", "mars", "avril", "mai", "juin", "juillet", "août", "septembre", "octobre", "novembre", "décembre")
    return f"{day.day} {months[day.month - 1]} {day.year}"


def generate_pdf(values, output_path, logo_path, generated_on=None, *, center_signature_path, center_stamp_path):
    import reportlab
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.lib.utils import ImageReader
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak

    validate_contract(values)
    if not all(path and os.path.isfile(path) for path in (center_signature_path, center_stamp_path)):
        raise ValueError("Le tampon et la signature du centre doivent être disponibles pour générer le contrat.")
    try:
        center_images = [ImageReader(path) for path in (center_signature_path, center_stamp_path)]
        for image in center_images:
            image.getSize()
    except (OSError, ValueError) as exc:
        raise ValueError("Le tampon ou la signature du centre est illisible.") from exc
    fonts = os.path.join(os.path.dirname(reportlab.__file__), "fonts")
    for name, filename in (("DotationSans", "Vera.ttf"), ("DotationSansBold", "VeraBd.ttf")):
        if name not in pdfmetrics.getRegisteredFontNames():
            pdfmetrics.registerFont(TTFont(name, os.path.join(fonts, filename)))
    pdfmetrics.registerFontFamily("DotationSans", normal="DotationSans", bold="DotationSansBold", italic="DotationSans", boldItalic="DotationSansBold")
    generated_on = generated_on or date.today().isoformat()
    gold, ink = colors.HexColor("#dfa846"), colors.HexColor("#242724")
    regular = ParagraphStyle("Body", fontName="DotationSans", fontSize=10, leading=15, textColor=ink, spaceAfter=12)
    heading = ParagraphStyle("Heading", parent=regular, fontName="DotationSansBold", fontSize=12, leading=17, spaceBefore=14, spaceAfter=12)
    small = ParagraphStyle("Small", parent=regular, fontSize=9, leading=13, spaceAfter=0)
    story = []
    p = lambda text, style=regular: Paragraph(text, style)
    e = lambda text: escape(str(text), quote=False)
    full_name = f"{values['prenom']} {values['nom'].upper()}"
    end = french_date(values["date_fin"])
    items = inventory(values)

    def footer_and_header(canvas, doc):
        canvas.saveState()
        width, height = A4
        canvas.setStrokeColor(gold)
        canvas.setLineWidth(2)
        canvas.line(44, height - 112, width - 44, height - 112)
        if logo_path and os.path.isfile(logo_path):
            canvas.drawImage(logo_path, 44, height - 101, width=85, height=68, preserveAspectRatio=True, anchor="c", mask="auto")
        canvas.setFillColor(ink)
        canvas.setFont("DotationSansBold", 12)
        canvas.drawString(152, height - 47, "INTÉGRALE ACADEMY")
        canvas.setFont("DotationSans", 9)
        canvas.drawString(152, height - 64, "Centre de formation OF-CFA")
        canvas.drawString(152, height - 79, "54 chemin du Carreou - 83480 PUGET SUR ARGENS")
        canvas.drawString(152, height - 94, "04 22 47 07 68 - ecole@integraleacademy.com")
        canvas.setStrokeColor(colors.HexColor("#dddddd"))
        canvas.setLineWidth(.5)
        canvas.line(44, 49, width - 44, 49)
        canvas.setFillColor(colors.HexColor("#777777"))
        canvas.setFont("DotationSans", 6.5)
        canvas.drawCentredString(width / 2, 36, "Intégrale Academy - Intégrale Sécurité Formations - 54 chemin du Carreou - 83480 PUGET SUR ARGENS")
        canvas.drawCentredString(width / 2, 25, "SIRET 840 899 884 00026 - RCS FRÉJUS - APE 8559A - NDA 93830600283 - UAI 0831774C")
        canvas.drawRightString(width - 44, 58, f"{doc.page} / 3")
        if doc.page == 3:
            for label, name, key, field in (("Pour le stagiaire", full_name, "stagiaire", SIGNATURE_FIELDS["stagiaire"]),
                                            ("Pour le centre de formation", "Clément VAILLANT - Directeur général", "centre", CENTER_SIGNATURE_AREA)):
                x, top = field["x"], height - field["y"]
                canvas.setFillColor(ink)
                canvas.setFont("DotationSansBold", 9.5)
                canvas.drawString(x, top + 77, label)
                name_p = p(e(name), small)
                _, text_height = name_p.wrap(field["width"], 55)
                name_p.drawOn(canvas, x, top + 66 - text_height)
                canvas.setStrokeColor(colors.HexColor("#c4c8c4"))
                canvas.roundRect(x, top - field["height"], field["width"], field["height"], 4)
                if key == "centre":
                    for image, offset, max_width in zip(center_images, (6, 82), (70, 117)):
                        image_width, image_height = image.getSize()
                        scale = min(max_width / image_width, (field["height"] - 12) / image_height)
                        drawn_width, drawn_height = image_width * scale, image_height * scale
                        canvas.drawImage(image, x + offset + (max_width - drawn_width) / 2,
                                         top - field["height"] + (field["height"] - drawn_height) / 2,
                                         width=drawn_width, height=drawn_height, mask="auto")
                canvas.setFillColor(colors.HexColor("#777777"))
                canvas.setFont("DotationSans", 8)
                canvas.drawString(x, top - field["height"] - 14,
                                  "Tampon et signature du centre" if key == "centre" else "Signature électronique via Yousign")
        canvas.restoreState()

    story += [p("Convention de mise à disposition<br/>de matériel", ParagraphStyle("Title", parent=heading, fontSize=20, leading=27, spaceAfter=28)),
              p("Entre les soussignés", heading),
              p("<b>OF-CFA Intégrale Academy - Intégrale Sécurité Formations (SASU)</b><br/>"
                "54 chemin du Carreou, 83480 PUGET SUR ARGENS<br/>"
                "RCS Fréjus 840 899 884 - SIRET 840 899 884 00026<br/>"
                "Déclaration d'activité n° 93830600283 auprès de la DREETS de la région Provence-Alpes-Côte d'Azur.<br/>"
                "Représenté par Monsieur <b>Clément VAILLANT</b>, en qualité de directeur général."),
              p("Ci-après nommé « l'organisme de formation ».", small), Spacer(1, 24),
              p("Et le stagiaire", heading),
              p(f"<b>{e(full_name)}</b><br/>{e(values['adresse'])}<br/>E-mail : {e(values['email'])}" +
                (f"<br/>Téléphone : {e(values['telephone'])}" if values.get("telephone") else "")),
              p("Ci-après nommé « le stagiaire ».", small), Spacer(1, 28),
              p("Il a été convenu ce qui suit."), PageBreak()]
    story += [p("Article 1 - Objet", heading),
              p("En exécution du présent contrat, l'organisme de formation accepte de mettre à disposition du stagiaire du matériel dans le cadre de l'action de formation intitulée :"),
              p(f"<b>{e(values['formation'])}</b>"),
              p("Article 2 - Durée de la convention", heading),
              p(f"Le matériel est mis à disposition du stagiaire par l'organisme de formation à compter du <b>{french_date(values['date_remise'])}</b> jusqu'au <b>{end}</b>. À l'issue de cette période, le matériel est cédé gratuitement au stagiaire par l'organisme de formation."),
              p(f"Si le stagiaire décide de quitter l'organisme de formation avant le {end}, il devra restituer au centre de formation l'intégralité du matériel mis à disposition, en parfait état, sous peine des pénalités financières exposées à l'article 4 de la présente convention."),
              p("Article 3 - Inventaire du matériel mis à disposition", heading)]
    rows = [[p("<b>Qté</b>", small), p("<b>Matériel</b>", small), p("<b>N° de série / badge</b>", small)]]
    rows.extend([[p("1", small), p(e(label), small), p(e(serial) or "Sans objet", small)] for label, serial, _ in items])
    table = Table(rows, colWidths=[35, 273, 187], hAlign="LEFT")
    table.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#f8eddb")), ("VALIGN", (0, 0), (-1, -1), "TOP"),
                               ("BOX", (0, 0), (-1, -1), .5, colors.HexColor("#dedede")), ("INNERGRID", (0, 0), (-1, -1), .4, colors.HexColor("#dedede")),
                               ("TOPPADDING", (0, 0), (-1, -1), 10), ("BOTTOMPADDING", (0, 0), (-1, -1), 10)]))
    story += [table, PageBreak(), p("Article 4 - Pénalités financières", heading),
              p(f"Comme indiqué à l'article 2, le matériel sera automatiquement rétrocédé au stagiaire à compter du {end}. En cas de cessation de l'action de formation du fait de l'abandon de la formation par le stagiaire avant cette date, l'intégralité du matériel listé à l'article 3 devra être restituée <b>EN PARFAIT ÉTAT</b> à l'organisme de formation dans les <b>5 jours suivant la rupture du contrat d'apprentissage</b>, sous peine de l'application des pénalités financières suivantes :")]
    for label, serial, amount in items:
        euros = f"{Decimal(amount):.2f}".replace(".", ",")
        story.append(p(f"<b>1 {e(label)} : {euros} euros</b>", small))
        story.append(Spacer(1, 8))
    story += [p("Article 5 - Cas de différend", heading),
              p("Si une contestation ou un différend n'ont pu être réglés à l'amiable, le Tribunal de Fréjus sera seul compétent pour régler le litige."),
              p(f"Fait à PUGET SUR ARGENS, le {french_date(generated_on)}.<br/>Un exemplaire électronique signé est destiné à chacune des parties.")]
    doc = SimpleDocTemplate(output_path, pagesize=A4, rightMargin=44, leftMargin=44, topMargin=126, bottomMargin=65,
                            title=f"Convention de mise à disposition - {full_name}", author="Intégrale Academy")
    doc.build(story, onFirstPage=footer_and_header, onLaterPages=footer_and_header)
    # Signature coordinates are only valid on this explicit, bounded template.
    from pypdf import PdfReader
    reader = PdfReader(output_path)
    if len(reader.pages) != 3:
        raise ValueError("Le contenu est trop long pour le modèle de convention. Raccourcissez les informations saisies.")
    return output_path
