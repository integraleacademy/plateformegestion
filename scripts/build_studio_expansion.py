"""Build exactly 35 illustrated layouts and 15 editable canvases (idempotent)."""
import copy
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PATH = ROOT / 'static/studio_visuals/data/templates.json'
catalog = json.loads(PATH.read_text())
assets = {a['file']: a for a in json.loads((ROOT / 'static/studio_visuals/img/manuals/sources.json').read_text())['assets']}

def asset(name):
    return {key: assets[name][key] for key in ('file', 'alt', 'width', 'height')}

def steps(*items):
    return [dict(title=title, text=text) for title, text in items]

new = []
universes = [
    ('aps', 'APS', 'aps_ronde.webp', 'La vigilance au quotidien', 'Sécurité', 'Votre parcours vers la sécurité privée'),
    ('ssiap', 'SSIAP 1', 'ssiap_prevention.webp', 'Prévenir commence sur le terrain', 'Prévenir', 'Votre parcours en sécurité incendie'),
    ('a3p', 'A3P', 'a3p_evenement.webp', 'L’attention fait la différence', 'Protéger', 'Votre parcours vers la protection'),
    ('vtc', 'VTC', 'vtc_hotel.webp', 'Le service, dans chaque détail', 'Accueillir', 'Votre projet de chauffeur VTC'),
    ('direction', 'Direction', 'direction_audit.webp', 'Donnez du cap à votre équipe', 'Piloter', 'Votre projet de direction'),
    ('bts', 'BTS', 'bts_projet.webp', 'Apprendre en faisant', 'Progresser', 'Votre projet prend forme en BTS'),
    ('general', 'Général', 'general_atelier.webp', 'Osez un nouveau départ', 'Évoluer', 'Construisez votre prochain chapitre'),
]
layouts = [
    ('spotlight', 'Portrait de métier', 'UN MÉTIER À DÉCOUVRIR', 'cover', []),
    ('editorial', 'Page de magazine', 'LE MÉTIER EN PERSPECTIVE', 'editorial', ['highlightedText', 'steps']),
    ('storyboard', 'Le métier en trois scènes', 'UNE HISTOIRE DE TERRAIN', 'process', ['steps']),
    ('dialogue', 'Questions de terrain', 'ON EN PARLE ?', 'faq', ['faq']),
    ('roadmap', 'Feuille de route', 'VOTRE PROCHAIN CHAPITRE', 'process', ['steps']),
]
for key, label, picture, title, word, roadmap_title in universes:
    base = next(t for t in catalog['templates'] if t['id'] == f'manual_{key}_cover')
    for layout, name, eyebrow, family, fields in layouts:
        t = copy.deepcopy(base)
        t.update(id=f'manual_{key}_{layout}', name=f'ILLUSTRÉ · {label} · {name}',
                 description=f'{name}, une nouvelle composition illustrée pour {label}. Textes modifiables dans les quatre formats.',
                 family=family, manualLayout=layout, isManualExpansion=True, isStudioExpansion=True,
                 illustration=asset(picture), illustrations=[asset(picture), base['illustration'], base['secondaryIllustration']],
                 supportedContent=['eyebrow','title','introduction',*fields,'cta','footer'])
        c=t['contentDefaults']
        c.update(eyebrow=eyebrow, title=title, highlightedText=word)
        if layout == 'roadmap':
            c.update(title=roadmap_title, steps=steps(('Votre point de départ','Échangez sur votre expérience et vos envies.'),('Votre formation','Identifiez le parcours adapté à votre projet.'),('Votre prochaine étape','Préparez la suite avec notre équipe.')))
        if layout == 'dialogue':
            c.update(title=f'Parlons de votre projet {label}' if key!='general' else 'Parlons de votre avenir', faq=[
                dict(q='Quel parcours choisir ?', a='Présentez votre projet à notre équipe.'),
                dict(q='Comment se préparer ?', a='Faites le point sur les conditions d’accès.'),
                dict(q='Et les prochaines dates ?', a='Contactez le centre pour les sessions à venir.')])
        new.append(t)

FORMATS=['instagram_square','instagram_portrait','instagram_story','linkedin_landscape']
common=dict(eyebrow='VOTRE CANEVAS À PERSONNALISER', title='Votre projet de formation', introduction='Présentez votre sujet en quelques mots.', cta='Contactez notre équipe', duration='', financing='', availability='', startDate='', stats=[], steps=[], faq=[])
def content(title, intro, **kwargs):
    return {**copy.deepcopy(common), 'title': title, 'introduction':intro, **kwargs}

