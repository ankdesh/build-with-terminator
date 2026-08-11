/* ============================================================
   Broadcast-Based Hardware Matrix Multiplication Tutorial
   Common JS Utilities (Matrix ops, PE Grid, Buses, Controls, Controller)
   ============================================================ */

// ─── CONSTANTS ───────────────────────────────────────────────
const SIZE = 4;

const DEFAULT_A = [
  [1, 2, 3, 0],
  [0, 1, 2, 3],
  [3, 0, 1, 2],
  [2, 3, 0, 1]
];

const DEFAULT_B = [
  [1, 0, 2, 1],
  [0, 2, 1, 0],
  [1, 1, 0, 2],
  [2, 0, 1, 1]
];

// ─── MATRIX UTILITIES ────────────────────────────────────────

function matMul(A, B) {
  const N = A.length;
  const C = Array.from({ length: N }, () => Array(N).fill(0));
  for (let i = 0; i < N; i++)
    for (let j = 0; j < N; j++)
      for (let k = 0; k < N; k++)
        C[i][j] += A[i][k] * B[k][j];
  return C;
}

function copyMatrix(M) { return M.map(r => [...r]); }

function randomMatrix(N, lo = 0, hi = 4) {
  return Array.from({ length: N }, () =>
    Array.from({ length: N }, () => Math.floor(Math.random() * (hi - lo + 1)) + lo));
}

// ─── DOM HELPERS ─────────────────────────────────────────────

function el(tag, attrs = {}, ...children) {
  const e = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs)) {
    if (k === 'className') e.className = v;
    else if (k === 'style' && typeof v === 'object') Object.assign(e.style, v);
    else if (k.startsWith('on')) e.addEventListener(k.slice(2).toLowerCase(), v);
    else e.setAttribute(k, v);
  }
  for (const c of children) {
    if (typeof c === 'string') e.appendChild(document.createTextNode(c));
    else if (c) e.appendChild(c);
  }
  return e;
}

function clearEl(id) {
  const c = typeof id === 'string' ? document.getElementById(id) : id;
  if (!c) return null;
  while (c.firstChild) c.removeChild(c.firstChild);
  return c;
}

function $(id) { return document.getElementById(id); }

// ─── MATRIX DISPLAY RENDERING ────────────────────────────────

function renderMatrixDisplay(containerId, matrix, label, colorClass) {
  const container = clearEl(containerId);
  if (!container) return;
  container.appendChild(el('div', { className: `matrix-label label-${colorClass}` }, label));

  const table = el('table', { className: `matrix-table mat-${colorClass}` });
  const tbody = el('tbody');
  for (let i = 0; i < matrix.length; i++) {
    const tr = el('tr');
    for (let j = 0; j < matrix[i].length; j++) {
      const td = el('td', { id: `${containerId}-cell-${i}-${j}` });
      td.textContent = matrix[i][j] !== null ? matrix[i][j] : '·';
      if (matrix[i][j] === null) td.classList.add('empty-cell');
      tr.appendChild(td);
    }
    tbody.appendChild(tr);
  }
  table.appendChild(tbody);
  container.appendChild(table);
}

function highlightMatrixCells(containerId, cells, highlightClass, clear = true) {
  const container = $(containerId);
  if (!container) return;
  if (clear) {
    container.querySelectorAll('.highlight-a, .highlight-b, .highlight-c, .computed')
      .forEach(td => td.classList.remove('highlight-a', 'highlight-b', 'highlight-c'));
  }
  for (const { row, col } of cells) {
    const c = $(`${containerId}-cell-${row}-${col}`);
    if (c) c.classList.add(highlightClass);
  }
}

function updateMatrixCell(containerId, row, col, value, addClass) {
  const c = $(`${containerId}-cell-${row}-${col}`);
  if (!c) return;
  c.textContent = value !== null && value !== undefined ? value : '·';
  c.classList.remove('empty-cell');
  if (addClass) c.classList.add(addClass);
  if (value === null || value === undefined) c.classList.add('empty-cell');
}

// ─── PE GRID ─────────────────────────────────────────────────

function createPEGrid(containerId, size) {
  const container = clearEl(containerId);
  if (!container) return [];
  container.classList.add(`size-${size}`);

  const cells = [];
  for (let i = 0; i < size; i++) {
    cells[i] = [];
    for (let j = 0; j < size; j++) {
      const pe = el('div', { className: 'pe-cell', id: `pe-${i}-${j}` });

      const header = el('div', { className: 'pe-header' });
      header.appendChild(el('span', { className: 'pe-coords' }, `PE(${i},${j})`));
      header.appendChild(el('span', { className: 'pe-status' }));
      pe.appendChild(header);
      pe.appendChild(el('div', { className: 'pe-divider' }));
      pe.appendChild(el('div', { className: 'pe-content', id: `pe-content-${i}-${j}` }));

      container.appendChild(pe);
      cells[i][j] = pe;
    }
  }
  return cells;
}

