/* ============================================================
   Systolic Array Tutorial — Common JavaScript Utilities
   Shared matrix operations, PE grid rendering, controls, etc.
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

/**
 * Multiply two NxN matrices A and B, returning C = A × B.
 */
function matMul(A, B) {
  const N = A.length;
  const C = Array.from({ length: N }, () => Array(N).fill(0));
  for (let i = 0; i < N; i++) {
    for (let j = 0; j < N; j++) {
      for (let k = 0; k < N; k++) {
        C[i][j] += A[i][k] * B[k][j];
      }
    }
  }
  return C;
}

/**
 * Deep-copy a 2D array.
 */
function copyMatrix(M) {
  return M.map(row => [...row]);
}

/**
 * Generate a random NxN matrix with values in [minVal, maxVal].
 */
function randomMatrix(N, minVal = 0, maxVal = 3) {
  return Array.from({ length: N }, () =>
    Array.from({ length: N }, () =>
      Math.floor(Math.random() * (maxVal - minVal + 1)) + minVal
    )
  );
}

// ─── DOM HELPERS ─────────────────────────────────────────────

function el(tag, attrs = {}, ...children) {
  const elem = document.createElement(tag);
  for (const [key, val] of Object.entries(attrs)) {
    if (key === 'className') elem.className = val;
    else if (key === 'style' && typeof val === 'object') Object.assign(elem.style, val);
    else if (key.startsWith('on')) elem.addEventListener(key.slice(2).toLowerCase(), val);
    else elem.setAttribute(key, val);
  }
  for (const child of children) {
    if (typeof child === 'string') elem.appendChild(document.createTextNode(child));
    else if (child) elem.appendChild(child);
  }
  return elem;
}

function clearEl(container) {
  if (typeof container === 'string') container = document.getElementById(container);
  while (container.firstChild) container.removeChild(container.firstChild);
  return container;
}

function $(id) { return document.getElementById(id); }

// ─── MATRIX DISPLAY RENDERING ────────────────────────────────

/**
 * Render a matrix as an HTML table inside a container.
 * @param {string} containerId - The container element ID.
 * @param {number[][]} matrix - The matrix data.
 * @param {string} label - Display label (e.g., "A", "B", "C").
 * @param {string} colorClass - CSS class for color theming ("a", "b", "c").
 */
