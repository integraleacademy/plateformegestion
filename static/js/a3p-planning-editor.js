const sid=document.getElementById('planningEditorConfig').dataset.session;
const REQUIRED_MINUTES=328*60;
let planning=[];
let modules=[];
let trainerOptions=[];
let maxDistinctModulesPerDay=3;
let needsRegeneration=false;
let isDraft=false;
let dirty=false;
let saving=false;
let loaded=false;
let examDate=null;
let serverErrors=[];
let undoStack=[];
let duplicateDayIndex=null;
let editedSlot=null;

const $=id=>document.getElementById(id);
const esc=value=>String(value??'').replaceAll('&','&amp;').replaceAll('<','&lt;').replaceAll('>','&gt;').replaceAll('"','&quot;');
const minutes=value=>{const match=String(value||'').match(/^(\d{2}):(\d{2})$/);if(!match)return NaN;const h=Number(match[1]),m=Number(match[2]);return h<24&&m<60?h*60+m:NaN};
const formatHours=value=>{const total=Math.round(Number(value)||0);return total%60?`${Math.floor(total/60)} h ${String(total%60).padStart(2,'0')}`:`${Math.floor(total/60)} h`;};
const formatDate=iso=>{const match=String(iso||'').match(/^(\d{4})-(\d{2})-(\d{2})$/);return match?`${match[3]}/${match[2]}/${match[1]}`:iso||'—';};
const dayName=iso=>{const date=new Date(`${iso}T12:00:00`);return Number.isNaN(date.getTime())?'Date invalide':new Intl.DateTimeFormat('fr-FR',{weekday:'long'}).format(date).replace(/^./,char=>char.toUpperCase());};
const slotMinutes=slot=>{const value=minutes(slot.end)-minutes(slot.start);return Number.isFinite(value)&&value>0?value:0;};
const distinctCodes=day=>new Set((day.slots||[]).map(slot=>slot.code).filter(Boolean));
const dayMinutes=day=>(day.slots||[]).reduce((total,slot)=>total+slotMinutes(slot),0);
const validDate=value=>/^\d{4}-\d{2}-\d{2}$/.test(value||'')&&!Number.isNaN(new Date(`${value}T12:00:00Z`).getTime())&&new Date(`${value}T12:00:00Z`).toISOString().slice(0,10)===value;
const timeString=value=>`${String(Math.floor(value/60)).padStart(2,'0')}:${String(value%60).padStart(2,'0')}`;

function changePlanning(change,focusDate=null){
  if(saving||!loaded)return;
  const previous=JSON.stringify(planning);
  change();
  planning.sort((a,b)=>a.date.localeCompare(b.date));
  planning.forEach(day=>(day.slots||[]).sort((a,b)=>a.start.localeCompare(b.start)));
  if(previous===JSON.stringify(planning))return;
  undoStack.push(previous);
  if(undoStack.length>40)undoStack.shift();
  dirty=true;serverErrors=[];hideNotices();render();
  if(focusDate)document.getElementById(`day-${focusDate}`)?.scrollIntoView({behavior:'smooth',block:'center'});
}

function dialogError(id,message){$(id).textContent=message;$(id).style.display='block';}
function nextDate(from=null){
  const value=from||planning.at(-1)?.date||new Date().toISOString().slice(0,10);
  const date=new Date(`${value}T12:00:00Z`);
  if(from||planning.length)date.setUTCDate(date.getUTCDate()+1);
  while([0,6].includes(date.getUTCDay())||planning.some(day=>day.date===date.toISOString().slice(0,10))||date.toISOString().slice(0,10)===examDate)date.setUTCDate(date.getUTCDate()+1);
  return date.toISOString().slice(0,10);
}

function openDayDialog(index=null){
  duplicateDayIndex=index;
  $('dayForm').reset();$('dayDialogError').style.display='none';
  $('dayDialogTitle').textContent=index===null?'Ajouter une journée':'Dupliquer la journée';
  $('dayDialogHelp').textContent=index===null?'Choisissez une date, puis ajoutez les cours de cette journée.':'Les cours, horaires, formateurs et salles seront copiés à la nouvelle date.';
  $('newDayDate').value=nextDate(index===null?null:planning[index].date);
  $('dayDialog').showModal();$('newDayDate').focus();
}

