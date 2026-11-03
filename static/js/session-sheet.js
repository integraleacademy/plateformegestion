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

  showSection();
  window.addEventListener('hashchange', showSection);
  window.addEventListener('pageshow', event => { if (event.persisted) showSection(); });
})();
