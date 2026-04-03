
import html
import json

import pandas as pd

from .popup_helpers import _clean
from constants import PROGRAM_ERASMUS_IN


def build_materias_blocks(
    e,
    programa: str,
    row_index_attr: str,
    idx_attr: str,
    asignaturas_catalog: list | None = None,
) -> tuple[bool, str, str]:
    """
    Devuelve (has_materias, materias_view_html, materias_edit_block).
    Solo actúa para Erasmus IN; para otros programas devuelve (False, "", "").
    """
    if (programa or "").upper() != PROGRAM_ERASMUS_IN.upper():
        return False, "", ""

    items, es_investigacion = _parse_materias(e, asignaturas_catalog, row_index_attr, idx_attr)
    has_materias = bool(items)

    materias_view_html  = _build_view_block(items, es_investigacion)
    materias_edit_block = _build_edit_block(
        e, items, es_investigacion, asignaturas_catalog,
        row_index_attr, idx_attr,
    )

    return has_materias, materias_view_html, materias_edit_block


# ─────────────────────────────────────────────────────────────────────────────
# Parseo de materias
# ─────────────────────────────────────────────────────────────────────────────

def _safe_or(a, b):
    """Como 'a or b' tolerando pd.NA."""
    try:
        return a or b
    except TypeError:
        return b


def _parse_materias(
    e,
    asignaturas_catalog: list | None,
    row_index_attr: str,
    idx_attr: str,
) -> tuple[list[dict], bool]:
    """
    Devuelve (items, es_investigacion).
    Cada item contiene los datos de una materia y su HTML preconstruido.
    """
    materias = e.get("materias_in") if isinstance(e, dict) else []
    if not isinstance(materias, list):
        materias = []

    es_investigacion = any(
        m.get("asignatura", "").strip().lower() == "estancia investigación"
        for m in materias if isinstance(m, dict)
    )

    items = []
    for j, m in enumerate(materias):
        if not isinstance(m, dict):
            continue

        asig = _clean(m.get("asignatura"))
        # Sanear dato corrupto: si asig es un JSON guardado como string
        if asig and (asig.startswith("[") or asig.startswith("{")):
            try:
                parsed = json.loads(asig)
                if isinstance(parsed, list) and parsed and isinstance(parsed[0], dict):
                    asig = _clean(parsed[0].get("asignatura") or parsed[0].get("nombre")) or asig
                elif isinstance(parsed, dict):
                    asig = _clean(parsed.get("asignatura") or parsed.get("nombre")) or asig
            except Exception:
                pass
        if not asig:
            continue

        cuat_val = m.get("cuat") if m.get("cuat") is not None else m.get("cuatrimestre")
        cuat     = _clean(cuat_val)

        firmado_raw  = str(m.get("firmado", "")).strip().lower()
        firmado_flag = "x" if firmado_raw in ("x", "1", "s", "si", "sí", "true", "t") else ""

        la_val     = _clean(_safe_or(m.get("la"), m.get("link_la"))) or ""
        origen_val = _clean(m.get("origen")) or ""
        centro_val = _clean(_safe_or(m.get("centro"), m.get("universidadorigen"))) or ""

        cat_info = next((a for a in (asignaturas_catalog or []) if a.get("asignatura") == asig), None)
        matr     = cat_info.get("matriculados") if cat_info else None
        cupo     = cat_info.get("cupo")         if cat_info else None

        if matr is not None and cupo is not None:
            matr_suffix = f" <span style='font-weight:600;color:#777;'>({matr}/{cupo} matriculados)</span>"
        elif matr is not None:
            matr_suffix = f" <span style='font-weight:600;color:#777;'>({matr} matriculados)</span>"
        else:
            matr_suffix = " <span style='font-weight:600;color:#777;'>(sin datos)</span>"

        mid     = f"{row_index_attr}-{idx_attr}-mat-{j}"
        clase   = "materia-row" + (" materia-nueva" if m.get("nueva") else "")
        mat_json = json.dumps({
            "nombre": asig, "asignatura": asig,
            "cuat": cuat or "", "firmado": firmado_flag,
            "la": la_val, "origen": origen_val, "centro": centro_val,
            "matriculados": matr, "cupo": cupo,
        }, ensure_ascii=False)

        items.append({
            "asig": asig, "cuat": cuat or "", "firmado": firmado_flag,
            "la": la_val, "origen": origen_val, "centro": centro_val,
            "matr": matr, "cupo": cupo,
            "matr_suffix": matr_suffix,
            "mid": mid, "clase": clase, "mat_json": mat_json,
            "mindex": len(items),
        })

    return items, es_investigacion


