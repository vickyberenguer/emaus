"""
Importa Espacios Educativos y el relevamiento semestre 2 del 2025 desde el CSV de informe.

Uso:
    cd backend && source venv/bin/activate
    python scripts/importar_ee_2025_2.py

Reglas según la columna "Baja 2026":
  - "x"  → EE base con activo=False + relevamiento 2025-S2 con todos los datos
  - "o"  → solo EE base activo=True (EE nuevo, sin datos 2025)
  - ""   → EE base activo=True + relevamiento 2025-S2 con todos los datos

Prerrequisito: migración 007 ejecutada en TiDB.
"""

import csv
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import text
from app.database import SessionLocal, engine
from app.models.emaus import Emaus
from app.models.usuario import Usuario, RolEnum
from app.models.espacio_educativo import (
    EspacioEducativo, EEAmbiente, EEServicio, EEEquipoCocina,
    EEEquipoInformatico, EEZona, RelevamientoEE,
)
from app.models.relevamiento import Relevamiento
import app.models  # registra todos los mappers

CSV_PATH = Path(__file__).resolve().parents[2] / "archivosdatos" / \
    "Informe Emaús de fin de termino 2025 - Total - EspaciosEducativos.csv"

EMAUS_OVERRIDES = {"Zarate Campana": "Zárate Campana"}

# ── helpers ───────────────────────────────────────────────────────────────────

def es_si(v):
    return str(v or "").strip().lower() in ("sí", "si", "s", "true", "1", "yes")

def nullable_bool(v):
    s = str(v or "").strip().lower()
    if s in ("sí", "si"): return True
    if s == "no": return False
    return None

def nullable_int(v):
    try:
        n = int(str(v).strip())
        return n if n >= 0 else None
    except (ValueError, TypeError):
        return None

def clean_str(v, invalidos=("sin respuesta", "seleccionar respuesta de la lista desplegable", ""), maxlen=None):
    s = str(v or "").strip()
    if s.lower() in invalidos:
        return None
    if not s:
        return None
    if maxlen and len(s) > maxlen:
        s = s[:maxlen]
    return s

def es_true_bool(v):
    return str(v or "").strip().upper() in ("TRUE", "SÍ", "SI", "1", "S")

# ── mapeos ────────────────────────────────────────────────────────────────────

AMBIENTES = [
    ("EE Cocina",             "Cocina",                         "EE Baño Nro"),
    ("EE Comedor",            "Salón comedor",                  None),
    ("EE Despensa",           "Despensa / almacén / depósito",  None),
    ("EE Baño",               "Baño",                           "EE Baño Nro"),
    ("EE Espacio Recreacion", "Espacio de recreación",          None),
]

SERVICIOS = [
    ("EE agua corriente",         "Agua corriente",                           True),
    ("EE agua aljibe reservorio", "Agua de aljibe/reservorio",                True),
    ("EE agua fueradelterreno",   "Agua fuera del terreno",                   True),
    ("EE cloacas",                "Servicio de cloacas",                      True),
    ("EE luz red",                "Energía eléctrica por red domiciliaria",   True),
    ("EE senalmovil",             "Señal de telefonía móvil",                 True),
    ("EE residuos",               "El tratamiento de residuos",               False),
    ("EE internet prov",          "Internet",                                 False),
    ("EE combustiblecocina",      "Tipo de combustible que utiliza la cocina", False),
]

EQUIPOS_COCINA = [
    ("EE cocina industrial",  "Cocina industrial"),
    ("EE cocina familiar",    "Cocina familiar"),
    ("EE cocina mechero",     "Mechero"),
    ("EE cocina heladeraind", "Heladera industrial"),
    ("EE cocina heladerafam", "Heladera familiar"),
    ("EE cocina freezerind",  "Freezer industrial"),
    ("EE cocina freezerfam",  "Freezer familiar"),
]

EQUIPOS_INFORMATICOS = [
    ("EquipInformatico MonitorTubo",  "Monitor de tubo"),
    ("EquipInformatico MonitorPlano", "Monitor plano"),
    ("EquipInformatico PCAllinOne",   "PC All in one"),
    ("EquipInformatico PCEscritorio", "PC de escritorio"),
    ("EquipInformatico Notebook",     "Notebook / laptop"),
    ("EquipInformatico Tablet",       "Tablet"),
    ("EquipInformatico Impresora",    "Impresora"),
    ("EquipInformatico Multifuncion", "Impresora multifunción (con escáner)"),
]

ZONAS = [
    ("EE zona urbana",         "Urbana"),
    ("EE zona periferica",     "Periférica"),
    ("EE zona rural",          "Rural"),
    ("EE zona inundable",      "Inundable"),
    ("EE zona dif transporte", "Con poco o sin acceso al transporte público"),
]

