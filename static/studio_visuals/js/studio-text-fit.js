let fontsReady;
const typography=new WeakMap();
export async function waitForStudioFonts(){
  if(!document.fonts)return;
  if(!fontsReady)fontsReady=Promise.all([
    document.fonts.load('800 48px StudioDisplay'),
    document.fonts.load('400 24px StudioText'),
    document.fonts.load('700 24px StudioText')
  ]).catch(()=>{}).then(()=>document.fonts.ready);
  await fontsReady;
}

function renderedLineCount(element,fontSize,lineHeight){
  if(document.createRange){
    const range=document.createRange();
    range.selectNodeContents(element);
    const vertical=String(getComputedStyle(element).writingMode||'').startsWith('vertical');
    const lineOffsets=[...range.getClientRects()].filter(rect=>rect.width>0&&rect.height>0).map(rect=>Math.round(vertical?rect.left:rect.top));
    if(lineOffsets.length)return new Set(lineOffsets).size;
  }
  const style=getComputedStyle(element);
  const padding=(parseFloat(style.paddingTop)||0)+(parseFloat(style.paddingBottom)||0);
  return Math.max(1,Math.round(Math.max(0,element.scrollHeight-padding)/(fontSize*lineHeight)));
}

function renderedTextHeight(element){
  // A grid item may stretch to its entire row: scrollHeight then measures the
  // empty row as well as the text. Only the rendered text needs to fit.
  if(document.createRange&&element.getBoundingClientRect){
    const range=document.createRange();range.selectNodeContents(element);
    const rect=range.getBoundingClientRect(),box=element.getBoundingClientRect();
    const zoom=box.height/(element.offsetHeight||box.height||1);
    if(rect.height>0)return rect.height/(zoom||1);
  }
  return element.scrollHeight;
}

export async function fitText({element,minFontSize,maxFontSize,maxLines,maxHeight,lineHeight}){
  await waitForStudioFonts();
  if(!element||element.hidden)return true;
  element.removeAttribute('data-fit-warning');
  element.style.lineHeight=String(lineHeight);
  element.style.boxSizing='border-box';
  let lo=Math.ceil(minFontSize),hi=Math.floor(maxFontSize),best=lo;
  while(lo<=hi){
    const mid=Math.floor((lo+hi)/2);
    element.style.fontSize=mid+'px';
    const lines=renderedLineCount(element,mid,lineHeight);
    const widthOk=element.scrollWidth<=element.clientWidth+3;
    const heightOk=renderedTextHeight(element)<=maxHeight+3;
    if(widthOk&&heightOk&&lines<=maxLines){best=mid;lo=mid+1}else hi=mid-1;
  }
  element.style.fontSize=best+'px';
  const bad=element.scrollWidth>element.clientWidth+3||renderedTextHeight(element)>maxHeight+3||renderedLineCount(element,best,lineHeight)>maxLines;
  if(bad)element.dataset.fitWarning='Texte trop long : réduisez-le.';
  return !bad;
}

