"""
Scraper standalone de datos individuales de becarios BTU (Becas Terciarias y
Universitarias).

Fuente: carpeta de Drive independiente de la del relevamiento (compartida con
la cuenta de servicio), con una subcarpeta por diócesis y, dentro de cada una,
una planilla "0-<DIOCESIS> BTU ..." con una hoja por año (ej. "2026").

No corre junto al sync de EE ni depende de anio/semestre del relevamiento —
se ejecuta a mano cuando haga falta actualizar los datos de BTU:

    python scripts/scraper_btu_becarios.py --anio 2026
    python scripts/scraper_btu_becarios.py --anio 2026 --dry-run
    python scripts/scraper_btu_becarios.py --anio 2026 --diocesis Salta

Guarda DNI y nombre completo en la base (para poder actualizar el mismo
registro entre corridas, upsert por DNI+año) pero esos datos nunca se
exponen en el tablero — ahí solo se muestran agregados.
"""
import argparse
import re
import sys
import unicodedata
from datetime import date, datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

_env_path = Path(__file__).resolve().parent.parent.parent / ".env"
if _env_path.exists():
    from dotenv import load_dotenv
    load_dotenv(_env_path)

from sqlalchemy import text

from scripts.scraper_control import build_services, get_engine

BTU_FOLDER_ID = "1bkPsSs7HIweYDoI3DAL0dZGyRVtzR8_A"
MESES = ["febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto",
         "septiembre", "octubre", "noviembre", "diciembre"]

# Alias para nombres de carpeta de diócesis que no coinciden textualmente con
# emaus.nombre (se compara ya normalizado: minúsculas, sin tildes, sin guiones).
ALIAS_DIOCESIS = {
    "san carlos de bariloche": "bariloche",
    "sde": "santiago del estero",
    "san roque": "pinedo gancedo",
    "comodoro": "comodoro rivadavia",
    "concepcion": "concepcion del uruguay",
    # "posadas": no corresponde a ningún Emaús vigente — se deja sin matchear a propósito.
}
PREFIJOS_DIOCESIS = ("prelatura de ", "diocesis de ", "arquidiocesis de ", "obispado de ")


