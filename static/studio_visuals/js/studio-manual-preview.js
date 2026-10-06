const status=document.getElementById('status');
status.textContent='Chargement du moteur de rendu…';
async function boot(){
 if(document.readyState!=='complete')await new Promise(resolve=>window.addEventListener('load',resolve,{once:true}));
 const missing=[...document.querySelectorAll('link[rel=stylesheet]')].filter(link=>!link.sheet);
 if(missing.length)throw new Error('Styles indisponibles : rechargez la page.');
 const {renderSlide}=await import('./studio-renderer.js');
 const {createProject,FORMATS,normalizeSlideContentForTemplate}=await import('./studio-store.js');
 const {applyCanvasTemplate}=await import('./studio-canvas-models.js');
 const {fitSlide}=await import('./studio-text-fit.js');
 const {waitForImages,SocialVisualExporter}=await import('./studio-exporter.js');
 const {validateStudioSlide}=await import('./studio-validation.js');
 const $=id=>document.getElementById(id);
 const [{templates},themes]=await Promise.all(['templates','themes'].map(name=>fetch('/static/studio_visuals/data/'+name+'.json').then(r=>r.json())));
 const catalog=templates.filter(t=>t.isManual||t.isCanvas);
 const total=catalog.reduce((sum,t)=>sum+(t.pages?.length||1)*t.supportedFormats.length,0);
 $('collectionCount').textContent=`Illustrations et canevas · ${catalog.length} modèles`;
 for(const t of catalog)$('template').add(new Option(t.name,t.id));
 for(const f of Object.values(FORMATS))$('format').add(new Option(f.label,f.id));
 function projectFor(t,format){
  const p=createProject({formation:t.formationPreset,templateId:t.id});
  if(t.isCanvas)applyCanvasTemplate(p,t);
  p.format=FORMATS[format];
  for(const slide of p.slides){slide.options.showSafeMargins=false;normalizeSlideContentForTemplate(slide,t);}
  return p;
 }
 async function render(target,t,format,page=0){
  const p=projectFor(t,format);p.activeSlideIndex=page;
  const node=renderSlide(p,p.slides[page],'export',{templates,themes});target.replaceChildren(node);
  await waitForImages(node);await fitSlide(node,{waitForPaint:false});await fitSlide(node,{waitForPaint:false});
  return {p,node,v:validateStudioSlide(node)};
 }
 function pageOptions(){const t=catalog.find(t=>t.id===$('template').value);$('page').replaceChildren();for(let i=0;i<(t.pages?.length||1);i++)$('page').add(new Option(`${i+1} / ${t.pages?.length||1}`,i));$('pageLabel').hidden=!t.isCarousel;}
 async function preview(){const t=catalog.find(t=>t.id===$('template').value);try{const {v}=await render($('preview'),t,$('format').value,Number($('page').value)||0);$('status').textContent=v.blockingErrors.length?v.blockingErrors.map(x=>x.message).join(' / '):'Rendu vérifié · illustrations chargées · aucun débordement';}catch(e){$('status').textContent=e.message;}}
 $('template').addEventListener('change',()=>{pageOptions();preview();});
 for(const id of ['format','page'])$(id).addEventListener('change',preview);
 $('audit').addEventListener('click',async()=>{
  const failures=[];let count=0;$('audit').disabled=true;
  try{
   for(const t of catalog)for(let page=0;page<(t.pages?.length||1);page++)for(const format of t.supportedFormats){
    const {node,v}=await render($('stage'),t,format,page);
    const images=[...node.querySelectorAll('.mi-picture img')],errors=v.blockingErrors.map(x=>x.message);
    if(images.some(i=>!i.complete||!i.naturalWidth))errors.push('Illustration non chargée');
    if(images.some(i=>i.parentElement.getBoundingClientRect().height<95))errors.push('Illustration trop petite');
    if(images.some(i=>getComputedStyle(i).objectFit!=='cover'))errors.push('Illustration avec bandes vides');
    const art=node.querySelector('.mi-spotlight>.mi-picture'),panel=node.querySelector('.mx-spotlight-panel');
    if(art&&panel){const a=art.getBoundingClientRect(),b=panel.getBoundingClientRect();if(Math.min(a.right,b.right)-Math.max(a.left,b.left)>1&&Math.min(a.bottom,b.bottom)-Math.max(a.top,b.top)>1)errors.push('Texte superposé à l’illustration');}

    if(errors.length)failures.push({id:t.id,page:page+1,format,errors});
    $('status').textContent=++count+`/${total} rendus contrôlés`;
   }
   $('report').textContent=JSON.stringify({total:count,failed:failures.length,failures},null,2);
   $('status').textContent=`Terminé : ${count-failures.length}/${count} rendus sans erreur`;
  }catch(e){$('report').textContent=e.stack}finally{$('audit').disabled=false;$('stage').replaceChildren();}
 });
 $('exportButton').addEventListener('click',async()=>{
  $('exportButton').disabled=true;
  try{
   const t=catalog.find(t=>t.id===$('template').value),p=projectFor(t,$('format').value),page=Number($('page').value)||0;
   p.activeSlideIndex=page;
   const exporter=new SocialVisualExporter({root:$('export'),templates,themes});
   const data=await exporter.exportSlide({project:p,slide:p.slides[page],outputWidth:p.format.width,outputHeight:p.format.height,onStatus:s=>$('status').textContent=s});
   const bytes=Uint8Array.from(atob(data.split(',')[1]),c=>c.charCodeAt(0));
   const a=document.createElement('a');a.download=t.id+(t.isCarousel?`-${page+1}`:'')+'.png';a.href=URL.createObjectURL(new Blob([bytes],{type:'image/png'}));a.textContent='Télécharger le PNG vérifié';
   $('status').replaceChildren(a);a.click();
  }catch(e){$('status').textContent='Export : '+e.message;}finally{$('exportButton').disabled=false;}
 });
 pageOptions();await preview();
 if(new URLSearchParams(location.search).has('audit'))$('audit').click();
}
boot().catch(error=>{status.textContent='Chargement impossible : '+error.message;console.error(error)});
