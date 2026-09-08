import {SOCIAL_BY_ID} from './studio-social-content.js';
export const escapeSocial=value=>String(value??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const e=escapeSocial;
const paths={
 route:'M12 75h27q13 0 13-14V35q0-13 14-13h18m-13-12 13 12-13 12 M12 65a10 10 0 1 0 0 20 10 10 0 0 0 0-20',
 monitor:'M10 15h76v48H10z M35 84h26 M48 63v21 M20 26h23v25H20z M53 26h22v9H53z M53 43h22v8H53z',
 dashboard:'M12 13h72v71H12z M12 34h72 M24 73V60m16 13V48m16 25V55m16 18V43',
 folder:'M8 28V15h31l10 13h39v56H8z M29 49h39 M29 64h28',
 fire:'M9 13h78v71H9z M18 24h35v20H18z M66 28h9 M66 40h9 M25 54v19 M37 54v19 M53 73c-14-10 9-12 3-24 28 18 25 27 9 28',
 car:'M12 49 23 24h50l12 25v29H12z M12 49h73 M24 24l-3 25 M72 24l4 25 M21 61h12 M65 61h11 M21 78v8 M75 78v8',
 home:'M9 42 48 11 87 42 M20 35v51h56V35 M38 86V59h20v27 M30 45h6 M61 45h6',
 shop:'M12 38h72v47H12z M8 38l9-25h63l8 25 M32 13v25 M64 13v25 M24 85V59h23v26 M59 57h14v14H59z',
 chat:'M11 13h74v51H51L27 84V64H11z M26 30h45 M26 44h31',
 globe:'M48 11a37 37 0 1 0 0 74 37 37 0 0 0 0-74 M11 48h74 M48 11c-23 18-23 57 0 74 M48 11c23 18 23 57 0 74 M20 25q28 22 56 0 M20 71q28-22 56 0',
 ledger:'M16 10h64v76H16z M28 24h40 M28 38h40 M28 52h40 M28 66h40 M48 24v52',
 portal:'M17 84V39a31 31 0 0 1 62 0v45 M33 84V42a15 15 0 0 1 30 0v42 M10 84h76 M43 58l10-10-10-10'
};
const glyph=(art,x,y,size,color='var(--social-accent)')=>`<g transform="translate(${x} ${y}) scale(${size/96})" stroke="${color}" stroke-width="4" stroke-linecap="round" stroke-linejoin="round" fill="none"><path d="${paths[art]||paths.portal}"/></g>`;
const rect=(x,y,w,h,fill,rx=24)=>`<rect x="${x}" y="${y}" width="${w}" height="${h}" rx="${rx}" fill="${fill}"/>`;
export function renderSocialIllustration(art='portal',variant=0){
 const a='var(--social-accent)',s='var(--social-tint)',l='var(--social-line)';let shapes='';
 if(variant%5===0)shapes=rect(18,22,464,312,'#fff',30)+rect(18,22,464,48,s,30)+[44,62,80].map(x=>`<circle cx="${x}" cy="46" r="5" fill="${a}"/>`).join('')+rect(42,91,234,217,s)+glyph(art,80,120,156)+rect(295,92,164,82,a)+glyph('portal',350,106,55,'#fff')+[205,243,281].map((y,i)=>rect(297,y,159-i*25,13,l,6)).join('');
 if(variant%5===1)shapes=`<circle cx="250" cy="176" r="155" fill="${s}"/><circle cx="250" cy="176" r="119" fill="#fff"/>`+glyph(art,165,90,172)+rect(32,254,144,74,a,22)+glyph('portal',81,264,51,'#fff')+rect(363,27,110,99,'#fff')+glyph(art,388,46,65);
 if(variant%5===2)shapes=rect(22,23,274,312,'#fff')+rect(43,44,232,220,s)+glyph(art,87,84,143)+rect(48,285,206,14,l,7)+rect(316,23,163,143,a)+glyph(art,354,52,86,'#fff')+rect(316,185,163,150,'#fff')+glyph('portal',354,215,86);
 if(variant%5===3)shapes=`<path d="M60 281C116 17 378 11 442 276" fill="none" stroke="${a}" opacity=".45" stroke-width="3" stroke-dasharray="8 12"/>`+rect(130,65,240,230,'#fff',38)+glyph(art,178,105,146)+rect(15,232,133,102,s)+glyph('folder',46,251,63)+rect(359,232,128,102,a)+glyph('portal',389,251,64,'#fff');
 if(variant%5===4)shapes=`<ellipse cx="250" cy="180" rx="211" ry="132" fill="none" stroke="${l}" stroke-width="4" transform="rotate(-20 250 180)"/><ellipse cx="250" cy="180" rx="178" ry="122" fill="${s}" transform="rotate(20 250 180)"/>`+rect(149,71,202,216,'#fff',36)+glyph(art,176,105,147)+rect(23,243,105,80,a)+glyph('portal',52,257,52,'#fff')+rect(382,29,98,85,'#fff')+glyph(art,404,45,53);
 return `<svg viewBox="0 0 500 360" xmlns="http://www.w3.org/2000/svg" aria-hidden="true">${shapes}</svg>`;
}
const text=(key,value,tag,cls,fit)=>`<${tag} class="${cls}" data-content-key="${key}" data-fit="${fit||key}">${e(value)}</${tag}>`;
export function socialDefaultContent(template,pageIndex=0){
 const d=SOCIAL_BY_ID[template.id];if(!d)return template.contentDefaults||{};
 const page=d.pages?.[pageIndex]||d;
 return {title:page.title,introduction:page.introduction,eyebrow:page.eyebrow||'✨ INTÉGRALE ACADEMY',cta:page.cta||(d.kind==='places'?'Vérifier les disponibilités':'Préparer mon inscription'),location:'Puget-sur-Argens',duration:'',financing:'',availability:'',date:'',startDate:'',endDate:'',examDate:'',_manual:false};
}
export function renderSocialTemplateBody({slide,template}){
 const d=SOCIAL_BY_ID[template.id];if(!d)throw new Error(`Modèle social absent : ${template.id}`);
 const page=Math.max(0,Math.min(4,Number(slide.carouselPage)||0)),c={...socialDefaultContent(template,page),...slide.content};
 const title=text('title',c.title,'h1','social-title','title'),intro=text('introduction',c.introduction,'p','social-intro','body');
 const kicker=text('eyebrow',c.eyebrow,'p','social-kicker','badge');
 const cta=`<div class="social-action">${text('cta',c.cta,'span','social-cta','cta')}<b aria-hidden="true">↗</b></div>`;
 const art=`<figure class="social-art" data-studio-decorative="true"><div ${template.motion?'data-motion="float"':''}>${renderSocialIllustration(d.course?.art||'portal',d.index+(d.pages?page:0))}</div></figure>`;
 const tags=`<div class="social-tags">${(d.course?.tags||['Sécurité','Mobilité','BTS']).map(t=>`<span>${e(t)}</span>`).join('')}</div>`;
 const details=template.isSession?`<div class="social-session-details">${[['startDate','📅'],['endDate','→'],['date','📅'],['availability','⏳']].filter(([key])=>c[key]).map(([key,icon])=>`<span>${icon} ${text(key,c[key],'b','social-session-value','meta')}</span>`).join('')}</div>`:'';
 const progress=d.pages?`<div class="social-progress" aria-label="Diapositive ${page+1}">${d.pages.map((_,i)=>`<i class="${i===page?'active':''}"></i>`).join('')}</div>`:'';
 const type=d.pages?.[page]?.kind||'announcement';
 return `<main class="social-main social-layout-${d.layout} social-page-${type}" data-layout-role="social-${d.layout}-${type}"><section class="social-copy">${kicker}${title}${intro}${details}${cta}</section>${art}${tags}${progress}</main>`;
}
export function renderSocialCoverBody({slide,template}){
 const d=SOCIAL_BY_ID[template.id],c={...socialDefaultContent(template),...slide.content};
 return `<main class="social-cover-main" data-layout-role="cover-${d.layout}">${text('title',c.title,'h1','social-cover-title','title')}${text('introduction',c.introduction,'p','social-cover-intro','body')}</main><div class="social-cover-art social-cover-art-${d.layout}" data-studio-decorative="true">${renderSocialIllustration('portal',d.index)}</div>`;
}
