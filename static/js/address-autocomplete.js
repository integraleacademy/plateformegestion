/* Address suggestions from IGN's current BAN geocoding endpoint.
 * The input remains editable, including when the service is unavailable.
 * API documentation: https://cartes.gouv.fr/aide/fr/guides-utilisateur/utiliser-les-services-de-la-geoplateforme/geocodage/
 */
document.addEventListener('DOMContentLoaded', () => {
  document.querySelectorAll('[data-address-autocomplete]').forEach(input => {
    const list = document.getElementById(input.getAttribute('aria-controls'));
    const status = document.getElementById(input.getAttribute('aria-describedby'));
    if (!list || !status || input.matches(':disabled')) return;
    let timer, controller, revision = 0, active = -1, selectedAddress = '';
    let suggestions = [];

    function cancelSearch() {
      clearTimeout(timer);
      if (controller) controller.abort();
      controller = null;
      revision += 1;
    }

    function close() {
      list.hidden = true;
      input.setAttribute('aria-expanded', 'false');
      input.removeAttribute('aria-activedescendant');
      active = -1;
    }

    function choose(index) {
      const address = suggestions[index];
      if (!address) return;
      cancelSearch();
      selectedAddress = address;
      input.value = address;
      close();
      input.dispatchEvent(new Event('input', {bubbles: true}));
      input.dispatchEvent(new Event('change', {bubbles: true}));
    }

    async function search(query, version) {
      const pending = new AbortController();
      controller = pending;
      const timeout = setTimeout(() => pending.abort(), 6000);
      try {
        const url = new URL('https://data.geopf.fr/geocodage/search');
        url.search = new URLSearchParams({q: query, index: 'address', autocomplete: '1', limit: '5'});
        const response = await fetch(url, {signal: pending.signal, credentials: 'omit', referrerPolicy: 'no-referrer'});
        if (!response.ok) throw new Error('Address service unavailable');
        const data = await response.json();
        if (!Array.isArray(data.features)) throw new Error('Invalid address response');
        if (version !== revision || document.activeElement !== input) return;
        suggestions = [...new Set(data.features.map(feature => feature.properties?.label)
          .filter(label => typeof label === 'string' && label.trim() && label.length <= input.maxLength))].slice(0, 5);
        list.replaceChildren();
        suggestions.forEach((address, index) => {
          const option = document.createElement('li');
          option.id = `${list.id}-${index}`;
          option.dataset.index = String(index);
          option.setAttribute('role', 'option');
          option.setAttribute('aria-selected', 'false');
          option.textContent = address;
          list.appendChild(option);
        });
        list.hidden = suggestions.length === 0;
        input.setAttribute('aria-expanded', String(suggestions.length > 0));
        status.textContent = suggestions.length
          ? 'Sélectionnez une adresse ou continuez la saisie.'
          : 'Aucune adresse trouvée. Précisez la ville ou saisissez votre adresse complète.';
      } catch (error) {
        if (version !== revision) return;
        close();
        status.textContent = 'Suggestions indisponibles. Vous pouvez saisir votre adresse complète.';
      } finally {
        clearTimeout(timeout);
        if (controller === pending) controller = null;
      }
    }

    function scheduleSearch(event) {
      cancelSearch();
      close();
      suggestions = [];
      list.replaceChildren();
      const query = input.value.trim();
      if (input.value === selectedAddress && selectedAddress) {
        status.textContent = 'Adresse sélectionnée. Vous pouvez ajouter un complément si nécessaire.';
        return;
      }
      if (query.length < 3 || event?.isComposing) {
        status.textContent = 'Saisissez au moins 3 caractères pour voir les adresses proposées.';
        return;
      }
      status.textContent = 'Recherche d’adresses…';
      const version = revision;
      timer = setTimeout(() => search(query, version), 300);
    }

    input.addEventListener('input', scheduleSearch);
    input.addEventListener('focus', scheduleSearch);
    input.addEventListener('compositionend', scheduleSearch);
    input.addEventListener('blur', () => { cancelSearch(); close(); status.textContent = ''; });
    input.addEventListener('keydown', event => {
      if (event.isComposing) return;
      if (event.key === 'Escape') {
        cancelSearch(); close(); status.textContent = ''; event.preventDefault();
      } else if (!list.hidden && ['ArrowDown', 'ArrowUp'].includes(event.key)) {
        event.preventDefault();
        active = event.key === 'ArrowDown' ? (active + 1) % suggestions.length
          : (active <= 0 ? suggestions.length - 1 : active - 1);
        Array.from(list.children).forEach((option, index) => option.setAttribute('aria-selected', String(index === active)));
        input.setAttribute('aria-activedescendant', list.children[active].id);
        list.children[active].scrollIntoView({block: 'nearest'});
      } else if (event.key === 'Enter' && !list.hidden) {
        event.preventDefault();
        choose(active < 0 ? 0 : active);
      }
    });
    // Keep focus on the combobox while clicking or tapping a suggestion.
    list.addEventListener('pointerdown', event => event.preventDefault());
    list.addEventListener('click', event => {
      const option = event.target.closest('[role="option"]');
      if (option && list.contains(option)) choose(Number(option.dataset.index));
    });
  });
});