function openSlotDialog(dayIndex,slotIndex=null){
  const day=planning[dayIndex],slot=slotIndex===null?null:day.slots[slotIndex];
  editedSlot=slot?{dayIndex,slotIndex}:null;
  $('slotForm').reset();$('slotDialogError').style.display='none';
  $('slotDialogTitle').textContent=slot?'Déplacer / modifier le créneau':'Ajouter un créneau';
  $('slotDialogHelp').textContent=slot?'Choisissez la date de destination et ajustez les horaires si besoin.':'La date peut être une journée existante ou une nouvelle journée.';
  $('slotSubmit').textContent=slot?'Appliquer au planning':'Ajouter le créneau';
  $('slotDate').value=day.date;
  const lastEnd=Math.max(0,...(day.slots||[]).map(item=>minutes(item.end)||0));
  const start=lastEnd?(lastEnd>=720&&lastEnd<810?810:Math.min(lastEnd,1380)):510;
  $('slotStart').value=slot?.start||timeString(start);
  $('slotEnd').value=slot?.end||timeString(Math.min(start+60,1439));
  $('slotCode').innerHTML=modules.map(module=>`<option value="${esc(module.code)}">${esc(module.code)} — ${esc(module.title)}</option>`).join('');
  const totals=moduleTotals();
  $('slotCode').value=slot?.code||modules.find(module=>(totals[module.code]||0)<Number(module.hours)*60)?.code||modules[0]?.code||'';
  $('slotTrainer').value=slot?.trainer||commonDayValue(day,'trainer');
  $('slotRoom').value=slot?.room||commonDayValue(day,'room');
  $('slotDialog').showModal();$('slotDate').focus();
}

function showNotice(id,message){const element=$(id);element.textContent=message;element.style.display='block';element.scrollIntoView({behavior:'smooth',block:'center'});}
function hideNotices(){['error','success'].forEach(id=>{$(id).style.display='none';$(id).textContent='';});}

function moduleTotals(){const totals=Object.fromEntries(modules.map(module=>[module.code,0]));planning.forEach(day=>(day.slots||[]).forEach(slot=>{if(slot.code in totals)totals[slot.code]+=slotMinutes(slot);}));return totals;}

function clientErrors(){
  const errors=[];
  const seenDates=new Set();
  planning.forEach(day=>{
    if(!validDate(day.date))errors.push('Une date du planning est invalide.');
    if(seenDates.has(day.date))errors.push(`La date ${formatDate(day.date)} apparaît plusieurs fois.`);
    seenDates.add(day.date);
    if(!(day.slots||[]).length)errors.push(`Le ${formatDate(day.date)} ne contient aucun créneau : ajoutez un cours ou supprimez la journée vide.`);
    if(day.date===examDate)errors.push(`Le ${formatDate(day.date)} est la date d’examen et ne peut pas compter dans les heures de formation.`);
    if([0,6].includes(new Date(`${day.date}T12:00:00Z`).getUTCDay()))errors.push(`Le ${formatDate(day.date)} tombe un week-end.`);
    const intervals=[];
    (day.slots||[]).forEach(slot=>{
      const start=minutes(slot.start),end=minutes(slot.end);
      if(!Number.isFinite(start)||!Number.isFinite(end)||end<=start){errors.push(`Horaire invalide le ${formatDate(day.date)} : ${slot.start||'—'}-${slot.end||'—'}.`);return;}
      if(intervals.some(([existingStart,existingEnd])=>start<existingEnd&&end>existingStart))errors.push(`Deux cours se chevauchent le ${formatDate(day.date)}.`);
      intervals.push([start,end]);
    });
    const codes=distinctCodes(day);
    if(codes.size>maxDistinctModulesPerDay)errors.push(`Le ${formatDate(day.date)} contient ${codes.size} modules différents (${[...codes].join(', ')}). Le maximum est de ${maxDistinctModulesPerDay}.`);
    if(dayMinutes(day)>480)errors.push(`Le ${formatDate(day.date)} dépasse 8 h de formation.`);
  });
  const total=planning.reduce((sum,day)=>sum+dayMinutes(day),0);
  if(total!==REQUIRED_MINUTES)errors.push(`Le planning doit totaliser exactement 328 h (actuel : ${formatHours(total)}).`);
  const totals=moduleTotals();
  modules.forEach(module=>{const expected=Number(module.hours)*60;if(totals[module.code]!==expected)errors.push(`${module.code} — ${module.title} doit totaliser ${module.hours} h (actuel : ${formatHours(totals[module.code])}).`);});
  return [...new Set(errors)];
}

