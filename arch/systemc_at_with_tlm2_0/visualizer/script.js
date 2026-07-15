// State Variables
let currentExample = "example0";
let currentScenario = "sc1";
let viewMode = "gantt"; // "gantt" or "wave"
let simulationTime = 0;
let maxSimulationTime = 12;
let playbackInterval = null;
let isPlaying = false;

// Parsed Data Structures
let transactions = [];
let waveforms = {};
let fifoSizeTimeline = [];
let switchStateTimeline = [];

// Initialize App
document.addEventListener("DOMContentLoaded", () => {
    setupEventListeners();
    loadExample(currentExample);
});

// Setup DOM Event Listeners
function setupEventListeners() {
    const exampleSelect = document.getElementById("example-select");
    const scenarioSelect = document.getElementById("scenario-select");

    exampleSelect.addEventListener("change", (e) => {
        loadExample(e.target.value);
    });

    scenarioSelect.addEventListener("change", (e) => {
        loadScenario(e.target.value);
    });

    // View Toggles
    const btnViewGantt = document.getElementById("btn-view-gantt");
    const btnViewWave = document.getElementById("btn-view-wave");

    btnViewGantt.addEventListener("click", () => {
        viewMode = "gantt";
        btnViewGantt.classList.add("active");
        btnViewWave.classList.remove("active");
        renderTimeline();
    });

    btnViewWave.addEventListener("click", () => {
        viewMode = "wave";
        btnViewWave.classList.add("active");
        btnViewGantt.classList.remove("active");
        renderTimeline();
    });

    const btnPreloaded = document.getElementById("btn-preloaded");
    const btnCustom = document.getElementById("btn-custom");
    const customContainer = document.getElementById("custom-trace-container");

    btnPreloaded.addEventListener("click", () => {
        btnPreloaded.classList.add("active");
        btnCustom.classList.remove("active");
        customContainer.classList.add("hidden");
        loadScenario(currentScenario);
    });

    btnCustom.addEventListener("click", () => {
        btnCustom.classList.add("active");
        btnPreloaded.classList.remove("active");
        customContainer.classList.remove("hidden");
    });

    document.getElementById("btn-parse-custom").addEventListener("click", () => {
        const customText = document.getElementById("custom-trace").value;
        parseTrace(customText, {});
    });

    // Playback Controls
    document.getElementById("btn-play-pause").addEventListener("click", togglePlayback);
    document.getElementById("btn-step-prev").addEventListener("click", () => stepPlayback(-1));
    document.getElementById("btn-step-next").addEventListener("click", () => stepPlayback(1));
    document.getElementById("btn-reset").addEventListener("click", resetPlayback);

    document.getElementById("time-slider").addEventListener("input", (e) => {
        setSimulationTime(parseInt(e.target.value));
    });
}

// Load Example
function loadExample(exampleKey) {
    currentExample = exampleKey;
    
    const hwSimple = document.getElementById("hardware-simple-pipeline");
    const hwAlu = document.getElementById("hardware-pipelined-alu");
    const hwFifo = document.getElementById("hardware-fifo-backpressure");
    const hwSwitch = document.getElementById("hardware-switch-arbitration");

    hwSimple.classList.add("hidden");
    hwAlu.classList.add("hidden");
    hwFifo.classList.add("hidden");
    hwSwitch.classList.add("hidden");

    if (exampleKey === "example0") {
        hwSimple.classList.remove("hidden");
        maxSimulationTime = 12; // 12 cycles (120ns)
    } else if (exampleKey === "example1") {
        hwAlu.classList.remove("hidden");
        maxSimulationTime = 20; // 20 cycles (200ns)
    } else if (exampleKey === "example2") {
        hwFifo.classList.remove("hidden");
        maxSimulationTime = 30; // 30 cycles (300ns)
    } else if (exampleKey === "example3") {
        hwSwitch.classList.remove("hidden");
        maxSimulationTime = 20; // 20 cycles (200ns)
    }

    // Configure Slider Limit
    const timeSlider = document.getElementById("time-slider");
    timeSlider.max = maxSimulationTime;
    document.getElementById("slider-max-label").textContent = `${maxSimulationTime} cy`;

    // Load Default Scenario (sc1)
    const scenarioSelect = document.getElementById("scenario-select");
    scenarioSelect.value = "sc1";
    loadScenario("sc1");
}

