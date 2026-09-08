import {PUBLICATION_COURSES,PUBLICATION_TOPICS,COVER_PUBLICATIONS,PUBLICATION_ACTIONS} from './studio-publication-copy.js';
import {SOCIAL_BY_ID,SOCIAL_COURSES} from './studio-social-content.js';
import {SEASONAL_DESIGNS} from './studio-seasonal-templates.js';
import {socialDefaultContent,escapeSocial as e} from './studio-social-templates.js';
import {normalizeSlide,defaultContentForFormation,ALL_FORMATS} from './studio-store.js';

export function normalizeSearch(value){return String(value??'').normalize('NFD').replace(/[\u0300-\u036f]/g,'').toLowerCase().replace(/[^a-z0-9]+/g,' ').trim()}
export function matchesTemplateSearch(template,query){
 const haystack=normalizeSearch([template.id,template.name,template.description,template.collection,template.formationPreset,template.courseKey,template.sessionKind,template.contentDefaults?.title,template.contentDefaults?.introduction,template.isCarousel?'carrousels carroussels carousels diapositives':'',template.isCover?'couverture cover banniere':''].join(' '));
 return normalizeSearch(query).split(' ').filter(Boolean).every(word=>haystack.includes(word));
}
export function compatibleFormat(template,current){const ids=template.supportedFormats||['instagram_square'];return ALL_FORMATS[ids.includes(current?.id)?current.id:ids[0]]||ALL_FORMATS.instagram_square}
export function normalizeCoverProject(project){
 const canonical=ALL_FORMATS[project.format?.id];
 if(!canonical||!['facebook_cover','linkedin_cover'].includes(canonical.id))return;
 if(canonical.id==='facebook_cover'&&project.format.width!==canonical.width){
  const factor=canonical.width/(project.format.width||851);
  for(const slide of project.slides||[]){
   if(slide.logo)slide.logo.width=Math.min(240,Math.round((slide.logo.width||150)*factor));
   const d=SOCIAL_BY_ID[slide.templateId];
   if(d?.network==='facebook'&&slide.content?.introduction===d.introduction)slide.content.introduction=socialDefaultContent({id:slide.templateId}).introduction;
  }
 }
 project.format=canonical;
}
export function applySocialTemplate(project,template){
 const d=SOCIAL_BY_ID[template.id];if(!d)throw new Error('Modèle social inconnu');
 const previous=project.slides[project.activeSlideIndex],formation=template.formationPreset;
 project.format=compatibleFormat(template,project.format);project.formation=formation;
 const build=(page,index)=>normalizeSlide({formation,templateId:template.id,layoutVariantId:template.id,carouselPage:index,role:index===0?'cover':index===4?'conclusion':'content',
  content:{...defaultContentForFormation(formation),...socialDefaultContent(template,index),footer:{...previous.content.footer},_autoFormation:formation,_socialTemplateId:template.id},options:{showSafeMargins:previous.options?.showSafeMargins!==false,showPagination:false}});
 if(template.isCarousel){project.slides=d.pages.map(build);project.activeSlideIndex=0;project.name=template.name;}
 else if(template.isCover){project.slides=[build(d,0)];project.slides[0].logo.width=d.network==='linkedin'?220:240;project.activeSlideIndex=0;project.name=template.name;}
 else{project.slides[project.activeSlideIndex]=build(d,0);}
}

