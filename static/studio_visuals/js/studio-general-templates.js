// Institution-wide stories use the same spacious compositions as the métier
// collection. Each illustration is distinct; colors come from the OR theme.
const definitions=[
 ['declic','Le déclic','Votre avenir mérite un déclic.','Une envie de changement ? Explorez les formations Intégrale Academy et donnez une direction à votre projet.','Envie · Projet · Formation','poster','pulse','Découvrir nos formations'],
 ['cap','Le nouveau cap','Changez de cap. Gardez votre ambition.','Faites le point sur vos envies et préparez votre prochaine étape professionnelle avec notre équipe.','Orientation · Ambition · Avenir','path','float','Parlons de votre projet'],
 ['avenir','L’horizon professionnel','Voyez plus loin pour votre avenir.','Un métier à découvrir, des compétences à construire : ouvrez de nouvelles perspectives avec Intégrale Academy.','Perspectives · Compétences · Métier','cinema','float','Explorer les possibilités'],
 ['reconversion','La reconversion','Une nouvelle voie s’ouvre à vous.','Votre expérience compte. Appuyez-vous sur elle pour imaginer un nouveau projet de formation.','Expérience · Évolution · Projet','editorial','','Préparer ma reconversion'],
 ['potentiel','Le potentiel','Donnez de la place à votre potentiel.','Cultivez votre envie d’apprendre et découvrez les parcours qui peuvent faire avancer votre projet.','Potentiel · Apprentissage · Élan','orbit','pulse','Trouver ma formation'],
 ['objectif','L’objectif','Un objectif en tête. Un projet à construire.','Transformez votre envie de progresser en un projet de formation concret, avec des repères pour avancer.','Objectif · Préparation · Progression','focus','pulse','Construire mon projet'],
 ['parcours','Le parcours de formation','Votre parcours commence à prendre forme.','Du choix de la formation à la préparation de votre entrée, échangeons sur les étapes de votre projet.','Choix · Préparation · Parcours','console','pulse','Préparer mon parcours'],
 ['accompagnement','L’accompagnement','Une équipe à vos côtés pour avancer.','Vos questions, vos envies, votre projet : prenons le temps de préparer ensemble votre parcours de formation.','Écoute · Échanges · Accompagnement','duo','','Rencontrer notre équipe'],
 ['choix','Le choix de la formation','Trouvez le parcours qui vous correspond.','Découvrez nos univers de formation et échangez avec notre équipe pour préciser votre orientation.','Découverte · Orientation · Choix','showcase','','Découvrir les parcours'],
 ['rencontre','Le premier échange','Votre projet mérite une conversation.','Une question sur une formation ? Faites connaissance avec notre équipe et parlons de votre prochaine étape.','Questions · Écoute · Rencontre','window','','Parlons de votre projet'],
 ['competences','La construction des compétences','Construisez des compétences qui comptent.','Apprendre, s’exercer, progresser : donnez une place à la formation dans votre avenir professionnel.','Apprendre · Pratiquer · Progresser','architect','','Explorer nos formations'],
 ['pratique','L’apprentissage par la pratique','Donnez du concret à vos ambitions.','Découvrez des formations tournées vers les métiers et la préparation de votre futur quotidien professionnel.','Pratique · Métier · Préparation','feature','float','Découvrir notre approche'],
 ['collectif','L’énergie du collectif','L’envie d’apprendre se partage.','Rencontres, échanges et apprentissage : imaginez votre place dans un nouvel environnement de formation.','Rencontres · Échanges · Collectif','cinema','float','Rejoindre un parcours'],
 ['progression','La progression','Chaque apprentissage vous fait avancer.','Construisez votre projet avec une idée simple : faire de votre envie d’apprendre une force pour la suite.','Apprentissage · Effort · Progression','slope','float','Faire avancer mon projet'],
 ['confiance','La confiance','Préparez la suite avec confiance.','Clarifiez votre projet, découvrez votre parcours et échangez avec notre équipe avant de vous lancer.','Repères · Préparation · Confiance','folio','','Préparer la prochaine étape'],
 ['inscription','Le projet d’inscription','Votre envie devient un projet.','Vous avez une formation en tête ? Contactez notre équipe pour préparer votre demande d’inscription.','Formation · Dossier · Inscription','dossier','','Préparer mon inscription'],
 ['agenda','Les prochaines sessions','Faites une place à votre avenir.','Consultez les prochaines sessions et préparez votre organisation pour votre projet de formation.','Sessions · Dates · Organisation','console','pulse','Voir les prochaines sessions'],
 ['accueil','L’accueil au centre','Un lieu pour apprendre et avancer.','Découvrez Intégrale Academy à Puget-sur-Argens et échangez avec notre équipe sur votre projet professionnel.','Centre · Équipe · Formation','architect','','Découvrir Intégrale Academy'],
 ['questions','Les réponses à vos questions','Vos questions font avancer votre projet.','Parcours, organisation, inscription : notre équipe vous aide à y voir plus clair avant de choisir votre formation.','Questions · Informations · Choix','duo','','Échanger avec notre équipe'],
 ['preparation','La préparation du départ','Préparez votre nouveau départ.','Faites le point sur les étapes de votre projet et les informations utiles pour préparer votre entrée en formation.','Préparation · Organisation · Départ','dossier','','Organiser mon parcours'],
 ['livre','Le prochain chapitre','Écrivez un nouveau chapitre professionnel.','Une envie d’évolution ou de changement ? Ouvrez le champ des possibles avec les formations Intégrale Academy.','Évolution · Apprentissage · Avenir','editorial','','Ouvrir de nouvelles pistes'],
 ['passerelle','La passerelle vers demain','Reliez vos envies à un nouveau métier.','Découvrez nos formations et commencez à dessiner un parcours entre votre expérience et votre projet.','Expérience · Formation · Métier','path','float','Dessiner mon parcours'],
 ['elan','L’élan professionnel','Donnez de l’élan à votre projet.','Votre motivation est un point de départ. Échangeons sur la formation qui peut accompagner votre prochaine étape.','Motivation · Formation · Évolution','poster','pulse','Lancer mon projet'],
 ['univers','Les univers de formation','Plusieurs univers. Votre prochaine voie.','Sécurité privée, incendie, protection, direction ou VTC : découvrez les parcours proposés par Intégrale Academy.','Découverte · Parcours · Orientation','orbit','pulse','Explorer nos univers'],
 ['savoir','Le savoir en mouvement','L’apprentissage ouvre de nouvelles portes.','Donnez du temps à votre curiosité et découvrez les compétences à travailler dans votre futur parcours.','Curiosité · Savoir · Compétences','showcase','','Choisir d’apprendre'],
 ['projet','Le projet qui se dessine','Faites grandir votre idée de départ.','Une envie, une question, une ambition : rassemblez vos idées et construisez votre projet avec notre équipe.','Idées · Échanges · Construction','folio','','Donner forme à mon projet'],
 ['immersion','La découverte des métiers','Projetez-vous dans un nouveau quotidien.','Découvrez les univers métiers de nos formations et imaginez la prochaine étape de votre vie professionnelle.','Découverte · Métier · Projection','window','float','Découvrir les métiers'],
 ['trajectoire','La trajectoire','Votre prochaine étape se prépare ici.','Prenez le temps de choisir votre direction et de préparer un parcours de formation cohérent avec votre projet.','Direction · Parcours · Avenir','slope','float','Préparer ma prochaine étape'],
 ['ambition','L’ambition en action','Passez de l’envie à l’action.','Découvrez nos parcours, posez vos questions et commencez à construire votre projet de formation.','Envie · Échange · Action','focus','pulse','Démarrer mon projet'],
 ['ensemble','L’aventure Intégrale Academy','Votre avenir nous donne rendez-vous.','Faisons connaissance et préparons ensemble votre projet de formation avec Intégrale Academy.','Rencontre · Formation · Avenir','feature','float','Parlons de votre avenir']
];

