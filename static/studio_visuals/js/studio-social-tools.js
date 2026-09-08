import {PUBLICATION_COURSES,COVER_PUBLICATIONS,PUBLICATION_ACTIONS} from './studio-publication-copy.js';
import {SOCIAL_BY_ID,SOCIAL_COURSES} from './studio-social-content.js';
import {SEASONAL_DESIGNS} from './studio-seasonal-templates.js';
import {socialDefaultContent,escapeSocial as e} from './studio-social-templates.js';
import {normalizeSlide,defaultContentForFormation,ALL_FORMATS} from './studio-store.js';

export function normalizeSearch(value){return String(value??'').normalize('NFD').replace(/[\u0300-\u036f]/g,'').toLowerCase().replace(/[^a-z0-9]+/g,' ').trim()}
export function matchesTemplateSearch(template,query){
 const haystack=normalizeSearch([template.id,template.name,template.description,template.collection,template.formationPreset,template.courseKey,template.sessionKind,template.contentDefaults?.title,template.contentDefaults?.introduction,template.isCarousel?'carrousel carousel diapositives':'',template.isCover?'couverture cover banniere':''].join(' '));
 return normalizeSearch(query).split(' ').filter(Boolean).every(word=>haystack.includes(word));
}
export function compatibleFormat(template,current){const ids=template.supportedFormats||['instagram_square'];return ALL_FORMATS[ids.includes(current?.id)?current.id:ids[0]]||ALL_FORMATS.instagram_square}
export function applySocialTemplate(project,template){
 const d=SOCIAL_BY_ID[template.id];if(!d)throw new Error('Modèle social inconnu');
 const previous=project.slides[project.activeSlideIndex],formation=template.formationPreset;
 project.format=compatibleFormat(template,project.format);project.formation=formation;
 const build=(page,index)=>normalizeSlide({formation,templateId:template.id,layoutVariantId:template.id,carouselPage:index,role:index===0?'cover':index===4?'conclusion':'content',
  content:{...defaultContentForFormation(formation),...socialDefaultContent(template,index),footer:{...previous.content.footer},_autoFormation:formation,_socialTemplateId:template.id},options:{showSafeMargins:previous.options?.showSafeMargins!==false,showPagination:false}});
 if(template.isCarousel){project.slides=d.pages.map(build);project.activeSlideIndex=0;project.name=template.name;}
 else if(template.isCover){project.slides=[build(d,0)];project.activeSlideIndex=0;project.name=template.name;}
 else{project.slides[project.activeSlideIndex]=build(d,0);}
}

