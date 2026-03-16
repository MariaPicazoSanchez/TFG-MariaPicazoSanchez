import html
import json
from .popup_helpers import _clean
from constants import PROGRAM_ERASMUS_IN

def build_materias_blocks(e, programa: str, row_index_attr: str, idx_attr: str, asignaturas_catalog: list = None):
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

      def _safe_or(a, b):
          """Como 'a or b' pero tolerando pd.NA (que lanza TypeError en __bool__)."""
          try:
              return a or b
          except TypeError:
              return b
      la_val = _clean(_safe_or(m.get("la"), m.get("link_la"))) or ""
      origen_val = _clean(m.get("origen")) or ""
      centro_val = _clean(_safe_or(m.get("centro"), m.get("universidadorigen"))) or ""

      # Buscar info de matriculados en el catálogo
      cat_info = next((a for a in (asignaturas_catalog or []) if a.get("asignatura") == asig), None)
      matr = cat_info.get("matriculados") if cat_info else None
      cupo = cat_info.get("cupo") if cat_info else None
      if matr is not None and cupo is not None:
          matr_suffix = f" <span style='font-weight:600;color:#777;'>" + f"({matr}/{cupo} matriculados)</span>"
      elif matr is not None:
          matr_suffix = f" <span style='font-weight:600;color:#777;'>({matr} matriculados)</span>"
      else:
          matr_suffix = " <span style='font-weight:600;color:#777;'>(sin datos)</span>"
      pills.append(f"<li class='mitem'>{html.escape(asig)}{matr_suffix}</li>")
      lines.append({
          "asignatura": asig,
          "cuat": cuat or "",
          "firmado": firmado_flag,
          "la": la_val,
          "origen": origen_val,
          "centro": centro_val,
      })

      mid = f"{row_index_attr}-{idx_attr}-mat-{j}"
      mindex = len(materias_items)

      # Serializar materia completa para recuperarla en el JS sin pérdidas
      materia_json = json.dumps({
          "nombre": asig, "asignatura": asig,
          "cuat": cuat or "", "firmado": firmado_flag,
          "la": la_val, "origen": origen_val, "centro": centro_val, "matriculados": matr, "cupo": cupo,
      }, ensure_ascii=False)

      # --- AQUI AÑADES LA CLASE SI ES NUEVA ---
      clase = "materia-row"
      if m.get("nueva"):
        clase += " materia-nueva"

      materias_items.append(f"""
        <li class="{clase}"
          data-mindex="{mindex}"
          data-nombre="{html.escape(asig, quote=True)}"
          data-materia="{html.escape(materia_json, quote=True)}">
          <span class="materia-name">{html.escape(asig)}{matr_suffix}</span>
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

    # ---- 3) Texto raw para enviar en el form (JSON con todos los campos) ----
    materias_text = json.dumps(lines, ensure_ascii=False)

    # ---- 4) Cuatrimestre del alumno ----
    student_cuat = _clean(
        e.get("cuatrimestre") or e.get("cuat")
        if isinstance(e, dict) else None
    )
    if student_cuat:
        try:
            student_cuat = str(int(float(student_cuat)))
        except Exception:
            pass

    # Catálogo para el editor: filtrado por cuat si el alumno lo tiene,
    # o todas con cuat indicado si no. Siempre incluye matriculados o "sin datos".
    catalog_for_editor = []
    for a in (asignaturas_catalog or []):
        asig_name = a.get("asignatura", "")
        a_cuat = str(a.get("cuat") or "").replace(".0", "").strip()
        matr_a = a.get("matriculados")
        cupo_a = a.get("cupo")
        if student_cuat and a_cuat and a_cuat != student_cuat:
            continue
        label = asig_name
        if not student_cuat and a_cuat:
            label += f" · C{a_cuat}"
        if matr_a is not None and cupo_a is not None:
            label += f" ({matr_a}/{cupo_a} matriculados)"
        elif matr_a is not None:
            label += f" ({matr_a} matriculados)"
        else:
            label += " (sin datos)"
        catalog_for_editor.append({
            "asignatura": asig_name,
            "label": label,
            "cuat": a_cuat,
            "matriculados": matr_a,
            "cupo": cupo_a,
        })

    catalog_json = json.dumps(catalog_for_editor, ensure_ascii=False)
    catalog_json_escaped = catalog_json.replace('"', '&quot;')

    # ---- 5) Bloque de EDICIÓN (lista + editor + textarea) ----
    materias_edit_block = f"""
      <div class="field full materias-block" data-catalog="{catalog_json_escaped}" data-student-cuat="{html.escape(student_cuat or '', quote=True)}">
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
            <input type="text" name="mat_nombre" class="mat-nombre-input"
                   list="mat-catalog-{row_index_attr}-{idx_attr}"
                   placeholder="Seleccionar o escribir asignatura"
                   autocomplete="off">
            <datalist id="mat-catalog-{row_index_attr}-{idx_attr}"></datalist>
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