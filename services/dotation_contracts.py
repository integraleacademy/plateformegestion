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

FORMATIONS = {
    "BTS CI": "Brevet de Technicien Supérieur Commerce International",
    "BTS MOS": "Brevet de Technicien Supérieur Management Opérationnel de la Sécurité",
    "BTS MCO": "Brevet de Technicien Supérieur Management Commercial Opérationnel",
    "BTS PI": "Brevet de Technicien Supérieur Professions Immobilières",
}
DEFAULTS = {
    "adresse": "", "telephone": "", "date_fin": "2028-07-01",
    "formation": FORMATIONS["BTS MOS"],
    "modele_ipad": "iPad Apple Wi-Fi 256 Go silver", "chargeur": True,
    "penalite_ipad": "400.00", "penalite_chargeur": "20.00", "penalite_badge": "20.00",
}
TEXT_LIMITS = {
    "nom": 80, "prenom": 80, "email": 254, "telephone": 25, "adresse": 350,
    "formation": 250, "modele_ipad": 150, "ipad": 100, "badge": 100,
    "date_remise": 10, "date_fin": 10,
}
FIELDS = tuple(TEXT_LIMITS) + ("chargeur", "penalite_ipad", "penalite_chargeur", "penalite_badge")
GENERATOR_VERSION = "dotation-expanded-v3"
CENTER_SIGNED_VERSIONS = {"dotation-center-signature-v2", GENERATOR_VERSION}
PDF_PAGE_COUNT = 4
SIGNATURE_FIELDS = {
    "stagiaire": {"page": PDF_PAGE_COUNT, "x": 50, "y": 650, "width": 205, "height": 75},
}
CENTER_SIGNATURE_AREA = {"page": PDF_PAGE_COUNT, "x": 335, "y": 650, "width": 205, "height": 75}


def contract_values(dotation):
    values = {**DEFAULTS, **{key: dotation.get(key, "") for key in ("nom", "prenom", "email", "ipad", "badge", "date_remise")}}
    values.update({key: dotation[key] for key in DEFAULTS if key in dotation})
    values["date_fin"] = values.get("date_fin") or DEFAULTS["date_fin"]
    values["formation"] = FORMATIONS.get(values.get("formation"), values.get("formation")) or DEFAULTS["formation"]
    return values


def read_contract_form(form):
    values = {key: " ".join(form.get(key, "").split()) for key in TEXT_LIMITS}
    values["formation"] = FORMATIONS.get(values["formation"], values["formation"])
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
                       ("formation", "la formation"), ("date_remise", "la date de remise"), ("date_fin", "la date de fin de formation")):
        if not str(values.get(key) or "").strip():
            raise ValueError(f"Veuillez renseigner {label}.")
    for key, limit in TEXT_LIMITS.items():
        if len(str(values.get(key) or "")) > limit:
            raise ValueError(f"Le champ {key.replace('_', ' ')} est trop long (maximum {limit} caractères).")
    if values.get("formation") not in FORMATIONS.values():
        raise ValueError("Veuillez sélectionner une formation : BTS CI, BTS MOS, BTS MCO ou BTS PI.")
    if not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", values.get("email") or ""):
        raise ValueError("Veuillez renseigner une adresse e-mail valide pour le stagiaire.")
    try:
        start, end = date.fromisoformat(values["date_remise"]), date.fromisoformat(values["date_fin"])
    except (ValueError, TypeError):
        raise ValueError("Veuillez renseigner des dates valides.")
    if end < start:
        raise ValueError("La date de fin de formation doit être postérieure ou égale à la date de remise.")
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
    return f"{'1er' if day.day == 1 else day.day} {months[day.month - 1]} {day.year}"