// Load Scenario
function loadScenario(scenarioKey) {
    currentScenario = scenarioKey;
    const scenarioData = ALL_SCENARIOS_DATA[currentExample][scenarioKey];
    
    document.getElementById("custom-trace").value = scenarioData.log;
    
    // Update header context text
    const titleEl = document.getElementById("example-title");
    const descEl = document.getElementById("example-desc");
    
    if (currentExample === "example0") {
        titleEl.textContent = `Example 0: Simple Pipeline Stage - Scenario ${scenarioKey === "sc1" ? "1 (Single)" : scenarioKey === "sc2" ? "2 (Back-to-Back)" : "3 (Alternate)"}`;
        descEl.textContent = scenarioKey === "sc1"
            ? "1 transaction is sent at cycle 1 and progresses through the 3-cycle pipelined stage B to C."
            : scenarioKey === "sc2"
            ? "5 transactions are launched back-to-back on consecutive cycles, filling B's pipeline."
            : "3 transactions are sent on alternate cycles (cycles 1, 3, 5) showing transient queue fills.";
    } else if (currentExample === "example1") {
        titleEl.textContent = `Example 1: Pipelined ALU - Scenario ${scenarioKey === "sc1" ? "1 (Mixed)" : scenarioKey === "sc2" ? "2 (Retire Stall)" : "3 (Back-to-Back)"}`;
        descEl.textContent = scenarioKey === "sc1" 
            ? "3-cycle Adder and 4-cycle Multiplier with In-Order Retirement."
            : scenarioKey === "sc2"
            ? "Demonstrates fast 1-cycle Adders stalled from retiring due to a preceding 4-cycle Multiplier."
            : "Demonstrates continuous back-to-back ADD operations maintaining full pipeline depth.";
    } else if (currentExample === "example2") {
        titleEl.textContent = `Example 2: FIFO Backpressure - Scenario ${scenarioKey === "sc1" ? "1 (Full Stall)" : scenarioKey === "sc2" ? "2 (Empty Stall)" : "3 (Bursty)"}`;
        descEl.textContent = scenarioKey === "sc1"
            ? "Fast Producer fills up the capacity-4 FIFO, causing a producer stall until the Consumer drains it."
            : scenarioKey === "sc2"
            ? "Slow Producer causes the fast Consumer to stall repeatedly on the empty FIFO."
            : "Both blocks produce bursty traffic, showing transient stalls and occupancy changes.";
    } else if (currentExample === "example3") {
        titleEl.textContent = `Example 3: Switch Arbitration - Scenario ${scenarioKey === "sc1" ? "1 (Contention)" : scenarioKey === "sc2" ? "2 (Staggered)" : "3 (Unbalanced)"}`;
        descEl.textContent = scenarioKey === "sc1"
            ? "4 Initiators query the Switch at the exact same cycle, demonstrating Round-Robin serialization."
            : scenarioKey === "sc2"
            ? "Staggered transaction requests avoid switch contention entirely, eliminating latency stalls."
            : "Initiator 0 floods the switch, while others make sparse requests, showing fair resource division.";
    }

    resetPlayback();
    parseTrace(scenarioData.log, scenarioData.waveforms);
}

// Playback Management
function togglePlayback() {
    const btn = document.getElementById("btn-play-pause");
    if (isPlaying) {
        clearInterval(playbackInterval);
        btn.textContent = "▶ Play";
        isPlaying = false;
    } else {
        btn.textContent = "⏸ Pause";
        isPlaying = true;
        playbackInterval = setInterval(() => {
            if (simulationTime >= maxSimulationTime) {
                togglePlayback(); // Pause
                return;
            }
            setSimulationTime(simulationTime + 1);
        }, 150);
    }
}

function stepPlayback(stepSize) {
    if (isPlaying) togglePlayback();
    let newTime = simulationTime + stepSize;
    if (newTime < 0) newTime = 0;
    if (newTime > maxSimulationTime) newTime = maxSimulationTime;
    setSimulationTime(newTime);
}

// Reset Playback
function resetPlayback() {
    if (isPlaying) togglePlayback();
    setSimulationTime(0);
}

function setSimulationTime(time) {
    simulationTime = time;
    document.getElementById("time-slider").value = time;
    document.getElementById("current-sim-time").textContent = `${time} cycles`;
    updateTimelineCursor();
    updateHardwareAnimator();
}

