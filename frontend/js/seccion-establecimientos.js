let articulacionesActuales = [];

async function cargarSeccionEstablecimientos(relevamientoId) {
  document.getElementById('seccion-establecimientos').innerHTML = `
    <div class="card border-0 shadow-sm p-3 mb-3">
      <h6 class="mb-2"><i class="bi bi-search"></i> Buscar establecimiento en el padrón</h6>
      <div class="row g-2">
        <div class="col-md-6"><input class="form-control" id="est-busqueda" placeholder="Nombre del establecimiento (mín. 3 caracteres)..."></div>
        <div class="col-md-2 d-grid"><button class="btn btn-outline-primary" id="btn-buscar-establecimiento"><i class="bi bi-search"></i> Buscar</button></div>
      </div>
      <div id="est-resultados" class="mt-2"></div>
    </div>
    <div class="card border-0 shadow-sm p-3">
      <h6 class="mb-2">Establecimientos articulados en este semestre</h6>
      <div id="est-articulados"></div>
      <button class="btn btn-primary mt-2 btn-guardar" id="btn-guardar-establecimientos"><i class="bi bi-save"></i> Guardar selección</button>
      <span id="establecimientos-guardado-msg" class="text-success small ms-2"></span>
    </div>`;

  document.getElementById('btn-buscar-establecimiento').addEventListener('click', buscarEstablecimientos);
  document.getElementById('btn-guardar-establecimientos').addEventListener('click', () => guardarEstablecimientos(relevamientoId));

  articulacionesActuales = await api.get(`/relevamientos/${relevamientoId}/establecimientos`);
  pintarArticulados();
}

async function buscarEstablecimientos() {
  const q = document.getElementById('est-busqueda').value.trim();
  if (q.length < 3) { alert('Ingresá al menos 3 caracteres'); return; }
  const resultados = await api.get(`/establecimientos?q=${encodeURIComponent(q)}`);
  document.getElementById('est-resultados').innerHTML = resultados.map(e => `
    <div class="d-flex justify-content-between align-items-center border-bottom py-1">
      <span class="small">${e.nombre} <span class="text-muted">(${e.jurisdiccion ?? ''} · ${e.localidad ?? ''})</span></span>
      <button class="btn btn-sm btn-outline-primary" onclick='agregarArticulacion(${e.id}, ${JSON.stringify(e.nombre)}, ${JSON.stringify(e.jurisdiccion)}, ${JSON.stringify(e.localidad)})'>
        <i class="bi bi-plus"></i> Agregar
      </button>
    </div>`).join('') || '<p class="text-muted small">Sin resultados.</p>';
}

function agregarArticulacion(id, nombre, jurisdiccion, localidad) {
  if (articulacionesActuales.find(a => a.establecimiento_id === id)) {
    alert('Ya está agregado');
    return;
  }
  articulacionesActuales.push({
    establecimiento_id: id, nombre, jurisdiccion, localidad,
    accion_institucion: false, accion_articulacion_alfa: false, accion_seguimiento: false,
    accion_intercambio: false, accion_otros: false, detalle_otros: '',
  });
  pintarArticulados();
}

function quitarArticulacion(id) {
  articulacionesActuales = articulacionesActuales.filter(a => a.establecimiento_id !== id);
  pintarArticulados();
}

function pintarArticulados() {
  const container = document.getElementById('est-articulados');
  container.innerHTML = articulacionesActuales.map(a => `
    <div class="fila-dinamica" data-est-id="${a.establecimiento_id}">
      <div class="d-flex justify-content-between">
        <strong class="small">${a.nombre} <span class="text-muted">(${a.jurisdiccion ?? ''} · ${a.localidad ?? ''})</span></strong>
        <button class="btn btn-sm btn-outline-danger btn-del-row" onclick="quitarArticulacion(${a.establecimiento_id})"><i class="bi bi-trash"></i></button>
      </div>
      <div class="d-flex gap-3 flex-wrap mt-1">
        <div class="form-check"><input class="form-check-input chk-accion" type="checkbox" data-accion="accion_institucion" ${a.accion_institucion ? 'checked' : ''}><label class="form-check-label small">Institución a la que asisten</label></div>
        <div class="form-check"><input class="form-check-input chk-accion" type="checkbox" data-accion="accion_articulacion_alfa" ${a.accion_articulacion_alfa ? 'checked' : ''}><label class="form-check-label small">Articulación por alfabetización</label></div>
        <div class="form-check"><input class="form-check-input chk-accion" type="checkbox" data-accion="accion_seguimiento" ${a.accion_seguimiento ? 'checked' : ''}><label class="form-check-label small">Seguimiento a estudiantes</label></div>
        <div class="form-check"><input class="form-check-input chk-accion" type="checkbox" data-accion="accion_intercambio" ${a.accion_intercambio ? 'checked' : ''}><label class="form-check-label small">Intercambio por problemáticas barriales</label></div>
        <div class="form-check"><input class="form-check-input chk-accion" type="checkbox" data-accion="accion_otros" ${a.accion_otros ? 'checked' : ''}><label class="form-check-label small">Otros</label></div>
      </div>
      <input class="form-control form-control-sm mt-1 input-detalle-otros" placeholder="Detalle (si marcaste Otros)" value="${a.detalle_otros ?? ''}">
    </div>`).join('') || '<p class="text-muted small">Todavía no se agregó ningún establecimiento.</p>';
}

function leerArticuladosDesdeDOM() {
  return Array.from(document.querySelectorAll('#est-articulados .fila-dinamica')).map(fila => {
    const estId = parseInt(fila.dataset.estId);
    const obj = { establecimiento_id: estId };
    fila.querySelectorAll('.chk-accion').forEach(chk => { obj[chk.dataset.accion] = chk.checked; });
    obj.detalle_otros = fila.querySelector('.input-detalle-otros').value || null;
    return obj;
  });
}

async function guardarEstablecimientos(relevamientoId) {
  const payload = leerArticuladosDesdeDOM();
  try {
    articulacionesActuales = await api.put(`/relevamientos/${relevamientoId}/establecimientos`, payload);
    pintarArticulados();
    const msg = document.getElementById('establecimientos-guardado-msg');
    msg.textContent = 'Guardado ✓';
    setTimeout(() => msg.textContent = '', 2000);
  } catch (err) {
    alert(err.message);
  }
}
