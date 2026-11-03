// Existing section and step fragments remain usable from emails, forms and history.
(() => {
  const panels = [...document.querySelectorAll('[data-sheet-panel]')];
  const links = [...document.querySelectorAll('[data-sheet-link]')];
  const overview = 'session-overview';

  function showSection() {
    const target = document.getElementById(location.hash.slice(1));
    const query = new URLSearchParams(location.search);
    const billing = document.getElementById('afc-dsf-section') &&
      ['billingUntil', 'periodStart', 'periodEnd', 'hourlyRate'].some(key => query.has(key));
    const section = target?.closest('[data-sheet-panel]')?.dataset.sheetPanel ||
      (billing && !location.hash ? 'afc-dsf-section' : overview);
    for (const panel of panels) panel.hidden = panel.dataset.sheetPanel !== section;
    for (const link of links) {
      if (link.dataset.sheetLink === section) link.setAttribute('aria-current', 'page');
      else link.removeAttribute('aria-current');
    }
    if (section === 'afc-dsf-section') {
      const billingAccordion = document.getElementById('afcDsfMainAccordion');
      if (billingAccordion) billingAccordion.open = true;
    }
    if (target?.closest('[data-sheet-panel]')) {
      // An ordinary link can target a panel which was hidden at navigation time.
      const destination = target.id === section ? links[0].closest('nav') : target;
      destination.scrollIntoView({block:'start', behavior:'instant'});
    }
  }

  const dialog = document.getElementById('editSessionDialog');
  const editLink = document.querySelector('[data-open-edit]');
  if (dialog && typeof dialog.showModal === 'function' && editLink) {
    editLink.addEventListener('click', event => {
      if (event.ctrlKey || event.metaKey || event.shiftKey || event.altKey) return;
      event.preventDefault();
      dialog.querySelector('form').reset();
      dialog.showModal();
    });
    dialog.querySelectorAll('[data-edit-close]').forEach(button => {
      button.addEventListener('click', () => dialog.close());
    });
    dialog.addEventListener('click', event => {
      if (event.target === dialog) dialog.close();
    });
    dialog.querySelector('[data-edit-location]').addEventListener('click', () => {
      dialog.close();
      const details = document.querySelector('#location-section details');
      details.open = true;
      requestAnimationFrame(() => details.querySelector('[name="location"]').focus());
    });
  }

  showSection();
  window.addEventListener('hashchange', showSection);
  window.addEventListener('pageshow', event => { if (event.persisted) showSection(); });
})();
