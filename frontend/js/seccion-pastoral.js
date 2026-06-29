let catEnfermedadNinos = [], catEnfermedadEmbarazadas = [], catTematicaPi = [], catArticulacion = [];

const ACCIONES_LIDER_FIJAS = [
  { accion: 'celebracion_vida', label: 'Celebración de la vida' },
  { accion: 'visita_domiciliaria', label: 'Visita domiciliaria' },
  { accion: 'reunion_evaluacion', label: 'Reunión de evaluación y reflexión' },
];

function selectEnfermedad(idx, catalogo, valorSeleccionado) {
  const opciones = catalogo.map(c => `<option value="${c.valor}" ${c.valor === valorSeleccionado ? 'selected' : ''}>${c.valor}</option>`).join('');
  return `<select class="form-select form-select-sm" id="pp-enf-${idx}">
    <option value="">— sin seleccionar —</option>${opciones}
  </select>`;
}

function renderShellPastoral() {
  document.getElementById('seccion-pastoral').innerHTML = `
    <div class="card border-0 shadow-sm p-3">
      <div class="row g-3">
        <div class="col-md-3"><label class="form-label small">Años de desarrollo de la pastoral</label><input type="number" class="form-control" id="pp-anios-desarrollo"></div>
        <div class="col-md-3"><label class="form-label small">Comunidades sin pastoral activa</label><input type="number" class="form-control" id="pp-comunidades-sin-pastoral"></div>
        <div class="col-md-3"><label class="form-label small">Capacitadoras</label><input type="number" class="form-control" id="pp-capacitadoras"></div>
        <div class="col-md-3"><label class="form-label small">Líderes</label><input type="number" class="form-control" id="pp-lideres"></div>
        <div class="col-md-6">
          <div class="form-check mt-2">
            <input class="form-check-input" type="checkbox" id="pp-presento-metodologia">
            <label class="form-check-label small" for="pp-presento-metodologia">Presentaron la metodología a otras comunidades</label>
          </div>
        </div>
      </div>

      <div class="subseccion-titulo">Personas acompañadas</div>
      <div class="row g-3">
        <div class="col-md-2"><label class="form-label small">Embarazadas 12-18</label><input type="number" class="form-control" id="pp-madres-embarazadas-12-18"></div>
        <div class="col-md-2"><label class="form-label small">Embarazadas 19-29</label><input type="number" class="form-control" id="pp-madres-embarazadas-19-29"></div>
        <div class="col-md-2"><label class="form-label small">Embarazadas 30+</label><input type="number" class="form-control" id="pp-madres-embarazadas-30-mas"></div>
        <div class="col-md-2"><label class="form-label small">No embarazadas</label><input type="number" class="form-control" id="pp-madres-no-embarazadas"></div>
        <div class="col-md-2"><label class="form-label small">Niños/as 0-3</label><input type="number" class="form-control" id="pp-ninos-0-3"></div>
        <div class="col-md-2"><label class="form-label small">Niños/as 4-6</label><input type="number" class="form-control" id="pp-ninos-4-6"></div>
        <div class="col-md-2"><label class="form-label small">Familias</label><input type="number" class="form-control" id="pp-familias"></div>
      </div>

      <div class="subseccion-titulo">Alfabetización</div>
      <div class="row g-3">
        <div class="col-md-6">
          <div class="form-check"><input class="form-check-input" type="checkbox" id="pp-lideres-todas-alfabetizadas"><label class="form-check-label small">¿Nuestras líderes saben leer y escribir? (todas)</label></div>
          <label class="form-label small mt-1">Si no todas, cantidad que no</label><input type="number" class="form-control" id="pp-lideres-no-alfabetizadas-cantidad" style="max-width:200px">
          <div class="form-check mt-1"><input class="form-check-input" type="checkbox" id="pp-lideres-en-alfabetizacion"><label class="form-check-label small">Alguna participa de una propuesta de alfabetización</label></div>
        </div>
        <div class="col-md-6">
          <div class="form-check"><input class="form-check-input" type="checkbox" id="pp-madres-todas-alfabetizadas"><label class="form-check-label small">¿Están todas las madres alfabetizadas?</label></div>
          <label class="form-label small mt-1">Si no todas, cantidad que no</label><input type="number" class="form-control" id="pp-madres-no-alfabetizadas-cantidad" style="max-width:200px">
          <div class="form-check mt-1"><input class="form-check-input" type="checkbox" id="pp-madres-en-alfabetizacion"><label class="form-check-label small">Alguna participa de una propuesta de alfabetización</label></div>
        </div>
      </div>

      <div class="subseccion-titulo">¿Cuáles son las 3 enfermedades más recurrentes en niños/as acompañados? ${ayudaIcon('Elegí las 3 enfermedades que más se repiten. Si alguna no está en la lista, elegí la opción "Otra" y escribí el detalle.')}</div>
      <div id="enf-ninos-slots" class="row g-2"></div>

      <div class="subseccion-titulo">¿Cuáles son las 3 enfermedades más recurrentes en embarazadas acompañadas?</div>
      <div id="enf-embarazadas-slots" class="row g-2"></div>

      <div class="subseccion-titulo">Las líderes, ¿están realizando las siguientes acciones?</div>
      <div id="dyn-acciones-lider"></div>

      <div class="subseccion-titulo">Temáticas abordadas desde julio a diciembre del semestre ${ayudaIcon('Tildá todas las temáticas que se trabajaron en el semestre y, en cada una, indicá en cuántas comunidades se abordó.')}</div>
      <div id="lista-tematicas"></div>

      <div class="subseccion-titulo">¿Trabajan de manera articulada con alguna de las siguientes organizaciones e instituciones?</div>
      <div id="lista-articulaciones"></div>

      <button class="btn btn-primary mt-3 btn-guardar" id="btn-guardar-pastoral"><i class="bi bi-save"></i> Guardar Pastoral PI</button>
      <span id="pastoral-guardado-msg" class="text-success small ms-2"></span>
    </div>`;

  document.getElementById('btn-guardar-pastoral').addEventListener('click', guardarPastoral);
}