# ---------------------------------------------------------------------------
# Clasificación de carrera en "Rama" — mismo criterio que el script del año
# pasado (Informes Emaus/Scripts/scrappeo BTUs.py), portado tal cual.
# ---------------------------------------------------------------------------
RAMAS_DICT = {
    'arte': 'Arte / Diseño', 'diseño': 'Arte / Diseño', 'diseno': 'Arte / Diseño',
    'musica': 'Arte / Diseño', 'teatro': 'Arte / Diseño', 'fotograf': 'Arte / Diseño',
    'danza': 'Arte / Diseño',
    'biolog': 'Ciencias Biologicas', 'bioquim': 'Ciencias Biologicas',
    'veterin': 'Ciencias Biologicas', 'jardineria': 'Ciencias Biologicas',
    'agronom': 'Ciencias Biologicas', 'energia': 'Ciencias Biologicas',
    'agroecolog': 'Ciencias Biologicas', 'agrop': 'Ciencias Biologicas',
    'mineros': 'Ciencias Biologicas',
    'guardaparques': 'Ciencias Sociales',
    'contad': 'Ciencias Economicas', 'econom': 'Ciencias Economicas',
    'administr': 'Ciencias Economicas', 'finanzas': 'Ciencias Economicas',
    'comercio': 'Ciencias Economicas',
    'matemat': 'Ciencias Exactas', 'fisica': 'Ciencias Exactas', 'quimic': 'Ciencias Exactas',
    'ingenier': 'Ingenieria', 'sistemas': 'Ingenieria', 'informatica': 'Ingenieria',
    'programacion': 'Ingenieria', 'robotica': 'Ingenieria', 'civil': 'Ingenieria',
    'industrial': 'Ingenieria',
    'abogacia': 'Ciencias Sociales', 'social': 'Ciencias Sociales', 'trabajo': 'Ciencias Sociales',
    'marketing': 'Ciencias Sociales', 'procurado': 'Ciencias Sociales',
    'periodismo': 'Ciencias Sociales', 'psico': 'Ciencias Sociales',
    'recursos humanos': 'Ciencias Sociales', 'rrhh': 'Ciencias Sociales',
    'sociolog': 'Ciencias Sociales', 'comunic': 'Ciencias Sociales', 'turismo': 'Ciencias Sociales',
    'derecho': 'Ciencias Sociales', 'politic': 'Ciencias Sociales',
    'profesor': 'Enseñanza', 'maestra': 'Enseñanza', 'maestro': 'Enseñanza',
    'docente': 'Enseñanza', 'educacion': 'Enseñanza',
    'oficio': 'Oficios', 'tecnico': 'Oficios', 'gastronom': 'Oficios', 'mecanic': 'Oficios',
    'estetica': 'Oficios', 'electric': 'Oficios', 'instrumentacion': 'Oficios', 'cocina': 'Oficios',
    'enfermer': 'Salud', 'medic': 'Salud', 'salud': 'Salud', 'kinesiolog': 'Salud',
    'nutric': 'Salud', 'odontolog': 'Salud', 'farmac': 'Salud', 'fisioterap': 'Salud',
    'cuidados geron': 'Salud', 'anestes': 'Salud', 'higiene': 'Salud',
    'analisis clinicos': 'Salud', 'dental': 'Salud', 'hemoterapia': 'Salud',
}
RAMAS_EXACTAS = {
    'profesorado de biologia': 'Enseñanza', 'educacion inicial': 'Enseñanza',
    'profesorado de educacion primaria': 'Enseñanza', 'magisterio': 'Enseñanza',
    'profesorado de educacion fisica': 'Enseñanza', 'profesorado de historia': 'Enseñanza',
    'profesorado de psicologia': 'Enseñanza', 'licenciatura en trabajo social': 'Ciencias Sociales',
    'licenciatura en administracion de empresas': 'Ciencias Economicas', 'abogacia': 'Ciencias Sociales',
    'profesorado de educacion secundaria en fisica': 'Enseñanza', 'profesorado de fisica': 'Enseñanza',
    'trabajo social': 'Ciencias Sociales', 'enfermeria universitaria': 'Salud',
    'licenciatura en turismo': 'Ciencias Sociales', 'licenciatura en psicologia': 'Ciencias Sociales',
    'diseno de imagen y sonido': 'Arte / Diseño', 'medicina': 'Salud',
    'ciencias politicas': 'Ciencias Sociales', 'profesorado de eduacion primaria': 'Enseñanza',
    'profesorado de educacion especial': 'Enseñanza', 'tecnicatura en turismo': 'Ciencias Sociales',
    'ingenieria electronica': 'Ingenieria', 'profesorado de matematica': 'Enseñanza',
    'profesorado de nivel inicial': 'Enseñanza', 'profesorado de primaria': 'Enseñanza',
    'tecnicatura superior en emergencias medicas': 'Salud', 'licenciatura en enfermeria': 'Salud',
    'profesorado de educacion inicial': 'Enseñanza', 'profesorado de lengua y literatura': 'Enseñanza',
    'profesorado de nivel primaria': 'Enseñanza', 'profesorado de ensenanza primaria': 'Enseñanza',
    'tecnicatura superior en turismo': 'Ciencias Sociales', 'profesorado de musica': 'Enseñanza',
    'profesorado de artes visuales': 'Enseñanza', 'licenciatura en geologia': 'Ciencias Exactas',
    'profesorado de educacion secundaria biologia': 'Enseñanza', 'ingenieria agronoma': 'Ingenieria',
    'profesorado de danzas': 'Enseñanza', 'profesorado de ciencias de la educacion': 'Enseñanza',
    'tecnicatura superior en rrhh': 'Ciencias Sociales',
    'profesorado de educacion secundaria de historia': 'Enseñanza', 'profesorado de quimica': 'Enseñanza',
    'ingenieria en minas': 'Ingenieria', 'tecnicatura superior en acompañante terapeutico': 'Ciencias Sociales',
    'contador publico': 'Ciencias Economicas', 'licenciatura en nutricion': 'Salud',
    'licenciatura en organizacion industrial': 'Ciencias Economicas', 'licenciatura en obstetricia': 'Salud',
    'licenciatura en historia': 'Ciencias Sociales', 'licenciatura en kinesiologia y fisiatria': 'Salud',
    'profesorado de ducacion fisica': 'Enseñanza', 'pep - profesorado de educacion primaria': 'Enseñanza',
    'tecnicatura en instrumentacion': 'Salud', 'profesorado de filosofia': 'Enseñanza',
    'tramo pedagogico formacion docente': 'Ciencias Sociales',
    'profesorado de educacion secundaria de matematica': 'Enseñanza',
    'licenciatura y profesorado de biologia': 'Enseñanza',
    'tecnicatura superior en trabajo social': 'Ciencias Sociales',
    'profesorado de educacion secundaria de lengua y literatura': 'Enseñanza',
    'licenciatura en relaciones laborales': 'Ciencias Sociales',
    'licenciatura en sistema de informacion': 'Ciencias Exactas', 'profesorado de ingles': 'Enseñanza',
    'profesorado de biologia licenciatura en biologia': 'Enseñanza',
    'tecnicatura superior en gastronomia': 'Ciencias Sociales', 'profesorado de idiomas': 'Enseñanza',
    'ingieniera agronoma': 'Ingenieria', 'tecnicatura superior en analisis y software': 'Ciencias Exactas',
    'ingenieria electrica': 'Ingenieria', 'profesorado ciencias de la educacion': 'Enseñanza',
    'profesorado de educacion tecnologica': 'Enseñanza',
    'tecnicatura superior en psicopedagogia': 'Ciencias Sociales', 'ingenieria civil': 'Ingenieria',
    'tecnicatura superior en enfermeria': 'Salud', 'odontologia': 'Salud',
    'profesorado de educacion secundaria en geografia': 'Enseñanza',
    'tecnicatura en higiene y seguridad laboral': 'Salud',
    'licenciatura en psicopedagogia': 'Ciencias Sociales', 'profesorado de ducacion primaria': 'Enseñanza',
    'profesorado de educacion de educacion inicial': 'Enseñanza',
    'tecnicatura en administracion contable': 'Ciencias Economicas', 'ingenieria quimica': 'Ingenieria',
    'profesorado de educacion secundaria en matematica': 'Enseñanza',
    'tecnicatura superior en acompanante terapeutico': 'Ciencias Sociales', 'ingenieria': 'Ingenieria',
    'profesorado de educacion secundaria en historia': 'Enseñanza',
    'tecnicatura en guardavidas': 'Salud', 'licenciatura bromatologia': 'Salud',
    'licenciatura en enfermeria/ medicina': 'Salud', 'instrumentacion quirurgica': 'Salud',
    'ciencias de la educacion': 'Ciencias Sociales', 'tecnicatura en asistencia dental': 'Salud',
    'profesorado de geografia': 'Enseñanza', 'analista de sistemas': 'Ciencias Exactas',
    'profesorado de tecnologia': 'Enseñanza', 'profesorado de letras': 'Enseñanza',
    'profesorado de economia': 'Enseñanza', 'licenciatura en musica': 'Arte / Diseño',
    'geologia': 'Ciencias Exactas', 'licenciatura en gestion ambiental': 'Salud',
    'licenciatura en ciencias de la comunicacion social': 'Ciencias Sociales',
    'profesorado de artes visuales con orientacion de pintura': 'Enseñanza',
    'profesorado de ciencias politicas': 'Enseñanza', 'profesorado de informatica': 'Enseñanza',
    'trayecto artistico profesorado de musica con itinerante en musica folclorica': 'Enseñanza',
    'tecnicatura superior en hoteleria': 'Ciencias Economicas',
    'profesorado de educacion especial con orientacion en discapacidad intelectual': 'Enseñanza',
    'tecnicatura superior en administracion servicios de salud': 'Ciencias Economicas',
    'tecnicatura superior en gestion hotelera': 'Ciencias Economicas', 'traductorado de ingles': 'Ciencias Sociales',
    'licenciatura en kinesiologia': 'Salud', 'profesorado de educacion secundaria en economia': 'Enseñanza',
    'profesorado de lengua': 'Enseñanza', 'tecnicatura en guia de turismo': 'Ciencias Sociales',
    'tecnicatura superior en gestion contable impositiva': 'Ciencias Economicas',
    'traductorado literario y tecnico en portugues': 'Ciencias Sociales',
    'tecnicatura superior en inspeccion bromatologica': 'Ciencias Biologicas', 'bioquimica': 'Salud',
    'tecnicatura superior en electricidad industrial': 'Ciencias Exactas',
    'tecnicatura superior en laboratorio': 'Salud',
    'tecnicatura superior en comunicacion social': 'Ciencias Sociales', 'licenciatura en letras': 'Arte / Diseño',
    'licenciatura en educacion para la salud': 'Salud',
    'profesorado de tecnologia de la informacion y la comunicacion (tic)': 'Enseñanza',
    'licenciatura en ciencias de la educacion': 'Ciencias Sociales',
    'tecnicatura superior en desarrollo de aplicaciones moviles': 'Ciencias Exactas',
    'enfermeria profesional': 'Salud', 'ingenieria industrial': 'Ingenieria',
    'licenciatura en comunicacion social': 'Ciencias Sociales',
    'tecnicatura en alimentacion de animales de granja': 'Ciencias Biologicas',
    'tecnicatura en industrias del hogar': 'Salud', 'preceptoria': 'Ciencias Sociales',
    'analista programador': 'Ciencias Exactas', 'licenciatura en criminologia': 'Ciencias Sociales',
    'geofisica': 'Ciencias Exactas', 'licenciatura en biotecnologia y biologia molecular': 'Ciencias Biologicas',
    'arquitectura': 'Ciencias Exactas', 'psicologia': 'Ciencias Sociales',
    'profesorado de ensenanza especial': 'Enseñanza', 'tecnicatura en alimentos': 'Salud',
    'enfermeria': 'Salud', 'tecnicatura en gestion y administracion rural': 'Ciencias Economicas',
    'profesorado de educacion especial con orientacion de sordos e hipoacusicos': 'Enseñanza',
    'tecnicatura en artes visuales': 'Arte / Diseño', 'tecnicatura en informatica': 'Ciencias Exactas',
    'quimica': 'Ciencias Exactas', 'ingles': 'Enseñanza', 'educacion especial': 'Enseñanza',
    'educacion fisica': 'Enseñanza', 'psicopedagogia': 'Ciencias Sociales', 'licenciatura en artes': 'Arte / Diseño',
    'veterinaria': 'Ciencias Biologicas',
    'tecnicatura universitaria gestion y riesgo en higiene y seguridad': 'Salud',
    'tecnicatura en ninez adolescencia y familia': 'Ciencias Sociales', 'ingenieria electromecanica': 'Ingenieria',
    'ilustracion': 'Arte / Diseño', 'tecnicatura superior en automatizacion y control': 'Ciencias Economicas',
    'tecnicatura superior en enfermeria profesional': 'Salud',
    'tecnicatura universitaria de gestion de politicas publicas': 'Ciencias Economicas',
    'diseno grafico': 'Ciencias Exactas', 'tecnicatura en logistica': 'Ciencias Economicas',
    'tecnicatura preparacion fisica': 'Salud', 'tecnicatura en comunicacion': 'Ciencias Sociales',
    'licenciatura en educacion fisica': 'Ciencias Sociales', 'ingenieria informatica': 'Ingenieria',
    'artes visuales': 'Arte / Diseño', 'licenciatura en ciencias de la comunicacion': 'Ciencias Sociales',
    'profesorado de la educacion secundaria en matematic': 'Enseñanza',
    'tecnicatura en administracion de empresas agropecuarias': 'Ciencias Economicas', 'farmacia': 'Salud',
    'profesorado 3er ciclo de la egb y de la educacion polimodal en lengua': 'Enseñanza',
    'tecnicatura en electricidad': 'Oficios', 'tecnicatura en gestion de proyecto': 'Ciencias Economicas',
    'profesorado de educacion secundaria en lengua y literatura': 'Enseñanza',
    'perito superior en investigacion criminalistica': 'Ciencias Sociales',
    'enfermera universitaria': 'Enseñanza', 'tecnicatura superior en administracion de pymes': 'Ciencias Economicas',
    'tecnicatura en informatica de gestion': 'Ciencias Exactas', 'guia de turismo': 'Ciencias Sociales',
    'profesorado de educacion secundaria geografia': 'Enseñanza',
    'tecnicatura superior en periodismo': 'Ciencias Sociales',
    'licenciatura en musica con orientacion en musica popular': 'Arte / Diseño',
    'licenciatura en economia social y solidaria': 'Ciencias Economicas',
    'higiene y seguridad en el trabajo': 'Salud', 'tecnicatura superior en gestion industrial': 'Ciencias Economicas',
    'tecnicatura en mecatronica': 'Ingenieria', 'profesorado de ciencias de la administracion': 'Enseñanza',
    'tecnicatura en laboratorio': 'Ciencias Biologicas', 'tecnicatura en lenguas': 'Ciencias Sociales',
    'pei - profesorado de educacion inicial': 'Enseñanza', 'diagnostico por imagenes': 'Salud',
    'tecnicatura en comercializacion': 'Ciencias Economicas', 'ingenieria mecanica': 'Ingenieria',
    'licenciatura en psicomotricidad': 'Salud', 'licenciatura en ciencias fisicas': 'Ciencias Exactas',
    'profesorado de secundaria en psicologia': 'Enseñanza', 'ingenieria telecomunicaciones': 'Ingenieria',
    'licenciatura en administracion y tecnicatura universitaria en gestion de las organizaciones': 'Ciencias Economicas',
    'radiologia por imagen': 'Salud', 'licenciatura en comunicacion': 'Ciencias Sociales',
    'licenciatura en rrhh': 'Ciencias Sociales', 'ingenieria recursos naturales y medio ambiente': 'Ingenieria',
    'tecnicatura en responsabilidad y gestion social': 'Ciencias Economicas',
    'tecnicatura en diseno y animacion digital': 'Ciencias Sociales',
    'tecnicatura en gestion y administracion de empresas': 'Ciencias Economicas',
    'tecnicatura traductorado de ingles': 'Ciencias Sociales',
    'licenciatura en administracion rural': 'Ciencias Economicas', 'sociologia': 'Ciencias Sociales',
    'seguridad ciudadana': 'Ciencias Sociales', 'ciencias agrarias': 'Ciencias Biologicas',
    'fonoaudiologia': 'Salud', 'ingenieria metalurgica': 'Ingenieria', 'licenciatura en fonoaudiologia': 'Salud',
    'ingenieria industrias de la alimentacion': 'Ingenieria', 'tecnicatura agropecuario': 'Ciencias Economicas',
    'profesorado de formacion docente en biblotecnologia': 'Enseñanza',
    'tecnicatura superior en economia social y desarrollo local': 'Ciencias Economicas',
    'tecnicatura superior en cap pedagogica tecnicos/prof': 'Ciencias Sociales',
    'licenciatura en educacion': 'Ciencias Sociales', 'comercio exterior': 'Ciencias Economicas',
    'tecnicatura en seguridad e higiene': 'Salud',
    'tecnicatura superior en gerenciamiento y conduccion de rrhh': 'Ciencias Economicas',
    'licenciatura en terapia ocupacional': 'Salud', 'pedagogia social': 'Ciencias Sociales',
    'tecnicatura superior en psicologia social': 'Ciencias Sociales',
    'licenciatura en gestion gubernamental': 'Ciencias Economicas', 'filosofia y letras': 'Ciencias Sociales',
}