function updatePE(row, col, data) {
  const peCell = $(`pe-${row}-${col}`);
  const content = $(`pe-content-${row}-${col}`);
  if (!peCell || !content) return;

  peCell.classList.toggle('active', !!data.active);
  peCell.classList.toggle('done', !!data.done);

  // Check header badge
  const header = peCell.querySelector('.pe-header');
  let badge = header ? header.querySelector('.pe-stationary-badge') : null;
  if (data.badge) {
    if (!badge && header) {
      badge = el('span', { className: 'pe-stationary-badge' }, data.badge);
      header.insertBefore(badge, header.querySelector('.pe-status'));
    } else if (badge) {
      badge.textContent = data.badge;
    }
  } else if (badge) {
    badge.remove();
  }

  clearEl(content);
  for (const r of (data.rows || [])) {
    const rowEl = el('div', { className: `pe-row ${r.className || ''}` });
    if (r.label) rowEl.appendChild(el('span', { className: 'pe-label' }, r.label));
    rowEl.appendChild(el('span', { className: 'pe-value' },
      r.value !== null && r.value !== undefined ? String(r.value) : '–'));
    if (r.dim) rowEl.classList.add('dim');
    content.appendChild(rowEl);
  }
}

// ─── BROADCAST BUS LABELS ────────────────────────────────────

function buildLeftBus(containerId, size, labelPrefix = 'A') {
  const container = clearEl(containerId);
  if (!container) return;
  for (let i = 0; i < size; i++) {
    const label = el('div', {
      className: `bus-label bus-${labelPrefix.toLowerCase()}`,
      id: `bus-left-${i}`,
      style: { minHeight: '120px', display: 'flex', flexDirection: 'column', justifyContent: 'center' }
    });
    label.innerHTML = `<span class="bus-arrow">→</span><span id="bus-left-val-${i}">–</span>`;
    container.appendChild(label);
  }
}

function buildTopBus(containerId, size, labelPrefix = 'B') {
  const container = clearEl(containerId);
  if (!container) return;
  for (let j = 0; j < size; j++) {
    const label = el('div', {
      className: `bus-label bus-${labelPrefix.toLowerCase()}`,
      id: `bus-top-${j}`,
      style: { minWidth: '145px' }
    });
    label.innerHTML = `<span class="bus-arrow">↓</span><span id="bus-top-val-${j}">–</span>`;
    container.appendChild(label);
  }
}

function updateLeftBus(row, text, isActive) {
  const label = $(`bus-left-${row}`);
  const val = $(`bus-left-val-${row}`);
  if (label) label.classList.toggle('active', isActive);
  if (val) val.textContent = text !== null && text !== undefined ? String(text) : '–';
}

function updateTopBus(col, text, isActive) {
  const label = $(`bus-top-${col}`);
  const val = $(`bus-top-val-${col}`);
  if (label) label.classList.toggle('active', isActive);
  if (val) val.textContent = text !== null && text !== undefined ? String(text) : '–';
}

// ─── CONTROLS ────────────────────────────────────────────────

function setupControls(containerId, callbacks) {
  const container = clearEl(containerId);
  if (!container) return null;

  const btnReset     = el('button', { className: 'ctrl-btn', title: 'Reset (R)',         onClick: callbacks.onReset },     '⏮');
  const btnStepBack  = el('button', { className: 'ctrl-btn', title: 'Step Back (←)',     onClick: callbacks.onStepBack },  '◀');
  const btnPlayPause = el('button', { className: 'ctrl-btn primary', title: 'Play/Pause (Space)', onClick: callbacks.onPlayPause }, '▶');
  const btnStep      = el('button', { className: 'ctrl-btn', title: 'Step Forward (→)',  onClick: callbacks.onStep },      '▶|');
  const btnEnd       = el('button', { className: 'ctrl-btn', title: 'Go to End (E)',     onClick: callbacks.onGoEnd },     '⏭');

  container.append(btnReset, btnStepBack, btnPlayPause, btnStep, btnEnd);

  const speedDiv = el('div', { className: 'speed-control' });
  speedDiv.appendChild(el('span', { className: 'speed-label' }, 'Speed'));
  const slider = el('input', { className: 'speed-slider', type: 'range', min: '1', max: '10', value: '4' });
  slider.addEventListener('input', () => callbacks.onSpeedChange(parseInt(slider.value)));
  speedDiv.appendChild(slider);
  container.appendChild(speedDiv);

  if (container.parentElement && !container.parentElement.querySelector('.shortcuts-hint')) {
    const shortcuts = el('div', { className: 'shortcuts-hint' });
    shortcuts.innerHTML = '<kbd>Space</kbd> Play/Pause &nbsp; <kbd>→</kbd> Step &nbsp; <kbd>←</kbd> Back &nbsp; <kbd>R</kbd> Reset';
    container.parentElement.appendChild(shortcuts);
  }

  return {
    updatePlayBtn(playing) { btnPlayPause.textContent = playing ? '⏸' : '▶'; },
    setDisabled(atStart, atEnd) {
      btnReset.disabled = atStart;
      btnStepBack.disabled = atStart;
      btnEnd.disabled = atEnd;
      btnStep.disabled = atEnd;
    }
  };
}

