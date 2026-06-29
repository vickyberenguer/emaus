let espaciosCache = [];
let catNecesidadInfra = [], catPreocupacionJoven = [];

// --- Listas fijas tomadas literalmente de la planilla de Sheets ---

const AMBIENTES_FIJOS = ['Cocina', 'Salón comedor', 'Despensa / almacén / depósito', 'Baño', 'Espacio de recreación'];
const SERVICIOS_FIJOS = [
  'Servicio de cloacas', 'Energía eléctrica por red domiciliaria', 'El tratamiento de residuos',
  'Señal de telefonía móvil', 'Internet por cable, fibra óptica, satelital', 'Tipo de combustible que utiliza la cocina',
];
const EQUIPO_COCINA_FIJO = ['Cocina industrial', 'Cocina familiar', 'Mechero', 'Heladera industrial', 'Heladera familiar', 'Freezer industrial', 'Freezer familiar'];
const EQUIPO_INFORMATICO_FIJO = ['Monitor de tubo', 'Monitor plano', 'PC All in one', 'PC de escritorio', 'Notebook / laptop', 'Tablet', 'Impresora', 'Impresora multifunción (con escáner)'];
const ZONA_FIJA = ['Urbana', 'Periférica', 'Rural', 'Inundable', 'Con poco o sin acceso al transporte público'];

const ACCIONES_POR_EJE = [
  ['Primera infancia', 'Pastoral PI'], ['Primera infancia', 'Capacitaciones, talleres y encuentros'],
  ['Primera infancia', 'Espacios de Primera Infancia'], ['Primera infancia', 'Estimulación temprana'],
  ['Apoyo a las trayectorias educativas', 'Becas Familiares'], ['Apoyo a las trayectorias educativas', 'Apoyo escolar'],
  ['Apoyo a las trayectorias educativas', 'Becas Terciarias y universitarias'], ['Apoyo a las trayectorias educativas', 'Alfabetización inicial'],
  ['Apoyo a las trayectorias educativas', 'Propuesta DALE'], ['Apoyo a las trayectorias educativas', 'Actividades de lectoescritura y oralidad'],
  ['Apoyo a las trayectorias educativas', 'Rincón de lectura'], ['Apoyo a las trayectorias educativas', 'Alfabetización de adultos'],
  ['Apoyo a las trayectorias educativas', 'Promotores socio-educativos'],
  ['Integración comunitaria', 'Itinerancia'], ['Integración comunitaria', 'Mochileros'], ['Integración comunitaria', 'Ludoteca'],
  ['Integración comunitaria', 'Actividades culturales y recreativas'], ['Integración comunitaria', 'Desarrollo habilidades duras y blandas'],
  ['Integración comunitaria', 'Habilidades para el mundo del trabajo'], ['Integración comunitaria', 'Talleres para mujeres'],
  ['Integración comunitaria', 'Propuestas para adolescentes'], ['Integración comunitaria', 'Potenciar trabajo'], ['Integración comunitaria', 'Talleres de oficio'],
  ['Nuevas tecnologías', 'Capacitaciones y talleres'], ['Nuevas tecnologías', 'Equipamiento informático e internet'],
  ['Nuevas tecnologías', 'Trámites del estado (ANSES, AUH, CUD, etc)'], ['Nuevas tecnologías', 'Acceso digital comunitario'],
  ['Salud integral', 'Deportes'], ['Salud integral', 'Alimentación saludable'], ['Salud integral', 'Meriendas'],
  ['Salud integral', 'Controles médicos'], ['Salud integral', 'Capacitaciones, talleres y encuentros'], ['Salud integral', 'Huertas comunitarias'],
];

const ITINERANCIA_ESPACIOS_FIJO = ['Club', 'Plaza/espacio público', 'Terreno baldío', 'Paraje', 'Otro:'];
const ITINERANCIA_ACTIVIDADES_FIJO = [
  'Estimulación adecuada y plaza blanda', 'Actividades de la Pastoral de Primera Infancia', 'Alfabetización', 'Merienda comunitaria',
  'Recreación (deportes, teatro, títeres, música, baile)', 'Talleres de artesanías, arte, oficios', 'Charlas de prevención y atención de la salud',
  'Festividades y celebraciones locales', 'Reuniones para trabajar sobre problemáticas barriales',
];
const BTU_ABANDONO_FIJO = [
  'Incompatibilidad de la cursada con horarios laborales', 'Dificultad para costear el transporte',
  'Cambio de domicilio (mudanza)', 'Falta de tiempo por tareas de cuidado familiar',
  'Problemas de accesibilidad del transporte local', 'Falta de acceso al boleto estudiantil', 'Otro:',
];
const CONTENIDOS_ESCOLARES_FIJO = ['Lengua', 'Matemáticas', 'Ciencias Naturales', 'Ciencias Sociales', 'Inglés', 'Otro:'];
const DIGITAL_TALLERES_FIJO = [
  'Herramientas digitales (navegador, correo, drive, etc.)', 'Herramientas de Microsoft Office (Word, Excel, PowerPoint)',
  'Redes sociales (Facebook, Instagram, TikTok, WhatsApp, YouTube)', 'Seguridad informática (estafas, contraseñas seguras)',
];

