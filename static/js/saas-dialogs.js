(function () {
  const DIALOG_COPY = {
    alert: { eyebrow: 'Notification', title: 'Information', icon: 'i' },
    confirm: { eyebrow: 'Confirmation', title: 'Action à confirmer', icon: '?' },
    prompt: { eyebrow: 'Saisie requise', title: 'Compléter l’information', icon: '✎' },
  };
  let active = null;

  function ensure() {
    let root = document.getElementById('saas-dialog-root');
    if (root) return root;

    root = document.createElement('div');
    root.id = 'saas-dialog-root';
    root.className = 'saas-dialog-overlay';
    root.innerHTML = `
      <section class="saas-dialog" role="dialog" aria-modal="true" aria-labelledby="saas-dialog-title">
        <div class="saas-dialog__hero"><div class="saas-dialog__icon" id="saas-dialog-icon"></div></div>
        <div class="saas-dialog__content">
          <p class="saas-dialog__eyebrow" id="saas-dialog-eyebrow"></p>
          <h2 class="saas-dialog__title" id="saas-dialog-title"></h2>
          <div class="saas-dialog__message" id="saas-dialog-message"></div>
          <input class="saas-dialog__input" id="saas-dialog-input" type="text" />
        </div>
        <div class="saas-dialog__actions">
          <button type="button" class="saas-dialog__btn saas-dialog__btn--ghost" data-dialog-cancel>Annuler</button>
          <button type="button" class="saas-dialog__btn saas-dialog__btn--primary" data-dialog-ok>OK</button>
        </div>
      </section>`;
    document.body.appendChild(root);
    return root;
  }

  function show(type, message, opts = {}) {
    return new Promise((resolve) => {
      const root = ensure();
      const copy = DIALOG_COPY[type] || DIALOG_COPY.alert;
      const ok = root.querySelector('[data-dialog-ok]');
      const cancel = root.querySelector('[data-dialog-cancel]');
      const input = root.querySelector('#saas-dialog-input');

      root.querySelector('#saas-dialog-eyebrow').textContent = opts.eyebrow || copy.eyebrow;
      root.querySelector('#saas-dialog-title').textContent = opts.title || copy.title;
      root.querySelector('#saas-dialog-icon').textContent = opts.icon || copy.icon;
      root.querySelector('#saas-dialog-message').textContent = String(message || '');
      input.style.display = type === 'prompt' ? 'block' : 'none';
      input.value = opts.defaultValue || '';
      cancel.style.display = type === 'alert' ? 'none' : 'inline-flex';
      ok.textContent = opts.okText || 'OK';
      cancel.textContent = opts.cancelText || 'Annuler';
      ok.classList.toggle('saas-dialog__btn--danger', !!opts.danger);
      active = { resolve, type };

      const close = (value) => {
        root.classList.remove('is-open');
        active = null;
        resolve(value);
      };

      ok.onclick = () => close(type === 'prompt' ? input.value : true);
      cancel.onclick = () => close(type === 'prompt' ? null : false);
      root.onclick = (event) => {
        if (event.target === root && type !== 'alert') close(type === 'prompt' ? null : false);
      };

      document.addEventListener('keydown', function esc(event) {
        if (!active) {
          document.removeEventListener('keydown', esc);
          return;
        }
        if (event.key === 'Escape') {
          document.removeEventListener('keydown', esc);
          close(type === 'prompt' ? null : false);
        }
        if (event.key === 'Enter' && document.activeElement !== cancel) {
          document.removeEventListener('keydown', esc);
          ok.click();
        }
      });

      root.classList.add('is-open');
      setTimeout(() => (type === 'prompt' ? input.focus() : ok.focus()), 30);
    });
  }

  window.SaasDialog = {
    alert: (message, options) => show('alert', message, options),
    confirm: (message, options) => show('confirm', message, options),
    prompt: (message, defaultValue, options) => show('prompt', message, Object.assign({ defaultValue }, options)),
  };

  window.alert = (message) => { show('alert', message); };
  window.prompt = (message, defaultValue) => { show('prompt', message, { defaultValue }); return null; };
  window.confirm = (message) => { show('confirm', message); return false; };

  document.addEventListener('submit', (event) => {
    const form = event.target;
    if (!form || form.dataset.saasConfirmed === '1') return;

    const attr = form.getAttribute('onsubmit') || '';
    const match = attr.match(/confirm\((['"])(.*?)\1\)/);
    if (!match) return;

    event.preventDefault();
    event.stopImmediatePropagation();
    show('confirm', match[2], { danger: /supprimer|réinitialiser|delete/i.test(match[2]) }).then((ok) => {
      if (!ok) return;
      form.dataset.saasConfirmed = '1';
      if (form.requestSubmit) form.requestSubmit();
      else form.submit();
      setTimeout(() => delete form.dataset.saasConfirmed, 0);
    });
  }, true);
}());
