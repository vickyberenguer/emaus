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
document.getElementById('filtro-rol-usuario').addEventListener('change', cargarUsuarios);

function formatUltimoIngreso(dt) {
  if (!dt) return '<span class="text-muted">—</span>';
  const d = new Date(dt.endsWith('Z') || dt.includes('+') ? dt : dt + 'Z');
  const opts = { timeZone: 'America/Argentina/Buenos_Aires' };
  const fecha = d.toLocaleDateString('es-AR', { ...opts, day: '2-digit', month: '2-digit', year: '2-digit' });
  const hora  = d.toLocaleTimeString('es-AR', { ...opts, hour: '2-digit', minute: '2-digit' });
  return `${fecha} ${hora}`;
}

async function cargarUsuarios() {
  const rol = document.getElementById('filtro-rol-usuario')?.value ?? 'responsable';
  const params = rol ? `?rol=${rol}` : '';
  const usuarios = await api.get(`/admin/usuarios${params}`);
  document.getElementById('tabla-usuarios').innerHTML = usuarios.map(u => `
    <tr>
      <td>${u.nombre} ${u.apellido}</td>
      <td>${u.email}</td>
      <td><span class="badge bg-light text-dark border">${u.rol}</span></td>
      <td>${u.emaus_id ? (emausCache.find(e => e.id === u.emaus_id)?.nombre ?? u.emaus_id) : '—'}</td>
      <td>${u.activo ? '<span class="badge bg-success">Sí</span>' : '<span class="badge bg-secondary">No</span>'}</td>
      <td class="text-muted small">${formatUltimoIngreso(u.ultimo_ingreso)}</td>
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
  "codigo de departamento": "cod_departamento",
  "localidad": "localidad",
  "cod_localidad": "cod_localidad",
  "codigo localidad": "cod_localidad",
  "codigo de localidad": "cod_localidad",
  "nombre": "nombre",
  "domicilio": "domicilio",
  "cp": "codigo_postal",
  "codigo postal": "codigo_postal",
  "c. p.": "codigo_postal",
  "telefono": "telefono",
  "mail": "mail",
  "email": "mail",
  "inicial - jardin maternal": "nivel_inicial_maternal",
  "nivel inicial - jardin maternal": "nivel_inicial_maternal",
  "inicial - jardin de infantes": "nivel_inicial_infantes",
  "nivel inicial - jardin de infantes": "nivel_inicial_infantes",
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

    // Buscamos la fila de encabezados real (la que tiene "cueanexo"), en vez de asumir
    // que es la fila 13 — distintas librerías pueden alinear filas vacías al inicio
    // de forma distinta y desplazar el índice.
    let filaEncabezados = -1;
    let columnaACampo = {};
    for (let i = 0; i < Math.min(filas.length, 40); i++) {
      const fila = filas[i] || [];
      const candidato = {};
      fila.forEach((enc, idx) => {
        if (!enc) return;
        const campo = ENCABEZADOS_PADRON[normalizarEncabezado(enc)];
        if (campo) candidato[idx] = campo;
      });
      if (Object.values(candidato).includes('cueanexo')) {
        filaEncabezados = i;
        columnaACampo = candidato;
        break;
      }
    }
    if (filaEncabezados === -1) {
      throw new Error("No se encontró una fila de encabezados con la columna 'cueanexo' en las primeras 40 filas del archivo");
    }

    const items = [];
    for (let i = filaEncabezados + 1; i < filas.length; i++) {
      const fila = filas[i];
      if (!fila) continue;
      const item = {};
      // Ojo: el archivo real repite nombres de columna (ej. "Primario" aparece una vez por
      // modalidad: Común, Especial, Adultos, etc.). Para los campos booleanos combinamos esas
      // columnas con OR en vez de dejar que la última pise a las anteriores.
      Object.entries(columnaACampo).forEach(([idx, campo]) => {
        const valor = fila[idx];
        if (PADRON_CAMPOS_BOOL.has(campo)) {
          item[campo] = !!item[campo] || esValorVerdadero(valor);
        } else {
          item[campo] = (valor === null || valor === undefined) ? null : String(valor).trim();
        }
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
// Espacios Educativos
// ============================================================

let eeCache = [];  // todos los EE cargados

async function cargarEEDeEmaus(emausId) {
  const emaus = emausCache.find(e => e.id === emausId);
  if (!emaus) return;
  try {
    const lista = await api.get(`/admin/ee?emaus_id=${emausId}`);
    lista.forEach(ee => { ee._emaus_nombre = emaus.nombre; });
    // Reemplazar EEs de este Emaús en el cache
    eeCache = eeCache.filter(e => e._emaus_nombre !== emaus.nombre).concat(lista);
  } catch (_) {}
  renderTablaEE();
}

function renderTablaEE() {
  const filtroEmausId = parseInt(document.getElementById('ee-filtro-emaus').value) || null;
  const mostrarInactivos = document.getElementById('ee-mostrar-inactivos').checked;

  const filas = eeCache.filter(ee => {
    if (filtroEmausId && ee._emaus_id !== filtroEmausId && !ee._emaus_nombre) return false;
    if (filtroEmausId) {
      const emaus = emausCache.find(e => e.id === filtroEmausId);
      if (emaus && ee._emaus_nombre !== emaus.nombre) return false;
    }
    if (!mostrarInactivos && !ee.activo) return false;
    return true;
  });

  document.getElementById('tabla-ee').innerHTML = filas.map(ee => `
    <tr class="${ee.activo ? '' : 'text-muted'}">
      <td>${ee.nombre}</td>
      <td><code class="small">${ee.nombre_hoja || '—'}</code></td>
      <td>${ee._emaus_nombre}</td>
      <td>${ee.activo
        ? '<span class="badge bg-success">Activo</span>'
        : '<span class="badge bg-secondary">Baja</span>'}</td>
      <td>${ee.activo
        ? `<button class="btn btn-sm btn-outline-danger" onclick="darDeBajaEE(${ee.id}, '${ee.nombre.replace(/'/g, "\\'")}')">
             <i class="bi bi-x-circle"></i> Dar de baja
           </button>`
        : ''}</td>
    </tr>`).join('');
}

async function darDeBajaEE(eeId, nombre) {
  if (!confirm(`¿Dar de baja "${nombre}"?\n\nSe ocultará la hoja en la planilla del Emaús.`)) return;
  try {
    const res = await api.patch(`/admin/ee/${eeId}/baja`);
    const idx = eeCache.findIndex(e => e.id === eeId);
    if (idx >= 0) eeCache[idx].activo = false;
    renderTablaEE();
    alert(`✓ EE dado de baja.\nSheets: ${res.sheets}`);
  } catch (e) {
    alert('Error: ' + (e.message || e));
  }
}

// Poblar select de Emaús en formulario de alta y filtro
function poblarSelectsEE() {
  const opts = emausCache.map(e => `<option value="${e.id}">${e.nombre}</option>`).join('');
  document.getElementById('ee-emaus-id').innerHTML = '<option value="">— Seleccionar —</option>' + opts;
  document.getElementById('ee-filtro-emaus').innerHTML = '<option value="">— Todos —</option>' + opts;
}

document.getElementById('form-ee-alta').addEventListener('submit', async (e) => {
  e.preventDefault();
  const body = {
    emaus_id: parseInt(document.getElementById('ee-emaus-id').value),
    nombre: document.getElementById('ee-nombre').value.trim(),
    nombre_hoja: document.getElementById('ee-nombre-hoja').value.trim(),
  };
  const res = document.getElementById('ee-alta-resultado');
  res.innerHTML = '<span class="text-muted">Procesando...</span>';
  try {
    const data = await api.post('/admin/ee', body);
    res.innerHTML = `<span class="text-success">✓ EE creado (id=${data.id}). Sheets: ${data.sheets}</span>`;
    e.target.reset();
    await cargarTodosLosEE();
  } catch (err) {
    res.innerHTML = `<span class="text-danger">Error: ${err.message || err}</span>`;
  }
});

document.getElementById('ee-filtro-emaus').addEventListener('change', async () => {
  const emausId = parseInt(document.getElementById('ee-filtro-emaus').value);
  if (emausId) await cargarEEDeEmaus(emausId);
  else renderTablaEE();
});
document.getElementById('ee-mostrar-inactivos').addEventListener('change', renderTablaEE);

// ============================================================
// Init
// ============================================================

(async function init() {
  await cargarEmaus();
  poblarSelectsEE();
  await Promise.all([cargarUsuarios(), cargarAsignaciones(), cargarCatalogo(), cargarEstadoPadron()]);
})();
