let dynEnfermedadesNinos, dynEnfermedadesEmbarazadas, dynAccionesLider, dynTematicas, dynArticulaciones;

function renderShellPastoral() {
  document.getElementById('seccion-pastoral').innerHTML = `
    <div class="card border-0 shadow-sm p-3">
      <div class="row g-3">
        <div class="col-md-3"><label class="form-label small">Años de desarrollo de la pastoral</label><input type="number" class="form-control" id="pp-anios-desarrollo"></div>
        <div class="col-md-3"><label class="form-label small">Comunidades sin pastoral activa</label><input type="number" class="form-control" id="pp-comunidades-sin-pastoral"></div>
        <div class="col-md-3"><label class="form-label small">Capacitadoras</label><input type="number" class="form-control" id="pp-capacitadoras"></div>
        <div class="col-md-3"><label class="form-label small">Líderes</label><input type="number" class="form-control" id="pp-lideres"></div>
        <div class="col-md-4">
          <div class="form-check mt-4">
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
        <div class="col-md-3">
          <div class="form-check"><input class="form-check-input" type="checkbox" id="pp-lideres-todas-alfabetizadas"><label class="form-check-label small">Todas las líderes alfabetizadas</label></div>
          <label class="form-label small mt-1">Líderes no alfabetizadas (cant.)</label><input type="number" class="form-control" id="pp-lideres-no-alfabetizadas-cantidad">
          <div class="form-check mt-1"><input class="form-check-input" type="checkbox" id="pp-lideres-en-alfabetizacion"><label class="form-check-label small">En proceso de alfabetización</label></div>
        </div>
        <div class="col-md-3">
          <div class="form-check"><input class="form-check-input" type="checkbox" id="pp-madres-todas-alfabetizadas"><label class="form-check-label small">Todas las madres alfabetizadas</label></div>
          <label class="form-label small mt-1">Madres no alfabetizadas (cant.)</label><input type="number" class="form-control" id="pp-madres-no-alfabetizadas-cantidad">
          <div class="form-check mt-1"><input class="form-check-input" type="checkbox" id="pp-madres-en-alfabetizacion"><label class="form-check-label small">En proceso de alfabetización</label></div>
        </div>
      </div>

      <div class="subseccion-titulo">Enfermedades más frecuentes en niños/as <button type="button" class="btn btn-sm btn-outline-primary btn-add-row" id="btn-add-enf-ninos"><i class="bi bi-plus"></i></button></div>
      <div id="dyn-enfermedades-ninos"></div>

      <div class="subseccion-titulo">Enfermedades más frecuentes en embarazadas <button type="button" class="btn btn-sm btn-outline-primary btn-add-row" id="btn-add-enf-embarazadas"><i class="bi bi-plus"></i></button></div>
      <div id="dyn-enfermedades-embarazadas"></div>

      <div class="subseccion-titulo">Acciones de líderes en el semestre</div>
      <div id="dyn-acciones-lider"></div>

      <div class="subseccion-titulo">Temáticas abordadas <button type="button" class="btn btn-sm btn-outline-primary btn-add-row" id="btn-add-tematica"><i class="bi bi-plus"></i></button></div>
      <div id="dyn-tematicas"></div>

      <div class="subseccion-titulo">Articulaciones con organizaciones/instituciones <button type="button" class="btn btn-sm btn-outline-primary btn-add-row" id="btn-add-articulacion"><i class="bi bi-plus"></i></button></div>
      <div id="dyn-articulaciones"></div>

      <button class="btn btn-primary mt-3 btn-guardar" id="btn-guardar-pastoral"><i class="bi bi-save"></i> Guardar Pastoral PI</button>
      <span id="pastoral-guardado-msg" class="text-success small ms-2"></span>
    </div>`;

  document.getElementById('btn-add-enf-ninos').addEventListener('click', () => dynEnfermedadesNinos.addRow());
  document.getElementById('btn-add-enf-embarazadas').addEventListener('click', () => dynEnfermedadesEmbarazadas.addRow());
  document.getElementById('btn-add-tematica').addEventListener('click', () => dynTematicas.addRow());
  document.getElementById('btn-add-articulacion').addEventListener('click', () => dynArticulaciones.addRow());
  document.getElementById('btn-guardar-pastoral').addEventListener('click', guardarPastoral);
}

const ACCIONES_LIDER_FIJAS = [
  { accion: 'celebracion_vida', label: 'Celebración de vida' },
  { accion: 'visita_domiciliaria', label: 'Visita domiciliaria' },
  { accion: 'reunion_evaluacion', label: 'Reunión de evaluación' },
];

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
  const data = await api.get(`/relevamientos/${relevamientoId}/pastoral-pi`) || {};

  const campos = [
    'anios_desarrollo', 'comunidades_sin_pastoral', 'capacitadoras', 'lideres',
    'madres_embarazadas_12_18', 'madres_embarazadas_19_29', 'madres_embarazadas_30_mas', 'madres_no_embarazadas',
    'ninos_0_3', 'ninos_4_6', 'familias',
    'lideres_no_alfabetizadas_cantidad', 'madres_no_alfabetizadas_cantidad',
  ];
  campos.forEach(c => {
    const el = document.getElementById(`pp-${c.replace(/_/g, '-')}`);
    if (el) el.value = data[c] ?? '';
  });

  ['presento_metodologia', 'lideres_todas_alfabetizadas', 'lideres_en_alfabetizacion', 'madres_todas_alfabetizadas', 'madres_en_alfabetizacion'].forEach(c => {
    const el = document.getElementById(`pp-${c.replace(/_/g, '-')}`);
    if (el) el.checked = !!data[c];
  });

  dynEnfermedadesNinos = dynList('dyn-enfermedades-ninos', [
    { key: 'enfermedad', label: 'Enfermedad' }, { key: 'enfermedad_otra', label: 'Detalle (si es "Otra")' }, { key: 'orden', label: 'Orden', type: 'number' },
  ], data.enfermedades_ninos || []);

  dynEnfermedadesEmbarazadas = dynList('dyn-enfermedades-embarazadas', [
    { key: 'enfermedad', label: 'Enfermedad' }, { key: 'enfermedad_otra', label: 'Detalle (si es "Otra")' }, { key: 'orden', label: 'Orden', type: 'number' },
  ], data.enfermedades_embarazadas || []);

  renderAccionesLider(data.acciones_lider || []);

  dynTematicas = dynList('dyn-tematicas', [
    { key: 'tematica', label: 'Temática' }, { key: 'tematica_otra', label: 'Detalle (si es "Otra")' }, { key: 'comunidades_cantidad', label: 'Cant. comunidades', type: 'number' },
  ], data.tematicas || []);

  dynArticulaciones = dynList('dyn-articulaciones', [
    { key: 'organizacion', label: 'Organización' }, { key: 'organizacion_otra', label: 'Detalle (si es "Otra")' },
  ], data.articulaciones || []);
}

async function guardarPastoral() {
  const payload = {
    enfermedades_ninos: dynEnfermedadesNinos.getValues(),
    enfermedades_embarazadas: dynEnfermedadesEmbarazadas.getValues(),
    acciones_lider: getAccionesLiderValues(),
    tematicas: dynTematicas.getValues(),
    articulaciones: dynArticulaciones.getValues(),
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