function renderSummary(){
  const total=planning.reduce((sum,day)=>sum+dayMinutes(day),0);
  const conforming=planning.filter(day=>distinctCodes(day).size<=maxDistinctModulesPerDay).length;
  $('plannedHours').textContent=formatHours(total);
  $('daysCount').textContent=String(planning.length);
  $('rulesCount').textContent=`${conforming} / ${planning.length}`;
  $('plannedMetric').className=`metric ${total===REQUIRED_MINUTES?'good':'bad'}`;
  $('rulesMetric').className=`metric ${conforming===planning.length?'good':'bad'}`;
  $('daysMetric').className='metric';
  const totals=moduleTotals();
  $('moduleSummary').innerHTML=modules.map(module=>{
    const expected=Number(module.hours)*60,actual=totals[module.code]||0,ok=actual===expected;
    return `<div class="module-chip ${ok?'good':'bad'}"><strong>${esc(module.code)} — ${esc(module.title)}</strong><span>${formatHours(actual)} planifiées / ${module.hours} h attendues</span>${ok?'':`<span class="remaining-hours">${formatHours(Math.abs(expected-actual))} ${actual<expected?'à placer':'en trop'}</span>`}</div>`;
  }).join('');
  const trainers=[...new Set(planning.flatMap(day=>(day.slots||[]).map(slot=>String(slot.trainer||'').trim())).filter(Boolean))].sort((a,b)=>a.localeCompare(b,'fr',{sensitivity:'base'}));
  $('planningTrainers').innerHTML=trainers.length?trainers.map(name=>`<span class="trainer-chip">${esc(name)}</span>`).join(''):'<div class="empty-trainers">Aucun formateur n’est encore affecté au planning.</div>';
  $('stale').style.display=needsRegeneration&&!isDraft?'block':'none';
  $('draftNotice').style.display=isDraft?'block':'none';
  const errors=serverErrors.length?serverErrors:clientErrors();
  $('planningChecks').hidden=!errors.length;
  $('planningChecksTitle').textContent=`${errors.length} point${errors.length>1?'s':''} à ajuster avant d’actualiser le PDF`;
  $('planningIssues').innerHTML=errors.map(error=>`<li>${esc(error)}</li>`).join('');
  $('editStatus').textContent=saving?'Enregistrement…':dirty?'Modifications non enregistrées':isDraft?'Brouillon enregistré':'Toutes les modifications sont enregistrées';
  $('editStatus').className=`edit-status ${dirty?'unsaved':''}`;
  $('undoChange').disabled=saving||!undoStack.length;
  $('addDay').disabled=saving||!loaded;
  $('openTrainerDialog').disabled=saving||!loaded;
  $('editor').classList.toggle('editor-busy',saving);
  document.querySelectorAll('[data-save],[data-save-pdf]').forEach(button=>button.disabled=saving||!loaded);
}

function commonDayValue(day,field){const values=[...new Set((day.slots||[]).map(slot=>String(slot[field]||'').trim()).filter(Boolean))];return values.length===1?values[0]:'';}

