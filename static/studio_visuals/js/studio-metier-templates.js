import {EXTRA_METIER_DEFINITIONS,createExtraMetierScenes} from './studio-metier-more.js';
// Profession-specific artwork: every subject has its own vector scene. Shared
// primitives keep colors tied to the training palette and exports resolution-free.
const courses={SSIAP:['SSIAP','Sécurité incendie'],APS:['APS','Prévention et sécurité'],VTC:['VTC','Chauffeur VTC'],A3P:['A3P','Protection rapprochée'],DIRIGEANT:['DESP','Direction d’entreprise']};
const definitions={
 SSIAP:[
  ['ssi','Le système de sécurité incendie','Au cœur du SSI. Au départ de votre avenir.','Découvrez l’univers du système de sécurité incendie et préparez votre projet de formation.','SSI · Surveillance · Prévention','console','pulse'],
  ['ronde','La ronde incendie','La vigilance se construit sur le terrain.','Rondes incendie, observation des lieux, repérage : donnez une dimension concrète à votre projet.','Rondes · Observation · Prévention','editorial','float'],
  ['pc','Le PC sécurité','Chaque information compte. Votre formation aussi.','Plongez dans l’univers du PC sécurité : surveillance, transmissions et coordination.','PC sécurité · Surveillance · Transmission','cinema','pulse'],
  ['alerte','L’alerte incendie','Repérer. Alerter. Garder le cap.','Préparez-vous aux missions de sécurité incendie avec une formation tournée vers le métier.','Alerte · Vigilance · Communication','poster','pulse'],
  ['evacuation','L’évacuation','Guider les autres commence par se former.','Cheminements, sorties et accompagnement : découvrez les enjeux de l’évacuation.','Évacuation · Orientation · Accompagnement','path','float'],
  ['extincteur','Les moyens de secours','Les bons gestes s’apprennent.','Faites des moyens de secours un sujet concret de votre parcours en sécurité incendie.','Matériel · Préparation · Mise en situation','showcase',''],
  ['detection','La détection incendie','Un détail repéré. Une vigilance renforcée.','Découvrez la place de la détection et de l’observation dans la prévention incendie.','Détection · Observation · Prévention','orbit','pulse'],
  ['transmission','Les transmissions','Une information claire fait la différence.','Radio, écoute, compte rendu : préparez les échanges qui accompagnent les missions SSIAP.','Radio · Écoute · Compte rendu','duo',''],
  ['main_courante','La main courante','La rigueur laisse une trace.','Apprenez à donner une place à chaque observation dans votre futur quotidien professionnel.','Main courante · Observation · Suivi','dossier',''],
  ['prevention','La prévention au quotidien','La prévention se joue dans les détails.','Portes, circulations et équipements : ouvrez les yeux sur l’environnement de la sécurité incendie.','Bâtiment · Circulations · Prévention','architect','']
 ],
 APS:[
  ['ronde','Les rondes de sécurité','Sur le terrain, votre vigilance prend sa place.','Explorez les rondes de sécurité et l’observation des sites dans votre projet de formation APS.','Rondes · Observation · Présence','editorial','float'],
  ['bagages','L’inspection visuelle des bagages','Un regard attentif. Une posture professionnelle.','Inspection visuelle des bagages et relation avec le public : découvrez cet aspect du métier APS.','Bagages · Attention · Accueil','showcase',''],
  ['acces','Le contrôle d’accès','L’accueil et la vigilance se rencontrent.','Badges, entrées et orientation : préparez votre place dans les missions de contrôle d’accès.','Accès · Badges · Orientation','path','float'],
  ['video','La surveillance vidéo','Observer avec attention. Comprendre la situation.','Découvrez l’univers de la surveillance vidéo et son articulation avec la présence sur le terrain.','Vidéo · Observation · Terrain','console','pulse'],
  ['perimetre','La surveillance du périmètre','Chaque zone mérite votre attention.','Abords, clôtures et points de passage : donnez du sens à votre regard sur un site.','Périmètre · Points de passage · Vigilance','architect',''],
  ['evenement','La sécurité événementielle','Au cœur de l’événement, gardez le sens du service.','Accueil du public, orientation et observation : projetez-vous dans la sécurité événementielle.','Événement · Public · Orientation','cinema','pulse'],
  ['radio','Les échanges radio','Écouter. Transmettre. Rester coordonné.','Préparez la communication professionnelle qui accompagne les missions d’un agent APS.','Radio · Transmission · Coordination','duo',''],
  ['rapport','Le compte rendu','Une observation utile se transmet clairement.','Mettez la précision et la traçabilité au cœur de votre projet dans la prévention et la sécurité.','Observation · Compte rendu · Suivi','dossier',''],
  ['vigilance','La vigilance de nuit','La vigilance ne perd pas le fil.','Découvrez les missions de surveillance et les repères d’une présence attentive sur le terrain.','Surveillance · Ronde · Attention','orbit','pulse'],
  ['commerce','La sécurité en commerce','Présent, attentif, professionnel.','Accueil, observation et échanges : imaginez votre futur quotidien dans un environnement commercial.','Commerce · Présence · Relationnel','poster','']
 ],
 VTC:[
  ['ville','Le chauffeur en ville','Votre prochaine direction : chauffeur VTC.','Faites de votre intérêt pour la conduite et le service le point de départ d’un nouveau projet.','Conduite · Mobilité · Service','cinema','float'],
  ['aeroport','L’accueil à l’aéroport','Le service commence avant le premier kilomètre.','Accueil à l’aéroport, prise de contact et accompagnement : projetez-vous dans le métier de chauffeur.','Aéroport · Accueil · Accompagnement','editorial',''],
  ['reservation','La réservation','Une course se prépare dès le premier échange.','Demande client, prise en charge et organisation : découvrez les coulisses du service VTC.','Réservation · Organisation · Client','console','pulse'],
  ['itineraire','La préparation de l’itinéraire','Une destination. Une préparation soignée.','Faites de la préparation des trajets et de l’anticipation des déplacements un vrai sujet de formation.','Itinéraire · Anticipation · Mobilité','path','float'],
  ['bagages','L’accompagnement des passagers','Le sens du service voyage avec vous.','Accueil des passagers, bagages et attention aux détails : donnez du relief à votre projet VTC.','Passagers · Bagages · Attention','showcase',''],
  ['conduite','La conduite professionnelle','Prenez le volant de votre nouveau projet.','Conduite, préparation et relation client : découvrez les dimensions du métier de chauffeur VTC.','Conduite · Préparation · Professionnalisme','orbit','pulse'],
  ['confort','Le confort à bord','À bord, chaque attention compte.','Projetez-vous dans un service de transport où l’accueil et le confort du passager ont toute leur place.','Confort · Accueil · Attention','architect',''],
  ['vehicule','La préparation du véhicule','Le soin du véhicule fait partie du voyage.','Préparation, propreté et présentation : explorez le quotidien professionnel d’un chauffeur VTC.','Véhicule · Préparation · Présentation','dossier',''],
  ['client','La relation client','Un trajet se vit aussi dans la relation.','Écoute et qualité d’accueil : développez votre projet autour du service aux passagers.','Écoute · Accueil · Service','duo',''],
  ['activite','L’organisation de l’activité','Derrière le volant, un projet à construire.','Planning, organisation et suivi : préparez les différentes facettes de votre future activité VTC.','Planning · Organisation · Activité','poster','pulse']
 ],
 A3P:[
  ['accompagnement','L’accompagnement rapproché','La protection commence par la préparation.','Accompagnement, attention et coordination : découvrez l’univers de la protection physique des personnes.','Accompagnement · Préparation · Coordination','cinema','float'],
  ['briefing','Le briefing de mission','Une mission se prépare en équipe.','Briefing, répartition des rôles et échanges : donnez une direction concrète à votre projet A3P.','Briefing · Mission · Équipe','console','pulse'],
  ['itineraire','La préparation des déplacements','Anticiper le déplacement. Préparer la mission.','Explorez la préparation des itinéraires et l’organisation des déplacements dans l’univers A3P.','Itinéraire · Repérage · Préparation','path','float'],
  ['observation','L’observation de l’environnement','Lire un environnement, ça se travaille.','Développez votre intérêt pour l’observation et la préparation dans la protection des personnes.','Observation · Environnement · Attention','orbit','pulse'],
  ['arrivee','L’arrivée sur site','Chaque arrivée mérite d’être préparée.','Accès, environnement et accompagnement : projetez-vous dans la préparation d’une arrivée sur site.','Arrivée · Accès · Accompagnement','architect',''],
  ['mobilite','L’accompagnement en mobilité','En mouvement, gardez le sens de la mission.','Gares, déplacements et environnement : découvrez un autre visage de l’accompagnement rapproché.','Mobilité · Accompagnement · Coordination','editorial','float'],
  ['evenement','L’accompagnement événementiel','Une présence discrète. Une préparation précise.','Explorez les enjeux de l’accompagnement d’une personne lors d’un événement.','Événement · Présence · Préparation','showcase',''],
  ['communication','La communication d’équipe','La coordination commence par l’écoute.','Communication et échanges d’équipe : préparez les interactions qui accompagnent les missions A3P.','Écoute · Communication · Équipe','duo',''],
  ['equipe','La coordination de mission','Des rôles définis. Une équipe coordonnée.','Donnez une place à l’organisation collective dans votre projet de protection physique des personnes.','Rôles · Équipe · Mission','poster','pulse'],
  ['mission','Le dossier de mission','Votre projet mérite une vraie préparation.','Organisation, repérage et suivi : entrez dans l’univers des missions de protection rapprochée.','Préparation · Repérage · Suivi','dossier','']
 ],
 DIRIGEANT:[
  ['pilotage','Le pilotage d’entreprise','Prenez la direction de votre projet.','Organisation, équipe et clients : découvrez les dimensions de la direction d’une entreprise de sécurité privée.','Direction · Organisation · Décisions','console','pulse'],
  ['planning','Le planning des équipes','Donnez du rythme à l’organisation.','Équipes, sites et planning : projetez-vous dans le quotidien d’un dirigeant en sécurité privée.','Planning · Équipes · Sites','dossier',''],
  ['management','Le management','Faire avancer l’équipe commence par se former.','Communication, répartition des rôles et organisation : préparez votre posture de dirigeant.','Management · Rôles · Communication','duo',''],
  ['contrat','La proposition commerciale','Transformez un besoin en projet de prestation.','Échanges clients, préparation des propositions et suivi : explorez la dimension commerciale du métier.','Client · Proposition · Prestation','showcase',''],
  ['gestion','La gestion de l’activité','Donnez de la visibilité à votre activité.','Budget, suivi et organisation : construisez votre projet avec une vision de la gestion d’entreprise.','Gestion · Budget · Suivi','poster','pulse'],
  ['client','La relation avec les clients','Une relation solide se construit dans la durée.','Écoute, préparation des prestations et suivi : donnez du sens à votre futur rôle de dirigeant.','Relation client · Écoute · Suivi','editorial',''],
  ['qualite','Le suivi de la qualité','La qualité se prépare et se suit.','Observations, échanges et amélioration : explorez le pilotage de la qualité des prestations.','Qualité · Observation · Amélioration','orbit','pulse'],
  ['cadre','Le cadre professionnel','Diriger, c’est aussi savoir s’organiser.','Dossiers, responsabilités et cadre professionnel : préparez les fondations de votre projet DESP.','Dossiers · Organisation · Responsabilités','architect',''],
  ['prestation','L’organisation d’une prestation','Du besoin client à l’organisation du terrain.','Sites, équipes et coordination : découvrez la préparation d’une prestation de sécurité privée.','Site · Équipe · Coordination','cinema','float'],
  ['strategie','Le développement de l’entreprise','Construisez la prochaine étape de votre entreprise.','Objectifs, organisation et développement : donnez une direction à votre projet dans la sécurité privée.','Objectifs · Développement · Direction','path','float']
 ]
};
for(const [formation,rows] of Object.entries(EXTRA_METIER_DEFINITIONS))definitions[formation].push(...rows);
export const METIER_DESIGNS=Object.entries(definitions).flatMap(([formation,rows])=>rows.map(([slug,name,title,introduction,subjects,layout,motion],index)=>({
 id:`metier_${formation.toLowerCase()}_${slug}`,formation,code:courses[formation][0],courseName:courses[formation][1],slug,name,title,introduction,subjects:subjects.split(' · '),layout,motion,index:index+1,
 contentDefaults:{title,introduction,cta:`Découvrir la formation ${courses[formation][0]}`}
})));
const esc=value=>String(value??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const A='var(--n2-accent)',S='var(--n2-soft)',I='var(--n2-ink)',L='var(--n2-line)',P='var(--n2-paper-alt)',W='#fff';
const rect=(x,y,w,h,fill=W,r=18,extra='')=>`<rect x="${x}" y="${y}" width="${w}" height="${h}" rx="${r}" fill="${fill}" ${extra}/>`;
const circle=(x,y,r,fill=A,extra='')=>`<circle cx="${x}" cy="${y}" r="${r}" fill="${fill}" ${extra}/>`;
const path=(d,stroke=I,width=5,fill='none',extra='')=>`<path d="${d}" stroke="${stroke}" stroke-width="${width}" fill="${fill}" stroke-linecap="round" stroke-linejoin="round" ${extra}/>`;
const text=(x,y,t,size=18,fill=I,extra='')=>size<28&&String(t).length>4?rect(x,y-size*.4,Math.min(120,String(t).length*size*.4),6,fill,3):`<text x="${x}" y="${y}" fill="${fill}" font-family="Arial,sans-serif" font-size="${Math.max(36,size)}" font-weight="700" ${extra}>${esc(t)}</text>`;
const group=(x,y,s,body)=>`<g transform="translate(${x} ${y}) scale(${s})">${body}</g>`;
const check=(x,y,s=1)=>group(x,y,s,circle(0,0,20,A)+path('M-9 0-2 7 10-8',W,4));
const person=(x,y,s=1,coat=A)=>group(x,y,s,circle(0,-61,23,I)+path('M-13-70Q0-82 14-69',W,2)+rect(-33,-31,66,88,coat,24)+path('M-18 55-23 118M18 55 25 118',I,17)+path('M-27-12-49 42M27-12 46 35',coat,14)+path('M-13-28 0-13 12-28',W,4));
const monitor=(x,y,w=230,h=150,body='')=>rect(x,y,w,h,I,16)+rect(x+10,y+10,w-20,h-26,W,9)+body+path(`M${x+w/2} ${y+h}v30m-38 0h76`,I,10);
const clipboard=(x,y,s=1,heading='SUIVI',body='')=>group(x,y,s,rect(0,0,235,302,L,18)+rect(9,8,217,280,W,12)+rect(72,-12,92,30,A,10)+text(27,63,heading,20)+path('M27 84H205',L,2)+(body||[118,167,216].map(y=>check(36,y,.65)+path(`M68 ${y}H198M68 ${y+14}H156`,L,5)).join('')));
const building=(x,y,s=1)=>group(x,y,s,rect(0,0,280,245,W,8)+rect(0,0,280,22,A,5)+[48,106].map(y=>[26,98,170].map(x=>rect(x,y,49,35,S,5)).join('')).join('')+rect(112,177,57,68,I,4)+path('M0 246H280',L,5));
const car=(x,y,s=1)=>group(x,y,s,path('M8 92 52 76 104 13Q113 3 143 3H276Q291 3 306 21L350 75 388 91Q404 96 404 117V143H0V112Q0 97 8 92',A,3,A)+path('M85 75 120 24H199V75ZM216 24H277L322 75Z',W,2,W)+path('M17 98H55M355 99H388',W,8)+path('M195 92H214',I,4)+circle(78,145,35,I)+circle(78,145,17,W)+circle(321,145,35,I)+circle(321,145,17,W)+path('M5 165H400',L,3));
const pin=(x,y,s=1)=>group(x,y,s,path('M0 47C-12 28-29 9-29-8a29 29 0 0 1 58 0C29 9 12 28 0 47Z',A,2,A)+circle(0,-9,11,W));
const route=(variant=0)=>rect(52,49,536,360,W,24)+path('M52 159H588M52 282H588M205 49V409M441 49V409',P,28)+path(variant?'M127 331V210H334V108H495':'M118 115H311V338H504',A,10,'none','stroke-dasharray="12 13"')+pin(variant?127:118,variant?313:97,.8)+pin(variant?495:504,variant?90:320,1)+rect(75,366,118,27,S,8)+text(91,386,'ITINÉRAIRE',12);
const radio=(x,y,s=1)=>group(x,y,s,path('M26 0V-77',I,15)+rect(0,0,129,236,I,20)+rect(13,29,103,78,S,10)+text(30,75,'RADIO',18)+[133,153,173].map(y=>path(`M25 ${y}H102`,W,5)).join('')+circle(40,207,9,A)+circle(88,207,9,A)+path('M156 40Q195 75 157 108M179 11Q246 73 179 136',A,9));
const bag=(x,y,s=1,open=false)=>group(x,y,s,rect(0,0,182,228,A,20)+rect(55,-36,72,39,'none',10,`stroke="${I}" stroke-width="9"`)+path('M28 32V193M154 32V193',W,4)+circle(34,233,10,I)+circle(149,233,10,I)+(open?rect(19,27,142,166,W,8)+rect(33,41,112,58,S,6)+rect(35,113,42,64,I,4)+rect(89,113,53,63,P,4):path('M49 92H135M49 135H135',W,6)));
const phone=(x,y,s=1,body='')=>group(x,y,s,rect(0,0,192,324,I,30)+rect(9,10,174,303,W,24)+rect(64,12,64,15,I,6)+body+path('M67 298H127',I,5));
const desk=(body='')=>path('M80 355H559M120 357V435M520 357V435',I,12)+body;
const handshake=(x,y,s=1)=>group(x,y,s,path('M0 54 80 10 141 62 108 132 28 90Z',A,2,A)+path('M250 54 174 11 115 66 145 132 222 90Z',S,2,S)+path('M76 59 106 40 145 48 178 78 149 116Q143 125 134 118L91 91',I,5,W)+path('M114 62 139 80M104 77 130 96M95 91 120 110',I,4));
const calendar=(x,y,s=1)=>group(x,y,s,rect(0,0,340,264,W,18)+rect(0,0,340,48,A,14)+[50,283].map(x=>path(`M${x} -12V16`,I,9)).join('')+[75,125,175,225].map((y,i)=>[28,91,154,217,280].map((x,j)=>rect(x,y,37,24,(i+j)%3===0?A:S,5)).join('')).join(''));
const scenes={
 'SSIAP/ssi':()=>rect(75,72,490,326,W,24)+rect(95,92,450,59,A,12)+text(121,131,'SYSTÈME DE SÉCURITÉ INCENDIE',21,W)+rect(112,176,245,161,P,12)+text(136,215,'SSI',34)+path('M136 240H325M136 264H290M136 289H312',L,9)+[193,253,313].map((y,i)=>circle(403,y,15,A)+text(431,y+6,['ZONE 01','ZONE 02','ZONE 03'][i],14)).join('')+rect(112,355,115,19,L,7)+circle(516,365,10,A),
 'SSIAP/ronde':()=>route(1)+group(377,212,.72,person(0,0,1,I))+text(299,384,'RONDE INCENDIE',17),
 'SSIAP/pc':()=>monitor(64,76,248,169,rect(83,94,101,95,S,4)+path('M198 109H286M198 136H263M198 163H278',A,7))+monitor(337,100,236,145,path('M360 167H552M419 119V211M503 119V211',L,4)+circle(460,156,22,A))+desk()+person(315,315,.67,A)+rect(262,327,109,91,I,19),
 'SSIAP/alerte':()=>rect(125,45,390,379,P,38)+rect(187,96,266,272,A,28)+rect(218,137,204,151,W,14)+path('M268 177 320 236 372 177M320 210v-60',A,11)+text(261,327,'ALERTE',27,W)+path('M82 176H51M110 112 84 87M543 173H575M524 110 552 87',A,8),
 'SSIAP/evacuation':()=>rect(320,69,199,327,W,6)+rect(344,111,151,284,S,3)+path('M410 111V394',I,4)+rect(316,45,207,51,A,8)+text(343,79,'ÉVACUATION',22,W)+person(195,280,.76)+path('M77 414H425M387 384l39 30-39 30',A,9)+person(93,233,.48,I),
 'SSIAP/extincteur':()=>rect(263,162,144,240,A,48)+rect(288,130,94,56,I,12)+path('M322 130V92H412M336 95l-52-13',I,12)+circle(379,136,23,W,`stroke="${I}" stroke-width="5"`)+path('M378 135l11-10',A,4)+path('M287 154Q202 171 217 337',I,16)+path('M217 335l-8 51',I,27)+rect(279,238,112,88,W,6)+text(296,276,'MOYENS',17)+text(300,301,'DE SECOURS',11)+path('M185 423H444',L,6),
 'SSIAP/detection':()=>path('M67 91H573',L,14)+rect(248,92,144,32,W,15)+path('M246 124Q320 217 394 124',A,4,S)+path('M277 139H364',I,5)+circle(322,166,7,A)+[250,305,360].map((y,i)=>path(`M${180-i*33} ${y}Q320 ${y-78} ${460+i*33} ${y}`,A,7)).join('')+text(236,413,'DÉTECTION',26),
 'SSIAP/transmission':()=>radio(136,137,1.05)+rect(354,86,210,116,W,22)+text(379,127,'PC SÉCURITÉ',20)+path('M380 154H528M380 174H482',L,7)+rect(352,258,213,96,S,20)+text(377,301,'TRANSMISSION',18)+path('M379 323H518',A,7),
 'SSIAP/main_courante':()=>clipboard(164,83,1.05,'MAIN COURANTE')+path('M453 327 521 129',I,19)+path('m449 341-4 31 20-21',A,5,A)+rect(74,342,112,48,A,12)+text(91,373,'SUIVI',19,W),
 'SSIAP/prevention':()=>building(247,91,1.12)+rect(72,194,125,192,S,5)+path('M133 200V383M86 275H183',I,5)+check(208,110,1.2)+path('M120 414H566',L,6)+text(70,102,'PRÉVENTION',20),
 'APS/ronde':()=>building(283,111,.95)+person(164,267,1.1)+path('M64 421H537',A,7,'none','stroke-dasharray="13 16"')+pin(551,382,.65),
 'APS/bagages':()=>bag(110,122,1.12,true)+path('M87 400H540',I,9)+circle(458,191,66,'none',`stroke="${A}" stroke-width="14"`)+path('M502 239l55 63',A,18)+rect(410,164,94,53,S,5)+path('M425 190H487',I,5),
 'APS/acces':()=>rect(305,85,71,309,I,12)+rect(313,112,55,68,W,6)+circle(341,146,14,A)+rect(392,85,71,309,I,12)+path('M375 249H467M377 249l-55 96M377 249l49-84',A,10)+person(163,256,.98)+group(506,135,.78,rect(0,0,94,132,W,12)+circle(47,38,17,A)+path('M24 74H70M24 97H63',L,6)),
 'APS/video':()=>monitor(77,62,486,294,[0,1].map(i=>[0,1].map(j=>rect(96+j*227,82+i*118,210,103,(i+j)%2?S:P,5)+path(`M${111+j*227} ${165+i*118}l50-58 36 33 39-12 58 37`,A,4)).join('')).join(''))+text(212,437,'SURVEILLANCE VIDÉO',20),
 'APS/perimetre':()=>building(193,85,.92)+[91,174,257,340,423,506].map(x=>path(`M${x} 235V412M${x} 238l83 166M${x} 402l83-162`,L,4)).join('')+path('M77 245H566M77 400H566',A,8)+pin(98,202,.8),
 'APS/evenement':()=>rect(195,86,372,114,W,12)+text(250,154,'ÉVÉNEMENT',32)+[99,241,383,525].map(x=>path(`M${x} 285V402`,I,8)+circle(x,280,12,A)).join('')+path('M99 296Q169 353 241 296M241 296Q313 353 383 296M383 296Q454 353 525 296',A,8)+person(139,181,.65)+person(332,210,.6,I)+person(465,210,.6,A),
 'APS/radio':()=>radio(277,130,1.18)+person(114,269,.88)+rect(98,75,160,58,W,14)+text(117,112,'COORDINATION',15),
 'APS/rapport':()=>clipboard(244,82,1.07,'COMPTE RENDU')+rect(62,260,201,131,A,18)+text(88,311,'OBSERVER',20,W)+path('M89 340H231M89 358H199',W,6),
 'APS/vigilance':()=>circle(365,220,155,S)+path('M121 227 551 89 550 381Z',A,0,P)+group(66,197,1,rect(0,0,124,57,I,16)+rect(111,-14,58,85,A,12)+path('M25 18H90',W,6))+building(334,153,.62)+path('M77 410H563',L,6),
 'APS/commerce':()=>rect(224,84,342,289,W,8)+rect(211,79,368,46,A,6)+[240,340,440].map(x=>rect(x,176,88,85,S,6)+rect(x+15,196,57,48,W,3)).join('')+rect(350,282,62,91,I,4)+person(125,271,1.04)+text(285,157,'ACCUEIL',21),
 'VTC/ville':()=>[80,170,261,360,470].map((x,i)=>rect(x,80+i%3*25,63,196-i%3*25,S,5)).join('')+car(71,224,1.23)+text(92,83,'VOTRE PROCHAINE DIRECTION',18),
 'VTC/aeroport':()=>rect(315,71,231,82,W,14)+text(348,125,'ARRIVÉES',27)+path('M366 192h121m-28-23 29 23-29 23',A,7)+person(170,260,1.12)+rect(87,238,182,65,W,9)+text(111,279,'BIENVENUE',21)+bag(374,265,.52),
 'VTC/reservation':()=>phone(223,58,1.1,text(26,73,'VOTRE COURSE',17)+rect(24,94,144,70,P,10)+pin(52,120,.4)+path('M78 116H145M78 134H128',L,5)+rect(24,182,144,51,A,9)+text(43,214,'RÉSERVATION',13,W))+circle(118,163,37,S)+check(505,325,1.55),
 'VTC/itineraire':()=>route()+car(246,180,.48),
 'VTC/bagages':()=>car(58,173,1.12)+bag(419,248,.68)+person(151,182,.59,I)+path('M469 135V88m-25 22 25-24 25 24',A,7),
 'VTC/conduite':()=>circle(320,243,159,I)+circle(320,243,130,P)+circle(320,243,50,A)+path('M180 210 277 233M361 234 462 210M320 293V378',I,25)+rect(237,38,166,51,W,15)+text(279,70,'VTC',23),
 'VTC/confort':()=>rect(61,70,518,331,W,30)+rect(126,131,128,200,S,40)+rect(386,131,128,200,S,40)+rect(140,102,98,64,A,24)+rect(400,102,98,64,A,24)+rect(270,257,101,104,I,18)+rect(289,205,20,84,A,7)+rect(331,229,20,60,A,7)+path('M80 363H558',L,7),
 'VTC/vehicule':()=>car(70,195,1.06)+clipboard(416,64,.61,'VÉHICULE')+path('M137 124v-38M119 105h38M82 169v-26M69 156h26',A,7),
 'VTC/client':()=>handshake(154,113,1.35)+car(196,328,.65)+rect(120,48,215,44,W,12)+text(147,78,'SENS DU SERVICE',18),
 'VTC/activite':()=>calendar(83,71,1.06)+phone(432,171,.61,rect(24,67,144,48,A,8)+text(47,97,'PLANNING',16,W)+path('M27 153H160M27 186H145M27 219H156',L,8))+car(126,348,.52),
 'A3P/accompagnement':()=>path('M63 401H572',L,7)+person(314,230,1.25,I)+person(132,263,1.07,A)+person(494,264,1.07,A)+path('M101 98H181M141 58v80M462 111h61',A,5),
 'A3P/briefing':()=>rect(139,57,376,218,W,16)+path('M174 107H331V221H477',A,7,'none','stroke-dasharray="10 11"')+pin(470,183,.6)+rect(354,87,131,51,S,8)+text(374,120,'MISSION',19)+desk()+person(153,309,.6)+person(326,309,.6,I)+person(500,309,.6),
 'A3P/itineraire':()=>route(1)+rect(356,330,192,51,A,12)+text(382,363,'DÉPLACEMENT',18,W),
 'A3P/observation':()=>circle(320,237,180,S)+building(202,132,.87)+path('M128 163V94H204M438 94H512V163M128 311V381H204M438 381H512V311',A,10)+circle(320,238,56,'none',`stroke="${I}" stroke-width="4"`)+path('M320 218V258M300 238H340',I,4),
 'A3P/arrivee':()=>building(249,57,1.08)+rect(262,101,275,39,A,4)+text(366,128,'ACCUEIL',18,W)+car(87,315,.91)+person(137,241,.58,I),
 'A3P/mobilite':()=>rect(242,74,325,215,W,25)+rect(265,112,94,85,S,13)+rect(378,112,163,85,S,13)+path('M246 250H564',A,11)+[280,502].map(x=>circle(x,300,24,I)).join('')+person(126,262,.94)+bag(204,320,.35)+text(322,233,'MOBILITÉ',18),
 'A3P/evenement':()=>rect(147,74,361,130,S,25)+text(209,151,'ÉVÉNEMENT',28)+rect(246,256,147,110,W,7)+person(321,221,.59,I)+person(114,297,.75,A)+person(519,297,.75,A)+path('M169 399H465',A,8),
 'A3P/communication':()=>person(180,263,1.25,I)+path('M203 179q47 8 26 60l-34 20',A,8)+circle(209,194,9,W)+radio(390,187,.8)+path('M304 141q66 31 24 94M329 108q104 57 36 156',A,8),
 'A3P/equipe':()=>circle(321,227,155,S)+path('M191 328 322 119 465 328Z',A,5,'none','stroke-dasharray="10 12"')+person(320,137,.63,I)+person(162,304,.8)+person(476,304,.8)+rect(240,337,165,59,W,14)+text(264,375,'MISSION',25),
 'A3P/mission':()=>clipboard(238,81,1.04,'MISSION')+rect(61,187,195,145,A,16)+path('M86 221H162V297H227',W,6,'none','stroke-dasharray="8 8"')+pin(219,251,.45)+text(86,160,'PRÉPARATION',18),
 'DIRIGEANT/pilotage':()=>monitor(76,65,338,234,rect(96,88,133,155,S,6)+[97,135,173].map((y,i)=>rect(246,y,65+i*20,17,A,4)).join('')+path('M252 243l33-32 32 11 65-50',A,7))+desk()+clipboard(435,202,.61,'PILOTAGE'),
 'DIRIGEANT/planning':()=>calendar(79,89,1.19)+rect(435,231,147,161,A,18)+[262,308,354].map(y=>circle(464,y,12,W)+path(`M490 ${y}H556`,W,6)).join(''),
 'DIRIGEANT/management':()=>person(319,145,.69,I)+path('M319 229V275H148V309M319 275H487V309M319 275V310',A,7)+[149,318,487].map((x,i)=>person(x,345,.56,i===1?I:A)).join('')+text(71,79,'FAIRE ÉQUIPE',24),
 'DIRIGEANT/contrat':()=>clipboard(161,84,1.07,'PROPOSITION',path('M30 112H195M30 140H174M30 168H193',L,8)+path('M33 225q35-80 42-9t38-10 39 15',A,5))+path('M452 350 531 107',I,20)+path('m445 365-4 24 18-19',A,5,A),
 'DIRIGEANT/gestion':()=>rect(99,111,435,282,W,23)+text(134,160,'SUIVI DE L’ACTIVITÉ',24)+[70,113,161,127].map((h,i)=>rect(137+i*83,354-h,45,h,i%2?S:A,6)).join('')+path('M136 355H484',I,4)+circle(492,95,50,A)+text(475,109,'€',42,W),
 'DIRIGEANT/client':()=>handshake(145,153,1.45)+rect(79,53,235,71,W,18)+text(105,99,'VOTRE CLIENT',22)+rect(354,345,212,56,S,16)+text(380,381,'VOTRE ÉQUIPE',20),
 'DIRIGEANT/qualite':()=>clipboard(113,86,1.04,'QUALITÉ')+circle(450,275,80,A)+path('M411 275l26 30 51-65',W,13)+path('M442 163V130M507 183l29-27M545 249h36',A,7),
 'DIRIGEANT/cadre':()=>[0,1,2].map(i=>rect(107+i*112,108-i*10,99,293-i*2,i===1?A:W,12)+circle(157+i*112,333-i*10,20,i===1?W:S)+path(`M${133+i*112} ${168-i*10}h46M${133+i*112} ${187-i*10}h46`,i===1?W:L,5)).join('')+rect(446,215,109,182,S,12)+text(86,66,'CADRE PROFESSIONNEL',23),
 'DIRIGEANT/prestation':()=>building(292,78,.97)+[133,243,353].map((x,i)=>person(x,325,.61,i===1?I:A)).join('')+path('M107 158H209V246H277',A,8,'none','stroke-dasharray="10 12"')+pin(114,114,.65)+rect(452,358,98,45,A,8)+text(473,386,'SITE',18,W),
 'DIRIGEANT/strategie':()=>path('M90 372H241V256H399V145H547',A,13)+[90,241,399,547].map((x,i)=>circle(x,[372,256,145,145][i],22,W,`stroke="${A}" stroke-width="7"`)).join('')+path('M481 232V51l90 34-90 34',I,7,S)+rect(83,60,241,72,W,18)+text(110,106,'DÉVELOPPEMENT',22)
};

Object.assign(scenes,createExtraMetierScenes({rect,circle,path,group,person,monitor,clipboard,building,car,pin,route,radio,bag,phone,desk,handshake,calendar,A,S,I,L,P,W}));

export function renderMetierIllustration(design){
 const scene=scenes[`${design.formation}/${design.slug}`];
 if(!scene)throw new Error('Illustration métier inconnue : '+design.id);
 return `<svg viewBox="0 0 640 480" xmlns="http://www.w3.org/2000/svg" aria-hidden="true">${scene()}</svg>`;
}
export function renderMetierTemplateBody(ctx){
 const d=METIER_DESIGNS.find(d=>d.id===ctx.template.id);
 if(!d)throw new Error('Composition métier inconnue : '+ctx.template.id);
 const c=ctx.slide.content||{};
 const field=(key,tag,fit)=>`<${tag} class="metier-${key}${key==='cta'?' n2-cta':''}" data-content-key="${key}" data-fit="${fit}" data-element-name="${key}">${esc(c[key]||d.contentDefaults[key])}</${tag}>`;
 const label=`<div class="metier-kicker"><span class="metier-code" data-fit="meta">FORMATION ${d.code}</span></div>`;
 const title=field('title','h1','title'),intro=field('introduction','p','body');
 const action=`<div class="n2-action">${field('cta','span','cta')}<b aria-hidden="true">↗</b></div>`;
 const tags=`<ul class="metier-subjects">${d.subjects.map(s=>`<li data-fit="meta">${esc(s)}</li>`).join('')}</ul>`;
 const visual=`<figure class="metier-visual" aria-label="${esc(d.name)}"><div class="metier-art" data-studio-decorative="true"${d.motion?` data-motion="${d.motion}"`:''}>${renderMetierIllustration(d)}</div><figcaption data-fit="meta" data-motion-foreground>${esc(d.name)}</figcaption></figure>`;
 const copy=`<section class="metier-copy">${label}${title}${intro}${action}</section>`;
 let body;
 if(['cinema','poster','feature'].includes(d.layout))body=`<header class="metier-head">${label}${title}</header>${visual}<section class="metier-bottom">${intro}${action}</section>${tags}`;
 else if(['dossier','folio'].includes(d.layout))body=`${label}<header class="metier-head">${title}</header>${visual}<section class="metier-copy">${intro}${tags}${action}</section>`;
 else body=`${copy}${visual}${tags}`;
 return `<main class="n2 metier-main metier-${d.layout}" data-layout-role="metier-${d.layout}" data-metier-formation="${d.formation}">${body}</main>`;
}
