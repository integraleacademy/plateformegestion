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
    const heightOk=element.scrollHeight<=maxHeight+3;
    if(widthOk&&heightOk&&lines<=maxLines){best=mid;lo=mid+1}else hi=mid-1;
  }
  element.style.fontSize=best+'px';
  const bad=element.scrollWidth>element.clientWidth+3||element.scrollHeight>maxHeight+3||renderedLineCount(element,best,lineHeight)>maxLines;
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

export async function fitSlide(root){
  const canvas=root.matches?.('.social-studio-slide')?root:root.querySelector?.('.social-studio-slide')||root;
  await waitForStudioFonts();
  const jobs=[...root.querySelectorAll('[data-fit]')].filter(element=>element.dataset.studioManualFont!=='true').map(element=>fitText({element,...fitOptions(element,canvas)}));
  const results=await Promise.all(jobs);
  await new Promise(resolve=>(globalThis.requestAnimationFrame||setTimeout)(resolve));
  if(canvas.dataset.studioManualLayout!=='true')fitLayoutFrame(root);
  return results;
}
