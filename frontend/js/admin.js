session.requireRol(['admin']);
session.pintarNavbar('Administración');

let emausCache = [];

// ============================================================
// Emaús (para el dropdown de usuarios y la pestaña de referencia)
// ============================================================

async function cargarEmaus() {
  emausCache = await api.get('/admin/emaus');
  const select = document.getElementById('u-emaus-id');
  select.innerHTML = '<option value="">— sin asignar —</option>' +
    emausCache.map(e => `<option value="${e.id}">${e.nombre} (${e.diocesis_nombre})</option>`).join('');

  document.getElementById('tabla-emaus').innerHTML = emausCache.map(e => `
    <tr>
      <td>${e.id}</td>
      <td>${e.nombre}</td>
      <td>${e.diocesis_nombre ?? ''}</td>
      <td>${e.activo ? '<span class="badge bg-success">Sí</span>' : '<span class="badge bg-secondary">No</span>'}</td>
    </tr>`).join('');
}

// ============================================================
// Usuarios
// ============================================================

function toggleEmausWrapper() {
  const rol = document.getElementById('u-rol').value;
  document.getElementById('u-emaus-wrapper').classList.toggle('hidden', rol !== 'atl');
}
document.getElementById('u-rol').addEventListener('change', toggleEmausWrapper);

async function cargarUsuarios() {
  const usuarios = await api.get('/admin/usuarios');
  document.getElementById('tabla-usuarios').innerHTML = usuarios.map(u => `
    <tr>
      <td>${u.nombre} ${u.apellido}</td>
      <td>${u.email}</td>
      <td><span class="badge bg-light text-dark border">${u.rol}</span></td>
      <td>${u.emaus_id ? (emausCache.find(e => e.id === u.emaus_id)?.nombre ?? u.emaus_id) : '—'}</td>
      <td>${u.activo ? '<span class="badge bg-success">Sí</span>' : '<span class="badge bg-secondary">No</span>'}</td>
      <td>
        <button class="btn btn-sm btn-outline-primary" onclick='editarUsuario(${JSON.stringify(u)})'>
          <i class="bi bi-pencil"></i>
        </button>
      </td>
    </tr>`).join('');
}

function editarUsuario(u) {
  document.getElementById('u-id').value = u.id;
  document.getElementById('u-nombre').value = u.nombre;
  document.getElementById('u-apellido').value = u.apellido;
  document.getElementById('u-email').value = u.email;
  document.getElementById('u-password').value = '';
  document.getElementById('u-rol').value = u.rol;
  document.getElementById('u-emaus-id').value = u.emaus_id ?? '';
  document.getElementById('u-activo').checked = u.activo;
  toggleEmausWrapper();
  window.scrollTo({ top: 0, behavior: 'smooth' });
}

document.getElementById('btn-cancelar-usuario').addEventListener('click', () => {
  document.getElementById('form-usuario').reset();
  document.getElementById('u-id').value = '';
  toggleEmausWrapper();
});

document.getElementById('form-usuario').addEventListener('submit', async (e) => {
  e.preventDefault();
  const id = document.getElementById('u-id').value;
  const emausId = document.getElementById('u-emaus-id').value;
  const password = document.getElementById('u-password').value;

  const payload = {
    nombre: document.getElementById('u-nombre').value,
    apellido: document.getElementById('u-apellido').value,
    email: document.getElementById('u-email').value,
    rol: document.getElementById('u-rol').value,
    emaus_id: emausId ? parseInt(emausId) : null,
  };

  try {
    if (id) {
      payload.activo = document.getElementById('u-activo').checked;
      if (password) payload.password = password;
      await api.put(`/admin/usuarios/${id}`, payload);
    } else {
      if (!password) { alert('La contraseña es obligatoria para un usuario nuevo'); return; }
      payload.password = password;
      await api.post('/admin/usuarios', payload);
    }
    document.getElementById('form-usuario').reset();
    document.getElementById('u-id').value = '';
    toggleEmausWrapper();
    await cargarUsuarios();
  } catch (err) {
    alert(err.message);
  }
});

// ============================================================
// Asignaciones Responsable → Emaús
// ============================================================

async function cargarAsignaciones() {
  const asignaciones = await api.get('/admin/responsable-emaus');
  document.getElementById('lista-asignaciones').innerHTML = asignaciones.map(a => `
    <div class="fila-dinamica">
      <div class="fw-semibold mb-1">${a.nombre} ${a.apellido} <span class="text-muted small">(${a.email})</span></div>
      <select multiple class="form-select mb-2" id="asig-${a.responsable_id}" style="height:100px">
        ${emausCache.map(e => `<option value="${e.id}" ${a.emaus_ids.includes(e.id) ? 'selected' : ''}>${e.nombre}</option>`).join('')}
      </select>
      <button class="btn btn-sm btn-primary" onclick="guardarAsignacion(${a.responsable_id})">
        <i class="bi bi-save"></i> Guardar
      </button>
    </div>`).join('') || '<p class="text-muted small">No hay usuarios con rol responsable todavía.</p>';
}