function toItems(strings) { return strings.map(s => ({ value: s, label: s })); }
function toItemsCatalogo(cat) { return cat.map(c => ({ value: c.valor, label: c.valor })); }

function valorOtro(seleccion, esOtroPrefijo = 'otr') {
  // si el ítem es "Otro:" usa el texto tipeado; si no, el label tal cual
  if (seleccion.valor.toLowerCase().startsWith(esOtroPrefijo)) {
    return seleccion.otro || seleccion.valor;
  }
  return seleccion.valor;
}

async function cargarSeccionEspacios(relevamientoId) {
  document.getElementById('seccion-espacios').innerHTML = `
    <div class="card border-0 shadow-sm p-3 mb-3">
      <h6 class="mb-2"><i class="bi bi-plus-circle"></i> Nuevo espacio educativo</h6>
      <div class="row g-2">
        <div class="col-md-3"><input class="form-control" id="ee-nuevo-nombre" placeholder="Nombre"></div>
        <div class="col-md-2 d-grid"><button class="btn btn-outline-primary" id="btn-add-ee"><i class="bi bi-plus"></i> Crear</button></div>
      </div>
    </div>
    <div id="lista-espacios"></div>`;

  document.getElementById('btn-add-ee').addEventListener('click', () => crearEspacioEducativo(relevamientoId));

  if (catNecesidadInfra.length === 0) {
    [catNecesidadInfra, catPreocupacionJoven] = await Promise.all([
      api.get('/catalogos/necesidad_infra'),
      api.get('/catalogos/preocupacion_joven'),
    ]);
  }

  await refrescarEspacios(relevamientoId);
}

async function refrescarEspacios(relevamientoId) {
  espaciosCache = await api.get(`/relevamientos/${relevamientoId}/espacios-educativos`);
  const container = document.getElementById('lista-espacios');
  container.innerHTML = espaciosCache.map(ee => `
    <div class="card border-0 shadow-sm p-3 mb-3">
      <div class="d-flex justify-content-between align-items-center">
        <strong>${ee.nombre}</strong>
        <div>
          <button class="btn btn-sm btn-outline-secondary" onclick="toggleEspacio(${ee.id}, 'base')"><i class="bi bi-pencil"></i> Datos de base</button>
          <button class="btn btn-sm btn-outline-primary" onclick="toggleEspacio(${ee.id}, 'semestral')"><i class="bi bi-calendar"></i> Datos semestrales</button>
        </div>
      </div>
      <div id="ee-panel-${ee.id}" class="mt-3 hidden"></div>
    </div>`).join('') || '<p class="text-muted small">Todavía no hay espacios educativos para este Emaús. El admin debería haberlos pre-cargado — si falta alguno, avisale.</p>';
}

async function crearEspacioEducativo(relevamientoId) {
  const nombre = document.getElementById('ee-nuevo-nombre').value.trim();
  if (!nombre) { alert('El nombre es obligatorio'); return; }
  try {
    await api.post(`/relevamientos/${relevamientoId}/espacios-educativos`, { nombre });
    document.getElementById('ee-nuevo-nombre').value = '';
    await refrescarEspacios(relevamientoId);
  } catch (err) {
    alert(err.message);
  }
}

let panelAbierto = null;

async function toggleEspacio(eeId, modo) {
  const panel = document.getElementById(`ee-panel-${eeId}`);
  if (panelAbierto && panelAbierto.eeId === eeId && panelAbierto.modo === modo) {
    panel.classList.add('hidden');
    panel.innerHTML = '';
    panelAbierto = null;
    return;
  }
  document.querySelectorAll('[id^=ee-panel-]').forEach(p => { p.classList.add('hidden'); p.innerHTML = ''; });

  panelAbierto = { eeId, modo };
  panel.classList.remove('hidden');
  const ee = espaciosCache.find(e => e.id === eeId);

  if (modo === 'base') renderPanelBase(panel, ee);
  else renderPanelSemestral(panel, ee);
}

// ============================================================
// Datos de base
// ============================================================

let chkAmbientes, chkServicios, chkEquipoCocina, chkEquipoInformatico, chkZonaBase;

function ambientesASeleccion(ambientes) {
  return (ambientes || []).filter(a => a.tiene).map(a => ({ valor: a.ambiente }));
}
function serviciosASeleccion(servicios) {
  return (servicios || []).map(s => ({ valor: s.servicio }));
}
function zonasASeleccion(zonas) {
  return (zonas || []).map(z => ({ valor: z.zona }));
}
function equipoCocinaASeleccion(equipos) {
  return (equipos || []).filter(e => e.tiene).map(e => ({ valor: e.equipo }));
}
function equipoInformaticoASeleccion(equipos) {
  return (equipos || []).map(e => ({ valor: e.equipo, extra: e.cantidad }));
}

