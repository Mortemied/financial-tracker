'use strict';
(() => {
  const dialog = document.getElementById('quick-dialog');
  if (!dialog) return;
  const form = document.getElementById('quick-form');
  const type = document.getElementById('quick-type');
  const category = document.getElementById('quick-category');
  const error = document.getElementById('quick-error');
  const submit = document.getElementById('quick-submit');
  const messages = document.getElementById('v2-messages');
  function syncCategories() {
    for (const option of category.options) {
      if (!option.dataset.type) continue;
      option.hidden = option.dataset.type !== type.value;
      option.disabled = option.hidden;
    }
    if (category.selectedOptions[0]?.disabled) category.value = '';
    try {
      const saved = localStorage.getItem('finance-category-' + type.value);
      if (!category.value && [...category.options].some(o => o.value === saved && !o.disabled)) category.value = saved;
    } catch (_) { /* Browser storage may be unavailable; the form still works. */ }
  }
  type.addEventListener('change', () => { category.value = ''; syncCategories(); });
  document.querySelectorAll('[data-quick-open]').forEach(button => button.addEventListener('click', () => {
    error.hidden = true;
    syncCategories();
    dialog.showModal();
    form.elements.amount.focus();
  }));
  document.querySelectorAll('[data-quick-close]').forEach(button => button.addEventListener('click', () => dialog.close()));
  form.addEventListener('submit', async event => {
    event.preventDefault();
    if (submit.disabled) return;
    const label = submit.textContent;
    submit.disabled = true; submit.textContent = submit.dataset.loading;
    error.hidden = true;
    try {
      const response = await fetch(form.action, { method: 'POST', body: new FormData(form), headers: { 'Accept':'application/json' } });
      const result = await response.json();
      if (!response.ok || !result.ok) throw new Error(result.error || messages.dataset.network);
      try { localStorage.setItem('finance-category-' + type.value, category.value); } catch (_) {}
      dialog.close();
      location.reload();
    } catch (failure) {
      error.textContent = (failure instanceof SyntaxError || failure instanceof TypeError) ? messages.dataset.network : failure.message;
      error.hidden = false;
      submit.disabled = false; submit.textContent = label;
    }
  });
  document.querySelectorAll('[data-undo-seconds]').forEach(undo => {
    setTimeout(() => {
      undo.querySelector('button').disabled = true;
      undo.querySelector('button').textContent = messages.dataset.undoExpired;
    }, Number(undo.dataset.undoSeconds) * 1000);
  });
})();

// Guard ordinary POST forms against accidental double taps; preserve back navigation.
document.addEventListener('submit', event => {
  const form = event.target;
  if (!(form instanceof HTMLFormElement) || form.id === 'quick-form' || form.method.toLowerCase() !== 'post' || event.defaultPrevented) return;
  if (form.dataset.submitting === 'true') { event.preventDefault(); return; }
  form.dataset.submitting = 'true';
  form.setAttribute('aria-busy', 'true');
  form.querySelectorAll('button:not([type="button"])').forEach(button => {
    if (!button.disabled) { button.dataset.releaseDisabled = 'true'; button.disabled = true; }
  });
});
window.addEventListener('pageshow', () => {
  document.querySelectorAll('form[data-submitting]').forEach(form => {
    delete form.dataset.submitting;
    form.removeAttribute('aria-busy');
    form.querySelectorAll('[data-release-disabled]').forEach(button => { button.disabled = false; delete button.dataset.releaseDisabled; });
  });
});