function render(){
  const moduleOptions=modules.map(module=>`<option value="${esc(module.code)}">${esc(module.code)} — ${esc(module.title)}</option>`).join('');
  $('editor').innerHTML=planning.map((day,dayIndex)=>{
    const codes=distinctCodes(day),total=dayMinutes(day),valid=codes.size<=maxDistinctModulesPerDay&&total<=480&&total>0;
    const rows=(day.slots||[]).map((slot,slotIndex)=>`<tr>
      <td><div class="time-pair"><input aria-label="Début du créneau" type="time" data-day="${dayIndex}" data-slot="${slotIndex}" data-field="start" value="${esc(slot.start)}"><input aria-label="Fin du créneau" type="time" data-day="${dayIndex}" data-slot="${slotIndex}" data-field="end" value="${esc(slot.end)}"></div></td>
      <td><select aria-label="Module du créneau" data-day="${dayIndex}" data-slot="${slotIndex}" data-field="code">${moduleOptions.replace(`value="${esc(slot.code)}"`,`value="${esc(slot.code)}" selected`)}</select></td>
      <td class="duration">${formatHours(slotMinutes(slot))}</td>
      <td><input aria-label="Formateur du créneau" list="trainerOptions" data-day="${dayIndex}" data-slot="${slotIndex}" data-field="trainer" value="${esc(slot.trainer)}" placeholder="Choisir ou saisir un formateur"></td>
      <td><input aria-label="Salle du créneau" data-day="${dayIndex}" data-slot="${slotIndex}" data-field="room" value="${esc(slot.room)}" placeholder="Salle / lieu"></td>
      <td><div class="row-actions"><button class="btn btn-small" type="button" data-move-slot="${slotIndex}" data-day="${dayIndex}">Déplacer</button><button class="btn btn-small btn-danger" type="button" data-remove-slot="${slotIndex}" data-day="${dayIndex}" aria-label="Supprimer le créneau ${esc(slot.start)} – ${esc(slot.end)} du ${formatDate(day.date)}">Supprimer</button></div></td>
    </tr>`).join('');
    return `<section class="day" id="day-${esc(day.date)}">
      <div class="day-head">
        <div class="day-title"><div><h2>${dayName(day.date)} ${formatDate(day.date)}</h2><div class="day-meta">${formatHours(total)} · ${codes.size} module${codes.size>1?'s':''} différent${codes.size>1?'s':''}</div></div><span class="badge ${valid?'badge-ok':'badge-warn'}">${valid?'Journée conforme':total===0?'À compléter':codes.size>maxDistinctModulesPerDay?'Trop de modules':'Plus de 8 h'}</span></div>
        <label class="day-date">Déplacer la journée <input aria-label="Date de la journée du ${formatDate(day.date)}" type="date" data-day="${dayIndex}" data-day-field="date" value="${esc(day.date)}"></label>
      </div>
      <div class="day-tools">
        <label>Formateur de la journée <input list="trainerOptions" data-day-trainer="${dayIndex}" value="${esc(commonDayValue(day,'trainer'))}" placeholder="Plusieurs formateurs ou aucun"></label>
        <button class="btn btn-small" type="button" data-apply-day="${dayIndex}" data-apply-field="trainer">Appliquer à la journée</button>
        <label>Salle de la journée <input data-day-room="${dayIndex}" value="${esc(commonDayValue(day,'room'))}" placeholder="Plusieurs salles ou aucune"></label>
        <button class="btn btn-small" type="button" data-apply-day="${dayIndex}" data-apply-field="room">Appliquer à la journée</button>
        <button class="btn btn-small btn-outline-gold day-add-trainer" type="button" data-open-trainer-day="${dayIndex}">＋ Ajouter / changer le formateur</button>
      </div>
      ${rows?`<div class="table-wrap"><table><thead><tr><th>Horaires</th><th>Module</th><th>Durée</th><th>Formateur</th><th>Salle</th><th>Actions</th></tr></thead><tbody>${rows}</tbody></table></div>`:'<div class="empty-day">Cette journée est vide. Ajoutez votre premier créneau ci-dessous.</div>'}
      <div class="day-footer"><button class="btn btn-small btn-gold" type="button" data-add-slot="${dayIndex}">＋ Ajouter un créneau</button><div class="day-actions"><button class="btn btn-small" type="button" data-duplicate-day="${dayIndex}">Dupliquer la journée</button><button class="btn btn-small btn-danger" type="button" data-remove-day="${dayIndex}">Supprimer cette journée</button></div></div>
    </section>`;
  }).join('')||'<div class="panel empty-day">Le planning est vide. Cliquez sur « Ajouter une journée » pour commencer.</div>';

  document.querySelectorAll('[data-field]').forEach(input=>input.addEventListener('change',event=>{
    const day=planning[Number(event.target.dataset.day)],slot=day?.slots?.[Number(event.target.dataset.slot)];if(!slot)return;
    const field=event.target.dataset.field,value=event.target.value;
    changePlanning(()=>{slot[field]=value;slot.placementMode='manuel';if(field==='code'){const module=modules.find(item=>item.code===slot.code);if(module)slot.title=module.title;}});
  }));
  document.querySelectorAll('[data-day-field]').forEach(input=>input.addEventListener('change',event=>{
    const index=Number(event.target.dataset.day),value=event.target.value;
    if(!validDate(value)){event.target.value=planning[index].date;showNotice('error','Choisissez une date valide.');return;}
    if(planning.some((day,i)=>i!==index&&day.date===value)){event.target.value=planning[index].date;showNotice('error','Cette journée existe déjà. Utilisez « Déplacer » pour y transférer un créneau.');return;}
    changePlanning(()=>{planning[index].date=value;},value);
  }));
  document.querySelectorAll('[data-apply-day]').forEach(button=>button.addEventListener('click',()=>{
    const dayIndex=Number(button.dataset.applyDay),field=button.dataset.applyField;
    const input=document.querySelector(field==='trainer'?`[data-day-trainer="${dayIndex}"]`:`[data-day-room="${dayIndex}"]`);
    const value=input?.value||'';
    changePlanning(()=>(planning[dayIndex].slots||[]).forEach(slot=>slot[field]=value));
  }));
  document.querySelectorAll('[data-open-trainer-day]').forEach(button=>button.addEventListener('click',()=>openTrainerDialog(Number(button.dataset.openTrainerDay))));
  document.querySelectorAll('[data-add-slot]').forEach(button=>button.addEventListener('click',()=>openSlotDialog(Number(button.dataset.addSlot))));
  document.querySelectorAll('[data-duplicate-day]').forEach(button=>button.addEventListener('click',()=>openDayDialog(Number(button.dataset.duplicateDay))));
  document.querySelectorAll('[data-remove-day]').forEach(button=>button.addEventListener('click',()=>{
    const index=Number(button.dataset.removeDay),day=planning[index];
    if((day.slots||[]).length&&!window.confirm(`Supprimer la journée du ${formatDate(day.date)} et ses ${formatHours(dayMinutes(day))} de cours ? Vous pourrez annuler cette modification.`))return;
    changePlanning(()=>planning.splice(index,1));
  }));
  document.querySelectorAll('[data-move-slot]').forEach(button=>button.addEventListener('click',()=>openSlotDialog(Number(button.dataset.day),Number(button.dataset.moveSlot))));
  document.querySelectorAll('[data-remove-slot]').forEach(button=>button.addEventListener('click',()=>changePlanning(()=>planning[Number(button.dataset.day)].slots.splice(Number(button.dataset.removeSlot),1))));
  renderSummary();
}

