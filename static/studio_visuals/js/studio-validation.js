function measureUnscaledWidth(element){
  const canvas=element.closest('.social-studio-slide');
  const zoom=canvas?canvas.getBoundingClientRect().width/(canvas.offsetWidth||1):1;
  return element.getBoundingClientRect().width/(zoom||1);
}

function isVisible(element){
  const cs=getComputedStyle(element);
  const r=element.getBoundingClientRect();
  return cs.display!=='none'&&cs.visibility!=='hidden'&&Number(cs.opacity)!==0&&r.width>0&&r.height>0;
}

function isTextClipped(element){
  const canvas=element.closest('.social-studio-slide');
  const tolerance=3*(canvas?canvas.getBoundingClientRect().width/(canvas.offsetWidth||1):1);
  if(!document.createRange)return false;
  try{
    // Measure text only: selection/resize handles are deliberately outside the
    // text box and must not turn a valid selected template into a failed export.
    const walker=document.createTreeWalker(element,NodeFilter.SHOW_TEXT);
    const rects=[];
    for(let textNode=walker.nextNode();textNode;textNode=walker.nextNode()){
      if(!textNode.textContent.trim()||textNode.parentElement?.closest('[data-editor-only]'))continue;
      const range=document.createRange();range.selectNodeContents(textNode);
      const rect=range.getBoundingClientRect();
      // display:none descendants have a zero rectangle at the page origin.
      // They must not make a visible parent appear to contain clipped text.
      if(rect.width>0&&rect.height>0)rects.push(rect);
    }
    if(!rects.length)return false;
    const textRect={left:Math.min(...rects.map(r=>r.left)),right:Math.max(...rects.map(r=>r.right)),top:Math.min(...rects.map(r=>r.top)),bottom:Math.max(...rects.map(r=>r.bottom))};
    let ancestor=element;
    while(ancestor&&ancestor!==canvas){
      const ancestorStyle=getComputedStyle(ancestor);
      if([ancestorStyle.overflow,ancestorStyle.overflowX,ancestorStyle.overflowY].some(value=>['hidden','clip'].includes(value))){
        const rect=ancestor.getBoundingClientRect();
        if(textRect.left<rect.left-tolerance||textRect.top<rect.top-tolerance||textRect.right>rect.right+tolerance||textRect.bottom>rect.bottom+tolerance)return true;
      }
      ancestor=ancestor.parentElement;
    }
  }catch(_error){return false}
  return false;
}

export function isOutsideCanvas(element,canvas){
  const e=element.getBoundingClientRect(),c=canvas.getBoundingClientRect(),t=1;
  return e.left<c.left-t||e.top<c.top-t||e.right>c.right+t||e.bottom>c.bottom+t;
}

function isOutsideRegion(element,region){
  const e=element.getBoundingClientRect(),r=region.getBoundingClientRect(),t=2;
  return e.left<r.left-t||e.top<r.top-t||e.right>r.right+t||e.bottom>r.bottom+t;
}

function overflowMessage(el,canvas){
  const e=el.getBoundingClientRect(),c=canvas.getBoundingClientRect();
  const name=el.dataset.elementName||el.dataset.contentKey||el.dataset.layoutRole||'Élément';
  const bottom=Math.max(0,Math.round(e.bottom-c.bottom)),right=Math.max(0,Math.round(e.right-c.right)),top=Math.max(0,Math.round(c.top-e.top)),left=Math.max(0,Math.round(c.left-e.left));
  const px=Math.max(bottom,right,top,left);
  const side=bottom?'en bas':right?'à droite':top?'en haut':'à gauche';
  return `Le bloc « ${name} » dépasse de ${px} px ${side}.`;
}

function intersectionArea(a,b){
  const width=Math.max(0,Math.min(a.right,b.right)-Math.max(a.left,b.left));
  const height=Math.max(0,Math.min(a.bottom,b.bottom)-Math.max(a.top,b.top));
  return width*height;
}

function regionOverlap(canvas,first,second){
  if(!first||!second||!isVisible(first)||!isVisible(second))return false;
  const scale=(canvas.getBoundingClientRect().width/(parseFloat(canvas.style.width)||canvas.offsetWidth||1))||1;
  return intersectionArea(first.getBoundingClientRect(),second.getBoundingClientRect())>16*scale*scale;
}