definitions=[
 ('session','ticket','Ticket de session','general_atelier.webp',content('Votre prochaine session','Présentez ici la formation et le public concerné.',eyebrow='PROCHAINE SESSION',startDate='Date à préciser',location='Lieu à préciser',duration='Horaires à préciser',cta='Demander les informations')),
 ('programme','programme','Programme en 4 modules','bts_projet.webp',content('Au programme','Un parcours à construire selon vos objectifs.',eyebrow='VOTRE PROGRAMME',steps=steps(('Comprendre','Présentez les notions essentielles.'),('S’exercer','Décrivez les mises en pratique.'),('Échanger','Précisez les temps de partage.'),('Faire le point','Présentez les modalités du bilan.')))),
 ('checklist','checklist','Checklist de préparation','aps_ronde.webp',content('Prêt pour le départ ?','Adaptez cette liste aux informations de votre centre.',eyebrow='LA CHECKLIST',steps=steps(('Votre inscription','Vérifier la confirmation.'),('Vos documents','Préparer les pièces demandées.'),('Votre trajet','Repérer le lieu de formation.'),('Vos horaires','Consulter la convocation.'),('Votre matériel','Suivre les indications reçues.'),('Vos questions','Noter les points à éclaircir.')))),
 ('fiche','fiche','Fiche pratique','ssiap_prevention.webp',content('Votre fiche pratique','Objectif : expliquez ce que le lecteur va apprendre.',eyebrow='LA MÉTHODE EN 3 ÉTAPES',steps=steps(('Observer','Décrivez le point à repérer.'),('Comprendre','Expliquez le principe essentiel.'),('Appliquer','Proposez une mise en pratique.')))),
 ('comparatif','comparatif','Comparatif à deux colonnes','direction_audit.webp',content('Deux pistes, un projet','Remplacez chaque critère par une information vérifiée.',eyebrow='POUR BIEN CHOISIR',before='Parcours A',after='Parcours B',steps=steps(('À qui s’adresse-t-il ?','Décrivez le public du parcours A.'),('Quel rythme ?','Précisez son organisation.'),('À qui s’adresse-t-il ?','Décrivez le public du parcours B.'),('Quel rythme ?','Précisez son organisation.')))),
 ('chronologie','chronologie','Frise du parcours','general_accompagnement.webp',content('Votre parcours, pas à pas','Présentez les étapes de votre accompagnement.',eyebrow='LA FEUILLE DE ROUTE',steps=steps(('Échanger','Clarifier le projet.'),('Préparer','Constituer le dossier.'),('Se former','Développer ses compétences.'),('Poursuivre','Préparer la suite.')))),
 ('objectifs','objectifs','Objectifs pédagogiques','bts_projet.webp',content('Ce que vous allez développer','À l’issue du parcours : indiquez votre objectif principal.',eyebrow='LES OBJECTIFS',steps=steps(('Connaissances','Précisez les notions à comprendre.'),('Savoir-faire','Décrivez les gestes ou méthodes.'),('Posture','Présentez les attitudes attendues.')))),
 ('faq','faq','Questions et réponses','general_atelier.webp',content('Vos questions, nos réponses','Complétez les réponses avec les informations du centre.',eyebrow='ON VOUS RÉPOND',faq=[dict(q=q,a=a) for q,a in [('Pour quel public ?','Indiquez le public concerné.'),('Quels prérequis ?','Précisez les conditions d’accès.'),('Quel calendrier ?','Ajoutez les dates confirmées.'),('Comment s’inscrire ?','Présentez la démarche à suivre.')]])),
 ('chiffres','chiffres','Chiffres clés','direction_audit.webp',content('Votre formation en chiffres','Ajoutez vos données vérifiées et leur période de référence.',eyebrow='LES REPÈRES',stats=[dict(label=x,value='—') for x in ['Durée du parcours','Nombre de modules','Effectif du groupe','Année de référence']])),
 ('temoignage','temoignage','Parole d’apprenant','bts_campus.webp',content('Une expérience à partager','Insérez un témoignage que vous êtes autorisé à publier.',eyebrow='PAROLE D’APPRENANT',quote='Votre témoignage à insérer ici.',author='Prénom · Parcours suivi')),
 ('evenement','evenement','Invitation à un événement','general_equipe.webp',content('Rencontrons-nous','Présentez les activités et les personnes à rencontrer.',eyebrow='VOTRE INVITATION',startDate='Date à préciser',location='Lieu à préciser',duration='Horaires à préciser',cta='Demander le programme')),
 ('annonce','annonce','Annonce illustrée','vtc_hotel.webp',content('Votre nouvelle commence ici','Présentez votre actualité en une ou deux phrases.',eyebrow='À LA UNE',cta='En savoir plus')),
 ('carnet','carnet','Carnet de révision','general_atelier.webp',content('L’essentiel à retenir','Transformez vos notes en repères faciles à relire.',eyebrow='LE CARNET DE RÉVISION',steps=steps(('Une notion','Votre définition en quelques mots.'),('Une méthode','Les étapes à mémoriser.'),('Un exemple','Une situation pour comprendre.'),('Une question','Un point à approfondir.')))),
]
fields={
 'ticket':['startDate','location','duration'], 'programme':['steps'], 'checklist':['steps'], 'fiche':['steps'],
 'comparatif':['before','after','steps'], 'chronologie':['steps'], 'objectifs':['steps'], 'faq':['faq'],
 'chiffres':['stats'], 'temoignage':['quote','author'], 'evenement':['startDate','location','duration'], 'annonce':[], 'carnet':['steps']}