function syncTrainerOptions(){
  trainerOptions=[...new Set(trainerOptions.map(name=>String(name||'').trim()).filter(Boolean))].sort((a,b)=>a.localeCompare(b,'fr',{sensitivity:'base'}));
  $('trainerOptions').innerHTML=trainerOptions.map(name=>`<option value="${esc(name)}"></option>`).join('');
}

function renderTrainerDayChoices(preselectedDayIndex=null){
  $('trainerDayChoices').innerHTML=planning.map((day,dayIndex)=>`<label class="day-choice"><input type="checkbox" name="trainerDays" value="${dayIndex}" ${dayIndex===preselectedDayIndex?'checked':''}><span><strong>${dayName(day.date)} ${formatDate(day.date)}</strong><small>${formatHours(dayMinutes(day))} · ${distinctCodes(day).size} module${distinctCodes(day).size>1?'s':''}</small></span></label>`).join('');
}

function openTrainerDialog(preselectedDayIndex=null){
  const dialog=$('trainerDialog');
  $('addTrainerForm').reset();
  $('trainerDialogError').style.display='none';
  $('trainerDialogError').textContent='';
  renderTrainerDayChoices(preselectedDayIndex);
  dialog.showModal();
  window.setTimeout(()=>$('trainerName').focus(),0);
}