ACCIONES = [
    ("Accion PI Pastoral",         "Primera infancia", "Pastoral PI"),
    ("Accion PI Capacitaciones",   "Primera infancia", "Capacitaciones, talleres y encuentros"),
    ("Accion PI EspPI",            "Primera infancia", "Espacios de Primera Infancia"),
    ("Accion PI EstimTemprana",    "Primera infancia", "Estimulación temprana"),
    ("Accion ATE BF",              "Apoyo a las trayectorias educativas", "Becas Familiares"),
    ("Accion ATE ApoyoEscolar",    "Apoyo a las trayectorias educativas", "Apoyo escolar"),
    ("Accion ATE BTU",             "Apoyo a las trayectorias educativas", "Becas Terciarias y universitarias"),
    ("Accion ATE AlfabInicial",    "Apoyo a las trayectorias educativas", "Alfabetización inicial"),
    ("Accion ATE DALE",            "Apoyo a las trayectorias educativas", "Propuesta DALE"),
    ("Accion ATE ActLectoEscOral", "Apoyo a las trayectorias educativas", "Actividades de lectoescritura y oralidad"),
    ("Accion ATE RinconLectura",   "Apoyo a las trayectorias educativas", "Rincón de lectura"),
    ("Accion ATE AlfabAdultos",    "Apoyo a las trayectorias educativas", "Alfabetización de adultos"),
    ("Accion ATE PromSE",          "Apoyo a las trayectorias educativas", "Promotores socio-educativos"),
    ("Accion IC Itinerancia",      "Integración comunitaria", "Itinerancia"),
    ("Accion IC Mochileros",       "Integración comunitaria", "Mochileros"),
    ("Accion IC Ludoteca",         "Integración comunitaria", "Ludoteca"),
    ("Accion IC ActCultRecre",     "Integración comunitaria", "Actividades culturales y recreativas"),
    ("Accion IC Desarrollo",       "Integración comunitaria", "Desarrollo habilidades duras y blandas"),
    ("Accion IC HabTrabajo",       "Integración comunitaria", "Habilidades para el mundo del trabajo"),
    ("Accion IC TalleresMuj",      "Integración comunitaria", "Talleres para mujeres"),
    ("Accion IC Adolescentes",     "Integración comunitaria", "Propuestas para adolescentes"),
    ("Accion IC Potenciar",        "Integración comunitaria", "Potenciar trabajo"),
    ("Accion IC TallOficio",       "Integración comunitaria", "Talleres de oficio"),
    ("Accion NT CapacTall",        "Nuevas tecnologías", "Capacitaciones y talleres"),
    ("Accion NT EquiInfInt",       "Nuevas tecnologías", "Equipamiento informático e internet"),
    ("Accion NT Tramites",         "Nuevas tecnologías", "Trámites del estado (ANSES, AUH, CUD, etc)"),
    ("Accion NT AccesoDig",        "Nuevas tecnologías", "Acceso digital comunitario"),
    ("Accion SI Deportes",         "Salud integral", "Deportes"),
    ("Accion SI Alimentacion",     "Salud integral", "Alimentación saludable"),
    ("Accion SI Meriendas",        "Salud integral", "Meriendas"),
    ("Accion SI ControlesMed",     "Salud integral", "Controles médicos"),
    ("Accion SI CapacitTall",      "Salud integral", "Capacitaciones, talleres y encuentros"),
    ("Accion SI Huertas",          "Salud integral", "Huertas comunitarias"),
]

PRIORIDADES = [
    ("Prioridad pintura exterior", "Pintura exterior"),
    ("Prioridad pintura interior", "Pintura interior"),
    ("Prioridad electricidad",     "Instalación eléctrica"),
    ("Prioridad agua",             "Instalación de agua"),
    ("Prioridad gas",              "Instalación de gas"),
    ("Prioridad arreglos",         "Arreglos generales"),
    ("Prioridad construccion",     "Construcción / ampliación"),
    ("Prioridad climatizacion",    "Climatización"),
    ("Prioridad banio",            "Baño"),
]

BTU_MOTIVOS = [
    ("BTU abandono horarios",                "Incompatibilidad de la cursada con horarios laborales"),
    ("BTU abandono costotransporte",         "Dificultad para costear el transporte"),
    ("BTU abandono cambiodomic",             "Cambio de domicilio (mudanza)"),
    ("BTU abandono faltatiempo",             "Falta de tiempo por tareas de cuidado familiar"),
    ("BTU abandono accesotranspor",          "Problemas de accesibilidad del transporte local"),
    ("BTU abandono accesoboletoestudiantil", "Falta de acceso al boleto estudiantil"),
    ("BTU abandono otro",                    "Otro:"),
]