function renderPanelBase(panel, ee) {
  panel.innerHTML = `
    <div class="row g-3">
      <div class="col-md-4"><label class="form-label small">Nombre</label><input class="form-control" id="eeb-nombre" value="${ee.nombre ?? ''}"></div>
      <div class="col-md-4"><label class="form-label small">Dirección</label><input class="form-control" id="eeb-direccion" value="${ee.direccion ?? ''}"></div>
      <div class="col-md-4"><label class="form-label small">Geolocalización (link de Google Maps)</label><input class="form-control" id="eeb-geolocalizacion" value="${ee.geolocalizacion ?? ''}"></div>
      <div class="col-md-3"><label class="form-label small">Titularidad</label><input class="form-control" id="eeb-titularidad" value="${ee.titularidad ?? ''}"></div>
      <div class="col-md-3"><label class="form-label small">Nombre del titular</label><input class="form-control" id="eeb-nombre-titular" value="${ee.nombre_titular ?? ''}"></div>
      <div class="col-md-3"><label class="form-label small">Construido de</label><input class="form-control" id="eeb-construccion-material" value="${ee.construccion_material ?? ''}"></div>
      <div class="col-md-3"><label class="form-label small">Acceso principal por</label><input class="form-control" id="eeb-acceso-principal" value="${ee.acceso_principal ?? ''}"></div>
      <div class="col-md-2"><div class="form-check mt-4"><input class="form-check-input" type="checkbox" id="eeb-renabap" ${ee.renabap ? 'checked' : ''}><label class="form-check-label small">RENABAP</label></div></div>
      <div class="col-md-2"><div class="form-check mt-4"><input class="form-check-input" type="checkbox" id="eeb-rampa-acceso" ${ee.rampa_acceso ? 'checked' : ''}><label class="form-check-label small">Rampa de acceso</label></div></div>
    </div>

    <div class="subseccion-titulo">¿Con cuál de los siguientes ambientes cuenta el espacio?</div>
    <div id="chk-ambientes"></div>

    <div class="subseccion-titulo">El espacio cuenta con</div>
    <div id="chk-servicios"></div>

    <div class="subseccion-titulo">¿Con qué equipamiento de cocina cuenta?</div>
    <div id="chk-equipo-cocina"></div>

    <div class="subseccion-titulo">¿Con cuántas unidades de este equipamiento informático cuenta?</div>
    <div id="chk-equipo-informatico"></div>

    <div class="subseccion-titulo">Zona donde está ubicado el espacio</div>
    <div id="chk-zona"></div>

    <button class="btn btn-primary mt-3" id="btn-guardar-ee-base"><i class="bi bi-save"></i> Guardar datos del espacio</button>
    <span id="ee-base-guardado-msg" class="text-success small ms-2"></span>`;

  chkAmbientes = checklist('chk-ambientes', toItems(AMBIENTES_FIJOS), ambientesASeleccion(ee.ambientes));
  chkServicios = checklist('chk-servicios', toItems(SERVICIOS_FIJOS), serviciosASeleccion(ee.servicios));
  chkEquipoCocina = checklist('chk-equipo-cocina', toItems(EQUIPO_COCINA_FIJO), equipoCocinaASeleccion(ee.equipos_cocina));
  chkEquipoInformatico = checklist('chk-equipo-informatico', toItems(EQUIPO_INFORMATICO_FIJO), equipoInformaticoASeleccion(ee.equipos_informaticos), { extraField: { key: 'cantidad', label: 'Cantidad', type: 'number' } });
  chkZonaBase = checklist('chk-zona', toItems(ZONA_FIJA), zonasASeleccion(ee.zonas));

  document.getElementById('btn-guardar-ee-base').addEventListener('click', () => guardarEspacioBase(ee.id));
}

async function guardarEspacioBase(eeId) {
  const payload = {
    nombre: document.getElementById('eeb-nombre').value,
    direccion: document.getElementById('eeb-direccion').value || null,
    geolocalizacion: document.getElementById('eeb-geolocalizacion').value || null,
    titularidad: document.getElementById('eeb-titularidad').value || null,
    nombre_titular: document.getElementById('eeb-nombre-titular').value || null,
    construccion_material: document.getElementById('eeb-construccion-material').value || null,
    acceso_principal: document.getElementById('eeb-acceso-principal').value || null,
    renabap: document.getElementById('eeb-renabap').checked,
    rampa_acceso: document.getElementById('eeb-rampa-acceso').checked,
    activo: true,
    ambientes: chkAmbientes.getValues().map(s => ({ ambiente: s.valor, tiene: true })),
    servicios: chkServicios.getValues().map(s => ({ servicio: s.valor, tiene: true })),
    equipos_cocina: chkEquipoCocina.getValues().map(s => ({ equipo: s.valor, tiene: true })),
    equipos_informaticos: chkEquipoInformatico.getValues().map(s => ({ equipo: s.valor, cantidad: s.extra ? parseInt(s.extra) : null })),
    zonas: chkZonaBase.getValues().map(s => ({ zona: s.valor })),
  };
  try {
    await api.put(`/relevamientos/${relevamientoActual.id}/espacios-educativos/${eeId}`, payload);
    await refrescarEspacios(relevamientoActual.id);
    const msg = document.getElementById('ee-base-guardado-msg');
    if (msg) { msg.textContent = 'Guardado ✓'; setTimeout(() => msg.textContent = '', 2000); }
  } catch (err) {
    alert(err.message);
  }
}

