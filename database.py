import sqlite3
import os
from pathlib import Path

DB_NAME = "movilidad.db"

class DatabaseManager:
    def __init__(self, db_name=DB_NAME):
        repo_dir = Path(__file__).parent
        self.db_name = str(repo_dir.joinpath(db_name).resolve())
        self.crear_tablas()
    
    def get_connection(self):
        conn = sqlite3.connect(self.db_name)
        # Activar claves foráneas
        conn.execute("PRAGMA foreign_keys = ON")
        return conn
    
    def crear_tablas(self):
        conn = self.get_connection()
        cursor = conn.cursor()
        
        # Tabla principal ESTUDIANTES
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS ESTUDIANTES (
                nombre VARCHAR(255) PRIMARY KEY,
                origen VARCHAR(255) NOT NULL,
                destino VARCHAR(255) NOT NULL,
                tipo VARCHAR(10) CHECK(tipo IN ('out', 'in', 'SICUE')) NOT NULL,
                la_link VARCHAR(500)
            )
        ''')
        
        # Tabla ESTUDIANTES_OUT
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS ESTUDIANTES_OUT (
                estudiante_nombre VARCHAR(255) PRIMARY KEY,
                tor_link VARCHAR(500),
                curso VARCHAR(50),
                acta_equivalencias VARCHAR(500),
                FOREIGN KEY (estudiante_nombre) REFERENCES ESTUDIANTES(nombre) ON DELETE CASCADE
            )
        ''')
        
        # Tabla ESTUDIANTES_IN
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS ESTUDIANTES_IN (
                estudiante_nombre VARCHAR(255) PRIMARY KEY,
                horario_link VARCHAR(500),
                FOREIGN KEY (estudiante_nombre) REFERENCES ESTUDIANTES(nombre) ON DELETE CASCADE
            )
        ''')
        
        # Tabla ESTUDIANTES_SICUE
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS ESTUDIANTES_SICUE (
                estudiante_nombre VARCHAR(255) PRIMARY KEY,
                plan_estudios_link VARCHAR(500),
                firmado_origen VARCHAR(20) CHECK(firmado_origen IN ('Pendiente', 'Firmado')) DEFAULT 'Pendiente',
                firmado_destino VARCHAR(20) CHECK(firmado_destino IN ('Pendiente', 'Firmado')) DEFAULT 'Pendiente',
                enviado_vicerrectorado VARCHAR(20) CHECK(enviado_vicerrectorado IN ('Pendiente', 'Enviado')) DEFAULT 'Pendiente',
                FOREIGN KEY (estudiante_nombre) REFERENCES ESTUDIANTES(nombre) ON DELETE CASCADE
            )
        ''')
        
        conn.commit()
        conn.close()
        print("Todas las tablas creadas/verificadas correctamente")
    
    # ===== OPERACIONES PARA ESTUDIANTES =====
    
    def insertar_estudiante(self, nombre, origen, destino, tipo, la_link=None):
        conn = self.get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute(
                "INSERT INTO ESTUDIANTES (nombre, origen, destino, tipo, la_link) VALUES (?, ?, ?, ?, ?)", 
                (nombre, origen, destino, tipo, la_link)
            )
            conn.commit()
            print(f"Estudiante '{nombre}' agregado correctamente.")
            return nombre
        except sqlite3.IntegrityError as e:
            print(f"Error al insertar estudiante: {e}")
            return None
        finally:
            conn.close()
    
    def obtener_estudiantes(self, tipo=None):
        conn = self.get_connection()
        cursor = conn.cursor()
        
        if tipo:
            cursor.execute("SELECT * FROM ESTUDIANTES WHERE tipo = ? ORDER BY nombre", (tipo,))
        else:
            cursor.execute("SELECT * FROM ESTUDIANTES ORDER BY nombre")
        
        filas = cursor.fetchall()
        conn.close()
        return filas
    
    def obtener_estudiante_por_nombre(self, estudiante_nombre):
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM ESTUDIANTES WHERE nombre = ?", (estudiante_nombre,))
        estudiante = cursor.fetchone()
        conn.close()
        return estudiante
    
    # ===== OPERACIONES PARA ESTUDIANTES_OUT =====
    
    def insertar_estudiante_out(self, estudiante_nombre, tor_link=None, curso=None, acta_equivalencias=None):
        conn = self.get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute(
                """INSERT INTO ESTUDIANTES_OUT 
                (estudiante_nombre, tor_link, curso, acta_equivalencias) 
                VALUES (?, ?, ?, ?)""", 
                (estudiante_nombre, tor_link, curso, acta_equivalencias)
            )
            conn.commit()
            print(f"Datos OUT agregados para estudiante: {estudiante_nombre}")
            return True
        except sqlite3.IntegrityError as e:
            print(f"Error al insertar datos OUT: {e}")
            return False
        finally:
            conn.close()
    
    def obtener_estudiante_out(self, estudiante_nombre):
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM ESTUDIANTES_OUT WHERE estudiante_nombre = ?", (estudiante_nombre,))
        datos = cursor.fetchone()
        conn.close()
        return datos
    
    # ===== OPERACIONES PARA ESTUDIANTES_IN =====
    
    def insertar_estudiante_in(self, estudiante_nombre, horario_link=None):
        conn = self.get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute(
                "INSERT INTO ESTUDIANTES_IN (estudiante_nombre, horario_link) VALUES (?, ?)", 
                (estudiante_nombre, horario_link)
            )
            conn.commit()
            print(f"Datos IN agregados para estudiante: {estudiante_nombre}")
            return True
        except sqlite3.IntegrityError as e:
            print(f"Error al insertar datos IN: {e}")
            return False
        finally:
            conn.close()
    
    def obtener_estudiante_in(self, estudiante_nombre):
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM ESTUDIANTES_IN WHERE estudiante_nombre = ?", (estudiante_nombre,))
        datos = cursor.fetchone()
        conn.close()
        return datos
    
    # ===== OPERACIONES PARA ESTUDIANTES_SICUE =====
    
    def insertar_estudiante_sicue(self, estudiante_nombre, plan_estudios_link=None, firmado_origen='Pendiente', firmado_destino='Pendiente', enviado_vicerrectorado='Pendiente'):
        conn = self.get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute(
                """INSERT INTO ESTUDIANTES_SICUE 
                (estudiante_nombre, plan_estudios_link, firmado_origen, firmado_destino, enviado_vicerrectorado) 
                VALUES (?, ?, ?, ?, ?)""", 
                (estudiante_nombre, plan_estudios_link, firmado_origen, firmado_destino, enviado_vicerrectorado)
            )
            conn.commit()
            print(f"Datos SICUE agregados para estudiante ID: {estudiante_nombre}")
            return True
        except sqlite3.IntegrityError as e:
            print(f"Error al insertar datos SICUE: {e}")
            return False
        finally:
            conn.close()
    
    def obtener_estudiante_sicue(self, estudiante_nombre):
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM ESTUDIANTES_SICUE WHERE estudiante_nombre = ?", (estudiante_nombre,))
        datos = cursor.fetchone()
        conn.close()
        return datos
    
    def obtener_estudiantes_completos(self, tipo=None):
        # Obtiene estudiantes con todos sus datos relacionados
        conn = self.get_connection()
        cursor = conn.cursor()
        
        query = """
        SELECT e.*, 
               o.tor_link, o.curso, o.acta_equivalencias,
               i.horario_link,
               s.plan_estudios_link, s.firmado_origen, s.firmado_destino, s.enviado_vicerrectorado
        FROM ESTUDIANTES e
        LEFT JOIN ESTUDIANTES_OUT o ON e.nombre = o.estudiante_nombre
        LEFT JOIN ESTUDIANTES_IN i ON e.nombre = i.estudiante_nombre
        LEFT JOIN ESTUDIANTES_SICUE s ON e.nombre = s.estudiante_nombre
        """
        
        if tipo:
            query += " WHERE e.tipo = ? ORDER BY e.nombre"
            cursor.execute(query, (tipo,))
        else:
            query += " ORDER BY e.nombre"
            cursor.execute(query)
        
        estudiantes = cursor.fetchall()
        conn.close()
        return estudiantes
    
    # def contar_estudiantes_por_tipo(self):
    #     """Cuenta estudiantes por tipo"""
    #     conn = self.get_connection()
    #     cursor = conn.cursor()
    #     cursor.execute("SELECT tipo, COUNT(*) FROM ESTUDIANTES GROUP BY tipo")
    #     resultados = cursor.fetchall()
    #     conn.close()
    #     return resultados
    
