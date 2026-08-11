/* ============================================================
   Broadcast-Based Input Stationary (IS) Dataflow
   
   Activation matrix A is pre-loaded into PEs: PE(i,k) holds activation A[i][k] stationary.
   At cycle n (0 ≤ n < 4) computing output column n of matrix C:
     - Weight element B[k][n] is column-broadcast vertically down column k.
     - Each PE(i,k) computes P[i][k] = A[i][k] × B[k][n].
     - Row reduction: Row i sums P[i][0..3] to produce C[i][n].
   ============================================================ */

(function () {
  'use strict';

  let A, B, C;
  let cycle;
  let maxCycle;
  let completedCols;
  let controller;
  let controlsUI;

  function init(matA, matB) {
    A = matA || copyMatrix(DEFAULT_A);
    B = matB || copyMatrix(DEFAULT_B);
    C = matMul(A, B);
    maxCycle = SIZE - 1; // 0..3 (4 cycles)
    cycle = -1;
    completedCols = Array(SIZE).fill(false);

    createPEGrid('peGrid', SIZE);
    renderMatrixDisplay('matrixA', A, 'Matrix A (stationary in PE)', 'a');
    renderMatrixDisplay('matrixB', B, 'Matrix B (col-broadcast ↓)', 'b');

    const emptyC = Array.from({ length: SIZE }, () => Array(SIZE).fill(null));
    renderMatrixDisplay('matrixC', emptyC, 'Matrix C (output col-by-col)', 'c');

    buildLeftBus('busLeft', SIZE, 'C'); // Left bus label shows row reduction sum
    buildTopBus('busTop', SIZE, 'B');
    render();
  }

  function stepForward() {
    if (cycle >= maxCycle) return false;
    cycle++;
    completedCols[cycle] = true;
    return cycle < maxCycle;
  }

  function stepBack() {
    if (cycle < 0) return;
    completedCols[cycle] = false;
    cycle--;
  }

  function goToEnd() {
    cycle = maxCycle;
    for (let c = 0; c <= maxCycle; c++) completedCols[c] = true;
    render();
  }

  function reset() {
    if (controller) controller.stop();
    cycle = -1;
    completedCols = Array(SIZE).fill(false);
    render();
  }

  function render() {
    const n = cycle; // Current output column n being computed
    const isActive = n >= 0 && n < SIZE;
    const isDone = n >= maxCycle;

    // Update left row buses (Showing row sum C[i][n])
    for (let i = 0; i < SIZE; i++) {
      if (isActive) {
        updateLeftBus(i, `C[${i}][${n}] = ${C[i][n]}`, true);
      } else {
        updateLeftBus(i, '–', false);
      }
    }

    // Update top column buses (Broadcasting B[k][n])
    for (let k = 0; k < SIZE; k++) {
      if (isActive) {
        updateTopBus(k, `B[${k}][${n}] = ${B[k][n]}`, true);
      } else {
        updateTopBus(k, '–', false);
      }
    }

    // Update PEs
    for (let i = 0; i < SIZE; i++) {
      for (let k = 0; k < SIZE; k++) {
        const rows = [
          { label: 'I:', value: A[i][k], className: 'row-i' } // Stationary activation
        ];

        if (isActive) {
          const act = A[i][k];
          const bVal = B[k][n];
          const prod = act * bVal;
          rows.push({ label: 'B↓', value: bVal, className: 'row-b' });
          rows.push({ label: '', value: `${act}×${bVal}=${prod}`, className: 'row-op' });
        } else {
          rows.push({ label: 'B↓', value: '–', className: 'row-b', dim: true });
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
    const n = cycle;

    // Highlight entire Matrix A (all PEs active with static activations)
    const aCells = [];
    for (let i = 0; i < SIZE; i++)
      for (let k = 0; k < SIZE; k++)
        aCells.push({ row: i, col: k });

    // Highlight column n of Matrix B (B[*][n])
    const bCells = [];
    for (let k = 0; k < SIZE; k++) bCells.push({ row: k, col: n });

    // Highlight completed columns of C
    const cCells = [];
    for (let i = 0; i < SIZE; i++) {
      for (let c = 0; c <= cycle; c++) cCells.push({ row: i, col: c });
    }

    highlightMatrixCells('matrixA', aCells, 'highlight-a', false);
    highlightMatrixCells('matrixB', bCells, 'highlight-b', false);
    highlightMatrixCells('matrixC', cCells, 'highlight-c', false);
  }

  function updateCMatrix() {
    for (let i = 0; i < SIZE; i++) {
      for (let c = 0; c < SIZE; c++) {
        if (c <= cycle) {
          updateMatrixCell('matrixC', i, c, C[i][c], 'computed');
        } else {
          updateMatrixCell('matrixC', i, c, null);
        }
      }
    }
  }

  function generateExplanation() {
    if (cycle < 0) {
      return `<strong>Input Stationary (IS) Broadcast Dataflow</strong><br>
        Elements of activation matrix A are pre-loaded in the PEs and stay <em>stationary</em>.<br>
        At cycle n (0 ≤ n < 4), column n of weight matrix B (<span class="val-b">B[:][n]</span>) is 
        <span class="val-bus">column-broadcast</span> down the array. 
        Each row sums its partial products via <span class="val-c">row reduction</span> to output complete column <span class="val-c">C[:][n]</span>.<br><br>
        Press <strong>▶</strong> or <strong>Step</strong> to run. Total cycles: <strong>${SIZE}</strong>!`;
    }

    if (cycle >= maxCycle) {
      return `<strong>Computation Complete!</strong><br>
        All 4 output columns of Matrix C computed in <strong>${SIZE} cycles</strong>. 
        Activations A remained 100% stationary inside the PEs, enabling input reuse across multiple weight sets!`;
    }

    const n = cycle;
    let html = `<strong>Cycle ${n}</strong> — Computing Output Column <span class="val-c">C[:][${n}]</span><br><br>`;
    html += `<span class="val-bus">Column Broadcast:</span> Column ${n} of weight matrix B (<span class="val-b">B[0..3][${n}]</span>) sent vertically.<br>`;
    html += `<span class="val-bus">Row Reduction:</span> Partial products $A[i][k] \\times B[k][${n}]$ summed across each row $i$.<br><br>`;

    for (let i = 0; i < SIZE; i++) {
      const terms = [];
      for (let k = 0; k < SIZE; k++) {
        terms.push(`${A[i][k]}×${B[k][n]}`);
      }
      html += `Row ${i}: <span class="val-c">C[${i}][${n}]</span> = ${terms.join(' + ')} = <strong>${C[i][n]}</strong><br>`;
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
