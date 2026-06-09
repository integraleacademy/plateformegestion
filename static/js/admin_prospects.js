const mailDialog = document.querySelector('#mail-dialog');
const mailContent = document.querySelector('#mail-content');
const mailLoading = document.querySelector('#mail-loading');
const mailtoLink = document.querySelector('#open-mailto');

document.querySelectorAll('.mail-action').forEach((button) => {
  button.addEventListener('click', async () => {
    document.querySelector('#mail-prospect').textContent = button.dataset.name;
    mailContent.value = '';
    mailLoading.hidden = false;
    mailDialog.showModal();
    try {
      const response = await fetch(button.dataset.mailUrl);
      if (!response.ok) throw new Error('Génération indisponible');
      const text = await response.text();
      mailContent.value = text;
      const lines = text.split('\n');
      const subjectLine = lines.find((line) => line.toLowerCase().startsWith('objet')) || 'Objet : Prise de contact';
      const subject = subjectLine.replace(/^objet\s*:\s*/i, '');
      mailtoLink.href = `mailto:${encodeURIComponent(button.dataset.email || '')}?subject=${encodeURIComponent(subject)}&body=${encodeURIComponent(text)}`;
    } catch (error) {
      mailContent.value = 'Impossible de préparer le mail pour le moment. Veuillez réessayer.';
    } finally {
      mailLoading.hidden = true;
    }
  });
});

document.querySelector('#copy-mail').addEventListener('click', async () => {
  await navigator.clipboard.writeText(mailContent.value);
  const button = document.querySelector('#copy-mail');
  button.textContent = 'Copié ✓';
  setTimeout(() => { button.textContent = 'Copier le texte'; }, 1400);
});

const editDialog = document.querySelector('#edit-dialog');
const editForm = document.querySelector('#edit-form');
document.querySelectorAll('.edit-action').forEach((button) => {
  button.addEventListener('click', () => {
    editForm.action = `/admin/prospects/${button.dataset.id}/update`;
    editForm.elements.commercial_status.value = button.dataset.status;
    editForm.elements.comment.value = button.dataset.comment;
    editDialog.showModal();
  });
});
document.querySelectorAll('.close-edit').forEach((button) => button.addEventListener('click', () => editDialog.close()));