// ============================================================
// Datos semestrales
// ============================================================

let chkAcciones = {}, chkItinEspacios, chkItinActividades, chkBtuMotivos;
let chkApoyoPrimContenidos, chkApoyoSecContenidos, chkDigitalTalleres, chkNecesidades;
let preocupacionesRanking = {};

function renderPanelSemestral(panel, ee) {
  const accionesPorEjeAgrupadas = {};
  ACCIONES_POR_EJE.forEach(([eje, accion]) => { (accionesPorEjeAgrupadas[eje] ||= []).push(accion); });
  const accionesActuales = ee.acciones || [];

  panel.innerHTML = `
    <div class="subseccion-titulo">¿Cuántas personas asisten al espacio entre las siguientes edades? ${ayudaIcon('Contá todas las personas que asisten al espacio educativo, separadas por edad. Una misma persona se cuenta en un solo rango.')}</div>
    <div class="row g-2">
      <div class="col"><label class="form-label small">0-6</label><input type="number" class="form-control" id="ees-asistentes-0-6" value="${ee.asistentes_0_6 ?? ''}"></div>
      <div class="col"><label class="form-label small">7-14</label><input type="number" class="form-control" id="ees-asistentes-7-14" value="${ee.asistentes_7_14 ?? ''}"></div>
      <div class="col"><label class="form-label small">15-24</label><input type="number" class="form-control" id="ees-asistentes-15-24" value="${ee.asistentes_15_24 ?? ''}"></div>
      <div class="col"><label class="form-label small">25-35</label><input type="number" class="form-control" id="ees-asistentes-25-35" value="${ee.asistentes_25_35 ?? ''}"></div>
      <div class="col"><label class="form-label small">35-50</label><input type="number" class="form-control" id="ees-asistentes-35-50" value="${ee.asistentes_35_50 ?? ''}"></div>
      <div class="col"><label class="form-label small">+50</label><input type="number" class="form-control" id="ees-asistentes-mas-50" value="${ee.asistentes_mas_50 ?? ''}"></div>
    </div>

    <div class="subseccion-titulo">Acciones que se realizan, por eje ${ayudaIcon('Marcá únicamente las acciones que efectivamente se realizan en este espacio educativo durante el semestre, agrupadas por el eje al que pertenecen.')}</div>
    <div id="acciones-por-eje">
      ${Object.entries(accionesPorEjeAgrupadas).map(([eje, acciones]) => `
        <div class="mb-2">
          <div class="fw-semibold small" style="color:var(--sec-navy)">${eje}</div>
          <div id="chk-acciones-${eje.replace(/\W/g, '')}"></div>
        </div>`).join('')}
    </div>

    <div class="subseccion-titulo">Grupo motor / Adolescentes referentes</div>
    <div class="row g-2">
      <div class="col-md-2"><label class="form-label small">Grupo motor (cant.)</label><input type="number" class="form-control" id="ees-grupo-motor-cantidad" value="${ee.grupo_motor_cantidad ?? ''}"></div>
      <div class="col-md-2"><label class="form-label small">Frecuencia reunión</label><input class="form-control" id="ees-grupo-motor-frecuencia" value="${ee.grupo_motor_frecuencia ?? ''}"></div>
      <div class="col-md-2"><label class="form-label small">Adolescentes referentes (cant.)</label><input type="number" class="form-control" id="ees-adolescentes-referentes" value="${ee.adolescentes_referentes ?? ''}"></div>
      <div class="col-md-2"><label class="form-label small">Frecuencia de reunión</label><input class="form-control" id="ees-adolescentes-frecuencia" value="${ee.adolescentes_frecuencia ?? ''}"></div>
    </div>
    <div class="small text-muted mt-1">¿Quiénes conforman el grupo motor? Cargá rol y cantidad (hasta 4)</div>
    <div id="slots-grupo-motor"></div>

    <div class="subseccion-titulo">Itinerancia</div>
    <div class="row g-2">
      <div class="col-md-3"><div class="form-check mt-4"><input class="form-check-input" type="checkbox" id="ees-itinerancia-realizo" ${ee.itinerancia_realizo ? 'checked' : ''}><label class="form-check-label small">Realizó itinerancia</label></div></div>
      <div class="col-md-3"><label class="form-label small">Frecuencia</label><input class="form-control" id="ees-itinerancia-frecuencia" value="${ee.itinerancia_frecuencia ?? ''}"></div>
    </div>
    <div class="row mt-2">
      <div class="col-md-4"><div class="small fw-semibold">¿En qué tipo de espacio?</div><div id="chk-itin-espacios"></div></div>
      <div class="col-md-4"><div class="small fw-semibold">Actividades predominantes</div><div id="chk-itin-actividades"></div></div>
      <div class="col-md-4"><div class="small fw-semibold">Roles a cargo (hasta 4)</div><div id="slots-itin-roles"></div></div>
    </div>

    <div class="subseccion-titulo">Alfabetización digital y nuevas tecnologías</div>
    <div class="row g-2">
      <div class="col-md-3"><div class="form-check mt-4"><input class="form-check-input" type="checkbox" id="ees-internet-acceso" ${ee.internet_acceso ? 'checked' : ''}><label class="form-check-label small">Tiene acceso a internet</label></div></div>
      <div class="col-md-4"><label class="form-label small">Si no tiene, ¿por qué?</label><input class="form-control" id="ees-internet-falta-motivo" value="${ee.internet_falta_motivo ?? ''}"></div>
      <div class="col-md-4"><div class="form-check mt-4"><input class="form-check-input" type="checkbox" id="ees-jornadas-formacion-digital" ${ee.jornadas_formacion_digital ? 'checked' : ''}><label class="form-check-label small">Se desarrollaron jornadas de formación digital</label></div></div>
    </div>
    <div class="small fw-semibold mt-2">Talleres realizados</div>
    <div id="chk-digital-talleres"></div>

    <div class="subseccion-titulo">Articulación con instituciones de Nivel Superior</div>
    <div class="row g-2">
      <div class="col-md-3"><div class="form-check mt-4"><input class="form-check-input" type="checkbox" id="ees-articula-nivel-superior" ${ee.articula_nivel_superior ? 'checked' : ''}><label class="form-check-label small">Articula</label></div></div>
      <div class="col-md-3"><label class="form-label small">¿Con cuántas instituciones?</label><input type="number" class="form-control" id="ees-nivel-superior-cantidad" value="${ee.nivel_superior_cantidad ?? ''}"></div>
    </div>
    <div class="small text-muted mt-1">Detalle por institución (hasta 5)</div>
    <div id="slots-niveles-superiores"></div>

    <div class="subseccion-titulo">Becas Familiares (responder solo si el componente está en este espacio)</div>
    <div class="row g-2">
      <div class="col"><label class="form-label small">Apoyo escolar</label><input type="number" class="form-control" id="ees-bf-apoyo-escolar" value="${ee.bf_apoyo_escolar ?? ''}"></div>
      <div class="col"><label class="form-label small">Nivel inicial</label><input type="number" class="form-control" id="ees-bf-nivel-inicial" value="${ee.bf_nivel_inicial ?? ''}"></div>
      <div class="col"><label class="form-label small">Primaria</label><input type="number" class="form-control" id="ees-bf-primaria" value="${ee.bf_primaria ?? ''}"></div>
      <div class="col"><label class="form-label small">Secundaria</label><input type="number" class="form-control" id="ees-bf-secundaria" value="${ee.bf_secundaria ?? ''}"></div>
      <div class="col"><label class="form-label small">Con asignaciones</label><input type="number" class="form-control" id="ees-bf-asignaciones" value="${ee.bf_asignaciones ?? ''}"></div>
      <div class="col"><label class="form-label small">Con discapacidad</label><input type="number" class="form-control" id="ees-bf-discapacidad" value="${ee.bf_discapacidad ?? ''}"></div>
      <div class="col"><label class="form-label small">Con CUD tramitado</label><input type="number" class="form-control" id="ees-bf-cud" value="${ee.bf_cud ?? ''}"></div>
    </div>

    <div class="subseccion-titulo">Becas Terciarias/Universitarias (BTU)</div>
    <div class="row g-2">
      <div class="col-md-2"><label class="form-label small">Regulares (a junio)</label><input type="number" class="form-control" id="ees-btu-regulares" value="${ee.btu_regulares ?? ''}"></div>
      <div class="col-md-2"><label class="form-label small">Egresados</label><input type="number" class="form-control" id="ees-btu-egresados" value="${ee.btu_egresados ?? ''}"></div>
      <div class="col-md-2"><label class="form-label small">Dejaron la cursada</label><input type="number" class="form-control" id="ees-btu-abandonaron" value="${ee.btu_abandonaron ?? ''}"></div>
    </div>
    <div class="small text-muted mt-1">Motivos de abandono más frecuentes (hasta 3)</div>
    <div id="chk-btu-motivos"></div>

    <div class="subseccion-titulo">Apoyo escolar — Nivel Primario</div>
    <div class="row g-2">
      <div class="col-md-2"><label class="form-label small">Niños/as</label><input type="number" class="form-control" id="ees-apoyo-primario-ninos" value="${ee.apoyo_primario_ninos ?? ''}"></div>
      <div class="col-md-3"><label class="form-label small">Frecuencia</label><input class="form-control" id="ees-apoyo-primario-frecuencia" value="${ee.apoyo_primario_frecuencia ?? ''}"></div>
      <div class="col-md-3"><label class="form-label small">Contenido más trabajado</label><input class="form-control" id="ees-apoyo-primario-contenido-principal" value="${ee.apoyo_primario_contenido_principal ?? ''}"></div>
    </div>
    <div class="small text-muted mt-1">Contenidos que se dictan</div>
    <div id="chk-apoyo-prim-contenidos"></div>

    <div class="subseccion-titulo">Apoyo escolar — Nivel Secundario</div>
    <div class="row g-2">
      <div class="col-md-2"><label class="form-label small">Adolescentes</label><input type="number" class="form-control" id="ees-apoyo-secundario-adolescentes" value="${ee.apoyo_secundario_adolescentes ?? ''}"></div>
      <div class="col-md-3"><label class="form-label small">Frecuencia</label><input class="form-control" id="ees-apoyo-secundario-frecuencia" value="${ee.apoyo_secundario_frecuencia ?? ''}"></div>
      <div class="col-md-3"><label class="form-label small">Contenido más trabajado</label><input class="form-control" id="ees-apoyo-secundario-contenido-principal" value="${ee.apoyo_secundario_contenido_principal ?? ''}"></div>
    </div>
    <div class="small text-muted mt-1">Contenidos que se dictan</div>
    <div id="chk-apoyo-sec-contenidos"></div>

    <div class="subseccion-titulo">Propuesta de Alfabetización</div>
    <div class="row g-2">
      <div class="col"><label class="form-label small">Total</label><input type="number" class="form-control" id="ees-alfa-total" value="${ee.alfa_total ?? ''}"></div>
      <div class="col"><label class="form-label small">6-9</label><input type="number" class="form-control" id="ees-alfa-6-9" value="${ee.alfa_6_9 ?? ''}"></div>
      <div class="col"><label class="form-label small">10-14</label><input type="number" class="form-control" id="ees-alfa-10-14" value="${ee.alfa_10_14 ?? ''}"></div>
      <div class="col"><label class="form-label small">15-24</label><input type="number" class="form-control" id="ees-alfa-15-24" value="${ee.alfa_15_24 ?? ''}"></div>
      <div class="col"><label class="form-label small">25+</label><input type="number" class="form-control" id="ees-alfa-25-mas" value="${ee.alfa_25_mas ?? ''}"></div>
      <div class="col"><label class="form-label small">Alfabetizadores</label><input type="number" class="form-control" id="ees-alfa-alfabetizadores" value="${ee.alfa_alfabetizadores ?? ''}"></div>
      <div class="col"><label class="form-label small">Frecuencia</label><input class="form-control" id="ees-alfa-frecuencia" value="${ee.alfa_frecuencia ?? ''}"></div>
    </div>

    <div class="subseccion-titulo">Propuesta DALE</div>
    <div class="row g-2">
      <div class="col"><label class="form-label small">Total</label><input type="number" class="form-control" id="ees-dale-total" value="${ee.dale_total ?? ''}"></div>
      <div class="col"><label class="form-label small">6-9</label><input type="number" class="form-control" id="ees-dale-6-9" value="${ee.dale_6_9 ?? ''}"></div>
      <div class="col"><label class="form-label small">10-14</label><input type="number" class="form-control" id="ees-dale-10-14" value="${ee.dale_10_14 ?? ''}"></div>
      <div class="col"><label class="form-label small">15-24</label><input type="number" class="form-control" id="ees-dale-15-24" value="${ee.dale_15_24 ?? ''}"></div>
      <div class="col"><label class="form-label small">25+</label><input type="number" class="form-control" id="ees-dale-25-mas" value="${ee.dale_25_mas ?? ''}"></div>
      <div class="col"><label class="form-label small">Educadores</label><input type="number" class="form-control" id="ees-dale-educadores" value="${ee.dale_educadores ?? ''}"></div>
      <div class="col"><label class="form-label small">Frecuencia (días/semana)</label><input type="number" class="form-control" id="ees-dale-frecuencia-dias" value="${ee.dale_frecuencia_dias ?? ''}"></div>
    </div>

    <div class="subseccion-titulo">Necesidades de infraestructura prioritarias ${ayudaIcon('Elegí hasta 3 necesidades, las que consideres más urgentes o importantes para este espacio en este momento.')}</div>
    <div id="chk-necesidades"></div>

    <div class="subseccion-titulo">Preocupaciones sobre adolescentes/jóvenes ${ayudaIcon('Hacé click en las situaciones en el orden en que más te preocupan: la primera que toques va a quedar como la #1 (la más preocupante), la siguiente como #2, y así. Podés tocar una ya elegida para sacarla del orden.')}</div>
    <div id="ranking-preocupaciones"></div>

    <button class="btn btn-primary mt-3" id="btn-guardar-ee-semestral"><i class="bi bi-save"></i> Guardar datos semestrales</button>
    <span id="ee-semestral-guardado-msg" class="text-success small ms-2"></span>`;

  Object.keys(accionesPorEjeAgrupadas).forEach(eje => {
    const items = toItems(accionesPorEjeAgrupadas[eje]);
    const seleccion = accionesActuales.filter(a => a.eje === eje && a.tiene).map(a => ({ valor: a.accion }));
    chkAcciones[eje] = checklist(`chk-acciones-${eje.replace(/\W/g, '')}`, items, seleccion);
  });

  chkItinEspacios = checklist('chk-itin-espacios', toItems(ITINERANCIA_ESPACIOS_FIJO), (ee.itinerancia_espacios || []).map(i => ({ valor: i.espacio, otro: i.espacio_otro })));
  chkItinActividades = checklist('chk-itin-actividades', toItems(ITINERANCIA_ACTIVIDADES_FIJO), (ee.itinerancia_actividades || []).map(i => ({ valor: i.actividad })), { maxSelected: 3 });
  chkBtuMotivos = checklist('chk-btu-motivos', toItems(BTU_ABANDONO_FIJO), (ee.btu_abandono_motivos || []).map(m => ({ valor: BTU_ABANDONO_FIJO.includes(m.motivo) ? m.motivo : 'Otro:', otro: BTU_ABANDONO_FIJO.includes(m.motivo) ? null : m.motivo })), { maxSelected: 3 });
  chkApoyoPrimContenidos = checklist('chk-apoyo-prim-contenidos', toItems(CONTENIDOS_ESCOLARES_FIJO), (ee.apoyo_primario_contenidos || []).map(c => ({ valor: CONTENIDOS_ESCOLARES_FIJO.includes(c.contenido) ? c.contenido : 'Otro:', otro: CONTENIDOS_ESCOLARES_FIJO.includes(c.contenido) ? null : c.contenido })));
  chkApoyoSecContenidos = checklist('chk-apoyo-sec-contenidos', toItems(CONTENIDOS_ESCOLARES_FIJO), (ee.apoyo_secundario_contenidos || []).map(c => ({ valor: CONTENIDOS_ESCOLARES_FIJO.includes(c.contenido) ? c.contenido : 'Otro:', otro: CONTENIDOS_ESCOLARES_FIJO.includes(c.contenido) ? null : c.contenido })));
  chkDigitalTalleres = checklist('chk-digital-talleres', toItems(DIGITAL_TALLERES_FIJO), (ee.digital_talleres || []).map(t => ({ valor: t.taller })));
  chkNecesidades = checklist('chk-necesidades', toItemsCatalogo(catNecesidadInfra), (ee.necesidades_infra || []).map(n => ({ valor: n.necesidad })), { maxSelected: 3 });

  renderSlotsFijos('slots-grupo-motor', 4, ee.grupo_motor_roles || [], ['rol', 'cantidad']);
  renderSlotsFijos('slots-itin-roles', 4, ee.itinerancia_roles || [], ['rol', 'cantidad']);
  renderSlotsFijos('slots-niveles-superiores', 5, ee.niveles_superiores || [], ['nombre_institucion', 'tipo_acciones']);

  renderRankingPreocupaciones(ee.preocupaciones_joven || []);

  document.getElementById('btn-guardar-ee-semestral').addEventListener('click', () => guardarEspacioSemestral(ee.id));
}