def normalizar_texto(texto) -> str:
    if not isinstance(texto, str):
        return ''
    texto = texto.lower()
    texto = unicodedata.normalize('NFKD', texto)
    return ''.join(c for c in texto if not unicodedata.combining(c))


def clasificar_rama(carrera: Optional[str]) -> str:
    if not carrera or not isinstance(carrera, str):
        return 'Sin clasificar'
    carrera_norm = normalizar_texto(carrera.strip())
    for key, rama in RAMAS_EXACTAS.items():
        if normalizar_texto(key) == carrera_norm:
            return rama
    for clave, rama in RAMAS_DICT.items():
        if normalizar_texto(clave) in carrera_norm:
            return rama
    return 'Sin clasificar'


def normalizar_diocesis(nombre: str) -> str:
    s = nombre.strip().lower().replace('-', ' ')
    s = unicodedata.normalize('NFKD', s)
    s = ''.join(c for c in s if not unicodedata.combining(c))
    s = ' '.join(s.split())
    for pref in PREFIJOS_DIOCESIS:
        if s.startswith(pref):
            s = s[len(pref):]
    return ALIAS_DIOCESIS.get(s, s)


def parsear_fecha(valor) -> Optional[date]:
    if not valor:
        return None
    valor = str(valor).strip()
    if not valor:
        return None
    for fmt in ("%d/%m/%Y", "%Y-%m-%d", "%d-%m-%Y"):
        try:
            return datetime.strptime(valor, fmt).date()
        except ValueError:
            continue
    return None


