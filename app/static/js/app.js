'use strict';
// Progressive enhancements only: every financial mutation uses a server form.
const menuButton = document.getElementById('menu-button');
const sidebar = document.getElementById('sidebar');
function closeMenu() {
  sidebar.classList.remove('open');
  menuButton.setAttribute('aria-expanded', 'false');
}
menuButton.addEventListener('click', () => {
  const open = sidebar.classList.toggle('open');
  menuButton.setAttribute('aria-expanded', String(open));
  if (open) sidebar.querySelector('a').focus();
});
document.addEventListener('click', event => {
  if (!sidebar.contains(event.target) && !menuButton.contains(event.target)) closeMenu();
});
document.addEventListener('keydown', event => {
  if (event.key === 'Escape' && sidebar.classList.contains('open')) {
    closeMenu(); menuButton.focus();
  }
});
document.querySelectorAll('.dismiss-flash').forEach(button => {
  button.addEventListener('click', () => button.closest('.flash').remove());
});

const dialog = document.getElementById('confirm-dialog');
let pendingForm = null;
document.querySelectorAll('form[data-confirm]').forEach(form => {
  form.addEventListener('submit', event => {
    if (form.dataset.confirmed === 'true') return;
    event.preventDefault();
    pendingForm = form;
    dialog.showModal();
    document.getElementById('confirm-cancel').focus();
  });
});
document.getElementById('confirm-cancel').addEventListener('click', () => dialog.close());
document.getElementById('confirm-delete').addEventListener('click', () => {
  if (!pendingForm) return;
  pendingForm.dataset.confirmed = 'true';
  pendingForm.requestSubmit();
  dialog.close();
});
dialog.addEventListener('close', () => { pendingForm = null; });

const typeSelect = document.getElementById('transaction-type');
if (typeSelect) {
  const categorySelect = document.getElementById('transaction-category');
  function filterCategories() {
    for (const option of categorySelect.options) {
      if (!option.dataset.type) continue;
      option.hidden = option.dataset.type !== typeSelect.value;
      option.disabled = option.hidden;
      if (option.hidden && option.selected) categorySelect.value = '';
    }
  }
  typeSelect.addEventListener('change', filterCategories);
  filterCategories();
}
const periodSelect = document.getElementById('analytics-period');
if (periodSelect) {
  function updatePeriod() {
    document.querySelectorAll('.custom-period').forEach(label => {
      label.hidden = periodSelect.value !== 'custom';
      label.querySelector('input').required = periodSelect.value === 'custom';
    });
  }
  periodSelect.addEventListener('change', updatePeriod);
  updatePeriod();
}