function renderEnfermedadSlots(containerId, catalogo, seleccionadas) {
  const container = document.getElementById(containerId);
  container.innerHTML = '';
  for (let i = 0; i < 3; i++) {
    const actual = seleccionadas[i] || {};
    const esOtra = actual.enfermedad && !catalogo.find(c => c.valor === actual.enfermedad && c.valor.toLowerCase() !== 'otra');
    const div = document.createElement('div');
    div.className = 'col-md-4';
    div.innerHTML = `
      <label class="form-label small">Enfermedad ${i + 1}</label>
      ${selectEnfermedad(i, catalogo, actual.enfermedad)}
      <input class="form-control form-control-sm mt-1" id="pp-enf-${containerId}-otra-${i}" placeholder="Detalle si elegiste 'Otra'" value="${actual.enfermedad_otra ?? ''}">`;
    container.appendChild(div);
    // corregimos el id del select para que sea único por containerId
    div.querySelector('select').id = `pp-enf-${containerId}-${i}`;
  }
}

function leerEnfermedadSlots(containerId) {
  const resultado = [];
  for (let i = 0; i < 3; i++) {
    const select = document.getElementById(`pp-enf-${containerId}-${i}`);
    const otra = document.getElementById(`pp-enf-${containerId}-otra-${i}`);
    if (select && select.value) {
      resultado.push({ enfermedad: select.value, enfermedad_otra: otra.value || null, orden: i + 1 });
    }
  }
  return resultado;
}