// Parse Trace Log text for Gantt Chart & Timeline Markers
function parseTrace(traceText, rawWaveforms) {
    transactions = [];
    fifoSizeTimeline = [{ time: 0, size: 0 }];
    switchStateTimeline = [{ time: 0, state: "FREE", rr: 0 }];
    waveforms = rawWaveforms;

    const lines = traceText.split('\n');
    const timeRegex = /\[CYCLE:\s*(\d+)\]/;
    
    // Core Handshake Parser
    let tempTxMap = {};

    lines.forEach(line => {
        const timeMatch = line.match(timeRegex);
        if (!timeMatch) return;
        const timeVal = parseInt(timeMatch[1]);

        if (currentExample === "example0") {
            const ex0InitReq = /Sending BEGIN_REQ for Tx (\d+) with value:/;
            const ex0InitEndReq = /Received backward call for Tx (\d+) with phase: END_REQ/;
            const ex0Comp = /\[TARGET_C\] Tx (\d+) completed/;

            let match;
            if ((match = line.match(ex0InitReq))) {
                const txId = match[1];
                const key = `tx_${txId}`;
                tempTxMap[key] = {
                    key: key,
                    id: `Tx ${txId}`,
                    op: "WRITE",
                    data: "A ➡ B ➡ C",
                    start: timeVal,
                    reqEnd: null,
                    respStart: null,
                    end: null,
                    stall: 0,
                    dest: "Component C"
                };
            }
            else if ((match = line.match(ex0InitEndReq))) {
                const txId = match[1];
                const key = `tx_${txId}`;
                if (tempTxMap[key]) {
                    tempTxMap[key].reqEnd = timeVal;
                }
            }
            else if (line.includes("Direct update: phase END_REQ")) {
                const pending = Object.values(tempTxMap).find(t => t.start !== undefined && t.reqEnd === null);
                if (pending) {
                    pending.reqEnd = timeVal;
                }
            }
            else if ((match = line.match(ex0Comp))) {
                const txId = match[1];
                const key = `tx_${txId}`;
                if (tempTxMap[key]) {
                    tempTxMap[key].respStart = timeVal - 1;
                    tempTxMap[key].end = timeVal;
                }
            }
        }
        else if (currentExample === "example1") {
            const ex1InitReq = /Sending BEGIN_REQ for Tx (\d+) \((ADD|MUL) (\d+), (\d+)\)/;
            const ex1EndReq = /Received backward call for Tx (\d+) with phase: END_REQ/;
            const ex1Comp = /\[TARGET\] Tx (\d+) completed/;

            let match;
            if ((match = line.match(ex1InitReq))) {
                const opType = match[1];
                const op = match[2];
                const a = match[3];
                const b = match[4];
                
                const key = `${op}_${opType}_${timeVal}`;
                tempTxMap[key] = {
                    key: key,
                    id: `Tx ${tempTxMap[key] ? Object.keys(tempTxMap).length : transactions.length + 1}`,
                    op: op,
                    data: `${a}, ${b}`,
                    start: timeVal,
                    reqEnd: null,
                    respStart: null,
                    end: null,
                    stall: 0,
                    dest: "ALU",
                    op_type_num: opType
                };
                tempTxMap[`active_${opType}`] = key;
            }
            else if ((match = line.match(ex1EndReq))) {
                const opType = match[1];
                const key = tempTxMap[`active_${opType}`];
                if (key && tempTxMap[key]) {
                    tempTxMap[key].reqEnd = timeVal;
                }
            }
            else if (line.includes("Direct update: phase END_REQ")) {
                const pending = Object.values(tempTxMap).find(t => t.start !== undefined && t.reqEnd === null);
                if (pending) {
                    pending.reqEnd = timeVal;
                }
            }
            else if ((match = line.match(ex1Comp))) {
                const opType = match[1];
                // Find oldest active transaction of this opType that has not completed
                const matchTx = Object.values(tempTxMap)
                    .filter(t => t.op_type_num === opType && t.end === null)
                    .sort((a, b) => a.start - b.start)[0];
                if (matchTx) {
                    matchTx.respStart = timeVal - 1;
                    matchTx.end = timeVal;
                }
            }
        }
        else if (currentExample === "example2") {
            const ex2ProdReq = /Sending write BEGIN_REQ \(Tx (\d+)\) with value: (\d+)/;
            const ex2ProdEndReq = /Direct update: phase END_REQ for Tx (\d+)\./;
            const ex2ProdStall = /Stalling on Tx (\d+) due to backpressure\.\.\./;
            const ex2ProdEndReqStalled = /Received END_REQ for write transaction (\d+)/;
            const ex2Comp = /\[CONSUMER\] Completed processing value: (\d+)/;

            let match;
            if ((match = line.match(ex2ProdReq))) {
                const txId = match[1];
                const val = match[2];
                const key = `write_${txId}`;
                tempTxMap[key] = {
                    key: key,
                    id: `Tx ${txId}`,
                    op: "WRITE",
                    data: `val: ${val}`,
                    start: timeVal,
                    reqEnd: null,
                    respStart: null,
                    end: null,
                    stall: 0,
                    dest: "FIFO",
                    stalledAt: null
                };
            }
            else if ((match = line.match(ex2ProdEndReq))) {
                const txId = match[1];
                const key = `write_${txId}`;
                if (tempTxMap[key]) {
                    tempTxMap[key].reqEnd = timeVal;
                }
            }
            else if ((match = line.match(ex2ProdStall))) {
                const txId = match[1];
                const key = `write_${txId}`;
                if (tempTxMap[key]) {
                    tempTxMap[key].stalledAt = timeVal;
                }
            }
            else if ((match = line.match(ex2ProdEndReqStalled))) {
                const txId = match[1];
                const key = `write_${txId}`;
                if (tempTxMap[key]) {
                    tempTxMap[key].reqEnd = timeVal;
                    if (tempTxMap[key].stalledAt !== null) {
                        tempTxMap[key].stall = timeVal - tempTxMap[key].stalledAt;
                    }
                }
            }
            else if (line.includes("Pushed value:") || line.includes("Popped value:") || line.includes("STALL RELEASE")) {
                // Parse FIFO size dynamically from output logs
                const sizeMatch = line.match(/size:\s*(\d+)/) || line.match(/Size:\s*(\d+)/);
                if (sizeMatch) {
                    const size = parseInt(sizeMatch[1]);
                    fifoSizeTimeline.push({ time: timeVal, size: size });
                }
            }
            else if ((match = line.match(ex2Comp))) {
                const val = parseInt(match[1]);
                const txId = val % 100;
                const key = `write_${txId}`;
                if (tempTxMap[key]) {
                    tempTxMap[key].respStart = timeVal - 1;
                    tempTxMap[key].end = timeVal;
                }
            }
        }
        else if (currentExample === "example3") {
            const ex3InitReq = /\[INITIATOR_(\d+)\] Sending BEGIN_REQ to target (\d+)\./;
            const ex3SwitchGrant = /Arbiter GRANTED access to Initiator (\d+)/;
            const ex3InitEndReq = /\[INITIATOR_(\d+)\] Received END_REQ/;
            const ex3SwitchRelease = /Switch transmission complete \(freeing switch\)\./;
            const ex3Comp = /\[TARGET_(\d+)\] Transaction completed/;

            let match;
            if ((match = line.match(ex3InitReq))) {
                const initId = match[1];
                const dest = match[2];
                const key = `init_${initId}_${timeVal}`;
                tempTxMap[key] = {
                    key: key,
                    id: `IP ${initId}`,
                    op: "SEND",
                    data: `Node ${dest}`,
                    start: timeVal,
                    reqEnd: null,
                    respStart: null,
                    end: null,
                    stall: 0,
                    dest: `Node ${dest}`,
                    initId: initId
                };
                tempTxMap[`active_init_${initId}`] = key;
            }
            else if ((match = line.match(ex3SwitchGrant))) {
                const initId = match[1];
                const key = tempTxMap[`active_init_${initId}`];
                if (key && tempTxMap[key]) {
                    tempTxMap[key].stall = timeVal - tempTxMap[key].start;
                }
                switchStateTimeline.push({ time: timeVal, state: `BUSY (IP ${initId})`, rr: (parseInt(initId) + 1) % 4 });
            }
            else if ((match = line.match(ex3InitEndReq))) {
                const initId = match[1];
                const key = tempTxMap[`active_init_${initId}`];
                if (key && tempTxMap[key]) {
                    tempTxMap[key].reqEnd = timeVal;
                }
            }
            else if (line.match(ex3SwitchRelease)) {
                const lastRR = switchStateTimeline.length > 0 ? switchStateTimeline[switchStateTimeline.length - 1].rr : 0;
                switchStateTimeline.push({ time: timeVal, state: "FREE", rr: lastRR });
            }
            else if ((match = line.match(ex3Comp))) {
                const destId = match[1];
                // Find oldest active transaction going to this target destination node
                const matchTx = Object.values(tempTxMap)
                    .filter(t => t.dest === `Node ${destId}` && t.end === null)
                    .sort((a, b) => a.start - b.start)[0];
                if (matchTx) {
                    matchTx.respStart = timeVal - 1;
                    matchTx.end = timeVal;
                }
            }
        }
    });

    transactions = Object.values(tempTxMap).filter(t => t.start !== undefined);
    transactions.sort((a, b) => a.start - b.start);

    renderTimeline();
}

