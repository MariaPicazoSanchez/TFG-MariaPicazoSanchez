POPUP_SAVE_STATUS_SCRIPT = """
<script>
(function() {
  // Evitamos enganchar el listener varias veces
  if (window.__alEditSubmitInit) return;
  window.__alEditSubmitInit = true;

  document.addEventListener('submit', function(ev) {
    var form = ev.target;
    if (!form.classList || !form.classList.contains('edit-form')) return;

    // Buscamos el contenedor del estudiante
    var container = form.closest('.pcontent');
    if (!container) return;

    // Checkbox que controla el modo edición
    var toggle = container.querySelector('.edit-toggle');
    if (toggle) {
      toggle.checked = false; // 🔒 vuelve al modo vista
    }
  });
})();
</script>
"""
