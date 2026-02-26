import html
from .popup_helpers import _clean
from constants import PROGRAM_ERASMUS_IN

def build_materias_blocks(e, programa: str, row_index_attr: str, idx_attr: str):
    """
    Devuelve:
      - has_materias: bool
      - materias_view_html: bloque de vista (detalles con lista de materias)
      - materias_edit_block: bloque de edición con lista + botones editar/borrar + añadir

    Solo actúa para Erasmus IN. Para otros programas -> (False, "", "").
    """

    prog_upper = (programa or "").upper()
    if prog_upper != PROGRAM_ERASMUS_IN.upper():
        return False, "", ""

    # ---- 1) Sacar materias_in del estudiante ----
    materias = e.get("materias_in") if isinstance(e, dict) else []
    if not isinstance(materias, list):
        materias = []

    has_materias = len(materias) > 0

    pills = []   # para la vista
    lines = []   # "Asignatura | Cuat | x"
    materias_items = []  # filas <li> editables

    import pandas as pd
    for j, m in enumerate(materias):
      if not isinstance(m, dict):
        continue

      asig = _clean(m.get("asignatura"))
      if not asig:
        continue

      # Mostrar el valor tal cual esté, sin filtrar ni comprobar NA
      cuat_val = m.get("cuat")
      if cuat_val is None:
        cuat_val = m.get("cuatrimestre")
      cuat = _clean(cuat_val)

      firmado_raw = str(m.get("firmado", "")).strip().lower()
      firmado_flag = "x" if firmado_raw in ("x", "1", "s", "si", "sí", "true", "t") else ""


      pills.append(f"<li class='mitem'>{html.escape(asig)}</li>")
      lines.append(f"{asig}")

      mid = f"{row_index_attr}-{idx_attr}-mat-{j}"
      mindex = len(materias_items)

      # --- AQUI AÑADES LA CLASE SI ES NUEVA ---
      clase = "materia-row"
      if m.get("nueva"):
        clase += " materia-nueva"

      materias_items.append(f"""
        <li class="{clase}"
          data-mindex="{mindex}"
          data-nombre="{html.escape(asig, quote=True)}"
          <span class="materia-name">{html.escape(asig)}</span>
          <span class="materia-actions">
            <button type="button" class="icon-btn materia-edit" title="Editar" data-mid="{mid}">✏️</button>
            <button type="button" class="icon-btn materia-delete" title="Eliminar" data-mid="{mid}">🗑️</button>
          </span>
        </li>
      """)

    materias_items_html = "\n".join(materias_items)

    # ---- 2) Bloque de VISTA ----
    if pills:
        materias_view_html = (
          "<details class='mat' role='group'>"
          f"<summary>📚 Materias ({len(pills)})</summary>"
          "<ul class='mlist'>" + "".join(pills) + "<li style='height:0.5rem;'></li></ul></details>"
        )
    else:
        materias_view_html = "<div class='no-mat'>Sin asignaturas asignadas</div>"

    # ---- 3) Texto raw para enviar en el form ----
    materias_text = "\n".join(lines)

    # ---- 4) Bloque de EDICIÓN (lista + editor + textarea) ----
    materias_edit_block = f"""
      <div class="field full materias-block">
        <label>Asignaturas (materias_in)</label>

        <ul class="materias-list">
          {materias_items_html}
          <li style="height:0.5rem;"></li>
          <li class="materia-row add-row">
            <button type="button" class="icon-btn materia-add"> Añadir asignatura</button>
          </li>
        </ul>

        <div class="materia-editor" style="display:none;">
          <div class="field">
            <label>Asignatura</label>
            <input type="text" name="mat_nombre" placeholder="Nombre de la asignatura">
          </div>

          <div class="materia-editor-row">
            <!-- Campos cuatrimestre y firmado eliminados para nuevas asignaturas -->
          </div>

          <div class="field acciones-materia" style="display:flex; justify-content:space-between; align-items:center; gap:1rem;">
            <div style="display:flex; flex-direction:row; gap:1rem; width:100%; justify-content:space-between; align-items:center;">
              <button type="button" class="materia-cancel" style="flex:1 1 0;">Cancelar</button>
              <button type="button" class="materia-save" style="flex:1 1 0;">Guardar</button>
            </div>
          </div>
        </div>
        <!-- Representación “raw” en texto, para enviar en el form -->
        <textarea name="materias_raw" style="display:none;">{html.escape(materias_text)}</textarea>
      </div>
    """

    return has_materias, materias_view_html, materias_edit_block