export const GENERAL_DESIGNS=definitions.map(([slug,name,title,introduction,subjects,layout,motion,cta],index)=>({
 id:`general_${slug}`,formation:'OR',code:'GÉNÉRAL',kicker:'VOTRE PROJET',courseName:'Intégrale Academy',slug,name,title,introduction,subjects:subjects.split(' · '),layout,motion,index:index+1,
 contentDefaults:{title,introduction,cta}
}));

export function createGeneralScenes(h){
 const {rect:r,circle:c,path:p,group:g,person:human,monitor,clipboard:doc,building:house,car,phone,calendar,A,S,I,L,P,W}=h;
 const floor=()=>p('M65 424H575',L,6);
 const star=(x,y,s=1)=>g(x,y,s,p('M0-34 10-10 34 0 10 10 0 34-10 10-34 0-10-10Z',A,2,A));
 const arrow=(x,y,s=1)=>g(x,y,s,p('M-45 45 45-45M-8-45H45V8',A,13));
 const book=(x,y,s=1)=>g(x,y,s,p('M0 0Q70-27 140 7Q210-27 280 0V169Q210 146 140 178Q70 146 0 169Z',I,5,W)+p('M140 7V177',A,7)+p('M28 40Q65 29 108 44M28 72Q65 61 108 77M28 105Q65 94 108 110M172 45Q216 28 252 41M172 78Q216 61 252 74M172 111Q216 94 252 107',L,6));
 const cap=(x,y,s=1)=>g(x,y,s,p('M-104 0 0-48 104 0 0 47Z',A,4,A)+p('M-62 22V70Q0 105 62 70V22',I,5,W)+p('M94 5V73',A,6)+c(94,78,8,A));
 const bulb=(x,y,s=1)=>g(x,y,s,p('M-32 65V42C-85-6-52-79 0-79S85-6 32 42V65Z',A,7,S)+p('M-31 78H31M-22 94H22M-10 45V5L-28-14M10 45V5L28-14',I,7)+[-1,1].map(a=>p(`M${a*87}-32h${a*24}M${a*63}-90l${a*17}-19`,A,7)).join('')+p('M0-119V-144',A,7));
 const bubble=(x,y,s=1,inverse=false)=>g(x,y,s,r(0,0,214,118,inverse?A:W,28)+p('M40 112v31l36-29',inverse?A:W,5,inverse?A:W)+p('M32 38H176M32 67H133',inverse?W:A,8));
 const target=(x,y,s=1)=>g(x,y,s,c(0,0,106,W,`stroke="${L}" stroke-width="8"`)+c(0,0,71,S)+c(0,0,34,A)+p('M0 0 86-87',I,9)+p('M61-87h26v27',I,8));
 const steps=(x,y,s=1)=>g(x,y,s,r(0,170,102,85,S,8)+r(111,102,102,153,A,8)+r(222,28,102,227,W,8)+p('M0 256H326',I,5));
 const doorway=(x,y,s=1)=>g(x,y,s,r(0,0,180,292,I,90)+r(12,12,156,280,S,78)+p('M48 280V67L152 30V285Z',A,3,A)+c(127,163,7,W));
 const loop=(x,y,s=1)=>g(x,y,s,p('M-125 0C-180-113-36-111 0 0S180 113 125 0S36-111 0 0S-180 113-125 0',A,21));
 const scene={
  declic:()=>c(317,232,176,P)+bulb(319,242,1.45)+star(108,143,.8)+star(522,354,.7)+floor(),
  cap:()=>c(320,236,176,W,`stroke="${L}" stroke-width="4"`)+c(320,236,137,S)+p('M270 289 343 150 375 189Z',A,5,A)+p('M343 150 375 189 270 289Z',I,4,W)+p('M320 77V100M320 372V395M161 236H184M457 236H480',A,8)+star(511,109,.7),
  avenir:()=>r(53,64,534,353,W,28)+c(447,176,69,S)+p('M79 345Q200 278 307 319T565 327',L,7)+p('M82 384 287 276 387 308 556 235',A,8)+p('M505 235H556V286',A,8)+human(171,240,.83,I)+floor(),
  reconversion:()=>p('M86 370H260Q332 370 332 293V167Q332 99 403 99H548',A,18)+p('M505 57 548 99 505 141',A,12)+p('M83 109H198Q249 109 249 165V221',L,11,'none','stroke-dasharray="12 16"')+human(181,261,.84)+star(455,281,1.1)+floor(),
  potentiel:()=>r(162,309,316,101,A,22)+p('M320 310V157',I,10)+p('M318 255Q209 273 183 163Q295 138 318 255Z',A,5,S)+p('M321 208Q442 211 465 103Q347 86 321 208Z',A,5,W)+p('M198 178 308 250M339 192 448 119',A,5)+star(136,112,.7)+star(519,296,.55)+floor(),
  objectif:()=>target(348,225,1.32)+human(149,310,.72)+r(462,347,108,38,S,12)+star(131,101,.7)+floor(),
  parcours:()=>monitor(82,76,476,285,r(111,105,418,53,S,12)+p('M147 291H260V207H383V263H498',A,9)+[147,260,383,498].map((x,i)=>c(x,[291,207,263,263][i],17,W,`stroke="${A}" stroke-width="6"`)).join(''))+cap(188,132,.45)+star(497,135,.45)+floor(),
  accompagnement:()=>bubble(85,61,1.2)+human(190,295,.94)+human(455,295,.94,I)+p('M251 338Q320 364 394 338',A,9)+c(470,110,37,S)+star(470,110,.65)+floor(),
  choix:()=>[-1,0,1].map((a,i)=>g(96+i*161,127+Math.abs(a)*40,1,r(0,0,141,231,i===1?A:W,22)+c(70,70,36,i===1?W:S)+p('M31 143H110M31 171H86',i===1?W:L,8)+(i===1?p('M51 70 66 85 92 56',A,7):p('M52 70H90',A,7)))).join('')+star(324, 70,.8)+floor(),
  rencontre:()=>r(76,94,489,272,P,30)+bubble(95,106,.91)+bubble(316,228,.91,true)+human(152,349,.45)+human(488,120,.45,I)+floor(),
  competences:()=>steps(110,156,1.22)+cap(448,113,.73)+p('M115 232 244 147 343 175',A,7)+star(105,100,.75)+floor(),
  pratique:()=>monitor(182,117,294,196,r(204,140,249,145,P,9)+p('M232 235 273 266 325 192 361 220 421 164',A,9))+human(107,281,.88)+book(368,338,.54)+floor(),
  collectif:()=>c(320,234,173,P)+[151,319,488].map((x,i)=>human(x,264,i===1?1.12:.86,i===1?I:A)).join('')+p('M191 143Q320 53 449 143',L,8)+star(320,92,.9)+floor(),
  progression:()=>steps(102,146,1.27)+human(447,116,.75,I)+p('M95 201 207 117 290 139',A,8)+star(372,98,.65)+floor(),
  confiance:()=>r(128,92,371,303,W,28)+c(315,223,93,S)+p('M267 221 306 260 371 184',A,18)+p('M183 365H444',L,8)+star(526,114,.7)+star(112,329,.55)+floor(),
  inscription:()=>doc(116,89,1.04)+phone(398,132,.78,r(22,56,147,70,S,12)+c(94,184,40,A)+p('M74 184 90 199 116 167',W,8))+star(481, 90,.65)+floor(),
  agenda:()=>calendar(90,111,1.1)+c(485,323,78,W,`stroke="${A}" stroke-width="8"`)+p('M485 275V323L520 344',I,9)+star(514,111,.8)+floor(),
  accueil:()=>house(183,121,1.17)+human(107,303,.8)+human(548,303,.8,I)+p('M92 132V92H137M518  70H559V112',A,7)+floor(),
  questions:()=>bubble(71, 80,1.13)+bubble(330,244,1.04,true)+c(490,132,54,S)+p('M471 117Q471  90 493 96Q522 100 507 123L490 138V147',I,8)+c(490,166,5,I)+human(166,328,.67)+floor(),
  preparation:()=>doc(142, 80,1.1)+r(424,245,122,144,A,15)+p('M451 245V219Q485 193 519 219V245',I,8)+p('M452 283H518M452 312H496',W,7)+star(482,147,.8)+floor(),
  livre:()=>r( 90,92,460,311,P,32)+book(132,191,1.35)+cap(318,118,.7)+star(113,145,.6)+star(534,311,.7)+floor(),
  passerelle:()=>p('M73 354H568',L,8)+p('M117 349Q320 55 523 349',A,18)+p('M168 292V352M247 194V352M392 194V352M472 292V352',L,8)+human(320,111,.72,I)+star(516,111,.75)+floor(),
  elan:()=>loop(320,249,1.13)+arrow(444,133,.68)+star(154,107,.8)+p('M179 389H460',L,6)+floor(),
  univers:()=>c(320,239,150,'none',`stroke="${L}" stroke-width="5" stroke-dasharray="8 14"`)+c(320,239,72,A)+cap(320,228,.49)+[[320,67],[488,191],[424,384],[216,384],[152,191]].map(([x,y],i)=>g(x,y,1,c(0,0,48,W)+[p('M-20 19V-20H20V19Z',A,5)+p('M-8-7H8M-8 5H8',A,5),bulb(0,3,.25),g(-29,-13,.15,car(0,0,1)),p('M-24 19H24M-16 19V-16H16V19M0-16V-27',A,5),book(-29,-15,.2)][i])).join(''),
  savoir:()=>doorway(143, 90,1.07)+book(331,252,.79)+star(475,131,1.1)+p('M458 215V189M516 200l17-15',A,7)+floor(),
  projet:()=>r( 80, 80,479,323,W,24)+r(109,108,171,118,S,16)+bulb(193,164,.48)+r(320,139,201, 50,A,12)+p('M320 217H499M320 250H460',L,8)+p('M143 320 212 290 274 336 355 292 464 334',A,7)+star(503,343,.55)+floor(),
  immersion:()=>r( 70, 50,500,369,I,32)+r(84,64,472,341,W,24)+p('M86 111H554',L,5)+[111,139,167].map(x=>c(x,87,6,A)).join('')+house(307,154,.76)+human(168,254,.83)+p('M261 299H322M301 278 322 299 301 320',A,9)+floor(),
  trajectoire:()=>p('M 90 367C 90 225 249 382 286 227S433 252 532 109',A,13)+p('M484 106 532 109 535 156',A,11)+[ 90,286,442].map((x,i)=>c(x,[367,227,221][i],21,W,`stroke="${A}" stroke-width="6"`)).join('')+cap(179,144,.69)+floor(),
  ambition:()=>c(320,232,168,P)+r(156,101,323,278,W,28)+arrow(320,237,1.37)+p('M199 336H436',L,8)+star(513,116,.7)+star(116,357,.7)+floor(),
  ensemble:()=>p('M126 218Q319-22 514 218',L,9)+[180,460].map((x,i)=>human(x,285,1,i?I:A)).join('')+c(320,252,65,A)+cap(320,243,.44)+star(320, 90,.8)+floor()
 };
 return Object.fromEntries(Object.entries(scene).map(([slug,draw])=>[`OR/${slug}`,draw]));
}
