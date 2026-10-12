(function () {
  const dialog = document.getElementById('framework-contract-date-dialog');
  if (!dialog) return;

  const dateForm = document.getElementById('framework-contract-date-form');
  const dateInput = document.getElementById('framework-contract-date');
  const description = document.getElementById('framework-contract-date-description');
  const submitButton = document.getElementById('framework-contract-date-submit');
  const replacementInput = document.getElementById('framework-contract-replace-request');

  document.querySelectorAll('form[data-framework-contract-action]').forEach((form) => {
    form.addEventListener('submit', (event) => {
      event.preventDefault();
      dateForm.action = form.action;
      dateInput.value = form.dataset.contractDate || '';
      replacementInput.value = form.dataset.replaceSignatureRequestId || '';
      description.textContent = form.dataset.contractMessage || '';
      submitButton.textContent = form.dataset.frameworkContractAction === 'send'
        ? 'Envoyer pour signature'
        : (replacementInput.value ? 'Annuler la demande et régénérer' : 'Générer le contrat');
      submitButton.disabled = false;
      dialog.showModal();
      dateInput.focus();
    });
  });

  document.getElementById('framework-contract-date-cancel').addEventListener('click', () => dialog.close());
  dateForm.addEventListener('submit', () => { submitButton.disabled = true; });
}());
