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
  return Math.max(1,Math.round(element.scrollHeight/(fontSize*lineHeight)));
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
  if(kind==='title')return {minFontSize:36,maxFontSize:96,maxLines:4,maxHeight:Math.min(330,Math.max(150,parentHeight*.48)),lineHeight:.96};
  if(kind==='cta')return {minFontSize:18,maxFontSize:30,maxLines:2,maxHeight:84,lineHeight:1.12};
  return {minFontSize:18,maxFontSize:32,maxLines:6,maxHeight:Math.min(250,Math.max(100,parentHeight*.42)),lineHeight:1.2};
}

export async function fitSlide(root){
  const canvas=root.matches?.('.social-studio-slide')?root:root.querySelector?.('.social-studio-slide')||root;
  await waitForStudioFonts();
  const jobs=[...root.querySelectorAll('[data-fit]')].map(element=>fitText({element,...fitOptions(element,canvas)}));
  return Promise.all(jobs);
}
