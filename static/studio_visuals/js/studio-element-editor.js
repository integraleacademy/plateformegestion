const EDITABLE_SELECTOR=[
  '[data-logo-id]',
  '[data-content-key]',
  '[data-layout-role]',
  '[data-studio-text-slot]',
  '.sv-brand__formation',
  '.sv-brand__slogan',
  '.sv-footer__identity',
  '.sv-footer__place',
  '.sv-footer__site',
  '.sv-footer__phone',
  '.sv-footer__cta',
  '.studio-added-icon',
  '.studio-added-icon em',
  '.sv-footer strong','.sv-footer small','.sv-footer b','.sv-footer i',
  'main h1','main h2','main h3','main h4','main p','main blockquote','main strong','main small','main span','main b','main em','main time','main button','main a','main cite','main mark',
  'main section','main article','main aside','main li','main details','main summary','main div','main header','main footer','main ul','main ol','main i','main svg','main img','main meter','main hr','main address','main dialog'
].join(',');

function slug(value='element'){
  return String(value).normalize?.('NFD').replace(/[\u0300-\u036f]/g,'').toLowerCase().replace(/[^a-z0-9]+/g,'-').replace(/^-|-$/g,'')||'element';
}

function stablePath(node,root){
  const parts=[];
  let current=node;
  while(current&&current!==root){
    const parent=current.parentElement;
    if(!parent)break;
    const siblings=[...parent.children].filter(item=>item.tagName===current.tagName&&!item.matches?.('[data-editor-only]'));
    parts.unshift(`${String(current.tagName||'node').toLowerCase()}${Math.max(0,siblings.indexOf(current))}`);
    current=parent;
  }
  return parts.join('-');
}

function preferredId(node,root,slide){
  const scope=slug(slide?.templateId||'template');
  let id='';
  if(node.dataset.logoId)id=`logo-${slug(node.dataset.logoId)}`;
  else if(node.dataset.contentKey)id=`content-${slug(node.dataset.contentKey)}`;
  else if(node.dataset.studioTextSlot)id=`text-${stablePath(node,root)}`;
  else if(node.classList.contains('sv-brand__formation'))id='brand-formation';
  else if(node.classList.contains('sv-brand__slogan'))id='brand-slogan';
  else if(node.classList.contains('sv-footer__place'))id='footer-place';
  else if(node.classList.contains('sv-footer__site'))id='footer-site';
  else if(node.classList.contains('sv-footer__phone'))id='footer-phone';
  else if(node.classList.contains('sv-footer__cta'))id='footer-cta';
  else if(node.classList.contains('sv-footer__identity'))id='footer-identity';
  else if(node.dataset.elementId)id=`added-${slug(node.dataset.elementId)}`;
  else if(node.dataset.layoutRole)id=`role-${slug(node.dataset.layoutRole)}`;
  else id=`auto-${stablePath(node,root)}`;
  return `${scope}--${id}`;
}

function hasEditableText(node){
  if(node.dataset.contentKey||node.dataset.studioTextSlot)return true;
  if(['SVG','IMG','METER','HR'].includes(node.tagName))return false;
  const structuralChildren=[...node.children].filter(child=>!child.matches?.('[data-editor-only]'));
  return structuralChildren.length===0&&String(node.textContent||'').trim().length>0;
}

export function ensureElementOverrides(slide){
  slide.elementOverrides=slide.elementOverrides&&typeof slide.elementOverrides==='object'?slide.elementOverrides:{};
  return slide.elementOverrides;
}

export function getElementOverride(slide,id){
  return {...(ensureElementOverrides(slide)[id]||{})};
}

export function setElementOverride(slide,id,patch={}){
  const all=ensureElementOverrides(slide);
  const next={...(all[id]||{}),...patch};
  for(const [key,value] of Object.entries(next)){
    if(value===undefined||value===null||(value===''&&key!=='text')||(['x','y','rotation'].includes(key)&&Number(value)===0)||(key==='scale'&&Number(value)===1))delete next[key];
  }
  if(Object.keys(next).length)all[id]=next;else delete all[id];
  return next;
}

export function resetElementOverride(slide,id){
  delete ensureElementOverrides(slide)[id];
}

export function applyElementOverride(node,override={}){
  if(!node?.style)return;
  const x=Number(override.x)||0,y=Number(override.y)||0,scale=Math.max(.2,Math.min(4,Number(override.scale)||1)),rotation=Math.max(-180,Math.min(180,Number(override.rotation)||0));
  node.style.translate=x||y?`${x}px ${y}px`:'';
  node.style.scale=scale!==1?String(scale):'';
  node.style.rotate=rotation?`${rotation}deg`:'';
  node.style.transformOrigin=override.transformOrigin||'center center';
  if(Number(override.fontSize)>0)node.style.fontSize=`${Math.max(8,Math.min(220,Number(override.fontSize)))}px`;else node.style.fontSize='';
  if(Number.isFinite(Number(override.opacity)))node.style.opacity=String(Math.max(.05,Math.min(1,Number(override.opacity))));
  if(Number.isFinite(Number(override.zIndex)))node.style.zIndex=String(Math.max(0,Math.min(99,Number(override.zIndex))));
  if(override.hidden===true)node.style.display='none';
  if(override.text!==undefined&&node.dataset.studioTextEditable==='true')node.textContent=String(override.text);
}

export function decorateEditableElements(root,slide,{renderMode='preview'}={}){
  if(!root?.querySelectorAll)return [];
  const overrides=ensureElementOverrides(slide);
  const hasManualLayout=Object.values(overrides).some(override=>override&&['x','y','scale','rotation','fontSize'].some(key=>override[key]!==undefined));
  if(root.dataset)root.dataset.studioManualLayout=String(hasManualLayout);
  const nodes=[...new Set(root.querySelectorAll(EDITABLE_SELECTOR))].filter(node=>!node.matches?.('[data-editor-only],svg *')&&!node.closest?.('[data-editor-only]'));
  const used=new Map();
  for(const node of nodes){
    let id=preferredId(node,root,slide);
    const count=used.get(id)||0;
    used.set(id,count+1);
    if(count)id=`${id}-${count+1}`;
    node.dataset.studioElementId=id;
    node.dataset.studioElementName=node.dataset.elementName||node.dataset.contentKey||node.dataset.layoutRole||node.getAttribute?.('aria-label')||String(node.textContent||'Élément').trim().slice(0,48)||'Élément';
    node.dataset.studioTextEditable=hasEditableText(node)?'true':'false';
    node.dataset.studioManualFont=String(Number(overrides[id]?.fontSize)>0);
    node.classList.add('studio-free-element');
    if(renderMode==='preview')node.tabIndex=0;
    applyElementOverride(node,overrides[id]);
  }
  return nodes;
}

export function previewElementOverride(root,id,patch){
  const escaped=globalThis.CSS?.escape?CSS.escape(id):String(id).replace(/["\\]/g,'\\$&');
  const node=root?.querySelector?.(`[data-studio-element-id="${escaped}"]`);
  if(!node)return null;
  const current={
    x:parseFloat(node.style.translate)||0,
    y:Number(String(node.style.translate||'').split(' ')[1]?.replace('px',''))||0,
    scale:parseFloat(node.style.scale)||1,
    rotation:parseFloat(node.style.rotate)||0,
    fontSize:parseFloat(node.style.fontSize)||undefined
  };
  applyElementOverride(node,{...current,...patch});
  return node;
}
