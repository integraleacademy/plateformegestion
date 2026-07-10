document.addEventListener('DOMContentLoaded', () => {
  const form = document.querySelector('.login-form');
  const submitButton = document.querySelector('.login-submit');
  const passwordInput = document.getElementById('password');
  const passwordToggle = document.querySelector('.password-toggle');

  if (passwordToggle && passwordInput) {
    passwordToggle.addEventListener('click', () => {
      const isPassword = passwordInput.type === 'password';
      passwordInput.type = isPassword ? 'text' : 'password';
      passwordToggle.classList.toggle('is-visible', isPassword);
      passwordToggle.setAttribute('aria-pressed', String(isPassword));
      passwordToggle.setAttribute('aria-label', isPassword ? 'Masquer le mot de passe' : 'Afficher le mot de passe');
      passwordInput.focus();
    });
  }

  if (form && submitButton) {
    form.addEventListener('submit', (event) => {
      if (!form.checkValidity()) {
        event.preventDefault();
        form.reportValidity();
        return;
      }

      submitButton.disabled = true;
      submitButton.classList.add('is-loading');
      submitButton.setAttribute('aria-busy', 'true');
    });
  }
});