function closeTrainerDialog(){$('trainerDialog').close();}

async function persist(regeneratePdf){
  if(saving||!loaded)return;
  hideNotices();
  const errors=clientErrors();
  if(regeneratePdf&&errors.length){
    $('planningChecks').open=true;
    showNotice('error','Le planning comporte encore des points à ajuster. Cliquez sur « Enregistrer » pour conserver votre brouillon, ou corrigez les points signalés avant d’actualiser le PDF.');
    return;
  }
  saving=true;renderSummary();$('editor').inert=true;
  try{
    const response=await fetch(`/api/sessions/${sid}/a3p-planning`,{method:'PUT',headers:{'Content-Type':'application/json'},body:JSON.stringify({planningData:planning,regeneratePdf,saveDraft:!regeneratePdf})});
    const payload=await response.json();
    if(!response.ok||!payload.ok)throw new Error((payload.errors||[payload.error||'Enregistrement impossible.']).join(' '));
    planning=payload.planningData||planning;needsRegeneration=!!payload.needsRegeneration;isDraft=!!payload.isDraft;serverErrors=payload.validationErrors||[];dirty=false;render();
    showNotice('success',isDraft?'Brouillon enregistré. Vous pouvez quitter cette page et reprendre vos ajustements plus tard.':regeneratePdf?'Modifications enregistrées et PDF A3P régénéré.':'Modifications enregistrées. Vous pouvez maintenant régénérer le PDF.');
    if(regeneratePdf&&payload.pdfUrl)window.open(payload.pdfUrl,'_blank','noopener');
  }catch(error){showNotice('error',error.message||'Enregistrement impossible.');}
  finally{saving=false;$('editor').inert=false;renderSummary();}
}

async function loadPlanning(){
  try{
    const response=await fetch(`/api/sessions/${sid}/a3p-planning`),payload=await response.json();
    if(!response.ok||!payload.ok)throw new Error(payload.error||'Chargement impossible.');
    planning=payload.planningData||[];modules=payload.modules||[];trainerOptions=payload.trainerOptions||[];maxDistinctModulesPerDay=payload.maxDistinctModulesPerDay||3;needsRegeneration=!!payload.needsRegeneration;isDraft=!!payload.isDraft;examDate=payload.examDate||null;serverErrors=payload.validationErrors||[];
    loaded=true;
    syncTrainerOptions();
    render();
    if(isDraft)$('planningChecks').open=true;
  }catch(error){$('editor').innerHTML='';$('editStatus').textContent='Chargement impossible';showNotice('error',error.message||'Chargement impossible.');}
}