def parsear_edad(valor) -> Optional[int]:
    try:
        return int(str(valor).strip())
    except (TypeError, ValueError):
        return None


def es_afirmativo(valor) -> bool:
    return str(valor or '').strip().lower() in ('x', 'si', 'sí', 'true', '1')


def parsear_progresar(valor) -> Optional[bool]:
    v = str(valor or '').strip().lower()
    if v in ('si', 'sí'):
        return True
    if v == 'no':
        return False
    return None


def cell(fila: List, idx: int) -> str:
    if idx < 0 or idx >= len(fila):
        return ''
    v = fila[idx]
    return '' if v is None else str(v).strip()


# ---------------------------------------------------------------------------
# Drive: listado de carpetas de diócesis y su planilla principal
# ---------------------------------------------------------------------------

def listar_carpetas_diocesis(drive_svc) -> List[Dict]:
    resp = drive_svc.files().list(
        q=f"'{BTU_FOLDER_ID}' in parents and trashed = false and mimeType = 'application/vnd.google-apps.folder'",
        fields="files(id, name)", pageSize=200,
        supportsAllDrives=True, includeItemsFromAllDrives=True,
    ).execute()
    return resp.get("files", [])


def encontrar_planilla_principal(drive_svc, carpeta_id: str) -> Optional[Dict]:
    resp = drive_svc.files().list(
        q=f"'{carpeta_id}' in parents and trashed = false and "
          f"mimeType = 'application/vnd.google-apps.spreadsheet'",
        fields="files(id, name)", pageSize=10,
        supportsAllDrives=True, includeItemsFromAllDrives=True,
    ).execute()
    archivos = resp.get("files", [])
    return archivos[0] if archivos else None


