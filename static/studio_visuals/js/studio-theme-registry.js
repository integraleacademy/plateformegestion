export async function loadThemeRegistry(){return fetch('/static/studio_visuals/data/themes.json').then(r=>r.json());}
