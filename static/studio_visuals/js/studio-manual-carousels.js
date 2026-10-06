import {normalizeSlide,defaultContentForFormation,normalizeSlideContentForTemplate,ALL_FORMATS,FORMATION_CONFIG} from './studio-store.js';

const clone=value=>JSON.parse(JSON.stringify(value));

export function applyManualCarousel(project,template) {
  if(!template.isManual||!template.isCarousel||!template.pages?.length)throw new Error('Carrousel illustré attendu');
  const previous=project.slides[project.activeSlideIndex],formation=template.formationPreset;
  project.formation=formation;
  project.themeId=FORMATION_CONFIG[formation].defaultThemeId;
  project.format=ALL_FORMATS[template.supportedFormats.includes(project.format?.id)?project.format.id:template.supportedFormats[0]];
  project.slides=template.pages.map((page,index)=>normalizeSlide({formation,templateId:template.id,carouselPage:index,
    role:index===0?'cover':index===template.pages.length-1?'conclusion':'content',
    logo:clone(previous?.logo||{}),
    content:{...defaultContentForFormation(formation),...clone(page.contentDefaults),footer:clone(previous?.content?.footer||{}),_autoFormation:formation,_manual:false},
    options:{showSafeMargins:previous?.options?.showSafeMargins!==false,showPagination:false}}));
  project.activeSlideIndex=0;
  project.name=template.name;
}

export function retargetManualCarousel(project,previous,next) {
  for(const slide of project.slides){
    if(slide.templateId!==previous.id)continue;
    slide.templateId=next.id;slide.layoutVariantId=next.id;
    slide.content._autoFormation=next.formationPreset;
    normalizeSlideContentForTemplate(slide,next);
  }
}
