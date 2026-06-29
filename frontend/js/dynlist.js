/**
 * Checklist fija: lista predefinida de opciones (igual a la planilla de Sheets),
 * cada una con un checkbox y, opcionalmente, un campo extra (cantidad, detalle, ranking).
 *
 * items: [{value, label}]
 * opts.extraField: {key, label, type: 'number'|'text'} — se muestra junto al check si está tildado
 * opts.maxSelected: número máximo de opciones que se pueden tildar (valida y avisa, no bloquea)
 * opts.otroKeys: valores (en minúsculas, sin tilde) que disparan un input de texto "Detalle" (ej: 'otro', 'otra', 'otras')
 */
function checklist(containerId, items, seleccionados = [], opts = {}) {
  const container = document.getElementById(containerId);
  const esOtro = (label) => /^otr[ao]s?\b/i.test(label.trim());

  container.innerHTML = `
    ${opts.maxSelected ? `<div class="small text-muted mb-1">Seleccioná hasta ${opts.maxSelected} opciones.</div>` : ''}
    ${items.map(item => {
      const actual = seleccionados.find(s => s.valor === item.value) || null;
      const otro = esOtro(item.label);
      return `
        <div class="row g-2 align-items-center mb-1 fila-checklist" data-valor="${item.value}">
          <div class="col-md-5">
            <div class="form-check">
              <input class="form-check-input chk-item" type="checkbox" ${actual ? 'checked' : ''}>
              <label class="form-check-label small">${item.label}</label>
            </div>
          </div>
          ${opts.extraField ? `<div class="col-md-3"><input type="${opts.extraField.type === 'number' ? 'number' : 'text'}" class="form-control form-control-sm input-extra" placeholder="${opts.extraField.label}" value="${actual?.extra ?? ''}"></div>` : ''}
          ${otro ? `<div class="col-md-4"><input class="form-control form-control-sm input-otro" placeholder="Detalle" value="${actual?.otro ?? ''}"></div>` : ''}
        </div>`;
    }).join('')}`;

  return {
    getValues() {
      const seleccionadas = Array.from(container.querySelectorAll('.fila-checklist')).filter(f => f.querySelector('.chk-item').checked);
      if (opts.maxSelected && seleccionadas.length > opts.maxSelected) {
        alert(`Seleccionaste más de ${opts.maxSelected} opciones en una lista que tiene ese límite. Revisá esa sección antes de guardar.`);
      }
      return seleccionadas.map(f => ({
        valor: f.dataset.valor,
        extra: f.querySelector('.input-extra')?.value || null,
        otro: f.querySelector('.input-otro')?.value || null,
      }));
    },
  };
}

/**
 * Editor genérico de listas dinámicas (subtablas) para formularios.
 * columns: [{key, label, type: 'text'|'number'|'checkbox'|'select', options?}]
 */
function dynList(containerId, columns, initialItems = []) {
  const container = document.getElementById(containerId);

  function renderRow(item = {}) {
    const row = document.createElement('div');
    row.className = 'row g-1 align-items-center mb-1 dyn-row';
    columns.forEach(col => {
      const cell = document.createElement('div');
      cell.className = 'col';
      let input;
      if (col.type === 'checkbox') {
        input = document.createElement('input');
        input.type = 'checkbox';
        input.className = 'form-check-input';
        input.checked = !!item[col.key];
      } else if (col.type === 'select') {
        input = document.createElement('select');
        input.className = 'form-select form-select-sm';
        (col.options || []).forEach(opt => {
          const o = document.createElement('option');
          o.value = opt; o.textContent = opt;
          if (item[col.key] === opt) o.selected = true;
          input.appendChild(o);
        });
      } else {
        input = document.createElement('input');
        input.type = col.type === 'number' ? 'number' : 'text';
        input.className = 'form-control form-control-sm';
        input.value = item[col.key] ?? '';
      }
      input.dataset.key = col.key;
      input.placeholder = col.label;
      cell.appendChild(input);
      row.appendChild(cell);
    });
    const delCell = document.createElement('div');
    delCell.className = 'col-auto';
    const delBtn = document.createElement('button');
    delBtn.type = 'button';
    delBtn.className = 'btn btn-sm btn-outline-danger';
    delBtn.innerHTML = '<i class="bi bi-trash"></i>';
    delBtn.onclick = () => row.remove();
    delCell.appendChild(delBtn);
    row.appendChild(delCell);
    container.appendChild(row);
  }

  container.innerHTML = '';
  initialItems.forEach(renderRow);

  return {
    addRow: () => renderRow({}),
    getValues: () => Array.from(container.querySelectorAll('.dyn-row')).map(row => {
      const obj = {};
      row.querySelectorAll('[data-key]').forEach(input => {
        const key = input.dataset.key;
        if (input.type === 'checkbox') obj[key] = input.checked;
        else if (input.type === 'number') obj[key] = input.value === '' ? null : parseInt(input.value);
        else obj[key] = input.value || null;
      });
      return obj;
    }),
  };
}
