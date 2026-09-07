// Each entry has its own composition. Color tokens come exclusively from the
// selected formation; motion is shared with the preview and video exporter.
const definitions=[
 ['prism','Le prisme de votre avenir','Prisme lumineux et affiche nocturne','split','orbit',true,false],
 ['sunrise','L’horizon s’ouvre','Soleil graphique et lignes d’horizon','stack','rise',false,false],
 ['monogram','Votre métier en grand','Monogramme découpé et bloc typographique','split','',false,false],
 ['archway','Passez à la suite','Arcades architecturales en perspective','split','',false,false],
 ['orbit_cards','Un projet, des possibilités','Cartes illustrées en constellation','split','float',true,true],
 ['ribbon_path','Dessinez votre parcours','Ruban continu et titre en marge','stack','float',false,false],
 ['paper_cut','Changez de perspective','Papier découpé en relief','split','',false,false],
 ['spotlight','C’est votre moment','Cercle de lumière et affiche de scène','poster','pulse',true,false],
 ['zigzag','L’élan qui change tout','Flèche pliée et typographie décalée','split','rise',false,false],
 ['wave_signal','Faites vibrer votre projet','Signal lumineux sur fond profond','stack','pulse',true,false],
 ['headline_press','La une de votre avenir','Une de magazine et cartouche de session','press','',false,false],
 ['column_cover','La prochaine édition','Couverture littéraire et tranche colorée','rail','',false,false],
 ['manifesto','Osez la suite','Manifeste typographique centré','poster','',false,false],
 ['underlined','Le déclic','Composition soulignée et flèche manuscrite','split','',false,false],
 ['index_tabs','Le bon chapitre','Intercalaires et fiche éditoriale','split','',false,false],
 ['editorial_seal','Un nouveau départ','Sceau graphique et affiche sérif','press','',false,false],
 ['cut_type','Place au changement','Grand lettrage et aplats découpés','split','',false,false],
 ['swiss_grid','Cap sur votre métier','Grille suisse et direction affirmée','press','',false,false],
 ['offset_blocks','Construisez la suite','Blocs asymétriques et surfaces superposées','blocks','',false,false],
 ['typographic_flag','Votre avenir prend place','Fanion typographique et colonne fine','rail','',false,false],
 ['mission_board','Projet métier','Tableau de projet en trois étapes','dashboard','',false,false],
 ['launchpad','Prêt à démarrer','Rampe de lancement illustrée','split','rise',true,true],
 ['chat_invite','Votre projet mérite une réponse','Invitation à échanger et bulles de dialogue','split','pulse',false,true],
 ['path_cards','À chaque étape, une équipe','Trois cartes pour accompagner votre parcours','dashboard','',false,true],
 ['agenda_card','La prochaine session','Invitation et date mise à l’honneur','invitation','',false,false],
 ['training_kit','Tout commence ici','Kit illustré du futur professionnel','dashboard','',false,true],
 ['metro_map','Votre ligne vers l’avenir','Ligne de métro et étapes du projet','stack','',false,false],
 ['swipe_deck','Faites le bon choix','Jeu de cartes en éventail','split','float',false,true],
 ['checklist','Votre projet prend vie','Liste de préparation et coche graphique','split','',false,false],
 ['focus_mode','Activez votre avenir','Interrupteur géant et affiche minimaliste','poster','pulse',true,false],
 ['emoji_diploma','Votre prochain chapitre','Diplôme illustré et halo rayonnant','split','float',false,true],
 ['emoji_rocket','Donnez de l’élan','Fusée et traînée verticale','poster','rise',false,true],
 ['emoji_toolbox','Un métier concret','Boîte à outils sur socle graphique','split','bob',false,true],
 ['emoji_handshake','Avançons ensemble','Poignée de main et deux formes réunies','stack','pulse',false,true],
 ['emoji_idea','Du projet à l’action','Ampoule et rayons graphiques','split','pulse',true,true],
 ['emoji_briefcase','La suite professionnelle','Mallette et carte de parcours','split','float',false,true],
 ['emoji_key','Ouvrez les possibilités','Clé et serrure monumentale','split','float',true,true],
 ['emoji_target','Gardez le cap','Cible illustrée et coordonnées graphiques','split','bob',false,true],
 ['emoji_spark','Votre talent, la suite','Étoiles et affiche lumineuse','poster','pulse',false,true],
 ['emoji_books','Apprendre pour avancer','Bibliothèque et pile de livres','split','bob',false,true],
 ['constellation','Reliez vos ambitions','Constellation et points de rencontre','stack','pulse',true,false],
 ['infinity','Une nouvelle dimension','Boucle infinie et jeu de lignes','split','float',false,false],
 ['kinetic_steps','Chaque étape compte','Escalier graphique en mouvement','split','rise',false,false],
 ['sonar','Trouvez votre voie','Éventail de lumière et signal circulaire','split','orbit',true,false],
 ['comet','Vers de nouveaux horizons','Comète et lignes de vitesse','poster','rise',true,false],
 ['folded_map','Tracez votre route','Carte pliée et repère de destination','split','bob',false,true],
 ['growth_garden','Faites grandir votre projet','Plante abstraite et courbes organiques','split','float',false,false],
 ['bridge','Un pont vers demain','Pont architectural et horizon ouvert','stack','',false,false],
 ['cascade','L’impulsion du changement','Dominos de couleur et rythme diagonal','split','orbit',false,false],
 ['celebration','Le début d’une belle suite','Arche festive et éclats illustrés','poster','bob',false,true]
];
export const NEW3_DESIGNS=definitions.map(([slug,name,description,layout,motion,dark,hasEmojis],index)=>({id:'new3_'+slug,slug,name,description,layout,motion,dark,hasEmojis,index:index+1}));
export const NEW3_IDS=NEW3_DESIGNS.map(d=>d.id);
const esc=value=>String(value??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const art=(name,body,motion='')=>`<div class="n3-art ${name}" aria-hidden="true" data-studio-decorative="true"${motion?` data-motion="${motion}"`:''}>${body}</div>`;
const svg=(body,box='0 0 400 400')=>`<svg viewBox="${box}" xmlns="http://www.w3.org/2000/svg">${body}</svg>`;
const line=(d,extra='')=>`<path d="${d}" fill="none" ${extra.includes('stroke="')?'':'stroke="currentColor"'} ${extra.includes('stroke-width=')?'':'stroke-width="3"'} ${extra}/>`;
const star=svg('<path d="m200 20 40 125 120-40-85 95 105 70-135-10-45 120-30-125-140 15 100-75-80-100 120 50Z" fill="currentColor"/>');
const arrow=svg('<path d="M45 325 330 40M100 40h230v230" fill="none" stroke="currentColor" stroke-width="52" stroke-linejoin="miter"/>');
const circles=n=>Array.from({length:n},(_,i)=>`<circle cx="200" cy="200" r="${175-i*27}" fill="none" stroke="currentColor" stroke-width="2"/>`).join('');
const emoji=(glyph,name,motion='')=>art('n3-emoji '+name,`<span>${glyph}</span>`,motion);
const tag=text=>`<span class="n3-label" data-fit="meta">${esc(text)}</span>`;
const field=(key,value,element='span')=>`<${element} class="n3-${key}" data-content-key="${key}" data-fit="${key==='title'?'title':key==='introduction'?'body':key==='cta'?'cta':'meta'}" data-element-name="${key}">${esc(value)}</${element}>`;

export function renderNew3TemplateBody(ctx){
 const d=NEW3_DESIGNS.find(d=>d.id===ctx.template.id);
 if(!d)throw new Error('Composition NEW3 inconnue : '+ctx.template.id);
 const c=ctx.slide.content||{},f=ctx.project.formation,codeText=f==='OR'?'INTÉGRALE':f==='DIRIGEANT'?'DESP':f;
 const value=(key,fallback)=>c[key]||c.data?.[key]||c.dates?.[key]||fallback;
 const title=field('title',c.title||'Préparez la prochaine étape de votre avenir','h1');
 const intro=field('introduction',c.introduction||'Une formation concrète, une équipe à vos côtés.','p');
 const cta=`<div class="n2-action">${field('cta',value('cta','Parlons de votre projet'))}<b aria-hidden="true">↗</b></div>`;
 const date=field('startDate',value('startDate',value('date','Prochaine session')),'time');
 const code=`<span class="n2-code" data-fit="meta" data-motion-foreground>${esc(codeText)}</span>`;
 const copy=(label=d.name,withDate=false)=>`<section class="n3-copy">${tag(label)}${title}${intro}${cta}${withDate?`<div class="n3-date-line">${date}</div>`:''}</section>`;
 const head=(label=d.name)=>`<header class="n3-head">${tag(label)}${title}</header>`;
 const bottom=()=>`<section class="n3-bottom">${intro}${cta}</section>`;
 const scene=body=>`<aside class="n3-scene">${body}</aside>`;
 const note=text=>`<span class="n3-note" data-fit="meta">${esc(text)}</span>`;
 const learningSteps=['Échangeons sur votre projet','Préparons votre inscription','Entrez en formation'];
 const rows=()=>`<ul class="n3-checks">${learningSteps.map(s=>`<li><i aria-hidden="true">✓</i><span data-fit="meta">${s}</span></li>`).join('')}</ul>`;
 const bodies={
  prism:()=>`${copy('CHANGEZ DE PERSPECTIVE',true)}${scene(art('n3-prism',svg('<path d="M70 310 185 35 345 270Z" fill="currentColor" opacity=".22"/><path d="m185 35 35 315 125-80Z" fill="currentColor" opacity=".52"/>'+line('M70 310 185 35 345 270 70 310 220 350 345 270M185 35 220 350')),d.motion)+code)}`,
  sunrise:()=>`${head('LE JOUR D’UN NOUVEAU DÉPART')}${scene(art('n3-sunrise',svg('<circle cx="200" cy="160" r="115" fill="currentColor"/>'+Array.from({length:8},(_,i)=>line(`M20 ${210+i*21}H380`)).join('')),d.motion)+`<div class="n3-horizon-label">${code}${date}</div>`)}${bottom()}`,
  monogram:()=>`${scene(`<div class="n3-monogram-letter" data-fit="title">${esc(codeText)}</div><div class="n3-monogram-bar"></div>${note('UN PROJET. UN MÉTIER. VOUS.')}`)}${copy('VOTRE MÉTIER EN GRAND',true)}`,
  archway:()=>`${copy('PASSEZ À LA SUITE')}${scene(art('n3-arches',svg(Array.from({length:5},(_,i)=>`<path d="M${35+i*29} 375V185a${165-i*29} ${165-i*29} 0 0 1 ${330-i*58} 0v190" fill="none" stroke="currentColor" stroke-width="15" opacity="${.22+i*.18}"/>`).join('')))+`<div class="n3-arch-code">${code}</div>`)}`,
  orbit_cards:()=>`${head('AUTOUR DE VOTRE PROJET')}${scene(art('n3-orbit-lines',svg(circles(3)))+emoji('🎓','n3-orbit-a','float')+emoji('💼','n3-orbit-b','bob')+emoji('✨','n3-orbit-c')+`<div class="n3-orbit-center">${code}</div>`)}${bottom()}`,
  ribbon_path:()=>`${head('UN PARCOURS QUI VOUS RESSEMBLE')}${scene(art('n3-ribbon-flow',svg('<path d="M20 245C90 50 145 340 210 145S310 70 375 195" fill="none" stroke="currentColor" stroke-width="62" stroke-linecap="square"/>'+line('M20 245C90 50 145 340 210 145S310 70 375 195','stroke-dasharray="3 14"'), '0 0 400 300'),d.motion))}${bottom()}<div class="n3-date-line">${date}</div>`,
  paper_cut:()=>`${scene(art('n3-paper-layers','<i></i><i></i><i></i><i></i><b>↗</b>'))}${copy('DÉCOUPEZ UN NOUVEL HORIZON',true)}`,
  spotlight:()=>`${tag('VOTRE PROJET MÉRITE LA LUMIÈRE')}${scene(art('n3-spotlight',svg('<circle cx="200" cy="200" r="178" fill="currentColor" opacity=".13"/><circle cx="200" cy="200" r="132" fill="currentColor" opacity=".28"/><circle cx="200" cy="200" r="80" fill="currentColor"/>'),d.motion)+code)}${title}${bottom()}`,
  zigzag:()=>`${scene(art('n3-zigzag',svg('<path d="m40 350 90-130 50 70 70-160 70 45 45-135" fill="none" stroke="currentColor" stroke-width="55" stroke-linejoin="bevel"/>'),d.motion)+note('L’ÉLAN COMMENCE ICI'))}${copy('ET SI VOUS OSIEZ ?',true)}`,
  wave_signal:()=>`${head('UNE NOUVELLE FRÉQUENCE')}${scene(art('n3-wave-bars',`<div>${[50,90,160,250,330,230,170,290,350,220,130,65,110,210,90].map(h=>`<i style="--bar:${h}"></i>`).join('')}</div>`,d.motion))}<div class="n3-wave-bottom">${code}${date}</div>${bottom()}`,
  headline_press:()=>`<div class="n3-press-masthead">${tag('INTÉGRALE / ÉDITION AVENIR')}${code}</div>${title}<div class="n3-press-rule"></div><section class="n3-press-columns"><div>${intro}${cta}</div><aside>${tag('À LA UNE')}${date}<b class="n3-print-arrow" aria-hidden="true">↗</b></aside></section>`,
  column_cover:()=>`<aside class="n3-spine"><span data-fit="badge">FORMATION PROFESSIONNELLE</span>${code}</aside><section class="n3-cover-copy">${tag('LE PROCHAIN CHAPITRE')}${title}${intro}${cta}</section><div class="n3-cover-stamp">${date}${note('INTÉGRALE ACADEMY')}</div>`,
  manifesto:()=>`${code}<div class="n3-manifesto-words"><span>APPRENDRE.</span><span>AVANCER.</span></div>${title}${intro}${cta}`,
  underlined:()=>`${copy('UN PROJET QUI PREND TOUT SON SENS',true)}${scene(`<div class="n3-handwritten">${note('LE DÉCLIC')}${art('n3-hand-arrow',svg(line('M65 55c260-20 300 160 130 230-95 40-150-40-80-80 60-35 115 35 95 130M158 290l52 45 50-75','stroke-width="12"')))}</div>${code}`)}`,
  index_tabs:()=>`${scene(`<div class="n3-tab-labels">${tag('PROJET')}${tag('FORMATION')}${tag('AVENIR')}</div><div class="n3-index-sheet">${code}${note('LA SUITE VOUS APPARTIENT')}<b aria-hidden="true">↗</b></div>`)}${copy('OUVREZ LE BON CHAPITRE')}`,
  editorial_seal:()=>`${head('LES BELLES HISTOIRES COMMENCENT ICI')}<section class="n3-seal-row"><div>${intro}${cta}${date}</div><aside>${art('n3-seal',svg('<path d="m200 20 32 22 39-4 20 34 38 10 5 39 27 28-16 36 9 38-34 20-10 38-39 5-28 27-36-16-38 9-20-34-38-10-5-39-27-28 16-36-9-38 34-20 10-38 39-5Z" fill="currentColor"/><circle cx="200" cy="200" r="120" fill="none" stroke="var(--n3-paper)" stroke-width="2"/>'))}${code}</aside></section>`,
  cut_type:()=>`${scene(`<div class="n3-cut-words"><strong>ET<br>SI ?</strong><i></i></div>${code}`)}${copy('PLACE AU CHANGEMENT',true)}`,
  swiss_grid:()=>`<header class="n3-swiss-top">${code}${tag('CAP SUR VOTRE AVENIR')}</header>${title}<div class="n3-swiss-grid"><div>${intro}${cta}</div>${art('n3-swiss-arrow',arrow)}<footer>${date}</footer></div>`,
  offset_blocks:()=>`<header class="n3-offset-heading">${tag('CONSTRUISEZ LA SUITE')}${title}</header><section class="n3-offset-intro">${intro}${code}</section><aside class="n3-offset-date">${tag('VOTRE PROCHAINE ÉTAPE')}${date}<b aria-hidden="true">↗</b></aside><footer class="n3-offset-cta">${cta}</footer>`,
  typographic_flag:()=>`<aside class="n3-flag-rail">${tag('FAIRE PLACE À VOTRE AVENIR')}<div class="n3-flag">${code}<b aria-hidden="true">↗</b></div></aside>${copy('UN NOUVEAU DÉPART',true)}`,
  mission_board:()=>`${head('VOTRE PROJET PREND FORME')}<section class="n3-mission-columns">${['UN PROJET','UNE FORMATION','UN AVENIR'].map((s,i)=>`<article><i aria-hidden="true">${['○','↗','✦'][i]}</i>${tag(s)}<span data-fit="meta">${['En parler ensemble','Acquérir des compétences','Préparer la suite'][i]}</span></article>`).join('')}</section>${bottom()}`,
  launchpad:()=>`${copy('PRÊT POUR LE DÉPART ?',true)}${scene(art('n3-launch-grid',svg(line('M30 320h340M50 355h300M100 390h200M200 250 40 400M200 250 360 400')))+emoji('🚀','n3-launch-rocket',d.motion)+`<div class="n3-launch-pill">${code}</div>`)}`,
  chat_invite:()=>`${copy('PARLONS DE VOTRE PROJET')}${scene(`<div class="n3-chat-stack"><article><b>👋</b>${note('Une envie de changement ?')}</article><article>${note('On prépare la suite ensemble.')}<b>💬</b></article>${art('n3-typing','<i></i><i></i><i></i>',d.motion)}${code}</div>`)}`,
  path_cards:()=>`${head('À CHAQUE ÉTAPE, UNE ÉQUIPE')}<ol class="n3-path-cards">${['💬','📚','🧭'].map((e,i)=>`<li><span aria-hidden="true">${e}</span><strong data-fit="meta">${learningSteps[i]}</strong><b aria-hidden="true">↗</b></li>`).join('')}</ol>${bottom()}`,
  agenda_card:()=>`<header class="n3-invitation-head">${tag('VOUS AVEZ RENDEZ-VOUS AVEC LA SUITE')}${code}</header>${title}<section class="n3-invitation-date"><i aria-hidden="true"></i><div>${tag('PROCHAINE ÉTAPE')}${date}</div><b aria-hidden="true">↗</b></section>${bottom()}`,
  training_kit:()=>`${head('LES OUTILS POUR AVANCER')}<section class="n3-kit">${['📚','🧰','💼'].map((e,i)=>`<article><span aria-hidden="true">${e}</span>${tag(['APPRENDRE','S’ENTRAÎNER','SE PROJETER'][i])}</article>`).join('')}</section>${bottom()}`,
  metro_map:()=>`${head('PRENEZ LA DIRECTION DE VOTRE AVENIR')}<section class="n3-metro">${learningSteps.map((s,i)=>`<div><i aria-hidden="true"></i><span data-fit="meta">${s}</span>${i===2?code:''}</div>`).join('')}</section>${bottom()}<div class="n3-date-line">${date}</div>`,
  swipe_deck:()=>`${scene(`<div class="n3-card-fan">${art('n3-playing-card n3-playing-a','<span>📚</span><b>+</b>','float')}${art('n3-playing-card n3-playing-b','<span>💼</span><b>↗</b>')}${art('n3-playing-card n3-playing-c','<span>🎓</span><b>✦</b>')}</div>`)}${copy('LA BONNE CARTE POUR VOTRE AVENIR',true)}`,
  checklist:()=>`${copy('DONNEZ FORME À VOTRE PROJET')}${scene(`<article class="n3-check-sheet"><header>${code}<b aria-hidden="true">✓</b></header>${rows()}<footer>${date}</footer></article>`)}`,
  focus_mode:()=>`${tag('ACTIVEZ LE MODE AVENIR')}${scene(art('n3-switch','<i></i><b>↗</b>',d.motion))}${title}${intro}${cta}`,
  emoji_diploma:()=>`${scene(art('n3-diploma-rays',svg(Array.from({length:12},(_,i)=>`<path d="M200 35v45" transform="rotate(${i*30} 200 200)" stroke="currentColor" stroke-width="12"/>`).join('')))+emoji('🎓','n3-diploma-emoji',d.motion)+`<div class="n3-diploma-code">${code}</div>`)}${copy('LA PROCHAINE PAGE DE VOTRE HISTOIRE')}`,
  emoji_rocket:()=>`<div class="n3-rocket-poster">${emoji('🚀','n3-rocket-emoji',d.motion)}${art('n3-rocket-trail','<i></i><i></i><i></i>')}</div>${tag('L’ÉLAN COMMENCE AVEC VOUS')}${title}${bottom()}`,
  emoji_toolbox:()=>`${copy('DES COMPÉTENCES POUR UN MÉTIER',true)}${scene(`<div class="n3-tool-podium">${emoji('🧰','n3-tool-emoji',d.motion)}<i></i><div>${code}</div></div>`)}`,
  emoji_handshake:()=>`${head('ENSEMBLE POUR PRÉPARER LA SUITE')}${scene(`<div class="n3-handshake-shapes"><i></i><i></i>${emoji('🤝','n3-handshake-emoji',d.motion)}</div>`)}${bottom()}`,
  emoji_idea:()=>`${scene(art('n3-idea-orbit',svg('<circle cx="200" cy="200" r="158" fill="none" stroke="currentColor" stroke-dasharray="8 17" stroke-width="3"/>'))+emoji('💡','n3-idea-emoji',d.motion)+note('LE DÉCLIC'))}${copy('VOTRE IDÉE MÉRITE UNE SUITE',true)}`,
  emoji_briefcase:()=>`${copy('LA PROCHAINE ÉTAPE PROFESSIONNELLE')}${scene(`<div class="n3-career-card"><header>${tag('VOTRE FUTUR MÉTIER')}${code}</header>${emoji('💼','n3-career-emoji',d.motion)}<footer>${note('UN PROJET À CONSTRUIRE ENSEMBLE')}</footer></div>`)}`,
  emoji_key:()=>`${scene(`<div class="n3-keyhole"><i></i>${emoji('🗝️','n3-key-emoji',d.motion)}</div>${code}`)}${copy('OUVREZ UN NOUVEAU CHAMP DES POSSIBLES')}`,
  emoji_target:()=>`${copy('VOTRE MÉTIER EN LIGNE DE MIRE',true)}${scene(`<div class="n3-target-frame"><i></i><i></i><i></i><i></i>${emoji('🎯','n3-target-emoji',d.motion)}${code}</div>`)}`,
  emoji_spark:()=>`<header class="n3-spark-heading">${code}${tag('FAITES GRANDIR VOTRE TALENT')}</header>${scene(art('n3-spark-rings',svg('<ellipse cx="200" cy="200" rx="180" ry="85" fill="none" stroke="currentColor" stroke-width="2" transform="rotate(-28 200 200)"/>'))+emoji('✨','n3-spark-emoji',d.motion))}${title}${bottom()}`,
  emoji_books:()=>`${scene(`<div class="n3-bookshelf">${emoji('📚','n3-books-emoji',d.motion)}<i></i>${tag('COMPRENDRE · S’ENTRAÎNER · AVANCER')}</div>`)}${copy('APPRENDRE POUR PRÉPARER LA SUITE',true)}`,
  constellation:()=>`${head('RELIEZ VOS AMBITIONS')}${scene(art('n3-constellation',svg(line('M35 210 110 55 220 155 345 65 300 290 170 345 35 210M110 55 170 345 220 155 300 290')+[[35,210],[110,55],[220,155],[345,65],[300,290],[170,345]].map(([x,y],i)=>`<circle cx="${x}" cy="${y}" r="${i===2?21:9}" fill="currentColor"/>`).join('')),d.motion)+code)}${bottom()}`,
  infinity:()=>`${copy('UNE NOUVELLE DIMENSION',true)}${scene(art('n3-infinity',svg('<path d="M200 200C80-20-55 300 85 300S285-20 370 150 280 390 200 200Z" fill="none" stroke="currentColor" stroke-width="38"/>'+line('M200 200C80-20-55 300 85 300S285-20 370 150 280 390 200 200Z','stroke="var(--n3-paper)"')),d.motion))}`,
  kinetic_steps:()=>`${scene(art('n3-step-ladder',`<div>${[1,2,3,4].map(i=>`<i style="--step:${i}"><b>↗</b></i>`).join('')}</div>`,d.motion)+note('À CHAQUE PAS, VOUS AVANCEZ'))}${copy('CONSTRUISEZ VOTRE PROGRESSION')}`,
  sonar:()=>`${copy('TROUVEZ VOTRE DIRECTION')}${scene(art('n3-sonar-disc',svg(circles(4)+line('M200 15v370M15 200h370')+'<path d="M200 200 340 70a185 185 0 0 1 45 130Z" fill="currentColor" opacity=".28"/><circle cx="280" cy="120" r="14" fill="currentColor"/>'),d.motion)+code)}`,
  comet:()=>`${scene(art('n3-comet',svg('<path d="M40 345 300 90M70 375 330 120M15 300 250 65" stroke="currentColor" stroke-width="27" stroke-linecap="round" opacity=".3"/><circle cx="290" cy="110" r="67" fill="currentColor"/><circle cx="290" cy="110" r="43" fill="var(--n3-paper)"/>'),d.motion))}${tag('PRENEZ DE L’ÉLAN')}${title}${bottom()}`,
  folded_map:()=>`${scene(`<div class="n3-map"><i></i><i></i><i></i>${art('n3-map-route',svg(line('M30 290 100 230 170 270 220 140 335 90','stroke-width="9" stroke-dasharray="12 9"')))}${emoji('📍','n3-map-pin',d.motion)}</div>`)}${copy('VOTRE ITINÉRAIRE VERS LA SUITE',true)}`,
  growth_garden:()=>`${copy('CULTIVEZ VOTRE PROJET')}${scene(art('n3-garden',svg('<path d="M200 365V90" stroke="currentColor" stroke-width="12"/><path d="M200 255C80 270 35 210 45 130c105-10 155 40 155 125Zm0-80C330 195 365 125 345 55c-100-5-145 55-145 120Z" fill="currentColor"/><path d="M200 335C280 345 325 310 330 245c-85-20-130 20-130 90Z" fill="currentColor" opacity=".45"/>'+line('M80 375h240')),d.motion)+code)}`,
  bridge:()=>`${head('UN PONT VERS VOTRE AVENIR')}${scene(art('n3-bridge',svg('<path d="M25 330h350M60 330V90M340 330V90M60 120q140 230 280 0" fill="none" stroke="currentColor" stroke-width="14"/>'+[100,140,180,220,260,300].map((x,i)=>line(`M${x} ${[177,218,240,240,218,177][i]}V330`)).join('')))+`<div class="n3-bridge-code">${code}</div>`)}${bottom()}`,
  cascade:()=>`${scene(art('n3-cascade',`<div>${[0,1,2,3,4].map(i=>`<i style="--tile:${i}"><b>↗</b></i>`).join('')}</div>`,d.motion))}${copy('UNE IMPULSION POUR TOUT CHANGER',true)}`,
  celebration:()=>`<header class="n3-celebration-top">${tag('LA SUITE S’ÉCRIT MAINTENANT')}${code}</header>${scene(art('n3-celebration-rays',svg('<path d="M45 210a155 155 0 0 1 310 0" fill="none" stroke="currentColor" stroke-width="35"/>'+line('M50 285 20 330M355 280l30 35M200 40V5')))+emoji('🎉','n3-celebration-emoji',d.motion))}${title}${bottom()}`
 };
 return `<main class="n2 n3 n3-${d.layout} n3-${d.slug}" data-layout-role="${d.id}" data-new3-design="${d.id}">${bodies[d.slug]()}</main>`;
}
