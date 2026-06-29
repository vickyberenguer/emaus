let espaciosCache = [];
let dynEEAmbientes, dynEEServicios, dynEEEquiposCocina, dynEEEquiposInformaticos;
let dynEENecesidades, dynEEPreocupaciones, dynEEAcciones, dynEEZonas;
let dynEENivelesSuperiores, dynEEBtuMotivos, dynEEApoyoPrimContenidos, dynEEApoyoSecContenidos;
let dynEEItinEspacios, dynEEItinActividades, dynEEItinRoles, dynEEDigitalTalleres, dynEEGrupoMotorRoles;

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
    </div>`).join('') || '<p class="text-muted small">Todavía no hay espacios educativos para este Emaús.</p>';
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

let panelAbierto = null; // {eeId, modo}

async function toggleEspacio(eeId, modo) {
  const panel = document.getElementById(`ee-panel-${eeId}`);
  if (panelAbierto && panelAbierto.eeId === eeId && panelAbierto.modo === modo) {
    panel.classList.add('hidden');
    panel.innerHTML = '';
    panelAbierto = null;
    return;
  }
  // cerrar cualquier otro panel abierto
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

function renderPanelBase(panel, ee) {
  panel.innerHTML = `
    <div class="row g-3">
      <div class="col-md-4"><label class="form-label small">Nombre</label><input class="form-control" id="eeb-nombre" value="${ee.nombre ?? ''}"></div>
      <div class="col-md-4"><label class="form-label small">Dirección</label><input class="form-control" id="eeb-direccion" value="${ee.direccion ?? ''}"></div>
      <div class="col-md-4"><label class="form-label small">Geolocalización</label><input class="form-control" id="eeb-geolocalizacion" value="${ee.geolocalizacion ?? ''}"></div>
      <div class="col-md-3"><label class="form-label small">Titularidad</label><input class="form-control" id="eeb-titularidad" value="${ee.titularidad ?? ''}"></div>
      <div class="col-md-3"><label class="form-label small">Nombre del titular</label><input class="form-control" id="eeb-nombre-titular" value="${ee.nombre_titular ?? ''}"></div>
      <div class="col-md-3"><label class="form-label small">Material de construcción</label><input class="form-control" id="eeb-construccion-material" value="${ee.construccion_material ?? ''}"></div>
      <div class="col-md-3"><label class="form-label small">Acceso principal</label><input class="form-control" id="eeb-acceso-principal" value="${ee.acceso_principal ?? ''}"></div>
      <div class="col-md-2"><div class="form-check mt-4"><input class="form-check-input" type="checkbox" id="eeb-renabap" ${ee.renabap ? 'checked' : ''}><label class="form-check-label small">RENABAP</label></div></div>
      <div class="col-md-2"><div class="form-check mt-4"><input class="form-check-input" type="checkbox" id="eeb-rampa-acceso" ${ee.rampa_acceso ? 'checked' : ''}><label class="form-check-label small">Rampa de acceso</label></div></div>
    </div>

    <div class="subseccion-titulo">Ambientes disponibles <button type="button" class="btn btn-sm btn-outline-primary" id="btn-add-ambiente"><i class="bi bi-plus"></i></button></div>
    <div id="dyn-ambientes"></div>

    <div class="subseccion-titulo">Servicios básicos <button type="button" class="btn btn-sm btn-outline-primary" id="btn-add-servicio"><i class="bi bi-plus"></i></button></div>
    <div id="dyn-servicios"></div>

    <div class="subseccion-titulo">Equipamiento de cocina <button type="button" class="btn btn-sm btn-outline-primary" id="btn-add-equipo-cocina"><i class="bi bi-plus"></i></button></div>
    <div id="dyn-equipos-cocina"></div>

    <div class="subseccion-titulo">Equipamiento informático <button type="button" class="btn btn-sm btn-outline-primary" id="btn-add-equipo-info"><i class="bi bi-plus"></i></button></div>
    <div id="dyn-equipos-informaticos"></div>

    <button class="btn btn-primary mt-3" id="btn-guardar-ee-base"><i class="bi bi-save"></i> Guardar datos de base</button>
    <span id="ee-base-guardado-msg" class="text-success small ms-2"></span>`;

  dynEEAmbientes = dynList('dyn-ambientes', [
    { key: 'ambiente', label: 'Ambiente' }, { key: 'tiene', label: 'Tiene', type: 'checkbox' }, { key: 'cantidad', label: 'Cantidad', type: 'number' },
  ], ee.ambientes || []);
  dynEEServicios = dynList('dyn-servicios', [
    { key: 'servicio', label: 'Servicio' }, { key: 'valor', label: 'Valor' },
  ], ee.servicios || []);
  dynEEEquiposCocina = dynList('dyn-equipos-cocina', [
    { key: 'equipo', label: 'Equipo' }, { key: 'tiene', label: 'Tiene', type: 'checkbox' },
  ], ee.equipos_cocina || []);
  dynEEEquiposInformaticos = dynList('dyn-equipos-informaticos', [
    { key: 'equipo', label: 'Equipo' }, { key: 'cantidad', label: 'Cantidad', type: 'number' },
  ], ee.equipos_informaticos || []);

  document.getElementById('btn-add-ambiente').addEventListener('click', () => dynEEAmbientes.addRow());
  document.getElementById('btn-add-servicio').addEventListener('click', () => dynEEServicios.addRow());
  document.getElementById('btn-add-equipo-cocina').addEventListener('click', () => dynEEEquiposCocina.addRow());
  document.getElementById('btn-add-equipo-info').addEventListener('click', () => dynEEEquiposInformaticos.addRow());
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
    ambientes: dynEEAmbientes.getValues(),
    servicios: dynEEServicios.getValues(),
    equipos_cocina: dynEEEquiposCocina.getValues(),
    equipos_informaticos: dynEEEquiposInformaticos.getValues(),
  };
  try {
    await api.put(`/relevamientos/${relevamientoActual.id}/espacios-educativos/${eeId}`, payload);
    await refrescarEspacios(relevamientoActual.id);
    document.getElementById(`ee-panel-${eeId}`)?.classList.remove('hidden');
    const msg = document.getElementById('ee-base-guardado-msg');
    if (msg) { msg.textContent = 'Guardado ✓'; setTimeout(() => msg.textContent = '', 2000); }
  } catch (err) {
    alert(err.message);
  }
}

// ============================================================
// Datos semestrales
// ============================================================

function renderPanelSemestral(panel, ee) {
  panel.innerHTML = `
    <div class="subseccion-titulo">Asistentes por rango etario</div>
    <div class="row g-2">
      <div class="col"><label class="form-label small">0-6</label><input type="number" class="form-control" id="ees-asistentes-0-6" value="${ee.asistentes_0_6 ?? ''}"></div>
      <div class="col"><label class="form-label small">7-14</label><input type="number" class="form-control" id="ees-asistentes-7-14" value="${ee.asistentes_7_14 ?? ''}"></div>
      <div class="col"><label class="form-label small">15-24</label><input type="number" class="form-control" id="ees-asistentes-15-24" value="${ee.asistentes_15_24 ?? ''}"></div>
      <div class="col"><label class="form-label small">25-35</label><input type="number" class="form-control" id="ees-asistentes-25-35" value="${ee.asistentes_25_35 ?? ''}"></div>
      <div class="col"><label class="form-label small">35-50</label><input type="number" class="form-control" id="ees-asistentes-35-50" value="${ee.asistentes_35_50 ?? ''}"></div>
      <div class="col"><label class="form-label small">+50</label><input type="number" class="form-control" id="ees-asistentes-mas-50" value="${ee.asistentes_mas_50 ?? ''}"></div>
    </div>

    <div class="subseccion-titulo">Acciones por eje <button type="button" class="btn btn-sm btn-outline-primary" id="btn-add-accion"><i class="bi bi-plus"></i></button></div>
    <div id="dyn-acciones-ee"></div>

    <div class="subseccion-titulo">Grupo motor / Adolescentes referentes</div>
    <div class="row g-2">
      <div class="col-md-2"><label class="form-label small">Grupo motor (cant.)</label><input type="number" class="form-control" id="ees-grupo-motor-cantidad" value="${ee.grupo_motor_cantidad ?? ''}"></div>
      <div class="col-md-2"><label class="form-label small">Frecuencia reunión</label><input class="form-control" id="ees-grupo-motor-frecuencia" value="${ee.grupo_motor_frecuencia ?? ''}"></div>
      <div class="col-md-2"><label class="form-label small">Adolescentes referentes</label><input type="number" class="form-control" id="ees-adolescentes-referentes" value="${ee.adolescentes_referentes ?? ''}"></div>
      <div class="col-md-2"><label class="form-label small">Frecuencia (adolesc.)</label><input class="form-control" id="ees-adolescentes-frecuencia" value="${ee.adolescentes_frecuencia ?? ''}"></div>
    </div>
    <div class="subseccion-titulo">Roles del grupo motor <button type="button" class="btn btn-sm btn-outline-primary" id="btn-add-rol-motor"><i class="bi bi-plus"></i></button></div>
    <div id="dyn-grupo-motor-roles"></div>

    <div class="subseccion-titulo">Itinerancia</div>
    <div class="row g-2">
      <div class="col-md-2"><div class="form-check mt-4"><input class="form-check-input" type="checkbox" id="ees-itinerancia-realizo" ${ee.itinerancia_realizo ? 'checked' : ''}><label class="form-check-label small">Realizó itinerancia</label></div></div>
      <div class="col-md-3"><label class="form-label small">Frecuencia</label><input class="form-control" id="ees-itinerancia-frecuencia" value="${ee.itinerancia_frecuencia ?? ''}"></div>
    </div>
    <div class="row mt-2">
      <div class="col-md-4">Espacios <button type="button" class="btn btn-sm btn-outline-primary" id="btn-add-itin-espacio"><i class="bi bi-plus"></i></button><div id="dyn-itin-espacios"></div></div>
      <div class="col-md-4">Actividades <button type="button" class="btn btn-sm btn-outline-primary" id="btn-add-itin-actividad"><i class="bi bi-plus"></i></button><div id="dyn-itin-actividades"></div></div>
      <div class="col-md-4">Roles a cargo <button type="button" class="btn btn-sm btn-outline-primary" id="btn-add-itin-rol"><i class="bi bi-plus"></i></button><div id="dyn-itin-roles"></div></div>
    </div>

    <div class="subseccion-titulo">Alfabetización digital</div>
    <div class="row g-2">
      <div class="col-md-3"><div class="form-check mt-4"><input class="form-check-input" type="checkbox" id="ees-internet-acceso" ${ee.internet_acceso ? 'checked' : ''}><label class="form-check-label small">Acceso a internet</label></div></div>
      <div class="col-md-4"><label class="form-label small">Motivo si falta</label><input class="form-control" id="ees-internet-falta-motivo" value="${ee.internet_falta_motivo ?? ''}"></div>
      <div class="col-md-3"><div class="form-check mt-4"><input class="form-check-input" type="checkbox" id="ees-jornadas-formacion-digital" ${ee.jornadas_formacion_digital ? 'checked' : ''}><label class="form-check-label small">Jornadas de formación digital</label></div></div>
    </div>
    <div>Talleres digitales realizados <button type="button" class="btn btn-sm btn-outline-primary" id="btn-add-digital-taller"><i class="bi bi-plus"></i></button><div id="dyn-digital-talleres"></div></div>

    <div class="subseccion-titulo">Articulación con nivel superior</div>
    <div class="row g-2">
      <div class="col-md-3"><div class="form-check mt-4"><input class="form-check-input" type="checkbox" id="ees-articula-nivel-superior" ${ee.articula_nivel_superior ? 'checked' : ''}><label class="form-check-label small">Articula</label></div></div>
      <div class="col-md-3"><label class="form-label small">Cantidad</label><input type="number" class="form-control" id="ees-nivel-superior-cantidad" value="${ee.nivel_superior_cantidad ?? ''}"></div>
    </div>
    <div>Instituciones <button type="button" class="btn btn-sm btn-outline-primary" id="btn-add-nivel-superior"><i class="bi bi-plus"></i></button><div id="dyn-niveles-superiores"></div></div>

    <div class="subseccion-titulo">Becas Familiares</div>
    <div class="row g-2">
      <div class="col"><label class="form-label small">Apoyo escolar</label><input type="number" class="form-control" id="ees-bf-apoyo-escolar" value="${ee.bf_apoyo_escolar ?? ''}"></div>
      <div class="col"><label class="form-label small">Nivel inicial</label><input type="number" class="form-control" id="ees-bf-nivel-inicial" value="${ee.bf_nivel_inicial ?? ''}"></div>
      <div class="col"><label class="form-label small">Primaria</label><input type="number" class="form-control" id="ees-bf-primaria" value="${ee.bf_primaria ?? ''}"></div>
      <div class="col"><label class="form-label small">Secundaria</label><input type="number" class="form-control" id="ees-bf-secundaria" value="${ee.bf_secundaria ?? ''}"></div>
      <div class="col"><label class="form-label small">Asignaciones</label><input type="number" class="form-control" id="ees-bf-asignaciones" value="${ee.bf_asignaciones ?? ''}"></div>
      <div class="col"><label class="form-label small">Discapacidad</label><input type="number" class="form-control" id="ees-bf-discapacidad" value="${ee.bf_discapacidad ?? ''}"></div>
      <div class="col"><label class="form-label small">CUD</label><input type="number" class="form-control" id="ees-bf-cud" value="${ee.bf_cud ?? ''}"></div>
    </div>

    <div class="subseccion-titulo">Becas Terciarias/Universitarias</div>
    <div class="row g-2">
      <div class="col-md-2"><label class="form-label small">Regulares</label><input type="number" class="form-control" id="ees-btu-regulares" value="${ee.btu_regulares ?? ''}"></div>
      <div class="col-md-2"><label class="form-label small">Egresados</label><input type="number" class="form-control" id="ees-btu-egresados" value="${ee.btu_egresados ?? ''}"></div>
      <div class="col-md-2"><label class="form-label small">Abandonaron</label><input type="number" class="form-control" id="ees-btu-abandonaron" value="${ee.btu_abandonaron ?? ''}"></div>
      <div class="col-md-6">Motivos de abandono <button type="button" class="btn btn-sm btn-outline-primary" id="btn-add-btu-motivo"><i class="bi bi-plus"></i></button><div id="dyn-btu-motivos"></div></div>
    </div>

    <div class="subseccion-titulo">Apoyo escolar primario</div>
    <div class="row g-2">
      <div class="col-md-2"><label class="form-label small">Niños/as</label><input type="number" class="form-control" id="ees-apoyo-primario-ninos" value="${ee.apoyo_primario_ninos ?? ''}"></div>
      <div class="col-md-3"><label class="form-label small">Frecuencia</label><input class="form-control" id="ees-apoyo-primario-frecuencia" value="${ee.apoyo_primario_frecuencia ?? ''}"></div>
      <div class="col-md-3"><label class="form-label small">Contenido principal</label><input class="form-control" id="ees-apoyo-primario-contenido-principal" value="${ee.apoyo_primario_contenido_principal ?? ''}"></div>
      <div class="col-md-4">Otros contenidos <button type="button" class="btn btn-sm btn-outline-primary" id="btn-add-apoyo-prim-contenido"><i class="bi bi-plus"></i></button><div id="dyn-apoyo-prim-contenidos"></div></div>
    </div>

    <div class="subseccion-titulo">Apoyo escolar secundario</div>
    <div class="row g-2">
      <div class="col-md-2"><label class="form-label small">Adolescentes</label><input type="number" class="form-control" id="ees-apoyo-secundario-adolescentes" value="${ee.apoyo_secundario_adolescentes ?? ''}"></div>
      <div class="col-md-3"><label class="form-label small">Frecuencia</label><input class="form-control" id="ees-apoyo-secundario-frecuencia" value="${ee.apoyo_secundario_frecuencia ?? ''}"></div>
      <div class="col-md-3"><label class="form-label small">Contenido principal</label><input class="form-control" id="ees-apoyo-secundario-contenido-principal" value="${ee.apoyo_secundario_contenido_principal ?? ''}"></div>
      <div class="col-md-4">Otros contenidos <button type="button" class="btn btn-sm btn-outline-primary" id="btn-add-apoyo-sec-contenido"><i class="bi bi-plus"></i></button><div id="dyn-apoyo-sec-contenidos"></div></div>
    </div>

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
      <div class="col"><label class="form-label small">Frecuencia (días)</label><input type="number" class="form-control" id="ees-dale-frecuencia-dias" value="${ee.dale_frecuencia_dias ?? ''}"></div>
    </div>

    <div class="subseccion-titulo">Necesidades de infraestructura (hasta 3) <button type="button" class="btn btn-sm btn-outline-primary" id="btn-add-necesidad"><i class="bi bi-plus"></i></button></div>
    <div id="dyn-necesidades"></div>

    <div class="subseccion-titulo">Preocupaciones sobre adolescentes/jóvenes (ranking 1-8) <button type="button" class="btn btn-sm btn-outline-primary" id="btn-add-preocupacion"><i class="bi bi-plus"></i></button></div>
    <div id="dyn-preocupaciones"></div>

    <div class="subseccion-titulo">Zona <button type="button" class="btn btn-sm btn-outline-primary" id="btn-add-zona"><i class="bi bi-plus"></i></button></div>
    <div id="dyn-zonas"></div>

    <button class="btn btn-primary mt-3" id="btn-guardar-ee-semestral"><i class="bi bi-save"></i> Guardar datos semestrales</button>
    <span id="ee-semestral-guardado-msg" class="text-success small ms-2"></span>`;

  dynEEAcciones = dynList('dyn-acciones-ee', [
    { key: 'eje', label: 'Eje' }, { key: 'accion', label: 'Acción' }, { key: 'tiene', label: 'Tiene', type: 'checkbox' },
  ], ee.acciones || []);
  dynEEGrupoMotorRoles = dynList('dyn-grupo-motor-roles', [
    { key: 'rol', label: 'Rol' }, { key: 'rol_otro', label: 'Detalle' }, { key: 'cantidad', label: 'Cantidad', type: 'number' },
  ], ee.grupo_motor_roles || []);
  dynEEItinEspacios = dynList('dyn-itin-espacios', [
    { key: 'espacio', label: 'Espacio' }, { key: 'espacio_otro', label: 'Detalle' },
  ], ee.itinerancia_espacios || []);
  dynEEItinActividades = dynList('dyn-itin-actividades', [{ key: 'actividad', label: 'Actividad' }], ee.itinerancia_actividades || []);
  dynEEItinRoles = dynList('dyn-itin-roles', [
    { key: 'rol', label: 'Rol' }, { key: 'rol_otro', label: 'Detalle' }, { key: 'cantidad', label: 'Cantidad', type: 'number' },
  ], ee.itinerancia_roles || []);
  dynEEDigitalTalleres = dynList('dyn-digital-talleres', [{ key: 'taller', label: 'Taller' }], ee.digital_talleres || []);
  dynEENivelesSuperiores = dynList('dyn-niveles-superiores', [
    { key: 'nombre_institucion', label: 'Institución' }, { key: 'tipo_acciones', label: 'Tipo de acciones' },
  ], ee.niveles_superiores || []);
  dynEEBtuMotivos = dynList('dyn-btu-motivos', [{ key: 'motivo', label: 'Motivo' }], ee.btu_abandono_motivos || []);
  dynEEApoyoPrimContenidos = dynList('dyn-apoyo-prim-contenidos', [{ key: 'contenido', label: 'Contenido' }], ee.apoyo_primario_contenidos || []);
  dynEEApoyoSecContenidos = dynList('dyn-apoyo-sec-contenidos', [{ key: 'contenido', label: 'Contenido' }], ee.apoyo_secundario_contenidos || []);
  dynEENecesidades = dynList('dyn-necesidades', [
    { key: 'necesidad', label: 'Necesidad' }, { key: 'orden', label: 'Orden', type: 'number' },
  ], ee.necesidades_infra || []);
  dynEEPreocupaciones = dynList('dyn-preocupaciones', [
    { key: 'preocupacion', label: 'Preocupación' }, { key: 'ranking', label: 'Ranking (1-8)', type: 'number' },
  ], ee.preocupaciones_joven || []);
  dynEEZonas = dynList('dyn-zonas', [{ key: 'zona', label: 'Zona' }], ee.ubicacion_zonas || []);

  const botones = {
    'btn-add-accion': dynEEAcciones, 'btn-add-rol-motor': dynEEGrupoMotorRoles,
    'btn-add-itin-espacio': dynEEItinEspacios, 'btn-add-itin-actividad': dynEEItinActividades, 'btn-add-itin-rol': dynEEItinRoles,
    'btn-add-digital-taller': dynEEDigitalTalleres, 'btn-add-nivel-superior': dynEENivelesSuperiores,
    'btn-add-btu-motivo': dynEEBtuMotivos, 'btn-add-apoyo-prim-contenido': dynEEApoyoPrimContenidos,
    'btn-add-apoyo-sec-contenido': dynEEApoyoSecContenidos, 'btn-add-necesidad': dynEENecesidades,
    'btn-add-preocupacion': dynEEPreocupaciones, 'btn-add-zona': dynEEZonas,
  };
  Object.entries(botones).forEach(([id, dyn]) => document.getElementById(id).addEventListener('click', () => dyn.addRow()));

  document.getElementById('btn-guardar-ee-semestral').addEventListener('click', () => guardarEspacioSemestral(ee.id));
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
  const payload = {
    acciones: dynEEAcciones.getValues(),
    grupo_motor_roles: dynEEGrupoMotorRoles.getValues(),
    itinerancia_espacios: dynEEItinEspacios.getValues(),
    itinerancia_actividades: dynEEItinActividades.getValues(),
    itinerancia_roles: dynEEItinRoles.getValues(),
    digital_talleres: dynEEDigitalTalleres.getValues(),
    niveles_superiores: dynEENivelesSuperiores.getValues(),
    btu_abandono_motivos: dynEEBtuMotivos.getValues(),
    apoyo_primario_contenidos: dynEEApoyoPrimContenidos.getValues(),
    apoyo_secundario_contenidos: dynEEApoyoSecContenidos.getValues(),
    necesidades_infra: dynEENecesidades.getValues(),
    preocupaciones_joven: dynEEPreocupaciones.getValues(),
    ubicacion_zonas: dynEEZonas.getValues(),
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
    document.getElementById(`ee-panel-${eeId}`)?.classList.remove('hidden');
    const msg = document.getElementById('ee-semestral-guardado-msg');
    if (msg) { msg.textContent = 'Guardado ✓'; setTimeout(() => msg.textContent = '', 2000); }
  } catch (err) {
    alert(err.message);
  }
}