document.querySelectorAll('[data-save]').forEach(button=>button.addEventListener('click',()=>persist(false)));
document.querySelectorAll('[data-save-pdf]').forEach(button=>button.addEventListener('click',()=>persist(true)));
$('openTrainerDialog').addEventListener('click',()=>openTrainerDialog());
document.querySelectorAll('[data-close-trainer-dialog]').forEach(button=>button.addEventListener('click',closeTrainerDialog));
$('selectAllTrainerDays').addEventListener('click',()=>document.querySelectorAll('input[name="trainerDays"]').forEach(input=>input.checked=true));
$('clearTrainerDays').addEventListener('click',()=>document.querySelectorAll('input[name="trainerDays"]').forEach(input=>input.checked=false));
$('addTrainerForm').addEventListener('submit',event=>{
  event.preventDefault();
  const name=$('trainerName').value.trim();
  const selectedDays=[...document.querySelectorAll('input[name="trainerDays"]:checked')].map(input=>Number(input.value)).filter(Number.isInteger);
  const error=$('trainerDialogError');
  if(!name||!selectedDays.length){error.textContent=!name?'Choisissez ou saisissez un formateur.':'Sélectionnez au moins une journée.';error.style.display='block';return;}
  changePlanning(()=>selectedDays.forEach(dayIndex=>(planning[dayIndex]?.slots||[]).forEach(slot=>slot.trainer=name)));
  if(!trainerOptions.some(option=>option.localeCompare(name,'fr',{sensitivity:'base'})===0))trainerOptions.push(name);
  syncTrainerOptions();
  closeTrainerDialog();
  render();
  showNotice('success',`${name} a été affecté à ${selectedDays.length} journée${selectedDays.length>1?'s':''}. Enregistrez le planning pour conserver la modification.`);
});
$('trainerDialog').addEventListener('click',event=>{if(event.target===$('trainerDialog'))closeTrainerDialog();});
$('addDay').addEventListener('click',()=>openDayDialog());
$('undoChange').addEventListener('click',()=>{
  if(saving||!undoStack.length)return;
  planning=JSON.parse(undoStack.pop());dirty=true;serverErrors=[];hideNotices();render();
});
document.querySelectorAll('[data-close-dialog]').forEach(button=>button.addEventListener('click',()=>$(button.dataset.closeDialog).close()));
$('dayForm').addEventListener('submit',event=>{
  event.preventDefault();
  const date=$('newDayDate').value;
  if(!validDate(date)){dialogError('dayDialogError','Choisissez une date valide.');return;}
  if(planning.some(day=>day.date===date)){dialogError('dayDialogError','Cette date existe déjà dans le planning. Ajoutez un créneau à cette journée.');return;}
  const slots=duplicateDayIndex===null?[]:JSON.parse(JSON.stringify(planning[duplicateDayIndex].slots||[]));
  changePlanning(()=>planning.push({date,slots}),date);
  $('dayDialog').close();
});
$('slotForm').addEventListener('submit',event=>{
  event.preventDefault();
  const date=$('slotDate').value,start=$('slotStart').value,end=$('slotEnd').value,code=$('slotCode').value;
  if(!validDate(date)){dialogError('slotDialogError','Choisissez une date valide.');return;}
  if(!Number.isFinite(minutes(start))||!Number.isFinite(minutes(end))||minutes(end)<=minutes(start)){dialogError('slotDialogError','L’heure de fin doit être après l’heure de début.');return;}
  const module=modules.find(item=>item.code===code);
  if(!module){dialogError('slotDialogError','Choisissez un module.');return;}
  const sourceDay=editedSlot?planning[editedSlot.dayIndex]:null;
  const original=editedSlot?sourceDay.slots[editedSlot.slotIndex]:null;
  const target=planning.find(day=>day.date===date);
  if((target?.slots||[]).some(slot=>slot!==original&&minutes(start)<minutes(slot.end)&&minutes(end)>minutes(slot.start))){dialogError('slotDialogError','Ce créneau chevauche un cours déjà présent à cette date. Ajustez les horaires.');return;}
  const slot={...(original||{}),start,end,code,title:module.title,trainer:$('slotTrainer').value.trim(),room:$('slotRoom').value.trim(),placementMode:'manuel',durationMinutes:minutes(end)-minutes(start)};
  changePlanning(()=>{
    if(editedSlot)sourceDay.slots.splice(editedSlot.slotIndex,1);
    let destination=planning.find(day=>day.date===date);
    if(!destination){destination={date,slots:[]};planning.push(destination);}
    destination.slots.push(slot);
    if(sourceDay&&sourceDay!==destination&&!sourceDay.slots.length)planning.splice(planning.indexOf(sourceDay),1);
  },date);
  $('slotDialog').close();
});
window.addEventListener('beforeunload',event=>{if(dirty||saving){event.preventDefault();event.returnValue='';}});
document.querySelectorAll('[data-save],[data-save-pdf],#addDay,#openTrainerDialog').forEach(button=>button.disabled=true);
loadPlanning();
