(function () {
    if (window.__materiasEditorInitialized) return;
    window.__materiasEditorInitialized = true;

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
        var nombreInput = editor.querySelector('input[name="mat_nombre"]');
        if (!nombreInput) {
            console.error("[materias] Falta input nombre", { nombreInput });
            return;
        }
        var mat = (idx >= 0 && idx < materias.length) ? normalizeMateria(materias[idx]) : { nombre: "" };
        nombreInput.value = mat.nombre || "";
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

        // Solo botones relevantes
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
            if (!textarea) {
                console.warn("[materias] No se encontró textarea[name='materias_raw']");
                return;
            }
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
            if (!textarea) {
                console.warn("[materias] No se encontró textarea[name='materias_raw']");
                return;
            }
            var nombreInput2 = editor.querySelector('input[name="mat_nombre"]');
            if (!nombreInput2) {
                console.error("[materias] Falta campo nombre en editor al guardar");
                return;
            }
            var idxS = parseInt(editor.getAttribute("data-edit-index") || "-1", 10);
            var nueva = normalizeMateria({ nombre: (nombreInput2.value || "").trim() });
            if (!nueva.nombre) {
                alert("La asignatura debe tener nombre.");
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

    // DEBUG: log de inicialización
    console.log("[materias] Editor de materias inicializado");

    // Escucha mensajes de la API y muestra errores
    window.addEventListener("message", function(event) {
        var data = event.data || {};
        if (typeof data === "string") {
            try { data = JSON.parse(data); } catch (e) { return; }
        }
        if (data.type === "saveStatus" && data.ok === false && Array.isArray(data.messages)) {
            var msg = data.messages.join("\n");
            alert(msg);
        }
    });
})();