CONTENIDOS_PRIM = [
    ("ApEscolar Lengua",         "Lengua"),
    ("ApEscolar Matematicas",    "Matemáticas"),
    ("ApEscolar CciasNaturales", "Ciencias Naturales"),
    ("ApEscolar CciasSociales",  "Ciencias Sociales"),
    ("ApEscolar Ingles",         "Inglés"),
    ("ApEscolar Otro",           "Otro:"),
]

CONTENIDOS_SEC = [
    ("ApEscolar Sec Lengua",         "Lengua"),
    ("ApEscolar Sec Matematicas",    "Matemáticas"),
    ("ApEscolar Sec CciasNaturales", "Ciencias Naturales"),
    ("ApEscolar Sec CciasSociales",  "Ciencias Sociales"),
    ("ApEscolar Sec Ingles",         "Inglés"),
    ("ApEscolar Sec Otro",           "Otro:"),
]

DIGITAL_TALLERES = [
    ("AlfabDig NT Digitales",     "Herramientas digitales (navegador, correo, drive, etc.)"),
    ("AlfabDig NT Tall Trabajo",  "Herramientas de Microsoft Office (Word, Excel, PowerPoint)"),
    ("AlfabDig NT Tall Redes",    "Redes sociales (Facebook, Instagram, TikTok, WhatsApp, YouTube)"),
    ("AlfabDig NT Tall Seguridad","Seguridad informática (estafas, contraseñas seguras)"),
]

ITINERANCIA_ESPACIOS = [
    ("Itinerancia Club",    "Club",                  None),
    ("Itinerancia Plaza",   "Plaza/espacio público",  None),
    ("Itinerancia Terreno", "Terreno baldío",         None),
    ("Itinerancia Paraje",  "Paraje",                 None),
    ("Itinerancia Otro",    "Otro:",                  "Itinerancia Otro"),
]

ITINERANCIA_ACTIVIDADES = [
    ("Itinerancia Act Estim",        "Estimulación adecuada y plaza blanda"),
    ("Itinerancia Act PI",           "Actividades de la Pastoral de Primera Infancia"),
    ("Itinerancia Act Alfabetizacion","Alfabetización"),
    ("Itinerancia Act Merienda",     "Merienda comunitaria"),
    ("Itinerancia Act Recreacion",   "Recreación (deportes, teatro, títeres, música, baile)"),
    ("Itinerancia Act Talleres",     "Talleres de artesanías, arte, oficios"),
    ("Itinerancia Act Charlas",      "Charlas de prevención y atención de la salud"),
    ("Itinerancia Act Festividades", "Festividades y celebraciones locales"),
    ("Itinerancia Act Reuniones",    "Reuniones para trabajar sobre problemáticas barriales"),
]

ITINERANCIA_ROLES = [
    ("Itinerancia Rol 1", "Itinerancia Rol 1 Cant", "Itinerancia Rol 1 Otro"),
    ("Itinerancia Rol 2", "Itinerancia Rol 2 Cant", "Itinerancia Rol 2 Otro"),
    ("Itinerancia Rol 3", "Itinerancia Rol 3 Cant", "Itinerancia Rol 3 Otro"),
    ("Itinerancia Rol 4", "Itinerancia Rol 4 Cant", "Itinerancia Rol 4 Otro"),
]

GM_ROLES = [
    ("GM Rol 1", "GM Rol 1 Cant", "GM Rol 1 Otro"),
    ("GM Rol 2", "GM Rol 2 Cant", "GM Rol 2 Otro"),
    ("GM Rol 3", "GM Rol 3 Cant", "GM Rol 3 Otro"),
    ("GM Rol 4", "GM Rol 4 Cant", "GM Rol 4 Otro"),
]

NIVEL_SUPERIOR_SLOTS = [
    ("Articula Institucion1", "Articula Institucion1 acciones"),
    ("Articula Institucion2", "Articula Institucion2 acciones"),
    ("Articula Institucion3", "Articula Institucion3 acciones"),
    ("Articula Institucion4", "Articula Institucion4 acciones"),
    ("Articula Institucion5", "Articula Institucion5 acciones"),
]

# ── bulk delete helper ────────────────────────────────────────────────────────

def bulk_delete(conn, table, id_col, ids):
    if not ids:
        return
    placeholders = ",".join(str(i) for i in ids)
    conn.execute(text(f"DELETE FROM {table} WHERE {id_col} IN ({placeholders})"))

# ── construcción de filas para bulk insert ────────────────────────────────────