function renderSlotsFijos(containerId, cantidad, datosExistentes, campos) {
  const container = document.getElementById(containerId);
  container.innerHTML = '';
  for (let i = 0; i < cantidad; i++) {
    const actual = datosExistentes[i] || {};
    const row = document.createElement('div');
    row.className = 'row g-2 mb-1 fila-slot-fijo';
    row.innerHTML = campos.map(campo => {
      const tipo = campo === 'cantidad' ? 'number' : 'text';
      const placeholder = { rol: 'Rol', cantidad: 'Cantidad', nombre_institucion: `Institución ${i + 1}`, tipo_acciones: 'Tipo de acciones' }[campo];
      return `<div class="col"><input type="${tipo}" class="form-control form-control-sm" data-campo="${campo}" placeholder="${placeholder}" value="${actual[campo] ?? ''}"></div>`;
    }).join('');
    container.appendChild(row);
  }
}

function leerSlotsFijos(containerId, campoClave) {
  return Array.from(document.querySelectorAll(`#${containerId} .fila-slot-fijo`))
    .map(row => {
      const obj = {};
      row.querySelectorAll('[data-campo]').forEach(input => {
        obj[input.dataset.campo] = input.type === 'number' ? (input.value ? parseInt(input.value) : null) : (input.value || null);
      });
      return obj;
    })
    .filter(obj => obj[campoClave]);
}

