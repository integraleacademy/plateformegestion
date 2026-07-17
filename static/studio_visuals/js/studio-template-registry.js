export async function loadTemplateRegistry(){return fetch('/static/studio_visuals/data/templates.json').then(r=>r.json());}
