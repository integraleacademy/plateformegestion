const status=document.getElementById('status');
status.textContent='Chargement du moteur de rendu…';
async function boot(){
const {renderSlide}=await import('/static/studio_visuals/js/studio-renderer.js');
const {createProject,FORMATS,normalizeSlideContentForTemplate}=await import('/static/studio_visuals/js/studio-store.js');
const {fitSlide}=await import('/static/studio_visuals/js/studio-text-fit.js');
const {waitForImages,SocialVisualExporter}=await import('/static/studio_visuals/js/studio-exporter.js');
const {validateStudioSlide}=await import('/static/studio_visuals/js/studio-validation.js');
const $=id=>document.getElementById(id);
const [{templates},themes]=await Promise.all(['templates','themes'].map(name=>fetch('/static/studio_visuals/data/'+name+'.json').then(r=>r.json())));
const catalog=templates.filter(t=>t.isManual);
for(const t of catalog)$('template').add(new Option(t.name,t.id));
for(const f of Object.values(FORMATS))$('format').add(new Option(f.label,f.id));
function projectFor(t,format){const p=createProject({formation:t.formationPreset,templateId:t.id,content:t.contentDefaults});p.format=FORMATS[format];p.slides[0].options.showSafeMargins=false;normalizeSlideContentForTemplate(p.slides[0],t);return p;}
async function render(target,t,format){const p=projectFor(t,format);const node=renderSlide(p,p.slides[0],'export',{templates,themes});target.replaceChildren(node);await waitForImages(node);await fitSlide(node);await fitSlide(node);return {p,node,v:validateStudioSlide(node)};}
async function preview(){const t=catalog.find(t=>t.id===$('template').value);try{const {v}=await render($('preview'),t,$('format').value);$('status').textContent=v.blockingErrors.length?v.blockingErrors.map(x=>x.message).join(' / '):'Rendu vérifié · illustrations chargées · aucun débordement';}catch(e){$('status').textContent=e.message;}}
for(const id of ['template','format'])$(id).addEventListener('change',preview);
$('audit').addEventListener('click',async()=>{const failures=[];let count=0;$('audit').disabled=true;try{for(const t of catalog)for(const format of Object.keys(FORMATS)){const {node,v}=await render($('stage'),t,format);const images=[...node.querySelectorAll('.mi-picture img')];const tooSmall=images.some(i=>i.parentElement.getBoundingClientRect().height<95);const errors=v.blockingErrors.map(x=>x.message);if(tooSmall)errors.push('Illustration trop petite');if(errors.length)failures.push({id:t.id,format,errors});$('status').textContent=++count+'/168 rendus contrôlés';}$('report').textContent=JSON.stringify({total:count,failed:failures.length,failures},null,2);$('status').textContent=`Terminé : ${count-failures.length}/${count} rendus sans erreur`;}catch(e){$('report').textContent=e.stack}finally{$('audit').disabled=false;$('stage').replaceChildren();}});
$('exportButton').addEventListener('click',async()=>{try{const t=catalog.find(t=>t.id===$('template').value),p=projectFor(t,$('format').value),exporter=new SocialVisualExporter({root:$('export'),templates,themes});const data=await exporter.exportSlide({project:p,slide:p.slides[0],outputWidth:p.format.width,outputHeight:p.format.height,onStatus:s=>$('status').textContent=s});const a=document.createElement('a');a.download=t.id+'.png';a.href=data;a.textContent='Télécharger le PNG vérifié';$('status').replaceChildren(a);a.click();}catch(e){$('status').textContent='Export : '+e.message;}});
await preview();
if(new URLSearchParams(location.search).has('audit'))$('audit').click();
}
boot().catch(error=>{status.textContent='Chargement impossible : '+error.message;console.error(error)});