let ordenPreocupaciones = [];

function renderRankingPreocupaciones(seleccionadas) {
  ordenPreocupaciones = seleccionadas
    .slice()
    .sort((a, b) => a.ranking - b.ranking)
    .map(p => p.preocupacion);
  pintarRankingPreocupaciones();
}

function pintarRankingPreocupaciones() {
  const container = document.getElementById('ranking-preocupaciones');
  container.innerHTML = `
    <p class="small text-muted mb-2">Tocá las situaciones en orden, de la más a la menos preocupante. La primera que toques queda como #1.</p>
    ${catPreocupacionJoven.map(c => {
      const posicion = ordenPreocupaciones.indexOf(c.valor);
      const rankeada = posicion !== -1;
      return `
        <div class="d-flex align-items-center mb-1 fila-ranking-click ${rankeada ? 'border border-primary' : 'border'}"
             style="border-radius:.5rem;padding:.4rem .7rem;cursor:pointer;background:${rankeada ? 'var(--sec-blue-light)' : '#fff'}"
             data-valor="${c.valor}" onclick="toggleRankingPreocupacion('${c.valor.replace(/'/g, "\\'")}')">
          <span class="badge ${rankeada ? 'bg-primary' : 'bg-secondary'} me-2" style="width:28px">${rankeada ? posicion + 1 : '–'}</span>
          <span class="small">${c.valor}</span>
        </div>`;
    }).join('')}`;
}