function renderMatrixDisplay(containerId, matrix, label, colorClass) {
  const container = clearEl(containerId);

  const labelEl = el('div', { className: `matrix-label label-${colorClass}` }, label);
  container.appendChild(labelEl);

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

/**
 * Highlight specific cells in a matrix display.
 * @param {string} containerId
 * @param {Array<{row:number, col:number}>} cells
 * @param {string} highlightClass - e.g., "highlight-a", "highlight-b"
 * @param {boolean} clear - if true, clear all highlights first
 */
function highlightMatrixCells(containerId, cells, highlightClass, clear = true) {
  const container = typeof containerId === 'string' ? $(containerId) : containerId;
  if (!container) return;

  if (clear) {
    container.querySelectorAll('.highlight-a, .highlight-b, .highlight-c, .computed').forEach(td => {
      td.classList.remove('highlight-a', 'highlight-b', 'highlight-c');
    });
  }

  for (const { row, col } of cells) {
    const cellEl = $(`${containerId}-cell-${row}-${col}`);
    if (cellEl) cellEl.classList.add(highlightClass);
  }
}

/**
 * Update a single cell value in a matrix display.
 */
function updateMatrixCell(containerId, row, col, value, addClass) {
  const cellEl = $(`${containerId}-cell-${row}-${col}`);
  if (!cellEl) return;
  cellEl.textContent = value !== null && value !== undefined ? value : '·';
  cellEl.classList.remove('empty-cell');
  if (addClass) cellEl.classList.add(addClass);
  if (value === null || value === undefined) cellEl.classList.add('empty-cell');
}

// ─── PE GRID CREATION ────────────────────────────────────────

/**
 * Create the PE grid HTML structure.
 * @param {string} containerId
 * @param {number} size
 * @param {string} mode - "os", "ws", or "is"
 * @returns {HTMLElement[][]} - 2D array of PE cell elements
 */
function createPEGrid(containerId, size, mode) {
  const container = clearEl(containerId);
  container.classList.add(`size-${size}`);

  const peCells = [];

  for (let i = 0; i < size; i++) {
    peCells[i] = [];
    for (let j = 0; j < size; j++) {
      const peCell = el('div', {
        className: 'pe-cell',
        id: `pe-${i}-${j}`
      });

      // Header with coordinates and status indicator
      const header = el('div', { className: 'pe-header' });
      header.appendChild(el('span', { className: 'pe-coords' }, `(${i},${j})`));
      header.appendChild(el('span', { className: 'pe-status' }));
      peCell.appendChild(header);

      peCell.appendChild(el('div', { className: 'pe-divider' }));

      // Content rows — filled by mode-specific code via updatePE()
      const contentArea = el('div', { className: 'pe-content', id: `pe-content-${i}-${j}` });
      peCell.appendChild(contentArea);

      container.appendChild(peCell);
      peCells[i][j] = peCell;
    }
  }

  return peCells;
}

/**
 * Update a PE cell's display content.
 * @param {number} row
 * @param {number} col
 * @param {Object} data
 *   - rows: Array of {label, value, className} to display
 *   - active: boolean — is this PE computing this cycle?
 *   - done: boolean — has this PE finished all its work?
 *   - badge: string | null — e.g., "STATIONARY"
 */
function updatePE(row, col, data) {
  const peCell = $(`pe-${row}-${col}`);
  const content = $(`pe-content-${row}-${col}`);
  if (!peCell || !content) return;

  // Update active / done state
  peCell.classList.toggle('active', !!data.active);
  peCell.classList.toggle('done', !!data.done);

  // Clear and rebuild content rows
  clearEl(content);

  if (data.badge) {
    content.appendChild(el('span', { className: 'pe-stationary-badge' }, data.badge));
  }

  for (const row of (data.rows || [])) {
    const rowEl = el('div', { className: `pe-row ${row.className || ''}` });
    if (row.label) {
      rowEl.appendChild(el('span', { className: 'pe-label' }, row.label));
    }
    rowEl.appendChild(el('span', { className: 'pe-value' }, row.value !== null && row.value !== undefined ? String(row.value) : '–'));
    if (row.dim) rowEl.classList.add('dim');
    content.appendChild(rowEl);
  }
}

// ─── INPUT QUEUE RENDERING ───────────────────────────────────

/**
 * Render the left input queue (A values entering rows).
 * @param {string} containerId
 * @param {number[][]} queues - queues[i] is the values for row i
 * @param {number} cycle - current cycle (to determine which values are used)
 * @param {string} colorClass - "val-a" or "val-b"
 */
function renderLeftQueue(containerId, queues, cycle, colorClass) {
  const container = clearEl(containerId);

  for (let i = 0; i < queues.length; i++) {
    const queueRow = el('div', { className: 'queue-row' });
    const items = queues[i];

    for (let idx = 0; idx < items.length; idx++) {
      const cell = el('div', { className: 'queue-cell' });
      if (items[idx] === null) {
        cell.classList.add('empty');
        cell.textContent = '';
      } else {
        cell.classList.add(colorClass);
        cell.textContent = items[idx];
        // Mark used items (those that have already entered the array)
        if (idx >= items.length - cycle + i) {
          // Not exactly right — mode-specific logic should handle this
        }
      }
      queueRow.appendChild(cell);
    }

    container.appendChild(queueRow);
  }
}

/**
 * Render the top input queue (B values entering columns).
 */
function renderTopQueue(containerId, queues, cycle, colorClass) {
  const container = clearEl(containerId);

  for (let j = 0; j < queues.length; j++) {
    const queueCol = el('div', { className: 'queue-column' });
    const items = queues[j];

    for (let idx = 0; idx < items.length; idx++) {
      const cell = el('div', { className: 'queue-cell' });
      if (items[idx] === null) {
        cell.classList.add('empty');
        cell.textContent = '';
      } else {
        cell.classList.add(colorClass);
        cell.textContent = items[idx];
      }
      queueCol.appendChild(cell);
    }

    container.appendChild(queueCol);
  }
}

// ─── CONTROLS ────────────────────────────────────────────────

/**
 * Set up the control panel with play/pause, step, reset, speed.
 * @param {string} containerId
 * @param {Object} callbacks - { onReset, onStepBack, onStep, onPlayPause, onGoEnd, onSpeedChange }
 * @returns {Object} - { updatePlayBtn(isPlaying), disableEnd(bool) }
 */
function setupControls(containerId, callbacks) {
  const container = clearEl(containerId);

  const btnReset = el('button', { className: 'ctrl-btn', title: 'Reset (R)', onClick: callbacks.onReset }, '⏮');
  const btnStepBack = el('button', { className: 'ctrl-btn', title: 'Step Back (←)', onClick: callbacks.onStepBack }, '◀');
  const btnPlayPause = el('button', { className: 'ctrl-btn primary', title: 'Play/Pause (Space)', onClick: callbacks.onPlayPause }, '▶');
  const btnStep = el('button', { className: 'ctrl-btn', title: 'Step Forward (→)', onClick: callbacks.onStep }, '▶▶');
  const btnEnd = el('button', { className: 'ctrl-btn', title: 'Go to End (E)', onClick: callbacks.onGoEnd }, '⏭');

  // Give unique text to differentiate step button
  btnStep.innerHTML = '▶|';

  container.appendChild(btnReset);
  container.appendChild(btnStepBack);
  container.appendChild(btnPlayPause);
  container.appendChild(btnStep);
  container.appendChild(btnEnd);

  // Speed control
  const speedDiv = el('div', { className: 'speed-control' });
  speedDiv.appendChild(el('span', { className: 'speed-label' }, 'Speed'));
  const slider = el('input', {
    className: 'speed-slider',
    type: 'range',
    min: '1',
    max: '10',
    value: '4'
  });
  slider.addEventListener('input', () => callbacks.onSpeedChange(parseInt(slider.value)));
  speedDiv.appendChild(slider);
  container.appendChild(speedDiv);

  // Shortcuts hint
  const shortcuts = el('div', { className: 'shortcuts-hint' });
  shortcuts.innerHTML = '<kbd>Space</kbd> Play/Pause &nbsp; <kbd>→</kbd> Step &nbsp; <kbd>←</kbd> Back &nbsp; <kbd>R</kbd> Reset';
  // Append after controls section, not inside the controls div
  container.parentElement.appendChild(shortcuts);

  return {
    updatePlayBtn(isPlaying) {
      btnPlayPause.textContent = isPlaying ? '⏸' : '▶';
    },
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
  /**
   * @param {Function} stepFn - Called to advance one cycle. Returns true if more cycles remain.
   * @param {Function} renderFn - Called after each step to update the display.
   * @param {number} initialSpeed - 1 (slow) to 10 (fast)
   */
  constructor(stepFn, renderFn, initialSpeed = 4) {
    this._stepFn = stepFn;
    this._renderFn = renderFn;
    this._speed = initialSpeed;
    this._playing = false;
    this._timerId = null;
  }

  get isPlaying() { return this._playing; }

  _interval() {
    // Speed 1 = 2000ms, Speed 10 = 200ms (linear interpolation)
    return 2200 - (this._speed * 200);
  }

  setSpeed(s) {
    this._speed = s;
    if (this._playing) {
      this.pause();
      this.play();
    }
  }

  play() {
    if (this._playing) return;
    this._playing = true;
    this._tick();
  }

  pause() {
    this._playing = false;
    if (this._timerId) {
      clearTimeout(this._timerId);
      this._timerId = null;
    }
  }

  toggle() {
    if (this._playing) this.pause();
    else this.play();
  }

  _tick() {
    if (!this._playing) return;
    const hasMore = this._stepFn();
    this._renderFn();
    if (hasMore) {
      this._timerId = setTimeout(() => this._tick(), this._interval());
    } else {
      this._playing = false;
    }
  }

  step() {
    this.pause();
    this._stepFn();
    this._renderFn();
  }

  stop() {
    this.pause();
  }
}

// ─── INFO PANEL UPDATE ───────────────────────────────────────

function updateInfoPanel(cycle, totalCycles, explanationHTML) {
  const currentEl = $('currentCycle');
  const totalEl = $('totalCycles');
  const explanationEl = $('stepExplanation');
  const progressBar = $('progressBar');

  if (currentEl) currentEl.textContent = cycle;
  if (totalEl) totalEl.textContent = `/ ${totalCycles}`;
  if (explanationEl) explanationEl.innerHTML = explanationHTML;
  if (progressBar) {
    const pct = totalCycles > 0 ? (cycle / totalCycles) * 100 : 0;
    progressBar.style.width = `${pct}%`;
  }
}

// ─── MATRIX INPUT EDITOR ─────────────────────────────────────

/**
 * Create editable matrix inputs.
 * @param {string} containerId
 * @param {number[][]} matA
 * @param {number[][]} matB
 * @param {Function} onApply - Called with (newA, newB)
 */
function createMatrixEditor(containerId, matA, matB, onApply) {
  const container = clearEl(containerId);

  const row = el('div', { className: 'matrix-input-row' });

  // Matrix A input
  const aDiv = el('div', { className: 'matrix-container' });
  aDiv.appendChild(el('div', { className: 'matrix-label label-a' }, 'Matrix A'));
  const aTable = el('table', { className: 'matrix-input-table' });
  const aBody = el('tbody');
  const aInputs = [];
  for (let i = 0; i < SIZE; i++) {
    aInputs[i] = [];
    const tr = el('tr');
    for (let j = 0; j < SIZE; j++) {
      const inp = el('input', {
        type: 'number',
        className: 'input-a',
        value: String(matA[i][j]),
      });
      aInputs[i][j] = inp;
      tr.appendChild(el('td', {}, inp));
    }
    aBody.appendChild(tr);
  }
  aTable.appendChild(aBody);
  aDiv.appendChild(aTable);
  row.appendChild(aDiv);

  row.appendChild(el('span', { className: 'matrix-operation' }, '×'));

  // Matrix B input
  const bDiv = el('div', { className: 'matrix-container' });
  bDiv.appendChild(el('div', { className: 'matrix-label label-b' }, 'Matrix B'));
  const bTable = el('table', { className: 'matrix-input-table' });
  const bBody = el('tbody');
  const bInputs = [];
  for (let i = 0; i < SIZE; i++) {
    bInputs[i] = [];
    const tr = el('tr');
    for (let j = 0; j < SIZE; j++) {
      const inp = el('input', {
        type: 'number',
        className: 'input-b',
        value: String(matB[i][j]),
      });
      bInputs[i][j] = inp;
      tr.appendChild(el('td', {}, inp));
    }
    bBody.appendChild(tr);
  }
  bTable.appendChild(bBody);
  bDiv.appendChild(bTable);
  row.appendChild(bDiv);

  container.appendChild(row);

  // Buttons row
  const btnRow = el('div', { style: { display: 'flex', gap: '12px', marginTop: '12px' } });

  const btnApply = el('button', { className: 'btn-apply', onClick: () => {
    const newA = aInputs.map(row => row.map(inp => parseInt(inp.value) || 0));
    const newB = bInputs.map(row => row.map(inp => parseInt(inp.value) || 0));
    onApply(newA, newB);
  }}, '✓ Apply & Reset');

  const btnRandom = el('button', { className: 'btn-randomize', onClick: () => {
    const rA = randomMatrix(SIZE, 0, 4);
    const rB = randomMatrix(SIZE, 0, 4);
    for (let i = 0; i < SIZE; i++) {
      for (let j = 0; j < SIZE; j++) {
        aInputs[i][j].value = rA[i][j];
        bInputs[i][j].value = rB[i][j];
      }
    }
  }}, '🎲 Randomize');

  btnRow.appendChild(btnApply);
  btnRow.appendChild(btnRandom);
  container.appendChild(btnRow);
}

// ─── KEYBOARD SHORTCUTS ──────────────────────────────────────

/**
 * Set up global keyboard shortcuts for the tutorial.
 * @param {Object} callbacks - { onSpace, onRight, onLeft, onR, onE }
 */
function setupKeyboard(callbacks) {
  document.addEventListener('keydown', (e) => {
    // Don't trigger when typing in an input
    if (e.target.tagName === 'INPUT' || e.target.tagName === 'TEXTAREA') return;

    switch (e.code) {
      case 'Space':
        e.preventDefault();
        callbacks.onSpace?.();
        break;
      case 'ArrowRight':
        e.preventDefault();
        callbacks.onRight?.();
        break;
      case 'ArrowLeft':
        e.preventDefault();
        callbacks.onLeft?.();
        break;
      case 'KeyR':
        e.preventDefault();
        callbacks.onR?.();
        break;
      case 'KeyE':
        e.preventDefault();
        callbacks.onE?.();
        break;
    }
  });
}
