function esc(value){return String(value??'').replace(/[&<>"']/g,char=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[char]))}
function val(content,key,fallback=''){return content?.[key]||content?.data?.[key]||content?.dates?.[key]||fallback}
function list(value,fallback=[]){return Array.isArray(value)&&value.length?value:fallback}
function edit(key,value,tag='span',className=''){
  const fit=key==='title'?'title':key==='cta'?'cta':['introduction','quote','question','explanation'].includes(key)?'body':'';
  return `<${tag} class="studio-editable-text ${className}" data-content-key="${key}" data-layout-role="new-${key}" data-element-name="${key}"${fit?` data-fit="${fit}"`:''}>${esc(value)}</${tag}>`;
}
function contentStats(content){return list(content.stats,[{label:'Durée',value:val(content,'duration','175 h')},{label:'Lieu',value:val(content,'location','Puget-sur-Argens')},{label:'Financement',value:val(content,'financing','CPF')},{label:'Certification',value:val(content,'highlightedText','APS')}])}
function contentSteps(content){return list(content.steps,[{title:'Choisir',text:'Trouvez votre formation'},{title:'Financer',text:'Montez votre dossier'},{title:'Se former',text:'Passez à la pratique'},{title:'Réussir',text:'Lancez votre métier'}])}
function contentModules(content){return list(content.modules,[{title:'Fondamentaux',duration:'01'},{title:'Techniques métier',duration:'02'},{title:'Mises en situation',duration:'03'},{title:'Préparation examen',duration:'04'}])}
function statCards(content,prefix='new-stat',limit=4){return contentStats(content).slice(0,limit).map((item,index)=>`<section data-layout-role="${prefix}-${index}"><small>${esc(item.label)}</small><strong>${esc(item.value)}</strong></section>`).join('')}
function stepCards(content,prefix='new-step',limit=4){return contentSteps(content).slice(0,limit).map((item,index)=>`<li data-layout-role="${prefix}-${index}"><b>${String(index+1).padStart(2,'0')}</b><span>${esc(item.title||item)}</span><small>${esc(item.text||'')}</small></li>`).join('')}
function moduleCards(content,prefix='new-module',limit=6){return contentModules(content).slice(0,limit).map((item,index)=>`<section data-layout-role="${prefix}-${index}"><b>${esc(item.duration||String(index+1).padStart(2,'0'))}</b><strong>${esc(item.title||item)}</strong></section>`).join('')}

export const NEW_TEMPLATE_IDS=[
  'new_manifesto_highlight','new_editorial_arch','new_split_signal','new_vertical_wordmark','new_quote_window','new_focus_stripe','new_typo_crop','new_center_orbit','new_dark_beam','new_soft_stack',
  'new_date_portal','new_calendar_strip','new_ticket_cut','new_countdown_flip','new_date_podium','new_route_launch','new_session_board','new_date_window','new_time_capsule','new_schedule_wave',
  'new_bento_benefits','new_module_mosaic','new_steps_snake','new_program_tabs','new_skill_radar','new_pathway_cards','new_checklist_big','new_acronym_grid','new_process_columns','new_learning_map',
  'new_number_monolith','new_dashboard_glass','new_proof_rings','new_metric_tower','new_success_stamp','new_barcode_stats','new_review_quote','new_result_spectrum','new_data_wave','new_badge_wall',
  'new_cta_launchpad','new_application_card','new_last_places','new_phone_mockup','new_arrow_story','new_contact_poster','new_enroll_steps','new_final_door','new_question_hook','new_future_card'
];

export function renderNewTemplateBody(ctx){
  const id=ctx.template.id,content=ctx.slide.content||{};
  const title=edit('title',content.title||'Votre futur métier commence ici','h1','new-title');
  const intro=edit('introduction',content.introduction||'Une formation concrète, moderne et tournée vers votre réussite.','p','new-intro');
  const highlight=edit('highlightedText',content.highlightedText||ctx.project.formation,'mark','new-highlight');
  const cta=edit('cta',val(content,'cta','Candidater maintenant'),'span','new-cta-label');
  const date=edit('startDate',val(content,'startDate',val(content,'date','Prochaine session')),'time','new-date');
  const location=edit('location',val(content,'location','Puget-sur-Argens'),'span','new-location');
  const places=edit('availability',val(content,'availability','Places limitées'),'strong','new-places');
  const quote=edit('quote',content.quote||'Faites le premier pas vers votre futur métier','blockquote','new-quote');
  const first=contentStats(content)[0],second=contentStats(content)[1]||first;
  const bodies={
    new_manifesto_highlight:`<main class="new-design new-manifesto" data-layout-role="new-manifesto-highlight"><span class="new-kicker">INTÉGRALE ACADEMY</span>${title}<div class="new-highlight-line">${highlight}</div>${intro}<button>${cta}<b>→</b></button></main>`,
    new_editorial_arch:`<main class="new-design new-arch" data-layout-role="new-editorial-arch"><i class="new-arch-shape"></i><span class="new-index">01 / FUTUR</span>${title}${intro}<aside>${date}${location}</aside></main>`,
    new_split_signal:`<main class="new-design new-signal" data-layout-role="new-split-signal"><section>${title}${highlight}${intro}</section><aside>${statCards(content,'new-signal-stat',3)}<button>${cta}</button></aside></main>`,
    new_vertical_wordmark:`<main class="new-design new-wordmark" data-layout-role="new-vertical-wordmark"><b class="new-vertical-acronym">${esc(content.highlightedText||ctx.project.formation)}</b><section>${title}${intro}<div>${date}${places}</div></section></main>`,
    new_quote_window:`<main class="new-design new-quote-window" data-layout-role="new-quote-window"><span class="new-quote-mark">“</span>${quote}<footer>${highlight}<cite>INTÉGRALE ACADEMY</cite></footer></main>`,
    new_focus_stripe:`<main class="new-design new-stripe" data-layout-role="new-focus-stripe"><i></i><span class="new-kicker">FORMATION PROFESSIONNELLE</span>${title}<div>${highlight}</div>${intro}</main>`,
    new_typo_crop:`<main class="new-design new-crop" data-layout-role="new-typo-crop"><b class="new-crop-word">${esc(content.highlightedText||ctx.project.formation)}</b><section>${title}${intro}<button>${cta}</button></section></main>`,
    new_center_orbit:`<main class="new-design new-orbit-card" data-layout-role="new-center-orbit"><div class="new-orbit-ring"></div><section>${highlight}${title}${intro}</section><span>${date}</span><em>${places}</em></main>`,
    new_dark_beam:`<main class="new-design new-beam" data-layout-role="new-dark-beam"><i class="new-beam-light"></i>${highlight}${title}${intro}<button>${cta}</button></main>`,
    new_soft_stack:`<main class="new-design new-stack" data-layout-role="new-soft-stack"><section>${title}</section><section>${intro}</section><section>${date}${location}${places}</section></main>`,

    new_date_portal:`<main class="new-design new-date-portal" data-layout-role="new-date-portal"><section>${date}<span>OUVERTURE</span></section><aside>${title}${location}<button>${cta}</button></aside></main>`,
    new_calendar_strip:`<main class="new-design new-calendar-strip" data-layout-role="new-calendar-strip"><header>${title}${places}</header><div>${Array.from({length:7},(_,i)=>`<span data-layout-role="new-calendar-day-${i}"><b>${i+9}</b><small>${['LUN','MAR','MER','JEU','VEN','SAM','DIM'][i]}</small></span>`).join('')}</div><footer>${date}${location}</footer></main>`,
    new_ticket_cut:`<main class="new-design new-ticket-cut" data-layout-role="new-ticket-cut"><section><small>VOTRE PASS FORMATION</small>${title}${intro}</section><i></i><aside>${date}${location}${places}<button>${cta}</button></aside></main>`,
    new_countdown_flip:`<main class="new-design new-flip" data-layout-role="new-countdown-flip"><span>INSCRIPTIONS</span><div><b>J</b><strong>${esc(val(content,'daysRemaining','12'))}</strong></div>${title}${places}</main>`,
    new_date_podium:`<main class="new-design new-podium" data-layout-role="new-date-podium"><header>${title}</header><div><section><small>DÉBUT</small>${date}</section><section><small>LIEU</small>${location}</section><section><small>PLACES</small>${places}</section></div></main>`,
    new_route_launch:`<main class="new-design new-route-launch" data-layout-role="new-route-launch">${title}<svg viewBox="0 0 720 310"><path d="M30 255 C170 30 270 300 420 110 S610 70 690 215"/></svg><ol>${stepCards(content,'new-route-point')}</ol></main>`,
    new_session_board:`<main class="new-design new-session-board" data-layout-role="new-session-board"><aside><span>SESSION</span>${date}</aside><section>${highlight}${title}${intro}</section><footer>${location}${places}</footer></main>`,
    new_date_window:`<main class="new-design new-date-window" data-layout-role="new-date-window"><div class="new-window-bar"><i></i><i></i><i></i></div><section>${title}${intro}</section><aside>${date}<small>À VOS AGENDAS</small></aside></main>`,
    new_time_capsule:`<main class="new-design new-capsule" data-layout-role="new-time-capsule"><div>${date}<span>${location}</span></div><section>${title}${places}<button>${cta}</button></section></main>`,
    new_schedule_wave:`<main class="new-design new-schedule-wave" data-layout-role="new-schedule-wave"><i class="new-wave"></i>${title}<ol>${stepCards(content,'new-wave-step')}</ol><footer>${date}${location}</footer></main>`,

    new_bento_benefits:`<main class="new-design new-bento" data-layout-role="new-bento-benefits"><header>${title}${intro}</header><div>${statCards(content,'new-bento-card',4)}</div></main>`,
    new_module_mosaic:`<main class="new-design new-mosaic" data-layout-role="new-module-mosaic">${title}<div>${moduleCards(content,'new-mosaic-module',6)}</div></main>`,
    new_steps_snake:`<main class="new-design new-snake" data-layout-role="new-steps-snake">${title}<ol>${stepCards(content,'new-snake-step')}</ol></main>`,
    new_program_tabs:`<main class="new-design new-tabs" data-layout-role="new-program-tabs"><aside>${contentModules(content).slice(0,4).map((item,index)=>`<button data-layout-role="new-tab-${index}">${String(index+1).padStart(2,'0')}</button>`).join('')}</aside><section>${title}${moduleCards(content,'new-tab-panel',4)}</section></main>`,
    new_skill_radar:`<main class="new-design new-radar" data-layout-role="new-skill-radar"><section><i></i><i></i><i></i><strong>${esc(content.highlightedText||ctx.project.formation)}</strong></section><aside>${title}${moduleCards(content,'new-radar-skill',4)}</aside></main>`,
    new_pathway_cards:`<main class="new-design new-pathway" data-layout-role="new-pathway-cards"><header>${title}</header><div>${stepCards(content,'new-pathway-card')}</div><footer>${intro}</footer></main>`,
    new_checklist_big:`<main class="new-design new-checklist" data-layout-role="new-checklist-big"><section>${title}${intro}</section><ul>${contentModules(content).slice(0,5).map((item,index)=>`<li data-layout-role="new-check-${index}"><b>✓</b><span>${esc(item.title||item)}</span></li>`).join('')}</ul></main>`,
    new_acronym_grid:`<main class="new-design new-acronym-grid" data-layout-role="new-acronym-grid"><b>${esc(content.highlightedText||ctx.project.formation)}</b><section>${moduleCards(content,'new-acronym-module',4)}</section><footer>${title}</footer></main>`,
    new_process_columns:`<main class="new-design new-process-columns" data-layout-role="new-process-columns">${title}<div>${stepCards(content,'new-process-column')}</div></main>`,
    new_learning_map:`<main class="new-design new-learning-map" data-layout-role="new-learning-map"><header>${title}${intro}</header><div>${contentSteps(content).slice(0,4).map((item,index)=>`<section data-layout-role="new-map-node-${index}"><b>${index+1}</b><strong>${esc(item.title||item)}</strong></section>`).join('')}</div></main>`,

    new_number_monolith:`<main class="new-design new-monolith" data-layout-role="new-number-monolith"><section><strong>${esc(first.value)}</strong><small>${esc(first.label)}</small></section><aside>${title}${intro}</aside></main>`,
    new_dashboard_glass:`<main class="new-design new-glass" data-layout-role="new-dashboard-glass"><header>${title}<span>LIVE</span></header><div>${statCards(content,'new-glass-stat',4)}</div></main>`,
    new_proof_rings:`<main class="new-design new-proof-rings" data-layout-role="new-proof-rings"><section><i></i><strong>${esc(first.value)}</strong><small>${esc(first.label)}</small></section><aside>${title}${statCards(content,'new-ring-stat',3)}</aside></main>`,
    new_metric_tower:`<main class="new-design new-tower" data-layout-role="new-metric-tower"><aside>${title}</aside><div>${contentStats(content).slice(0,4).map((item,index)=>`<section data-layout-role="new-tower-stat-${index}" style="--level:${index+1}"><b>${esc(item.value)}</b><span>${esc(item.label)}</span></section>`).join('')}</div></main>`,
    new_success_stamp:`<main class="new-design new-success-stamp" data-layout-role="new-success-stamp"><div><span>RÉSULTAT</span><strong>${esc(first.value)}</strong><small>${esc(first.label)}</small></div>${title}${intro}</main>`,
    new_barcode_stats:`<main class="new-design new-barcode" data-layout-role="new-barcode-stats"><header>${title}</header><div>${contentStats(content).slice(0,4).map((item,index)=>`<section data-layout-role="new-bar-${index}"><i style="--bar:${45+index*15}%"></i><strong>${esc(item.value)}</strong><small>${esc(item.label)}</small></section>`).join('')}</div></main>`,
    new_review_quote:`<main class="new-design new-review" data-layout-role="new-review-quote"><span>★★★★★</span>${quote}<footer><b>${esc(first.value)}</b><small>${esc(first.label)}</small></footer></main>`,
    new_result_spectrum:`<main class="new-design new-spectrum" data-layout-role="new-result-spectrum"><i></i>${title}<div>${statCards(content,'new-spectrum-stat',4)}</div></main>`,
    new_data_wave:`<main class="new-design new-data-wave" data-layout-role="new-data-wave"><header>${title}${intro}</header><svg viewBox="0 0 720 220"><path d="M0 180 C110 190 120 55 240 95 S360 185 470 65 S610 95 720 18"/></svg><footer><strong>${esc(first.value)}</strong><span>${esc(first.label)}</span><b>${esc(second.value)}</b></footer></main>`,
    new_badge_wall:`<main class="new-design new-badge-wall" data-layout-role="new-badge-wall"><section>${title}</section><div>${contentStats(content).slice(0,5).map((item,index)=>`<span data-layout-role="new-badge-${index}"><b>${esc(item.value)}</b>${esc(item.label)}</span>`).join('')}</div></main>`,

    new_cta_launchpad:`<main class="new-design new-launchpad" data-layout-role="new-cta-launchpad"><i></i>${highlight}${title}${intro}<button>${cta}<b>↗</b></button></main>`,
    new_application_card:`<main class="new-design new-application" data-layout-role="new-application-card"><section><small>VOTRE CANDIDATURE</small>${title}${intro}<button>${cta}</button></section><aside>${date}${location}${places}</aside></main>`,
    new_last_places:`<main class="new-design new-last-places" data-layout-role="new-last-places"><span>DERNIÈRES</span>${places}${title}<button>${cta}</button></main>`,
    new_phone_mockup:`<main class="new-design new-phone" data-layout-role="new-phone-mockup"><div class="new-device"><span>INTÉGRALE</span>${highlight}<button>${cta}</button></div><section>${title}${intro}${date}</section></main>`,
    new_arrow_story:`<main class="new-design new-arrow-story" data-layout-role="new-arrow-story"><span class="new-arrow">↘</span>${title}<div>${intro}${places}</div><button>${cta}</button></main>`,
    new_contact_poster:`<main class="new-design new-contact" data-layout-role="new-contact-poster"><header>${highlight}<span>UNE QUESTION ?</span></header>${title}<section><strong>04 22 47 07 68</strong><small>integraleacademy.com</small></section></main>`,
    new_enroll_steps:`<main class="new-design new-enroll" data-layout-role="new-enroll-steps"><header>${title}</header><ol>${stepCards(content,'new-enroll-step',3)}</ol><button>${cta}</button></main>`,
    new_final_door:`<main class="new-design new-door" data-layout-role="new-final-door"><div><i></i><span>ENTREZ</span></div><section>${title}${intro}<button>${cta}</button></section></main>`,
    new_question_hook:`<main class="new-design new-hook" data-layout-role="new-question-hook"><span>?</span>${edit('question',val(content,'question','Prêt à changer de métier ?'),'h1','new-title')}${intro}<button>${cta}</button></main>`,
    new_future_card:`<main class="new-design new-future" data-layout-role="new-future-card"><span>VOTRE PROCHAINE ÉTAPE</span>${title}<div>${date}${location}</div><button>${cta}<b>→</b></button></main>`
  };
  return bodies[id]||bodies.new_manifesto_highlight;
}
