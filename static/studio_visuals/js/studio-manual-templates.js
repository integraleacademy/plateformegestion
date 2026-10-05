import {EXPANDED_MANUAL_LAYOUTS,renderExpandedManualBody} from './studio-expanded-templates.js';
// Illustrations are local, optimised assets. Text always remains editable.
const esc = value => String(value ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
export const MANUAL_LAYOUTS = ['cover','session','immersion','skills','path','duo',...EXPANDED_MANUAL_LAYOUTS];

export function renderManualTemplateBody({template, slide, renderMode}) {
  if(EXPANDED_MANUAL_LAYOUTS.includes(template.manualLayout))return renderExpandedManualBody({template,slide,renderMode});
  const c = {...template.contentDefaults, ...slide.content};
  const layout = template.manualLayout;
  if (!MANUAL_LAYOUTS.includes(layout)) throw new Error('Composition illustrée inconnue : '+layout);
  const field = (key, tag='span', fit='meta') => `<${tag} class="mi-${key}" data-content-key="${key}" data-fit="${fit}">${esc(c[key])}</${tag}>`;
  const title = () => field('title','h1','title');
  const intro = () => field('introduction','p','body');
  const eyebrow = () => field('eyebrow','span','badge');
  const action = () => `<div class="mi-action">${field('cta','span','cta')}<b aria-hidden="true">↗</b></div>`;
  const picture = (secondary=false) => {
    const asset = secondary ? template.secondaryIllustration : template.illustration;
    return `<figure class="mi-picture${secondary?' mi-picture-secondary':''}" data-element-name="Illustration ${secondary?'complémentaire':'principale'}"><img src="/static/studio_visuals/img/manuals/${esc(asset.file)}" alt="${esc(asset.alt)}" width="${asset.width||1536}" height="${asset.height||1024}" ${renderMode==='thumbnail'?'loading="lazy"':''} decoding="async" crossorigin="anonymous" style="object-position:${esc(asset.position||'50% 50%')}"></figure>`;
  };
  const header = () => `<header class="mi-heading">${eyebrow()}${title()}</header>`;
  const ending = () => `<div class="mi-ending">${intro()}${action()}</div>`;
  const steps = () => `<ol class="mi-steps">${(c.steps||[]).slice(0,3).map((item,i)=>`<li><b class="mi-number" aria-hidden="true">0${i+1}</b><div><strong data-content-key="steps.${i}.title" data-fit="meta">${esc(item.title)}</strong><span data-content-key="steps.${i}.text" data-fit="meta">${esc(item.text)}</span></div></li>`).join('')}</ol>`;
  const bodies = {
    cover: () => `${header()}${picture()}${ending()}`,
    session: () => `<section class="mi-copy">${eyebrow()}${title()}${intro()}<div class="mi-date"><small>PROCHAINE SESSION</small>${field('startDate','time')}</div>${action()}</section>${picture()}`,
    immersion: () => `${picture()}<section class="mi-caption">${eyebrow()}${title()}${intro()}${action()}</section>`,
    skills: () => `${header()}<div class="mi-skill-grid">${picture()}${steps()}</div>${ending()}`,
    path: () => `<div class="mi-path-top"><section class="mi-copy">${eyebrow()}${title()}${intro()}</section>${picture()}</div>${steps()}${action()}`,
    duo: () => `<div class="mi-diptych">${picture()}${picture(true)}</div>${header()}${ending()}`
  };
  return `<main class="mi mi-${layout}" data-manual-layout="${layout}">${bodies[layout]()}</main>`;
}