// ─── ANIMATION CONTROLLER ────────────────────────────────────

class AnimationController {
  constructor(stepFn, renderFn, speed = 4) {
    this._stepFn = stepFn;
    this._renderFn = renderFn;
    this._speed = speed;
    this._playing = false;
    this._timer = null;
  }
  get isPlaying() { return this._playing; }
  _interval() { return 2200 - this._speed * 200; }
  setSpeed(s) { this._speed = s; if (this._playing) { this.pause(); this.play(); } }
  play()  { if (this._playing) return; this._playing = true; this._tick(); }
  pause() { this._playing = false; clearTimeout(this._timer); this._timer = null; }
  toggle(){ this._playing ? this.pause() : this.play(); }
  step()  { this.pause(); this._stepFn(); this._renderFn(); }
  stop()  { this.pause(); }
  _tick() {
    if (!this._playing) return;
    const more = this._stepFn();
    this._renderFn();
    if (more) this._timer = setTimeout(() => this._tick(), this._interval());
    else this._playing = false;
  }
}

// ─── INFO PANEL ──────────────────────────────────────────────

function updateInfoPanel(cycle, total, html) {
  const cur = $('currentCycle'), tot = $('totalCycles');
  const exp = $('stepExplanation'), bar = $('progressBar');
  if (cur) cur.textContent = cycle;
  if (tot) tot.textContent = `/ ${total}`;
  if (exp) exp.innerHTML = html;
  if (bar) bar.style.width = `${total > 0 ? (cycle / total) * 100 : 0}%`;
}

// ─── MATRIX EDITOR ───────────────────────────────────────────

function createMatrixEditor(containerId, matA, matB, onApply) {
  const container = clearEl(containerId);
  if (!container) return;
  const row = el('div', { className: 'matrix-input-row' });

  const makeTable = (mat, colorCls, label) => {
    const div = el('div', { className: 'matrix-container' });
    div.appendChild(el('div', { className: `matrix-label label-${colorCls}` }, label));
    const table = el('table', { className: 'matrix-input-table' });
    const body = el('tbody');
    const inputs = [];
    for (let i = 0; i < SIZE; i++) {
      inputs[i] = [];
      const tr = el('tr');
      for (let j = 0; j < SIZE; j++) {
        const inp = el('input', { type: 'number', className: `input-${colorCls}`, value: String(mat[i][j]) });
        inputs[i][j] = inp;
        tr.appendChild(el('td', {}, inp));
      }
      body.appendChild(tr);
    }
    table.appendChild(body);
    div.appendChild(table);
    return { div, inputs };
  };

  const aRes = makeTable(matA, 'a', 'Matrix A');
  const bRes = makeTable(matB, 'b', 'Matrix B');
  row.append(aRes.div, el('span', { className: 'matrix-operation' }, '×'), bRes.div);
  container.appendChild(row);

  const btnRow = el('div', { style: { display: 'flex', gap: '12px', marginTop: '12px' } });
  btnRow.appendChild(el('button', { className: 'btn-apply', onClick: () => {
    const nA = aRes.inputs.map(r => r.map(i => parseInt(i.value) || 0));
    const nB = bRes.inputs.map(r => r.map(i => parseInt(i.value) || 0));
    onApply(nA, nB);
  }}, '✓ Apply & Reset'));
  btnRow.appendChild(el('button', { className: 'btn-randomize', onClick: () => {
    const rA = randomMatrix(SIZE, 0, 4), rB = randomMatrix(SIZE, 0, 4);
    for (let i = 0; i < SIZE; i++) for (let j = 0; j < SIZE; j++) {
      aRes.inputs[i][j].value = rA[i][j];
      bRes.inputs[i][j].value = rB[i][j];
    }
  }}, '🎲 Randomize'));
  container.appendChild(btnRow);
}

// ─── KEYBOARD ────────────────────────────────────────────────

function setupKeyboard(cb) {
  document.addEventListener('keydown', e => {
    if (e.target.tagName === 'INPUT' || e.target.tagName === 'TEXTAREA') return;
    switch (e.code) {
      case 'Space':      e.preventDefault(); cb.onSpace?.(); break;
      case 'ArrowRight': e.preventDefault(); cb.onRight?.(); break;
      case 'ArrowLeft':  e.preventDefault(); cb.onLeft?.();  break;
      case 'KeyR':       e.preventDefault(); cb.onR?.();     break;
      case 'KeyE':       e.preventDefault(); cb.onE?.();     break;
    }
  });
}