// Render Timeline panel (switches between Gantt and VCD Waveform)
function renderTimeline() {
    if (viewMode === "gantt") {
        renderGanttChart();
    } else {
        renderVCDWaveforms();
    }
    updateTimelineCursor();
    updateHardwareAnimator();
}

// Render Gantt Timeline Chart
function renderGanttChart() {
    const svg = document.getElementById("timeline-svg");
    svg.innerHTML = "";

    if (transactions.length === 0) return;

    const margin = { top: 40, right: 40, bottom: 40, left: 120 };
    const width = svg.clientWidth - margin.left - margin.right;
    const height = (transactions.length * 40) + 60;
    svg.setAttribute("height", height);

    const timeToX = (t) => margin.left + (t / maxSimulationTime) * width;
    const rowToY = (i) => margin.top + i * 40;

    // Draw Grid Lines & Labels
    for (let t = 0; t <= maxSimulationTime; t += 2) {
        const x = timeToX(t);
        
        const line = document.createElementNS("http://www.w3.org/2000/svg", "line");
        line.setAttribute("x1", x);
        line.setAttribute("y1", margin.top - 10);
        line.setAttribute("x2", x);
        line.setAttribute("y2", height - margin.bottom);
        line.setAttribute("stroke", "rgba(255, 255, 255, 0.05)");
        line.setAttribute("stroke-dasharray", "4");
        svg.appendChild(line);

        const text = document.createElementNS("http://www.w3.org/2000/svg", "text");
        text.setAttribute("x", x);
        text.setAttribute("y", height - 10);
        text.setAttribute("fill", "#64748b");
        text.setAttribute("font-size", "10px");
        text.setAttribute("text-anchor", "middle");
        text.textContent = `${t} cy`;
        svg.appendChild(text);
    }

    // Draw transactions
    transactions.forEach((tx, index) => {
        const y = rowToY(index);

        // Row Label
        const label = document.createElementNS("http://www.w3.org/2000/svg", "text");
        label.setAttribute("x", 10);
        label.setAttribute("y", y + 16);
        label.setAttribute("fill", "#f8fafc");
        label.setAttribute("font-weight", "600");
        label.setAttribute("font-size", "12px");
        label.textContent = `${tx.id} (${tx.op})`;
        svg.appendChild(label);

        const bgLine = document.createElementNS("http://www.w3.org/2000/svg", "line");
        bgLine.setAttribute("x1", margin.left);
        bgLine.setAttribute("y1", y + 12);
        bgLine.setAttribute("x2", margin.left + width);
        bgLine.setAttribute("y2", y + 12);
        bgLine.setAttribute("stroke", "rgba(255, 255, 255, 0.03)");
        svg.appendChild(bgLine);

        // Req phase
        const reqEnd = tx.reqEnd || tx.end || maxSimulationTime;
        const xReqStart = timeToX(tx.start);
        const wReq = timeToX(reqEnd) - xReqStart;

        if (wReq > 0) {
            const rect = document.createElementNS("http://www.w3.org/2000/svg", "rect");
            rect.setAttribute("x", xReqStart);
            rect.setAttribute("y", y);
            rect.setAttribute("width", wReq);
            rect.setAttribute("height", 24);
            rect.setAttribute("rx", 4);
            
            if (tx.stall > 0 && currentExample === "example3") {
                rect.setAttribute("fill", "url(#stall-hatch)");
                rect.setAttribute("class", "timeline-bar solid-stall");
            } else {
                rect.setAttribute("class", "timeline-bar hatched-req");
            }
            setupTooltip(rect, tx);
            svg.appendChild(rect);
        }

        // Active/Exec phase
        if (tx.reqEnd !== null) {
            const activeEnd = tx.respStart || tx.end || maxSimulationTime;
            const xActiveStart = timeToX(tx.reqEnd);
            const wActive = timeToX(activeEnd) - xActiveStart;

            if (wActive > 0) {
                const rect = document.createElementNS("http://www.w3.org/2000/svg", "rect");
                rect.setAttribute("x", xActiveStart);
                rect.setAttribute("y", y);
                rect.setAttribute("width", wActive);
                rect.setAttribute("height", 24);
                rect.setAttribute("rx", 4);

                if (tx.stall > 0 && tx.stalledAt !== null && tx.reqEnd > tx.stalledAt) {
                    const xStallStart = timeToX(tx.stalledAt);
                    const wStall = timeToX(tx.reqEnd) - xStallStart;
                    
                    const stallRect = document.createElementNS("http://www.w3.org/2000/svg", "rect");
                    stallRect.setAttribute("x", xStallStart);
                    stallRect.setAttribute("y", y);
                    stallRect.setAttribute("width", wStall);
                    stallRect.setAttribute("height", 24);
                    stallRect.setAttribute("rx", 4);
                    stallRect.setAttribute("class", "timeline-bar solid-stall");
                    setupTooltip(stallRect, tx);
                    svg.appendChild(stallRect);

                    rect.setAttribute("x", xActiveStart);
                    rect.setAttribute("width", wActive);
                    rect.setAttribute("class", "timeline-bar solid-active");
                } else {
                    rect.setAttribute("class", "timeline-bar solid-active");
                }
                setupTooltip(rect, tx);
                svg.appendChild(rect);
            }
        }

        // Resp phase
        if (tx.respStart !== null && tx.end !== null) {
            const xRespStart = timeToX(tx.respStart);
            const wResp = timeToX(tx.end) - xRespStart;

            if (wResp > 0) {
                const rect = document.createElementNS("http://www.w3.org/2000/svg", "rect");
                rect.setAttribute("x", xRespStart);
                rect.setAttribute("y", y);
                rect.setAttribute("width", wResp);
                rect.setAttribute("height", 24);
                rect.setAttribute("rx", 4);
                rect.setAttribute("class", "timeline-bar solid-resp");
                setupTooltip(rect, tx);
                svg.appendChild(rect);
            }
        }
    });

    appendDefsAndCursor(svg, margin.top, height - margin.bottom);
}