async function guardarAsignacion(responsableId) {
  const select = document.getElementById(`asig-${responsableId}`);
  const emausIds = Array.from(select.selectedOptions).map(o => parseInt(o.value));
  try {
    await api.put(`/admin/responsable-emaus/${responsableId}`, { emaus_ids: emausIds });
    alert('Asignación guardada');
  } catch (err) {
    alert(err.message);
  }
}

// ============================================================
// Catálogos
// ============================================================

async function cargarCatalogo() {
  const categoria = document.getElementById('cat-categoria').value;
  const items = await api.get(`/admin/catalogos/${categoria}`);
  document.getElementById('tabla-catalogo').innerHTML = items.map(i => `
    <tr>
      <td>${i.valor}</td>
      <td><input type="number" class="form-control form-control-sm" style="width:80px" value="${i.orden}" onchange="actualizarCatalogo(${i.id}, {orden: parseInt(this.value)})"></td>
      <td>
        <div class="form-check form-switch">
          <input class="form-check-input" type="checkbox" ${i.activo ? 'checked' : ''} onchange="actualizarCatalogo(${i.id}, {activo: this.checked})">
        </div>
      </td>
      <td></td>
    </tr>`).join('');
}

async function actualizarCatalogo(id, cambios) {
  try {
    await api.put(`/admin/catalogos/${id}`, cambios);
  } catch (err) {
    alert(err.message);
  }
}

document.getElementById('cat-categoria').addEventListener('change', cargarCatalogo);

document.getElementById('btn-agregar-catalogo').addEventListener('click', async () => {
  const categoria = document.getElementById('cat-categoria').value;
  const valor = document.getElementById('cat-nuevo-valor').value.trim();
  if (!valor) return;
  try {
    await api.post('/admin/catalogos', { categoria, valor, orden: 0 });
    document.getElementById('cat-nuevo-valor').value = '';
    await cargarCatalogo();
  } catch (err) {
    alert(err.message);
  }
});

// ============================================================
// Padrón
// ============================================================

async function cargarEstadoPadron() {
  const estado = await api.get('/admin/padron/estado');
  const el = document.getElementById('padron-estado');
  if (!estado.ultima_importacion) {
    el.textContent = `Total de registros: ${estado.total_registros}. Todavía no se realizó ninguna importación.`;
  } else {
    el.innerHTML = `Total de registros: <strong>${estado.total_registros}</strong>. ` +
      `Última importación: ${new Date(estado.ultima_importacion).toLocaleString('es-AR')} ` +
      `(procesados: ${estado.ultimo_total_procesados}, insertados: ${estado.ultimo_insertados}, actualizados: ${estado.ultimo_actualizados}).`;
  }
}

// Encabezados esperados en la fila 13 del Excel del Ministerio → campo del modelo.
// Debe coincidir con ENCABEZADOS_PADRON en backend/app/routers/admin.py.
const ENCABEZADOS_PADRON = {
  "cueanexo": "cueanexo",
  "jurisdiccion": "jurisdiccion",
  "sector": "sector",
  "ambito": "ambito",
  "departamento": "departamento",
  "cod_depto": "cod_departamento",
  "codigo departamento": "cod_departamento",
  "localidad": "localidad",
  "cod_localidad": "cod_localidad",
  "codigo localidad": "cod_localidad",
  "nombre": "nombre",
  "domicilio": "domicilio",
  "cp": "codigo_postal",
  "codigo postal": "codigo_postal",
  "telefono": "telefono",
  "mail": "mail",
  "email": "mail",
  "inicial - jardin maternal": "nivel_inicial_maternal",
  "inicial - jardin de infantes": "nivel_inicial_infantes",
  "primario": "primario",
  "secundario": "secundario",
  "adultos": "adultos",
  "formacion profesional": "formacion_profesional",
  "alfabetizacion": "alfabetizacion",
};
const PADRON_CAMPOS_BOOL = new Set([
  'nivel_inicial_maternal', 'nivel_inicial_infantes', 'primario',
  'secundario', 'adultos', 'formacion_profesional', 'alfabetizacion',
]);
const PADRON_TAMANO_LOTE = 1500;

function normalizarEncabezado(texto) {
  return String(texto).trim().toLowerCase().normalize('NFD').replace(/[̀-ͯ]/g, '');
}

function esValorVerdadero(valor) {
  if (valor === null || valor === undefined) return false;
  if (typeof valor === 'boolean') return valor;
  const texto = String(valor).trim();
  return !['0', '', 'False', 'NO', 'No'].includes(texto);
}

