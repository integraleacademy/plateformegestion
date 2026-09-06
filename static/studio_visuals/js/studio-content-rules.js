export const STUDIO_SLOGAN='Faites le premier pas vers votre futur métier';
export const STUDIO_CTA='Parlons de votre projet';
const normalized=value=>String(value||'').normalize('NFD').replace(/[\u0300-\u036f]/g,'').toLowerCase().replace(/[^a-z0-9]/g,'');
export function isStudioSlogan(value){return normalized(value)===normalized(STUDIO_SLOGAN)}
export function uniqueSignatureContent(content={}){
  // Work on a render copy: opening an existing project never destroys its text.
  // Legacy defaults used the brand signature for the title, quote and CTA.
  const copy={...content};
  for(const key of ['title','quote','cta','introduction','question','explanation']){
    if(!isStudioSlogan(copy[key]))continue;
    copy[key]=key==='cta'?STUDIO_CTA:key==='title'?'Construisez votre avenir avec Intégrale Academy':key==='quote'?'Un nouveau métier. Une nouvelle perspective.':'Une équipe à vos côtés pour concrétiser votre projet.';
  }
  return copy;
}