const WEBSITE='https://www.integraleacademy.com';
export const PUBLICATION_DATA_FIELDS=[
 ['startDate','Date de début'],['endDate','Date de fin'],['date','Dates (texte libre)'],
 ['examDate','Date d’examen'],['location','Lieu'],['duration','Durée'],
 ['price','Tarif'],['financing','Financement'],['availability','Places disponibles']
];
const FACT_FIELDS=PUBLICATION_DATA_FIELDS.map(([key])=>key);
const clean=value=>String(value??'').trim();
const paragraphs=parts=>parts.map(clean).filter(Boolean).join('\n\n');
const SESSION_INTROS=[
 'Préparez dès maintenant votre projet de formation.',
 'Découvrez le parcours et préparez votre dossier avec notre équipe.',
 'Renseignez-vous sur le programme et les conditions d’entrée en formation.',
 'Anticipez les démarches pour organiser votre entrée en formation.',
 'Faites le point sur votre projet avant de choisir votre session.'
];
const LEGACY_FACTS={duration:['175 h'],financing:['CPF','CPF / autres'],availability:['Places limitées']};
function factualContent(content){
 const facts={};
 for(const field of FACT_FIELDS){
  const value=clean(content[field]);
  facts[field]=LEGACY_FACTS[field]?.includes(value)&&!content._publicationFields?.includes(field)?'':value;
 }
 return facts;
}
function stableIndex(id){return Array.from(id||'').reduce((n,c)=>n+c.codePointAt(0),0)%5}
function courseFor(project,template,d=SOCIAL_BY_ID[template.id]){
 const formation=template.formationPreset||project.formation;
 let key=d?.key||template.courseKey;
 if(!PUBLICATION_COURSES[key]){
  const c=project.slides[project.activeSlideIndex]?.content||{};
  const isVae=formation==='DIRIGEANT'&&/\bvae\b/.test(normalizeSearch([template.id,template.name,c.eyebrow,c.title].join(' ')));
  key=isVae?'desp_vae':Object.keys(SOCIAL_COURSES).find(k=>SOCIAL_COURSES[k].formation===formation)||'general';
 }
 return {key,course:SOCIAL_COURSES[key],copy:PUBLICATION_COURSES[key]};
}
function publicationPages(project,template,d){
 if(!d?.pages)return [project.slides[project.activeSlideIndex]?.content||{}];
 return d.pages.map((page,i)=>project.slides.find(s=>s.templateId===template.id&&s.carouselPage===i)?.content||page);
}
export function publicationFacts(project,template){
 const d=SOCIAL_BY_ID[template.id],pages=publicationPages(project,template,d);
 const {copy}=courseFor(project,template,d),facts={};
 for(const field of FACT_FIELDS){
  // An explicit edit, including clearing a value, wins over an earlier slide.
  const edited=pages.find(p=>p._publicationFields?.includes(field));
  facts[field]=edited?clean(edited[field]):pages.map(factualContent).find(p=>p[field])?.[field]||copy.defaults?.[field]||'';
 }
 return facts;
}
function frenchDate(value){
 const raw=clean(value);
 if(!/^\d{4}-\d{2}-\d{2}$/.test(raw))return raw;
 const date=new Date(raw+'T12:00:00Z');
 if(!Number.isFinite(date.getTime())||date.toISOString().slice(0,10)!==raw)return raw;
 return new Intl.DateTimeFormat('fr-FR',{day:'numeric',month:'long',year:'numeric',timeZone:'UTC'}).format(date);
}
function priceLabel(value){
 const raw=clean(value),number=raw.replace(/[\s\u00a0\u202f]/g,'').replace(',','.');
 if(!/^\d+(?:\.\d{1,2})?$/.test(number))return raw;
 return new Intl.NumberFormat('fr-FR',{minimumFractionDigits:Number.isInteger(Number(number))?0:2,maximumFractionDigits:2}).format(Number(number)).replace(/[\u00a0\u202f]/g,' ')+' €';
}
function scheduleLines(content,course,{upcoming=false,vae=false}={}){
 const start=frenchDate(content.startDate),end=frenchDate(content.endDate);
 const dates=start&&end?'du '+start+' au '+end:start?'à partir du '+start:content.date||'';
 const label=vae?'Parcours DESP VAE':(upcoming?'Prochaine session ':'Session ')+course.label;
 return [dates?'📅 '+label+' : '+dates:'',content.location?'📍 '+content.location:'',
  content.examDate?(vae?'📝 Jury le ':'📝 Examen le ')+frenchDate(content.examDate):'',
  content.availability?'⏳ '+content.availability:''].filter(Boolean).join('\n');
}
function practicalLines(content){
 return [content.duration?'⏱️ Durée : '+content.duration:'',content.price?'💶 Tarif : '+priceLabel(content.price):'',
  content.financing?'💡 Financement : '+content.financing:''].filter(Boolean).join('\n');
}
function changedCopy(content,defaults,keys=['title','introduction']){
 return keys.filter(key=>clean(content[key])!==clean(defaults[key])).map(key=>clean(content[key])).filter(Boolean).join('\n\n');
}
function finishPublication(body,action,course,copy,network){
 const tags=[...new Set([...(copy.hashtags||course.hashtags).split(/\s+/),'#IntegraleAcademy',...(network==='instagram'?['#FormationProfessionnelle']:[])])];
 const url=course.formation==='A3P'?WEBSITE+'/securiteprivee':WEBSITE;
 return paragraphs([body,action||PUBLICATION_ACTIONS[network], '👉 Informations et inscriptions sur '+url,tags.join(' ')]);
}
export function publicationText(project,template,network='facebook'){
 if(!PUBLICATION_ACTIONS[network])network='facebook';
 const c=project.slides[project.activeSlideIndex]?.content||{},d=SOCIAL_BY_ID[template.id],seasonal=SEASONAL_DESIGNS.find(x=>x.id===template.id);
 const {key,course,copy}=courseFor(project,template,d),index=d?.index??stableIndex(template.id);
 const customCta=c._publicationFields?.includes('cta')&&clean(c.cta)&&c.cta!=='Faites le premier pas vers votre futur métier';
 const facts=publicationFacts(project,template),schedule=scheduleLines(facts,course,{upcoming:Boolean(d?.kind),vae:key==='desp_vae'});
 const practical=practicalLines(facts),program='🎓 '+copy.program,hook=copy.emoji+' '+copy.hook;
 let body,action=key.startsWith('bts_')?'Échangez avec notre équipe pour découvrir le parcours et préparer votre candidature en '+course.label+'.':copy.action;
 if(d?.pages){
  const pages=publicationPages(project,template,d);
  const titleChanged=clean(pages[0].title)!==clean(d.pages[0].title);
  const introChanged=clean(pages[0].introduction)!==clean(d.pages[0].introduction);
  const lead=introChanged?pages[0].introduction:copy.angles[index];
  const editedPoints=pages.slice(1,4).map((p,i)=>changedCopy(p,d.pages[i+1])).filter(Boolean);
  const points=network==='linkedin'||key==='bts_all'
   ?'Dans ce carrousel :\n'+pages.slice(1,4).map((p,i)=>'• '+clean(p.title)+(key==='bts_all'||clean(p.introduction)!==clean(d.pages[i+1].introduction)?'\n'+clean(p.introduction):'')).join('\n')
   :paragraphs(editedPoints);
  body=paragraphs([titleChanged?copy.emoji+' '+clean(pages[0].title):hook,lead,schedule,
   program,points,network==='instagram'?'Faites défiler pour découvrir le parcours.':'',
   changedCopy(pages[4],d.pages[4]),practical]);
 }else if(d?.kind){
  body=paragraphs([hook,changedCopy(c,d)||SESSION_INTROS[index],
   d.kind==='places'?'⏳ Vous souhaitez rejoindre la session ? Vérifiez les dernières disponibilités auprès de notre équipe.':'',
   schedule,program,practical]);
 }else if(d?.network){
  body=paragraphs(['✨ '+clean(c.title),COVER_PUBLICATIONS[index],changedCopy(c,socialDefaultContent(template),['introduction']),program]);
 }else if(seasonal&&!c._manual){
  return seasonal.socialCopy[network==='instagram'?'instagram':'facebook'];
 }else{
  const defaults=template.contentDefaults||defaultContentForFormation(project.formation);
  const titleChanged=Boolean(c._manual||c._publicationFields?.includes('title'))&&clean(c.title)!==clean(defaults.title);
  const introChanged=clean(c.introduction)!==clean(defaults.introduction);
  const lead=introChanged?clean(c.introduction):PUBLICATION_TOPICS[template.id]||clean(c.introduction)||copy.angles[index];
  body=paragraphs([titleChanged?copy.emoji+' '+clean(c.title):key==='general'?'✨ '+clean(c.title||copy.hook):hook,lead,schedule,program,practical]);
 }
 // Keep practical facts on every network; vary the invitation without adding
 // a second web CTA or asking candidates to send a private message.
 if(network==='instagram')action=key==='desp_vae'?copy.action:'Parlons de votre projet et préparons votre '+(key.startsWith('bts_')?'candidature.':'inscription.');
 if(network==='linkedin')action=paragraphs([action,'Programme et modalités du parcours à retrouver sur notre site.']);
 if(customCta)action=clean(c.cta);
 return finishPublication(body,action,course,copy,network);
}
export function publicationKey(template,network){return `${template.id}:${network}`}
export function renderPublicationPanel(project,template,network='facebook'){
 const value=project.publications?.[publicationKey(template,network)]??publicationText(project,template,network);
 return `${template.isCover&&template.network==='facebook'?'<div class="studio-publication-actions"><button type="button" data-action="previewFacebook">Aperçu Facebook mobile</button></div>':''}<section class="studio-publication" aria-labelledby="publicationTitle"><div class="studio-publication-heading"><span>✎</span><h3 id="publicationTitle">Texte de publication</h3></div><p>${template.isCarousel?'Le texte accompagne le carrousel complet.':'Votre publication, prête à personnaliser et à copier.'}</p><label>Réseau social<select id="publicationNetwork">${[['facebook','Facebook'],['instagram','Instagram'],['linkedin','LinkedIn']].map(([id,label])=>`<option value="${id}" ${id===network?'selected':''}>${label}</option>`).join('')}</select></label><div class="studio-publication-actions"><button type="button" class="social-studio__primary" data-action="copyPublication">Copier le texte complet</button><button type="button" data-action="resetPublication">Actualiser depuis le visuel</button><button type="button" data-action="publicationData">Dates, durée et tarif</button></div><label class="studio-publication-label" for="publicationText">Texte, emojis et hashtags</label><textarea id="publicationText" spellcheck="true" rows="13">${e(value)}</textarea><small>Vos retouches sont enregistrées avec le projet. « Actualiser » régénère le texte à partir du visuel.</small></section>`;
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
