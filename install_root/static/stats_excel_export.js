window.saveExcelWithPywebview = function(base64Data, filename) {
    alert('[DEBUG] saveExcelWithPywebview llamada');
    var pw = null;
    try { pw = (window.top || window).pywebview; } catch(e) {}
    if (pw && pw.api && pw.api.save_file) {
        alert('[DEBUG] pywebview detectado, llamando a save_file');
        pw.api.save_file(base64Data, filename).then(function(result) {
            if (result && !result.ok && result.reason !== "cancelled") {
                alert("No se pudo guardar el archivo.");
            } else if (result && result.ok) {
                alert("Archivo guardado correctamente en: " + result.path);
            }
        }).catch(function(e) {
            alert("Error al guardar el archivo: " + e);
        });
        return true;
    }
    alert('[DEBUG] pywebview NO detectado, usando fallback');
    return false;
};
