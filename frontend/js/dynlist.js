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
