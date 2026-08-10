/* ============================================================
   Input Stationary (IS) Dataflow — Simulation & Rendering
   
   Each PE(i,k) holds input A[i][k] stationary.
   Elements of B stream top→bottom. 
   Partial sums of C accumulate and stream left→right.
   
   At cycle t, PE(i,k) processes n = t − i − k:
     if 0 ≤ n < SIZE: psum_out = psum_in + A[i][k] × B[k][n]
   ============================================================ */

(function () {
  'use strict';

  // ─── STATE ─────────────────────────────────────────────────
  let A, B, C;
  let cycle;
  let maxCycle;
  let controller;
  let controlsUI;

  // ─── INIT ──────────────────────────────────────────────────
  function init(matA, matB) {
    A = matA || copyMatrix(DEFAULT_A);
    B = matB || copyMatrix(DEFAULT_B);
    C = matMul(A, B);
    maxCycle = 3 * (SIZE - 1);
    cycle = -1;

    createPEGrid('peGrid', SIZE, 'is');

    renderMatrixDisplay('matrixA', A, 'Matrix A (stationary)', 'a');
    renderMatrixDisplay('matrixB', B, 'Matrix B (streaming ↓)', 'b');

    const emptyC = Array.from({ length: SIZE }, () => Array(SIZE).fill(null));
    renderMatrixDisplay('matrixC', emptyC, 'Matrix C (streaming →)', 'c');

    buildQueues();
    render();
  }

  // ─── INPUT QUEUES & OUTPUT AREA ─────────────────────────────
  function buildQueues() {
    // Left aQueue shows "Inputs A Preloaded" label set in HTML — no clearing needed

    // Top queue: B values entering each column, staggered
    const topContainer = clearEl('bQueue');
    for (let k = 0; k < SIZE; k++) {
      const queueCol = el('div', { className: 'queue-column' });
      const items = [];
      for (let s = 0; s < k; s++) items.push(null);
      for (let n = 0; n < SIZE; n++) items.push(B[k][n]);
      
      for (let idx = items.length - 1; idx >= 0; idx--) {
        const cell = el('div', { className: 'queue-cell', id: `bq-${k}-${idx}` });
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

    // Right side output area
    const rightContainer = clearEl('cOutput');
    // Alignment styles matching PE grid padding & gaps
    rightContainer.style.paddingTop = '12px';
    rightContainer.style.gap = '4px';
    
    for (let i = 0; i < SIZE; i++) {
        const cell = el('div', { className: 'output-cell', id: `cout-${i}` }, '');
        cell.style.height = '110px';
        cell.style.width = '60px';
        rightContainer.appendChild(cell);
    }
  }

  function updateQueueHighlights() {
    for (let k = 0; k < SIZE; k++) {
      const items = [];
      for (let s = 0; s < k; s++) items.push(null);
      for (let n = 0; n < SIZE; n++) items.push(B[k][n]);

      for (let idx = 0; idx < items.length; idx++) {
        const cell = $(`bq-${k}-${idx}`);
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
    return cycle < maxCycle;
  }

  function stepBack() {
    if (cycle < 0) return;
    cycle--;
  }

  function goToEnd() {
    while (cycle < maxCycle) {
      cycle++;
    }
    render();
  }

  function reset() {
    if (controller) controller.stop();
    cycle = -1;
    render();
  }

  // ─── RENDER ────────────────────────────────────────────────
  function render() {
    for (let i = 0; i < SIZE; i++) {
      for (let k = 0; k < SIZE; k++) {
        const n = cycle >= 0 ? cycle - i - k : -1;
        const isActive = n >= 0 && n < SIZE;
        const isDone = cycle >= i + k + (SIZE - 1);

        const rows = [];

        if (isActive) {
          const product = A[i][k] * B[k][n];
          let psum_out = 0;
          for (let l = 0; l <= k; l++) {
            psum_out += A[i][l] * B[l][n];
          }

          rows.push({ label: 'I:', value: A[i][k], className: 'row-i' });
          rows.push({ label: 'B↓', value: B[k][n], className: 'row-b' });
          rows.push({ label: '', value: `${A[i][k]}×${B[k][n]}=${product}`, className: 'row-op', dim: false });
          rows.push({ label: 'Σ→', value: psum_out, className: 'row-c' });
        } else {
          rows.push({ label: 'I:', value: A[i][k], className: 'row-i' });
          rows.push({ label: 'B↓', value: '–', className: 'row-b', dim: true });
          rows.push({ label: '', value: '', className: '' }); // spacer row
          rows.push({ label: 'Σ→', value: '–', className: 'row-c', dim: true });
        }

        updatePE(i, k, {
          rows: rows,
          active: isActive,
          done: isDone,
          badge: 'STATIONARY'
        });
      }
    }

    updateMatrixHighlights();
    updateCMatrix();
    updateCOutput();
    updateQueueHighlights();
    updateInfoPanel(Math.max(0, cycle), maxCycle, generateExplanation());

    if (controlsUI) {
      controlsUI.setDisabled(cycle < 0, cycle >= maxCycle);
      controlsUI.updatePlayBtn(controller?.isPlaying || false);
    }
  }

  function updateMatrixHighlights() {
    highlightMatrixCells('matrixA', [], 'highlight-a', true);
    highlightMatrixCells('matrixB', [], 'highlight-b', true);
    highlightMatrixCells('matrixC', [], 'highlight-c', true);

    if (cycle < 0) return;

    const aCells = [];
    const bCells = [];
    const cCells = [];

    for (let i = 0; i < SIZE; i++) {
      for (let k = 0; k < SIZE; k++) {
        const n = cycle - i - k;
        if (n >= 0 && n < SIZE) {
          aCells.push({ row: i, col: k });
          bCells.push({ row: k, col: n });
        }
      }
      for (let n = 0; n < SIZE; n++) {
        if (cycle >= i + (SIZE - 1) + n) {
          cCells.push({ row: i, col: n });
        }
      }
    }

    highlightMatrixCells('matrixA', aCells, 'highlight-a', false);
    highlightMatrixCells('matrixB', bCells, 'highlight-b', false);
    highlightMatrixCells('matrixC', cCells, 'highlight-c', false);
  }

  function updateCMatrix() {
    for (let i = 0; i < SIZE; i++) {
      for (let n = 0; n < SIZE; n++) {
        const completeCycle = i + (SIZE - 1) + n;
        if (cycle >= completeCycle) {
          updateMatrixCell('matrixC', i, n, C[i][n], 'computed');
        } else {
          updateMatrixCell('matrixC', i, n, null);
        }
      }
    }
  }

  function updateCOutput() {
    for (let i = 0; i < SIZE; i++) {
      const cell = $(`cout-${i}`);
      if (!cell) continue;
      
      const n = cycle - i - (SIZE - 1);
      if (n >= 0 && n < SIZE) {
        cell.textContent = C[i][n];
        cell.classList.add('has-value');
      } else if (n >= SIZE) {
        cell.textContent = C[i][SIZE-1];
        cell.classList.remove('has-value'); 
      } else {
        cell.textContent = '';
        cell.classList.remove('has-value');
      }
    }
  }

  // ─── EXPLANATION GENERATOR ─────────────────────────────────
  function generateExplanation() {
    if (cycle < 0) {
      return `<strong>Input Stationary (IS) Mode</strong><br>
        Elements of Matrix A are pre-loaded into the PEs and stay <em>stationary</em>. 
        Weights from Matrix B stream <span class="val-b">top → bottom</span>, and 
        partial sums for Matrix C accumulate and flow <span class="val-c">left → right</span>.<br><br>
        Press <strong>▶</strong> or <strong>Step</strong> to begin.`;
    }

    if (cycle > maxCycle) {
      return `<strong>Computation Complete!</strong><br>
        All ${SIZE}×${SIZE} = ${SIZE * SIZE} output values have been computed. 
        The partial sums have flowed through the array to form the final Matrix C.`;
    }

    const activePEs = [];
    for (let i = 0; i < SIZE; i++) {
      for (let k = 0; k < SIZE; k++) {
        const n = cycle - i - k;
        if (n >= 0 && n < SIZE) {
          activePEs.push({ i, k, n });
        }
      }
    }

    if (activePEs.length === 0) {
      return `<strong>Cycle ${cycle}</strong> — No PEs active this cycle (all computations complete).`;
    }

    let html = `<strong>Cycle ${cycle}</strong> — <span class="val-pe">${activePEs.length} PE${activePEs.length > 1 ? 's' : ''}</span> active<br><br>`;
    html += `PEs are computing partial sums for output columns n = cycle − i − k.<br>`;

    const showCount = Math.min(activePEs.length, 4);
    for (let idx = 0; idx < showCount; idx++) {
      const { i, k, n } = activePEs[idx];
      const aVal = A[i][k];
      const bVal = B[k][n];
      const product = aVal * bVal;
      html += `PE(${i},${k}): <span class="val-a">A[${i}][${k}]=${aVal}</span> × 
               <span class="val-b">B[${k}][${n}]=${bVal}</span> = ${product} → 
               <span class="val-c">add to Σ</span><br>`;
    }
    if (activePEs.length > showCount) {
      html += `<span style="color:var(--text-dim)">... and ${activePEs.length - showCount} more</span>`;
    }

    return html;
  }

  // ─── INITIALIZATION ────────────────────────────────────────
  document.addEventListener('DOMContentLoaded', () => {
    createMatrixEditor('matrixEditor', DEFAULT_A, DEFAULT_B, (newA, newB) => {
      if (controller) controller.stop();
      init(newA, newB);
    });

    init();

    controller = new AnimationController(
      () => {
        const hasMore = stepForward();
        return hasMore;
      },
      render,
      4
    );

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

    setupKeyboard({
      onSpace: () => { controller.toggle(); render(); },
      onRight: () => { controller.step(); },
      onLeft: () => { stepBack(); render(); },
      onR: () => { reset(); },
      onE: () => { goToEnd(); }
    });
  });

})();