def generate_pdf(values, output_path, logo_path, generated_on=None, *, center_signature_path, center_stamp_path):
    import reportlab
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.lib.utils import ImageReader
    from reportlab.platypus import BaseDocTemplate, Frame, PageTemplate, NextPageTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak

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
    regular = ParagraphStyle("Body", fontName="DotationSans", fontSize=10, leading=14.5, textColor=ink, spaceAfter=10)
    heading = ParagraphStyle("Heading", parent=regular, fontName="DotationSansBold", fontSize=12, leading=17, spaceBefore=12, spaceAfter=9, keepWithNext=True)
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
        canvas.drawRightString(width - 44, 58, f"{doc.page} / {PDF_PAGE_COUNT}")
        if doc.page == PDF_PAGE_COUNT:
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

    story += [p("Convention de mise à disposition<br/>de matériel", ParagraphStyle("Title", parent=heading, fontSize=20, leading=27, spaceAfter=20)),
              p("Entre les soussignés", heading),
              p("<b>OF-CFA Intégrale Academy - Intégrale Sécurité Formations (SASU)</b><br/>"
                "54 chemin du Carreou, 83480 PUGET SUR ARGENS<br/>"
                "RCS Fréjus 840 899 884 - SIRET 840 899 884 00026<br/>"
                "Déclaration d'activité n° 93830600283 auprès de la DREETS de la région Provence-Alpes-Côte d'Azur.<br/>"
                "Représenté par Monsieur <b>Clément VAILLANT</b>, en qualité de directeur général."),
              p("Ci-après nommé « l'organisme de formation ».", small), Spacer(1, 12),
              p("Et le stagiaire", heading),
              p(f"<b>{e(full_name)}</b><br/>{e(values['adresse'])}<br/>E-mail : {e(values['email'])}" +
                (f"<br/>Téléphone : {e(values['telephone'])}" if values.get("telephone") else "")),
              p("Ci-après nommé « le stagiaire ».", small), Spacer(1, 12),
              p("Article 1 - Objet de la mise à disposition", heading),
              p("L'organisme de formation confie gratuitement au stagiaire le matériel désigné à l'article 3 pour l'accompagner dans la formation suivante :"),
              p(f"<b>{e(values['formation'])}</b>"),
              p("Cette mise à disposition personnelle facilite l'accès aux supports pédagogiques, la réalisation des travaux et les échanges liés à la formation. La présente convention précise les conditions d'utilisation, de conservation et de restitution du matériel, ainsi que sa cession en fin de formation."),
              PageBreak()]
    story += [p("Article 2 - Durée, propriété et cession", heading),
              p(f"<b>Date de remise du matériel : {french_date(values['date_remise'])}.</b><br/>"
                f"<b>Date de fin de formation : {end}.</b>"),
              p("Le matériel reste la propriété de l'organisme de formation pendant cette période. Le stagiaire en bénéficie à titre gratuit et en assure la garde dans les conditions de la présente convention."),
              p(f"À la date de fin de formation, soit le <b>{end}</b>, le matériel est <b>cédé gratuitement au stagiaire</b>, sauf s'il a dû être restitué à la suite d'un abandon antérieur dans les conditions de l'article 8. Toute modification de ces dates ou de l'inventaire fait l'objet d'un accord écrit entre les parties."),
              p("Article 3 - Inventaire et remise du matériel", heading)]
    rows = [[p("<b>Qté</b>", small), p("<b>Matériel</b>", small), p("<b>N° de série / badge</b>", small)]]
    rows.extend([[p("1", small), p(e(label), small), p(e(serial) or "Sans objet", small)] for label, serial, _ in items])
    table = Table(rows, colWidths=[35, 273, 187], hAlign="LEFT")
    table.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#f8eddb")), ("VALIGN", (0, 0), (-1, -1), "TOP"),
                               ("BOX", (0, 0), (-1, -1), .5, colors.HexColor("#dedede")), ("INNERGRID", (0, 0), (-1, -1), .4, colors.HexColor("#dedede")),
                               ("TOPPADDING", (0, 0), (-1, -1), 10), ("BOTTOMPADDING", (0, 0), (-1, -1), 10)]))
    story += [table, Spacer(1, 12),
              p("À la réception, le stagiaire vérifie les références, l'état apparent, le fonctionnement et la présence des accessoires. Il signale par écrit toute anomalie ou pièce manquante afin qu'une réserve soit enregistrée. La signature de cette convention ne vaut pas, à elle seule, constat de remise effective du matériel."),
              p("Article 4 - Conditions d'utilisation", heading),
              p("Le matériel est destiné en priorité aux besoins de la formation. Le stagiaire respecte les consignes pédagogiques, les licences des logiciels, les droits d'auteur et la confidentialité des informations auxquelles il accède. Il n'utilise pas le matériel pour une activité illicite ou susceptible de compromettre sa sécurité."),
              p("Avant la cession prévue à l'article 2, il ne peut ni vendre le matériel, ni le céder, le donner en garantie ou le prêter à un tiers sans l'accord écrit du centre. Le badge, lorsqu'il est fourni, est personnel et utilisé conformément aux consignes du centre."),
              PageBreak(),
              p("Article 5 - Garde, entretien et précautions", heading),
              p("Le stagiaire conserve le matériel avec soin et le protège contre les chocs, les liquides, les températures excessives et le vol. Il utilise un moyen de transport adapté, évite de le laisser sans surveillance et conserve ensemble les accessoires remis. Il applique les consignes du fabricant pour le nettoyage, la recharge et les mises à jour de sécurité."),
              p("Sans l'accord du centre, il ne démonte pas le matériel, ne fait pas effectuer de réparation et ne retire pas les dispositifs de protection ou de gestion éventuellement installés. L'usure normale résultant d'un usage conforme, sans faute du stagiaire, ne constitue pas une dégradation à sa charge."),
              p("Article 6 - Panne, dommage, perte ou vol", heading),
              p("Tout incident est signalé au centre dès sa découverte, par téléphone au 04 22 47 07 68 puis, si nécessaire, confirmé par écrit à ecole@integraleacademy.com. Le signalement précise le matériel concerné, la date et les circonstances connues ; des photographies ou justificatifs peuvent être joints. En cas de vol, le stagiaire effectue les démarches utiles auprès des autorités et transmet le justificatif disponible."),
              p("En cas de panne ou de risque pour la sécurité, le stagiaire cesse d'utiliser l'équipement et suit les instructions du centre. Celui-ci examine l'origine de l'incident et les suites possibles : diagnostic, garantie, réparation ou solution temporaire selon les disponibilités. Un incident ne déclenche pas, à lui seul, une facturation automatique ; les circonstances et les responsabilités sont examinées."),
              p("Article 7 - Comptes et données sur l'appareil", heading),
              p("Lorsqu'un appareil numérique est remis, le stagiaire protège ses accès par un code et sauvegarde ses travaux. Il ne communique pas ses mots de passe personnels au centre. Avant une intervention ou une restitution, il convient des sauvegardes et déconnexions nécessaires. En cas de restitution, il retire ses comptes personnels et les verrous associés ; en cas de cession, le centre organise le retrait de ses éventuels outils de gestion."),
              p("Article 8 - Restitution en cas d'abandon", heading),
              p(f"En cas d'abandon définitif de la formation avant le <b>{end}</b>, le stagiaire restitue l'ensemble du matériel et des accessoires. Pour l'apprenti, la restitution intervient dans les <b>5 jours suivant la rupture du contrat d'apprentissage</b> accompagnant cet abandon ; hors apprentissage, dans les 5 jours suivant la notification écrite de l'abandon au centre. Une rupture du contrat d'apprentissage avec poursuite de la formation au centre ne vaut pas, à elle seule, abandon."),
              p("La restitution est organisée avec le centre, à l'adresse indiquée en première page. Le matériel doit être complet, propre et en état de fonctionnement, compte tenu de l'usure normale et des réserves signalées. Les parties vérifient les numéros, accessoires et éventuelles anomalies ; un écrit confirme la restitution et les observations de chacune."),
              NextPageTemplate("Signature"), PageBreak(),
              p("Article 9 - Pénalités en cas de manquement", heading),
              p("En cas d'abandon avant la fin de formation et de non-restitution, de restitution incomplète ou de dégradation imputable au stagiaire, les pénalités prévues pour les seuls éléments concernés sont les suivantes :")]
    for label, serial, amount in items:
        euros = f"{Decimal(amount):.2f}".replace(".", ",")
        story.append(p(f"<b>1 {e(label)} : {euros} euros</b>"))
    story += [p("Le centre communique par écrit le manquement constaté, les éléments concernés et le montant réclamé, afin que le stagiaire puisse présenter ses observations. Sauf inexécution définitive, une mise en demeure précède l'application de la pénalité. L'usure normale et les pannes non imputables au stagiaire en sont exclues. Les pouvoirs du juge prévus à l'article 1231-5 du Code civil demeurent applicables."),
              p("Article 10 - Échanges, différends et acceptation", heading),
              p("Les parties conservent leurs échanges écrits relatifs au matériel et s'informent de tout changement de coordonnées utile à son suivi. En cas de désaccord, elles recherchent une solution amiable, sans priver l'une ou l'autre des recours prévus par la loi. À défaut d'accord, les juridictions compétentes sont déterminées par les règles légales applicables."),
              p(f"Fait à PUGET SUR ARGENS, le {french_date(generated_on)}.<br/>"
                "Le stagiaire reconnaît avoir pris connaissance des dix articles et de l'inventaire. Un exemplaire électronique signé est destiné à chacune des parties.")]
    width, height = A4
    doc = BaseDocTemplate(output_path, pagesize=A4,
                          title=f"Convention de mise à disposition - {full_name}", author="Intégrale Academy")
    # A separate final-page frame prevents any clause from overlapping signatures.
    doc.addPageTemplates([
        PageTemplate(id="Body", frames=[Frame(44, 65, width - 88, height - 191)], onPage=footer_and_header),
        PageTemplate(id="Signature", frames=[Frame(44, 300, width - 88, height - 426)], onPage=footer_and_header),
    ])
    doc.build(story)
    # Signature coordinates are only valid on this explicit, bounded template.
    from pypdf import PdfReader
    reader = PdfReader(output_path)
    if len(reader.pages) != PDF_PAGE_COUNT:
        raise ValueError("Le contenu est trop long pour le modèle de convention. Raccourcissez les informations saisies.")
    return output_path