function renderListaTematicas(seleccionadas) {
  const container = document.getElementById('lista-tematicas');
  container.innerHTML = catTematicaPi.map((c, i) => {
    const actual = seleccionadas.find(t => t.tematica === c.valor) || {};
    const esOtras = c.valor.toLowerCase().startsWith('otra');
    return `
      <div class="row g-2 align-items-center mb-1 fila-tematica" data-valor="${c.valor}">
        <div class="col-md-5"><div class="form-check"><input class="form-check-input chk-tematica" type="checkbox" ${actual.tematica ? 'checked' : ''}><label class="form-check-label small">${c.valor}</label></div></div>
        <div class="col-md-3"><input type="number" class="form-control form-control-sm input-cantidad" placeholder="Cant. comunidades" value="${actual.comunidades_cantidad ?? ''}"></div>
        ${esOtras ? `<div class="col-md-4"><input class="form-control form-control-sm input-otra" placeholder="Detalle" value="${actual.tematica_otra ?? ''}"></div>` : ''}
      </div>`;
  }).join('');
}

function leerListaTematicas() {
  return Array.from(document.querySelectorAll('#lista-tematicas .fila-tematica'))
    .filter(fila => fila.querySelector('.chk-tematica').checked)
    .map(fila => ({
      tematica: fila.dataset.valor,
      comunidades_cantidad: fila.querySelector('.input-cantidad').value ? parseInt(fila.querySelector('.input-cantidad').value) : null,
      tematica_otra: fila.querySelector('.input-otra')?.value || null,
    }));
}

function renderListaArticulaciones(seleccionadas) {
  const container = document.getElementById('lista-articulaciones');
  container.innerHTML = catArticulacion.map(c => {
    const actual = seleccionadas.find(a => a.organizacion === c.valor) || {};
    const esOtro = c.valor.toLowerCase().startsWith('otro');
    return `
      <div class="row g-2 align-items-center mb-1 fila-articulacion" data-valor="${c.valor}">
        <div class="col-md-5"><div class="form-check"><input class="form-check-input chk-articulacion" type="checkbox" ${actual.organizacion ? 'checked' : ''}><label class="form-check-label small">${c.valor}</label></div></div>
        ${esOtro ? `<div class="col-md-4"><input class="form-control form-control-sm input-otra" placeholder="Detalle" value="${actual.organizacion_otra ?? ''}"></div>` : ''}
      </div>`;
  }).join('');
}

function leerListaArticulaciones() {
  return Array.from(document.querySelectorAll('#lista-articulaciones .fila-articulacion'))
    .filter(fila => fila.querySelector('.chk-articulacion').checked)
    .map(fila => ({
      organizacion: fila.dataset.valor,
      organizacion_otra: fila.querySelector('.input-otra')?.value || null,
    }));
}

function renderAccionesLider(acciones) {
  const container = document.getElementById('dyn-acciones-lider');
  container.innerHTML = '';
  ACCIONES_LIDER_FIJAS.forEach(def => {
    const existente = acciones.find(a => a.accion === def.accion) || {};
    const row = document.createElement('div');
    row.className = 'row g-2 align-items-center mb-1 dyn-row-fija';
    row.dataset.accion = def.accion;
    row.innerHTML = `
      <div class="col-md-3">${def.label}</div>
      <div class="col-md-2 form-check"><input class="form-check-input" type="checkbox" data-key="realiza" ${existente.realiza ? 'checked' : ''}> <label class="form-check-label small">Realiza</label></div>
      <div class="col-md-3"><input class="form-control form-control-sm" data-key="frecuencia" placeholder="Frecuencia" value="${existente.frecuencia ?? ''}"></div>
      <div class="col-md-3"><input type="number" class="form-control form-control-sm" data-key="cantidad_semestre" placeholder="Cantidad semestre" value="${existente.cantidad_semestre ?? ''}"></div>`;
    container.appendChild(row);
  });
}

function getAccionesLiderValues() {
  return Array.from(document.querySelectorAll('#dyn-acciones-lider .dyn-row-fija')).map(row => ({
    accion: row.dataset.accion,
    realiza: row.querySelector('[data-key=realiza]').checked,
    frecuencia: row.querySelector('[data-key=frecuencia]').value || null,
    cantidad_semestre: row.querySelector('[data-key=cantidad_semestre]').value ? parseInt(row.querySelector('[data-key=cantidad_semestre]').value) : null,
  }));
}

