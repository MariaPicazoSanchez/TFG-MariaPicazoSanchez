# popup_materias.py
import html

from popup_helpers import _clean


def build_materias_blocks(e, programa: str, row_index_attr: str, idx_attr: str):
    """
    Construye:
      - has_materias: bool
      - materias_view_html: HTML para la vista (píldoras / 'Sin asignaturas...')
      - materias_edit_block: bloque HTML del editor de materias

    Ahora mismo SOLO hace cosas para 'Erasmus IN'.
    Para otros programas devuelve (False, "", "").
    """
    has_materias = False
    materias_view_html = ""
    materias_edit_block = ""

    if programa == "Erasmus IN":
        has_materias = True
        materias = e.get("materias_in") if isinstance(e, dict) else []
        if not isinstance(materias, list):
            materias = []

        pills = []
        lines = []
        for m in materias:
            if not isinstance(m, dict):
                continue
            asig = _clean(m.get("asignatura"))
            cuat = _clean(m.get("cuat"))
            if not asig:
                continue

            pill = html.escape(asig)
            if cuat:
                pill += f". Cuatri: {html.escape(cuat)}"
                lines.append(f"{asig} | {cuat}")
            else:
                lines.append(asig)
            pills.append(f"<li class='mitem'>{pill}</li>")

        if pills:
            materias_view_html = (
                "<details class='mat' role='group'>"
                f"<summary>📚 Materias ({len(pills)})</summary>"
                "<ul class='mlist'>" + "".join(pills) + "</ul></details>"
            )
        else:
            materias_view_html = "<div class='no-mat'>Sin asignaturas asignadas</div>"

        # materias_text a partir de las líneas
        materias_text = "\n".join(lines)

        materias_items = []
        for j, line in enumerate([l for l in materias_text.splitlines() if l.strip()]):
            nombre_asig = line.split("|", 1)[0].strip() or "Sin nombre"
            asig = html.escape(nombre_asig)
            mid = f"{row_index_attr}-{idx_attr}-mat-{j}"
            materias_items.append(f"""
              <li class="materia-row" data-mindex="{j}">
                <span class="materia-name">{asig}</span>
                <span class="materia-actions">
                  <button type="button" class="icon-btn materia-edit" title="Editar" data-mid="{mid}">✏️</button>
                  <button type="button" class="icon-btn materia-delete" title="Eliminar" data-mid="{mid}">🗑️</button>
                </span>
              </li>
            """)

        materias_items_html = "\n".join(materias_items)

        materias_edit_block = f"""
          <div class="field full materias-block">
            <label>Asignaturas (materias_in)</label>

            <ul class="materias-list">
              {materias_items_html}
              <li class="materia-row add-row">
                <button type="button" class="icon-btn materia-add">+ Añadir asignatura</button>
              </li>
            </ul>

            <div class="materia-editor" style="display:none;">
              <div class="field">
                <label>Asignatura</label>
                <input type="text" name="mat_nombre">
              </div>
              <div class="field">
                <label>Cuatrimestre</label>
                <select name="mat_cuat" class="slim-select">
                  <option value="">--</option>
                  <option value="1">1</option>
                  <option value="2">2</option>
                </select>
              </div>
              <div class="field">
                <label class="checkbox-label">
                  <input type="checkbox" name="mat_firmado">
                  Firmado
                </label>
              </div>
            </div>

            <textarea name="materias_raw" style="display:none;">{html.escape(materias_text)}</textarea>
          </div>
        """

    return has_materias, materias_view_html, materias_edit_block