// Render VCD Timing Diagrams (Digital lines & hexagon buses)
function renderVCDWaveforms() {
    const svg = document.getElementById("timeline-svg");
    svg.innerHTML = "";

    if (!waveforms || Object.keys(waveforms).length === 0) {
        const text = document.createElementNS("http://www.w3.org/2000/svg", "text");
        text.setAttribute("x", svg.clientWidth / 2);
        text.setAttribute("y", 100);
        text.setAttribute("fill", "#64748b");
        text.setAttribute("text-anchor", "middle");
        text.textContent = "No VCD signal data available for this run.";
        svg.appendChild(text);
        return;
    }

    const signalKeys = Object.keys(waveforms).sort();
    const margin = { top: 40, right: 40, bottom: 40, left: 240 };
    const width = svg.clientWidth - margin.left - margin.right;
    const height = (signalKeys.length * 60) + 60;
    svg.setAttribute("height", height);

    const timeToX = (t) => margin.left + (t / maxSimulationTime) * width;
    const rowToY = (i) => margin.top + i * 60;

    // Draw Grid Lines
    for (let t = 0; t <= maxSimulationTime; t += 2) {
        const x = timeToX(t);
        
        const line = document.createElementNS("http://www.w3.org/2000/svg", "line");
        line.setAttribute("x1", x);
        line.setAttribute("y1", margin.top - 10);
        line.setAttribute("x2", x);
        line.setAttribute("y2", height - margin.bottom);
        line.setAttribute("stroke", "rgba(255, 255, 255, 0.05)");
        line.setAttribute("stroke-dasharray", "4");
        svg.appendChild(line);

        const text = document.createElementNS("http://www.w3.org/2000/svg", "text");
        text.setAttribute("x", x);
        text.setAttribute("y", height - 10);
        text.setAttribute("fill", "#64748b");
        text.setAttribute("font-size", "10px");
        text.setAttribute("text-anchor", "middle");
        text.textContent = `${t} cy`;
        svg.appendChild(text);
    }

    // Draw each signal waveform
    signalKeys.forEach((sigName, index) => {
        const y = rowToY(index);
        const y_mid = y + 20;
        const y_high = y + 5;
        const y_low = y + 35;

        // Signal Label
        const label = document.createElementNS("http://www.w3.org/2000/svg", "text");
        label.setAttribute("x", 10);
        label.setAttribute("y", y_mid + 4);
        label.setAttribute("class", "vcd-signal-label");
        label.textContent = sigName;
        svg.appendChild(label);

        // Divider Line
        const bgLine = document.createElementNS("http://www.w3.org/2000/svg", "line");
        bgLine.setAttribute("x1", margin.left);
        bgLine.setAttribute("y1", y + 45);
        bgLine.setAttribute("x2", margin.left + width);
        bgLine.setAttribute("y2", y + 45);
        bgLine.setAttribute("stroke", "rgba(255, 255, 255, 0.03)");
        svg.appendChild(bgLine);

        const points = waveforms[sigName];
        if (!points || points.length === 0) return;

        const isSingleBit = sigName.includes("occupied") || sigName.includes("stalled") || sigName.includes("busy");

        if (isSingleBit) {
            // Draw Single-Bit Square Wave
            let pathD = "";
            let prevX = timeToX(0);
            let prevY = (points[0][1] === 1) ? y_high : y_low;

            pathD += `M ${prevX} ${prevY}`;

            for (let i = 0; i < points.length; ++i) {
                const pTime = points[i][0];
                const pVal = points[i][1];
                const x = timeToX(pTime);
                const nextY = (pVal === 1) ? y_high : y_low;

                pathD += ` H ${x}`;
                pathD += ` V ${nextY}`;
                
                prevX = x;
                prevY = nextY;
            }

            pathD += ` H ${timeToX(maxSimulationTime)}`;

            const path = document.createElementNS("http://www.w3.org/2000/svg", "path");
            path.setAttribute("d", pathD);
            path.setAttribute("class", `vcd-wave-line ${sigName.includes("stalled") ? "stalled" : sigName.includes("occupied") ? "occupied" : ""}`);
            svg.appendChild(path);
        } 
        else {
            // Draw Multi-Bit Bus (Hexagon packets)
            for (let i = 0; i < points.length; ++i) {
                const tStart = points[i][0];
                const tEnd = (i + 1 < points.length) ? points[i + 1][0] : maxSimulationTime;
                
                if (tStart >= maxSimulationTime) break;
                
                const val = points[i][1];
                const xStart = timeToX(tStart);
                const xEnd = timeToX(Math.min(tEnd, maxSimulationTime));
                const w = xEnd - xStart;

                if (w <= 0) continue;

                let valLabel = String(val);
                if (sigName.includes("active_op")) {
                    valLabel = (val === 0) ? "IDLE" : (val === 1) ? "ADD" : (val === 2) ? "MUL" : "MIXED";
                } else if (sigName.includes("active_initiator")) {
                    valLabel = (val === 0) ? "NONE" : `IP ${val - 1}`;
                } else if (sigName.includes("retired_tx_id")) {
                    valLabel = (val === 0) ? "NONE" : `Tx ${val}`;
                } else if (sigName.includes("switch_rr_index")) {
                    valLabel = `RR: ${val}`;
                } else if (sigName.includes("_tx")) {
                    valLabel = (val === 0) ? "IDLE" : `Tx ${val - 1}`;
                }

                if (val === 0 || valLabel === "IDLE" || valLabel === "NONE") {
                    const flatLine = document.createElementNS("http://www.w3.org/2000/svg", "line");
                    flatLine.setAttribute("x1", xStart);
                    flatLine.setAttribute("y1", y_mid);
                    flatLine.setAttribute("x2", xEnd);
                    flatLine.setAttribute("y2", y_mid);
                    flatLine.setAttribute("stroke", "rgba(255, 255, 255, 0.15)");
                    flatLine.setAttribute("stroke-width", "1");
                    svg.appendChild(flatLine);
                    
                    if (w > 20) {
                        const txt = document.createElementNS("http://www.w3.org/2000/svg", "text");
                        txt.setAttribute("x", (xStart + xEnd) / 2);
                        txt.setAttribute("y", y_mid - 4);
                        txt.setAttribute("fill", "#64748b");
                        txt.setAttribute("font-size", "8px");
                        txt.setAttribute("text-anchor", "middle");
                        txt.textContent = valLabel;
                        svg.appendChild(txt);
                    }
                    continue;
                }

                const slope = Math.min(4, w / 2);
                const pointsStr = `
                    ${xStart},${y_mid} 
                    ${xStart + slope},${y_high} 
                    ${xEnd - slope},${y_high} 
                    ${xEnd},${y_mid} 
                    ${xEnd - slope},${y_low} 
                    ${xStart + slope},${y_low}
                `;

                const poly = document.createElementNS("http://www.w3.org/2000/svg", "polygon");
                poly.setAttribute("points", pointsStr);
                poly.setAttribute("class", "vcd-bus-polygon");
                svg.appendChild(poly);

                if (w > 12) {
                    const txt = document.createElementNS("http://www.w3.org/2000/svg", "text");
                    txt.setAttribute("x", (xStart + xEnd) / 2);
                    txt.setAttribute("y", y_mid + 4);
                    txt.setAttribute("class", "vcd-bus-text");
                    
                    let dispLabel = valLabel;
                    if (w < 40 && valLabel.length > 5) dispLabel = valLabel.slice(0, 3) + "..";
                    txt.textContent = dispLabel;
                    
                    svg.appendChild(txt);
                }
            }
        }
    });

    appendDefsAndCursor(svg, margin.top, height - margin.bottom);
}