# ─────────────────────────────────────────────────────────────────────────────
# Bloque de vista (solo lectura)
# ─────────────────────────────────────────────────────────────────────────────

def _build_view_block(items: list[dict], es_investigacion: bool) -> str:
    if es_investigacion:
        return "<div class='no-mat'>Alumno de estancia de investigación</div>"
    if not items:
        return "<div class='no-mat'>Sin asignaturas asignadas</div>"

    pills = "".join(
        f"<li class='mitem'>{html.escape(it['asig'])}{it['matr_suffix']}</li>"
        for it in items
    )
    return (
        "<details class='mat' role='group'>"
        f"<summary>📚 Materias ({len(items)})</summary>"
        "<ul class='mlist'>" + pills + "<li style='height:0.5rem;'></li></ul>"
        "</details>"
    )


# ─────────────────────────────────────────────────────────────────────────────
# Bloque de edición
# ─────────────────────────────────────────────────────────────────────────────

def _build_edit_block(
    e,
    items: list[dict],
    es_investigacion: bool,
    asignaturas_catalog: list | None,
    row_index_attr: str,
    idx_attr: str,
) -> str:
    materias_text = json.dumps(
        [{"asignatura": it["asig"], "cuat": it["cuat"], "firmado": it["firmado"],
          "la": it["la"], "origen": it["origen"], "centro": it["centro"]}
         for it in items],
        ensure_ascii=False,
    )

    if es_investigacion:
        return f"""
      <input type="hidden" name="is_investigacion" value="1">
      <div class="field full">
        <label>Tipo de estancia</label>
        <div class="no-mat">Estancia de investigación</div>
        <textarea name="materias_raw" style="display:none;">{html.escape(materias_text)}</textarea>
      </div>
    """

    items_html = "\n".join(
        f"""<li class="{it['clase']}"
          data-mindex="{it['mindex']}"
          data-nombre="{html.escape(it['asig'], quote=True)}"
          data-materia="{html.escape(it['mat_json'], quote=True)}">
          <span class="materia-name">{html.escape(it['asig'])}{it['matr_suffix']}</span>
          <span class="materia-actions">
            <button type="button" class="icon-btn materia-edit" title="Editar" data-mid="{it['mid']}">✏️</button>
            <button type="button" class="icon-btn materia-delete" title="Eliminar" data-mid="{it['mid']}">🗑️</button>
          </span>
        </li>"""
        for it in items
    )

    catalog_for_editor = _build_catalog_for_editor(e, asignaturas_catalog)
    catalog_json_escaped = json.dumps(catalog_for_editor, ensure_ascii=False).replace('"', '&quot;')

    student_cuat = _get_student_cuat(e)

    editor_html = f"""
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
        </div>"""

    add_row_html = """
          <li style="height:0.5rem;"></li>
          <li class="materia-row add-row">
            <button type="button" class="icon-btn materia-add"> Añadir asignatura</button>
          </li>"""

    return f"""
      <div class="field full materias-block"
           data-catalog="{catalog_json_escaped}"
           data-student-cuat="{html.escape(student_cuat, quote=True)}">
        <label>Asignaturas (materias_in)</label>
        <ul class="materias-list">
          {items_html}
          {add_row_html}
        </ul>
        {editor_html}
        <textarea name="materias_raw" style="display:none;">{html.escape(materias_text)}</textarea>
      </div>
    """


def _get_student_cuat(e) -> str:
    """Extrae el cuatrimestre del estudiante como string limpio."""
    raw = _clean(e.get("cuatrimestre") or e.get("cuat") if isinstance(e, dict) else None)
    if raw:
        try:
            return str(int(float(raw)))
        except Exception:
            pass
    return raw or ""


def _build_catalog_for_editor(e, asignaturas_catalog: list | None) -> list[dict]:
    """Filtra el catálogo según el cuatrimestre del alumno."""
    student_cuat = _get_student_cuat(e)
    result = []
    for a in (asignaturas_catalog or []):
        asig_name = a.get("asignatura", "")
        if asig_name.strip().lower() == "estancia investigación":
            continue
        a_cuat = str(a.get("cuat") or "").replace(".0", "").strip()
        if student_cuat and a_cuat and a_cuat != student_cuat:
            continue
        matr = a.get("matriculados")
        cupo = a.get("cupo")
        label = asig_name
        if not student_cuat and a_cuat:
            label += f" · C{a_cuat}"
        if matr is not None and cupo is not None:
            label += f" ({matr}/{cupo} matriculados)"
        elif matr is not None:
            label += f" ({matr} matriculados)"
        else:
            label += " (sin datos)"
        result.append({"asignatura": asig_name, "label": label, "cuat": a_cuat,
                        "matriculados": matr, "cupo": cupo})
    return result
