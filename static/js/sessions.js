const creation = document.getElementById('sessionModal');
const form = creation.querySelector('form');
const fields = form.elements;

function updateFields() {
  const dirigeant = fields.formation.value === 'DIRIGEANT';
  const afc = fields.formation.value === 'AFC_APS_SSIAP';
  document.getElementById('dirigeantLocationField').hidden = !dirigeant;
  document.getElementById('standardSessionDates').hidden = afc;
  document.getElementById('afcFields').hidden = !afc;
  fields.dirigeant_location.required = dirigeant;
  fields.dirigeant_location.disabled = !dirigeant;
  fields.contractual_end_date.required = afc;
  fields.contractual_end_date.disabled = !afc;
  fields.interruptions.disabled = !afc;
  for (const field of [fields.date_fin, fields.date_exam]) {
    field.required = !afc;
    field.disabled = afc;
  }
}
fields.formation.addEventListener('change', updateFields);
document.getElementById('openModal').addEventListener('click', () => {
  updateFields();
  creation.showModal();
});

for (const dialog of document.querySelectorAll('dialog')) {
  dialog.querySelectorAll('.dismiss, .cancel').forEach(button => {
    button.addEventListener('click', () => dialog.close());
  });
  dialog.addEventListener('click', event => {
    if (event.target === dialog) dialog.close();
  });
}

const rename = document.getElementById('renameModal');
const renameForm = document.getElementById('renameForm');
const nameInput = renameForm.elements.name;
const error = renameForm.querySelector('[role="alert"]');
let editing;
document.querySelectorAll('[data-rename-url]').forEach(button => {
  button.addEventListener('click', () => {
    editing = button;
    nameInput.value = button.closest('article').querySelector('.session-link').textContent;
    error.hidden = true;
    rename.showModal();
    nameInput.focus();
    nameInput.select();
  });
});
renameForm.addEventListener('submit', async event => {
  event.preventDefault();
  const button = editing;
  const submit = renameForm.querySelector('[type="submit"]');
  submit.disabled = true;
  error.hidden = true;
  try {
    const response = await fetch(button.dataset.renameUrl, {
      method:'POST', headers:{'Content-Type':'application/json'},
      body:JSON.stringify({name:nameInput.value.trim()})
    });
    const data = await response.json();
    if (!response.ok || !data.ok) throw new Error(data.error || data.message || 'Le nom n’a pas pu être enregistré.');
    button.closest('article').querySelector('.session-link').textContent = data.name;
    button.setAttribute('aria-label', 'Renommer la session ' + data.name);
    if (editing === button) rename.close();
  } catch (failure) {
    error.textContent = failure instanceof SyntaxError ? 'La session de connexion a expiré. Rechargez la page.' : failure.message;
    error.hidden = false;
  } finally {
    submit.disabled = false;
  }
});