const WEBSITE='https://www.integraleacademy.com';
const FACT_FIELDS=['date','startDate','endDate','examDate','location','availability','duration','financing'];
const clean=value=>String(value??'').trim();
const paragraphs=parts=>parts.map(clean).filter(Boolean).join('\n\n');
const shortAngle=text=>text.split(/(?<=[.!?])\s+/)[0];
const SESSION_ANGLES=[
 'Vous aimeriez vous projeter dans le quotidien du métier ? Commencez par découvrir les compétences à travailler.',
 'Une envie de changer de voie ou de faire évoluer votre activité ? Donnez à votre projet une prochaine étape concrète.',
 'Vous avez envie d’apprendre à partir de situations métier ? Regardez ce que ce parcours peut vous permettre de travailler.',
 'Choisir une formation, c’est aussi penser à son organisation : objectifs, prérequis, déroulement et démarches.',
 'Vous comparez les possibilités pour la suite de votre parcours ? Faites le lien entre vos envies et les missions du métier.'
];
const SESSION_PRO_ANGLES=[
 'Un projet professionnel se prépare en identifiant les compétences à développer et les missions auxquelles elles répondent.',
 'Pour préparer une évolution ou une reconversion, rapprochez votre objectif des contenus et des conditions du parcours.',
 'Relier les apprentissages à des situations métier permet de mieux se projeter dans une formation.',
 'Objectifs, prérequis, déroulement et démarches : ces repères permettent de planifier un parcours de formation.',
 'Comparer les parcours commence par une lecture concrète des missions et des compétences à travailler.'
];
function infoLines(content){
 const date=content.startDate&&content.endDate?`Du ${content.startDate} au ${content.endDate}`:content.startDate?`À partir du ${content.startDate}`:content.date||'';
 return [date?`📅 ${date}`:'',content.examDate?`📝 Examen : ${content.examDate}`:'',content.location?`📍 ${content.location}`:'',content.availability?`⏳ ${content.availability}`:'',content.duration?`⏱️ ${content.duration}`:'',content.financing?`💡 Financement : ${content.financing}`:''].filter(Boolean).join('\n');
}
function factualContent(content){
 const factual={...content};
 for(const [key,defaultValue] of [['duration','175 h'],['financing','CPF'],['availability','Places limitées']])if(content[key]===defaultValue&&!content._publicationFields?.includes(key))factual[key]='';
 return factual;
}
function stableIndex(id){return Array.from(id||'').reduce((n,c)=>n+c.codePointAt(0),0)%5}
function courseFor(project,d){
 const key=d?.key||Object.keys(SOCIAL_COURSES).find(k=>SOCIAL_COURSES[k].formation===project.formation)||'general';
 return {key,course:SOCIAL_COURSES[key],copy:PUBLICATION_COURSES[key]};
}
function changedCopy(content,defaults,keys=['title','introduction']){
 return keys.filter(key=>clean(content[key])!==clean(defaults[key])).map(key=>clean(content[key])).filter(Boolean).join('\n\n');
}
function finishPublication(body,action,course,network,index){
 const tags=[...new Set(['#IntegraleAcademy',...(course?.hashtags||'#Formation #ProjetProfessionnel').split(/\s+/),...(network==='instagram'?['#FormationProfessionnelle']:[])])];
 return paragraphs([body,`👉 ${action||PUBLICATION_ACTIONS[network][index]}\n${course?.formation==='A3P'?WEBSITE+'/securiteprivee':WEBSITE}`,tags.join(' ')]).replace(/\n{3,}/g,'\n\n');
}
export function publicationText(project,template,network='facebook'){
 if(!PUBLICATION_ACTIONS[network])network='facebook';
 const c=project.slides[project.activeSlideIndex]?.content||{},d=SOCIAL_BY_ID[template.id],seasonal=SEASONAL_DESIGNS.find(x=>x.id===template.id);
 const {key,course,copy}=courseFor(project,d),emoji=course.emoji,index=d?.index??stableIndex(template.id);
 let body,action;
 if(d?.pages){
  // Resolve each page independently, including a partially edited carrousel.
  const pages=d.pages.map((page,i)=>project.slides.find(s=>s.templateId===template.id&&s.carouselPage===i)?.content||page);
  const lead=clean(pages[0].introduction)!==clean(d.pages[0].introduction)?pages[0].introduction:network==='instagram'?shortAngle(copy.angles[index]):copy.angles[index];
  const points=pages.slice(1,4).map((p,i)=>{
   const includeBody=network==='linkedin'||clean(p.introduction)!==clean(d.pages[i+1].introduction);
   return `${network==='linkedin'?'•':copy.bullets[i]} ${clean(p.title)}${includeBody&&clean(p.introduction)?`\n${clean(p.introduction)}`:''}`;
  }).join(network==='linkedin'?'\n\n':'\n');
  const facts=Object.fromEntries(FACT_FIELDS.map(field=>[field,pages.find(p=>clean(p[field]))?.[field]||'']));
  body=paragraphs([
   `${emoji} ${clean(pages[0].title)}`,lead,
   `${network==='instagram'?'Faites défiler pour découvrir 👇':network==='linkedin'?'Trois repères à explorer dans ce carrousel :':'Au fil des images 👇'}\n${points}`,
   changedCopy(pages[4],d.pages[4]),infoLines(facts),
   key==='desp_vae'?'La décision de validation appartient au jury.':''
  ]);
  action=network==='instagram'?`Envie d’aller plus loin ? Découvrez le parcours et préparons ${copy.goal}.`:network==='linkedin'?`Pour préparer ${copy.goal}, consultez les modalités du parcours et contactez notre équipe sur le site.`:`${copy.question} Retrouvez le parcours sur notre site et parlons de vos prochaines étapes.`;
 }else if(d?.kind){
  const label=d.key==='desp_initial'?'DESP':course.label;
  const title=`${d.kind==='places'?'⏳ DERNIÈRES PLACES':'📅 PROCHAINE SESSION'} · ${label}\n${clean(c.title)}`;
  const lead=clean(c.introduction)!==clean(d.introduction)?c.introduction:network==='instagram'?copy.question:network==='linkedin'?SESSION_PRO_ANGLES[index]:SESSION_ANGLES[index];
  body=paragraphs([title,lead,network==='instagram'?`${emoji} ${course.tags.join(' · ')}`:`${emoji} ${copy.reason}`,infoLines(c)]);
  action=d.kind==='places'
   ?network==='instagram'?'Intéressé ? Vérifiez les places restantes et préparez votre inscription avec notre équipe sur le site.':`Vous souhaitez rejoindre la session ? Vérifiez les disponibilités et les conditions d’entrée pour préparer ${copy.goal} avec notre équipe.`
   :network==='instagram'?'Dates, programme, inscription : retrouvez les informations de la session sur notre site.':`Pour organiser ${copy.goal}, retrouvez le programme et renseignez-vous sur les dates, les prérequis et l’inscription sur notre site.`;
 }else if(d?.network){
  body=paragraphs([`✨ ${clean(c.title)}`,COVER_PUBLICATIONS[index][network],changedCopy(c,d,['introduction'])]);
 }else if(seasonal&&!c._manual){
  // These seasonal posts already have authored event-specific copy.
  return seasonal.socialCopy[network==='instagram'?'instagram':'facebook'];
 }else{
  const intro=clean(c.introduction||template.description),title=clean(c.title||template.name);
  body=paragraphs([`${emoji} ${title}`,intro,network==='instagram'?'':key==='general'?'':copy.reason,infoLines(factualContent(c))]);
  if(network==='instagram'&&key!=='general')action=`${copy.question} Découvrez le programme et les modalités sur notre site.`;
  // A CTA explicitly edited in the visual remains part of the generated post.
  const customCta=c._publicationFields?.includes('cta')&&clean(c.cta)&&c.cta!=='Faites le premier pas vers votre futur métier';
  if(customCta)action=`${clean(c.cta).replace(/[.!]+$/,'')}. Retrouvez les informations sur notre site.`;
 }
 return finishPublication(body,action,course,network,index);
}
export function publicationKey(template,network){return `${template.id}:${network}`}
export function renderPublicationPanel(project,template,network='facebook'){
 const value=project.publications?.[publicationKey(template,network)]??publicationText(project,template,network);
 return `<section class="studio-publication" aria-labelledby="publicationTitle"><div class="studio-publication-heading"><span>✎</span><h3 id="publicationTitle">Texte de publication</h3></div><p>${template.isCarousel?'Le texte accompagne le carrousel complet.':'Votre publication, prête à personnaliser et à copier.'}</p><label>Réseau social<select id="publicationNetwork">${[['facebook','Facebook'],['instagram','Instagram'],['linkedin','LinkedIn']].map(([id,label])=>`<option value="${id}" ${id===network?'selected':''}>${label}</option>`).join('')}</select></label><div class="studio-publication-actions"><button type="button" class="social-studio__primary" data-action="copyPublication">Copier le texte complet</button><button type="button" data-action="resetPublication">Actualiser depuis le visuel</button></div><label class="studio-publication-label" for="publicationText">Texte, emojis et hashtags</label><textarea id="publicationText" spellcheck="true" rows="13">${e(value)}</textarea><small>Vos retouches sont enregistrées avec le projet. « Actualiser » régénère le texte à partir du visuel.</small></section>`;
}

