async function cargarSeccionTalleres(relevamientoId) {
  document.getElementById('seccion-talleres').innerHTML = `
    <div class="card border-0 shadow-sm p-3 mb-3">
      <h6 class="mb-3"><i class="bi bi-plus-circle"></i> Nuevo taller</h6>
      <div class="row g-2">
        <div class="col-md-2"><label class="form-label small">Eje</label><input class="form-control" id="tl-eje"></div>
        <div class="col-md-2"><label class="form-label small">Temática</label><input class="form-control" id="tl-tematica"></div>
        <div class="col-md-1"><label class="form-label small">Participantes</label><input type="number" class="form-control" id="tl-participantes"></div>
        <div class="col-md-1"><label class="form-label small">EE invol.</label><input type="number" class="form-control" id="tl-ee"></div>
        <div class="col-md-1"><label class="form-label small">Comunidades PI</label><input type="number" class="form-control" id="tl-comunidades-pi"></div>
        <div class="col-md-2"><label class="form-label small">Otras instituciones</label><input class="form-control" id="tl-otras-instituciones"></div>
        <div class="col-md-2"><label class="form-label small">Perfil capacitadores</label><input class="form-control" id="tl-perfil-capacitadores"></div>
        <div class="col-md-1 d-grid"><button class="btn btn-primary btn-guardar" id="btn-add-taller"><i class="bi bi-plus"></i></button></div>
      </div>
    </div>
    <div class="card border-0 shadow-sm p-3">
      <table class="table table-sm">
        <thead><tr><th>Eje</th><th>Temática</th><th>Participantes</th><th>EE</th><th>Com. PI</th><th></th></tr></thead>
        <tbody id="tabla-talleres"></tbody>
      </table>
    </div>`;

  document.getElementById('btn-add-taller').addEventListener('click', () => agregarTaller(relevamientoId));
  await refrescarTalleres(relevamientoId);
}

async function refrescarTalleres(relevamientoId) {
  const talleres = await api.get(`/relevamientos/${relevamientoId}/talleres`);
  document.getElementById('tabla-talleres').innerHTML = talleres.map(t => `
    <tr>
      <td>${t.eje}</td>
      <td>${t.tematica}</td>
      <td>${t.cantidad_participantes ?? ''}</td>
      <td>${t.cantidad_ee ?? ''}</td>
      <td>${t.cantidad_comunidades_pi ?? ''}</td>
      <td><button class="btn btn-sm btn-outline-danger btn-del-row" onclick="eliminarTaller(${relevamientoId}, ${t.id})"><i class="bi bi-trash"></i></button></td>
    </tr>`).join('') || '<tr><td colspan="6" class="text-muted small">Sin talleres registrados.</td></tr>';
}

async function agregarTaller(relevamientoId) {
  const eje = document.getElementById('tl-eje').value.trim();
  const tematica = document.getElementById('tl-tematica').value.trim();
  if (!eje || !tematica) { alert('Eje y temática son obligatorios'); return; }

  const payload = {
    eje, tematica,
    cantidad_participantes: parseInt(document.getElementById('tl-participantes').value) || null,
    cantidad_ee: parseInt(document.getElementById('tl-ee').value) || null,
    cantidad_comunidades_pi: parseInt(document.getElementById('tl-comunidades-pi').value) || null,
    otras_instituciones: document.getElementById('tl-otras-instituciones').value || null,
    perfil_capacitadores: document.getElementById('tl-perfil-capacitadores').value || null,
  };

  try {
    await api.post(`/relevamientos/${relevamientoId}/talleres`, payload);
    ['tl-eje', 'tl-tematica', 'tl-participantes', 'tl-ee', 'tl-comunidades-pi', 'tl-otras-instituciones', 'tl-perfil-capacitadores']
      .forEach(id => document.getElementById(id).value = '');
    await refrescarTalleres(relevamientoId);
  } catch (err) {
    alert(err.message);
  }
}

async function eliminarTaller(relevamientoId, tallerId) {
  if (!confirm('¿Eliminar este taller?')) return;
  try {
    await api.delete(`/relevamientos/${relevamientoId}/talleres/${tallerId}`);
    await refrescarTalleres(relevamientoId);
  } catch (err) {
    alert(err.message);
  }
}
