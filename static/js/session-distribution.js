document.querySelectorAll('input[data-gestion-only]').forEach(input => {
  const status = input.closest('.session-distribution').querySelector('[role="status"]');
  const editor = document.querySelector('#editSessionDialog [name="catalogue_gestion_only"]');
  const marker = editor?.form.elements.namedItem('catalogue_scope_form');

  input.addEventListener('change', async () => {
    const enabled = input.checked;
    input.disabled = true;
    if (editor) {
      editor.disabled = true;
      marker.disabled = true;
    }
    status.textContent = 'Enregistrement…';
    try {
      const response = await fetch(input.dataset.gestionOnly, {
        method: 'POST',
        headers: {'Content-Type': 'application/json', 'X-CSRF-Token': input.dataset.csrf},
        body: JSON.stringify({enabled})
      });
      if (!response.ok || (await response.json()).enabled !== enabled) throw new Error();
      input.defaultChecked = enabled;
      if (editor) {
        editor.defaultChecked = enabled;
        editor.checked = enabled;
      }
      status.textContent = 'Diffusion enregistrée.';
    } catch {
      input.checked = !enabled;
      status.textContent = 'Enregistrement impossible. Rechargez la page et réessayez.';
    } finally {
      input.disabled = false;
      if (editor) {
        editor.disabled = false;
        marker.disabled = false;
      }
    }
  });
});