// Utility to append patterns and play cursor
function appendDefsAndCursor(svg, yStart, yEnd) {
    const margin = { left: viewMode === "gantt" ? 120 : 240, right: 40 };
    const width = svg.clientWidth - margin.left - margin.right;
    
    const defs = document.createElementNS("http://www.w3.org/2000/svg", "defs");
    const stallPattern = document.createElementNS("http://www.w3.org/2000/svg", "pattern");
    stallPattern.setAttribute("id", "stall-hatch");
    stallPattern.setAttribute("width", "8");
    stallPattern.setAttribute("height", "8");
    stallPattern.setAttribute("patternTransform", "rotate(-45)");
    stallPattern.setAttribute("patternUnits", "userSpaceOnUse");
    
    const stallLine = document.createElementNS("http://www.w3.org/2000/svg", "line");
    stallLine.setAttribute("x1", "0");
    stallLine.setAttribute("y1", "0");
    stallLine.setAttribute("x2", "0");
    stallLine.setAttribute("y2", "8");
    stallLine.setAttribute("stroke", "var(--color-stall)");
    stallLine.setAttribute("stroke-width", "4");
    
    stallPattern.appendChild(stallLine);
    defs.appendChild(stallPattern);
    svg.appendChild(defs);

    const timeToX = (t) => margin.left + (t / maxSimulationTime) * width;
    
    const cursor = document.createElementNS("http://www.w3.org/2000/svg", "line");
    cursor.setAttribute("id", "time-cursor-line");
    cursor.setAttribute("x1", timeToX(simulationTime));
    cursor.setAttribute("y1", yStart - 10);
    cursor.setAttribute("x2", timeToX(simulationTime));
    cursor.setAttribute("y2", yEnd);
    cursor.setAttribute("stroke", "var(--text-highlight)");
    cursor.setAttribute("stroke-width", "2");
    svg.appendChild(cursor);
}

