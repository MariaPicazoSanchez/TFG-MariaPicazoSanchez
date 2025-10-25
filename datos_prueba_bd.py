from database import DatabaseManager
def datos_prueba():
    # USUARIOS DE PRUEBA
    db = DatabaseManager()
    # --- ESTUDIANTE OUT ---
    nombre_out = db.insertar_estudiante(
        nombre="Maria Prueba",
        origen="Universidad de Castilla-La Mancha (Albacete)",
        destino="Universidad de Paris (Paris)",
        tipo="out",
        la_link="http://enlace_la_out"
    )
    db.insertar_estudiante_out(
        estudiante_nombre=nombre_out,
        tor_link="http://enlace_tor",
        curso="2024-2025",
        acta_equivalencias="http://enlace_acta"
    )
    nombre_out = db.insertar_estudiante(
        nombre="Juan Pérez",
        origen="Universidad de Madrid (Madrid)",
        destino="Universidad de Londres (Londres)",
        tipo="out",
        la_link="http://enlace_la_out"
    )
    db.insertar_estudiante_out(
        estudiante_nombre=nombre_out,
        tor_link="http://enlace_tor",
        curso="2024-2025",
        acta_equivalencias="http://enlace_acta"
    )

    # --- ESTUDIANTE IN ---
    nombre_in = db.insertar_estudiante(
        nombre="María López",
        origen="Universidad de Mexico (Ciudad de México)",
        destino="Universidad de Castilla-La Mancha (Albacete)",
        tipo="in",
        la_link="http://enlace_la_in"
    )
    db.insertar_estudiante_in(
        estudiante_nombre=nombre_in,
        horario_link="http://enlace_horario"
    )
    nombre_in = db.insertar_estudiante(
        nombre="William Smith",
        origen="Universidad de Canada (Ottawa)",
        destino="Universidad de Castilla-La Mancha (Albacete)",
        tipo="in",
        la_link="http://enlace_la_in"
    )
    db.insertar_estudiante_in(
        estudiante_nombre=nombre_in,
        horario_link="http://enlace_horario"
    )

    # --- ESTUDIANTE SICUE ---
    nombre_sicue = db.insertar_estudiante(
        nombre="Carlos García",
        origen="Universidad de Zaragoza (Zaragoza)",
        destino="Universidad de Salamanca (Salamanca)",
        tipo="SICUE",
        la_link="http://enlace_la_sicue"
    )
    db.insertar_estudiante_sicue(
        estudiante_nombre=nombre_sicue,
        plan_estudios_link="http://enlace_plan",
        firmado_origen="Firmado",
        firmado_destino="Firmado",
        enviado_vicerrectorado="Pendiente"
    )