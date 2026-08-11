/* ============================================================
   Broadcast-Based Weight Stationary (WS) Dataflow
   
   Weight matrix B is pre-loaded into PEs: PE(i,j) holds weight B[i][j] stationary.
   At cycle m (0 ≤ m < 4) computing output row m of matrix C:
     - Input element A[m][i] is row-broadcast horizontally across row i.
     - Each PE(i,j) computes P[i][j] = A[m][i] × B[i][j].
     - Column reduction: Column j sums P[0..3][j] to produce C[m][j].
   ============================================================ */

(function () {
  'use strict';

  let A, B, C;
  let cycle;
  let maxCycle;
  let completedRows;
  let controller;
  let controlsUI;

  function init(matA, matB) {
    A = matA || copyMatrix(DEFAULT_A);
    B = matB || copyMatrix(DEFAULT_B);
    C = matMul(A, B);
    maxCycle = SIZE - 1; // 0..3 (4 cycles)
    cycle = -1;
    completedRows = Array(SIZE).fill(false);

    createPEGrid('peGrid', SIZE);
    renderMatrixDisplay('matrixA', A, 'Matrix A (row-broadcast →)', 'a');
    renderMatrixDisplay('matrixB', B, 'Matrix B (stationary in PE)', 'b');

    const emptyC = Array.from({ length: SIZE }, () => Array(SIZE).fill(null));
    renderMatrixDisplay('matrixC', emptyC, 'Matrix C (output row-by-row)', 'c');

    buildLeftBus('busLeft', SIZE, 'A');
    buildTopBus('busTop', SIZE, 'C'); // Top bus label shows column reduction sum
    render();
  }

  function stepForward() {
    if (cycle >= maxCycle) return false;
    cycle++;
    completedRows[cycle] = true;
    return cycle < maxCycle;
  }

  function stepBack() {
    if (cycle < 0) return;
    completedRows[cycle] = false;
    cycle--;
  }

  function goToEnd() {
    cycle = maxCycle;
    for (let i = 0; i <= maxCycle; i++) completedRows[i] = true;
    render();
  }

  function reset() {
    if (controller) controller.stop();
    cycle = -1;
    completedRows = Array(SIZE).fill(false);
    render();
  }

  function render() {
    const m = cycle; // Current output row m being computed
    const isActive = m >= 0 && m < SIZE;
    const isDone = m >= maxCycle;

    // Update left row buses (Broadcasting A[m][i])
    for (let i = 0; i < SIZE; i++) {
      if (isActive) {
        updateLeftBus(i, `A[${m}][${i}] = ${A[m][i]}`, true);
      } else {
        updateLeftBus(i, '–', false);
      }
    }

    // Update top column buses (Showing column sum C[m][j])
    for (let j = 0; j < SIZE; j++) {
      if (isActive) {
        updateTopBus(j, `C[${m}][${j}] = ${C[m][j]}`, true);
      } else {
        updateTopBus(j, '–', false);
      }
    }

    // Update PEs
    for (let i = 0; i < SIZE; i++) {
      for (let j = 0; j < SIZE; j++) {
        const rows = [
          { label: 'W:', value: B[i][j], className: 'row-w' } // Stationary weight
        ];

        if (isActive) {
          const aVal = A[m][i];
          const weight = B[i][j];
          const prod = aVal * weight;
          rows.push({ label: 'A→', value: aVal, className: 'row-a' });
          rows.push({ label: '', value: `${aVal}×${weight}=${prod}`, className: 'row-op' });
        } else {
          rows.push({ label: 'A→', value: '–', className: 'row-a', dim: true });
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
    const m = cycle;

    // Highlight row m of Matrix A (A[m][*])
    const aCells = [];
    for (let i = 0; i < SIZE; i++) aCells.push({ row: m, col: i });

    // Highlight entire Matrix B (all PEs active with static weights)
    const bCells = [];
    for (let i = 0; i < SIZE; i++)
      for (let j = 0; j < SIZE; j++)
        bCells.push({ row: i, col: j });

    // Highlight completed rows of C
    const cCells = [];
    for (let r = 0; r <= cycle; r++) {
      for (let j = 0; j < SIZE; j++) cCells.push({ row: r, col: j });
    }

    highlightMatrixCells('matrixA', aCells, 'highlight-a', false);
    highlightMatrixCells('matrixB', bCells, 'highlight-b', false);
    highlightMatrixCells('matrixC', cCells, 'highlight-c', false);
  }

  function updateCMatrix() {
    for (let r = 0; r < SIZE; r++) {
      for (let j = 0; j < SIZE; j++) {
        if (r <= cycle) {
          updateMatrixCell('matrixC', r, j, C[r][j], 'computed');
        } else {
          updateMatrixCell('matrixC', r, j, null);
        }
      }
    }
  }

  function generateExplanation() {
    if (cycle < 0) {
      return `<strong>Weight Stationary (WS) Broadcast Dataflow</strong><br>
        Elements of weight matrix B are pre-loaded in the PEs and stay <em>stationary</em>.<br>
        At cycle m (0 ≤ m < 4), row m of input matrix A (<span class="val-a">A[m][:]</span>) is 
        <span class="val-bus">row-broadcast</span> across the array. 
        Each column sums its partial products via <span class="val-c">column reduction</span> to output complete row <span class="val-c">C[m][:]</span>.<br><br>
        Press <strong>▶</strong> or <strong>Step</strong> to run. Total cycles: <strong>${SIZE}</strong>!`;
    }

    if (cycle >= maxCycle) {
      return `<strong>Computation Complete!</strong><br>
        All 4 output rows of Matrix C computed in <strong>${SIZE} cycles</strong>. 
        Weights B remained 100% stationary inside the PEs, eliminating weight reload overhead. Perfect for Neural Network inference!`;
    }

    const m = cycle;
    let html = `<strong>Cycle ${m}</strong> — Computing Output Row <span class="val-c">C[${m}][:]</span><br><br>`;
    html += `<span class="val-bus">Row Broadcast:</span> Row ${m} of input matrix A (<span class="val-a">A[${m}][0..3]</span>) sent horizontally.<br>`;
    html += `<span class="val-bus">Column Reduction:</span> Partial products $A[${m}][i] \\times B[i][j]$ summed down each column $j$.<br><br>`;

    for (let j = 0; j < SIZE; j++) {
      const terms = [];
      for (let i = 0; i < SIZE; i++) {
        terms.push(`${A[m][i]}×${B[i][j]}`);
      }
      html += `Col ${j}: <span class="val-c">C[${m}][${j}]</span> = ${terms.join(' + ')} = <strong>${C[m][j]}</strong><br>`;
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
