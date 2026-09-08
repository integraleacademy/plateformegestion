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
function infoLines(content){
 const date=content.startDate&&content.endDate?`Du ${content.startDate} au ${content.endDate}`:content.startDate?`À partir du ${content.startDate}`:content.date||'';
 return [date?`📅 ${date}`:'',content.location?`📍 ${content.location}`:'',content.availability?`⏳ ${content.availability}`:'',content.duration?`⏱️ ${content.duration}`:'',content.financing?`💡 Financement : ${content.financing}`:''].filter(Boolean);
}
export function publicationText(project,template,network='facebook'){
 const c=project.slides[project.activeSlideIndex]?.content||{},d=SOCIAL_BY_ID[template.id],seasonal=SEASONAL_DESIGNS.find(x=>x.id===template.id);
 const course=d?.course||Object.values(SOCIAL_COURSES).find(x=>x.formation===project.formation),emoji=course?.emoji||'✨';
 let body;
 if(d?.pages){
  const slides=project.slides.filter(s=>s.templateId===template.id).sort((a,b)=>(a.carouselPage||0)-(b.carouselPage||0));
  const pages=slides.length===5?slides.map(s=>s.content):d.pages;
  body=`${emoji} ${pages[0].title}\n\n${pages[0].introduction}\n\n${pages.slice(1,4).map(p=>`✨ ${p.title}\n${p.introduction}`).join('\n\n')}\n\n🎯 ${pages[4].introduction}`;
  if(d.key==='desp_vae')body+='\nLa décision de validation appartient au jury.';
 }else if(d?.kind){body=`${d.kind==='places'?'⏳ DERNIÈRES PLACES':'📅 PROCHAINE SESSION'} — ${d.key==='desp_initial'?'DESP':d.course.label}\n\n${c.title}\n\n${c.introduction}\n\n${emoji} Au cœur du parcours : ${d.course.tags.join(', ').toLowerCase()}.\n\n${infoLines(c).join('\n')}\n\n🎯 ${d.kind==='places'?'Contactez notre équipe pour vérifier les disponibilités et préparer votre inscription.':'Découvrez les modalités et préparez votre inscription avec notre équipe.'}`;}
 else if(d?.network){body=`✨ ${c.title}\n\n${c.introduction}\n\n🎓 Sécurité, mobilité, management et BTS : explorez les parcours Intégrale Academy.\n\n💬 Une envie d’évolution ou de reconversion ? Préparons votre projet.`;}
 else if(seasonal&&!c._manual){return seasonal.socialCopy[network==='instagram'?'instagram':'facebook'];}
 else{body=`${emoji} ${c.title||template.name}\n\n${c.introduction||template.description||''}\n\n${infoLines(c).join('\n')}\n\n🎯 ${c.cta&&c.cta!=='Faites le premier pas vers votre futur métier'?c.cta:'Parlons de votre projet de formation'}.`;}
 const tags=course?.hashtags||'#Formation #ProjetProfessionnel';
 return `${body}\n\n👉 Découvrez nos formations et contactez notre équipe :\n${WEBSITE}${network==='instagram'?'\n🔗 Retrouvez également le lien dans notre bio.':''}\n\n#IntegraleAcademy ${tags}`.replace(/\n{3,}/g,'\n\n').trim();
}
export function publicationKey(template,network){return `${template.id}:${network}`}
export function renderPublicationPanel(project,template,network='facebook'){
 const value=project.publications?.[publicationKey(template,network)]??publicationText(project,template,network);
 return `<section class="studio-publication" aria-labelledby="publicationTitle"><div class="studio-publication-heading"><span>✎</span><h3 id="publicationTitle">Texte de publication</h3></div><p>${template.isCarousel?'Le texte accompagne le carrousel complet.':'Votre publication, prête à personnaliser et à copier.'}</p><label>Réseau social<select id="publicationNetwork">${[['facebook','Facebook'],['instagram','Instagram'],['linkedin','LinkedIn']].map(([id,label])=>`<option value="${id}" ${id===network?'selected':''}>${label}</option>`).join('')}</select></label><label class="studio-publication-label" for="publicationText">Texte, emojis et hashtags</label><textarea id="publicationText" spellcheck="true" rows="13">${e(value)}</textarea><div class="studio-publication-actions"><button type="button" class="social-studio__primary" data-action="copyPublication">Copier le texte complet</button><button type="button" data-action="resetPublication">Actualiser depuis le visuel</button></div><small>Vos retouches sont enregistrées avec le projet. « Actualiser » régénère le texte à partir du visuel.</small></section>`;
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
