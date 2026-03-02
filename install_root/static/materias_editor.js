(function () {
    if (window.__materiasEditorInitialized) return;
    window.__materiasEditorInitialized = true;

    // ---------------------------------------------------------------------------
    // Carga el catálogo desde data-catalog y rellena el <datalist> del editor
    // ---------------------------------------------------------------------------
    function buildCatalogSelect(block) {
        var dl = block.querySelector('datalist');
        if (!dl) return;
        if (dl.childElementCount > 0) return;  // ya poblado

        var raw = block.getAttribute("data-catalog") || "[]";
        var catalog = [];
        try { catalog = JSON.parse(raw); } catch (e) { console.warn("[materias] catalog JSON inválido", e); }

        if (!catalog.length) return;

        // Cuatrimestre del alumno (puede estar vacío -> mostrar todo)
        var studentCuat = (block.getAttribute("data-student-cuat") || "").replace(".0","").trim();

        catalog.forEach(function(item) {
            var c = (item.cuat || "").toString().replace(".0","").trim();
            // Si el alumno tiene cuatrimestre, solo mostrar las del mismo
            if (studentCuat && c && c !== studentCuat) return;
            var opt = document.createElement("option");
            opt.value = item.asignatura;
            opt.label = c ? item.asignatura + "  [Cuat. " + c + "]" : item.asignatura;
            dl.appendChild(opt);
        });
    }

    // Inicializar todos los bloques ya presentes en el DOM
    function initAllBlocks() {
        document.querySelectorAll(".materias-block").forEach(buildCatalogSelect);
    }

    // Utilidad: normaliza materia (acepta nombre/asignatura)
    function normalizeMateria(m) {
        m = m || {};
        var nombre = m.nombre != null ? m.nombre : m.asignatura;
        return {
            nombre: (nombre || "").toString(),
            asignatura: (nombre || "").toString()
        };
    }
    function normalizeMaterias(arr) {
        if (!Array.isArray(arr)) return [];
        return arr.map(normalizeMateria);
    }

    // Lee materias del DOM
    function getMateriasFromDOM(block) {
        var rows = block.querySelectorAll(".materia-row:not(.add-row)");
        var result = [];
        for (var i = 0; i < rows.length; i++) {
            var row = rows[i];
            var nombre = row.getAttribute("data-nombre") || "";
            result.push(normalizeMateria({ nombre: nombre }));
        }
        return result;
    }

    // Renderiza la lista de materias
    function renderMateriasList(block, materias) {
        var list = block.querySelector(".materias-list");
        if (!list) return;
        var addRow = list.querySelector(".add-row");
        var olds = list.querySelectorAll(".materia-row:not(.add-row)");
        for (var i = 0; i < olds.length; i++) list.removeChild(olds[i]);
        for (var j = 0; j < materias.length; j++) {
            var m = materias[j];
            var li = document.createElement("li");
            li.className = "materia-row";
            li.setAttribute("data-mindex", String(j));
            li.setAttribute("data-nombre", m.nombre || "");
            li.innerHTML =
                '<span class="materia-name">' + (m.nombre || "") + '</span>' +
                '<span class="materia-actions">' +
                '<button type="button" class="icon-btn materia-edit" title="Editar">✏️</button>' +
                '<button type="button" class="icon-btn materia-delete" title="Eliminar">🗑️</button>' +
                '</span>';
            list.insertBefore(li, addRow);
        }
    }

    // Abre el editor
    function openEditor(block, idx, materias) {
        var editor = block.querySelector(".materia-editor");
        var list = block.querySelector(".materias-list");
        if (!editor || !list) return;

        // Asegurar que el datalist tiene el catálogo
        buildCatalogSelect(block);

        var inp = editor.querySelector('input[name="mat_nombre"]');
        if (!inp) {
            console.error("[materias] Falta input nombre", { inp });
            return;
        }
        var mat = (idx >= 0 && idx < materias.length) ? normalizeMateria(materias[idx]) : { nombre: "" };
        inp.value = mat.nombre || "";
        editor.setAttribute("data-edit-index", String(idx));
        editor.style.display = "";
        list.style.display = "none";
    }

    function closeEditor(block) {
        var editor = block.querySelector(".materia-editor");
        var list = block.querySelector(".materias-list");
        if (!editor || !list) return;
        editor.style.display = "none";
        list.style.display = "";
    }

    // Handler global
    document.addEventListener("click", function (ev) {
        var target = ev.target || ev.srcElement;
        if (!(target instanceof Element)) return;

        var editBtn = target.closest(".materia-edit");
        var delBtn = target.closest(".materia-delete");
        var addBtn = target.closest(".materia-add");
        var saveBtn = target.closest(".materia-save");
        var cancelBtn = target.closest(".materia-cancel");
        if (!editBtn && !delBtn && !addBtn && !saveBtn && !cancelBtn) return;

        ev.preventDefault();
        ev.stopPropagation();

        var block = target.closest(".materias-block");
        if (!block) {
            console.warn("[materias] No se encontró .materias-block");
            return;
        }
        var textarea = block.querySelector('textarea[name="materias_raw"]');
        var editor = block.querySelector(".materia-editor");
        if (!editor) {
            console.warn("[materias] No se encontró .materia-editor");
            return;
        }

        var materias = [];
        try {
            materias = normalizeMaterias(getMateriasFromDOM(block));
        } catch (e) {
            console.error("[materias] Error en getMateriasFromDOM:", e);
            materias = [];
        }

        // EDITAR
        if (editBtn) {
            var rowE = editBtn.closest(".materia-row");
            if (!rowE) return;
            var idxE = parseInt(rowE.getAttribute("data-mindex") || "-1", 10);
            openEditor(block, idxE, materias);
            return;
        }

        // BORRAR
        if (delBtn) {
            if (!textarea) return;
            var rowD = delBtn.closest(".materia-row");
            if (!rowD) return;
            var idxD = parseInt(rowD.getAttribute("data-mindex") || "-1", 10);
            if (idxD >= 0 && idxD < materias.length) {
                materias.splice(idxD, 1);
                textarea.value = JSON.stringify(materias);
                renderMateriasList(block, materias);
            }
            return;
        }

        // AÑADIR
        if (addBtn) {
            openEditor(block, -1, materias);
            return;
        }

        // GUARDAR
        if (saveBtn) {
            if (!textarea) return;
            var inpNombre = editor.querySelector('input[name="mat_nombre"]');
            if (!inpNombre) {
                console.error("[materias] Falta input nombre en editor al guardar");
                return;
            }
            var idxS = parseInt(editor.getAttribute("data-edit-index") || "-1", 10);
            var nueva = normalizeMateria({ nombre: (inpNombre.value || "").trim() });
            if (!nueva.nombre) {
                alert("Selecciona o escribe una asignatura.");
                return;
            }
            if (idxS >= 0 && idxS < materias.length) {
                materias[idxS] = nueva;
            } else {
                materias.push(nueva);
            }
            textarea.value = JSON.stringify(materias);
            renderMateriasList(block, materias);
            closeEditor(block);
            return;
        }

        // CANCELAR
        if (cancelBtn) {
            closeEditor(block);
            return;
        }
    });

    // Inicializar catálogos al cargar
    initAllBlocks();
    console.log("[materias] Editor de materias inicializado");

    // Toast flotante inyectado en window.top (sobrevive re-renders de Streamlit)
    function getTopDoc() {
        try { return window.top.document; } catch(e) { return document; }
    }

    function ensureToastStyles() {
        var topDoc = getTopDoc();
        if (topDoc.getElementById("save-toast-styles")) return;
        var s = topDoc.createElement("style");
        s.id = "save-toast-styles";
        s.textContent = [
            ".st-save-toast{position:fixed;top:50%;left:50%;transform:translate(-50%,-50%) scale(1);",
            "padding:28px 40px;border-radius:12px;font-weight:700;font-size:1.1rem;text-align:center;",
            "z-index:9999999;box-shadow:0 8px 32px rgba(0,0,0,0.25);min-width:280px;max-width:480px;",
            "cursor:pointer;font-family:sans-serif;}",
            ".st-save-toast-success{background:#dcfce7;color:#14532d;border:2px solid #16a34a;}",
            ".st-save-toast-error{background:#fee2e2;color:#7f1d1d;border:2px solid #dc2626;}",
            ".st-save-toast small{display:block;font-size:0.75rem;font-weight:400;opacity:0.7;margin-top:6px;}"
        ].join("");
        topDoc.head.appendChild(s);
    }

    function getGlobalToast() {
        var topDoc = getTopDoc();
        ensureToastStyles();
        var t = topDoc.getElementById("global-save-toast");
        if (!t) {
            t = topDoc.createElement("div");
            t.id = "global-save-toast";
            topDoc.body.appendChild(t);
        }
        return t;
    }

    function showSaveToast(ok, messages) {
        // Resetear botón
        var btn = window._saveBtnRef;
        if (btn) {
            btn.textContent = "Guardar";
            btn.disabled = false;
        }

        var topDoc = getTopDoc();

        // Eliminar toast y overlay anteriores si existen
        var old = topDoc.getElementById("global-save-toast");
        if (old && old.parentNode) old.parentNode.removeChild(old);
        var oldOverlay = topDoc.getElementById("global-save-overlay");
        if (oldOverlay && oldOverlay.parentNode) oldOverlay.parentNode.removeChild(oldOverlay);

        ensureToastStyles();

        // Guardar removeToast en window.top para que sobreviva si el iframe se destruye
        window.top._stRemoveToast = function() {
            var topDoc = window.top.document;
            var t = topDoc.getElementById("global-save-toast");
            if (t && t.parentNode) t.parentNode.removeChild(t);
            var ov = topDoc.getElementById("global-save-overlay");
            if (ov && ov.parentNode) ov.parentNode.removeChild(ov);
            window.top._stRemoveToast = null;
        };

        // Overlay invisible: cualquier clic cierra el toast
        var overlay = topDoc.createElement("div");
        overlay.id = "global-save-overlay";
        overlay.style.cssText = "position:fixed;top:0;left:0;width:100%;height:100%;z-index:9999998;cursor:pointer;";
        overlay.setAttribute("onclick", "window._stRemoveToast && window._stRemoveToast()");
        topDoc.body.appendChild(overlay);

        var toast = topDoc.createElement("div");
        toast.id = "global-save-toast";
        toast.setAttribute("onclick", "window._stRemoveToast && window._stRemoveToast()");

        if (ok) {
            toast.className = "st-save-toast st-save-toast-success";
            toast.innerHTML = "Guardado correctamente.<br><small>Recarga la p\u00e1gina para ver los cambios actualizados. Clic para cerrar.</small>";
        } else {
            var msgs = Array.isArray(messages) ? messages : [];
            var displayMsg = msgs.length ? msgs.join(" ") : "Error al guardar.";
            toast.className = "st-save-toast st-save-toast-error";
            toast.innerHTML = "<strong>Error:</strong> " + displayMsg + "<br><small>Clic para cerrar</small>";
        }

        topDoc.body.appendChild(toast);
    }

    // Escucha mensajes de la API
    window.addEventListener("message", function(event) {
        var data = event.data || {};
        if (typeof data === "string") {
            try { data = JSON.parse(data); } catch (e) { return; }
        }
        if (data.type === "saveStatus") {
            showSaveToast(data.ok, data.messages || []);
        }
    });
})();
