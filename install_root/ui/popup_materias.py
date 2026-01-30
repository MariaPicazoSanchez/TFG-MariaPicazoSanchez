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

    for j, m in enumerate(materias):
      if not isinstance(m, dict):
        continue

      asig = _clean(m.get("asignatura"))
      if not asig:
        continue

      cuat = _clean(m.get("cuat") or m.get("cuatrimestre"))

      firmado_raw = str(m.get("firmado", "")).strip().lower()
      firmado_flag = "x" if firmado_raw in ("x", "1", "s", "si", "sí", "true", "t") else ""

      trozos = [asig]
      if cuat:
        trozos.append(f"Cuatri: {cuat}")
      trozos.append("Firmado" if firmado_flag == "x" else "No firmado")
      display_txt = " · ".join(trozos)

      pills.append(f"<li class='mitem'>{html.escape(display_txt)}</li>")
      lines.append(f"{asig} | {cuat} | {firmado_flag}")

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
          data-cuat="{html.escape(cuat or '', quote=True)}"
          data-firmado="{html.escape(firmado_flag, quote=True)}">
          <span class="materia-name">{html.escape(display_txt)}</span>
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
            "<ul class='mlist'>" + "".join(pills) + "</ul></details>"
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
            <div class="field">
              <label>Cuatrimestre</label>
              <select name="mat_cuat" class="slim-select">
                <option value="">-</option>
                <option value="1">1</option>
                <option value="2">2</option>
              </select>
            </div>

            <div class="field field-firmado">
              <label class="firmado-toggle">
                <input type="checkbox" name="mat_firmado">
                <span class="firmado-pill">Firmado</span>
              </label>
            </div>
          </div>

          <div class="field acciones-materia">
            <button type="button" class="materia-save">Guardar</button>
            <button type="button" class="materia-cancel">Cancelar</button>
          </div>
        </div>
        <!-- Representación “raw” en texto, para enviar en el form -->
        <textarea name="materias_raw" style="display:none;">{html.escape(materias_text)}</textarea>
      </div>
    """

    return has_materias, materias_view_html, materias_edit_block
