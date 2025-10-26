import tkinter as tk
from tkinter import ttk
from tkinter import messagebox
import tkinter.simpledialog as simpledialog
import os
import csv
from datetime import datetime
import copy 
import cv2 
from pyzbar import pyzbar
# NOTA: Se eliminan las importaciones de sonido ya que no se usarán

# ======================================================================
# --- 1. Base de Datos MAESTRA de Productos (Plantilla) ---
# ======================================================================
# ======================================================================
# --- 1. Base de Datos MAESTRA de Productos (Plantilla) ---
# ======================================================================
CATEGORIAS_DB = {
    'A': {
        'nombre': 'Papas',
        'subtipos': {
            '1': 'Saladas (Originales)',
            '2': 'Limón',
            '3': 'Picante' # <-- MODIFICADO
        }
    },
    'B': {
        'nombre': 'Galletas',
        'subtipos': {
            '1': 'Chocolate',
            '2': 'Vainilla',
        }
    },
    'C': {
        'nombre': 'Refrescos',
        'subtipos': {
            '1': 'Cola',
            '2': 'Fuze tea', # <-- MODIFICADO
            '3': 'Agua en lata'
        }
    },
    'D': {
        'nombre': 'Bebidas Alcohólicas',
        'subtipos': {
            '1': 'Cerveza',
            '2': 'Vino Tinto',
        }
    },
    # --- ¡NUEVA CATEGORÍA! ---
    'E': {
        'nombre': 'Extra',
        'subtipos': {
            '1': 'Palomitas',
            '2': 'Atún',
        }
    }
}

# ======================================================================
# --- 2. Base de Datos de Mapeo de Códigos de Barras (Clave: BARCODE) ---
# ======================================================================
BD_CODIGOS_BARRA = {
    # Papas (A)
    "87000000001": ("A", "1"), # Papas Saladas
    "87000000002": ("A", "2"), # Papas Limón
    "7500478026746": ("A", "3"), # Papas Picante <-- MODIFICADO

    # Galletas (B)
    "7501000392490": ("B", "1"), # Galletas Chocolate
    "7501000393022": ("B", "2"), # Galletas Vainilla

    # Refrescos (C)
    "7501055300075": ("C", "1"), # Refresco Cola
    "7501055358885": ("C", "2"), # Fuze tea <-- MODIFICADO
    "7501055308323": ("C", "3"), # Agua en lata

    # Bebidas Alcohólicas (D)
    "92000000101": ("D", "1"), # Cerveza
    "92000000102": ("D", "2"), # Vino Tinto

    # --- ¡NUEVOS CÓDIGOS PARA CATEGORÍA EXTRA (E)! ---
    "0081100001210": ("E", "1"), # Palomitas
    "7501045400860": ("E", "2"), # Atún
}

# ======================================================================
# --- 3. Nombre del Archivo de Registro CSV (¡NUEVO!) ---
# ======================================================================
REGISTRO_CSV_FILENAME = "registro_carritos_completados.csv"