// Tooltip Inspector Bindings
function setupTooltip(element, tx) {
    element.addEventListener("mouseenter", () => {
        document.getElementById("inspector-placeholder").classList.add("hidden");
        const content = document.getElementById("inspector-content");
        content.classList.remove("hidden");

        document.getElementById("inspect-id").textContent = tx.id;
        document.getElementById("inspect-op").textContent = tx.op;
        document.getElementById("inspect-addr").textContent = tx.dest;
        document.getElementById("inspect-data").textContent = tx.data;
        document.getElementById("inspect-start").textContent = `${tx.start} cy`;
        document.getElementById("inspect-req-end").textContent = tx.reqEnd ? `${tx.reqEnd} cy` : "Incomplete";
        document.getElementById("inspect-resp-start").textContent = tx.respStart ? `${tx.respStart} cy` : "Incomplete";
        document.getElementById("inspect-end").textContent = tx.end ? `${tx.end} cy` : "Incomplete";
        
        const latency = tx.end ? `${tx.end - tx.start} cy` : "In-flight";
        document.getElementById("inspect-latency").textContent = latency;
        document.getElementById("inspect-stall").textContent = `${tx.stall} cy`;
    });
}

// Update cursor line position
function updateTimelineCursor() {
    const cursor = document.getElementById("time-cursor-line");
    if (!cursor) return;
    
    const svg = document.getElementById("timeline-svg");
    const margin = { left: viewMode === "gantt" ? 120 : 240, right: 40 };
    const width = svg.clientWidth - margin.left - margin.right;
    const x = margin.left + (simulationTime / maxSimulationTime) * width;
    
    cursor.setAttribute("x1", x);
    cursor.setAttribute("x2", x);
}