function fitOptions(element,canvas){
  const kind=element.dataset.fit;
  const style=getComputedStyle(element);
  if(!typography.has(element))typography.set(element,{
    fontSize:parseFloat(style.fontSize)||24,
    lineHeight:(parseFloat(style.lineHeight)/(parseFloat(style.fontSize)||24))||1.2
  });
  const designed=typography.get(element);
  const canvasHeight=canvas.clientHeight||parseFloat(canvas.style.height)||1080;
  const parentHeight=element.parentElement?.clientHeight||canvasHeight;
  // The template owns its hierarchy. Fitting can reduce text, never inflate a
  // small date, button or caption to the generic title/metric maximum.
  const options=(minimum,lines,height)=>({
    minFontSize:Math.min(designed.fontSize,minimum),maxFontSize:designed.fontSize,
    maxLines:lines,maxHeight:height,
    lineHeight:designed.lineHeight
  });
  if(canvas.classList?.contains('social-cover')){
    if(kind==='title')return options(30,2,110);
    if(kind==='body')return options(16,2,60);
    return options(14,2,45);
  }
  if(canvas.classList?.contains('metier-layout')||canvas.classList?.contains('bts-layout')){
    const landscape=canvas.dataset.studioFormat==='linkedin_landscape';
    const story=canvas.dataset.studioFormat==='instagram_story';
    // A heading's parent often contains only that heading. Multiplying its
    // height by .62 was shrinking readable type even when the canvas had room.
    // Profession layouts reserve room for copy and keep a meaningful type floor.
    if(kind==='title')return options(landscape?30:42,5,landscape?210:story?520:360);
    if(kind==='body')return options(landscape?20:26,6,landscape?175:story?440:330);
    if(kind==='cta')return options(landscape?20:24,3,landscape?90:130);
    if(kind==='badge')return options(landscape?16:19,2,78);
    if(kind==='meta')return options(landscape?18:22,3,150);
  }
  if(kind==='badge'){
    const vertical=String(style.writingMode||'').startsWith('vertical');
    if(vertical)return options(8,2,Math.max(180,Math.min(520,parentHeight-40)));
    return options(8,2,54);
  }
  if(kind==='title')return options(24,5,Math.min(360,Math.max(110,parentHeight*.62)));
  if(kind==='cta')return options(12,3,96);
  if(kind==='metric')return options(20,3,Math.min(240,Math.max(80,parentHeight*.4)));
  if(kind==='meta')return options(12,3,Math.min(160,Math.max(64,parentHeight*.3)));
  return options(14,7,Math.min(300,Math.max(90,parentHeight*.5)));
}

function visibleElement(element){
  const style=getComputedStyle(element),rect=element.getBoundingClientRect();
  return style.display!=='none'&&style.visibility!=='hidden'&&Number(style.opacity)!==0&&rect.width>0&&rect.height>0;
}

export function fitLayoutFrame(root){
  const main=root.querySelector?.('[data-region="content"]');
  if(!main)return 1;
  main.style.transform='';
  main.removeAttribute('data-layout-scale');
  const frame=main.getBoundingClientRect();
  if(!frame.width||!frame.height)return 1;
  const artDirected=main.dataset.layoutFitMode==='art-directed';
  const rects=[...main.children]
    .filter(visibleElement)
    .filter(element=>!artDirected||getComputedStyle(element).position!=='absolute')
    .map(element=>element.getBoundingClientRect());
  const left=Math.min(frame.left,...rects.map(rect=>rect.left));
  const top=Math.min(frame.top,...rects.map(rect=>rect.top));
  const right=Math.max(frame.right,...rects.map(rect=>rect.right));
  const bottom=Math.max(frame.bottom,...rects.map(rect=>rect.bottom));
  // scrollWidth/Height are CSS pixels; DOMRects include the editor zoom.
  // Mixing them used to shrink otherwise valid compositions in the preview.
  const zoomX=frame.width/(main.offsetWidth||frame.width);
  const zoomY=frame.height/(main.offsetHeight||frame.height);
  const requiredWidth=artDirected?right-left:Math.max(main.scrollWidth*zoomX,right-left);
  const requiredHeight=artDirected?bottom-top:Math.max(main.scrollHeight*zoomY,bottom-top);
  const scale=Math.min(1,frame.width/Math.max(1,requiredWidth),frame.height/Math.max(1,requiredHeight));
  if(scale<.995){
    const fitted=Math.max(.72,scale);
    main.style.transform=`scale(${fitted.toFixed(4)})`;
    main.dataset.layoutScale=fitted.toFixed(3);
    return fitted;
  }
  return 1;
}

export async function fitSlide(root,{waitForPaint=true}={}){
  const canvas=root.matches?.('.social-studio-slide')?root:root.querySelector?.('.social-studio-slide')||root;
  await waitForStudioFonts();
  const jobs=[...root.querySelectorAll('[data-fit]')].filter(element=>element.dataset.studioManualFont!=='true').map(element=>fitText({element,...fitOptions(element,canvas)}));
  const results=await Promise.all(jobs);
  if(waitForPaint)await new Promise(resolve=>(globalThis.requestAnimationFrame||setTimeout)(resolve));
  if(canvas.dataset.studioManualLayout!=='true')fitLayoutFrame(root);
  return results;
}
