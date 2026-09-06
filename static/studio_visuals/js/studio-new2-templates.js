const esc=value=>String(value??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const value=(c,key,fallback='')=>c[key]||c.data?.[key]||c.dates?.[key]||fallback;
function text(key,value,tag='span',className=''){
  const fit=key==='title'?'title':key==='cta'?'cta':key==='introduction'?'body':'meta';
  return `<${tag} class="n2-${key} ${className}" data-content-key="${key}" data-fit="${fit}" data-element-name="${key}">${esc(value)}</${tag}>`;
}
function art(className,body,motion=''){
  return `<div class="n2-art ${className}" aria-hidden="true" data-studio-decorative="true"${motion?` data-motion="${motion}"`:''}>${body}</div>`;
}
const star='<svg viewBox="0 0 100 100"><path d="M50 0 60 35 85 15 65 40 100 50 65 60 85 85 60 65 50 100 40 65 15 85 35 60 0 50 35 40 15 15 40 35Z"/></svg>';
const arrow='<svg viewBox="0 0 100 100"><path d="M10 82 77 15M28 15H80V68" fill="none" stroke="currentColor" stroke-width="13"/></svg>';
export const NEW2_IDS=[
  'new2_aperture','new2_paperfold','new2_passport','new2_sticker_club','new2_conversation',
  'new2_launch_arc','new2_desktop','new2_editorial','new2_ribbon','new2_target',
  'new2_playbill','new2_polaroid','new2_compass','new2_kinetic','new2_pixel',
  'new2_neon_ticket','new2_calendar_stack','new2_portal_gradient','new2_flipbook','new2_confetti'
];

export function renderNew2TemplateBody(ctx){
  const c=ctx.slide.content||{},formation=ctx.project.formation==='OR'?'INTÉGRALE':ctx.project.formation;
  const title=text('title',c.title||'Votre avenir mérite un nouveau départ','h1');
  const intro=text('introduction',c.introduction||'Un projet, une équipe, une formation pour avancer.','p');
  const cta=`<div class="n2-action">${text('cta',value(c,'cta','Parlons de votre projet'))}<b aria-hidden="true">↗</b></div>`;
  const date=text('startDate',value(c,'startDate',value(c,'date','Prochaine session')),'time');
  const location=text('location',value(c,'location','Puget-sur-Argens'));
  const code=`<span class="n2-code" data-fit="meta">${esc(formation)}</span>`;
  const copy=`<section class="n2-copy">${title}${intro}${cta}</section>`;
  const details=`<div class="n2-details"><span>VOTRE PROCHAINE ÉTAPE</span>${date}${location}</div>`;
  const steps=(c.steps?.length?c.steps:[{title:'Échangeons sur votre projet'},{title:'Préparons votre inscription'},{title:'Entrez en formation'}]).slice(0,3);
  const stepList=`<ol class="n2-steps">${steps.map((s,i)=>`<li><b>0${i+1}</b><span data-fit="meta">${esc(s.title||s)}</span></li>`).join('')}</ol>`;
  const modules=(c.modules?.length?c.modules:[{title:'Comprendre les fondamentaux'},{title:'S’entraîner à la pratique'},{title:'Préparer son avenir'}]).slice(0,3);
  const moduleList=`<ul class="n2-modules">${modules.map(m=>`<li><b>✓</b><span data-fit="meta">${esc(m.title||m)}</span></li>`).join('')}</ul>`;
  const bodies={
    new2_aperture:`<div class="n2-overline">LE CHAMP DES POSSIBLES</div>${copy}<aside class="n2-aperture-stage">${art('n2-lens','<i></i><i></i><i></i>','orbit')}${code}<small>CHANGEZ DE PERSPECTIVE</small></aside>${details}`,
    new2_paperfold:`<header class="n2-issue">INTÉGRALE / NOUVEAU CHAPITRE <b>01</b></header>${copy}<aside class="n2-fold"><span>VOTRE<br>FUTUR</span>${art('n2-fold-arrow',arrow)}${date}</aside>${location}`,
    new2_passport:`<header class="n2-pass-heading"><span>PASS / FORMATION</span>${code}</header><section class="n2-pass-main">${title}${intro}${cta}</section><aside class="n2-pass-stub"><span>DESTINATION</span><strong>VOTRE<br>FUTUR MÉTIER</strong>${date}${art('n2-bars','<i></i>'.repeat(16))}</aside><footer class="n2-pass-bottom">INTÉGRALE ACADEMY ${location}</footer>` ,
    new2_sticker_club:`<div class="n2-sticker-stage">${art('n2-sticker n2-sticker-a','🎓','float')}${art('n2-sticker n2-sticker-b','🚀','bob')}${art('n2-sticker n2-sticker-c','✨','pulse')}<span class="n2-sticker-note">ON PASSE<br>À L’ACTION ?</span></div>${copy}${code}`,
    new2_conversation:`<section class="n2-chat-copy">${code}${title}${cta}</section><aside class="n2-chat"><div class="n2-chat-message"><span>👋</span><p>Et si on parlait de votre futur métier ?</p></div><div class="n2-chat-message"><span>💬</span><p>Une équipe vous accompagne dans votre projet.</p></div><div class="n2-chat-message"><span>📍</span>${location}</div>${art('n2-chat-dot','<i></i><i></i><i></i>','pulse')}</aside>` ,
    new2_launch_arc:`<header class="n2-overline">PRÊT POUR LA SUITE ?</header>${copy}<aside class="n2-launch-stage">${art('n2-launch-path','<svg viewBox="0 0 300 430"><path d="M20 410C280 410 35 130 260 35"/></svg>')}${art('n2-rocket','🚀','rise')}<span class="n2-launch-label">C’EST<br>VOTRE MOMENT.</span></aside>${date}`,
    new2_desktop:`<header class="n2-overline">VOTRE PROJET PREND FORME</header><section class="n2-window"><header><i></i><i></i><i></i><span>integrale / votre-avenir</span></header><div>${code}${title}${intro}${cta}</div></section><aside class="n2-widget"><b>📅</b>${date}</aside>${art('n2-pointer','↖','float')}`,
    new2_editorial:`<aside class="n2-editorial-rail"><span>FORMATION / ${esc(formation)}</span><b>ÉDITION<br>AVENIR</b></aside><section class="n2-editorial-copy"><small>LA PREMIÈRE PAGE DE LA SUITE</small>${title}<div class="n2-editorial-bottom">${intro}${cta}</div></section><footer>${date}${location}</footer>` ,
    new2_ribbon:`<aside class="n2-award-stage">${art('n2-award','<span>🏅</span>')}<div>${code}<span>LE SAVOIR<br>POUR AVANCER</span></div></aside>${copy}${details}`,
    new2_target:`<section class="n2-target-copy"><span class="n2-overline">OBJECTIF : VOTRE MÉTIER</span>${title}${intro}${cta}</section><aside class="n2-target-stage">${art('n2-target-rings','<i></i><i></i><i></i>','pulse')}${art('n2-target-arrow',arrow,'bob')}${code}</aside>${date}`,
    new2_playbill:`<header class="n2-playbill-top"><b>PLACE À<br>VOTRE AVENIR.</b>${code}</header><section class="n2-playbill-copy">${title}${intro}${cta}</section><aside class="n2-playbill-star">${art('n2-star',star)}${date}</aside>` ,
    new2_polaroid:`<aside class="n2-photo"><div>${art('n2-briefcase','💼')}<span>NOUVEL<br>HORIZON</span></div><footer>Votre prochaine aventure professionnelle.</footer></aside><section class="n2-photo-copy">${code}${title}${intro}${cta}</section>${location}`,
    new2_compass:`<header>${title}${intro}</header><aside class="n2-compass-stage">${art('n2-compass-rose','<svg viewBox="0 0 300 300"><circle cx="150" cy="150" r="133" fill="none" stroke="currentColor"/><path d="M150 8 182 118 292 150 182 182 150 292 118 182 8 150 118 118Z"/></svg>','spin')}${code}</aside><section>${stepList}${cta}</section>` ,
    new2_kinetic:`<aside class="n2-kinetic-type"><span>FAIRE</span><span>OSER</span><span>AVANCER</span>${art('n2-kinetic-star',star,'spin')}</aside><section class="n2-kinetic-copy">${code}${title}${intro}${cta}</section><footer>${date}${location}</footer>` ,
    new2_pixel:`<header class="n2-pixel-heading"><span>LEVEL UP / ${esc(formation)}</span><b>↗</b></header>${copy}<aside class="n2-pixel-stairs">${[1,2,3,4,5].map(i=>`<i style="--step:${i}"></i>`).join('')}${art('n2-pixel-trophy','🏆','bob')}</aside><footer><span>🎯 UN OBJECTIF</span><span>📚 UNE FORMATION</span><span>💼 UN AVENIR</span></footer>` ,
    new2_neon_ticket:`<header><span>LA SUITE COMMENCE ICI</span>${code}</header><section>${title}${intro}${cta}</section><aside><span class="n2-neon-word">GO.</span>${date}${location}${art('n2-neon-orbit','<i></i><i></i>','orbit')}</aside>` ,
    new2_calendar_stack:`<section class="n2-calendar-copy">${code}${title}${intro}${cta}</section><aside class="n2-calendar"><header><i></i><i></i><span>À VOS AGENDAS</span></header><div><span>📅</span>${date}</div><footer>${location}</footer></aside>` ,
    new2_portal_gradient:`<aside class="n2-portal-stage">${art('n2-portal-door','<i></i><i></i>')}${art('n2-key','🗝️','float')}<span>OUVREZ<br>LA SUITE.</span></aside>${copy}${date}`,
    new2_flipbook:`<header>${code}${title}</header><section class="n2-book"><aside><span>📚</span><strong>Apprendre.<br>Pratiquer.<br>Avancer.</strong></aside><div>${moduleList}</div></section><footer>${intro}${cta}</footer>` ,
    new2_confetti:`<header class="n2-confetti-heading"><span>LE DÉBUT D’UNE NOUVELLE HISTOIRE</span>${code}</header>${art('n2-celebrate','🎉','bob')}<section class="n2-confetti-copy">${title}${intro}${cta}</section>${art('n2-spark n2-spark-a',star,'spin')}${art('n2-spark n2-spark-b','✨','pulse')}<footer>${date}${location}</footer>`
  };
  return `<main class="n2 n2-${ctx.template.id.replace('new2_','').replaceAll('_','-')}" data-layout-role="${ctx.template.id}" data-new2-design="${ctx.template.id}">${bodies[ctx.template.id]||bodies.new2_aperture}</main>`;
}
