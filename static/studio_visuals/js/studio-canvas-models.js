import {normalizeSlide,defaultContentForFormation,ALL_FORMATS} from './studio-store.js';

export function applyCanvasTemplate(project,template) {
  if(!template.isCanvas)throw new Error('Canevas attendu');
  const previous=project.slides[project.activeSlideIndex], formation=project.formation||'OR';
  const clone=value=>JSON.parse(JSON.stringify(value));
  const pages=template.pages||[{contentDefaults:template.contentDefaults}];
  const build=(page,index)=>normalizeSlide({formation,templateId:template.id,carouselPage:index,
    role:index===0?'cover':index===pages.length-1?'conclusion':'content',
    content:{...defaultContentForFormation(formation),...clone(page.contentDefaults),footer:clone(previous?.content?.footer||{}),_autoFormation:formation,_manual:false},
    options:{showSafeMargins:previous?.options?.showSafeMargins!==false,showPagination:false}});
  project.format=ALL_FORMATS[template.supportedFormats.includes(project.format?.id)?project.format.id:template.supportedFormats[0]];
  if(template.isCarousel){project.slides=pages.map(build);project.activeSlideIndex=0;project.name=template.name;}
  else project.slides[project.activeSlideIndex]=build(pages[0],0);
}
