/* ============================================================
   Output Stationary (OS) Dataflow — Simulation & Rendering
   
   Each PE(i,j) accumulates C[i][j]. Elements of A stream 
   left→right; elements of B stream top→bottom. The output
   partial sum stays in each PE until complete.
   
   At cycle t, PE(i,j) processes k = t − i − j:
     if 0 ≤ k < K: accumulator += A[i][k] × B[k][j]
   ============================================================ */

(function () {
  'use strict';

  // ─── STATE ─────────────────────────────────────────────────
  let A, B, C;        // Matrices
  let cycle;           // Current cycle (0-indexed)
  let maxCycle;        // Maximum cycle index = 3*(SIZE-1)
  let accum;           // accum[i][j] = accumulated partial sum at PE(i,j)
  let history;         // history[t] = snapshot of accum at cycle t
  let controller;      // AnimationController
  let controlsUI;      // Controls UI handle

  // ─── INIT ──────────────────────────────────────────────────

  function init(matA, matB) {
    A = matA || copyMatrix(DEFAULT_A);
    B = matB || copyMatrix(DEFAULT_B);
    C = matMul(A, B);
    maxCycle = 3 * (SIZE - 1); // For 4×4: cycles 0..9 → max = 9
    cycle = -1; // -1 means "not started"
    accum = Array.from({ length: SIZE }, () => Array(SIZE).fill(0));
    history = [copyMatrix(accum)];

    // Create PE grid
    createPEGrid('peGrid', SIZE, 'os');

    // Render matrices
    renderMatrixDisplay('matrixA', A, 'Matrix A (streaming →)', 'a');
    renderMatrixDisplay('matrixB', B, 'Matrix B (streaming ↓)', 'b');

    // Render C with empty values
    const emptyC = Array.from({ length: SIZE }, () => Array(SIZE).fill(null));
    renderMatrixDisplay('matrixC', emptyC, 'Matrix C (output)', 'c');

    // Build input queue visualizations
    buildQueues();

    // Initial render
    render();
  }

  // ─── INPUT QUEUES ──────────────────────────────────────────

  function buildQueues() {
    // Left queue: A values entering each row, staggered
    // Row i starts with i empty slots, then A[i][0..K-1]
    const leftContainer = clearEl('aQueue');
    for (let i = 0; i < SIZE; i++) {
      const queueRow = el('div', { className: 'queue-row' });
      // Build in reverse order (rightmost enters first)
      const items = [];
      // Stagger: i empty slots
      for (let s = 0; s < i; s++) items.push(null);
      // Data: A[i][0..K-1]
      for (let k = 0; k < SIZE; k++) items.push(A[i][k]);
      // Render items (reversed so the first to enter is closest to the array)
      for (let idx = items.length - 1; idx >= 0; idx--) {
        const cell = el('div', { className: 'queue-cell', id: `aq-${i}-${idx}` });
        if (items[idx] === null) {
          cell.classList.add('empty');
        } else {
          cell.classList.add('val-a');
          cell.textContent = items[idx];
        }
        queueRow.appendChild(cell);
      }
      leftContainer.appendChild(queueRow);
    }

    // Top queue: B values entering each column, staggered
    const topContainer = clearEl('bQueue');
    for (let j = 0; j < SIZE; j++) {
      const queueCol = el('div', { className: 'queue-column' });
      const items = [];
      for (let s = 0; s < j; s++) items.push(null);
      for (let k = 0; k < SIZE; k++) items.push(B[k][j]);
      for (let idx = items.length - 1; idx >= 0; idx--) {
        const cell = el('div', { className: 'queue-cell', id: `bq-${j}-${idx}` });
        if (items[idx] === null) {
          cell.classList.add('empty');
        } else {
          cell.classList.add('val-b');
          cell.textContent = items[idx];
        }
        queueCol.appendChild(cell);
      }
      topContainer.appendChild(queueCol);
    }
  }

  // ─── QUEUE HIGHLIGHTING ────────────────────────────────────

  function updateQueueHighlights() {
    // Mark A queue items as used if they've entered the array
    for (let i = 0; i < SIZE; i++) {
      const items = [];
      for (let s = 0; s < i; s++) items.push(null);
      for (let k = 0; k < SIZE; k++) items.push(A[i][k]);

      for (let idx = 0; idx < items.length; idx++) {
        const cell = $(`aq-${i}-${idx}`);
        if (!cell) continue;
        cell.classList.remove('used', 'entering');
        if (items[idx] === null) continue;

        // This item enters the array at time = idx (since stagger is built in)
        // Item at index idx in items corresponds to time = idx
        const enterTime = idx; // time when this element enters the array
        if (cycle >= enterTime) {
          cell.classList.add('used');
        }
        if (cycle === enterTime) {
          cell.classList.add('entering');
        }
      }
    }

    // Mark B queue items as used
    for (let j = 0; j < SIZE; j++) {
      const items = [];
      for (let s = 0; s < j; s++) items.push(null);
      for (let k = 0; k < SIZE; k++) items.push(B[k][j]);

      for (let idx = 0; idx < items.length; idx++) {
        const cell = $(`bq-${j}-${idx}`);
        if (!cell) continue;
        cell.classList.remove('used', 'entering');
        if (items[idx] === null) continue;

        const enterTime = idx;
        if (cycle >= enterTime) {
          cell.classList.add('used');
        }
        if (cycle === enterTime) {
          cell.classList.add('entering');
        }
      }
    }
  }

  // ─── SIMULATION STEP ──────────────────────────────────────

  function stepForward() {
    if (cycle >= maxCycle) return false;
    cycle++;

    // At this cycle, for each PE(i,j), compute k = cycle - i - j
    for (let i = 0; i < SIZE; i++) {
      for (let j = 0; j < SIZE; j++) {
        const k = cycle - i - j;
        if (k >= 0 && k < SIZE) {
          accum[i][j] += A[i][k] * B[k][j];
        }
      }
    }

    // Save snapshot
    history[cycle + 1] = copyMatrix(accum);

    return cycle < maxCycle;
  }

  function stepBack() {
    if (cycle < 0) return;
    cycle--;
    if (cycle < 0) {
      // Reset accumulator
      accum = Array.from({ length: SIZE }, () => Array(SIZE).fill(0));
    } else {
      accum = copyMatrix(history[cycle + 1]);
    }
  }

  function goToEnd() {
    while (cycle < maxCycle) {
      stepForward();
    }
    render();
  }

  function reset() {
    if (controller) controller.stop();
    cycle = -1;
    accum = Array.from({ length: SIZE }, () => Array(SIZE).fill(0));
    history = [copyMatrix(accum)];
    render();
  }

  // ─── RENDER ────────────────────────────────────────────────

  function render() {
    // Update each PE
    for (let i = 0; i < SIZE; i++) {
      for (let j = 0; j < SIZE; j++) {
        const k = cycle >= 0 ? cycle - i - j : -1;
        const isActive = k >= 0 && k < SIZE;
        const isDone = (i + j + SIZE - 1) <= cycle; // All K values processed

        const rows = [];

        // A value flowing through
        if (isActive) {
          rows.push({ label: 'A→', value: A[i][k], className: 'row-a' });
          rows.push({ label: 'B↓', value: B[k][j], className: 'row-b' });
          rows.push({ label: '', value: '', className: 'row-op', dim: false });

          const product = A[i][k] * B[k][j];
          rows[2].value = `${A[i][k]}×${B[k][j]}=${product}`;

          rows.push({ label: '', value: '', className: '' }); // spacer row
        } else {
          rows.push({ label: 'A→', value: '–', className: 'row-a', dim: true });
          rows.push({ label: 'B↓', value: '–', className: 'row-b', dim: true });
        }

        // Accumulated value (stationary output)
        rows.push({ label: 'C:', value: accum[i][j], className: 'row-c' });

        updatePE(i, j, {
          rows: rows,
          active: isActive,
          done: isDone,
          badge: null
        });
      }
    }

    // Update matrix highlights
    updateMatrixHighlights();

    // Update C matrix display
    updateCMatrix();

    // Update queue highlights
    updateQueueHighlights();

    // Update info panel
    updateInfoPanel(
      Math.max(0, cycle),
      maxCycle,
      generateExplanation()
    );

    // Update control buttons
    if (controlsUI) {
      controlsUI.setDisabled(cycle < 0, cycle >= maxCycle);
      controlsUI.updatePlayBtn(controller?.isPlaying || false);
    }
  }

  function updateMatrixHighlights() {
    // Clear all highlights
    highlightMatrixCells('matrixA', [], 'highlight-a', true);
    highlightMatrixCells('matrixB', [], 'highlight-b', true);
    highlightMatrixCells('matrixC', [], 'highlight-c', true);

    if (cycle < 0) return;

    // Highlight active A and B cells
    const aCells = [];
    const bCells = [];
    const cCells = [];

    for (let i = 0; i < SIZE; i++) {
      for (let j = 0; j < SIZE; j++) {
        const k = cycle - i - j;
        if (k >= 0 && k < SIZE) {
          aCells.push({ row: i, col: k });
          bCells.push({ row: k, col: j });
        }
        // Mark completed C cells
        if ((i + j + SIZE - 1) <= cycle) {
          cCells.push({ row: i, col: j });
        }
      }
    }

    highlightMatrixCells('matrixA', aCells, 'highlight-a', false);
    highlightMatrixCells('matrixB', bCells, 'highlight-b', false);
    highlightMatrixCells('matrixC', cCells, 'highlight-c', false);
  }

  function updateCMatrix() {
    for (let i = 0; i < SIZE; i++) {
      for (let j = 0; j < SIZE; j++) {
        const isDone = (i + j + SIZE - 1) <= cycle;
        if (isDone) {
          updateMatrixCell('matrixC', i, j, C[i][j], 'computed');
        } else if (accum[i][j] > 0 && cycle >= 0) {
          updateMatrixCell('matrixC', i, j, accum[i][j] + '…', '');
        } else {
          updateMatrixCell('matrixC', i, j, null);
        }
      }
    }
  }

  // ─── EXPLANATION GENERATOR ─────────────────────────────────

  function generateExplanation() {
    if (cycle < 0) {
      return `<strong>Output Stationary (OS) Mode</strong><br>
        Each PE(i,j) is dedicated to computing C[i][j]. The output value stays <em>stationary</em> inside the PE 
        while elements of A stream <span class="val-a">left → right</span> and 
        elements of B stream <span class="val-b">top → bottom</span>.<br><br>
        Press <strong>▶</strong> or <strong>Step</strong> to begin.`;
    }

    if (cycle > maxCycle) {
      return `<strong>Computation Complete!</strong><br>
        All ${SIZE}×${SIZE} = ${SIZE * SIZE} output values have been computed. 
        Each PE accumulated its final C value through ${SIZE} multiply-accumulate operations.`;
    }

    // Find active PEs
    const activePEs = [];
    for (let i = 0; i < SIZE; i++) {
      for (let j = 0; j < SIZE; j++) {
        const k = cycle - i - j;
        if (k >= 0 && k < SIZE) {
          activePEs.push({ i, j, k });
        }
      }
    }

    if (activePEs.length === 0) {
      return `<strong>Cycle ${cycle}</strong> — No PEs active this cycle (all computations complete).`;
    }

    let html = `<strong>Cycle ${cycle}</strong> — <span class="val-pe">${activePEs.length} PE${activePEs.length > 1 ? 's' : ''}</span> active<br><br>`;

    // Show diagonal wavefront info
    html += `The <em>diagonal wavefront</em> activates PEs where i + j = ${cycle} − k.<br>`;

    // Show first few active PE computations
    const showCount = Math.min(activePEs.length, 4);
    for (let idx = 0; idx < showCount; idx++) {
      const { i, j, k } = activePEs[idx];
      const aVal = A[i][k];
      const bVal = B[k][j];
      const product = aVal * bVal;
      html += `PE(${i},${j}): <span class="val-a">A[${i}][${k}]=${aVal}</span> × 
               <span class="val-b">B[${k}][${j}]=${bVal}</span> = ${product} → 
               <span class="val-c">C[${i}][${j}] += ${product}</span><br>`;
    }
    if (activePEs.length > showCount) {
      html += `<span style="color:var(--text-dim)">... and ${activePEs.length - showCount} more</span>`;
    }

    return html;
  }

  // ─── INITIALIZATION ────────────────────────────────────────

  document.addEventListener('DOMContentLoaded', () => {
    // Create matrix editor
    createMatrixEditor('matrixEditor', DEFAULT_A, DEFAULT_B, (newA, newB) => {
      if (controller) controller.stop();
      init(newA, newB);
    });

    // Initialize simulation
    init();

    // Create animation controller
    controller = new AnimationController(
      () => {
        const hasMore = stepForward();
        return hasMore;
      },
      render,
      4
    );

    // Setup controls
    controlsUI = setupControls('controls', {
      onReset: () => { reset(); },
      onStepBack: () => { stepBack(); render(); },
      onStep: () => { controller.step(); },
      onPlayPause: () => {
        controller.toggle();
        render();
      },
      onGoEnd: () => { goToEnd(); },
      onSpeedChange: (speed) => { controller.setSpeed(speed); }
    });

    // Keyboard shortcuts
    setupKeyboard({
      onSpace: () => { controller.toggle(); render(); },
      onRight: () => { controller.step(); },
      onLeft: () => { stepBack(); render(); },
      onR: () => { reset(); },
      onE: () => { goToEnd(); }
    });

    // Initial render
    render();
  });

})();
