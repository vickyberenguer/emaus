session.requireRol(['atl']);
session.pintarNavbar('Formulario de relevamiento');

let relevamientosCache = [];
let relevamientoActual = null;

const ESTADO_LABEL = {
  borrador: 'Borrador',
  enviado: 'Enviado',
  validado: 'Validado',
  rechazado: 'Rechazado',
};

function pintarEstado() {
  const info = document.getElementById('rel-estado-info');
  const btnEnviar = document.getElementById('btn-enviar-relevamiento');

  if (!relevamientoActual) {
    info.innerHTML = '';
    btnEnviar.disabled = true;
    document.getElementById('form-wrapper').classList.add('hidden');
    document.getElementById('sin-relevamiento').classList.remove('hidden');
    return;
  }

  document.getElementById('form-wrapper').classList.remove('hidden');
  document.getElementById('sin-relevamiento').classList.add('hidden');

  const badgeClass = `badge-estado-${relevamientoActual.estado}`;
  let html = `<span class="badge ${badgeClass}">${ESTADO_LABEL[relevamientoActual.estado]}</span>`;
  if (relevamientoActual.comentario_rechazo) {
    html += ` <span class="text-danger small ms-2"><i class="bi bi-exclamation-triangle"></i> Motivo de rechazo: ${relevamientoActual.comentario_rechazo}</span>`;
  }
  info.innerHTML = html;

  const editable = relevamientoActual.estado === 'borrador';
  btnEnviar.disabled = !editable;
  document.querySelectorAll('#form-wrapper input, #form-wrapper select, #form-wrapper textarea, #form-wrapper button.btn-guardar, #form-wrapper button.btn-add-row, #form-wrapper button.btn-del-row')
    .forEach(el => { el.disabled = !editable; });
}

async function cargarRelevamientos() {
  relevamientosCache = await api.get('/relevamientos');
  const select = document.getElementById('rel-selector');
  select.innerHTML = '<option value="">— seleccionar —</option>' +
    relevamientosCache.map(r => `<option value="${r.id}">${r.anio} - Semestre ${r.semestre} (${ESTADO_LABEL[r.estado]})</option>`).join('');
}

async function seleccionarRelevamiento(id) {
  if (!id) {
    relevamientoActual = null;
    pintarEstado();
    return;
  }
  relevamientoActual = await api.get(`/relevamientos/${id}`);
  pintarEstado();
  await Promise.all([
    cargarSeccionPastoral(relevamientoActual.id),
    cargarSeccionEspacios(relevamientoActual.id),
    cargarSeccionTalleres(relevamientoActual.id),
    cargarSeccionEstablecimientos(relevamientoActual.id),
  ]);
}

document.getElementById('rel-selector').addEventListener('change', (e) => seleccionarRelevamiento(e.target.value));

document.getElementById('btn-enviar-relevamiento').addEventListener('click', async () => {
  if (!relevamientoActual) return;
  if (!confirm('¿Enviar este relevamiento para validación? No vas a poder seguir editándolo hasta que el responsable lo revise.')) return;
  try {
    relevamientoActual = await api.put(`/relevamientos/${relevamientoActual.id}/estado`, { accion: 'enviar' });
    pintarEstado();
  } catch (err) {
    alert(err.message);
  }
});

(async function init() {
  await cargarRelevamientos();
  // El más reciente (primero de la lista, ya viene ordenado por año/semestre desc) se selecciona solo
  if (relevamientosCache.length > 0) {
    document.getElementById('rel-selector').value = relevamientosCache[0].id;
    await seleccionarRelevamiento(relevamientosCache[0].id);
  } else {
    pintarEstado();
  }
})();
