export async function waitForStudioFonts(){
  if(!document.fonts)return;
  await Promise.all([
    document.fonts.load('800 48px StudioDisplay'),
    document.fonts.load('400 24px StudioText'),
    document.fonts.load('700 24px StudioText')
  ]).catch(()=>{});
  await document.fonts.ready;
}

function renderedLineCount(element,fontSize,lineHeight){
  if(document.createRange){
    const range=document.createRange();
    range.selectNodeContents(element);
    const tops=[...range.getClientRects()].filter(rect=>rect.width>0&&rect.height>0).map(rect=>Math.round(rect.top));
    if(tops.length)return new Set(tops).size;
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
  element.style.maxWidth='100%';
  element.style.boxSizing='border-box';
  let lo=minFontSize,hi=maxFontSize,best=minFontSize;
  while(lo<=hi){
    const mid=Math.floor((lo+hi)/2);
    element.style.fontSize=mid+'px';
    const lines=renderedLineCount(element,mid,lineHeight);
    const widthOk=element.scrollWidth<=element.clientWidth+1;
    const heightOk=element.scrollHeight<=maxHeight+1;
    if(widthOk&&heightOk&&lines<=maxLines){best=mid;lo=mid+1}else hi=mid-1;
  }
  element.style.fontSize=best+'px';
  const bad=element.scrollWidth>element.clientWidth+1||element.scrollHeight>maxHeight+1||renderedLineCount(element,best,lineHeight)>maxLines;
  if(bad)element.dataset.fitWarning='Texte trop long : réduisez-le.';
  return !bad;
}

function fitOptions(element,canvas){
  const kind=element.dataset.fit;
  const canvasHeight=canvas.clientHeight||parseFloat(canvas.style.height)||1080;
  const parentHeight=element.parentElement?.clientHeight||canvasHeight;
  if(kind==='badge')return {minFontSize:10,maxFontSize:14,maxLines:1,maxHeight:54,lineHeight:1};
  if(kind==='title')return {minFontSize:36,maxFontSize:96,maxLines:4,maxHeight:Math.min(330,Math.max(150,parentHeight*.48)),lineHeight:.96};
  if(kind==='cta')return {minFontSize:18,maxFontSize:30,maxLines:2,maxHeight:84,lineHeight:1.12};
  return {minFontSize:18,maxFontSize:32,maxLines:6,maxHeight:Math.min(250,Math.max(100,parentHeight*.42)),lineHeight:1.2};
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
  const rects=[...main.children].filter(visibleElement).map(element=>element.getBoundingClientRect());
  const left=Math.min(frame.left,...rects.map(rect=>rect.left));
  const top=Math.min(frame.top,...rects.map(rect=>rect.top));
  const right=Math.max(frame.right,...rects.map(rect=>rect.right));
  const bottom=Math.max(frame.bottom,...rects.map(rect=>rect.bottom));
  const requiredWidth=Math.max(main.scrollWidth,right-left);
  const requiredHeight=Math.max(main.scrollHeight,bottom-top);
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
  const jobs=[...root.querySelectorAll('[data-fit]')].map(element=>fitText({element,...fitOptions(element,canvas)}));
  const results=await Promise.all(jobs);
  await new Promise(resolve=>(globalThis.requestAnimationFrame||setTimeout)(resolve));
  fitLayoutFrame(root);
  return results;
}
