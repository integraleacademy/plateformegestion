// Second illustrated collection and reusable, editable canvases.
const esc = value => String(value ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const read = (object, path) => path.split('.').reduce((value, key) => value?.[key], object);
export const EXPANDED_MANUAL_LAYOUTS = ['spotlight','editorial','storyboard','dialogue','roadmap'];
export const CANVAS_LAYOUTS = ['ticket','programme','checklist','fiche','comparatif','chronologie','objectifs','faq','chiffres','temoignage','evenement','annonce','carnet'];

function parts(template, slide, renderMode, defaults=template.contentDefaults) {
  const content = {...defaults, ...slide.content};
  const field = (key, tag='span', fit='meta', className='') => `<${tag} class="${className}" data-content-key="${key}" data-fit="${fit}">${esc(read(content,key))}</${tag}>`;
  const image = (index=0) => {
    const asset = template.illustrations?.[index] || (index ? template.secondaryIllustration : template.illustration) || template.illustration;
    if (!asset) return '';
    return `<figure class="mi-picture mx-picture" data-element-name="Illustration ${index+1}"><img src="/static/studio_visuals/img/manuals/${esc(asset.file)}" alt="${esc(asset.alt)}" width="${asset.width||1536}" height="${asset.height||1024}" ${renderMode==='thumbnail'?'loading="lazy"':''} decoding="async" crossorigin="anonymous" style="object-position:${esc(asset.position||'50% 50%')}"></figure>`;
  };
  const header = () => `<header class="mi-heading">${field('eyebrow','span','badge','mi-eyebrow')}${field('title','h1','title')}</header>`;
  const intro = () => field('introduction','p','body','mi-introduction');
  const action = () => `<div class="mi-action">${field('cta','span','cta')}<b aria-hidden="true">↗</b></div>`;
  const ending = () => `<div class="mi-ending">${intro()}${action()}</div>`;
  const steps = (limit=4, cls='') => `<ol class="mx-cards ${cls}">${(content.steps||[]).slice(0,limit).map((_,i)=>`<li><i class="mx-index" aria-hidden="true">${cls.includes('cv-checks')?'':String(i+1).padStart(2,'0')}</i><div>${field(`steps.${i}.title`,'strong')}${field(`steps.${i}.text`,'p','meta')}</div></li>`).join('')}</ol>`;
  const faq = (limit=4) => `<div class="mx-questions">${(content.faq||[]).slice(0,limit).map((_,i)=>`<section><i aria-hidden="true">?</i><div>${field(`faq.${i}.q`,'h2')}${field(`faq.${i}.a`,'p','body')}</div></section>`).join('')}</div>`;
  return {content,field,image,header,intro,action,ending,steps,faq};
}

export function renderExpandedManualBody({template,slide,renderMode}) {
  const p=parts(template,slide,renderMode), {header,intro,image,ending,action,steps,faq,field}=p;
  const layout=template.manualLayout;
  const bodies={
    spotlight:()=>`${image()}<section class="mx-spotlight-panel">${header()}${intro()}${action()}</section>`,
    editorial:()=>`${header()}<div class="mx-editorial-scene">${image()}<aside>${field('highlightedText','strong','metric','mx-large-word')}${intro()}</aside></div>${steps(3)}${action()}`,
    storyboard:()=>`${header()}<div class="mx-story-panels">${[0,1,2].map(i=>`<section>${image(i)}<div><i class="mx-index" aria-hidden="true">0${i+1}</i>${field(`steps.${i}.title`,'strong')}${field(`steps.${i}.text`,'p','meta')}</div></section>`).join('')}</div>${ending()}`,
    dialogue:()=>`${header()}<div class="mx-dialogue-scene">${image()}${faq(3)}</div>${ending()}`,
    roadmap:()=>`${header()}<div class="mx-roadmap-scene">${image()}${steps(3,'mx-route')}</div>${ending()}`
  };
  if(!bodies[layout])throw new Error('Composition illustrée inconnue : '+layout);
  return `<main class="mi mx mi-${layout}" data-layout-role="manual-${layout}" data-manual-layout="${layout}">${bodies[layout]()}</main>`;
}

export function renderCanvasTemplateBody({template,slide,renderMode}) {
  const page=template.pages?.[slide.carouselPage||0], layout=page?.layout||template.canvasLayout;
  const {content,field,image,header,intro,action,steps,faq}=parts(template,slide,renderMode,page?.contentDefaults||template.contentDefaults);
  const heading=()=>`<div class="cv-heading">${header()}${image()}</div>`;
  const foot=()=>`<div class="cv-ending">${intro()}${action()}</div>`;
  const stats=()=>`<div class="cv-stats">${(content.stats||[]).slice(0,4).map((_,i)=>`<section>${field(`stats.${i}.value`,'strong','metric')}${field(`stats.${i}.label`,'span')}</section>`).join('')}</div>`;
  const bodies={
    ticket:()=>`${header()}<div class="cv-ticket-body"><section class="cv-ticket-art">${image()}${field('startDate','strong','meta','cv-date')}</section><section class="cv-ticket-details">${intro()}<div>${field('location','strong')}${field('duration','span')}</div>${action()}</section></div>`,
    programme:()=>`${heading()}${steps(4,'cv-programme-grid')}${foot()}`,
    checklist:()=>`${header()}<div class="cv-checklist-grid">${steps(6,'cv-checks')}${image()}</div>${foot()}`,
    fiche:()=>`${heading()}<section class="cv-objective">${intro()}</section>${steps(3,'cv-method')}${action()}`,
    comparatif:()=>`${heading()}<div class="cv-comparison">${[0,1].map(col=>`<section>${field(col?'after':'before','h2')}<ul>${[0,1].map(i=>{const n=col*2+i;return `<li>${field(`steps.${n}.title`,'strong')}${field(`steps.${n}.text`,'p','body')}</li>`}).join('')}</ul></section>`).join('')}</div>${foot()}`,
    chronologie:()=>`${header()}<div class="cv-timeline-art">${image()}${intro()}</div>${steps(4,'cv-timeline')}${action()}`,
    objectifs:()=>`${header()}<div class="cv-goals">${image()}<section><div class="cv-objective">${intro()}</div>${steps(3,'cv-goal-list')}</section></div>${action()}`,
    faq:()=>`${heading()}${faq(4)}${foot()}`,
    chiffres:()=>`${heading()}${stats()}${foot()}`,
    temoignage:()=>`${header()}<div class="cv-quote-layout">${image()}<section><i aria-hidden="true">“</i>${field('quote','blockquote','body')}${field('author','cite')}</section></div>${foot()}`,
    evenement:()=>`${header()}<div class="cv-event"><section>${field('startDate','strong','title','cv-date')}${intro()}<div class="cv-event-place">${field('location','strong')}${field('duration','span')}</div>${action()}</section>${image()}</div>`,
    annonce:()=>`<div class="cv-news-art">${image()}${field('eyebrow','span','badge','mi-eyebrow')}</div><div class="cv-news-copy">${field('title','h1','title')}${intro()}${action()}</div>`,
    carnet:()=>`${heading()}${steps(4,'cv-notes')}${foot()}`
  };
  if(!bodies[layout])throw new Error('Canevas inconnu : '+layout);
  const pagination=template.isCarousel?`<small class="cv-pagination" aria-label="Diapositive ${Number(slide.carouselPage||0)+1} sur ${template.pages.length}">${Number(slide.carouselPage||0)+1} / ${template.pages.length}</small>`:'';
  return `<main class="mi cv cv-${layout}" data-layout-role="canvas-${layout}" data-canvas-layout="${layout}">${bodies[layout]()}${pagination}</main>`;
}