function toggleRankingPreocupacion(valor) {
  const idx = ordenPreocupaciones.indexOf(valor);
  if (idx !== -1) {
    ordenPreocupaciones.splice(idx, 1);
  } else {
    ordenPreocupaciones.push(valor);
  }
  pintarRankingPreocupaciones();
}

function leerRankingPreocupaciones() {
  return ordenPreocupaciones.map((valor, i) => ({ preocupacion: valor, ranking: i + 1 }));
}

const CAMPOS_SEMESTRALES_NUM = [
  'asistentes_0_6', 'asistentes_7_14', 'asistentes_15_24', 'asistentes_25_35', 'asistentes_35_50', 'asistentes_mas_50',
  'grupo_motor_cantidad', 'adolescentes_referentes', 'nivel_superior_cantidad',
  'bf_apoyo_escolar', 'bf_nivel_inicial', 'bf_primaria', 'bf_secundaria', 'bf_asignaciones', 'bf_discapacidad', 'bf_cud',
  'btu_regulares', 'btu_egresados', 'btu_abandonaron',
  'apoyo_primario_ninos', 'apoyo_secundario_adolescentes',
  'alfa_total', 'alfa_6_9', 'alfa_10_14', 'alfa_15_24', 'alfa_25_mas', 'alfa_alfabetizadores',
  'dale_total', 'dale_6_9', 'dale_10_14', 'dale_15_24', 'dale_25_mas', 'dale_educadores', 'dale_frecuencia_dias',
];
const CAMPOS_SEMESTRALES_TEXTO = [
  'grupo_motor_frecuencia', 'adolescentes_frecuencia', 'itinerancia_frecuencia', 'internet_falta_motivo',
  'apoyo_primario_frecuencia', 'apoyo_primario_contenido_principal', 'apoyo_secundario_frecuencia',
  'apoyo_secundario_contenido_principal', 'alfa_frecuencia',
];
const CAMPOS_SEMESTRALES_BOOL = ['itinerancia_realizo', 'internet_acceso', 'jornadas_formacion_digital', 'articula_nivel_superior'];

