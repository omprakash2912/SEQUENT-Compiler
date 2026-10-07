// SEQUENT Compiler - Web IDE & Execution Dashboard Frontend Driver
// Pure Vanilla ES6 JavaScript (Zero Third-Party Dependencies)

document.addEventListener("DOMContentLoaded", () => {
  // =============================================================
  // DOM Elements
  // =============================================================
  const sourceEditor = document.getElementById("sourceEditor");
  const editorLineNumbers = document.getElementById("editorLineNumbers");
  const dirtyIndicator = document.getElementById("dirtyIndicator");
  const activeFileName = document.getElementById("activeFileName");
  const timelineInput = document.getElementById("timelineInput");
  const exampleSelect = document.getElementById("exampleSelect");
  const quickExamplesList = document.getElementById("quickExamplesList");

  // Action Buttons
  const btnCompile = document.getElementById("btnCompile");
  const btnRun = document.getElementById("btnRun");
  const btnCompileRun = document.getElementById("btnCompileRun");
  const btnEmitSeqc = document.getElementById("btnEmitSeqc");
  const btnReloadExample = document.getElementById("btnReloadExample");
  const btnClearEditor = document.getElementById("btnClearEditor");
  const btnCopySource = document.getElementById("btnCopySource");
  const btnDownloadSeq = document.getElementById("btnDownloadSeq");
  const btnResetTimeline = document.getElementById("btnResetTimeline");
  const btnDownloadSeqcBinary = document.getElementById("btnDownloadSeqcBinary");

  // File Inputs
  const inputSeqFile = document.getElementById("inputSeqFile");
  const inputTelemetryFile = document.getElementById("inputTelemetryFile");
  const inputSeqcBinary = document.getElementById("inputSeqcBinary");
  const inputSeqcBinaryHeader = document.getElementById("inputSeqcBinaryHeader");

  // Badges & Error Banner
  const globalStatusBadge = document.getElementById("globalStatusBadge");
  const compilerErrorBanner = document.getElementById("compilerErrorBanner");
  const errStageCategory = document.getElementById("errStageCategory");
  const errCoordinates = document.getElementById("errCoordinates");
  const errMessage = document.getElementById("errMessage");

  // Inspector Header
  const inspectorStageTitle = document.getElementById("inspectorStageTitle");
  const inspectorStageSubtitle = document.getElementById("inspectorStageSubtitle");
  const inspectorStageBadge = document.getElementById("inspectorStageBadge");

  // Sidebar Summary Card
  const sideSysName = document.getElementById("sideSysName");
  const sideSysSpan = document.getElementById("sideSysSpan");
  const sideSysCounts = document.getElementById("sideSysCounts");
  const sideSysConstraints = document.getElementById("sideSysConstraints");

  // Bottom Dock & Diagnostics Elements
  const editorHighlightLayer = document.getElementById("editorHighlightLayer");
  const editorDock = document.getElementById("editorDock");
  const badgeProblemsCount = document.getElementById("badgeProblemsCount");
  const problemsList = document.getElementById("problemsList");
  const assistantContent = document.getElementById("assistantContent");
  const btnToggleDock = document.getElementById("btnToggleDock");
  const btnTemplatesDropdown = document.getElementById("btnTemplatesDropdown");
  const templatesDropdownMenu = document.getElementById("templatesDropdownMenu");

  // Stage Views & Navigation
  const stageNavButtons = document.querySelectorAll(".stage-nav-btn");
  const stageViews = document.querySelectorAll(".stage-view");

  // State
  let examplesCatalog = [];
  let currentExample = null;
  let lastCompiledData = null;
  let lastSimulationData = null;
  let lastSeqcEmitData = null;
  let currentExecutionMode = "source"; // "source" | "seqc"
  let loadedSeqcData = null; // { filename, base64, metadata, bytecode }
  let currentActiveStage = "editor";
  let currentDiagnostics = [];
  let activeErrorLines = new Set();

  // Stage metadata definitions
  const STAGE_METADATA = {
    editor: { title: "SEQUENT Source Code Editor", subtitle: "Live interactive domain-specific code workbench" },
    lexer: { title: "Stage 1: Lexical Analysis (Token Stream)", subtitle: "Deterministic token stream output with line/col coordinates" },
    parser: { title: "Stage 2: Syntax Analysis & AST", subtitle: "Hierarchical Abstract Syntax Tree construction" },
    symbols: { title: "Stage 3: Symbol Table", subtitle: "Resolved state variables and event identifiers with static types" },
    semantic: { title: "Stage 4: Semantic Analysis", subtitle: "Static type checking, scope validation, and handler declaration rules" },
    temporal: { title: "Stage 5: Static Temporal Analysis", subtitle: "Duration normalization and static constraint bounds" },
    ir: { title: "Stage 6: Intermediate Representation (IR)", subtitle: "Linear 3-address style intermediate instructions" },
    optimization: { title: "Stage 7: IR Optimization Pass", subtitle: "Dead Store Elimination (DSE) and redundant store removal" },
    bytecode: { title: "Stage 8: Bytecode Disassembly", subtitle: "Stack-based Virtual Machine instruction set" },
    vm: { title: "Stage 9: Virtual Machine Execution", subtitle: "State environment mutations and event dispatch steps" },
    simulation: { title: "Stage 10: Discrete-Event Simulation", subtitle: "Priority-queue deterministic virtual clock scheduling" },
    verification: { title: "Stage 11: Temporal Verification Audit", subtitle: "Runtime constraint satisfaction, exact boundaries, and timeouts" },
    timeline: { title: "Stage 12: Visual Timeline & Gantt View", subtitle: "Virtual millisecond coordinate map with constraint intervals" },
    transitions: { title: "Stage 13: State Transition History", subtitle: "Audited state mutations across discrete virtual time" },
    telemetry: { title: "Stage 14: Structured Execution Telemetry", subtitle: "Standardized JSON execution telemetry for verification" },
    seqc: { title: "Stage 15: Binary Bytecode Container (.seqc)", subtitle: "16-byte fixed header container with CRC32 integrity verification" },
  };

  // =============================================================
  // Editor Initialization & Line Numbers Synchronization
  // =============================================================
  // =============================================================
  // Utility & HTML Sanitization
  // =============================================================
  function escapeHtml(str) {
    if (str === null || str === undefined) return "";
    return String(str)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;")
      .replace(/'/g, "&#39;");
  }

  // =============================================================
  // Built-in Boilerplate Templates
  // =============================================================
  const BUILTIN_TEMPLATES = {
    emergency_response: {
      name: "Emergency Response System",
      filename: "EmergencyResponse.seq",
      default_events: "EmergencyDetected@0ms, TeamDispatched@3200ms, IncidentResolved@5000ms",
      code: `system EmergencyResponseSystem {

    state active = false
    state team = "AVAILABLE"

    event EmergencyDetected
    event TeamDispatched
    event IncidentResolved

    constraint EmergencyDetected -> TeamDispatched within 5s
    constraint TeamDispatched -> IncidentResolved within 30m

    on EmergencyDetected {
        active = true
        team = "DISPATCHED"
    }

    on TeamDispatched {
        team = "EN_ROUTE"
    }

    on IncidentResolved {
        active = false
        team = "AVAILABLE"
    }
}
`
    },
    industrial_monitoring: {
      name: "Industrial Monitoring System",
      filename: "IndustrialMonitoring.seq",
      default_events: "PressureThresholdExceeded@0ms, ReliefValveTriggered@1200ms, PressureStabilized@4500ms",
      code: `system IndustrialMonitoringSystem {

    state pressure_alert = false
    state valve_open = false
    state safe_mode = false

    event PressureThresholdExceeded
    event ReliefValveTriggered
    event PressureStabilized

    constraint PressureThresholdExceeded -> ReliefValveTriggered within 2000ms
    constraint ReliefValveTriggered -> PressureStabilized within 10s

    on PressureThresholdExceeded {
        pressure_alert = true
        safe_mode = true
    }

    on ReliefValveTriggered {
        valve_open = true
    }

    on PressureStabilized {
        pressure_alert = false
        valve_open = false
        safe_mode = false
    }
}
`
    },
    smart_building: {
      name: "Smart Building System",
      filename: "SmartBuilding.seq",
      default_events: "PowerGridFailure@0ms, AuxGeneratorStarted@1800ms, GridRestored@5000ms",
      code: `system SmartBuildingSystem {

    state power_alert = false
    state auxiliary_power = false
    state grid_stable = true

    event PowerGridFailure
    event AuxGeneratorStarted
    event GridRestored

    constraint PowerGridFailure -> AuxGeneratorStarted within 3s
    constraint AuxGeneratorStarted -> GridRestored within 1h

    on PowerGridFailure {
        power_alert = true
        grid_stable = false
    }

    on AuxGeneratorStarted {
        auxiliary_power = true
    }

    on GridRestored {
        power_alert = false
        auxiliary_power = false
        grid_stable = true
    }
}
`
    },
    simple_timer: {
      name: "Simple Timer System",
      filename: "SimpleTimer.seq",
      default_events: "StartTimer@0ms, TimerTick@800ms, TimerExpired@3500ms",
      code: `system SimpleTimerSystem {

    state timer_running = false
    state ticks = 0

    event StartTimer
    event TimerTick
    event TimerExpired

    constraint StartTimer -> TimerTick within 1s
    constraint TimerTick -> TimerExpired within 5s

    on StartTimer {
        timer_running = true
        ticks = 1
    }

    on TimerTick {
        ticks = 2
    }

    on TimerExpired {
        timer_running = false
        ticks = 0
    }
}
`
    },
    fault_detection: {
      name: "Fault Detection System",
      filename: "FaultDetection.seq",
      default_events: "SensorFaultDetected@0ms, FailsafeEngaged@350ms, DiagnosticsCompleted@8000ms",
      code: `system FaultDetectionSystem {

    state fault_active = false
    state safe_mode = false
    state alert_level = 0

    event SensorFaultDetected
    event FailsafeEngaged
    event DiagnosticsCompleted

    constraint SensorFaultDetected -> FailsafeEngaged within 500ms
    constraint FailsafeEngaged -> DiagnosticsCompleted within 15s

    on SensorFaultDetected {
        fault_active = true
        safe_mode = true
        alert_level = 1
    }

    on FailsafeEngaged {
        alert_level = 2
    }

    on DiagnosticsCompleted {
        fault_active = false
        safe_mode = false
        alert_level = 0
    }
}
`
    }
  };

  // =============================================================
  // Editor Initialization, Diagnostics & Highlight Synchronization
  // =============================================================
  function updateHighlightOverlay() {
    if (!editorHighlightLayer) return;
    const lines = sourceEditor.value.split("\n");
    const lineDiagMap = new Map();
    for (const d of currentDiagnostics) {
      if (d.line && !lineDiagMap.has(d.line)) {
        lineDiagMap.set(d.line, d);
      }
    }

    let html = "";
    for (let i = 1; i <= lines.length; i++) {
      const lineText = lines[i - 1];
      const diag = lineDiagMap.get(i);
      if (diag) {
        let content = escapeHtml(lineText);
        if (diag.token && lineText.includes(diag.token)) {
          const escapedToken = escapeHtml(diag.token);
          const idx = lineText.indexOf(diag.token);
          const before = escapeHtml(lineText.substring(0, idx));
          const after = escapeHtml(lineText.substring(idx + diag.token.length));
          content = `${before}<span class="hl-token-error" title="${escapeHtml(diag.message)}">${escapedToken}</span>${after}`;
        }
        html += `<div class="hl-line hl-line-error">${content || "&nbsp;"}</div>`;
      } else {
        html += `<div class="hl-line">${escapeHtml(lineText) || "&nbsp;"}</div>`;
      }
    }
    editorHighlightLayer.innerHTML = html;
    editorHighlightLayer.scrollTop = sourceEditor.scrollTop;
    editorHighlightLayer.scrollLeft = sourceEditor.scrollLeft;
  }

  function updateLineNumbers() {
    const lines = sourceEditor.value.split("\n");
    const count = lines.length;
    let numbersHtml = "";
    for (let i = 1; i <= count; i++) {
      if (activeErrorLines.has(i)) {
        numbersHtml += `<div class="gutter-num gutter-has-error" title="Compilation error on line ${i}"><span class="gutter-err-marker">❌</span>${i}</div>`;
      } else {
        numbersHtml += `<div class="gutter-num">${i}</div>`;
      }
    }
    editorLineNumbers.innerHTML = numbersHtml;
    updateHighlightOverlay();
  }

  function clearDiagnostics() {
    currentDiagnostics = [];
    activeErrorLines.clear();
    updateLineNumbers();
    if (badgeProblemsCount) {
      badgeProblemsCount.textContent = "0";
      badgeProblemsCount.className = "dock-badge dock-badge-clean";
    }
    if (problemsList) {
      problemsList.innerHTML = `
        <div class="problems-empty">
          <span class="check-icon">✓</span>
          <span>No problems detected</span>
        </div>
      `;
    }
    renderAssistant(null);
  }

  function renderDiagnostics(diagnostics) {
    currentDiagnostics = Array.isArray(diagnostics) ? diagnostics : [];
    activeErrorLines.clear();
    for (const d of currentDiagnostics) {
      if (d.line) {
        activeErrorLines.add(d.line);
      }
    }
    updateLineNumbers();

    if (badgeProblemsCount) {
      badgeProblemsCount.textContent = currentDiagnostics.length;
      badgeProblemsCount.className = currentDiagnostics.length > 0 ? "dock-badge dock-badge-error" : "dock-badge dock-badge-clean";
    }

    renderProblemsList(currentDiagnostics);

    if (currentDiagnostics.length > 0) {
      renderAssistant(currentDiagnostics[0]);
    }
  }

  function renderProblemsList(diagnostics) {
    if (!problemsList) return;
    if (!diagnostics || diagnostics.length === 0) {
      problemsList.innerHTML = `
        <div class="problems-empty">
          <span class="check-icon">✓</span>
          <span>No problems detected</span>
        </div>
      `;
      return;
    }

    let html = "";
    diagnostics.forEach((d, idx) => {
      const isWarning = d.severity === "WARNING";
      const icon = isWarning ? "⚠️" : "❌";
      const rowClass = isWarning ? "problem-row problem-row-warning" : "problem-row";
      const badgeClass = isWarning ? "problem-stage-badge badge-warning" : "problem-stage-badge";
      const locText = d.line ? `Ln ${d.line}, Col ${d.column || 1}` : "Global";

      html += `
        <div class="problem-row ${rowClass}" data-index="${idx}">
          <div class="problem-main">
            <span class="problem-icon">${icon}</span>
            <span class="${badgeClass}">${escapeHtml(d.stage || "ERROR")}</span>
            <span class="problem-message" title="${escapeHtml(d.message)}">${escapeHtml(d.message)}</span>
          </div>
          <div class="problem-actions">
            <span class="problem-location">${locText}</span>
            ${d.line ? `<button class="btn-goto-line" onclick="window.SequentIDE.goToLine(${d.line}, ${d.column || 1}, '${escapeHtml(d.token || "")}')">Go to Line</button>` : ""}
          </div>
        </div>
      `;
    });
    problemsList.innerHTML = html;
  }

  function renderAssistant(diag, successData = null, isSeqc = false) {
    if (!assistantContent) return;

    if (isSeqc) {
      assistantContent.innerHTML = `
        <div class="assistant-card assistant-success">
          <div class="assistant-title-row">
            <div class="assistant-title"><span class="check-icon">✓</span> Direct .seqc Binary Container Execution</div>
            <span class="symbol-tag">SEQC CONTAINER</span>
          </div>
          <div class="assistant-text">
            Pre-compiled bytecode executed directly in the SEQUENT Virtual Machine.
            Lexer, parser, and semantic analysis stages were bypassed for verified binary execution.
          </div>
          <div class="assistant-section">
            <div class="assistant-section-label">Container Metadata</div>
            <div class="assistant-text">
              System: <strong>${escapeHtml(successData?.system_name || successData?.seqc_metadata?.system_name || "CompiledSystem")}</strong> · 
              Instructions: <strong>${successData?.seqc_metadata?.total_instructions || successData?.bytecode?.total_instructions || 0}</strong> · 
              CRC32: <strong>${successData?.seqc_metadata?.crc32_hex || "-"}</strong> · 
              Status: <strong>${successData?.success ? "All Constraints Satisfied" : "Constraints Violated"}</strong>
            </div>
          </div>
        </div>
      `;
      return;
    }

    if (diag) {
      let declaredHtml = "";
      if (diag.declared_events && diag.declared_events.length > 0) {
        declaredHtml += `
          <div class="assistant-section">
            <div class="assistant-section-label">Declared Events:</div>
            <div class="assistant-symbols-list">
              ${diag.declared_events.map(ev => `<span class="symbol-tag">${escapeHtml(ev)}</span>`).join("")}
            </div>
          </div>
        `;
      }
      if (diag.declared_states && diag.declared_states.length > 0) {
        declaredHtml += `
          <div class="assistant-section">
            <div class="assistant-section-label">Declared States:</div>
            <div class="assistant-symbols-list">
              ${diag.declared_states.map(st => `<span class="symbol-tag">${escapeHtml(st)}</span>`).join("")}
            </div>
          </div>
        `;
      }

      let fixBtnHtml = "";
      if (diag.code_fix) {
        const fix = diag.code_fix;
        const fixLabel = fix.type === "replace_token"
          ? `Apply Fix: Replace '${escapeHtml(fix.target)}' with '${escapeHtml(fix.replacement)}'`
          : `Apply Fix: Add '${escapeHtml(fix.replacement.trim())}'`;
        fixBtnHtml = `<button class="btn-apply-fix" id="btnApplyFix">${fixLabel}</button>`;
      }

      assistantContent.innerHTML = `
        <div class="assistant-card assistant-error">
          <div class="assistant-title-row">
            <div class="assistant-title">
              <span>⚠️</span> ${escapeHtml(diag.stage || "COMPILER")} DIAGNOSTIC
            </div>
            ${diag.line ? `<span class="problem-location">Line ${diag.line}, Col ${diag.column || 1}</span>` : ""}
          </div>
          <div class="assistant-section">
            <div class="assistant-section-label">What went wrong?</div>
            <div class="assistant-text">${escapeHtml(diag.explanation || diag.message)}</div>
          </div>
          ${declaredHtml}
          <div class="assistant-section">
            <div class="assistant-section-label">How to fix it</div>
            <div class="assistant-text">${escapeHtml(diag.suggestion || "Review source code around this location.")}</div>
          </div>
          <div class="assistant-actions-row">
            ${diag.line ? `<button class="btn btn-sm btn-goto-line" onclick="window.SequentIDE.goToLine(${diag.line}, ${diag.column || 1}, '${escapeHtml(diag.token || "")}')">Go to Line ${diag.line}</button>` : ""}
            ${fixBtnHtml}
          </div>
        </div>
      `;

      if (diag.code_fix) {
        const applyBtn = document.getElementById("btnApplyFix");
        if (applyBtn) {
          applyBtn.addEventListener("click", () => {
            applyCodeFix(diag.code_fix);
          });
        }
      }
      return;
    }

    if (successData) {
      const sim = successData.summary || {};
      const satisfied = sim.constraints_satisfied || 0;
      const violated = sim.constraints_violated || 0;
      const events = sim.total_events || 0;

      assistantContent.innerHTML = `
        <div class="assistant-card assistant-success">
          <div class="assistant-title-row">
            <div class="assistant-title"><span class="check-icon">✓</span> Build & Verification Clean</div>
            <span class="symbol-tag">VERIFIED</span>
          </div>
          <div class="assistant-text">
            All compiler stages completed without errors: Lexer, Parser, Symbol Table, Semantic Analyzer, Temporal Analyzer, IR Generator, Optimizer, and Bytecode Disassembler.
          </div>
          <div class="assistant-section">
            <div class="assistant-section-label">Pipeline Summary</div>
            <div class="assistant-text">
              System: <strong>${escapeHtml(successData.system_name || "ActiveSystem")}</strong> · 
              Stages: <strong>8/8 Passed</strong>
              ${sim.constraints_checked ? ` · Constraints: <strong>${satisfied} Satisfied, ${violated} Violated</strong> · Events: <strong>${events}</strong>` : ""}
            </div>
          </div>
        </div>
      `;
      return;
    }

    // Default idle state
    assistantContent.innerHTML = `
      <div class="assistant-card assistant-idle">
        <div class="assistant-title-row">
          <div class="assistant-title"><span>🤖</span> SEQUENT Assistant Ready</div>
        </div>
        <div class="assistant-text">
          Compile or run your program to receive intelligent rule-based explanations, typo corrections, and automatic fixes.
        </div>
      </div>
    `;
  }

  function goToLine(line, column = 1, token = null) {
    if (!line || line < 1) return;
    const lines = sourceEditor.value.split("\n");
    if (line > lines.length) return;

    let charOffset = 0;
    for (let i = 0; i < line - 1; i++) {
      charOffset += lines[i].length + 1;
    }

    const targetLineText = lines[line - 1];
    let startCol = (column && column > 0) ? column - 1 : 0;
    let tokenLen = 0;

    if (token && targetLineText.includes(token)) {
      const idx = targetLineText.indexOf(token);
      startCol = idx;
      tokenLen = token.length;
    } else if (startCol < targetLineText.length) {
      const wordMatch = targetLineText.substring(startCol).match(/^[A-Za-z0-9_]+/);
      tokenLen = wordMatch ? wordMatch[0].length : 1;
    }

    const selStart = charOffset + startCol;
    const selEnd = selStart + (tokenLen > 0 ? tokenLen : 1);

    sourceEditor.focus();
    sourceEditor.setSelectionRange(selStart, selEnd);

    const lineTop = (line - 1) * 20;
    const editorHeight = sourceEditor.clientHeight;
    if (lineTop < sourceEditor.scrollTop || lineTop > sourceEditor.scrollTop + editorHeight - 40) {
      sourceEditor.scrollTop = Math.max(0, lineTop - Math.floor(editorHeight / 2));
    }
  }

  function applyCodeFix(fix) {
    if (!fix) return;
    const lines = sourceEditor.value.split("\n");
    if (fix.type === "replace_token" && fix.line && fix.line <= lines.length) {
      const lineIdx = fix.line - 1;
      const targetLine = lines[lineIdx];
      if (targetLine.includes(fix.target)) {
        lines[lineIdx] = targetLine.replace(fix.target, fix.replacement);
        sourceEditor.value = lines.join("\n");
        updateLineNumbers();
        dirtyIndicator.classList.add("dirty");
        runCompileOnly();
      }
    } else if (fix.type === "append_text") {
      sourceEditor.value = sourceEditor.value + fix.replacement;
      updateLineNumbers();
      dirtyIndicator.classList.add("dirty");
      runCompileOnly();
    }
  }

  function insertTemplate(templateKey) {
    const tmpl = BUILTIN_TEMPLATES[templateKey];
    if (!tmpl) return;
    clearAllStageData();
    clearDiagnostics();
    currentExecutionMode = "source";
    loadedSeqcData = null;
    sourceEditor.value = tmpl.code;
    timelineInput.value = tmpl.default_events || "";
    activeFileName.textContent = tmpl.filename;
    updateLineNumbers();
    dirtyIndicator.classList.remove("dirty");
    hideError();
    setStatus("ready", "READY");
    switchStage("editor");
    runCompileOnly();
  }

  // Global handle for inline button events
  window.SequentIDE = {
    goToLine,
    applyCodeFix,
    insertTemplate,
  };

  sourceEditor.addEventListener("input", () => {
    updateLineNumbers();
    dirtyIndicator.classList.add("dirty");
    if (currentExecutionMode === "seqc") {
      currentExecutionMode = "source";
      loadedSeqcData = null;
    }
  });

  sourceEditor.addEventListener("scroll", () => {
    editorLineNumbers.scrollTop = sourceEditor.scrollTop;
    if (editorHighlightLayer) {
      editorHighlightLayer.scrollTop = sourceEditor.scrollTop;
      editorHighlightLayer.scrollLeft = sourceEditor.scrollLeft;
    }
  });

  // Handle Tab key indentation inside editor
  sourceEditor.addEventListener("keydown", (e) => {
    if (e.key === "Tab") {
      e.preventDefault();
      const start = sourceEditor.selectionStart;
      const end = sourceEditor.selectionEnd;
      const spaces = "    ";
      sourceEditor.value = sourceEditor.value.substring(0, start) + spaces + sourceEditor.value.substring(end);
      sourceEditor.selectionStart = sourceEditor.selectionEnd = start + spaces.length;
      updateLineNumbers();
      dirtyIndicator.classList.add("dirty");
    } else if (e.key === "Enter" && (e.ctrlKey || e.metaKey)) {
      e.preventDefault();
      handleRunClick();
    }
  });

  // =============================================================
  // Navigation & Stage Switching
  // =============================================================
  function switchStage(stageKey) {
    currentActiveStage = stageKey;

    // Update buttons
    stageNavButtons.forEach(btn => {
      btn.classList.toggle("active", btn.dataset.stage === stageKey);
    });

    // Update views
    stageViews.forEach(view => {
      view.classList.toggle("active", view.id === `view-${stageKey}`);
    });

    // Update header
    const meta = STAGE_METADATA[stageKey] || { title: stageKey, subtitle: "" };
    inspectorStageTitle.textContent = meta.title;
    inspectorStageSubtitle.textContent = meta.subtitle;

    // Refresh SVGs or layouts if needed
    if (stageKey === "timeline" && lastSimulationData) {
      renderInteractiveTimeline(lastSimulationData);
    }
  }

  stageNavButtons.forEach(btn => {
    btn.addEventListener("click", () => switchStage(btn.dataset.stage));
  });

  // =============================================================
  // Status & Error Management
  // =============================================================
  function setStatus(status, text) {
    globalStatusBadge.className = `status-badge status-${status}`;
    globalStatusBadge.textContent = text || status.toUpperCase();
  }

  function hideError() {
    compilerErrorBanner.style.display = "none";
  }

  function showError(errorObj) {
    compilerErrorBanner.style.display = "block";
    errStageCategory.textContent = `${errorObj.stage || "COMPILER"} ERROR: ${errorObj.category || "FAILURE"}`;
    errCoordinates.textContent = (errorObj.line !== undefined && errorObj.line !== null)
      ? `Line ${errorObj.line}, Column ${errorObj.column}`
      : "Global / Runtime";
    errMessage.textContent = errorObj.message || "An unspecified compiler error occurred.";
    setStatus("danger", "ERROR");
  }

  function clearAllStageData(preserveSeqc = false) {
    lastCompiledData = null;
    lastSimulationData = null;
    if (!preserveSeqc) {
      lastSeqcEmitData = null;
      loadedSeqcData = null;
      currentExecutionMode = "source";
    }

    // Reset sidebar summary card
    if (sideSysName) sideSysName.textContent = "-";
    if (sideSysSpan) sideSysSpan.textContent = "-";
    if (sideSysCounts) sideSysCounts.textContent = "-";
    if (sideSysConstraints) sideSysConstraints.textContent = "-";

    // Reset all sidebar stage status icons
    const allStages = [
      "lexer", "parser", "symbols", "semantic", "temporal", "ir",
      "optimization", "bytecode", "vm", "simulation", "verification",
      "timeline", "transitions", "telemetry", "seqc"
    ];
    allStages.forEach(st => {
      const el = document.getElementById(`statusIcon-${st}`);
      if (el) {
        el.textContent = "○";
        el.className = "stage-status-icon status-idle";
      }
    });

    // Reset Tokens
    const tokensBody = document.getElementById("tokensTableBody");
    if (tokensBody) tokensBody.innerHTML = '<tr><td colspan="5" class="empty-state">Compile source to inspect token stream.</td></tr>';
    const tokenBadge = document.getElementById("tokenCountBadge");
    if (tokenBadge) tokenBadge.textContent = "0 tokens";
    const tokenFilter = document.getElementById("tokenFilterInput");
    if (tokenFilter) tokenFilter.value = "";

    // Reset AST
    const astTreeContainer = document.getElementById("astTreeContainer");
    if (astTreeContainer) astTreeContainer.innerHTML = '<div class="empty-state">Compile source to inspect the Abstract Syntax Tree.</div>';
    const astTextContainer = document.getElementById("astTextContainer");
    if (astTextContainer) astTextContainer.textContent = "(No AST generated)";

    // Reset Symbol Table
    const statesBody = document.getElementById("symbolsStatesBody");
    if (statesBody) statesBody.innerHTML = '<tr><td colspan="4" class="empty-state">No states registered.</td></tr>';
    const eventsBody = document.getElementById("symbolsEventsBody");
    if (eventsBody) eventsBody.innerHTML = '<tr><td colspan="2" class="empty-state">No events registered.</td></tr>';

    // Reset Semantic Analysis
    const semanticCard = document.getElementById("semanticStatusCard");
    if (semanticCard) semanticCard.innerHTML = '<div class="empty-state">Run compilation to perform semantic and scope validation.</div>';

    // Reset Static Temporal Constraints
    const temporalBody = document.getElementById("temporalStaticBody");
    if (temporalBody) temporalBody.innerHTML = '<tr><td colspan="6" class="empty-state">No static temporal constraints defined.</td></tr>';

    // Reset IR Table
    const irBody = document.getElementById("irTableBody");
    if (irBody) irBody.innerHTML = '<tr><td colspan="6" class="empty-state">Compile source to inspect 3-address linear IR.</td></tr>';

    // Reset Optimization
    const optInitial = document.getElementById("optInitial");
    if (optInitial) optInitial.textContent = "-";
    const optFinal = document.getElementById("optFinal");
    if (optFinal) optFinal.textContent = "-";
    const optEliminated = document.getElementById("optEliminated");
    if (optEliminated) optEliminated.textContent = "-";
    const optReduction = document.getElementById("optReduction");
    if (optReduction) optReduction.textContent = "-";
    const optPasses = document.getElementById("optPasses");
    if (optPasses) optPasses.textContent = "-";
    const optComp = document.getElementById("optComparisonText");
    if (optComp) optComp.textContent = "(Run compilation to view IR optimization diff)";

    // Reset Bytecode
    const bcTotalBadge = document.getElementById("bcTotalBadge");
    if (bcTotalBadge) bcTotalBadge.textContent = "0 instructions";
    const bcHandlersBadge = document.getElementById("bcHandlersBadge");
    if (bcHandlersBadge) bcHandlersBadge.textContent = "0 handlers";
    const bcBody = document.getElementById("bytecodeTableBody");
    if (bcBody) bcBody.innerHTML = '<tr><td colspan="5" class="empty-state">Compile source to inspect generated bytecode.</td></tr>';

    // Reset VM Execution Log
    const vmLog = document.getElementById("vmExecutionLog");
    if (vmLog) vmLog.textContent = "(Execute program to view runtime VM step log)";

    // Reset Simulation Trace
    const simTrace = document.getElementById("simTraceBody");
    if (simTrace) simTrace.innerHTML = '<tr><td colspan="6" class="empty-state">Run simulation to inspect priority queue execution order.</td></tr>';

    // Reset Verification Table
    const verifBody = document.getElementById("verificationTableBody");
    if (verifBody) verifBody.innerHTML = '<tr><td colspan="7" class="empty-state">Run program to verify runtime temporal constraints.</td></tr>';

    // Reset Interactive Timeline SVG
    const svg = document.getElementById("interactiveTimelineSvg");
    if (svg) {
      svg.innerHTML = "";
      svg.setAttribute("height", "240");
    }

    // Reset State Transitions
    const stBody = document.getElementById("stateTransitionsBody");
    if (stBody) stBody.innerHTML = '<tr><td colspan="4" class="empty-state">No state transitions recorded.</td></tr>';
    const stBadge = document.getElementById("stateCountBadge");
    if (stBadge) stBadge.textContent = "0 mutations";
    const stFilter = document.getElementById("stateFilterInput");
    if (stFilter) stFilter.value = "";

    // Reset Telemetry
    const telemCard = document.getElementById("telemetryLoadedCard");
    if (telemCard) telemCard.style.display = "none";
    const telemDisplay = document.getElementById("telemetryJsonDisplay");
    if (telemDisplay) telemDisplay.textContent = "(Run program or load a telemetry JSON file to view structured telemetry)";

    // Reset .seqc Inspector
    if (!preserveSeqc) {
      const seqcMagic = document.getElementById("seqcMagic");
      if (seqcMagic) seqcMagic.textContent = 'b"SEQC" (0x53 0x45 0x51 0x43)';
      const seqcVersion = document.getElementById("seqcVersion");
      if (seqcVersion) seqcVersion.textContent = "1 (16-bit Big-Endian)";
      const seqcFlags = document.getElementById("seqcFlags");
      if (seqcFlags) seqcFlags.textContent = "0x0000";
      const seqcPayloadLen = document.getElementById("seqcPayloadLen");
      if (seqcPayloadLen) seqcPayloadLen.textContent = "-";
      const seqcChecksum = document.getElementById("seqcChecksum");
      if (seqcChecksum) seqcChecksum.textContent = "-";
      const seqcInstructions = document.getElementById("seqcInstructions");
      if (seqcInstructions) seqcInstructions.textContent = "-";
      const seqcSystemName = document.getElementById("seqcSystemName");
      if (seqcSystemName) seqcSystemName.textContent = "-";
      const seqcHandlers = document.getElementById("seqcHandlers");
      if (seqcHandlers) seqcHandlers.textContent = "-";
    }
  }

  function updateSidebarStageIcons(statuses) {
    for (const [stage, stat] of Object.entries(statuses)) {
      const iconEl = document.getElementById(`statusIcon-${stage}`);
      if (!iconEl) continue;

      if (stat === "ok") {
        iconEl.textContent = "✓";
        iconEl.className = "stage-status-icon status-ok";
      } else if (stat === "failed") {
        iconEl.textContent = "✗";
        iconEl.className = "stage-status-icon status-fail";
      } else if (stat === "warning") {
        iconEl.textContent = "⚠️";
        iconEl.className = "stage-status-icon status-warn";
      } else if (stat === "skipped") {
        iconEl.textContent = "—";
        iconEl.className = "stage-status-icon status-idle";
      } else {
        iconEl.textContent = "○";
        iconEl.className = "stage-status-icon status-idle";
      }
    }
  }

  // =============================================================
  // API Calls: Compile & Simulate
  // =============================================================
  async function runCompileOnly() {
    clearAllStageData();
    clearDiagnostics();
    hideError();
    setStatus("compiling", "COMPILING...");

    try {
      const res = await fetch("/api/compile", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          source: sourceEditor.value,
          optimize: true,
        }),
      });

      const data = await res.json();
      lastCompiledData = data;

      if (data.stages_status) {
        updateSidebarStageIcons(data.stages_status);
      }

      if (!data.success) {
        showError(data.error);
        renderDiagnostics(data.diagnostics && data.diagnostics.length > 0 ? data.diagnostics : [data.error]);
        if (data.partial_stages) {
          renderCompilerOutputs({
            ...data.partial_stages,
            error: data.error,
          });
        }
        if (data.error && data.error.stage) {
          const map = { LEXER: "lexer", PARSER: "parser", SEMANTIC: "semantic", TEMPORAL: "temporal" };
          const target = map[data.error.stage] || "editor";
          switchStage(target);
        }
        return;
      }

      // Success
      setStatus("success", "COMPILED");
      renderCompilerOutputs(data);
      renderDiagnostics(data.diagnostics || []);
      renderAssistant(null, data);
      switchStage("tokens");
    } catch (err) {
      showError({ stage: "NETWORK", category: "REQUEST FAILED", message: err.message });
      renderDiagnostics([{ stage: "NETWORK", severity: "ERROR", message: err.message, explanation: "Network request failed while connecting to compilation server.", suggestion: "Verify server status." }]);
    }
  }

  async function runCompileAndExecute() {
    clearAllStageData();
    clearDiagnostics();
    hideError();
    setStatus("compiling", "RUNNING...");

    try {
      const res = await fetch("/api/compile-run", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          source: sourceEditor.value,
          events: timelineInput.value,
          optimize: true,
        }),
      });

      const data = await res.json();

      if (!data.success && data.error && !data.simulation) {
        // Compiler error
        if (data.stages_status) updateSidebarStageIcons(data.stages_status);
        showError(data.error);
        renderDiagnostics(data.diagnostics && data.diagnostics.length > 0 ? data.diagnostics : [data.error]);
        if (data.partial_stages) {
          renderCompilerOutputs({
            ...data.partial_stages,
            error: data.error,
          });
        }
        if (data.error && data.error.stage) {
          const map = { LEXER: "lexer", PARSER: "parser", SEMANTIC: "semantic", TEMPORAL: "temporal" };
          const target = map[data.error.stage] || "editor";
          switchStage(target);
        }
        return;
      }

      if (data.compiler && data.compiler.stages_status) {
        const statuses = { ...data.compiler.stages_status };
        statuses["vm"] = "ok";
        statuses["simulation"] = "ok";
        statuses["verification"] = data.success ? "ok" : "failed";
        statuses["timeline"] = "ok";
        statuses["transitions"] = "ok";
        statuses["telemetry"] = "ok";
        updateSidebarStageIcons(statuses);
      }

      lastSimulationData = data;
      if (data.compiler) {
        lastCompiledData = data.compiler;
        renderCompilerOutputs(data.compiler);
      }

      renderSimulationOutputs(data);

      renderDiagnostics(data.diagnostics || []);
      renderAssistant(data.diagnostics && data.diagnostics.length > 0 ? data.diagnostics[0] : null, data);

      if (data.success) {
        setStatus("success", "SUCCESS");
      } else {
        setStatus("warning", "CONSTRAINTS BREACHED");
      }

      dirtyIndicator.classList.remove("dirty");
      switchStage("verification");
    } catch (err) {
      showError({ stage: "RUNTIME", category: "EXECUTION ERROR", message: err.message });
      renderDiagnostics([{ stage: "RUNTIME", severity: "ERROR", message: err.message, explanation: "Network error during simulation request.", suggestion: "Verify server connection." }]);
    }
  }

  async function emitSeqcBinary() {
    hideError();
    try {
      const res = await fetch("/api/emit-seqc", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          source: sourceEditor.value,
          optimize: true,
        }),
      });

      const data = await res.json();
      if (!data.success) {
        showError(data.error);
        return;
      }

      lastSeqcEmitData = data;
      renderSeqcMetadata(data);
      btnDownloadSeqcBinary.disabled = false;
      switchStage("seqc");
      setStatus("success", ".SEQC EMITTED");
    } catch (err) {
      showError({ stage: "SERIALIZATION", category: "EMIT ERROR", message: err.message });
    }
  }

  // =============================================================
  // Renderers for All Major Compiler Stages
  // =============================================================
  function renderCompilerOutputs(data) {
    if (!data) return;

    // 1. Tokens Table
    const tokensBody = document.getElementById("tokensTableBody");
    const tokenBadge = document.getElementById("tokenCountBadge");
    if (data.tokens && data.tokens.length > 0) {
      tokenBadge.textContent = `${data.tokens.length} tokens`;
      tokensBody.innerHTML = "";
      data.tokens.forEach(tok => {
        const tr = document.createElement("tr");
        tr.innerHTML = `
          <td>${tok.line}</td>
          <td>${tok.column}</td>
          <td><strong style="color:var(--primary);">${escapeHtml(tok.type)}</strong></td>
          <td><code>${escapeHtml(String(tok.lexeme))}</code></td>
          <td style="color:#FBBF24;">${escapeHtml(JSON.stringify(tok.value))}</td>
        `;
        tokensBody.appendChild(tr);
      });
    }

    // 2. AST Visual Tree & Formatted Text
    const astTreeContainer = document.getElementById("astTreeContainer");
    const astTextContainer = document.getElementById("astTextContainer");
    if (data.ast) {
      astTextContainer.textContent = data.ast.formatted || "(No formatted AST)";
      if (data.ast.tree) {
        astTreeContainer.innerHTML = "";
        astTreeContainer.appendChild(renderAstTreeNode(data.ast.tree));
      }
    }

    // 3. Symbol Table
    const statesBody = document.getElementById("symbolsStatesBody");
    const eventsBody = document.getElementById("symbolsEventsBody");
    if (data.symbols) {
      statesBody.innerHTML = "";
      if (data.symbols.states && data.symbols.states.length > 0) {
        data.symbols.states.forEach(s => {
          const tr = document.createElement("tr");
          tr.innerHTML = `
            <td><code>${escapeHtml(s.name)}</code></td>
            <td><span class="pill">${escapeHtml(s.type)}</span></td>
            <td style="color:#FBBF24;">${escapeHtml(JSON.stringify(s.initial_value))}</td>
            <td>Line ${s.line}, Col ${s.column}</td>
          `;
          statesBody.appendChild(tr);
        });
      } else {
        statesBody.innerHTML = '<tr><td colspan="4" class="empty-state">No states defined.</td></tr>';
      }

      eventsBody.innerHTML = "";
      if (data.symbols.events && data.symbols.events.length > 0) {
        data.symbols.events.forEach(e => {
          const tr = document.createElement("tr");
          tr.innerHTML = `
            <td><strong style="color:var(--primary);">${escapeHtml(e.name)}</strong></td>
            <td>Line ${e.line}, Col ${e.column}</td>
          `;
          eventsBody.appendChild(tr);
        });
      } else {
        eventsBody.innerHTML = '<tr><td colspan="2" class="empty-state">No events declared.</td></tr>';
      }
    }

    // 4. Semantic Analysis Card
    const semanticCard = document.getElementById("semanticStatusCard");
    if (data.error && data.error.stage === "SEMANTIC") {
      semanticCard.innerHTML = `
        <div style="display:flex; align-items:center; gap:0.6rem; color:var(--danger); font-weight:700; margin-bottom:0.5rem;">
          <span style="font-size:1.2rem;">✗</span>
          <span>SEMANTIC ANALYSIS FAILED</span>
        </div>
        <p style="color:var(--danger);">${escapeHtml(data.error.message)}</p>
      `;
    } else if (data.semantic && data.semantic.status === "UNRESOLVED_IDENTIFIERS") {
      semanticCard.innerHTML = `
        <div style="display:flex; align-items:center; gap:0.6rem; color:var(--warning); font-weight:700; margin-bottom:0.5rem;">
          <span style="font-size:1.2rem;">⚠️</span>
          <span>UNRESOLVED IDENTIFIERS IN CONSTRAINTS</span>
        </div>
        <p style="color:var(--warning);">${escapeHtml(data.semantic.message)}</p>
      `;
    } else if (data.error && data.error.stage === "TEMPORAL" && data.error.message && data.error.message.includes("Undefined event")) {
      semanticCard.innerHTML = `
        <div style="display:flex; align-items:center; gap:0.6rem; color:var(--warning); font-weight:700; margin-bottom:0.5rem;">
          <span style="font-size:1.2rem;">⚠️</span>
          <span>UNRESOLVED EVENT IDENTIFIER IN CONSTRAINT</span>
        </div>
        <p style="color:var(--warning);">${escapeHtml(data.error.message)}</p>
      `;
    } else if (data.semantic) {
      semanticCard.innerHTML = `
        <div style="display:flex; align-items:center; gap:0.6rem; color:var(--success); font-weight:700; margin-bottom:0.5rem;">
          <span style="font-size:1.2rem;">✓</span>
          <span>SEMANTIC ANALYSIS SUCCESSFUL</span>
        </div>
        <p>${escapeHtml(data.semantic.message || "All states and events are well-typed and in scope.")}</p>
      `;
    }

    // 5. Static Temporal Constraints
    const temporalBody = document.getElementById("temporalStaticBody");
    if (data.temporal && data.temporal.constraints) {
      temporalBody.innerHTML = "";
      if (data.temporal.constraints.length > 0) {
        data.temporal.constraints.forEach(c => {
          const tr = document.createElement("tr");
          const isValid = c.status === "VALID";
          const pillClass = isValid ? "pill-success" : "pill-danger";
          tr.innerHTML = `
            <td><strong>${escapeHtml(c.source)}</strong></td>
            <td><strong>${escapeHtml(c.target)}</strong></td>
            <td><code>${escapeHtml(c.raw_duration)}</code></td>
            <td><strong style="color:var(--primary);">${c.duration_ms} ms</strong></td>
            <td>Line ${c.line}, Col ${c.column}</td>
            <td><span class="pill ${pillClass}">${escapeHtml(c.status || "VALID")}</span></td>
          `;
          temporalBody.appendChild(tr);
        });
      } else {
        temporalBody.innerHTML = '<tr><td colspan="6" class="empty-state">No static temporal constraints defined.</td></tr>';
      }
    } else if (data.error && data.error.stage === "TEMPORAL") {
      temporalBody.innerHTML = `<tr><td colspan="6" class="empty-state" style="color:var(--danger); font-weight:600;">Temporal Analysis Failed: ${escapeHtml(data.error.message)}</td></tr>`;
    }

    // 6. IR Table
    const irBody = document.getElementById("irTableBody");
    if (data.ir && data.ir.instructions) {
      irBody.innerHTML = "";
      data.ir.instructions.forEach(ins => {
        const tr = document.createElement("tr");
        tr.innerHTML = `
          <td>${ins.source_line || "-"}</td>
          <td><strong style="color:var(--primary);">${escapeHtml(ins.opcode)}</strong></td>
          <td>${ins.arg1 !== null ? escapeHtml(String(ins.arg1)) : "-"}</td>
          <td style="color:#FBBF24;">${ins.arg2 !== null ? escapeHtml(String(ins.arg2)) : "-"}</td>
          <td>${ins.arg3 !== null ? escapeHtml(String(ins.arg3)) : "-"}</td>
          <td style="color:var(--text-dim); font-style:italic;">${escapeHtml(ins.comment || "")}</td>
        `;
        irBody.appendChild(tr);
      });
    }

    // 7. Optimization Diff & Stats
    if (data.optimization) {
      const stats = data.optimization.stats;
      if (stats) {
        document.getElementById("optInitial").textContent = stats.initial_instructions;
        document.getElementById("optFinal").textContent = stats.final_instructions;
        document.getElementById("optEliminated").textContent = stats.instructions_eliminated;
        document.getElementById("optReduction").textContent = `${stats.reduction_percentage.toFixed(1)}%`;
        document.getElementById("optPasses").textContent = stats.passes;
      }
      document.getElementById("optComparisonText").textContent = data.optimization.formatted || "(No diff available)";
    }

    // 8. Bytecode Table
    if (data.bytecode) {
      renderBytecodeTable(data.bytecode);
    }
  }

  function renderBytecodeTable(bytecode) {
    const bcBody = document.getElementById("bytecodeTableBody");
    const bcTotalBadge = document.getElementById("bcTotalBadge");
    const bcHandlersBadge = document.getElementById("bcHandlersBadge");
    if (!bytecode) return;

    if (bcTotalBadge) bcTotalBadge.textContent = `${bytecode.total_instructions || 0} instructions`;
    const handlerCount = bytecode.handler_table ? Object.keys(bytecode.handler_table).length : 0;
    if (bcHandlersBadge) bcHandlersBadge.textContent = `${handlerCount} handlers`;

    if (bcBody) {
      bcBody.innerHTML = "";
      if (bytecode.instructions && bytecode.instructions.length > 0) {
        bytecode.instructions.forEach(b => {
          const tr = document.createElement("tr");
          tr.innerHTML = `
            <td><code>${String(b.offset).padStart(4, "0")}</code></td>
            <td><strong style="color:var(--primary);">${escapeHtml(b.opcode)}</strong></td>
            <td style="color:#FBBF24;">${b.arg !== null ? escapeHtml(String(b.arg)) : "-"}</td>
            <td>${b.source_line || "-"}</td>
            <td style="color:var(--text-dim); font-style:italic;">${escapeHtml(b.comment || "")}</td>
          `;
          bcBody.appendChild(tr);
        });
      } else {
        bcBody.innerHTML = '<tr><td colspan="5" class="empty-state">No bytecode instructions available.</td></tr>';
      }
    }
  }

  // Render AST tree view
  function renderAstTreeNode(node) {
    const el = document.createElement("div");
    el.className = "ast-node";

    const header = document.createElement("div");
    header.className = "ast-node-header";

    if (node.type === "Program") {
      header.innerHTML = `<span class="ast-node-type">Program:</span> <strong>${escapeHtml(node.system_name)}</strong> (Line ${node.line})`;
      el.appendChild(header);

      if (node.declarations && node.declarations.length > 0) {
        const declsGroup = document.createElement("div");
        declsGroup.className = "ast-node";
        declsGroup.innerHTML = `<div class="ast-node-header"><span class="ast-node-type">Declarations (${node.declarations.length})</span></div>`;
        node.declarations.forEach(d => declsGroup.appendChild(renderAstTreeNode(d)));
        el.appendChild(declsGroup);
      }

      if (node.handlers && node.handlers.length > 0) {
        const hGroup = document.createElement("div");
        hGroup.className = "ast-node";
        hGroup.innerHTML = `<div class="ast-node-header"><span class="ast-node-type">Handlers (${node.handlers.length})</span></div>`;
        node.handlers.forEach(h => hGroup.appendChild(renderAstTreeNode(h)));
        el.appendChild(hGroup);
      }

      if (node.constraints && node.constraints.length > 0) {
        const cGroup = document.createElement("div");
        cGroup.className = "ast-node";
        cGroup.innerHTML = `<div class="ast-node-header"><span class="ast-node-type">Constraints (${node.constraints.length})</span></div>`;
        node.constraints.forEach(c => cGroup.appendChild(renderAstTreeNode(c)));
        el.appendChild(cGroup);
      }
    } else if (node.type === "StateDecl") {
      header.innerHTML = `<span>State:</span> <code>${escapeHtml(node.name)}</code> = <span class="ast-node-val">${escapeHtml(JSON.stringify(node.initial_value))}</span> [${node.lit_type}]`;
      el.appendChild(header);
    } else if (node.type === "EventDecl") {
      header.innerHTML = `<span>Event:</span> <strong>${escapeHtml(node.name)}</strong>`;
      el.appendChild(header);
    } else if (node.type === "Handler") {
      header.innerHTML = `<span>Handler:</span> on <strong>${escapeHtml(node.event_name)}</strong>`;
      el.appendChild(header);
      if (node.assignments) {
        node.assignments.forEach(a => el.appendChild(renderAstTreeNode(a)));
      }
    } else if (node.type === "Assignment") {
      header.innerHTML = `<span>Assignment:</span> <code>${escapeHtml(node.state_name)}</code> = <span class="ast-node-val">${escapeHtml(JSON.stringify(node.value))}</span>`;
      el.appendChild(header);
    } else if (node.type === "Constraint") {
      const dur = node.duration || node.raw_duration || (node.amount && node.unit ? `${node.amount}${node.unit}` : "");
      header.innerHTML = `<span>Constraint:</span> <strong>${escapeHtml(node.source_event)}</strong> &rarr; <strong>${escapeHtml(node.target_event)}</strong> within <code>${escapeHtml(dur)}</code>`;
      el.appendChild(header);
    } else {
      header.textContent = JSON.stringify(node);
      el.appendChild(header);
    }

    return el;
  }

  // =============================================================
  // Renderers for Execution & Simulation
  // =============================================================
  function renderSimulationOutputs(data) {
    if (!data) return;

    // 1. Sidebar Summary Card
    sideSysName.textContent = data.system_name || data.system || "-";
    const simStats = data.simulation || {};
    sideSysSpan.textContent = (simStats.start_time_ms !== undefined)
      ? `${simStats.start_time_ms} - ${simStats.end_time_ms} ms (${simStats.duration_ms} ms)`
      : "-";

    const totalEvents = data.summary ? data.summary.total_events : (data.events ? data.events.length : 0);
    const totalMutations = data.summary ? data.summary.total_state_changes : 0;
    sideSysCounts.textContent = `${totalEvents} / ${totalMutations}`;

    const satisfied = data.summary ? data.summary.constraints_satisfied : 0;
    const checked = data.summary ? data.summary.constraints_checked : (data.temporal_checks ? data.temporal_checks.length : 0);
    sideSysConstraints.textContent = `${satisfied} / ${checked} satisfied`;

    // 2. VM Execution Log
    document.getElementById("vmExecutionLog").textContent = data.formatted_log || "(Execution completed)";

    // 3. Simulation Trace Table
    const simTraceBody = document.getElementById("simTraceBody");
    simTraceBody.innerHTML = "";
    if (data.events && data.events.length > 0) {
      data.events.forEach(ev => {
        const tr = document.createElement("tr");
        const mutStr = ev.state_changes && ev.state_changes.length > 0
          ? ev.state_changes.map(c => `${c.variable}: ${c.old_value} &rarr; ${c.new_value}`).join(", ")
          : "<span style='color:var(--text-muted);'>none</span>";

        tr.innerHTML = `
          <td><strong>${ev.timestamp_ms} ms</strong></td>
          <td><strong style="color:var(--primary);">${escapeHtml(ev.event)}</strong></td>
          <td>${ev.priority !== undefined ? ev.priority : 10}</td>
          <td>${ev.seq_id !== undefined ? ev.seq_id : 0}</td>
          <td>${ev.handler_executed ? '<span class="pill pill-success">Executed</span>' : '<span class="pill">No Handler</span>'}</td>
          <td style="font-family:var(--font-mono); font-size:0.75rem;">${mutStr}</td>
        `;
        simTraceBody.appendChild(tr);
      });
    } else {
      simTraceBody.innerHTML = '<tr><td colspan="6" class="empty-state">No events dispatched.</td></tr>';
    }

    // 4. Temporal Verification Table
    const vBody = document.getElementById("verificationTableBody");
    vBody.innerHTML = "";
    const checks = data.temporal_checks || [];
    if (checks.length > 0) {
      checks.forEach(tc => {
        const tr = document.createElement("tr");
        let pillClass = "pill-success";
        let statusText = tc.status;

        if (tc.status === "SATISFIED") {
          if (tc.elapsed_ms === tc.limit_ms) {
            statusText = "SATISFIED (EXACT BOUNDARY)";
          }
          pillClass = "pill-success";
        } else if (tc.status === "VIOLATED") {
          pillClass = "pill-danger";
        } else {
          pillClass = "pill-warning";
        }

        const elapsed = tc.elapsed_ms !== null && tc.elapsed_ms !== undefined ? `${tc.elapsed_ms} ms` : "N/A (Timeout)";
        const targetTime = tc.target_timestamp_ms !== null && tc.target_timestamp_ms !== undefined ? `${tc.target_timestamp_ms} ms` : "Never";

        tr.innerHTML = `
          <td><strong>${escapeHtml(tc.source_event)}</strong></td>
          <td><strong>${escapeHtml(tc.target_event)}</strong></td>
          <td>${tc.source_timestamp_ms} ms</td>
          <td>${targetTime}</td>
          <td>${elapsed}</td>
          <td>${tc.limit_ms} ms</td>
          <td><span class="pill ${pillClass}">${statusText}</span></td>
        `;
        vBody.appendChild(tr);
      });
    } else {
      vBody.innerHTML = '<tr><td colspan="7" class="empty-state">No temporal constraints registered.</td></tr>';
    }

    // 5. State Transitions
    renderStateTransitions(data);

    // 6. Interactive SVG Timeline
    renderInteractiveTimeline(data);

    // 7. Telemetry JSON Display
    const jsonStr = data.telemetry_json || JSON.stringify(data, null, 2);
    document.getElementById("telemetryJsonDisplay").textContent = jsonStr;
  }

  function renderStateTransitions(data, filter = "") {
    const transitionsBody = document.getElementById("stateTransitionsBody");
    const countBadge = document.getElementById("stateCountBadge");
    transitionsBody.innerHTML = "";

    const list = [];
    if (data.state_transitions && data.state_transitions.length > 0) {
      list.push(...data.state_transitions);
    } else if (data.events) {
      data.events.forEach(ev => {
        if (ev.state_changes) {
          ev.state_changes.forEach(sc => {
            list.push({
              timestamp_ms: ev.timestamp_ms,
              event: ev.event,
              variable: sc.variable,
              old_value: sc.old_value,
              new_value: sc.new_value,
            });
          });
        }
      });
    }

    const filtered = list.filter(item => {
      if (!filter) return true;
      const f = filter.toLowerCase();
      return (item.variable && item.variable.toLowerCase().includes(f)) ||
             (item.event && item.event.toLowerCase().includes(f));
    });

    countBadge.textContent = `${filtered.length} mutations`;

    if (filtered.length === 0) {
      transitionsBody.innerHTML = '<tr><td colspan="4" class="empty-state">No state mutations recorded.</td></tr>';
      return;
    }

    filtered.forEach(sc => {
      const tr = document.createElement("tr");
      tr.innerHTML = `
        <td><strong>${sc.timestamp_ms} ms</strong></td>
        <td><strong style="color:var(--primary);">${escapeHtml(sc.event || "-")}</strong></td>
        <td><code>${escapeHtml(sc.variable)}</code></td>
        <td style="font-family:var(--font-mono);">${escapeHtml(JSON.stringify(sc.old_value))} &rarr; <strong style="color:var(--primary);">${escapeHtml(JSON.stringify(sc.new_value))}</strong></td>
      `;
      transitionsBody.appendChild(tr);
    });
  }

  // =============================================================
  // SVG Timeline Renderer
  // =============================================================
  function renderInteractiveTimeline(data) {
    const svg = document.getElementById("interactiveTimelineSvg");
    svg.innerHTML = "";

    const events = data.events || [];
    const checks = data.temporal_checks || [];
    if (events.length === 0 && checks.length === 0) return;

    let maxTime = 1000;
    events.forEach(e => { if (e.timestamp_ms > maxTime) maxTime = e.timestamp_ms; });
    checks.forEach(c => {
      if (c.source_timestamp_ms > maxTime) maxTime = c.source_timestamp_ms;
      if (c.target_timestamp_ms !== null && c.target_timestamp_ms > maxTime) maxTime = c.target_timestamp_ms;
    });

    // Provide headroom
    maxTime = Math.ceil(maxTime * 1.15);

    const padLeft = 70;
    const padRight = 70;
    const svgWidth = svg.clientWidth || 800;
    const usableWidth = Math.max(300, svgWidth - padLeft - padRight);
    const timeToX = (t) => padLeft + (t / maxTime) * usableWidth;

    const axisY = 60;

    // Time Axis Line
    const axisLine = document.createElementNS("http://www.w3.org/2000/svg", "line");
    axisLine.setAttribute("x1", padLeft);
    axisLine.setAttribute("y1", axisY);
    axisLine.setAttribute("x2", padLeft + usableWidth);
    axisLine.setAttribute("y2", axisY);
    axisLine.setAttribute("stroke", "#475569");
    axisLine.setAttribute("stroke-width", "2");
    svg.appendChild(axisLine);

    // Ticks
    const tickSteps = 5;
    for (let i = 0; i <= tickSteps; i++) {
      const tVal = Math.round((maxTime / tickSteps) * i);
      const x = timeToX(tVal);

      const tick = document.createElementNS("http://www.w3.org/2000/svg", "line");
      tick.setAttribute("x1", x);
      tick.setAttribute("y1", axisY - 5);
      tick.setAttribute("x2", x);
      tick.setAttribute("y2", axisY + 5);
      tick.setAttribute("stroke", "#64748B");
      svg.appendChild(tick);

      const label = document.createElementNS("http://www.w3.org/2000/svg", "text");
      label.setAttribute("x", x);
      label.setAttribute("y", axisY + 20);
      label.setAttribute("fill", "#94A3B8");
      label.setAttribute("font-size", "11");
      label.setAttribute("text-anchor", "middle");
      label.textContent = `${tVal} ms`;
      svg.appendChild(label);
    }

    // Event markers
    events.forEach((ev, idx) => {
      const x = timeToX(ev.timestamp_ms);

      // Circle
      const circle = document.createElementNS("http://www.w3.org/2000/svg", "circle");
      circle.setAttribute("cx", x);
      circle.setAttribute("cy", axisY);
      circle.setAttribute("r", "6");
      circle.setAttribute("fill", "#38BDF8");
      circle.setAttribute("stroke", "#0B0F17");
      circle.setAttribute("stroke-width", "2");
      svg.appendChild(circle);

      // Label (alternate height for anti-collision)
      const labelY = (idx % 2 === 0) ? axisY - 14 : axisY - 26;
      const label = document.createElementNS("http://www.w3.org/2000/svg", "text");
      label.setAttribute("x", x);
      label.setAttribute("y", labelY);
      label.setAttribute("fill", "#F1F5F9");
      label.setAttribute("font-size", "11");
      label.setAttribute("font-weight", "600");
      label.setAttribute("text-anchor", "middle");
      label.textContent = ev.event;
      svg.appendChild(label);
    });

    // Constraint interval bars
    let barY = 110;
    checks.forEach(tc => {
      const xSrc = timeToX(tc.source_timestamp_ms);
      const xTgt = tc.target_timestamp_ms !== null ? timeToX(tc.target_timestamp_ms) : (padLeft + usableWidth);
      const color = tc.status === "SATISFIED" ? "#10B981" : (tc.status === "VIOLATED" ? "#EF4444" : "#F59E0B");

      const intervalLine = document.createElementNS("http://www.w3.org/2000/svg", "line");
      intervalLine.setAttribute("x1", xSrc);
      intervalLine.setAttribute("y1", barY);
      intervalLine.setAttribute("x2", xTgt);
      intervalLine.setAttribute("y2", barY);
      intervalLine.setAttribute("stroke", color);
      intervalLine.setAttribute("stroke-width", "4");
      if (tc.status === "TIMEOUT") {
        intervalLine.setAttribute("stroke-dasharray", "6,4");
      }
      svg.appendChild(intervalLine);

      // End ticks
      [xSrc, xTgt].forEach(cx => {
        const endTick = document.createElementNS("http://www.w3.org/2000/svg", "line");
        endTick.setAttribute("x1", cx);
        endTick.setAttribute("y1", barY - 4);
        endTick.setAttribute("x2", cx);
        endTick.setAttribute("y2", barY + 4);
        endTick.setAttribute("stroke", color);
        endTick.setAttribute("stroke-width", "2");
        svg.appendChild(endTick);
      });

      // Constraint text
      const cText = document.createElementNS("http://www.w3.org/2000/svg", "text");
      cText.setAttribute("x", (xSrc + xTgt) / 2);
      cText.setAttribute("y", barY - 6);
      cText.setAttribute("fill", color);
      cText.setAttribute("font-size", "10");
      cText.setAttribute("font-weight", "700");
      cText.setAttribute("text-anchor", "middle");
      cText.textContent = `${tc.source_event} -> ${tc.target_event} (${tc.status} \u2022 limit ${tc.limit_ms}ms)`;
      svg.appendChild(cText);

      barY += 34;
    });

    svg.setAttribute("height", Math.max(160, barY + 20));
  }

  // =============================================================
  // .seqc Binary Inspector Renderer
  // =============================================================
  function renderSeqcMetadata(data) {
    if (!data) return;
    const magicEl = document.getElementById("seqcMagic");
    if (magicEl) magicEl.textContent = data.magic || "SEQC";
    const verEl = document.getElementById("seqcVersion");
    if (verEl) verEl.textContent = `${data.version || 1} (Version ${data.version || 1})`;
    const flagsEl = document.getElementById("seqcFlags");
    if (flagsEl) flagsEl.textContent = `0x${(data.flags || 0).toString(16).padStart(4, "0").toUpperCase()}`;
    const lenEl = document.getElementById("seqcPayloadLen");
    if (lenEl) lenEl.textContent = `${(data.payload_len || data.size_bytes || 0).toLocaleString()} bytes`;
    const crcEl = document.getElementById("seqcChecksum");
    if (crcEl) crcEl.textContent = data.crc32_hex || "-";
    const instEl = document.getElementById("seqcInstructions");
    if (instEl) instEl.textContent = `${data.total_instructions || 0} instructions`;
    const sysEl = document.getElementById("seqcSystemName");
    if (sysEl) sysEl.textContent = data.system_name || data.system || "-";
    const handEl = document.getElementById("seqcHandlers");
    if (handEl) handEl.textContent = `${data.handler_count !== undefined ? data.handler_count : (data.handler_table ? Object.keys(data.handler_table).length : "-")} handlers`;
  }

  // =============================================================
  // File Upload Handlers (Telemetry JSON, .seqc, .seq)
  // =============================================================
  inputTelemetryFile.addEventListener("change", (e) => {
    const file = e.target.files[0];
    if (!file) return;

    const reader = new FileReader();
    reader.onload = (evt) => {
      try {
        const json = JSON.parse(evt.target.result);
        lastSimulationData = json;
        renderSimulationOutputs(json);

        // Show the required confirmation card
        const card = document.getElementById("telemetryLoadedCard");
        document.getElementById("telemetryFilename").textContent = file.name;
        document.getElementById("telemetrySystemName").textContent = json.system || json.system_name || "Unknown";
        document.getElementById("telemetryEventCount").textContent = json.summary ? json.summary.total_events : (json.events ? json.events.length : 0);
        document.getElementById("telemetryMutationCount").textContent = json.summary ? json.summary.total_state_changes : 0;

        const satisfied = json.summary ? json.summary.constraints_satisfied : 0;
        const totalChecked = json.summary ? json.summary.constraints_checked : (json.temporal_checks ? json.temporal_checks.length : 0);
        document.getElementById("telemetryConstraintsStatus").textContent = `${satisfied}/${totalChecked} satisfied`;

        card.style.display = "flex";
        switchStage("telemetry");
        setStatus("success", "TELEMETRY LOADED");
      } catch (err) {
        alert("Invalid telemetry JSON file: " + err.message);
      }
    };
    reader.readAsText(file);
  });

  if (inputSeqFile) {
    inputSeqFile.addEventListener("change", (e) => {
      const file = e.target.files[0];
      if (!file) return;

      if (file.name.endsWith(".seqc")) {
        loadSeqcFile(file);
        return;
      }

      currentExecutionMode = "source";
      loadedSeqcData = null;
      const reader = new FileReader();
      reader.onload = (evt) => {
        sourceEditor.value = evt.target.result;
        updateLineNumbers();
        activeFileName.textContent = file.name;
        dirtyIndicator.classList.remove("dirty");
        switchStage("editor");
        setStatus("ready", "FILE LOADED");
      };
      reader.readAsText(file);
    });
  }

  function loadSeqcFile(file) {
    if (!file) return;
    const reader = new FileReader();
    reader.onload = async (evt) => {
      try {
        clearAllStageData(true);
        hideError();
        setStatus("compiling", "LOADING .SEQC...");

        const arrayBuf = evt.target.result;
        const base64Str = arrayBufferToBase64(arrayBuf);

        // Pre-configure reasonable simulation events if empty or if loading the violated example
        if (file.name.includes("Violat") && (!timelineInput.value || timelineInput.value.includes("500ms"))) {
          timelineInput.value = "EmergencyDetected@0ms, TeamDispatched@6000ms, IncidentResolved@7000ms";
        } else if (!timelineInput.value) {
          timelineInput.value = "EmergencyDetected@0ms, TeamDispatched@500ms, IncidentResolved@1500ms";
        }

        const res = await fetch("/api/load-seqc", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            base64_data: base64Str,
            events: timelineInput.value,
            filename: file.name,
          }),
        });

        const data = await res.json();
        if (!data.success && data.error && !data.simulation) {
          showError(data.error);
          renderDiagnostics(data.diagnostics && data.diagnostics.length > 0 ? data.diagnostics : [data.error]);
          return;
        }

        currentExecutionMode = "seqc";
        loadedSeqcData = {
          filename: file.name,
          base64: base64Str,
          metadata: data.seqc_metadata,
          bytecode: data.bytecode,
        };
        lastSeqcEmitData = {
          base64_data: base64Str,
          filename: file.name,
          ...(data.seqc_metadata || {}),
        };

        // Informative source editor banner
        sourceEditor.value = [
          "// ============================================================",
          `// COMPILED SEQUENT BINARY CONTAINER (.seqc)`,
          `// File: ${file.name}`,
          `// System Name: ${data.system_name || data.seqc_metadata?.system_name || "Unknown"}`,
          `// Total Instructions: ${data.seqc_metadata?.total_instructions || 0}`,
          `// Handler Count: ${data.seqc_metadata?.handler_count || 0}`,
          `// CRC32 Checksum: ${data.seqc_metadata?.crc32_hex || "-"}`,
          "//",
          "// Source compilation stages (Lexer/Parser/Semantic/IR) bypassed.",
          "// Program is executed directly from verified bytecode in the SEQUENT VM.",
          "// Modify the simulation timeline above and click 'Run' to execute.",
          "// ============================================================"
        ].join("\n");
        clearDiagnostics();
        renderDiagnostics(data.diagnostics || []);
        renderAssistant(null, data, true);
        dirtyIndicator.classList.remove("dirty");
        activeFileName.textContent = file.name;

        // Render stage outputs
        if (data.seqc_metadata) renderSeqcMetadata(data.seqc_metadata);
        if (data.bytecode) renderBytecodeTable(data.bytecode);
        if (data.stages_status) updateSidebarStageIcons(data.stages_status);

        lastSimulationData = data;
        renderSimulationOutputs(data);

        btnDownloadSeqcBinary.disabled = false;
        setStatus(data.success ? "success" : "warning", "SEQC BINARY LOADED");
        switchStage("seqc");
      } catch (err) {
        showError({ stage: "SEQC", category: "LOAD ERROR", message: err.message });
        renderDiagnostics([{ stage: "SEQC", severity: "ERROR", message: err.message, explanation: "Failed to parse SEQC binary container.", suggestion: "Verify file integrity." }]);
      }
    };
    reader.readAsArrayBuffer(file);
  }

  async function runSeqcExecution() {
    if (!loadedSeqcData || !loadedSeqcData.base64) {
      showError({ stage: "SEQC", category: "EXECUTION ERROR", message: "No .seqc binary loaded." });
      return;
    }

    hideError();
    setStatus("compiling", "RUNNING .SEQC...");

    try {
      const res = await fetch("/api/run-seqc", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          base64_data: loadedSeqcData.base64,
          events: timelineInput.value,
          filename: loadedSeqcData.filename,
        }),
      });

      const data = await res.json();
      if (!data.success && data.error && !data.simulation) {
        showError(data.error);
        renderDiagnostics(data.diagnostics && data.diagnostics.length > 0 ? data.diagnostics : [data.error]);
        return;
      }

      if (data.stages_status) updateSidebarStageIcons(data.stages_status);
      if (data.seqc_metadata) renderSeqcMetadata(data.seqc_metadata);
      if (data.bytecode) renderBytecodeTable(data.bytecode);

      lastSimulationData = data;
      renderSimulationOutputs(data);
      renderDiagnostics(data.diagnostics || []);
      renderAssistant(null, data, true);

      if (data.success) {
        setStatus("success", "SUCCESS");
      } else {
        setStatus("warning", "CONSTRAINTS BREACHED");
      }
      switchStage("verification");
    } catch (err) {
      showError({ stage: "SEQC", category: "EXECUTION ERROR", message: err.message });
      renderDiagnostics([{ stage: "SEQC", severity: "ERROR", message: err.message, explanation: "Error executing .seqc binary container.", suggestion: "Verify file integrity." }]);
    }
  }

  function handleRunClick() {
    if (currentExecutionMode === "seqc") {
      runSeqcExecution();
    } else {
      runCompileAndExecute();
    }
  }

  function handleCompileClick() {
    if (currentExecutionMode === "seqc") {
      switchStage("bytecode");
      setStatus("ready", "BINARY LOADED");
    } else {
      runCompileOnly();
    }
  }

  inputSeqcBinary.addEventListener("change", (e) => {
    const file = e.target.files[0];
    if (file) loadSeqcFile(file);
  });

  if (inputSeqcBinaryHeader) {
    inputSeqcBinaryHeader.addEventListener("change", (e) => {
      const file = e.target.files[0];
      if (!file) return;
      if (file.name.endsWith(".seq") || file.name.endsWith(".txt")) {
        currentExecutionMode = "source";
        loadedSeqcData = null;
        const reader = new FileReader();
        reader.onload = (evt) => {
          sourceEditor.value = evt.target.result;
          updateLineNumbers();
          activeFileName.textContent = file.name;
          dirtyIndicator.classList.remove("dirty");
          switchStage("editor");
          setStatus("ready", "FILE LOADED");
        };
        reader.readAsText(file);
      } else {
        loadSeqcFile(file);
      }
    });
  }

  function arrayBufferToBase64(buffer) {
    let binary = "";
    const bytes = new Uint8Array(buffer);
    const len = bytes.byteLength;
    for (let i = 0; i < len; i++) {
      binary += String.fromCharCode(bytes[i]);
    }
    return window.btoa(binary);
  }

  // =============================================================
  // Examples Catalog Loading & Selection
  // =============================================================
  async function loadExamplesCatalog() {
    try {
      const res = await fetch("/api/examples");
      examplesCatalog = await res.json();

      exampleSelect.innerHTML = "";
      quickExamplesList.innerHTML = "";

      examplesCatalog.forEach((ex, idx) => {
        // Dropdown option
        const opt = document.createElement("option");
        opt.value = ex.id;
        opt.textContent = `${ex.name} (${ex.filename})`;
        exampleSelect.appendChild(opt);

        // Quick list item
        const li = document.createElement("li");
        li.innerHTML = `<strong>${escapeHtml(ex.name)}</strong> <span style="color:var(--text-dim);">${escapeHtml(ex.filename)}</span>`;
        li.addEventListener("click", () => applyExample(ex));
        quickExamplesList.appendChild(li);
      });

      // Apply first example by default
      if (examplesCatalog.length > 0) {
        applyExample(examplesCatalog[0]);
      }
    } catch (err) {
      console.error("Failed to load examples catalog:", err);
    }
  }

  function applyExample(ex) {
    clearAllStageData();
    clearDiagnostics();
    currentExecutionMode = "source";
    loadedSeqcData = null;
    currentExample = ex;
    exampleSelect.value = ex.id;
    sourceEditor.value = ex.source;
    timelineInput.value = ex.default_events || "";
    activeFileName.textContent = ex.filename;
    updateLineNumbers();
    dirtyIndicator.classList.remove("dirty");
    hideError();
    setStatus("ready", "READY");
    switchStage("editor");
  }

  exampleSelect.addEventListener("change", (e) => {
    const ex = examplesCatalog.find(item => item.id === e.target.value);
    if (ex) applyExample(ex);
  });

  btnReloadExample.addEventListener("click", () => {
    if (currentExample) applyExample(currentExample);
  });

  btnResetTimeline.addEventListener("click", () => {
    if (currentExample) timelineInput.value = currentExample.default_events || "";
  });

  // =============================================================
  // Utility Buttons & Actions
  // =============================================================
  btnCompile.addEventListener("click", handleCompileClick);
  btnRun.addEventListener("click", handleRunClick);
  btnCompileRun.addEventListener("click", handleRunClick);
  btnEmitSeqc.addEventListener("click", emitSeqcBinary);

  btnClearEditor.addEventListener("click", () => {
    clearAllStageData();
    clearDiagnostics();
    currentExecutionMode = "source";
    loadedSeqcData = null;
    sourceEditor.value = "";
    timelineInput.value = "";
    activeFileName.textContent = "untitled.seq";
    updateLineNumbers();
    dirtyIndicator.classList.add("dirty");
    hideError();
    setStatus("ready", "READY");
    switchStage("editor");
  });

  btnCopySource.addEventListener("click", () => {
    navigator.clipboard.writeText(sourceEditor.value);
    btnCopySource.textContent = "Copied!";
    setTimeout(() => { btnCopySource.textContent = "Copy"; }, 1500);
  });

  btnDownloadSeq.addEventListener("click", () => {
    downloadBlob(sourceEditor.value, activeFileName.textContent || "program.seq", "text/plain");
  });

  btnDownloadSeqcBinary.addEventListener("click", () => {
    const emitData = lastSeqcEmitData || (loadedSeqcData ? { base64_data: loadedSeqcData.base64, filename: loadedSeqcData.filename } : null);
    if (!emitData || !emitData.base64_data) return;
    const binaryStr = window.atob(emitData.base64_data);
    const len = binaryStr.length;
    const bytes = new Uint8Array(len);
    for (let i = 0; i < len; i++) {
      bytes[i] = binaryStr.charCodeAt(i);
    }
    const blob = new Blob([bytes], { type: "application/octet-stream" });
    const link = document.createElement("a");
    link.href = URL.createObjectURL(blob);
    link.download = emitData.filename || "compiled.seqc";
    link.click();
    URL.revokeObjectURL(link.href);
  });

  document.getElementById("btnCopyTelemetry").addEventListener("click", () => {
    const text = document.getElementById("telemetryJsonDisplay").textContent;
    navigator.clipboard.writeText(text);
    alert("Telemetry JSON copied to clipboard!");
  });

  document.getElementById("btnDownloadTelemetry").addEventListener("click", () => {
    const text = document.getElementById("telemetryJsonDisplay").textContent;
    downloadBlob(text, "telemetry.json", "application/json");
  });

  // Toggle formatted / raw telemetry
  document.getElementById("btnTelemetryFormatted").addEventListener("click", (e) => {
    document.querySelectorAll("#view-telemetry .toggle-btn").forEach(b => b.classList.remove("active"));
    e.target.classList.add("active");
    if (lastSimulationData) {
      document.getElementById("telemetryJsonDisplay").textContent = JSON.stringify(lastSimulationData, null, 2);
    }
  });

  document.getElementById("btnTelemetryRaw").addEventListener("click", (e) => {
    document.querySelectorAll("#view-telemetry .toggle-btn").forEach(b => b.classList.remove("active"));
    e.target.classList.add("active");
    if (lastSimulationData) {
      document.getElementById("telemetryJsonDisplay").textContent = JSON.stringify(lastSimulationData);
    }
  });

  // AST view toggles
  document.getElementById("btnAstViewTree").addEventListener("click", (e) => {
    document.querySelectorAll("#view-parser .toggle-btn").forEach(b => b.classList.remove("active"));
    e.target.classList.add("active");
    document.getElementById("astTreeContainer").style.display = "block";
    document.getElementById("astTextContainer").style.display = "none";
  });

  document.getElementById("btnAstViewText").addEventListener("click", (e) => {
    document.querySelectorAll("#view-parser .toggle-btn").forEach(b => b.classList.remove("active"));
    e.target.classList.add("active");
    document.getElementById("astTreeContainer").style.display = "none";
    document.getElementById("astTextContainer").style.display = "block";
  });

  // State mutation filter
  document.getElementById("stateFilterInput").addEventListener("input", (e) => {
    if (lastSimulationData) {
      renderStateTransitions(lastSimulationData, e.target.value);
    }
  });

  // Token filter
  document.getElementById("tokenFilterInput").addEventListener("input", (e) => {
    if (!lastCompiledData || !lastCompiledData.tokens) return;
    const filter = e.target.value.toLowerCase();
    const rows = document.querySelectorAll("#tokensTableBody tr");
    rows.forEach(r => {
      r.style.display = r.textContent.toLowerCase().includes(filter) ? "" : "none";
    });
  });

  function downloadBlob(content, filename, contentType) {
    const blob = new Blob([content], { type: contentType });
    const link = document.createElement("a");
    link.href = URL.createObjectURL(blob);
    link.download = filename;
    link.click();
    URL.revokeObjectURL(link.href);
  }

  // =============================================================
  // Dock Tabs, Collapse Toggle, and Templates Event Listeners
  // =============================================================
  document.querySelectorAll(".dock-tab-btn").forEach(btn => {
    btn.addEventListener("click", () => {
      const tabId = btn.dataset.dockTab;
      document.querySelectorAll(".dock-tab-btn").forEach(b => b.classList.remove("active"));
      btn.classList.add("active");
      document.querySelectorAll(".dock-panel").forEach(p => p.classList.remove("active"));
      const targetPanel = document.getElementById(`dockPanel${tabId.charAt(0).toUpperCase() + tabId.slice(1)}`);
      if (targetPanel) targetPanel.classList.add("active");

      // Expand dock if currently collapsed
      if (editorDock && editorDock.classList.contains("collapsed")) {
        editorDock.classList.remove("collapsed");
        if (btnToggleDock) btnToggleDock.textContent = "▾";
      }
    });
  });

  if (btnToggleDock) {
    btnToggleDock.addEventListener("click", () => {
      if (editorDock) {
        editorDock.classList.toggle("collapsed");
        btnToggleDock.textContent = editorDock.classList.contains("collapsed") ? "▴" : "▾";
      }
    });
  }

  if (btnTemplatesDropdown && templatesDropdownMenu) {
    btnTemplatesDropdown.addEventListener("click", (e) => {
      e.stopPropagation();
      const isVis = templatesDropdownMenu.style.display === "block";
      templatesDropdownMenu.style.display = isVis ? "none" : "block";
    });

    document.addEventListener("click", () => {
      templatesDropdownMenu.style.display = "none";
    });

    templatesDropdownMenu.querySelectorAll(".dropdown-item-custom").forEach(item => {
      item.addEventListener("click", (e) => {
        e.stopPropagation();
        const tmpl = item.dataset.template;
        templatesDropdownMenu.style.display = "none";
        insertTemplate(tmpl);
      });
    });
  }

  document.querySelectorAll(".btn-template-insert").forEach(btn => {
    btn.addEventListener("click", () => {
      const tmpl = btn.dataset.template;
      insertTemplate(tmpl);
    });
  });

  // =============================================================
  // Boot
  // =============================================================
  loadExamplesCatalog();
  updateLineNumbers();
});