def listar_subcarpetas(drive_svc, carpeta_id: str) -> List[Dict]:
    resp = drive_svc.files().list(
        q=f"'{carpeta_id}' in parents and trashed = false and mimeType = 'application/vnd.google-apps.folder'",
        fields="files(id, name)", pageSize=50,
        supportsAllDrives=True, includeItemsFromAllDrives=True,
    ).execute()
    return resp.get("files", [])


def descubrir_unidades(drive_svc, carpeta: Dict) -> List[Tuple[str, Dict]]:
    """Devuelve [(nombre_unidad, planilla)] para una carpeta de diócesis.
    La mayoría tiene la planilla directamente adentro; si no (ej. Santiago
    del Estero, que tiene subcarpetas SDE/La Banda), se busca un nivel más
    abajo y cada subcarpeta con planilla propia se trata como una unidad."""
    planilla = encontrar_planilla_principal(drive_svc, carpeta["id"])
    if planilla:
        return [(carpeta["name"], planilla)]

    unidades = []
    for sub in listar_subcarpetas(drive_svc, carpeta["id"]):
        sub_planilla = encontrar_planilla_principal(drive_svc, sub["id"])
        if sub_planilla:
            unidades.append((sub["name"], sub_planilla))
    return unidades


# ---------------------------------------------------------------------------
# Parseo de la hoja de un año
# ---------------------------------------------------------------------------