function idDeCampo(campo) { return `ees-${campo.replace(/_/g, '-')}`; }

async function guardarEspacioSemestral(eeId) {
  const acciones = [];
  Object.entries(chkAcciones).forEach(([eje, chk]) => {
    chk.getValues().forEach(s => acciones.push({ eje, accion: s.valor, tiene: true }));
  });

  const payload = {
    acciones,
    grupo_motor_roles: leerSlotsFijos('slots-grupo-motor', 'rol'),
    itinerancia_espacios: chkItinEspacios.getValues().map(s => ({ espacio: s.valor, espacio_otro: s.otro })),
    itinerancia_actividades: chkItinActividades.getValues().map(s => ({ actividad: s.valor })),
    itinerancia_roles: leerSlotsFijos('slots-itin-roles', 'rol'),
    digital_talleres: chkDigitalTalleres.getValues().map(s => ({ taller: s.valor })),
    niveles_superiores: leerSlotsFijos('slots-niveles-superiores', 'nombre_institucion'),
    btu_abandono_motivos: chkBtuMotivos.getValues().map(s => ({ motivo: valorOtro(s) })),
    apoyo_primario_contenidos: chkApoyoPrimContenidos.getValues().map(s => ({ contenido: valorOtro(s) })),
    apoyo_secundario_contenidos: chkApoyoSecContenidos.getValues().map(s => ({ contenido: valorOtro(s) })),
    necesidades_infra: chkNecesidades.getValues().map((s, i) => ({ necesidad: s.valor, orden: i + 1 })),
    preocupaciones_joven: leerRankingPreocupaciones(),
  };

  CAMPOS_SEMESTRALES_NUM.forEach(c => {
    const el = document.getElementById(idDeCampo(c));
    payload[c] = el && el.value !== '' ? parseInt(el.value) : null;
  });
  CAMPOS_SEMESTRALES_TEXTO.forEach(c => {
    const el = document.getElementById(idDeCampo(c));
    payload[c] = el ? (el.value || null) : null;
  });
  CAMPOS_SEMESTRALES_BOOL.forEach(c => {
    const el = document.getElementById(idDeCampo(c));
    payload[c] = el ? el.checked : false;
  });

  try {
    await api.put(`/relevamientos/${relevamientoActual.id}/espacios-educativos/${eeId}/datos-semestrales`, payload);
    await refrescarEspacios(relevamientoActual.id);
    const msg = document.getElementById('ee-semestral-guardado-msg');
    if (msg) { msg.textContent = 'Guardado ✓'; setTimeout(() => msg.textContent = '', 2000); }
  } catch (err) {
    alert(err.message);
  }
}