document.getElementById('btn-importar-padron').addEventListener('click', async () => {
  const fileInput = document.getElementById('padron-file');
  const resultado = document.getElementById('padron-resultado');
  const progressWrapper = document.getElementById('padron-progress-wrapper');
  const progressBar = document.getElementById('padron-progress-bar');
  if (!fileInput.files.length) { alert('Seleccioná un archivo .xlsx primero'); return; }

  resultado.textContent = 'Leyendo el archivo en el navegador...';
  progressWrapper.classList.remove('hidden');
  progressBar.style.width = '0%';
  progressBar.textContent = '0%';

  try {
    const buffer = await fileInput.files[0].arrayBuffer();
    const wb = XLSX.read(buffer, { type: 'array' });
    const hoja = wb.Sheets[wb.SheetNames[0]];
    const filas = XLSX.utils.sheet_to_json(hoja, { header: 1, raw: true, defval: null });

    if (filas.length < 13) throw new Error('El archivo no tiene suficientes filas (se esperan encabezados en la fila 13)');
    const encabezados = filas[12]; // fila 13 (índice 12)

    const columnaACampo = {};
    encabezados.forEach((enc, idx) => {
      if (!enc) return;
      const campo = ENCABEZADOS_PADRON[normalizarEncabezado(enc)];
      if (campo) columnaACampo[idx] = campo;
    });
    if (!Object.values(columnaACampo).includes('cueanexo')) {
      throw new Error("No se encontró la columna 'cueanexo' en los encabezados (fila 13)");
    }

    const items = [];
    for (let i = 13; i < filas.length; i++) {
      const fila = filas[i];
      if (!fila) continue;
      const item = {};
      Object.entries(columnaACampo).forEach(([idx, campo]) => {
        const valor = fila[idx];
        item[campo] = PADRON_CAMPOS_BOOL.has(campo) ? esValorVerdadero(valor) : (valor === null || valor === undefined ? null : String(valor).trim());
      });
      if (!item.cueanexo) continue;
      items.push(item);
    }

    if (items.length === 0) throw new Error('No se encontraron filas con datos para importar');

    let totalProcesados = 0, totalInsertados = 0, totalActualizados = 0;
    const totalLotes = Math.ceil(items.length / PADRON_TAMANO_LOTE);

    for (let lote = 0; lote < totalLotes; lote++) {
      const desde = lote * PADRON_TAMANO_LOTE;
      const grupo = items.slice(desde, desde + PADRON_TAMANO_LOTE);
      const data = await api.post('/admin/padron/importar-batch', { items: grupo });
      totalProcesados += data.procesados;
      totalInsertados += data.insertados;
      totalActualizados += data.actualizados;

      const porcentaje = Math.round(((lote + 1) / totalLotes) * 100);
      progressBar.style.width = `${porcentaje}%`;
      progressBar.textContent = `${porcentaje}% (${desde + grupo.length}/${items.length})`;
      resultado.textContent = `Importando... lote ${lote + 1} de ${totalLotes}`;
    }

    await api.post('/admin/padron/registrar-importacion', {
      total_procesados: totalProcesados, insertados: totalInsertados, actualizados: totalActualizados,
    });

    resultado.innerHTML = `<span class="text-success">Listo.</span> Procesados: ${totalProcesados}, insertados: ${totalInsertados}, actualizados: ${totalActualizados}.`;
    await cargarEstadoPadron();
  } catch (err) {
    resultado.innerHTML = `<span class="text-danger">${err.message}</span>`;
  } finally {
    progressWrapper.classList.add('hidden');
  }
});

// ============================================================
// Relevamientos (abrir período)
// ============================================================

document.getElementById('btn-generar-relevamientos').addEventListener('click', async () => {
  const anio = parseInt(document.getElementById('rel-gen-anio').value);
  const semestre = document.getElementById('rel-gen-semestre').value;
  const resultado = document.getElementById('rel-gen-resultado');
  if (!confirm(`¿Abrir el relevamiento ${anio} - Semestre ${semestre} para todos los Emaús con ATL asignado?`)) return;

  resultado.textContent = 'Generando...';
  try {
    const data = await api.post('/relevamientos/generar', { anio, semestre });
    let html = `<span class="text-success">Listo.</span> Creados: ${data.creados}. Ya existían: ${data.ya_existian}.`;
    if (data.sin_atl.length) {
      html += `<div class="text-warning mt-1">Emaús sin ATL asignado (no se les creó relevamiento): ${data.sin_atl.join(', ')}</div>`;
    }
    resultado.innerHTML = html;
  } catch (err) {
    resultado.innerHTML = `<span class="text-danger">${err.message}</span>`;
  }
});

// ============================================================
// Init
// ============================================================

(async function init() {
  await cargarEmaus();
  await Promise.all([cargarUsuarios(), cargarAsignaciones(), cargarCatalogo(), cargarEstadoPadron()]);
})();
