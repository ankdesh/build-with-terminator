/* ============================================================
   Weight Stationary (WS) Dataflow — Simulation & Rendering
   
   Each PE(i,j) holds B[i][j] stationary.
   Elements of A stream left→right.
   Partial sums of C stream top→bottom.
   
   At cycle t, PE(i,j) processes output row m = t − i − j:
     if 0 ≤ m < K: psum_out = psum_in + A[m][i] × B[i][j]
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

    createPEGrid('peGrid', SIZE, 'ws');

    renderMatrixDisplay('matrixA', A, 'Matrix A (streaming →)', 'a');
    renderMatrixDisplay('matrixB', B, 'Matrix B (stationary)', 'b');

    const emptyC = Array.from({ length: SIZE }, () => Array(SIZE).fill(null));
    renderMatrixDisplay('matrixC', emptyC, 'Matrix C (streaming ↓)', 'c');

    buildQueues();
    render();
  }

  // ─── INPUT QUEUES ──────────────────────────────────────────
  function buildQueues() {
    const leftContainer = clearEl('aQueue');
    for (let i = 0; i < SIZE; i++) {
      const queueRow = el('div', { className: 'queue-row' });
      const items = [];
      for (let s = 0; s < i; s++) items.push(null);
      for (let m = 0; m < SIZE; m++) items.push(A[m][i]);
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

    const cContainer = clearEl('cQueue');
    for (let j = 0; j < SIZE; j++) {
      const cell = el('div', { className: 'output-cell', id: `cq-${j}` });
      cContainer.appendChild(cell);
    }
  }

  function updateQueueHighlights() {
    for (let i = 0; i < SIZE; i++) {
      const items = [];
      for (let s = 0; s < i; s++) items.push(null);
      for (let m = 0; m < SIZE; m++) items.push(A[m][i]);

      for (let idx = 0; idx < items.length; idx++) {
        const cell = $(`aq-${i}-${idx}`);
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
    cycle = maxCycle;
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
      for (let j = 0; j < SIZE; j++) {
        const m = cycle >= 0 ? cycle - i - j : -1;
        const isActive = m >= 0 && m < SIZE;
        
        // A PE is 'done' when it has processed all its inputs.
        // For PE(i,j), it processes m = 0..SIZE-1. The last m is SIZE-1, at cycle t = SIZE-1 + i + j.
        const isDone = cycle >= (SIZE - 1 + i + j);

        const rows = [];
        
        // B value is stationary
        rows.push({ label: 'W:', value: B[i][j], className: 'row-w' });
        
        if (isActive) {
          rows.push({ label: 'A→', value: A[m][i], className: 'row-a' });
          rows.push({ label: '', value: '', className: 'row-op', dim: false });
          const product = A[m][i] * B[i][j];
          rows[2].value = `${A[m][i]}×${B[i][j]}=${product}`;
          
          let psum = 0;
          for (let k = 0; k <= i; k++) {
            psum += A[m][k] * B[k][j];
          }
          rows.push({ label: 'Σ↓', value: psum, className: 'row-ps' });
        } else {
          rows.push({ label: 'A→', value: '–', className: 'row-a', dim: true });
          rows.push({ label: 'Σ↓', value: '–', className: 'row-ps', dim: true });
        }

        updatePE(i, j, {
          rows: rows,
          active: isActive,
          done: isDone,
          badge: 'STATIONARY'
        });
      }
    }

    updateMatrixHighlights();
    updateCMatrixAndQueue();
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
      for (let j = 0; j < SIZE; j++) {
        const m = cycle - i - j;
        if (m >= 0 && m < SIZE) {
          aCells.push({ row: m, col: i });
          bCells.push({ row: i, col: j });
        }
      }
    }
    
    for (let m = 0; m < SIZE; m++) {
      for (let j = 0; j < SIZE; j++) {
        if (cycle >= m + SIZE - 1 + j) {
          cCells.push({ row: m, col: j });
        }
      }
    }

    highlightMatrixCells('matrixA', aCells, 'highlight-a', false);
    highlightMatrixCells('matrixB', bCells, 'highlight-b', false);
    highlightMatrixCells('matrixC', cCells, 'highlight-c', false);
  }

  function updateCMatrixAndQueue() {
    for (let j = 0; j < SIZE; j++) {
      const cell = $(`cq-${j}`);
      if (cell) {
        cell.textContent = '';
        cell.classList.remove('has-value');
      }
    }

    for (let m = 0; m < SIZE; m++) {
      for (let j = 0; j < SIZE; j++) {
        const isComplete = cycle >= m + SIZE - 1 + j;
        if (isComplete) {
          updateMatrixCell('matrixC', m, j, C[m][j], 'computed');
          
          const doneCycle = m + SIZE - 1 + j;
          // Output C[m][j] flows out. Show it at the bottom for a couple of cycles.
          if (cycle - doneCycle >= 0 && cycle - doneCycle < SIZE) {
             const cell = $(`cq-${j}`);
             if (cell) {
               cell.textContent = C[m][j];
               cell.classList.add('has-value');
             }
          }
        } else {
          // You could show partial sum here if needed, but in WS partial sums are streaming
          // and not bound to one static C element until they pop out. We can show nothing until complete.
          updateMatrixCell('matrixC', m, j, null);
        }
      }
    }
  }

  function generateExplanation() {
    if (cycle < 0) {
      return `<strong>Weight Stationary (WS) Mode</strong><br>
        Each PE(i,j) holds weight B[i][j] <em>stationary</em>. 
        Elements of A stream <span class="val-a">left → right</span> and 
        partial sums of C stream <span class="val-c">top → bottom</span>.<br><br>
        Press <strong>▶</strong> or <strong>Step</strong> to begin.`;
    }

    if (cycle > maxCycle) {
      return `<strong>Computation Complete!</strong><br>
        All ${SIZE}×${SIZE} = ${SIZE * SIZE} output values have been computed.`;
    }

    const activePEs = [];
    for (let i = 0; i < SIZE; i++) {
      for (let j = 0; j < SIZE; j++) {
        const m = cycle - i - j;
        if (m >= 0 && m < SIZE) {
          activePEs.push({ i, j, m });
        }
      }
    }

    if (activePEs.length === 0) {
      return `<strong>Cycle ${cycle}</strong> — No PEs active this cycle.`;
    }

    let html = `<strong>Cycle ${cycle}</strong> — <span class="val-pe">${activePEs.length} PE${activePEs.length > 1 ? 's' : ''}</span> active<br><br>`;
    html += `The <em>diagonal wavefront</em> processes output row m = ${cycle} − i − j.<br>`;

    const showCount = Math.min(activePEs.length, 4);
    for (let idx = 0; idx < showCount; idx++) {
      const { i, j, m } = activePEs[idx];
      const aVal = A[m][i];
      const bVal = B[i][j];
      const product = aVal * bVal;
      html += `PE(${i},${j}): <span class="val-a">A[${m}][${i}]=${aVal}</span> × 
               <span class="val-w">B[${i}][${j}]=${bVal}</span> = ${product} → 
               <span class="val-c">psum += ${product}</span><br>`;
    }
    if (activePEs.length > showCount) {
      html += `<span style="color:var(--text-dim)">... and ${activePEs.length - showCount} more</span>`;
    }

    return html;
  }

  document.addEventListener('DOMContentLoaded', () => {
    createMatrixEditor('matrixEditor', DEFAULT_A, DEFAULT_B, (newA, newB) => {
      if (controller) controller.stop();
      init(newA, newB);
    });
    init();
    controller = new AnimationController(() => stepForward(), render, 4);
    controlsUI = setupControls('controls', {
      onReset: () => { reset(); },
      onStepBack: () => { stepBack(); render(); },
      onStep: () => { controller.step(); },
      onPlayPause: () => { controller.toggle(); render(); },
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
