(() => {
    if (window.__materiasEditorInitialized) return;
    window.__materiasEditorInitialized = true;

    // ─── Constants ────────────────────────────────────────────────────────────
    const PROGRAMA_ERASMUS_IN = "erasmus in";
    const TOAST_STYLES_ID     = "save-toast-styles";
    const TOAST_ID            = "global-save-toast";
    const OVERLAY_ID          = "global-save-overlay";
    const nn = (v, fallback) => (v === null || v === undefined ? fallback : v);

    // ─── Catalog / Autocomplete ───────────────────────────────────────────────

    /**
     * Puebla el <datalist> nativo del input de asignaturas con las opciones del catálogo.
     * Así las sugerencias las renderiza el propio navegador, igual que las de universidad.
     */
    function buildCatalogSelect(block) {
        const inp = block.querySelector('input[name="mat_nombre"]');
        if (!inp) return;

        if (inp.dataset.autocompleteReady) return;
        inp.dataset.autocompleteReady = "1";

        let catalog = [];
        try {
            catalog = JSON.parse(block.getAttribute("data-catalog") || "[]");
        } catch (e) {
            console.warn("[materias] catalog JSON inválido", e);
        }
        if (!catalog.length) return;

        const datalistId = inp.getAttribute("list");
        const datalist = datalistId
            ? (block.querySelector(`datalist#${CSS.escape(datalistId)}`) || document.getElementById(datalistId))
            : null;
        if (!datalist) return;

        catalog.forEach(item => {
            const opt = document.createElement("option");
            opt.value = item.asignatura;
            if (item.matriculados !== null && item.matriculados !== undefined) {
                const cupo = (item.cupo !== null && item.cupo !== undefined) ? item.cupo : "?";
                opt.textContent = `${item.matriculados}/${cupo} matriculados`;
            }
            datalist.appendChild(opt);
        });
    }

    function initAllBlocks() {
        document.querySelectorAll(".materias-block").forEach(buildCatalogSelect);
    }

    // ─── Data helpers ─────────────────────────────────────────────────────────

    /** Normalises a materia object, accepting both nombre and asignatura as the name field. */
    function normalizeMateria(m = {}) {
        const nombre = m.nombre != null ? m.nombre : m.asignatura;
        const str    = s => nn(s, "").toString();
        const num    = v => (v !== null && v !== undefined && v !== "" && !isNaN(Number(v))) ? Number(v) : null;
        return {
            nombre:       str(nombre),
            asignatura:   str(nombre),
            cuat:         str(m.cuat),
            firmado:      str(m.firmado),
            la:           str(m.la || m.link_la),
            origen:       str(m.origen),
            centro:       str(m.centro),
            matriculados: num(m.matriculados),
            cupo:         num(m.cupo),
        };
    }

    const normalizeMaterias = arr => Array.isArray(arr) ? arr.map(normalizeMateria) : [];

    /** Reads materias from DOM rows, preserving extra fields stored in data-materia. */
    function getMateriasFromDOM(block) {
        return Array.from(block.querySelectorAll(".materia-row:not(.add-row)")).map(row => {
            let m = {};
            try { m = JSON.parse(row.getAttribute("data-materia") || "{}"); } catch (_) {}
            if (!m.nombre && !m.asignatura) m.nombre = nn(row.getAttribute("data-nombre"), "");
            return normalizeMateria(m);
        });
    }

    // ─── Rendering ────────────────────────────────────────────────────────────

    /** Re-renders the materia list items, preserving the add-row at the bottom. */
    function renderMateriasList(block, materias) {
        const list = block.querySelector(".materias-list");
        if (!list) return;

        let catalogMap = {};
        try {
            const cat = JSON.parse(block.getAttribute("data-catalog") || "[]");
            for (const item of cat) { if (item.asignatura) catalogMap[item.asignatura] = item; }
        } catch (_) {}

        const addRow = list.querySelector(".add-row");
        list.querySelectorAll(".materia-row:not(.add-row)").forEach(el => el.remove());

        for (const [j, m] of materias.entries()) {
            const info = catalogMap[m.nombre] || {};
            const matr = m.matriculados !== null && m.matriculados !== undefined
                ? m.matriculados
                : (info.matriculados !== null && info.matriculados !== undefined ? info.matriculados : null);
            const cupo = m.cupo !== null && m.cupo !== undefined
                ? m.cupo
                : (info.cupo !== null && info.cupo !== undefined ? info.cupo : null);
            let matrHtml = "";
            if (matr !== null && cupo !== null) {
                matrHtml = ` <span style="font-weight:600;color:#777;">(${matr}/${cupo} matriculados)</span>`;
            } else if (matr !== null) {
                matrHtml = ` <span style="font-weight:600;color:#777;">(${matr} matriculados)</span>`;
            } else {
                matrHtml = ` <span style="font-weight:600;color:#777;">(sin datos)</span>`;
            }

            const li = document.createElement("li");
            li.className = "materia-row";
            li.dataset.mindex  = j;
            li.dataset.nombre  = m.nombre;
            li.dataset.materia = JSON.stringify(m);
            li.innerHTML = `
                <span class="materia-name">${m.nombre}${matrHtml}</span>
                <span class="materia-actions">
                    <button type="button" class="icon-btn materia-edit"   title="Editar">✏️</button>
                    <button type="button" class="icon-btn materia-delete" title="Eliminar">🗑️</button>
                </span>`;
            list.insertBefore(li, addRow);
        }
    }

    // ─── Editor open / close ──────────────────────────────────────────────────

    function openEditor(block, idx, materias) {
        const editor = block.querySelector(".materia-editor");
        const list   = block.querySelector(".materias-list");
        if (!editor || !list) return;

        buildCatalogSelect(block);

        const inp = editor.querySelector('input[name="mat_nombre"]');
        if (!inp) { console.error("[materias] Falta input nombre"); return; }

        const mat = (idx >= 0 && idx < materias.length) ? normalizeMateria(materias[idx]) : { nombre: "" };
        inp.value = mat.nombre;
        editor.dataset.editIndex = idx;
        editor.style.display = "";
        list.style.display   = "none";
    }

    function closeEditor(block) {
        const editor = block.querySelector(".materia-editor");
        const list   = block.querySelector(".materias-list");
        if (!editor || !list) return;
        editor.style.display = "none";
        list.style.display   = "";
    }

    // ─── Click action handlers ────────────────────────────────────────────────

    function handleEdit(target, block, materias) {
        const row = target.closest(".materia-row");
        if (!row) return;
        openEditor(block, parseInt(nn(row.dataset.mindex, "-1"), 10), materias);
    }

    function handleDelete(target, block, textarea, materias) {
        if (!textarea) return;
        const row = target.closest(".materia-row");
        if (!row) return;
        const idx = parseInt(nn(row.dataset.mindex, "-1"), 10);
        if (idx >= 0 && idx < materias.length) {
            materias.splice(idx, 1);
            textarea.value = JSON.stringify(materias);
            renderMateriasList(block, materias);
        }
    }

    function handleSave(block, textarea, editor, materias) {
        if (!textarea) return;
        const inp = editor.querySelector('input[name="mat_nombre"]');
        if (!inp) { console.error("[materias] Falta input nombre al guardar"); return; }

        const nuevoNombre = inp.value.trim();
        if (!nuevoNombre) { alert("Selecciona o escribe una asignatura."); return; }

        const idx = parseInt(nn(editor.dataset.editIndex, "-1"), 10);
        const norm = s => s.trim().toLowerCase().normalize("NFD").replace(/[\u0300-\u036f]/g, "");
        const duplicado = materias.some((m, i) => {
            if (idx >= 0 && i === idx) return false;
            return norm(m.nombre || m.asignatura || "") === norm(nuevoNombre);
        });
        if (duplicado) {
            showSaveToast(false, [`El alumno ya tiene la asignatura "${nuevoNombre}".`]);
            return;
        }

        if (idx >= 0 && idx < materias.length) {
            materias[idx] = normalizeMateria({ ...materias[idx], nombre: nuevoNombre });
        } else {
            materias.push(normalizeMateria({ nombre: nuevoNombre }));
        }

        textarea.value = JSON.stringify(materias);
        renderMateriasList(block, materias);
        closeEditor(block);
    }

    // ─── Global click dispatcher ──────────────────────────────────────────────

    document.addEventListener("click", ev => {
        const target = ev.target;
        if (!(target instanceof Element)) return;

        const editBtn   = target.closest(".materia-edit");
        const delBtn    = target.closest(".materia-delete");
        const addBtn    = target.closest(".materia-add");
        const saveBtn   = target.closest(".materia-save");
        const cancelBtn = target.closest(".materia-cancel");

        if (!editBtn && !delBtn && !addBtn && !saveBtn && !cancelBtn) return;

        ev.preventDefault();
        ev.stopPropagation();

        const block = target.closest(".materias-block");
        if (!block) { console.warn("[materias] No se encontró .materias-block"); return; }

        const textarea = block.querySelector('textarea[name="materias_raw"]');
        const editor   = block.querySelector(".materia-editor");
        if (!editor) { console.warn("[materias] No se encontró .materia-editor"); return; }

        let materias;
        try {
            materias = normalizeMaterias(getMateriasFromDOM(block));
        } catch (e) {
            console.error("[materias] Error en getMateriasFromDOM:", e);
            materias = [];
        }

        if (editBtn)   return handleEdit(target, block, materias);
        if (delBtn)    return handleDelete(target, block, textarea, materias);
        if (addBtn)    return openEditor(block, -1, materias);
        if (saveBtn)   return handleSave(block, textarea, editor, materias);
        if (cancelBtn) return closeEditor(block);
    });

    // ─── Init ─────────────────────────────────────────────────────────────────

    initAllBlocks();

    // ─── Toast ────────────────────────────────────────────────────────────────

    const TOAST_CSS = `
        .st-save-toast {
            position: fixed; top: 50%; left: 50%;
            transform: translate(-50%, -50%) scale(1);
            padding: 28px 40px; border-radius: 12px;
            font-weight: 700; font-size: 1.1rem; text-align: center;
            z-index: 9999999; box-shadow: 0 8px 32px rgba(0,0,0,0.25);
            min-width: 280px; max-width: 480px;
            cursor: pointer; font-family: sans-serif;
        }
        .st-save-toast-success { background: #dcfce7; color: #14532d; border: 2px solid #16a34a; }
        .st-save-toast-error   { background: #fee2e2; color: #7f1d1d; border: 2px solid #dc2626; }
        .st-save-toast small   { display: block; font-size: 0.75rem; font-weight: 400; opacity: 0.7; margin-top: 6px; }
    `;

    function getTopDoc() {
        try { return window.top.document; } catch (_) { return document; }
    }

    function ensureToastStyles() {
        const topDoc = getTopDoc();
        if (topDoc.getElementById(TOAST_STYLES_ID)) return;
        const style = topDoc.createElement("style");
        style.id = TOAST_STYLES_ID;
        style.textContent = TOAST_CSS;
        topDoc.head.appendChild(style);
    }

    /** Removes the toast. If reload=true, recarga Streamlit para actualizar datos. */
    function removeToast(reload) {
        const topDoc = window.top.document;
        const toastEl = topDoc.getElementById(TOAST_ID);
        const ovlEl = topDoc.getElementById(OVERLAY_ID);
        if (toastEl) toastEl.remove();
        if (ovlEl) ovlEl.remove();
        window.top._stRemoveToast = null;
        if (reload) {
            try {
                const url = new URL(window.top.location.href);
                url.searchParams.set("student_saved", "1");
                window.top.location.href = url.toString();
            } catch(e) { window.top.location.reload(); }
        }
    }

    function showSaveToast(ok, messages = [], programa = "") {
        // Reset the save button as early as possible
        if (window._saveBtnRef) {
            window._saveBtnRef.textContent = "Guardar";
            window._saveBtnRef.disabled    = false;
        }

        const topDoc = getTopDoc();

        // Remove any stale toast / overlay
        const staleToast = topDoc.getElementById(TOAST_ID);
        const staleOverlay = topDoc.getElementById(OVERLAY_ID);
        if (staleToast) staleToast.remove();
        if (staleOverlay) staleOverlay.remove();

        ensureToastStyles();

        // Los onclick son autocontenidos en el contexto de window.top para que funcionen
        // aunque el iframe que creó este toast sea destruido por un re-render de Streamlit.
        const TID = "global-save-toast";
        const OID = "global-save-overlay";
        const closeOnlyScript = `(function(){var t=document.getElementById('${TID}');var o=document.getElementById('${OID}');if(t)t.remove();if(o)o.remove();})()`;
        const _sp = programa ? `u.searchParams.set('saved_program',${JSON.stringify(programa)});` : "";
        const closeAndReloadScript = `(function(){var t=document.getElementById('${TID}');var o=document.getElementById('${OID}');if(t)t.remove();if(o)o.remove();try{var u=new URL(location.href);u.searchParams.set('student_saved','1');u.searchParams.set('clear_cache','1');${_sp}location.href=u.toString();}catch(e){location.reload();}})()`;

        const overlay = topDoc.createElement("div");
        overlay.id = OVERLAY_ID;
        overlay.style.cssText = "position:fixed;top:0;left:0;width:100%;height:100%;z-index:9999998;cursor:pointer;";
        overlay.setAttribute("onclick", ok ? closeAndReloadScript : closeOnlyScript);
        topDoc.body.appendChild(overlay);

        const toast = topDoc.createElement("div");
        toast.id = TOAST_ID;
        toast.setAttribute("onclick", ok ? closeAndReloadScript : closeOnlyScript);

        if (ok) {
            toast.className = "st-save-toast st-save-toast-success";
            toast.innerHTML = `Guardado correctamente.<br><small>Clic para cerrar y actualizar.</small>`;
        } else {
            const displayMsg = messages.length ? messages.join(" ") : "Error al guardar.";
            toast.className  = "st-save-toast st-save-toast-error";
            toast.innerHTML  = `<strong>Error:</strong> ${displayMsg}<br><small>Clic para cerrar</small>`;
        }

        topDoc.body.appendChild(toast);
    }

    // ─── Form validation (Erasmus IN requires at least one subject) ───────────

    document.addEventListener("submit", ev => {
        const form = ev.target;
        if (!form || form.tagName !== "FORM") return;

        const progInput = form.querySelector('input[name="programa"]');
        if (!progInput || progInput.value.toLowerCase() !== PROGRAMA_ERASMUS_IN) return;

        // Alumnos de investigación no necesitan asignaturas
        const invInput = form.querySelector('input[name="is_investigacion"]');
        const isInvestigacion = invInput ? invInput.value === "1" : false;
        if (isInvestigacion) return;

        const textarea = form.querySelector('textarea[name="materias_raw"]');
        let materias = [];
        try { materias = JSON.parse(textarea ? nn(textarea.value, "[]") : "[]"); } catch (_) {}

        const hasSubjects = Array.isArray(materias) && materias.some(
            m => {
                const asig = m && m.asignatura ? m.asignatura : "";
                const nombre = m && m.nombre ? m.nombre : "";
                return (asig || nombre || "").toString().trim() !== "";
            }
        );

        if (!hasSubjects) {
            ev.preventDefault();
            ev.stopImmediatePropagation();
            clearTimeout(window._saveBtnTimeout);
            if (window._saveBtnRef) {
                window._saveBtnRef.disabled    = false;
                window._saveBtnRef.textContent = "Guardar";
            }
            showSaveToast(false, ["El alumno debe tener al menos una asignatura."]);
        }
    }, /* capture */ true);

    // ─── API response messages ────────────────────────────────────────────────

    window.addEventListener("message", ev => {
        let data = nn(ev.data, {});
        if (typeof data === "string") {
            try { data = JSON.parse(data); } catch (_) { return; }
        }
        if (data.type === "saveStatus") {
            showSaveToast(data.ok, nn(data.messages, []), nn(data.programa, ""));
        }
    });
})();