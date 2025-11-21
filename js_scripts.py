POPUP_LIVE_UPDATE_JS = r"""
document.addEventListener('submit', function (ev) {
  var form = ev.target;
  if (!form.classList || !form.classList.contains('edit-form')) return;

  // Tarjeta del estudiante
  var card = form.closest('.pitem');
  if (!card) return;

  function syncField(name) {
    var input = form.querySelector('[name="' + name + '"]');
    var span  = card.querySelector('[data-field="' + name + '"]');
    if (!input || !span) return;
    span.textContent = input.value.trim();
  }

  // Campos típicos
  syncField('email');
  syncField('curso');
  syncField('cuatrimestre');
  syncField('duracion_meses');
  syncField('gestion_LA');
  syncField('coordinador_destino');
  syncField('responsable');
  // Enlaces: podemos mostrar el texto (normalmente la URL)
  syncField('link_la');
  syncField('link_plan');
  syncField('ToR');

  // Nombre en la cabecera de la tarjeta
  var nombreInput = form.querySelector('[name="estudiante"]');
  if (nombreInput) {
    var nombre = nombreInput.value.trim() || '(sin nombre)';
    var nameEl = card.querySelector('.pname-text');
    if (nameEl) nameEl.textContent = nombre;
  }
});
"""
