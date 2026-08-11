/* ============================================================
   Broadcast-Based Output Stationary (OS) Dataflow
   
   Each PE(i,j) accumulates output C[i][j] in its local register.
   At cycle k (0 ≤ k < 4):
     - Matrix A column k is row-broadcast: row i receives A[i][k]
     - Matrix B row k is column-broadcast: col j receives B[k][j]
     - All 16 PEs compute in parallel: C[i][j] += A[i][k] × B[k][j]
   ============================================================ */

(function () {
  'use strict';

  let A, B, C;
  let cycle;
  let maxCycle;
  let accum;
  let history;
  let controller;
  let controlsUI;

  function init(matA, matB) {
    A = matA || copyMatrix(DEFAULT_A);
    B = matB || copyMatrix(DEFAULT_B);
    C = matMul(A, B);
    maxCycle = SIZE - 1; // 0..3 (4 cycles)
    cycle = -1;
    accum = Array.from({ length: SIZE }, () => Array(SIZE).fill(0));
    history = [copyMatrix(accum)];

    createPEGrid('peGrid', SIZE);
    renderMatrixDisplay('matrixA', A, 'Matrix A (row-broadcast →)', 'a');
    renderMatrixDisplay('matrixB', B, 'Matrix B (col-broadcast ↓)', 'b');
    renderMatrixDisplay('matrixC',
      Array.from({ length: SIZE }, () => Array(SIZE).fill(null)),
      'Matrix C (output stationary)', 'c');

    buildLeftBus('busLeft', SIZE, 'A');
    buildTopBus('busTop', SIZE, 'B');
    render();
  }

  function stepForward() {
    if (cycle >= maxCycle) return false;
    cycle++;
    const k = cycle;
    for (let i = 0; i < SIZE; i++) {
      for (let j = 0; j < SIZE; j++) {
        accum[i][j] += A[i][k] * B[k][j];
      }
    }
    history.push(copyMatrix(accum));
    return cycle < maxCycle;
  }

  function stepBack() {
    if (cycle < 0) return;
    history.pop();
    cycle--;
    if (cycle >= 0) {
      accum = copyMatrix(history[history.length - 1]);
    } else {
      accum = Array.from({ length: SIZE }, () => Array(SIZE).fill(0));
    }
  }

  function goToEnd() {
    while (cycle < maxCycle) {
      cycle++;
      const k = cycle;
      for (let i = 0; i < SIZE; i++)
        for (let j = 0; j < SIZE; j++)
          accum[i][j] += A[i][k] * B[k][j];
      history.push(copyMatrix(accum));
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

  function render() {
    const k = cycle;
    const isActive = k >= 0 && k < SIZE;
    const isDone = k >= maxCycle;

    // Update buses
    for (let i = 0; i < SIZE; i++) {
      updateLeftBus(i, isActive ? `A[${i}][${k}] = ${A[i][k]}` : '–', isActive);
    }
    for (let j = 0; j < SIZE; j++) {
      updateTopBus(j, isActive ? `B[${k}][${j}] = ${B[k][j]}` : '–', isActive);
    }

    // Update PEs
    for (let i = 0; i < SIZE; i++) {
      for (let j = 0; j < SIZE; j++) {
        const currentAccum = cycle >= 0 ? history[Math.min(cycle + 1, history.length - 1)][i][j] : 0;
        const rows = [
          { label: 'C:', value: currentAccum, className: 'row-c' }
        ];

        if (isActive) {
          const aVal = A[i][k];
          const bVal = B[k][j];
          const product = aVal * bVal;
          rows.push({ label: 'A→', value: aVal, className: 'row-a' });
          rows.push({ label: 'B↓', value: bVal, className: 'row-b' });
          rows.push({ label: '', value: `${aVal}×${bVal}=${product}`, className: 'row-op' });
        } else {
          rows.push({ label: 'A→', value: '–', className: 'row-a', dim: true });
          rows.push({ label: 'B↓', value: '–', className: 'row-b', dim: true });
        }

        updatePE(i, j, {
          rows: rows,
          active: isActive,
          done: isDone
        });
      }
    }

    updateMatrixHighlights();
    updateCMatrix();
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
    const k = cycle;

    const aCells = [];
    for (let i = 0; i < SIZE; i++) aCells.push({ row: i, col: k });

    const bCells = [];
    for (let j = 0; j < SIZE; j++) bCells.push({ row: k, col: j });

    const cCells = [];
    if (cycle >= maxCycle) {
      for (let i = 0; i < SIZE; i++)
        for (let j = 0; j < SIZE; j++)
          cCells.push({ row: i, col: j });
    }

    highlightMatrixCells('matrixA', aCells, 'highlight-a', false);
    highlightMatrixCells('matrixB', bCells, 'highlight-b', false);
    highlightMatrixCells('matrixC', cCells, 'highlight-c', false);
  }

  function updateCMatrix() {
    for (let i = 0; i < SIZE; i++) {
      for (let j = 0; j < SIZE; j++) {
        if (cycle >= maxCycle) {
          updateMatrixCell('matrixC', i, j, C[i][j], 'computed');
        } else if (cycle >= 0) {
          const partial = history[cycle + 1][i][j];
          updateMatrixCell('matrixC', i, j, partial);
        } else {
          updateMatrixCell('matrixC', i, j, null);
        }
      }
    }
  }

  function generateExplanation() {
    if (cycle < 0) {
      return `<strong>Output Stationary (OS) Broadcast Dataflow</strong><br>
        Each PE(i,j) holds accumulator C[i][j] locally. 
        At each cycle k, <span class="val-a">column k of A</span> is <span class="val-bus">row-broadcast</span> 
        and <span class="val-b">row k of B</span> is <span class="val-bus">column-broadcast</span> 
        simultaneously to <strong>all 16 PEs</strong>.<br><br>
        Press <strong>▶</strong> or <strong>Step</strong> to run. Total cycles: <strong>${SIZE}</strong>!`;
    }

    if (cycle >= maxCycle) {
      return `<strong>Computation Complete!</strong><br>
        All ${SIZE}×${SIZE} = ${SIZE * SIZE} output elements computed in exactly <strong>${SIZE} cycles</strong> 
        (16 MACs per cycle). Matrix C accumulated in-place inside PEs without external write-backs during calculation.`;
    }

    const k = cycle;
    let html = `<strong>Cycle ${k}</strong> (k = ${k}) — <span class="val-pe">ALL 16 PEs active</span><br><br>`;
    html += `<span class="val-bus">Row Broadcast:</span> <span class="val-a">A[i][${k}]</span> sent horizontally to all PEs in row i.<br>`;
    html += `<span class="val-bus">Column Broadcast:</span> <span class="val-b">B[${k}][j]</span> sent vertically to all PEs in col j.<br><br>`;

    const samplePEs = [[0, 0], [0, 3], [3, 0], [3, 3]];
    for (const [i, j] of samplePEs) {
      const aVal = A[i][k];
      const bVal = B[k][j];
      const prod = aVal * bVal;
      const curSum = history[cycle + 1][i][j];
      html += `PE(${i},${j}): <span class="val-a">A[${i}][${k}]=${aVal}</span> × 
               <span class="val-b">B[${k}][${j}]=${bVal}</span> = ${prod} → 
               <span class="val-c">C[${i}][${j}] = ${curSum}</span><br>`;
    }
    return html;
  }

  document.addEventListener('DOMContentLoaded', () => {
    createMatrixEditor('matrixEditor', DEFAULT_A, DEFAULT_B, (nA, nB) => {
      if (controller) controller.stop();
      init(nA, nB);
    });

    init();

    controller = new AnimationController(() => stepForward(), render, 4);

    controlsUI = setupControls('controls', {
      onReset:      () => reset(),
      onStepBack:   () => { stepBack(); render(); },
      onStep:       () => controller.step(),
      onPlayPause:  () => { controller.toggle(); render(); },
      onGoEnd:      () => goToEnd(),
      onSpeedChange:(s) => controller.setSpeed(s)
    });

    setupKeyboard({
      onSpace: () => { controller.toggle(); render(); },
      onRight: () => controller.step(),
      onLeft:  () => { stepBack(); render(); },
      onR:     () => reset(),
      onE:     () => goToEnd()
    });
  });
})();
