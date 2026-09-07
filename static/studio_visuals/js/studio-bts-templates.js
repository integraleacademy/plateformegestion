// BTS recruitment collection: ten compositions for each of six audiences.
// Illustrations are local vectors; editable copy and motion use the Studio pipeline.
export const BTS_COURSES = {
  'BTS MOS': {name:'Management opérationnel de la sécurité',emoji:'👀',icon:'monitor',topics:['Prévention','Coordination','Management']},
  'BTS PI': {name:'Professions immobilières',emoji:'🔑',icon:'home',topics:['Transaction','Location','Copropriété']},
  'BTS MCO': {name:'Management commercial opérationnel',emoji:'🛍️',icon:'shop',topics:['Relation client','Animation','Management']},
  'BTS NDRC': {name:'Négociation et digitalisation de la relation client',emoji:'💬',icon:'chat',topics:['Négociation','Digital','Fidélisation']},
  'BTS CI': {name:'Commerce international',emoji:'🌍',icon:'globe',topics:['Import-export','Langues','Prospection']},
  BTS: {name:'Trouvez le BTS qui vous ressemble',emoji:'🎓',icon:'cap',topics:['MOS','PI','MCO','NDRC','CI','CG']}
};

// [slug, name, headline, introduction, illustration, three focus labels]
const stories = {
 'BTS MOS': [
  ['supervision','PC sécurité','Prenez de la hauteur sur la sécurité.','Du PC sécurité à la coordination des équipes, découvrez un BTS au cœur des opérations.','monitor',['Observer','Analyser','Coordonner']],
  ['leadership','Leadership terrain','Le terrain a besoin de votre leadership.','Apprenez à organiser une équipe et à accompagner les missions de sécurité au quotidien.','team',['Équipe','Consignes','Mission']],
  ['prevention','Prévention des risques','Anticipez. Organisez. Faites la différence.','Analyse des risques, prévention et préparation : construisez votre regard professionnel.','radar',['Repérer','Prévenir','Préparer']],
  ['rondes','Rondes et coordination','Chaque mission mérite une bonne organisation.','Préparez les rondes, structurez les consignes et travaillez la coordination des interventions.','route',['Rondes','Consignes','Suivi']],
  ['evenement','Sécurité événementielle','Dans les coulisses des grands rendez-vous.','Accueil du public, organisation et sécurité événementielle : explorez un univers qui bouge.','ticket',['Public','Dispositif','Équipe']],
  ['planning','Organisation des équipes','Donnez le bon rythme à votre équipe.','Répartir les missions, préparer les plannings et communiquer : le management commence ici.','calendar',['Planning','Missions','Échanges']],
  ['crise','Gestion des situations','Gardez le cap quand tout s’accélère.','Travaillez l’analyse de situation, la communication et la coordination dans votre parcours MOS.','signal',['Analyser','Communiquer','Agir']],
  ['qualite','Qualité de service','La qualité se construit sur le terrain.','Consignes, suivi des prestations et relation client : donnez du sens à chaque détail.','check',['Consignes','Suivi','Qualité']],
  ['alternance','Expérience et formation','Apprenez aujourd’hui. Coordonnez demain.','Reliez les enseignements du BTS MOS à votre expérience en entreprise grâce à l’alternance.','bridge',['Formation','Entreprise','Expérience']],
  ['projet','Votre projet MOS','Votre prochain défi : manager la sécurité.','Envie d’allier organisation, terrain et responsabilités ? Découvrez le BTS MOS chez Intégrale Academy.','target',['Terrain','Organisation','Projet']]
 ],
 'BTS PI': [
  ['transaction','La transaction immobilière','Ouvrez la porte de votre avenir.','De la découverte d’un bien à la relation client, explorez les métiers de la transaction immobilière.','home',['Découverte','Conseil','Transaction']],
  ['visite','La visite immobilière','Faites visiter. Faites la différence.','Apprenez à présenter un bien, comprendre un projet et accompagner vos futurs clients.','key',['Bien','Visite','Projet']],
  ['location','La gestion locative','Derrière chaque location, un vrai métier.','Dossiers, suivi et relation avec les occupants : découvrez les enjeux de la gestion locative.','folder',['Location','Dossier','Suivi']],
  ['copropriete','La copropriété','Un immeuble. Des projets à coordonner.','Organisation, échanges et suivi : préparez-vous à comprendre la vie d’une copropriété.','building',['Immeuble','Gestion','Échanges']],
  ['estimation','Le marché immobilier','Apprenez à lire le marché immobilier.','Observez les biens, leur environnement et les attentes des clients pour construire votre analyse.','chart',['Marché','Analyse','Conseil']],
  ['conseil','Le conseil client','Les bons projets commencent par l’écoute.','Comprendre les besoins, présenter des solutions et créer une relation professionnelle de confiance.','chat',['Écoute','Besoins','Solutions']],
  ['digital','L’immobilier et le digital','L’immobilier prend une nouvelle dimension.','Présentation des biens, outils numériques et relation client : connectez vos compétences.','phone',['Biens','Digital','Clients']],
  ['negociation','La négociation immobilière','Donnez de la valeur à chaque échange.','Travaillez votre argumentation et votre posture pour accompagner un projet immobilier.','handshake',['Argumenter','Échanger','Accompagner']],
  ['alternance','Votre terrain immobilier','Un pied en cours. Un pied dans l’immobilier.','Avec le BTS PI en alternance, reliez les apprentissages à une expérience concrète en entreprise.','bridge',['Formation','Entreprise','Immobilier']],
  ['projet','Votre projet PI','Votre avenir a trouvé une nouvelle adresse.','Transaction, location ou copropriété : explorez votre voie avec le BTS Professions immobilières.','target',['Transaction','Location','Copropriété']]
 ],
 'BTS MCO': [
  ['boutique','L’unité commerciale','Entrez dans les coulisses du commerce.','Relation client, offre et organisation : découvrez ce qui fait vivre une unité commerciale.','shop',['Clients','Offre','Équipe']],
  ['experience','L’expérience client','Faites de chaque visite une expérience.','Accueil, écoute et conseil : travaillez une relation client qui donne envie de revenir.','heart',['Accueillir','Conseiller','Fidéliser']],
  ['animation','L’animation commerciale','Donnez envie. Donnez vie au commerce.','Mettez en valeur une offre et découvrez comment préparer une animation commerciale.','spark',['Offre','Mise en valeur','Animation']],
  ['management','Le management d’équipe','Votre énergie peut faire grandir une équipe.','Organisation, échanges et accompagnement : construisez vos premiers repères de manager.','team',['Organiser','Accompagner','Manager']],
  ['merchandising','Le merchandising','Le détail qui change toute une vitrine.','Présentation des produits et organisation de l’espace : cultivez votre regard commercial.','shelves',['Produits','Espace','Vitrine']],
  ['gestion','La gestion opérationnelle','Pilotez le commerce au quotidien.','Approvisionnements, stocks et suivi de l’activité : découvrez la gestion opérationnelle.','boxes',['Stocks','Flux','Activité']],
  ['omnicanal','Le commerce omnicanal','Le commerce se vit sur tous les canaux.','Du point de vente au digital, apprenez à penser une expérience client cohérente.','phone',['Boutique','Digital','Parcours']],
  ['performance','Le suivi de l’activité','Transformez l’analyse en actions.','Comprendre les indicateurs et préparer des actions : donnez une direction à votre activité.','chart',['Observer','Comprendre','Améliorer']],
  ['alternance','Le commerce en pratique','Apprenez le commerce en le vivant.','Avec le BTS MCO en alternance, faites le lien entre les cours et votre quotidien en entreprise.','bridge',['Cours','Entreprise','Pratique']],
  ['projet','Votre projet MCO','Votre prochain terrain de jeu : le commerce.','Vous aimez le contact, les projets et le travail en équipe ? Découvrez le BTS MCO.','target',['Contact','Projets','Équipe']]
 ],
 'BTS NDRC': [
  ['relation','La relation client','Votre talent commence par une conversation.','Écouter, comprendre et proposer : construisez une relation client avec le BTS NDRC.','chat',['Écouter','Comprendre','Proposer']],
  ['negociation','La négociation','Faites de vos arguments une force.','Préparez vos échanges commerciaux et apprenez à construire une proposition adaptée.','handshake',['Préparer','Argumenter','Négocier']],
  ['crm','Le suivi client','Chaque échange fait avancer la relation.','Outils de suivi, connaissance client et organisation : structurez votre démarche commerciale.','pipeline',['Contact','Échange','Suivi']],
  ['social','La relation client digitale','Connectez votre avenir au digital.','Réseaux sociaux, contenus et interactions : découvrez la relation client à l’ère numérique.','phone',['Contenus','Réseaux','Interactions']],
  ['prospection','La prospection','Osez créer de nouvelles opportunités.','Identifier des contacts, préparer une approche et organiser sa prospection : tout se travaille.','radar',['Cibler','Préparer','Contacter']],
  ['reseau','L’animation de réseaux','Les bonnes connexions font avancer.','Partenaires, distributeurs et réseaux : découvrez de nouvelles façons de développer l’activité.','network',['Partenaires','Échanges','Réseaux']],
  ['fidelisation','La fidélisation','La relation continue après la vente.','Écoute, suivi et qualité des échanges : apprenez à faire vivre la relation dans la durée.','heart',['Écoute','Suivi','Fidélisation']],
  ['distance','La relation à distance','Proche de vos clients, même à distance.','Téléphone, visio et outils digitaux : travaillez votre présence et votre posture commerciale.','headset',['Téléphone','Visio','Digital']],
  ['alternance','La relation client en pratique','Du cours au rendez-vous client.','En BTS NDRC en alternance, reliez les méthodes commerciales à votre expérience en entreprise.','bridge',['Méthodes','Entreprise','Expérience']],
  ['projet','Votre projet NDRC','Vous avez le contact. Construisez la suite.','Négociation, relation client et digital : découvrez un BTS qui réunit vos envies.','target',['Contact','Négociation','Digital']]
 ],
 'BTS CI': [
  ['monde','Votre horizon international','Votre avenir voit plus grand.','Langues, échanges et commerce : ouvrez de nouvelles perspectives avec le BTS CI.','globe',['Langues','Échanges','Commerce']],
  ['importexport','Les opérations internationales','Connectez les marchés. Ouvrez des portes.','Découvrez les opérations d’import-export et les échanges entre partenaires internationaux.','boxes',['Import','Export','Partenaires']],
  ['langues','Les langues et les échanges','Les langues donnent de l’élan à vos projets.','Travaillez votre communication professionnelle pour échanger dans un contexte international.','chat',['Langues','Culture','Communication']],
  ['logistique','La chaîne logistique','Suivez le parcours derrière chaque échange.','Transport, documents et coordination : explorez la logistique du commerce international.','route',['Transport','Documents','Coordination']],
  ['prospection','La prospection internationale','Allez à la rencontre de nouveaux marchés.','Analysez un environnement, repérez des contacts et préparez votre démarche de prospection.','radar',['Marchés','Contacts','Prospection']],
  ['interculturel','Les relations interculturelles','Apprenez à travailler au-delà des frontières.','Comprendre les cultures et adapter ses échanges : une autre dimension de la relation professionnelle.','network',['Cultures','Écoute','Coopération']],
  ['negociation','Les partenaires internationaux','Créez des liens qui traversent les frontières.','Préparez vos échanges et découvrez les relations avec des partenaires internationaux.','handshake',['Partenaires','Échanges','Relation']],
  ['veille','La veille internationale','Comprenez un monde qui bouge.','Observez les marchés, recherchez l’information et développez votre capacité d’analyse.','chart',['Information','Marchés','Analyse']],
  ['alternance','L’international en pratique','Un projet international. Un parcours concret.','Reliez les enseignements du BTS CI à l’expérience en entreprise grâce à l’alternance.','bridge',['Formation','Entreprise','International']],
  ['projet','Votre projet CI','Curieux du monde ? Faites-en votre projet.','Langues, ouverture et commerce : explorez le BTS Commerce international chez Intégrale Academy.','target',['Curiosité','Ouverture','Commerce']]
 ],
 BTS: [
  ['univers','Tous nos BTS','Six univers. Votre prochaine direction.','Sécurité, immobilier, commerce, relation client, international ou comptabilité : trouvez votre BTS.','catalog',['MOS','PI','MCO','NDRC','CI','CG']],
  ['avenir','Votre avenir après le bac','Après le bac, donnez du relief à vos envies.','Explorez nos six BTS et construisez un projet qui vous ressemble avec Intégrale Academy.','cap',['Choisir','Apprendre','Avancer']],
  ['competences','Vos futures compétences','Des envies aux compétences.','Organisation, conseil, gestion ou négociation : découvrez les savoir-faire à construire dans nos BTS.','grid',['Savoir-faire','Pratique','Projet']],
  ['orientation','Votre orientation','Trouvez votre voie, gardez votre ambition.','Comparez nos univers de formation et échangez avec notre équipe pour préciser votre choix.','route',['Univers','Choix','Orientation']],
  ['alternance','L’alternance','Les cours vous forment. L’expérience aussi.','Découvrez nos BTS en alternance et préparez un parcours entre formation et entreprise.','bridge',['Formation','Entreprise','Expérience']],
  ['collectif','L’énergie du collectif','Votre avenir se construit aussi ensemble.','Rencontres, projets et apprentissages : imaginez votre place au sein d’Intégrale Academy.','team',['Rencontres','Projets','Collectif']],
  ['projet','Votre projet de formation','L’envie est là. Donnons-lui une direction.','Parlons de vos intérêts et des parcours BTS qui peuvent correspondre à votre projet.','target',['Envies','Échanges','Parcours']],
  ['questions','Vos questions sur les BTS','Un BTS en tête ? Parlons-en.','Formation, alternance et inscription : notre équipe vous aide à préparer votre prochaine étape.','chat',['Formation','Alternance','Inscription']],
  ['domaines','Les six domaines','Votre avenir a plusieurs portes d’entrée.','MOS, PI, MCO, NDRC, CI et CG : explorez nos six BTS et découvrez celui qui vous correspond.','catalog',['MOS','PI','MCO','NDRC','CI','CG']],
  ['inscription','Votre candidature','Le prochain chapitre commence avec vous.','Découvrez nos BTS et contactez notre équipe pour préparer votre projet de candidature.','spark',['Découverte','Projet','Candidature']]
 ]
};
const layouts=['workspace','spotlight','bento','poster','flow','arch','editorial','cards','orbit','launch'];
const motions=['pulse','float','','bob','rise','','float','','orbit',''];
export const BTS_DESIGNS=Object.entries(stories).flatMap(([formation,rows])=>rows.map(([slug,name,title,introduction,icon,subjects],index)=>({
 id:`bts_${formation==='BTS'?'tous':formation.slice(4).toLowerCase()}_${slug}`,formation,slug,name,title,introduction,icon,subjects,
 layout:layouts[index],motion:motions[index],index:index+1,
 contentDefaults:{title,introduction,cta:formation==='BTS'?'Découvrir nos BTS':`Découvrir le ${formation}`}
})));
const designsById=new Map(BTS_DESIGNS.map(d=>[d.id,d]));
const esc=value=>String(value??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));