export function validateStudioSlide(slideNode,options={}){
  const blockingErrors=[],warnings=[],info=[];
  const canvas=slideNode.matches?.('.social-studio-slide')?slideNode:slideNode.querySelector('.social-studio-slide')||slideNode;
  const w=parseInt(canvas.style.width||canvas.dataset.canvasWidth||canvas.dataset.width||canvas.offsetWidth,10);
  const h=parseInt(canvas.style.height||canvas.dataset.canvasHeight||canvas.dataset.height||canvas.offsetHeight,10);
  if(!w||!h)blockingErrors.push({message:'Dimensions de la scène invalides.',element:null});
  if(!canvas.dataset.renderedTemplateId)blockingErrors.push({message:'Renderer absent ou template non rendu.',element:canvas});

  const logos=[...canvas.querySelectorAll('.studio-brand-footer__logo,img[src*="logo-integrale"],img[alt*="Intégrale"]')].filter(el=>!el.closest('[data-editor-only]'));
  const uniqueLogos=[...new Set(logos)],logo=uniqueLogos[0];
  if(!logo)blockingErrors.push({message:'Logo officiel obligatoire absent.',element:canvas});
  else{
    if(uniqueLogos.length>1)blockingErrors.push({message:'Plusieurs logos détectés',element:logo});
    if(!logo.complete||!logo.naturalWidth)blockingErrors.push({message:'Le logo n’a pas pu être chargé.',element:logo});
    const width=measureUnscaledWidth(logo);
    const minimum=canvas.dataset.studioFormat==='linkedin_landscape'?48:72;
    if(width&&width<minimum)warnings.push({message:'Le logo est petit : agrandissez-le pour améliorer sa lisibilité.',element:logo});
  }
  if(!canvas.textContent.includes('Faites le premier pas vers votre futur métier'))blockingErrors.push({message:'Slogan obligatoire absent.',element:canvas});
  if(!canvas.querySelector('.sv-brand__formation'))blockingErrors.push({message:'Repère couleur de la formation absent.',element:canvas});

  for(const element of canvas.querySelectorAll('.sv-brand__slogan,.sv-brand__formation,.sv-footer__place,.sv-footer__site,.sv-footer__phone,.sv-footer__cta,.new-design [data-content-key],[data-fit]')){
    if(isVisible(element)&&isTextClipped(element))blockingErrors.push({message:`Le texte « ${element.dataset.elementName||element.textContent.trim()||'identité'} » est coupé.`,element});
  }

  const monitored=[...new Set([
    ...canvas.querySelectorAll('[data-exportable="true"]'),
    ...canvas.querySelectorAll('[data-layout-role]'),
    ...canvas.querySelectorAll('[data-fit]')
  ])].filter(el=>!el.closest('[data-editor-only]')&&isVisible(el));
  for(const el of monitored){
    if(isOutsideCanvas(el,canvas))blockingErrors.push({message:overflowMessage(el,canvas),element:el});
  }
  for(const el of canvas.querySelectorAll('[data-fit-warning]')){
    if(isVisible(el))blockingErrors.push({message:`Le texte « ${el.dataset.elementName||el.dataset.contentKey||'contenu'} » est trop long pour ce template.`,element:el});
  }

  const brand=canvas.querySelector('[data-region="brand"]'),content=canvas.querySelector('[data-region="content"]'),footer=canvas.querySelector('[data-region="footer"]');
  if(content?.dataset.layoutFitMode==='art-directed'){
    for(const element of content.querySelectorAll('[data-content-key]')){
      if(isVisible(element)&&isOutsideRegion(element,content))blockingErrors.push({message:`Le contenu « ${element.dataset.elementName||element.dataset.contentKey||'élément'} » sort de sa zone de composition.`,element});
    }
  }
  if(regionOverlap(canvas,brand,content))blockingErrors.push({message:'Le contenu chevauche la zone du logo.',element:content});
  if(regionOverlap(canvas,content,footer))blockingErrors.push({message:'Le contenu chevauche le pied de page.',element:content});
  if(regionOverlap(canvas,brand,footer))blockingErrors.push({message:'Le logo chevauche le pied de page.',element:brand});
  // Cover illustrations are decorative but still need their own visible area.
  // Pulling a cropped drawing inward must not hide the logo or the copy.
  for(const art of canvas.querySelectorAll('[data-cover-illustration]')){
    for(const [region,label] of [[brand,'le logo'],[content,'le texte'],[footer,'le pied de page']]){
      if(regionOverlap(canvas,art,region))blockingErrors.push({message:`L’illustration de couverture chevauche ${label}.`,element:art});
    }
  }

  const scale=(canvas.getBoundingClientRect().width/(w||canvas.offsetWidth||1))||1,safe=70*scale,c=canvas.getBoundingClientRect();
  canvas.querySelectorAll('[data-exportable="true"]').forEach(el=>{
    if(!isVisible(el)||isOutsideCanvas(el,canvas))return;
    const r=el.getBoundingClientRect();
    if(r.left<c.left+safe||r.top<c.top+safe||r.right>c.right-safe||r.bottom>c.bottom-safe)warnings.push({message:`Le bloc « ${el.dataset.elementName||'élément'} » est proche de la marge de sécurité.`,element:el});
  });
  if(canvas.textContent.match(/(Lieu|Début|Durée|Financement|Places)(?=\S)/))warnings.push({message:'Texte potentiellement concaténé détecté.',element:canvas});

  const dedupe=items=>items.filter((item,index)=>items.findIndex(other=>other.message===item.message)===index);
  const errors=dedupe(blockingErrors),notices=dedupe(warnings);
  if(!errors.length)info.push(
    {message:`Dimensions : ${w} × ${h}`},
    {message:'Logo chargé et taille correcte'},
    {message:'Slogan présent'},
    {message:`Couleur ${canvas.dataset.formation||'formation'} appliquée`},
    {message:'Blocs contenus dans le canevas'},
    {message:'Zones logo, contenu et pied de page séparées'}
  );
  return {blockingErrors:errors,warnings:notices,info};
}

export function validateProject(project){
  const warnings=[],slide=project.slides[project.activeSlideIndex],c=slide.content;
  if((c.title||'').length>90)warnings.push({type:'warning',message:`Titre trop long : réduisez-le de ${c.title.length-90} caractères.`});
  if(c._autoFormation&&c._autoFormation!==project.formation)warnings.push({type:'warning',message:`Le contenu actuel semble concerner ${c._autoFormation}, alors que la formation sélectionnée est ${project.formation}.`});
  return warnings;
}

export function validateRendered(root){
  const r=validateStudioSlide(root);
  return [...r.blockingErrors.map(x=>({type:'error',message:x.message,element:x.element})),...r.warnings.map(x=>({type:'warning',message:x.message,element:x.element}))];
}