def canvas(key,layout,name,picture,defaults):
    return dict(id=f'canvas_{key}',name=f'CANEVAS · {name}',description=f'{name} illustré et personnalisable. Textes, couleurs et quatre formats adaptables à votre formation.',family='canvas',renderer='renderCanvasTemplate',status='ready',version=1,isCanvas=True,isStudioExpansion=True,collection='Canevas personnalisables',formationPreset='OR',canvasLayout=layout,supportedFormats=FORMATS,suitableRoles=['cover','content','conclusion'],supportedContent=['eyebrow','title','introduction',*fields[layout],'cta','footer'],contentLabels={'steps':'Contenu des blocs','before':'Colonne gauche','after':'Colonne droite','startDate':'Date à afficher'},density='modulable',style='canevas illustré',brandLayout='top-horizontal',illustration=asset(picture),contentDefaults=defaults)

for definition in definitions:
    new.append(canvas(*definition))

discovery=[
 ('annonce',content('Découvrez votre future formation','Présentez en une phrase ce qui rend ce parcours utile.',eyebrow='DÉCOUVERTE · 1/5',cta='Faites défiler')),
 ('objectifs',content('Trois objectifs pour avancer','Votre objectif principal, formulé simplement.',eyebrow='LES OBJECTIFS · 2/5',steps=steps(('Comprendre','Indiquez la première compétence.'),('Pratiquer','Décrivez la mise en application.'),('Progresser','Présentez le résultat attendu.')),cta='La suite du parcours')),
 ('programme',content('Un programme concret','Adaptez les quatre modules à votre formation.',eyebrow='LE PROGRAMME · 3/5',steps=copy.deepcopy(definitions[1][4]['steps']),cta='Vos questions')),
 ('faq',content('Avant de vous lancer','Remplacez ces réponses par vos informations à jour.',eyebrow='LES REPÈRES · 4/5',faq=copy.deepcopy(definitions[7][4]['faq']),cta='Préparons votre projet')),
 ('evenement',content('Parlons de votre projet','Invitez votre lecteur à prendre contact avec le centre.',eyebrow='VOTRE PROCHAINE ÉTAPE · 5/5',startDate='À votre rythme',location='Intégrale Academy',duration='Informations sur demande',cta='Contactez notre équipe')),
]
advice=[
 ('annonce',content('Préparez votre formation','Quelques repères pour aborder votre parcours sereinement.',eyebrow='LES BONS REPÈRES · 1/5',cta='Faites défiler')),
 ('checklist',content('Avant le premier jour','Une liste à adapter aux consignes de votre centre.',eyebrow='SE PRÉPARER · 2/5',steps=copy.deepcopy(definitions[2][4]['steps']),cta='Pendant la formation')),
 ('fiche',content('Apprendre avec méthode','Objectif : construire des habitudes qui vous aident à progresser.',eyebrow='S’ORGANISER · 3/5',steps=steps(('Prendre des notes','Relever les idées essentielles.'),('Poser des questions','Faire préciser ce qui reste flou.'),('S’entraîner','Revenir sur les exercices proposés.')),cta='Pour vos révisions')),
 ('carnet',content('Votre carnet de repères','Reprenez chaque point avec vos propres exemples.',eyebrow='FAIRE LE POINT · 4/5',steps=copy.deepcopy(definitions[12][4]['steps']),cta='La prochaine étape')),
 ('annonce',content('À vous de jouer','Besoin d’un renseignement ? Échangez avec notre équipe.',eyebrow='RESTONS EN CONTACT · 5/5',cta='Parlons de votre projet')),
]
for key,name,pages,picture in [('decouverte','Carrousel découverte',discovery,'general_atelier.webp'),('conseils','Carrousel conseils',advice,'bts_projet.webp')]:
    t=canvas('carousel_'+key,pages[0][0],name+' · 5 pages',picture,copy.deepcopy(pages[0][1]))
    t.update(isCarousel=True,pageCount=5,pages=[dict(layout=layout,contentDefaults=c,supportedContent=['eyebrow','title','introduction',*fields[layout],'cta','footer']) for layout,c in pages])
    new.append(t)

assert len(new)==50 and sum(bool(t.get('isCanvas')) for t in new)==15
ids={t['id'] for t in new}
catalog['templates']=new+[t for t in catalog['templates'] if t['id'] not in ids]
assert len({t['id'] for t in catalog['templates']})==len(catalog['templates'])
PATH.write_text(json.dumps(catalog,ensure_ascii=False,indent=2)+'\n')
print(f'{len(new)} nouveaux modèles · {len(catalog["templates"])} modèles au total')
