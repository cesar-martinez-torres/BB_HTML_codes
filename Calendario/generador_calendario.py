import tkinter as tk
from tkinter import filedialog, messagebox
import pandas as pd

current_output = ""

def generate_js_from_excel(filepath):
    try:
        df = pd.read_excel(filepath)
        if not {'tipo', 'titulo', 'fecha'}.issubset(df.columns):
            return "El archivo debe contener las columnas: tipo, titulo, fecha"

        def generate_js_dict(df, tipo):
            sub = df[df['tipo'] == tipo]
            entries = [f'  "{row["fecha"]}": "{row["titulo"]}"' for _, row in sub.iterrows()]
            if entries:
                return f'const {tipo}Days = {{\n' + ",\n".join(entries) + '\n};\n'
            else:
                return f'const {tipo}Days = {{}};\n'

        output_js = ''
        for t in ['class', 'task', 'info', 'exam']:
            output_js += generate_js_dict(df, t) + '\n'

        return output_js.strip()
    except Exception as e:
        return f"Error: {str(e)}"

def open_file():
    filepath = filedialog.askopenfilename(filetypes=[("Archivos Excel", "*.xlsx")])
    if not filepath:
        return
    global current_output
    current_output = generate_js_from_excel(filepath)
    text_output.delete("1.0", tk.END)
    text_output.insert(tk.END, current_output)

def copy_to_clipboard():
    if not current_output.strip():
        messagebox.showwarning("Sin contenido", "Primero carga un archivo Excel válido.")
        return
    root.clipboard_clear()
    root.clipboard_append(current_output)
    messagebox.showinfo("Copiado", "El código ha sido copiado al portapapeles.")

# Interfaz gráfica
root = tk.Tk()
root.title("Generador de código JavaScript para Calendario HTML")
root.geometry("900x600")

frame = tk.Frame(root)
frame.pack(pady=10)

btn_load = tk.Button(frame, text="Seleccionar archivo Excel", command=open_file)
btn_load.pack(side="left", padx=10)

btn_copy = tk.Button(frame, text="Copiar al portapapeles", command=copy_to_clipboard)
btn_copy.pack(side="left", padx=10)

text_output = tk.Text(root, wrap=tk.NONE, height=30, width=120)
text_output.pack(padx=10, pady=10)

root.mainloop()
