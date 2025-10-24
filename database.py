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
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                nombre VARCHAR(255) NOT NULL,
                origen VARCHAR(255) NOT NULL,
                destino VARCHAR(255) NOT NULL,
                tipo VARCHAR(10) CHECK(tipo IN ('out', 'in', 'SICUE')) NOT NULL,
                la_link VARCHAR(500)
            )
        ''')
        
        # Tabla ESTUDIANTES_OUT
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS ESTUDIANTES_OUT (
                estudiante_id INTEGER PRIMARY KEY,
                tor_link VARCHAR(500),
                curso VARCHAR(50),
                acta_equivalencias VARCHAR(500),
                FOREIGN KEY (estudiante_id) REFERENCES ESTUDIANTES(id) ON DELETE CASCADE
            )
        ''')
        
        # Tabla ESTUDIANTES_IN
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS ESTUDIANTES_IN (
                estudiante_id INTEGER PRIMARY KEY,
                horario_link VARCHAR(500),
                FOREIGN KEY (estudiante_id) REFERENCES ESTUDIANTES(id) ON DELETE CASCADE
            )
        ''')
        
        # Tabla ESTUDIANTES_SICUE
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS ESTUDIANTES_SICUE (
                estudiante_id INTEGER PRIMARY KEY,
                plan_estudios_link VARCHAR(500),
                firmado_origen VARCHAR(20) CHECK(firmado_origen IN ('Pendiente', 'Firmado')) DEFAULT 'Pendiente',
                firmado_destino VARCHAR(20) CHECK(firmado_destino IN ('Pendiente', 'Firmado')) DEFAULT 'Pendiente',
                enviado_vicerrectorado VARCHAR(20) CHECK(enviado_vicerrectorado IN ('Pendiente', 'Enviado')) DEFAULT 'Pendiente',
                FOREIGN KEY (estudiante_id) REFERENCES ESTUDIANTES(id) ON DELETE CASCADE
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
            estudiante_id = cursor.lastrowid
            conn.commit()
            print(f"Estudiante '{nombre}' agregado con ID: {estudiante_id}")
            return estudiante_id
        except sqlite3.IntegrityError as e:
            print(f"Error al insertar estudiante: {e}")
            return None
        finally:
            conn.close()
    
    def obtener_estudiantes(self, tipo=None):
        conn = self.get_connection()
        cursor = conn.cursor()
        
        if tipo:
            cursor.execute("SELECT * FROM ESTUDIANTES WHERE tipo = ? ORDER BY id", (tipo,))
        else:
            cursor.execute("SELECT * FROM ESTUDIANTES ORDER BY id")
        
        filas = cursor.fetchall()
        conn.close()
        return filas
    
    def obtener_estudiante_por_id(self, estudiante_id):
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM ESTUDIANTES WHERE id = ?", (estudiante_id,))
        estudiante = cursor.fetchone()
        conn.close()
        return estudiante
    
    # ===== OPERACIONES PARA ESTUDIANTES_OUT =====
    
    def insertar_estudiante_out(self, estudiante_id, tor_link=None, curso=None, acta_equivalencias=None):
        conn = self.get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute(
                """INSERT INTO ESTUDIANTES_OUT 
                (estudiante_id, tor_link, curso, acta_equivalencias) 
                VALUES (?, ?, ?, ?)""", 
                (estudiante_id, tor_link, curso, acta_equivalencias)
            )
            conn.commit()
            print(f"Datos OUT agregados para estudiante ID: {estudiante_id}")
            return True
        except sqlite3.IntegrityError as e:
            print(f"Error al insertar datos OUT: {e}")
            return False
        finally:
            conn.close()
    
    def obtener_estudiante_out(self, estudiante_id):
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM ESTUDIANTES_OUT WHERE estudiante_id = ?", (estudiante_id,))
        datos = cursor.fetchone()
        conn.close()
        return datos
    
    # ===== OPERACIONES PARA ESTUDIANTES_IN =====
    
    def insertar_estudiante_in(self, estudiante_id, horario_link=None):
        conn = self.get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute(
                "INSERT INTO ESTUDIANTES_IN (estudiante_id, horario_link) VALUES (?, ?)", 
                (estudiante_id, horario_link)
            )
            conn.commit()
            print(f"Datos IN agregados para estudiante ID: {estudiante_id}")
            return True
        except sqlite3.IntegrityError as e:
            print(f"Error al insertar datos IN: {e}")
            return False
        finally:
            conn.close()
    
    def obtener_estudiante_in(self, estudiante_id):
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM ESTUDIANTES_IN WHERE estudiante_id = ?", (estudiante_id,))
        datos = cursor.fetchone()
        conn.close()
        return datos
    
    # ===== OPERACIONES PARA ESTUDIANTES_SICUE =====
    
    def insertar_estudiante_sicue(self, estudiante_id, plan_estudios_link=None, firmado_origen='Pendiente', firmado_destino='Pendiente', enviado_vicerrectorado='Pendiente'):
        conn = self.get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute(
                """INSERT INTO ESTUDIANTES_SICUE 
                (estudiante_id, plan_estudios_link, firmado_origen, firmado_destino, enviado_vicerrectorado) 
                VALUES (?, ?, ?, ?, ?)""", 
                (estudiante_id, plan_estudios_link, firmado_origen, firmado_destino, enviado_vicerrectorado)
            )
            conn.commit()
            print(f"Datos SICUE agregados para estudiante ID: {estudiante_id}")
            return True
        except sqlite3.IntegrityError as e:
            print(f"Error al insertar datos SICUE: {e}")
            return False
        finally:
            conn.close()
    
    def obtener_estudiante_sicue(self, estudiante_id):
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM ESTUDIANTES_SICUE WHERE estudiante_id = ?", (estudiante_id,))
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
        LEFT JOIN ESTUDIANTES_OUT o ON e.id = o.estudiante_id
        LEFT JOIN ESTUDIANTES_IN i ON e.id = i.estudiante_id
        LEFT JOIN ESTUDIANTES_SICUE s ON e.id = s.estudiante_id
        """
        
        if tipo:
            query += " WHERE e.tipo = ? ORDER BY e.id"
            cursor.execute(query, (tipo,))
        else:
            query += " ORDER BY e.id"
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
    
