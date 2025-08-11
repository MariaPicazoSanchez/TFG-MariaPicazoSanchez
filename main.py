from tkinter import Tk, Button, filedialog, messagebox
from extract_pdf import extraer_datos_pdf
from map_generator import generar_mapa
import os

def seleccionar_y_procesar_pdf():
    ruta_pdf = filedialog.askopenfilename(
        title="Selecciona un archivo PDF",
        filetypes=[("Archivos PDF", "*.pdf")]
    )
    
    if not ruta_pdf:
        return  # Usuario canceló

    try:
        print(f"Procesando: {ruta_pdf}")
        datos = extraer_datos_pdf(ruta_pdf)
        generar_mapa("output/datos_extraidos.json")
        messagebox.showinfo("Éxito", "Se ha generado el mapa con éxito.")

    except Exception as e:
        print(f"Error: {e}")
        messagebox.showerror("Error", f"Hubo un problema: {e}")

def lanzar_app():
    ventana = Tk()
    ventana.title("Visualizador de Traslados")
    ventana.geometry("350x150")

    boton = Button(ventana, text="Seleccionar archivo PDF", command=seleccionar_y_procesar_pdf)
    boton.pack(pady=50)

    ventana.mainloop()

if __name__ == "__main__":
    os.makedirs("output", exist_ok=True)
    lanzar_app()