async function cargarSeccionPastoral(relevamientoId) {
  renderShellPastoral();
  const [data, enfNinos, enfEmb, tematicas, articulaciones] = await Promise.all([
    api.get(`/relevamientos/${relevamientoId}/pastoral-pi`),
    api.get('/catalogos/enfermedad_ninos'),
    api.get('/catalogos/enfermedad_embarazadas'),
    api.get('/catalogos/tematica_pi'),
    api.get('/catalogos/articulacion'),
  ]);
  catEnfermedadNinos = enfNinos;
  catEnfermedadEmbarazadas = enfEmb;
  catTematicaPi = tematicas;
  catArticulacion = articulaciones;
  const pastoral = data || {};

  const campos = [
    'anios_desarrollo', 'comunidades_sin_pastoral', 'capacitadoras', 'lideres',
    'madres_embarazadas_12_18', 'madres_embarazadas_19_29', 'madres_embarazadas_30_mas', 'madres_no_embarazadas',
    'ninos_0_3', 'ninos_4_6', 'familias',
    'lideres_no_alfabetizadas_cantidad', 'madres_no_alfabetizadas_cantidad',
  ];
  campos.forEach(c => {
    const el = document.getElementById(`pp-${c.replace(/_/g, '-')}`);
    if (el) el.value = pastoral[c] ?? '';
  });

  ['presento_metodologia', 'lideres_todas_alfabetizadas', 'lideres_en_alfabetizacion', 'madres_todas_alfabetizadas', 'madres_en_alfabetizacion'].forEach(c => {
    const el = document.getElementById(`pp-${c.replace(/_/g, '-')}`);
    if (el) el.checked = !!pastoral[c];
  });

  renderEnfermedadSlots('enf-ninos-slots', catEnfermedadNinos, pastoral.enfermedades_ninos || []);
  renderEnfermedadSlots('enf-embarazadas-slots', catEnfermedadEmbarazadas, pastoral.enfermedades_embarazadas || []);
  renderAccionesLider(pastoral.acciones_lider || []);
  renderListaTematicas(pastoral.tematicas || []);
  renderListaArticulaciones(pastoral.articulaciones || []);
}

async function guardarPastoral() {
  const payload = {
    enfermedades_ninos: leerEnfermedadSlots('enf-ninos-slots'),
    enfermedades_embarazadas: leerEnfermedadSlots('enf-embarazadas-slots'),
    acciones_lider: getAccionesLiderValues(),
    tematicas: leerListaTematicas(),
    articulaciones: leerListaArticulaciones(),
  };

  const numCampos = [
    'anios_desarrollo', 'comunidades_sin_pastoral', 'capacitadoras', 'lideres',
    'madres_embarazadas_12_18', 'madres_embarazadas_19_29', 'madres_embarazadas_30_mas', 'madres_no_embarazadas',
    'ninos_0_3', 'ninos_4_6', 'familias',
    'lideres_no_alfabetizadas_cantidad', 'madres_no_alfabetizadas_cantidad',
  ];
  numCampos.forEach(c => {
    const el = document.getElementById(`pp-${c.replace(/_/g, '-')}`);
    payload[c] = el.value === '' ? null : parseInt(el.value);
  });

  ['presento_metodologia', 'lideres_todas_alfabetizadas', 'lideres_en_alfabetizacion', 'madres_todas_alfabetizadas', 'madres_en_alfabetizacion'].forEach(c => {
    payload[c] = document.getElementById(`pp-${c.replace(/_/g, '-')}`).checked;
  });

  try {
    await api.put(`/relevamientos/${relevamientoActual.id}/pastoral-pi`, payload);
    const msg = document.getElementById('pastoral-guardado-msg');
    msg.textContent = 'Guardado ✓';
    setTimeout(() => msg.textContent = '', 2000);
  } catch (err) {
    alert(err.message);
  }
}