def leer_becarios_planilla(sheets_svc, spreadsheet_id: str, anio: str) -> Tuple[Optional[str], List[Dict], Optional[str]]:
    """Devuelve (nombre_diocesis_en_hoja, lista_de_becarios_dict, error)."""
    try:
        resp = sheets_svc.spreadsheets().values().get(
            spreadsheetId=spreadsheet_id, range=f"{anio}!A1:AN500",
        ).execute()
    except Exception as e:
        return None, [], f"error leyendo hoja '{anio}': {e}"

    rows = resp.get("values", [])
    if not rows:
        return None, [], f"hoja '{anio}' vacía o no existe"

    # Buscar la celda "Emaus" (define la columna base / offset) y el nombre
    # de diócesis en la primera celda no vacía a su derecha.
    fila_emaus = None
    offset = None
    nombre_diocesis = None
    for i, fila in enumerate(rows):
        for j, val in enumerate(fila):
            if normalizar_texto(str(val).strip()) == "emaus":
                fila_emaus, offset = i, j
                for k in range(j + 1, len(fila)):
                    if str(fila[k]).strip():
                        nombre_diocesis = str(fila[k]).strip()
                        break
                break
        if fila_emaus is not None:
            break

    if fila_emaus is None:
        return None, [], "no se encontró la celda 'Emaus' (offset de columnas)"

    # Buscar la fila de encabezados (algunas filas después de "Emaus")
    fila_encabezados = None
    patrones = ('apellido', 'dni', 'sexo', 'fecha', 'edad', 'nivel', 'ambito', 'carrera')
    for i in range(fila_emaus + 1, min(fila_emaus + 6, len(rows))):
        texto = [normalizar_texto(str(c)) for c in rows[i]]
        coincidencias = sum(1 for p in patrones for c in texto if p in c)
        if coincidencias >= 3:
            fila_encabezados = i
            break
    if fila_encabezados is None:
        fila_encabezados = fila_emaus + 3  # fallback razonable según la plantilla

    fila_inicio = fila_encabezados + 1

    becarios = []
    for i in range(fila_inicio, len(rows)):
        fila = rows[i]
        apellido_nombres = cell(fila, offset + 3)
        dni = re.sub(r"\D", "", cell(fila, offset + 4)) or None
        if not apellido_nombres or len(apellido_nombres) < 3:
            continue
        if apellido_nombres.strip().upper().startswith('NUEVOS BECADOS'):
            continue

        sexo_f = cell(fila, offset + 5)
        sexo_m = cell(fila, offset + 6)
        sexo = 'F' if es_afirmativo(sexo_f) else ('M' if es_afirmativo(sexo_m) else None)

        nivel_terciario = cell(fila, offset + 11)
        nivel_universitario = cell(fila, offset + 12)
        nivel = ('Terciario' if es_afirmativo(nivel_terciario) else
                 ('Universitario' if es_afirmativo(nivel_universitario) else None))

        ambito_publico = cell(fila, offset + 13)
        ambito_privado = cell(fila, offset + 14)
        ambito = ('Publico' if es_afirmativo(ambito_publico) else
                  ('Privado' if es_afirmativo(ambito_privado) else None))

        carrera = cell(fila, offset + 15) or None
        motivo_baja = cell(fila, offset + 21) or None
        mes_fin_beca = cell(fila, offset + 23) or None
        observaciones = cell(fila, offset + 1) or None

        activo = (
            not mes_fin_beca and not motivo_baja and
            'baja' not in normalizar_texto(observaciones or '')
        )

        meses = {}
        for idx_mes, nombre_mes in enumerate(MESES):
            valor_mes = cell(fila, offset + 24 + idx_mes)
            if valor_mes:
                meses[nombre_mes] = valor_mes

        becarios.append({
            "nro": cell(fila, offset) or None,
            "observaciones": observaciones,
            "certificados": cell(fila, offset + 2) or None,
            "apellido_nombres": apellido_nombres,
            "dni": dni,
            "sexo": sexo,
            "fecha_nacimiento": parsear_fecha(cell(fila, offset + 7)),
            "edad": parsear_edad(cell(fila, offset + 8)),
            "percibe_progresar": parsear_progresar(cell(fila, offset + 9)),
            "institucion": cell(fila, offset + 10) or None,
            "nivel": nivel,
            "ambito": ambito,
            "carrera": carrera,
            "rama": clasificar_rama(carrera),
            "duracion_carrera": cell(fila, offset + 16) or None,
            "anio_comienzo_carrera": cell(fila, offset + 17) or None,
            "anio_comienzo_beca": cell(fila, offset + 18) or None,
            "anio_cursando": cell(fila, offset + 19) or None,
            "continua_periodo_siguiente": parsear_progresar(cell(fila, offset + 20)),
            "motivo_baja": motivo_baja,
            "mes_comienzo_beca": cell(fila, offset + 22) or None,
            "mes_fin_beca": mes_fin_beca,
            "activo": activo,
            "meses": meses,
        })

    return nombre_diocesis, becarios, None