def filas_ee_base(ee_id, row):
    """Devuelve listas de dicts para bulk_insert_mappings de las subtablas base."""
    ambientes, servicios, eq_cocina, eq_info, zonas = [], [], [], [], []

    for col_csv, nombre, col_cant in AMBIENTES:
        tiene = es_si(row.get(col_csv))
        cantidad = nullable_int(row.get(col_cant)) if col_cant else None
        ambientes.append({"espacio_educativo_id": ee_id, "ambiente": nombre,
                          "tiene": tiene, "cantidad": cantidad})

    for col_csv, nombre, is_bool in SERVICIOS:
        val = str(row.get(col_csv) or "").strip()
        val_l = val.lower()
        if is_bool:
            if es_si(val):
                servicios.append({"espacio_educativo_id": ee_id, "servicio": nombre, "valor": None})
        else:
            v = clean_str(val)
            if v and val_l not in ("sin respuesta", "no tiene", "no"):
                servicios.append({"espacio_educativo_id": ee_id, "servicio": nombre, "valor": v})

    for col_csv, nombre in EQUIPOS_COCINA:
        eq_cocina.append({"espacio_educativo_id": ee_id, "equipo": nombre, "tiene": es_si(row.get(col_csv))})

    for col_csv, nombre in EQUIPOS_INFORMATICOS:
        cant = nullable_int(row.get(col_csv))
        if cant and cant > 0:
            eq_info.append({"espacio_educativo_id": ee_id, "equipo": nombre, "cantidad": cant})

    for col_csv, nombre in ZONAS:
        if es_si(row.get(col_csv)):
            zonas.append({"espacio_educativo_id": ee_id, "zona": nombre})

    return ambientes, servicios, eq_cocina, eq_info, zonas


def filas_ree(ree_id, row):
    """Devuelve dicts con listas de rows para bulk insert de subtablas del REE."""
    acciones, prioridades, btu_motivos = [], [], []
    cont_prim, cont_sec, dig_tall = [], [], []
    iter_esp, iter_act, iter_rol = [], [], []
    gm_roles, niv_sup = [], []

    for col_csv, eje, accion in ACCIONES:
        acciones.append({"relevamiento_ee_id": ree_id, "eje": eje,
                         "accion": accion, "tiene": es_si(row.get(col_csv))})

    for col_csv, nombre in PRIORIDADES:
        if es_true_bool(row.get(col_csv)):
            prioridades.append({"relevamiento_ee_id": ree_id, "necesidad": nombre, "orden": None})

    for col_csv, motivo in BTU_MOTIVOS:
        if es_true_bool(row.get(col_csv)):
            btu_motivos.append({"relevamiento_ee_id": ree_id, "motivo": motivo})

    for col_csv, contenido in CONTENIDOS_PRIM:
        if es_si(row.get(col_csv)):
            cont_prim.append({"relevamiento_ee_id": ree_id, "contenido": contenido})

    for col_csv, contenido in CONTENIDOS_SEC:
        if es_si(row.get(col_csv)):
            cont_sec.append({"relevamiento_ee_id": ree_id, "contenido": contenido})

    for col_csv, taller in DIGITAL_TALLERES:
        if es_si(row.get(col_csv)):
            dig_tall.append({"relevamiento_ee_id": ree_id, "taller": taller})

    for col_csv, espacio, col_otro in ITINERANCIA_ESPACIOS:
        if es_si(row.get(col_csv)):
            otro = clean_str(row.get(col_otro)) if col_otro else None
            iter_esp.append({"relevamiento_ee_id": ree_id, "espacio": espacio, "espacio_otro": otro})

    for col_csv, actividad in ITINERANCIA_ACTIVIDADES:
        if es_si(row.get(col_csv)):
            iter_act.append({"relevamiento_ee_id": ree_id, "actividad": actividad})

    for col_rol, col_cant, col_otro in ITINERANCIA_ROLES:
        rol = clean_str(row.get(col_rol))
        if rol and rol.lower() != "sin respuesta":
            iter_rol.append({"relevamiento_ee_id": ree_id, "rol": rol,
                             "rol_otro": clean_str(row.get(col_otro)),
                             "cantidad": nullable_int(row.get(col_cant))})

    for col_rol, col_cant, col_otro in GM_ROLES:
        rol = clean_str(row.get(col_rol))
        if rol and rol.lower() != "sin respuesta":
            gm_roles.append({"relevamiento_ee_id": ree_id, "rol": rol,
                             "rol_otro": clean_str(row.get(col_otro)),
                             "cantidad": nullable_int(row.get(col_cant))})

    for col_inst, col_acc in NIVEL_SUPERIOR_SLOTS:
        inst = clean_str(row.get(col_inst))
        if inst:
            niv_sup.append({"relevamiento_ee_id": ree_id,
                            "nombre_institucion": inst,
                            "tipo_acciones": clean_str(row.get(col_acc))})

    return acciones, prioridades, btu_motivos, cont_prim, cont_sec, dig_tall, \
           iter_esp, iter_act, iter_rol, gm_roles, niv_sup