# ======================================================================
# --- 4. Clase Principal de la Aplicación ---
# ======================================================================
class AppClasificacion:
    def __init__(self, root):
        self.root = root
        self.root.title("Software de Inventario de Carritos v5.6 (Registro Único)")
        self.root.geometry("600x650")
        self.style = ttk.Style()
        self.style.theme_use('clam')

        self.PASSWORD_ADMIN = "admin123"
        self.base_de_datos_carritos = {}
        
        self.HORAS_DEL_DIA = ["N/A"] + [f"{h:02d}:00" for h in range(24)]
        self.dialog_result = None 

        self.carrito_seleccionado = None
        self.limites_carrito_actual = {}      
        self.inventario_carrito_actual = {}   
        self.historial_carrito_total = []
        self.total_carrito_requerido = 0
        self.restantes_carrito_total = 0
        
        self.scan_cooldown = False 
        
        self.var_total_restante = tk.StringVar(value="Restantes por escanear: 0")
        
        self.main_frame = ttk.Frame(root, padding="10")
        self.main_frame.pack(fill=tk.BOTH, expand=True)

        self.mostrar_pantalla_menu_principal()

    def limpiar_frame_principal(self):
        for widget in self.main_frame.winfo_children():
            widget.destroy()

    # --- 0. Menú Principal (Selector de Carrito) ---
    # --- ¡MODIFICADO! Cambia el texto y comando del botón de reporte ---
    def mostrar_pantalla_menu_principal(self):
        self.limpiar_frame_principal()
        self.carrito_seleccionado = None 
        
        ttk.Label(self.main_frame, text="Menú Principal", 
                    font=("Helvetica", 16, "bold")).pack(pady=(10, 20))
        
        ttk.Button(
            self.main_frame, 
            text="⚙ Panel de Administrador (Gestionar Carritos)", 
            command=self.solicitar_password_admin
        ).pack(fill='x', padx=50, pady=(5, 15))

        ttk.Separator(self.main_frame, orient='horizontal').pack(fill='x', pady=10, padx=20)

        ttk.Label(self.main_frame, text="Selecciona el carrito para escanear:").pack(pady=10)

        carritos_frame = ttk.Frame(self.main_frame)
        carritos_frame.pack(fill='x', padx=50)

        if not self.base_de_datos_carritos:
            ttk.Label(carritos_frame, text="(No hay carritos configurados por el administrador)").pack()

        for nombre_carrito, cart_data in self.base_de_datos_carritos.items():
            limites_dict = cart_data.get('limites', {})
            completados = cart_data.get('completado_categorias', set())
            hora_entrega = cart_data.get('hora_entrega', 'N/A')
            
            btn_text = f"Carrito: {nombre_carrito} (Entrega: {hora_entrega})"
            btn_state = "disabled"

            if not limites_dict:
                btn_text += " (No configurado)"
            elif len(completados) > 0 and len(completados) == len(limites_dict):
                timestamp = cart_data.get('timestamp_completado', '')
                if timestamp:
                    btn_text += f" (Completado {timestamp})"
                else:
                    btn_text += " (Completado)"
            else:
                btn_state = "normal"
                total_req = sum(sum(sub.values()) for sub in limites_dict.values())
                total_ing = sum(sum(sub.values()) for sub in cart_data.get('inventario_realizado', {}).values())
                btn_text += f" (Progreso: {total_ing}/{total_req})"

            ttk.Button(
                carritos_frame, 
                text=btn_text, 
                state=btn_state,
                command=lambda k=nombre_carrito: self.iniciar_escaneo_total_carrito(k)
            ).pack(fill='x', pady=5)

        ttk.Separator(self.main_frame, orient='horizontal').pack(fill='x', pady=20, padx=20)
        
        # --- ¡BOTÓN MODIFICADO! ---
        ttk.Button(
            self.main_frame, 
            text="ℹ️ Mostrar Ubicación del Registro CSV", 
            command=self.mostrar_ubicacion_registro # Llama a la nueva función
        ).pack(fill='x', padx=50, pady=5)

    # --- 1. Flujo de Administrador ---
    def solicitar_password_admin(self):
        password = simpledialog.askstring("Acceso de Administrador", 
                                        "Introduce la contraseña:", 
                                        show='*')
        if password == self.PASSWORD_ADMIN:
            self.mostrar_pantalla_admin_gestion()
        elif password is not None:
            messagebox.showerror("Error", "Contraseña incorrecta.")

    def mostrar_pantalla_admin_gestion(self):
        self.limpiar_frame_principal()
        
        ttk.Label(self.main_frame, text="Panel de Administrador", 
                    font=("Helvetica", 16, "bold")).pack(pady=(10, 20))
        
        ttk.Label(self.main_frame, text="Gestionar Carritos de Vuelo:").pack(pady=10)

        frame_lista = ttk.LabelFrame(self.main_frame, text="Carritos Existentes")
        frame_lista.pack(fill='x', padx=50, pady=10)

        self.admin_lista_carritos = tk.Listbox(frame_lista, height=8)
        self.admin_lista_carritos.pack(fill='x', expand=True, padx=10, pady=10)

        for nombre_carrito, cart_data in self.base_de_datos_carritos.items():
            
            limites_dict = cart_data.get('limites', {})
            completados = cart_data.get('completado_categorias', set())
            timestamp = cart_data.get('timestamp_completado', '')
            
            texto_lista = nombre_carrito 

            if not limites_dict:
                texto_lista += " (No configurado)"
            elif len(completados) > 0 and len(completados) == len(limites_dict):
                if timestamp:
                    texto_lista += f" (Completado {timestamp})"
                else:
                    texto_lista += " (Completado)"
            else:
                texto_lista += " (Pendiente)" 

            self.admin_lista_carritos.insert(tk.END, texto_lista)

        frame_botones = ttk.Frame(self.main_frame)
        frame_botones.pack(fill='x', padx=50)

        ttk.Button(frame_botones, text="Crear Nuevo", command=self.admin_crear_carrito).pack(side=tk.LEFT, expand=True, padx=5)
        ttk.Button(frame_botones, text="Editar Selec.", command=self.admin_editar_carrito).pack(side=tk.LEFT, expand=True, padx=5)
        ttk.Button(frame_botones, text="Copiar Selec.", command=self.admin_copiar_carrito).pack(side=tk.LEFT, expand=True, padx=5)
        ttk.Button(frame_botones, text="Eliminar Selec.", command=self.admin_eliminar_carrito).pack(side=tk.LEFT, expand=True, padx=5)
        
        ttk.Separator(self.main_frame, orient='horizontal').pack(fill='x', pady=20, padx=20)
        ttk.Button(self.main_frame, text="Volver al Menú Principal", 
                    command=self.mostrar_pantalla_menu_principal).pack(pady=10)

    def pedir_hora_entrega(self, titulo_carrito):
        self.dialog_result = None 
        
        dialog = tk.Toplevel(self.root)
        dialog.title("Seleccionar Hora")
        dialog.geometry("350x150")
        dialog.transient(self.root) 
        dialog.grab_set() 
        dialog.resizable(False, False)

        frame = ttk.Frame(dialog, padding="10")
        frame.pack(fill=tk.BOTH, expand=True)

        ttk.Label(frame, text=f"Selecciona la hora de entrega para:\n'{titulo_carrito}'", 
                  font=("Helvetica", 10)).pack(pady=10)

        var_hora = tk.StringVar(value=self.HORAS_DEL_DIA[0]) 

        combo = ttk.Combobox(frame, textvariable=var_hora, values=self.HORAS_DEL_DIA, 
                             state="readonly", font=("Helvetica", 12), justify="center")
        combo.pack(pady=10, padx=10, fill='x')

        def _guardar_y_cerrar():
            self.dialog_result = var_hora.get() 
            dialog.destroy()
        
        dialog.protocol("WM_DELETE_WINDOW", _guardar_y_cerrar)

        btn_ok = ttk.Button(frame, text="Aceptar", command=_guardar_y_cerrar)
        btn_ok.pack(pady=10)
        
        dialog.update_idletasks()
        x = self.root.winfo_x() + (self.root.winfo_width() - dialog.winfo_width()) // 2
        y = self.root.winfo_y() + (self.root.winfo_height() - dialog.winfo_height()) // 2
        dialog.geometry(f"+{x}+{y}")

        self.root.wait_window(dialog) 
        
        return self.dialog_result

    def admin_crear_carrito(self):
        nombre = simpledialog.askstring("Crear Carrito", "Nombre del nuevo carrito (ej. Vuelo Nacional):")
        if not nombre:
            return
        if nombre in self.base_de_datos_carritos:
            messagebox.showerror("Error", "Ya existe un carrito con ese nombre.")
            return
            
        self.base_de_datos_carritos[nombre] = {
            'limites': {},
            'inventario_realizado': {},
            'completado_categorias': set(),
            'hora_entrega': "N/A", 
            'timestamp_completado': None 
        }
        
        self.admin_lista_carritos.insert(tk.END, f"{nombre} (No configurado)") 
        self.mostrar_pantalla_admin_edicion(nombre)

    def admin_copiar_carrito(self):
        try:
            seleccion = self.admin_lista_carritos.curselection()
            nombre_carrito_lista = self.admin_lista_carritos.get(seleccion[0])
            nombre_carrito_fuente = nombre_carrito_lista.split(" (")[0]
        except IndexError:
            messagebox.showwarning("Error", "Selecciona un carrito de la lista para copiar.")
            return
        
        source_data = self.base_de_datos_carritos[nombre_carrito_fuente]

        nombre_base = simpledialog.askstring("Copiar Carrito", "Nombre base para las copias:", initialvalue=f"{nombre_carrito_fuente} Copia")
        if not nombre_base: return
        
        num_copias = simpledialog.askinteger("Copiar Carrito", f"¿Cuántas copias de '{nombre_carrito_fuente}' quieres crear (1-10)?", minvalue=1, maxvalue=10)
        if not num_copias: return

        hora_entrega_copias = self.pedir_hora_entrega(f"todas las copias de {nombre_base}")
        if hora_entrega_copias is None: return 

        copias_creadas = 0
        for i in range(1, num_copias + 1):
            nuevo_nombre = f"{nombre_base} {i}"
            if nuevo_nombre in self.base_de_datos_carritos:
                messagebox.showwarning("Omisión", f"Ya existe un carrito llamado '{nuevo_nombre}'. Se omitirá.")
                continue
            
            nueva_data = {
                'limites': copy.deepcopy(source_data.get('limites', {})),
                'hora_entrega': hora_entrega_copias,
                'inventario_realizado': {}, 
                'completado_categorias': set(), 
                'timestamp_completado': None 
            }
            
            self.base_de_datos_carritos[nuevo_nombre] = nueva_data
            texto_lista_nuevo = f"{nuevo_nombre} (Pendiente)" if nueva_data['limites'] else f"{nuevo_nombre} (No configurado)"
            self.admin_lista_carritos.insert(tk.END, texto_lista_nuevo)
            copias_creadas += 1
        
        messagebox.showinfo("Éxito", f"Se crearon {copias_creadas} copias de '{nombre_carrito_fuente}'.")


    def admin_eliminar_carrito(self):
        try:
            seleccion = self.admin_lista_carritos.curselection()
            nombre_carrito_lista = self.admin_lista_carritos.get(seleccion[0])
            nombre_carrito = nombre_carrito_lista.split(" (")[0]
        except IndexError:
            messagebox.showwarning("Error", "Selecciona un carrito de la lista para eliminar.")
            return

        if messagebox.askyesno("Confirmar", f"¿Seguro que quieres eliminar el carrito '{nombre_carrito}'?\nSe perderán todos sus datos y progreso."):
            del self.base_de_datos_carritos[nombre_carrito]
            self.admin_lista_carritos.delete(seleccion[0])

    def admin_editar_carrito(self):
        try:
            seleccion = self.admin_lista_carritos.curselection()
            nombre_carrito_lista = self.admin_lista_carritos.get(seleccion[0])
            nombre_carrito = nombre_carrito_lista.split(" (")[0]
        except IndexError:
            messagebox.showwarning("Error", "Selecciona un carrito de la lista para editar.")
            return
            
        self.mostrar_pantalla_admin_edicion(nombre_carrito)

    def mostrar_pantalla_admin_edicion(self, nombre_carrito):
        self.limpiar_frame_principal()
        cart_data = self.base_de_datos_carritos[nombre_carrito]
        
        ttk.Label(self.main_frame, text=f"Editando Carrito: {nombre_carrito}", 
                    font=("Helvetica", 16, "bold")).pack(pady=(10, 10))
        
        ttk.Label(self.main_frame, text="Establece los límites para cada producto:").pack()

        self.admin_edicion_widgets = {}
        frame_botones = ttk.Frame(self.main_frame)
        frame_scroll_container = ttk.Frame(self.main_frame)
        canvas = tk.Canvas(frame_scroll_container)
        scrollbar = ttk.Scrollbar(frame_scroll_container, orient="vertical", command=canvas.yview)
        frame_productos = ttk.Frame(canvas) 
        frame_productos.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )
        canvas.create_window((0, 0), window=frame_productos, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        frame_botones.pack(side="bottom", fill='x', pady=10, padx=20)
        frame_scroll_container.pack(side="top", fill="both", expand=True, padx=20, pady=10)
        scrollbar.pack(side="right", fill="y")
        canvas.pack(side="left", fill="both", expand=True)
        
        limites_actuales = cart_data.get('limites', {}) 

        for cat_key, cat_data in CATEGORIAS_DB.items():
            frame_cat = ttk.LabelFrame(frame_productos, text=f"[{cat_key}] {cat_data['nombre']}")
            frame_cat.pack(fill='x', pady=5, padx=5, ipady=5)
            cat_widgets = {}
            for sub_key, sub_nombre in cat_data['subtipos'].items():
                frame_sub = ttk.Frame(frame_cat)
                frame_sub.pack(fill='x', padx=15, pady=2)
                limite_actual = limites_actuales.get(cat_key, {}).get(sub_key, 0)
                ttk.Label(frame_sub, text=sub_nombre, width=30).pack(side=tk.LEFT, anchor='w')
                ttk.Label(frame_sub, text="Límite:").pack(side=tk.LEFT)
                entry = ttk.Entry(frame_sub, width=8, justify="center")
                entry.insert(0, str(limite_actual))
                entry.pack(side=tk.LEFT, padx=10)
                cat_widgets[sub_key] = entry
            self.admin_edicion_widgets[cat_key] = cat_widgets
        
        ttk.Button(frame_botones, text="Guardar Cambios", 
                    command=lambda n=nombre_carrito: self.guardar_limites_carrito(n)).pack(side=tk.LEFT, expand=True, padx=5)
        ttk.Button(frame_botones, text="Volver (Sin Guardar)", 
                    command=self.mostrar_pantalla_admin_gestion).pack(side=tk.RIGHT, expand=True, padx=5)

    def guardar_limites_carrito(self, nombre_carrito):
        nuevos_limites = {} 
        try:
            for cat_key, cat_widgets in self.admin_edicion_widgets.items():
                sub_limites = {}
                for sub_key, entry in cat_widgets.items():
                    limite = int(entry.get())
                    if limite < 0:
                         raise ValueError(f"El límite para '{CATEGORIAS_DB[cat_key]['subtipos'][sub_key]}' no puede ser negativo.")
                    if limite > 0:
                        sub_limites[sub_key] = limite
                if sub_limites:
                    nuevos_limites[cat_key] = sub_limites
            
            hora_seleccionada = self.pedir_hora_entrega(nombre_carrito)
            
            if hora_seleccionada is None:
                messagebox.showwarning("Cancelado", "No se seleccionó una hora. Los cambios de límites no se guardaron.")
                return 

            self.base_de_datos_carritos[nombre_carrito]['limites'] = nuevos_limites
            self.base_de_datos_carritos[nombre_carrito]['hora_entrega'] = hora_seleccionada
            
            self.base_de_datos_carritos[nombre_carrito]['inventario_realizado'] = {}
            self.base_de_datos_carritos[nombre_carrito]['completado_categorias'] = set()
            self.base_de_datos_carritos[nombre_carrito]['timestamp_completado'] = None

            messagebox.showinfo("Éxito", f"Configuración del carrito '{nombre_carrito}' guardada.")
            self.mostrar_pantalla_admin_gestion()

        except ValueError as e:
            messagebox.showerror("Error de Entrada", str(e))

    # --- 2. Flujo de Usuario ---
    
    def iniciar_escaneo_total_carrito(self, nombre_carrito):
        self.carrito_seleccionado = nombre_carrito
        cart_data = self.base_de_datos_carritos[self.carrito_seleccionado]
        
        self.limites_carrito_actual = cart_data.get('limites', {})
        if not self.limites_carrito_actual:
            messagebox.showerror("Error", "Este carrito no tiene productos configurados.")
            return

        self.inventario_carrito_actual = {}
        inventario_guardado = cart_data.get('inventario_realizado', {})
        for cat_key in self.limites_carrito_actual.keys():
            self.inventario_carrito_actual[cat_key] = inventario_guardado.get(cat_key, {}).copy()

        self.historial_carrito_total = []
        
        total_requerido = 0
        total_ingresado = 0
        for cat_key, sub_limites in self.limites_carrito_actual.items():
            for sub_key, limite in sub_limites.items():
                total_requerido += limite
                total_ingresado += self.inventario_carrito_actual.get(cat_key, {}).get(sub_key, 0)

        self.total_carrito_requerido = total_requerido
        self.restantes_carrito_total = total_requerido - total_ingresado
        self.var_total_restante.set(f"Restantes por escanear: {self.restantes_carrito_total}")

        self.mostrar_pantalla_asignacion_total()

    def mostrar_pantalla_asignacion_total(self):
        self.limpiar_frame_principal()

        frame_izq = ttk.Frame(self.main_frame)
        frame_izq.pack(side=tk.LEFT, fill=tk.Y, padx=10, anchor='n')
        
        ttk.Label(frame_izq, text=f"Escaneando: {self.carrito_seleccionado}", 
                    font=("Helvetica", 14, "bold")).pack(pady=10)
        
        ttk.Label(frame_izq, text=f"Total de productos: {self.total_carrito_requerido}", 
                    font=("Helvetica", 12)).pack(pady=2)
        ttk.Label(frame_izq, textvariable=self.var_total_restante, 
                    font=("Helvetica", 12, "bold"), foreground="blue").pack(pady=10)

        self.btn_escanear = ttk.Button(
            frame_izq, 
            text="🚨 INICIAR ESCÁNER (Cámara)", 
            command=self.iniciar_escaneo_ventana_total
        )
        self.btn_escanear.pack(fill='x', padx=10, pady=5)
        
        self.btn_deshacer = ttk.Button(frame_izq, text="Deshacer Último", 
                            command=self.accion_deshacer_total)
        self.btn_deshacer.pack(fill='x', padx=10, pady=5)
        
        ttk.Separator(frame_izq, orient='horizontal').pack(fill='x', pady=15)

        self.btn_confirmar = ttk.Button(
            frame_izq, text="✅ Confirmar Carrito Completo", 
            command=self.confirmar_carrito_total, state="disabled")
        self.btn_confirmar.pack(fill='x', padx=10, pady=5)

        self.btn_cancelar = ttk.Button(
            frame_izq, text="Volver (Sin Confirmar)", 
            command=self.cancelar_escaneo_total)
        self.btn_cancelar.pack(fill='x', padx=10, pady=5)

        frame_der = ttk.LabelFrame(self.main_frame, text="Resumen del Carrito")
        frame_der.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True, padx=10, pady=10)

        scroll_resumen_container = ttk.Frame(frame_der)
        scroll_resumen_container.pack(fill="both", expand=True, padx=5, pady=5)
        
        canvas_resumen = tk.Canvas(scroll_resumen_container)
        scrollbar_resumen = ttk.Scrollbar(scroll_resumen_container, orient="vertical", command=canvas_resumen.yview)
        self.frame_resumen_scrollable = ttk.Frame(canvas_resumen)

        self.frame_resumen_scrollable.bind(
            "<Configure>",
            lambda e: canvas_resumen.configure(scrollregion=canvas_resumen.bbox("all"))
        )

        canvas_resumen.create_window((0, 0), window=self.frame_resumen_scrollable, anchor="nw")
        canvas_resumen.configure(yscrollcommand=scrollbar_resumen.set)

        scrollbar_resumen.pack(side="right", fill="y")
        canvas_resumen.pack(side="left", fill="both", expand=True)
        
        self.actualizar_estado_botones_asignacion_total()
        self.actualizar_resumen_carrito()

    def actualizar_resumen_carrito(self):
        for widget in self.frame_resumen_scrollable.winfo_children():
            widget.destroy()
        
        style_cat = ttk.Style()
        style_cat.configure("Categoria.TLabel", font=("Helvetica", 10, "bold"))

        style_ok = ttk.Style()
        style_ok.configure("OK.TLabel", foreground="green")
        style_pend = ttk.Style()
        style_pend.configure("PEND.TLabel", foreground="black")

        for cat_key, sub_limites in self.limites_carrito_actual.items():
            
            ttk.Label(self.frame_resumen_scrollable, 
                      text=f"--- {CATEGORIAS_DB[cat_key]['nombre']} ---", 
                      style="Categoria.TLabel").pack(anchor='w', pady=(5,2))
            
            cat_inventario_actual = self.inventario_carrito_actual.get(cat_key, {})
            
            for sub_key, limite in sub_limites.items():
                sub_nombre = CATEGORIAS_DB[cat_key]['subtipos'][sub_key]
                conteo = cat_inventario_actual.get(sub_key, 0)
                
                texto_resumen = f"  {sub_nombre:<25}: {conteo} / {limite}"
                label_style = "OK.TLabel" if conteo == limite else "PEND.TLabel"
                
                ttk.Label(self.frame_resumen_scrollable, text=texto_resumen, style=label_style, font=("Courier", 11)).pack(anchor='w')

    def actualizar_estado_botones_asignacion_total(self):
        if self.restantes_carrito_total == 0:
            self.btn_confirmar.config(state="normal")
        else:
            self.btn_confirmar.config(state="disabled")
            
        self.btn_deshacer.config(state="normal" if self.historial_carrito_total else "disabled")

    # ======================================================================
    # --- FUNCIONES DE ESCANEO ---
    # ======================================================================
    
    def reset_scan_feedback_total(self):
        self.scan_cooldown = False
        if hasattr(self, 'scan_window') and self.scan_window.winfo_exists():
            self.scan_feedback_label.config(text="")
            self.status_label.config(text="Listo para escanear...", foreground="gray")

    def iniciar_escaneo_ventana_total(self):
        if self.restantes_carrito_total <= 0:
            messagebox.showwarning("Límite Alcanzado", "Ya has registrado el total de productos para este carrito.")
            return

        self.scan_cooldown = False 

        self.scan_window = tk.Toplevel(self.root)
        self.scan_window.title(f"Escáner: {self.carrito_seleccionado}")
        self.scan_window.protocol("WM_DELETE_WINDOW", self.detener_escaneo_total) 
        
        ttk.Label(self.scan_window, text="Enfoca el código de barras/QR en la cámara", font=("Helvetica", 12)).pack(pady=10)
        
        self.scan_feedback_label = ttk.Label(self.scan_window, text="", font=("Helvetica", 16, "bold"), justify="center")
        self.scan_feedback_label.pack(pady=5)
        
        ttk.Label(self.scan_window, textvariable=self.var_total_restante, 
                    font=("Helvetica", 12, "bold"), foreground="blue").pack(pady=5)

        self.camera_label = ttk.Label(self.scan_window)
        self.camera_label.pack(padx=10, pady=10)

        self.status_label = ttk.Label(self.scan_window, text="Listo para escanear...", foreground="gray")
        self.status_label.pack(pady=5)
        
        self.cap = cv2.VideoCapture(0)
        if not self.cap.isOpened():
            messagebox.showerror("Error de Cámara", "No se pudo acceder a la cámara de la laptop.")
            self.detener_escaneo_total()
            return
            
        self.escanear_loop_total()

    def escanear_loop_total(self):
        if not hasattr(self, 'cap') or not self.cap.isOpened():
            return
        
        if self.restantes_carrito_total <= 0:
            self.detener_escaneo_total("¡Límite del carrito alcanzado! Escaneo detenido.")
            return
            
        ret, frame = self.cap.read()
        
        if ret:
            if not self.scan_cooldown:
                decoded_objects = pyzbar.decode(frame)
                
                for obj in decoded_objects:
                    codigo_leido = obj.data.decode("utf-8")
                    mapeo = BD_CODIGOS_BARRA.get(codigo_leido)
                    
                    color = (0, 0, 255) # Rojo
                    product_name = ""

                    if mapeo:
                        cat_key_escaneado, sub_key_escaneado = mapeo
                        product_name = CATEGORIAS_DB.get(cat_key_escaneado, {}).get('subtipos', {}).get(sub_key_escaneado, "Desconocido")
                        
                        if cat_key_escaneado in self.limites_carrito_actual and sub_key_escaneado in self.limites_carrito_actual[cat_key_escaneado]:
                            
                            limite_subtipo = self.limites_carrito_actual[cat_key_escaneado][sub_key_escaneado]
                            conteo_actual_subtipo = self.inventario_carrito_actual.get(cat_key_escaneado, {}).get(sub_key_escaneado, 0)

                            if conteo_actual_subtipo >= limite_subtipo:
                                self.status_label.config(text=f"LÍMITE ALCANZADO: {product_name} ({limite_subtipo})", foreground="orange")
                                color = (0, 165, 255) # Naranja
                            else:
                                self.scan_cooldown = True 
                                self.procesar_escaneo_exitoso_total(cat_key_escaneado, sub_key_escaneado)
                                
                                self.scan_feedback_label.config(text=f"¡Registrado!\n{product_name}", foreground="green")
                                self.status_label.config(text="OK", foreground="green")
                                color = (0, 255, 0) # Verde
                                
                                self.scan_window.after(500, self.reset_scan_feedback_total) 
                                
                                (x, y, w, h) = obj.rect
                                cv2.rectangle(frame, (x, y), (x + w, y + h), color, 2)
                                break 
                        else:
                            self.status_label.config(text=f"ERROR: Producto '{product_name}' no pertenece a este carrito.", foreground="red")
                    else:
                        self.status_label.config(text=f"ERROR: Código '{codigo_leido}' no mapeado.", foreground="orange")
                        
                    (x, y, w, h) = obj.rect
                    cv2.rectangle(frame, (x, y), (x + w, y + h), color, 2)
            
            cv2image = cv2.cvtColor(frame, cv2.COLOR_BGR2RGBA)
            _, img_encoded = cv2.imencode('.png', cv2image)
            img_data = img_encoded.tobytes()
            img = tk.PhotoImage(data=img_data)
            
            self.camera_label.imgtk = img
            self.camera_label.config(image=img)

        self.scan_window.after(10, self.escanear_loop_total)

    def detener_escaneo_total(self, mensaje="Escaneo detenido."):
        if hasattr(self, 'cap') and self.cap.isOpened():
            self.cap.release()
            
        if hasattr(self, 'scan_window') and self.scan_window.winfo_exists():
            self.scan_window.destroy()

        if mensaje and mensaje != "Escaneo detenido.":
            messagebox.showinfo("Proceso Detenido", mensaje)
            
        self.actualizar_estado_botones_asignacion_total()
        self.actualizar_resumen_carrito()
        
    def procesar_escaneo_exitoso_total(self, cat_key, sub_key):
        self.historial_carrito_total.append({k: v.copy() for k, v in self.inventario_carrito_actual.items()})
        self.restantes_carrito_total -= 1
        self.inventario_carrito_actual.setdefault(cat_key, {})[sub_key] = self.inventario_carrito_actual.get(cat_key, {}).get(sub_key, 0) + 1
        self.var_total_restante.set(f"Restantes por escanear: {self.restantes_carrito_total}")
        self.actualizar_resumen_carrito()
        self.actualizar_estado_botones_asignacion_total()
        
    def accion_deshacer_total(self):
        if not self.historial_carrito_total:
            return

        if hasattr(self, 'scan_window') and self.scan_window.winfo_exists():
            self.detener_escaneo_total()
            
        self.inventario_carrito_actual = self.historial_carrito_total.pop()
        
        total_ingresado = 0
        for cat_key, sub_conteo in self.inventario_carrito_actual.items():
            total_ingresado += sum(sub_conteo.values())
            
        self.restantes_carrito_total = self.total_carrito_requerido - total_ingresado
        
        self.var_total_restante.set(f"Restantes por escanear: {self.restantes_carrito_total}")
        self.actualizar_resumen_carrito()
        self.actualizar_estado_botones_asignacion_total()

    # --- ¡MODIFICADO! Llama a la función de guardar en CSV ---
    def confirmar_carrito_total(self):
        cart_data = self.base_de_datos_carritos[self.carrito_seleccionado]
        
        cart_data['inventario_realizado'] = self.inventario_carrito_actual
        cart_data['completado_categorias'] = set(self.limites_carrito_actual.keys())
        
        ahora = datetime.now()
        timestamp_str = ahora.strftime("%H:%M") 
        cart_data['timestamp_completado'] = timestamp_str
        
        # --- ¡NUEVA LLAMADA! Guardar en el CSV único ---
        self.agregar_carrito_completado_a_csv(self.carrito_seleccionado, cart_data, ahora)
        
        messagebox.showinfo("Carrito Completo", 
                            f"Se guardaron todos los datos del '{self.carrito_seleccionado}' y se actualizó el registro CSV.")
        self.mostrar_pantalla_menu_principal()

    def cancelar_escaneo_total(self):
        if self.historial_carrito_total:
            if not messagebox.askyesno("Confirmar Cancelación",
                                        "¿Seguro que quieres cancelar?\nSe perderán los cambios hechos en esta sesión de escaneo."):
                return
        
        if hasattr(self, 'scan_window') and self.scan_window.winfo_exists():
            self.detener_escaneo_total()

        self.mostrar_pantalla_menu_principal()

    # --- 3. Finalización y Reporte ---
    # --- ¡MODIFICADO! Ya no genera CSVs, solo muestra la ubicación ---
    def mostrar_ubicacion_registro(self):
        """Muestra un mensaje indicando dónde se guarda el registro CSV."""
        filepath = os.path.abspath(REGISTRO_CSV_FILENAME)
        messagebox.showinfo("Ubicación del Registro",
                            f"Los carritos completados se guardan automáticamente en:\n\n{filepath}")

    # --- ¡NUEVA FUNCIÓN! Guarda un carrito completado en el CSV único ---
    def agregar_carrito_completado_a_csv(self, nombre_carrito, cart_data, timestamp_dt):
        """Añade las filas de un carrito completado al archivo CSV principal."""
        
        # Definir encabezados incluyendo los nuevos campos
        encabezados = ['Timestamp_Completado_DT', 'Timestamp_Completado_HM', 'Nombre_Carrito', 'Hora_Entrega', 
                       'Codigo', 'Categoria', 'Subtipo', 'Cantidad_Registrada', 'Cantidad_Limite']
        
        datos_para_csv = []
        
        # Obtener datos generales del carrito
        timestamp_completo_dt_str = timestamp_dt.strftime("%Y-%m-%d %H:%M:%S")
        timestamp_completo_hm_str = cart_data.get('timestamp_completado', '') # Ya está en H:M
        hora_entrega = cart_data.get('hora_entrega', 'N/A')
        
        inventario_realizado = cart_data.get('inventario_realizado', {})
        limites = cart_data.get('limites', {}) 

        # Crear las filas de datos para este carrito
        for cat_key, sub_limites in limites.items():
            cat_inventario = inventario_realizado.get(cat_key, {})
            cat_maestra = CATEGORIAS_DB[cat_key]
            
            for sub_key, limite_subtipo in sub_limites.items():
                cantidad_reg = cat_inventario.get(sub_key, 0)
                
                datos_para_csv.append({
                    'Timestamp_Completado_DT': timestamp_completo_dt_str,
                    'Timestamp_Completado_HM': timestamp_completo_hm_str,
                    'Nombre_Carrito': nombre_carrito,
                    'Hora_Entrega': hora_entrega,
                    'Codigo': f"{cat_key}{sub_key}",
                    'Categoria': cat_maestra['nombre'],
                    'Subtipo': cat_maestra['subtipos'].get(sub_key, "???"),
                    'Cantidad_Registrada': cantidad_reg,
                    'Cantidad_Limite': limite_subtipo 
                })

        if not datos_para_csv:
            return # No hacer nada si no hay datos

        try:
            # Comprobar si el archivo ya existe para saber si escribir el header
            escribir_header = not os.path.exists(REGISTRO_CSV_FILENAME)

            # Abrir en modo 'append' (añadir al final)
            with open(REGISTRO_CSV_FILENAME, mode='a', newline='', encoding='utf-8') as file:
                writer = csv.DictWriter(file, fieldnames=encabezados)
                
                if escribir_header:
                    writer.writeheader() # Escribir encabezados solo si es nuevo
                    
                writer.writerows(datos_para_csv) # Añadir las filas de este carrito

        except Exception as e:
            messagebox.showerror("Error al Guardar Registro CSV", 
                                f"No se pudo actualizar el archivo '{REGISTRO_CSV_FILENAME}'.\nError: {e}")

    # --- FUNCIÓN OBSOLETA (guardar_csv_por_carrito) eliminada ---


# --- 4. Ejecutar la Aplicación ---
if __name__ == "__main__":
    root = tk.Tk()
    app = AppClasificacion(root)
    root.mainloop()