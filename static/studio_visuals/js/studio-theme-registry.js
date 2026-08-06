export const FORMATION_THEME_ALIASES=Object.freeze({DESP:'DIRIGEANT',DIRIGEANT:'DIRIGEANT',APS:'APS',A3P:'A3P',SSIAP:'SSIAP',VTC:'VTC'});
export function getFormationTheme(formation,themes={}){const key=FORMATION_THEME_ALIASES[String(formation||'').trim().toUpperCase()]||'APS';return themes[key]||themes.APS||{};}
export async function loadThemeRegistry(){const themes=await fetch('/static/studio_visuals/data/themes.json').then(r=>r.json());themes.DESP=themes.DIRIGEANT;return themes;}