// One ordered ZIP avoids browsers blocking multiple carousel downloads. PNGs
// are already compressed, so the ZIP uses the standard uncompressed method.
const crcTable=Array.from({length:256},(_,n)=>{for(let k=0;k<8;k++)n=n&1?0xedb88320^(n>>>1):n>>>1;return n>>>0});
function crc32(bytes){let crc=0xffffffff;for(const b of bytes)crc=crcTable[(crc^b)&255]^(crc>>>8);return (crc^0xffffffff)>>>0}
export function createCarouselZip(files){
 const chunks=[],central=[];let offset=0,centralSize=0;
 for(const file of files){const name=new TextEncoder().encode(file.name),bytes=file.bytes,crc=crc32(bytes),header=new Uint8Array(30+name.length),v=new DataView(header.buffer);
  v.setUint32(0,0x04034b50,true);v.setUint16(4,20,true);v.setUint16(6,0x800,true);v.setUint32(14,crc,true);v.setUint32(18,bytes.length,true);v.setUint32(22,bytes.length,true);v.setUint16(26,name.length,true);header.set(name,30);chunks.push(header,bytes);
  const cd=new Uint8Array(46+name.length),c=new DataView(cd.buffer);c.setUint32(0,0x02014b50,true);c.setUint16(4,20,true);c.setUint16(6,20,true);c.setUint16(8,0x800,true);c.setUint32(16,crc,true);c.setUint32(20,bytes.length,true);c.setUint32(24,bytes.length,true);c.setUint16(28,name.length,true);c.setUint32(42,offset,true);cd.set(name,46);central.push(cd);centralSize+=cd.length;offset+=header.length+bytes.length;
 }
 const end=new Uint8Array(22),v=new DataView(end.buffer);v.setUint32(0,0x06054b50,true);v.setUint16(8,files.length,true);v.setUint16(10,files.length,true);v.setUint32(12,centralSize,true);v.setUint32(16,offset,true);
 return new Blob([...chunks,...central,end],{type:'application/zip'});
}