// Recognisable métier objects, deliberately free of fictional dates or metrics.
const glyphs={
 monitor:'M10 14h76v49H10z M35 82h26 M48 64v17 M19 24h24v28H19z M53 24h23v12H53z M53 43h23v9H53z',
 home:'M8 42 48 10 88 42 M19 35v51h58V35 M39 86V58h19v28 M29 43h8 M61 43h8',
 shop:'M12 37h72v49H12z M8 37l8-25h64l8 25 M31 12v25 M64 12v25 M25 86V58h23v28 M58 56h16v16H58z',
 chat:'M12 12h72v53H51L28 84V65H12z M25 29h46 M25 43h32',
 globe:'M48 10a38 38 0 1 0 0 76 38 38 0 1 0 0-76 M10 48h76 M48 10c-23 17-23 59 0 76 M48 10c23 17 23 59 0 76 M20 24c19 12 37 12 56 0 M20 72c19-12 37-12 56 0',
 cap:'M7 34 48 13 89 34 48 55 7 34 M24 44v25q24 22 48 0V44 M88 35v33',
 team:'M34 25a11 11 0 1 0 22 0 11 11 0 1 0-22 0 M25 81V61q20-25 40 0v20 M7 69V56q4-14 15-14 M88 69V56q-4-14-15-14 M12 22a8 8 0 1 0 16 0 8 8 0 1 0-16 0 M69 22a8 8 0 1 0 16 0 8 8 0 1 0-16 0',
 radar:'M48 10a38 38 0 1 0 38 38 M48 26a22 22 0 1 0 22 22 M48 48 80 16 M48 44a4 4 0 1 0 0 8 4 4 0 1 0 0-8',
 route:'M12 74h28q15 0 15-15V37q0-15 15-15h15 M71 10l14 12-14 12 M10 65a9 9 0 1 0 0 18 9 9 0 1 0 0-18',
 ticket:'M12 21h72v18a9 9 0 0 0 0 18v18H12V57a9 9 0 0 0 0-18z M61 30v8 M61 45v8 M61 60v7 M25 37h22 M25 51h16',
 calendar:'M12 20h72v64H12z M12 39h72 M30 10v20 M66 10v20 M27 52h8 M47 52h8 M67 52h5 M27 67h8 M47 67h8',
 signal:'M14 21h68v48H48L31 83V69H14z M48 32v16 M48 58h.1 M7 9h12 M77 9h12',
 check:'M22 14h52v71H22z M35 9h26v14H35z M32 42l7 7 14-14 M32 67l7 7 14-14 M60 43h5 M60 68h5',
 bridge:'M8 74h80 M15 73V44q33-48 66 0v29 M29 31v43 M48 18v56 M67 31v43',
 target:'M48 11a37 37 0 1 0 37 37 M48 28a20 20 0 1 0 20 20 M48 48l33-33 M64 15h17v17',
 key:'M22 12a20 20 0 1 0 0 40 20 20 0 1 0 0-40 M37 47l40 40h12V74L75 61h-9L51 46 M18 26h.1',
 folder:'M10 29V15h29l9 14h38v55H10z M27 49h42 M27 64h29',
 building:'M21 87V10h54v77 M10 87h76 M33 26h6 M57 26h6 M33 42h6 M57 42h6 M33 58h6 M57 58h6 M43 87V73h11v14',
 chart:'M12 13v71h74 M25 62l18-21 18 8 20-27 M68 22h13v14',
 phone:'M29 8h38q9 0 9 9v62q0 9-9 9H29q-9 0-9-9V17q0-9 9-9 M36 19h24 M41 76h14 M32 39h32 M32 52h23',
 handshake:'M8 32l17-17 23 11 23-11 17 17-17 39-17 12-34-25z M26 26l22 16 12-4 11 18 M40 59l16 13 M32 66l13 11',
 heart:'M48 81 14 48C-10 16 29 1 48 24 67 1 106 16 82 48Z',
 spark:'M48 7 59 34 88 48 59 60 48 89 36 60 7 48 36 34Z',
 shelves:'M10 10v76 M86 10v76 M10 46h76 M10 83h76 M20 20h18v26H20z M55 17h19v29H55z M25 57h20v26H25z M60 58h14v25H60z',
 boxes:'M10 48l20-12 20 12v25L30 85 10 73z M48 19 68 7 88 19v25L68 56 48 44z M10 48l20 12 20-12 M30 60v25 M48 19l20 12 20-12 M68 31v25',
 pipeline:'M8 14h23v18H8z M37 14h23v18H37z M66 14h23v18H66z M8 43h23v18H8z M37 43h23v18H37z M66 43h23v18H66z M8 72h23v12H8z M37 72h23v12H37z',
 network:'M39 39a13 13 0 1 0 18 18 13 13 0 1 0-18-18 M48 35V19 M48 61v17 M35 48H19 M61 48h17 M8 8h16v16H8z M72 8h16v16H72z M8 72h16v16H8z M72 72h16v16H72z M27 27l12 12 M57 57l12 12 M27 69l12-12 M57 39l12-12',
 headset:'M13 56V42a35 35 0 0 1 70 0v24q0 18-24 18 M9 45h16v24H9z M71 45h16v24H71z M43 77h17v12H43z',
 grid:'M10 10h30v30H10z M56 10h30v30H56z M10 56h30v30H10z M56 56h30v30H56z'
};
function icon(name,x,y,size=96){return `<g transform="translate(${x} ${y}) scale(${size/96})" fill="none" stroke="currentColor" stroke-width="4.5" stroke-linecap="round" stroke-linejoin="round"><path d="${glyphs[name]||glyphs.cap}"/></g>`;}
const rect=(x,y,w,h,fill,rx=20)=>`<rect x="${x}" y="${y}" width="${w}" height="${h}" rx="${rx}" fill="${fill}"/>`;
export function renderBtsIllustration(d){
 const course=BTS_COURSES[d.formation],a='var(--bts-accent)',s='var(--bts-tint)',line='var(--bts-line)';
 const mode=(d.index-1)%5;
 let art='';
 if(d.icon==='catalog'){
  art=Object.values(BTS_COURSES).slice(0,5).map((c,i)=>{const x=26+(i%3)*156,y=35+Math.floor(i/3)*159;return rect(x,y,138,138,'#fff',25)+icon(c.icon,x+29,y+27,78)}).join('')+rect(338,194,138,138,a,25)+`<g style="color:#fff">${icon('chart',367,224,78)}</g>`;
 }else if(mode===0){
  art=rect(22,25,456,308,'#fff',27)+rect(22,25,456,50,s,27)+[47,66,85].map(x=>`<circle cx="${x}" cy="50" r="5" fill="${a}"/>`).join('')+rect(44,94,217,215,s,19)+icon(d.icon,82,125,143)+rect(280,96,174,93,a,18)+`<g style="color:#fff">${icon(course.icon,338,113,57)}</g>`+[215,250,285].map((y,i)=>rect(283,y,164-i*25,11,line,5)).join('');
 }else if(mode===1){
  art=`<circle cx="250" cy="180" r="144" fill="${s}"/><circle cx="250" cy="180" r="117" fill="#fff" stroke="${line}" stroke-width="2"/>`+icon(d.icon,164,94,172)+rect(23,269,148,64,a,18)+`<g style="color:#fff">${icon('spark',72,282,40)}</g>`+rect(365,24,104,96,'#fff',22)+icon(course.icon,387,40,64);
 }else if(mode===2){
  art=rect(24,25,270,304,'#fff',24)+rect(44,44,230,213,s,19)+icon(d.icon,83,83,148)+rect(50,276,203,13,line,6)+rect(50,302,144,9,line,4)+rect(312,25,164,141,a,24)+`<g style="color:#fff">${icon(course.icon,356,55,77)}</g>`+rect(312,184,164,145,'#fff',24)+icon('check',356,216,77);
 }else if(mode===3){
  art=`<path d="M72 261C145 41 363 45 430 278" fill="none" stroke="${line}" stroke-width="3" stroke-dasharray="8 10"/>`+rect(135,65,230,232,'#fff',33)+icon(d.icon,179,105,144)+rect(22,232,137,98,s,23)+icon('check',61,252,59)+rect(354,229,123,99,a,23)+`<g style="color:#fff">${icon(course.icon,386,249,59)}</g>`;
 }else{
  art=rect(34,38,432,272,'#fff',30)+rect(57,63,191,222,s,24)+icon(d.icon,80,101,145)+icon(course.icon,297,72,80)+`<path d="M281 273v-89m0 89h148" fill="none" stroke="${line}" stroke-width="4"/>`+[47,79,115].map((h,i)=>rect(305+i*42,267-h,26,h,i===2?a:s,9)).join('');
 }
 return `<svg viewBox="0 0 500 360" xmlns="http://www.w3.org/2000/svg" role="img" aria-label="${esc(d.name)}" style="color:${a}">${art}</svg>`;
}
const editable=(key,text,tag,cls)=>`<${tag} class="${cls}" data-content-key="${key}" data-layout-role="${key}" data-fit="${key==='title'?'title':key==='cta'?'cta':'body'}">${esc(text)}</${tag}>`;
export function renderBtsTemplateBody(ctx){
 const d=designsById.get(ctx.template.id);if(!d)throw new Error(`Template BTS inconnu : ${ctx.template.id}`);
 const course=BTS_COURSES[d.formation],c=ctx.slide.content?._manual?ctx.slide.content:{...ctx.slide.content,...d.contentDefaults};
 const kicker=`<div class="bts-kicker" data-layout-role="bts-kicker"><span class="bts-emoji" data-studio-decorative="true">${course.emoji}</span><span>${d.formation==='BTS'?'NOS BTS EN ALTERNANCE':esc(d.formation)+' · ALTERNANCE'}</span></div>`;
 const heading=editable('title',c.title,'h1','bts-title');
 const intro=editable('introduction',c.introduction,'p','bts-intro');
 const cta=`<div class="bts-action">${editable('cta',c.cta,'span','bts-cta')}<b aria-hidden="true">↗</b></div>`;
 const topics=`<div class="bts-topics" data-layout-role="bts-topics">${d.subjects.map(s=>`<span>${esc(s)}</span>`).join('')}</div>`;
 const courseNames=d.formation==='BTS'&&d.subjects.length<6?'<div class="bts-course-list" data-layout-role="bts-all-courses">MOS · PI · MCO · NDRC · CI · CG</div>':'';
 const visual=`<figure class="bts-visual" data-layout-role="bts-visual-${d.icon}"><div class="bts-windowbar" data-studio-decorative="true"><i></i><i></i><i></i><span>INTÉGRALE ACADEMY</span></div><div class="bts-illustration"${d.motion?` data-motion="${d.motion}"`:''}>${renderBtsIllustration(d)}</div><figcaption data-fit="meta">${esc(d.name)}</figcaption></figure>`;
 const top=`<header class="bts-heading">${kicker}${heading}</header>`;
 const copy=`<section class="bts-copy">${kicker}${heading}${intro}${courseNames}${cta}</section>`;
 let body=copy+visual+topics;
 if(['spotlight','flow'].includes(d.layout))body=top+visual+`<section class="bts-bottom">${intro}${courseNames}${cta}</section>`+topics;
 if(d.layout==='bento')body=top+`<section class="bts-copy bts-copy-secondary">${intro}${courseNames}${cta}</section>`+visual+topics;
 if(['arch','orbit','editorial'].includes(d.layout))body=visual+copy+topics;
 return `<main class="bts-main bts-${d.layout}" data-layout-role="bts-${d.layout}">${body}</main>`;
}