# ── main ──────────────────────────────────────────────────────────────────────

def main():
    db = SessionLocal()
    try:
        with open(CSV_PATH, encoding="utf-8") as f:
            rows = list(csv.DictReader(f))

        emaus_by_nombre = {e.nombre: e for e in db.query(Emaus).all()}
        atl_by_emaus    = {u.emaus_id: u.id for u in
                           db.query(Usuario).filter(Usuario.rol == RolEnum.atl,
                                                    Usuario.emaus_id.isnot(None)).all()}

        # Pre-cargar EEs y REEs existentes para evitar queries individuales
        ee_existentes = {}   # (emaus_id, nombre) → EspacioEducativo
        for ee in db.query(EspacioEducativo).all():
            ee_existentes[(ee.emaus_id, ee.nombre)] = ee

        rel_existentes = {}  # emaus_id → Relevamiento
        for r in db.query(Relevamiento).filter_by(anio=2025, semestre="2").all():
            rel_existentes[r.emaus_id] = r

        ree_existentes = {}  # (rel_id, ee_id) → RelevamientoEE
        for ree in db.query(RelevamientoEE).all():
            ree_existentes[(ree.relevamiento_id, ree.espacio_educativo_id)] = ree

        # Agrupar filas por Emaús para hacer commit por grupo
        grupos = defaultdict(list)
        errores = []
        for i, row in enumerate(rows, start=2):
            nombre_csv = str(row.get("CarpetaEmaus") or "").strip()
            nombre_emaus = EMAUS_OVERRIDES.get(nombre_csv, nombre_csv)
            emaus = emaus_by_nombre.get(nombre_emaus)
            if not emaus:
                errores.append(f"Fila {i}: Emaús '{nombre_csv}' no encontrado")
                continue
            grupos[emaus.id].append((i, row))

        cont = {"ee_creados": 0, "ee_act": 0, "ree_creados": 0, "ree_act": 0}

        for emaus_id, filas in grupos.items():
            print(f"  Procesando Emaús id={emaus_id} ({len(filas)} EE)...")
            for fila_num, row in filas:
                baja = str(row.get("Baja 2026") or "").strip().lower()
                activo = baja != "x"
                nombre_ee = clean_str(row.get("Espacio Educativo"))
                if not nombre_ee:
                    errores.append(f"Fila {fila_num}: nombre vacío, se ignora")
                    continue

                # Cada EE se procesa en su propia conexión (evita timeout de TiDB)
                for intento in range(3):
                    try:
                        with engine.begin() as conn:
                            # ── EE base ──────────────────────────────────────
                            key_ee = (emaus_id, nombre_ee)
                            if key_ee in ee_existentes:
                                ee_id = ee_existentes[key_ee].id
                                es_nuevo_ee = False
                            else:
                                r = conn.execute(text(
                                    "INSERT INTO espacio_educativo (emaus_id, nombre, activo) "
                                    "VALUES (:eid, :n, :a)"
                                ), {"eid": emaus_id, "n": nombre_ee, "a": activo})
                                ee_id = r.lastrowid
                                class _EE: id = None
                                _ee = _EE(); _ee.id = ee_id
                                ee_existentes[key_ee] = _ee
                                es_nuevo_ee = True

                            conn.execute(text("""
                                UPDATE espacio_educativo SET
                                    direccion=:d, geolocalizacion=:g, renabap=:r,
                                    titularidad=:t, nombre_titular=:nt,
                                    construccion_material=:cm, rampa_acceso=:ra,
                                    acceso_principal=:ap, activo=:ac
                                WHERE id=:id
                            """), {
                                "d":  clean_str(row.get("Direccion"), maxlen=500),
                                "g":  clean_str(row.get("Geolocalizacion"), maxlen=500),
                                "r":  es_si(row.get("Barrio RENABAP")),
                                "t":  clean_str(row.get("EE Edil Titularidad")),
                                "nt": clean_str(row.get("EE Edil Titular")),
                                "cm": clean_str(row.get("EE Edil Construccion")),
                                "ra": es_si(row.get("EE Edil rampa")),
                                "ap": clean_str(row.get("EE Edil acceso por")),
                                "ac": activo, "id": ee_id,
                            })

                            bulk_delete(conn, "ee_ambiente",           "espacio_educativo_id", [ee_id])
                            bulk_delete(conn, "ee_servicio",           "espacio_educativo_id", [ee_id])
                            bulk_delete(conn, "ee_equipo_cocina",      "espacio_educativo_id", [ee_id])
                            bulk_delete(conn, "ee_equipo_informatico", "espacio_educativo_id", [ee_id])
                            bulk_delete(conn, "ee_zona",               "espacio_educativo_id", [ee_id])

                            ambientes, servicios, eq_cocina, eq_info, zonas = filas_ee_base(ee_id, row)
                            if ambientes:
                                conn.execute(text("INSERT INTO ee_ambiente (espacio_educativo_id, ambiente, tiene, cantidad) VALUES (:espacio_educativo_id, :ambiente, :tiene, :cantidad)"), ambientes)
                            if servicios:
                                conn.execute(text("INSERT INTO ee_servicio (espacio_educativo_id, servicio, valor) VALUES (:espacio_educativo_id, :servicio, :valor)"), servicios)
                            if eq_cocina:
                                conn.execute(text("INSERT INTO ee_equipo_cocina (espacio_educativo_id, equipo, tiene) VALUES (:espacio_educativo_id, :equipo, :tiene)"), eq_cocina)
                            if eq_info:
                                conn.execute(text("INSERT INTO ee_equipo_informatico (espacio_educativo_id, equipo, cantidad) VALUES (:espacio_educativo_id, :equipo, :cantidad)"), eq_info)
                            if zonas:
                                conn.execute(text("INSERT INTO ee_zona (espacio_educativo_id, zona) VALUES (:espacio_educativo_id, :zona)"), zonas)

                            # ── Relevamiento 2025-S2 ──────────────────────────
                            if baja != "o":
                                if emaus_id not in rel_existentes:
                                    atl_id = atl_by_emaus.get(emaus_id)
                                    if not atl_id:
                                        errores.append(f"Emaús id={emaus_id}: sin ATL — EE creado pero sin relevamiento 2025-S2")
                                        rel_existentes[emaus_id] = None
                                    else:
                                        res = conn.execute(text(
                                            "INSERT INTO relevamiento (emaus_id, atl_id, anio, semestre, estado) "
                                            "VALUES (:eid, :aid, 2025, '2', 'enviado')"
                                        ), {"eid": emaus_id, "aid": atl_id})
                                        class _Rel: id = None
                                        _r = _Rel(); _r.id = res.lastrowid
                                        rel_existentes[emaus_id] = _r

                                rel = rel_existentes.get(emaus_id)
                                if rel is not None:
                                    rel_id = rel.id
                                    key_ree = (rel_id, ee_id)
                                    if key_ree not in ree_existentes:
                                        res = conn.execute(text(
                                            "INSERT INTO relevamiento_ee (relevamiento_id, espacio_educativo_id) "
                                            "VALUES (:rid, :eid)"
                                        ), {"rid": rel_id, "eid": ee_id})
                                        class _REE: id = None
                                        _ree = _REE(); _ree.id = res.lastrowid
                                        ree_existentes[key_ree] = _ree
                                        cont["ree_creados"] += 1
                                    else:
                                        _ree = ree_existentes[key_ree]
                                        cont["ree_act"] += 1

                                    ree_id = _ree.id
                                    conn.execute(text("""
                                        UPDATE relevamiento_ee SET
                                            asistentes_0_6=:a06, asistentes_7_14=:a714,
                                            asistentes_15_24=:a1524, asistentes_25_35=:a2535,
                                            asistentes_35_50=:a3550, asistentes_mas_50=:am50,
                                            grupo_motor_cantidad=:gmc, grupo_motor_frecuencia=:gmf,
                                            adolescentes_referentes=:ar, adolescentes_frecuencia=:af,
                                            itinerancia_realizo=:ir, itinerancia_frecuencia=:if_,
                                            internet_acceso=:ia, internet_falta_motivo=:ifm,
                                            internet_uso_social=:ius, internet_uso_estudio=:iue,
                                            jornadas_formacion_digital=:jfd,
                                            articula_nivel_superior=:ans, nivel_superior_cantidad=:nsc,
                                            bf_apoyo_escolar=:bfae, bf_nivel_inicial=:bfni,
                                            bf_primaria=:bfp, bf_secundaria=:bfs,
                                            bf_asignaciones=:bfa, bf_discapacidad=:bfd, bf_cud=:bfc,
                                            btu_regulares=:btur, btu_egresados=:btue, btu_abandonaron=:btua,
                                            apoyo_primario_ninos=:apn, apoyo_primario_frecuencia=:apf,
                                            apoyo_primario_contenido_principal=:apcp,
                                            apoyo_secundario_adolescentes=:asa,
                                            apoyo_secundario_frecuencia=:asf,
                                            apoyo_secundario_contenido_principal=:ascp,
                                            alfa_total=:alt, alfa_6_9=:al69, alfa_10_14=:al1014,
                                            alfa_15_24=:al1524, alfa_25_mas=:al25,
                                            alfa_alfabetizadores=:alalf, alfa_frecuencia=:alfreq,
                                            dale_total=:dt, dale_6_9=:d69, dale_10_14=:d1014,
                                            dale_15_24=:d1524, dale_25_mas=:d25,
                                            dale_educadores=:de, dale_frecuencia_dias=:dfd
                                        WHERE id=:id
                                    """), {
                                        "a06":    nullable_int(row.get("Asistentes 0 6")),
                                        "a714":   nullable_int(row.get("Asistentes 7 14")),
                                        "a1524":  nullable_int(row.get("Asistentes 15 24")),
                                        "a2535":  nullable_int(row.get("Asistentes 25 34")),
                                        "a3550":  nullable_int(row.get("Asistentes 35 50")),
                                        "am50":   nullable_int(row.get("Asistentes Mas 50")),
                                        "gmc":    nullable_int(row.get("GM RC Nro")),
                                        "gmf":    clean_str(row.get("GM RC Freq")),
                                        "ar":     nullable_int(row.get("AyJ Nro")),
                                        "af":     clean_str(row.get("AyJ Freq")),
                                        "ir":     es_si(row.get("Itinerancia Activ")),
                                        "if_":    clean_str(row.get("Itinerancia Freq")),
                                        "ia":     es_si(row.get("AlfabDig NT AccesoInternet")),
                                        "ifm":    clean_str(row.get("AlfabDig NT AccesoInternet Falta")),
                                        "ius":    nullable_bool(row.get("AlfabDig NT Internet Uso")),
                                        "iue":    nullable_bool(row.get("AlfabDig NT Internet Estudio")),
                                        "jfd":    es_si(row.get("AlfabDig NT Formacion")),
                                        "ans":    es_si(row.get("Articula InstNivelSuperior")),
                                        "nsc":    nullable_int(row.get("Articula InstNivelSuperior Cuantas")),
                                        "bfae":   nullable_int(row.get("BF Nro ApEscolar")),
                                        "bfni":   nullable_int(row.get("BF Nro Inicial")),
                                        "bfp":    nullable_int(row.get("BF Nro Primaria")),
                                        "bfs":    nullable_int(row.get("BF Nro Secundaria")),
                                        "bfa":    nullable_int(row.get("BF Nro Asignaciones")),
                                        "bfd":    nullable_int(row.get("BF Nro Discapacidad")),
                                        "bfc":    nullable_int(row.get("BF Nro Discapacidad CUD")),
                                        "btur":   nullable_int(row.get("BTU regulares")),
                                        "btue":   nullable_int(row.get("BTU egresados")),
                                        "btua":   nullable_int(row.get("BTU abandono")),
                                        "apn":    nullable_int(row.get("ApEscolar Nro Primaria")),
                                        "apf":    clean_str(row.get("ApEscolar Freq Primaria")),
                                        "apcp":   clean_str(row.get("ApEscolar Contenido Prim May")),
                                        "asa":    nullable_int(row.get("ApEscolar Nro Secundaria")),
                                        "asf":    clean_str(row.get("ApEscolar Freq Secundaria")),
                                        "ascp":   clean_str(row.get("ApEscolar Contenido Sec May")),
                                        "alt":    nullable_int(row.get("Alfabetizacion Nro")),
                                        "al69":   nullable_int(row.get("Alfabetizacion 6 a 9")),
                                        "al1014": nullable_int(row.get("Alfabetizacion 10 a 14")),
                                        "al1524": nullable_int(row.get("Alfabetizacion 15 a 24")),
                                        "al25":   nullable_int(row.get("Alfabetizacion 25mas")),
                                        "alalf":  nullable_int(row.get("Alfabetizacion CantAlfabetizadores")),
                                        "alfreq": clean_str(row.get("Alfabetizacion Freq")),
                                        "dt":     nullable_int(row.get("DALE Nro")),
                                        "d69":    nullable_int(row.get("DALE 6 a 9")),
                                        "d1014":  nullable_int(row.get("DALE 10 a 14")),
                                        "d1524":  nullable_int(row.get("DALE 15 a 24")),
                                        "d25":    nullable_int(row.get("DALE 25mas")),
                                        "de":     nullable_int(row.get("DALE EducadoresDale")),
                                        "dfd":    clean_str(row.get("DALE Freq")),
                                        "id":     ree_id,
                                    })

                                    for tbl in [
                                        "relevamiento_ee_accion", "relevamiento_ee_necesidad_infra",
                                        "relevamiento_ee_btu_abandono_motivo",
                                        "relevamiento_ee_apoyo_primario_contenido",
                                        "relevamiento_ee_apoyo_secundario_contenido",
                                        "relevamiento_ee_digital_taller",
                                        "relevamiento_ee_itinerancia_espacio",
                                        "relevamiento_ee_itinerancia_actividad",
                                        "relevamiento_ee_itinerancia_rol",
                                        "relevamiento_ee_grupo_motor_rol",
                                        "relevamiento_ee_nivel_superior",
                                    ]:
                                        bulk_delete(conn, tbl, "relevamiento_ee_id", [ree_id])

                                    acc, prio, btu, cp, cs, dgt, ie, ia2, irol, gmr, ns = filas_ree(ree_id, row)
                                    if acc:  conn.execute(text("INSERT INTO relevamiento_ee_accion (relevamiento_ee_id, eje, accion, tiene) VALUES (:relevamiento_ee_id, :eje, :accion, :tiene)"), acc)
                                    if prio: conn.execute(text("INSERT INTO relevamiento_ee_necesidad_infra (relevamiento_ee_id, necesidad, orden) VALUES (:relevamiento_ee_id, :necesidad, :orden)"), prio)
                                    if btu:  conn.execute(text("INSERT INTO relevamiento_ee_btu_abandono_motivo (relevamiento_ee_id, motivo) VALUES (:relevamiento_ee_id, :motivo)"), btu)
                                    if cp:   conn.execute(text("INSERT INTO relevamiento_ee_apoyo_primario_contenido (relevamiento_ee_id, contenido) VALUES (:relevamiento_ee_id, :contenido)"), cp)
                                    if cs:   conn.execute(text("INSERT INTO relevamiento_ee_apoyo_secundario_contenido (relevamiento_ee_id, contenido) VALUES (:relevamiento_ee_id, :contenido)"), cs)
                                    if dgt:  conn.execute(text("INSERT INTO relevamiento_ee_digital_taller (relevamiento_ee_id, taller) VALUES (:relevamiento_ee_id, :taller)"), dgt)
                                    if ie:   conn.execute(text("INSERT INTO relevamiento_ee_itinerancia_espacio (relevamiento_ee_id, espacio, espacio_otro) VALUES (:relevamiento_ee_id, :espacio, :espacio_otro)"), ie)
                                    if ia2:  conn.execute(text("INSERT INTO relevamiento_ee_itinerancia_actividad (relevamiento_ee_id, actividad) VALUES (:relevamiento_ee_id, :actividad)"), ia2)
                                    if irol: conn.execute(text("INSERT INTO relevamiento_ee_itinerancia_rol (relevamiento_ee_id, rol, rol_otro, cantidad) VALUES (:relevamiento_ee_id, :rol, :rol_otro, :cantidad)"), irol)
                                    if gmr:  conn.execute(text("INSERT INTO relevamiento_ee_grupo_motor_rol (relevamiento_ee_id, rol, rol_otro, cantidad) VALUES (:relevamiento_ee_id, :rol, :rol_otro, :cantidad)"), gmr)
                                    if ns:   conn.execute(text("INSERT INTO relevamiento_ee_nivel_superior (relevamiento_ee_id, nombre_institucion, tipo_acciones) VALUES (:relevamiento_ee_id, :nombre_institucion, :tipo_acciones)"), ns)

                        # engine.begin() auto-commit al salir sin excepción
                        if es_nuevo_ee:
                            cont["ee_creados"] += 1
                        else:
                            cont["ee_act"] += 1
                        break  # éxito — no reintentar

                    except Exception as exc:
                        if intento < 2 and "2013" in str(exc):
                            import time
                            print(f"    Conexión perdida en fila {fila_num}, reintento {intento+1}/2...")
                            time.sleep(2)
                            engine.dispose()  # fuerza reconexión limpia
                        else:
                            errores.append(f"Fila {fila_num} ({nombre_ee}): {exc}")
                            break

        print("\n── Resultado ────────────────────────────────────────────────")
        print(f"  EE creados:              {cont['ee_creados']}")
        print(f"  EE actualizados:         {cont['ee_act']}")
        print(f"  REE 2025-S2 creados:     {cont['ree_creados']}")
        print(f"  REE 2025-S2 actualizados:{cont['ree_act']}")
        if errores:
            print(f"\n  ERRORES ({len(errores)}):")
            for e in errores:
                print(f"    ⚠  {e}")
        else:
            print("  Sin errores.")

    finally:
        db.close()


if __name__ == "__main__":
    main()