// Hardware Component Animator Logic (scenario-dependent)
function updateHardwareAnimator() {
    // ==================== EXAMPLE 0 SIMPLE PIPELINE ANIMATION ====================
    if (currentExample === "example0") {
        const compA = document.getElementById("hw-comp-a-status");
        const compC = document.getElementById("hw-comp-c-status");
        const slots = document.getElementById("pipe-pipeline-slots");

        const getWaveValue = (sigName, time) => {
            let val = 0;
            if (waveforms && waveforms[sigName]) {
                waveforms[sigName].forEach(p => {
                    if (p[0] <= time) val = p[1];
                });
            }
            return val;
        };

        const abReq = getWaveValue("top.pipeline_b.A_B_req_tx", simulationTime);
        const abResp = getWaveValue("top.pipeline_b.A_B_resp_tx", simulationTime);
        const bcReq = getWaveValue("top.pipeline_b.B_C_req_tx", simulationTime);
        const bcResp = getWaveValue("top.pipeline_b.B_C_resp_tx", simulationTime);

        let aStatus = "Idle";
        if (abReq > 0) aStatus = `Sending Tx ${abReq - 1}`;
        else if (abResp > 0) aStatus = `Completing Tx ${abResp - 1}`;
        compA.textContent = aStatus;
        compA.parentElement.classList.toggle("pulse", abReq > 0 || abResp > 0);

        slots.innerHTML = "";
        transactions.forEach(t => {
            if (t.reqEnd && t.respStart && simulationTime >= t.reqEnd && simulationTime < t.respStart) {
                const slot = document.createElement("div");
                slot.className = "pipeline-slot";
                slot.textContent = t.id;
                slots.appendChild(slot);
            }
        });

        let cStatus = "Idle";
        if (bcReq > 0) cStatus = `Receiving Tx ${bcReq - 1}`;
        else if (bcResp > 0) cStatus = `Responding Tx ${bcResp - 1}`;
        compC.textContent = cStatus;
        compC.parentElement.classList.toggle("pulse", bcReq > 0 || bcResp > 0);
    }

    // ==================== EXAMPLE 1 ALU ANIMATION ====================
    else if (currentExample === "example1") {
        const cpuContent = document.getElementById("hw-cpu-content");
        const inputRegVal = document.querySelector("#alu-stage-input .stage-val");
        const activeSlots = document.getElementById("alu-pipeline-slots");

        let cpuActive = false;
        let cpuTarget = "";
        transactions.forEach(t => {
            if (simulationTime >= t.start && simulationTime < t.reqEnd) {
                cpuActive = true;
                cpuTarget = `${t.op} (Tx ${t.id})`;
            }
        });
        cpuContent.textContent = cpuActive ? `Sending ${cpuTarget}` : "Idle";
        cpuContent.parentElement.classList.toggle("pulse", cpuActive);

        let inputOccupied = false;
        let inputTx = "";
        transactions.forEach(t => {
            if (t.reqEnd && simulationTime >= t.start && simulationTime < t.reqEnd) {
                inputOccupied = true;
                inputTx = `${t.op} (${t.id})`;
            }
        });
        inputRegVal.textContent = inputOccupied ? inputTx : "Empty";
        inputRegVal.parentElement.classList.toggle("pulse", inputOccupied);

        activeSlots.innerHTML = "";
        transactions.forEach(t => {
            if (t.reqEnd && t.respStart && simulationTime >= t.reqEnd && simulationTime < t.respStart) {
                const slot = document.createElement("div");
                slot.className = "pipeline-slot";
                slot.textContent = `${t.op === "ADD" ? "+" : "×"} ${t.id}`;
                activeSlots.appendChild(slot);
            }
        });
    }

    // ==================== EXAMPLE 2 FIFO ANIMATION ====================
    else if (currentExample === "example2") {
        const prodStatus = document.getElementById("hw-producer-status");
        const consStatus = document.getElementById("hw-consumer-status");
        const slots = document.querySelectorAll("#fifo-slots-container .fifo-slot");

        let isStalled = false;
        let activeWrite = "";
        transactions.forEach(t => {
            if (t.op === "WRITE") {
                if (simulationTime >= t.start && t.stalledAt && simulationTime >= t.stalledAt && simulationTime < t.reqEnd) {
                    isStalled = true;
                }
                if (simulationTime >= t.start && simulationTime < t.end) {
                    activeWrite = `Write Tx ${t.id}`;
                }
            }
        });

        if (isStalled) {
            prodStatus.textContent = "STALLED (FIFO Full)";
            prodStatus.style.color = "var(--color-stall)";
            prodStatus.parentElement.classList.add("pulse");
        } else if (activeWrite) {
            prodStatus.textContent = activeWrite;
            prodStatus.style.color = "var(--text-highlight)";
            prodStatus.parentElement.classList.remove("pulse");
        } else {
            prodStatus.textContent = "Idle";
            prodStatus.style.color = "var(--text-secondary)";
            prodStatus.parentElement.classList.remove("pulse");
        }

        let isConsStalled = false;
        let activeRead = "";
        transactions.forEach(t => {
            if (t.op === "READ") {
                if (simulationTime >= t.start && t.stalledAt && simulationTime >= t.stalledAt && simulationTime < t.reqEnd) {
                    isConsStalled = true;
                }
                if (simulationTime >= t.start && simulationTime < t.end) {
                    activeRead = "Reading...";
                }
            }
        });
        
        if (isConsStalled) {
            consStatus.textContent = "STALLED (FIFO Empty)";
            consStatus.style.color = "var(--color-stall)";
            consStatus.parentElement.classList.add("pulse");
        } else {
            consStatus.textContent = activeRead ? activeRead : "Idle";
            consStatus.style.color = activeRead ? "var(--text-highlight)" : "var(--text-secondary)";
            consStatus.parentElement.classList.toggle("pulse", activeRead !== "");
        }

        // Trace FIFO Size dynamically from waveforms
        let currentSize = 0;
        if (waveforms && waveforms["top.fifo_target.fifo_size"]) {
            const sizePoints = waveforms["top.fifo_target.fifo_size"];
            sizePoints.forEach(p => {
                if (p[0] <= simulationTime) currentSize = p[1];
            });
        }

        slots.forEach((slot, index) => {
            if (index < currentSize) {
                slot.classList.add("occupied");
            } else {
                slot.classList.remove("occupied");
            }
        });
    }

    // ==================== EXAMPLE 3 SWITCH ANIMATION ====================
    else if (currentExample === "example3") {
        const switchStateEl = document.getElementById("switch-state-val");
        const switchArbEl = document.getElementById("switch-arb-ptr");
        const initBlocks = document.querySelectorAll(".hw-mini-block.init");
        const targetBlocks = document.querySelectorAll(".hw-mini-block.target-node");

        initBlocks.forEach(b => { b.className = "hw-mini-block init"; });
        targetBlocks.forEach(b => { b.className = "hw-mini-block target-node"; });

        transactions.forEach(t => {
            const id = parseInt(t.initId);
            const block = document.getElementById(`hw-init-${id}`);
            if (!block) return;

            if (simulationTime >= t.start && simulationTime < t.end) {
                if (t.reqEnd && simulationTime >= t.start && simulationTime < t.reqEnd && t.stall > 0 && (simulationTime - t.start) < t.stall) {
                    block.className = "hw-mini-block init stalled";
                } else {
                    block.className = "hw-mini-block init active-tx";
                }
            }
        });

        transactions.forEach(t => {
            if (t.reqEnd && t.respStart && simulationTime >= t.reqEnd && simulationTime < t.respStart) {
                const destNode = t.dest.match(/Node (\d+)/);
                if (destNode) {
                    const id = parseInt(destNode[1]);
                    document.getElementById(`hw-target-${id}`).className = "hw-mini-block target-node active-tx";
                }
            }
        });

        let switchBusy = false;
        let activeInitId = 0;
        let rrIndex = 0;

        if (waveforms) {
            if (waveforms["top.switch.switch_busy"]) {
                waveforms["top.switch.switch_busy"].forEach(p => {
                    if (p[0] <= simulationTime) switchBusy = (p[1] === 1);
                });
            }
            if (waveforms["top.switch.active_initiator_id"]) {
                waveforms["top.switch.active_initiator_id"].forEach(p => {
                    if (p[0] <= simulationTime) activeInitId = p[1];
                });
            }
            if (waveforms["top.switch.switch_rr_index"]) {
                waveforms["top.switch.switch_rr_index"].forEach(p => {
                    if (p[0] <= simulationTime) rrIndex = p[1];
                });
            }
        }

        switchStateEl.textContent = switchBusy ? `BUSY (IP ${activeInitId - 1})` : "FREE";
        switchStateEl.className = `switch-state ${switchBusy ? "switch-state-busy" : ""}`;
        switchArbEl.textContent = `RR Index: ${rrIndex}`;
    }
}