# ---------------------------------------------------------------------------
# Persistencia
# ---------------------------------------------------------------------------

def upsert_becario(conn, emaus_id: int, anio: int, diocesis_nombre_hoja: str, b: Dict):
    row = {**b, "emaus_id": emaus_id, "anio": anio, "diocesis_nombre_hoja": diocesis_nombre_hoja}
    meses = row.pop("meses")

    if row["dni"]:
        existente = conn.execute(
            text("SELECT id FROM btu_becario WHERE dni = :dni AND anio = :anio"),
            {"dni": row["dni"], "anio": anio},
        ).fetchone()
    else:
        existente = None

    cols = [k for k in row.keys()]
    if existente:
        becario_id = existente[0]
        sets = ", ".join(f"{c} = :{c}" for c in cols)
        conn.execute(text(f"UPDATE btu_becario SET {sets} WHERE id = :id"), {**row, "id": becario_id})
    else:
        placeholders = ", ".join(f":{c}" for c in cols)
        result = conn.execute(
            text(f"INSERT INTO btu_becario ({', '.join(cols)}) VALUES ({placeholders})"),
            row,
        )
        becario_id = result.lastrowid

    conn.execute(text("DELETE FROM btu_becario_mes WHERE btu_becario_id = :id"), {"id": becario_id})
    if meses:
        conn.execute(
            text("INSERT INTO btu_becario_mes (btu_becario_id, mes, valor) VALUES (:id, :mes, :valor)"),
            [{"id": becario_id, "mes": m, "valor": v} for m, v in meses.items()],
        )
    return becario_id


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Scraper de becarios BTU individuales")
    parser.add_argument("--anio", required=True, help="Año/hoja a leer, ej. 2026")
    parser.add_argument("--dry-run", action="store_true", help="No escribe en la base, solo reporta")
    parser.add_argument("--diocesis", default=None, help="Procesar solo una carpeta de diócesis (para probar)")
    args = parser.parse_args()

    sheets_svc, drive_svc = build_services()
    engine = get_engine()

    with engine.connect() as conn:
        emaus_rows = conn.execute(text("SELECT id, nombre FROM emaus")).fetchall()
    emaus_por_nombre = {normalizar_diocesis(r[1]): (r[0], r[1]) for r in emaus_rows}

    carpetas = listar_carpetas_diocesis(drive_svc)
    if args.diocesis:
        carpetas = [c for c in carpetas if args.diocesis.strip().lower() in c["name"].strip().lower()]

    print(f"Carpetas de diócesis a procesar: {len(carpetas)}")

    no_matcheadas = []
    sin_planilla = []
    con_error = []
    total_becarios = 0
    total_activos = 0

    # Una conexión/transacción por diócesis (no una sola para todo el proceso):
    # el scrapeo cruza ~40 llamadas a Drive/Sheets y una transacción única
    # queda abierta demasiado tiempo sin actividad, cortando la conexión a
    # TiDB a mitad de camino y perdiendo todo el trabajo previo.
    for carpeta in carpetas:
        unidades = descubrir_unidades(drive_svc, carpeta)
        if not unidades:
            sin_planilla.append(carpeta["name"])
            continue

        for nombre_unidad, planilla in unidades:
            clave = normalizar_diocesis(nombre_unidad)
            match = emaus_por_nombre.get(clave)
            if not match:
                no_matcheadas.append(f"{carpeta['name']} / {nombre_unidad}" if nombre_unidad != carpeta["name"] else nombre_unidad)
                continue
            emaus_id, emaus_nombre = match

            nombre_diocesis_hoja, becarios, error = leer_becarios_planilla(
                sheets_svc, planilla["id"], args.anio
            )
            if error:
                con_error.append(f"{nombre_unidad} ({planilla['name']}): {error}")
                continue

            print(f"  {nombre_unidad:30s} -> {emaus_nombre:25s} | {planilla['name']:35s} | {len(becarios)} becarios")
            total_becarios += len(becarios)
            total_activos += sum(1 for b in becarios if b["activo"])

            if not args.dry_run:
                with engine.begin() as conn:
                    for b in becarios:
                        upsert_becario(conn, emaus_id, int(args.anio), nombre_diocesis_hoja or nombre_unidad, b)

    print(f"\nTotal becarios leídos: {total_becarios} (activos: {total_activos})")

    if no_matcheadas or sin_planilla or con_error:
        reporte_path = Path(__file__).resolve().parent.parent / "reporte_btu_becarios.txt"
        with open(reporte_path, "w") as f:
            f.write(f"Reporte scraper_btu_becarios — año {args.anio}\n\n")
            f.write(f"Diócesis sin Emaús correspondiente en la DB ({len(no_matcheadas)}):\n")
            for n in no_matcheadas:
                f.write(f"  - {n}\n")
            f.write(f"\nCarpetas sin planilla encontrada ({len(sin_planilla)}):\n")
            for n in sin_planilla:
                f.write(f"  - {n}\n")
            f.write(f"\nErrores de lectura ({len(con_error)}):\n")
            for n in con_error:
                f.write(f"  - {n}\n")
        print(f"\n⚠️  Hay incidencias — ver detalle en {reporte_path}")


if __name__ == "__main__":
    main()
