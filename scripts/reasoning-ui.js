(function (root) {
  var DEFAULT_ENDPOINT = "https://script.google.com/macros/s/AKfycbwyIKBPHCatx1zdei0aYv-l3hZt65e7ph8kCvZubh0qFbsCLc4FXjH33yTwtGKyGPFj/exec";

  function fallbackScrubPHI(raw) {
    return String(raw || "")
      .replace(/(\b(?:patient|patient name|name|pt|client)\s*:\s*)([^\n\r]+)/gi, "\$1[REDACTED]")
      .replace(/\b\d{1,2}[\/\-]\d{1,2}[\/\-]\d{2,4}\b/g, "[DATE]")
      .replace(/\b(?:\+?1[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}\b/g, "[PHONE]")
      .replace(/\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b/gi, "[EMAIL]")
      .replace(/\b\d{3}-\d{2}-\d{4}\b/g, "[SSN]");
  }

  function escapeHtmlSafe(str) {
    return String(str || "")
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;");
  }

  // Cross-checks the eval text in case the model or an older deployment missed the hold flag
  function evaluateClinicalHold(item, rawEx, evalText) {
    var status = (rawEx && rawEx.status) ? String(rawEx.status).toLowerCase().trim() : "active";
    var note = (rawEx && rawEx.note) ? String(rawEx.note).trim() : "";

    if (status === "hold" || status === "restricted" || status === "contraindicated" || /^hold\b/i.test(note)) {
      return { status: "hold", note: note || "MD Protocol Restriction" };
    }

    var baseName = String((item && item.name) || "")
      .replace(/\([^)]*\)/g, " ")
      .toLowerCase()
      .replace(/[^a-z0-9\s]/g, " ")
      .replace(/\s+/g, " ")
      .trim();

    if (!baseName || !evalText) return { status: "active", note: note };

    var nameWords = baseName.split(" ").filter(function (w) {
      return w.length > 2 && w !== "with" && w !== "and" && w !== "the" && w !== "seated" && w !== "standing" && w !== "supine";
    });

    var lines = String(evalText).split(/[\n\r.;]+/);
    for (var i = 0; i < lines.length; i++) {
      var line = lines[i].trim();
      var lowerLine = line.toLowerCase();
      var hasHoldKeyword = /\b(hold|strict hold|no|avoid|contraindicat\w*|do not|restrict\w*|precaution)\b/i.test(lowerLine);
      if (!hasHoldKeyword) continue;

      var matchedWords = nameWords.filter(function (w) {
        return lowerLine.indexOf(w) !== -1;
      });

      if (matchedWords.length >= 2 || (nameWords.length === 1 && matchedWords.length === 1)) {
        return {
          status: "hold",
          note: note || line.replace(/^md\s*precaution\s*:\s*/i, "").trim()
        };
      }
    }

    return { status: "active", note: note };
  }

  // Paints any held exercise card red directly in the DOM
  function applyHoldStylingToDOM() {
    var container = document.getElementById("activeProgramList");
    if (!container || typeof currentProgram === "undefined" || !Array.isArray(currentProgram)) return;

    var rows = container.children;
    currentProgram.forEach(function (item, idx) {
      var row = rows[idx];
      if (!row || !item) return;

      var isHold = String(item.status || "").toLowerCase() === "hold";
      if (!isHold) return;

      row.className = "p-3 rounded-lg border-2 border-[#dc3545] bg-[#fff8f8] shadow-sm space-y-2";

      if (!row.querySelector(".pw-clinical-hold-banner")) {
        var banner = document.createElement("div");
        banner.className = "pw-clinical-hold-banner text-[#dc3545] font-bold px-2 py-1.5 mb-1 text-[11px] border border-[#dc3545] bg-white rounded shadow-sm flex items-start gap-1.5";
        banner.innerHTML =
          '<span class="text-[14px]">⚠️</span>' +
          '<span>CLINICAL HOLD: ' + escapeHtmlSafe(item.note || "MD Protocol Restriction") + '</span>';
        row.insertBefore(banner, row.firstChild);
      }
    });
  }

  function hookRenderActiveProgram() {
    if (typeof window.renderActiveProgram === "function" && !window.renderActiveProgram._pwHoldHooked) {
      var originalRender = window.renderActiveProgram;
      var wrappedRender = function () {
        var result = originalRender.apply(this, arguments);
        applyHoldStylingToDOM();
        return result;
      };
      wrappedRender._pwHoldHooked = true;
      window.renderActiveProgram = wrappedRender;
    }
  }

  function clearExistingRoutine() {
    if (typeof clearProgram === "function") {
      clearProgram();
      return;
    }
    if (typeof currentProgram !== "undefined" && Array.isArray(currentProgram)) {
      currentProgram.length = 0;
    }
    if (typeof currentProgramState !== "undefined" && currentProgramState && Array.isArray(currentProgramState.directives)) {
      currentProgramState.directives.length = 0;
    }
    if (typeof renderDirectiveChips === "function") renderDirectiveChips();
    if (typeof renderActiveProgram === "function") renderActiveProgram();
  }

  function mount(target, options) {
    var ENDPOINT = (options && options.endpoint) ? options.endpoint : DEFAULT_ENDPOINT;

    hookRenderActiveProgram();

    var card = document.createElement("div");
    card.className = "bg-[#11224A] rounded-xl shadow-lg overflow-hidden border border-[#0d1a38] text-white";

    var header = document.createElement("div");
    header.className = "px-4 py-3 flex items-center justify-between bg-[#0a142c] border-b border-[#1d354e]";
    header.innerHTML = `
      <div>
        <h2 class="text-sm font-bold tracking-widest text-white uppercase flex items-center gap-2">
          Clinical Reasoning
        </h2>
        <p class="text-[10px] text-slate-400 mt-0.5 font-medium tracking-wide">Paste eval notes, scrub PHI, then generate a draft program</p>
      </div>
      <button type="button" class="text-slate-400 hover:text-white transition p-1" title="Collapse">▼</button>
    `;

    var bodyPanel = document.createElement("div");
    bodyPanel.className = "p-4 bg-white text-slate-800 space-y-4";

    var grid = document.createElement("div");
    grid.className = "grid grid-cols-1 lg:grid-cols-2 gap-4";

    var leftCol = document.createElement("div");
    leftCol.className = "flex flex-col h-full";
    var leftLabel = document.createElement("label");
    leftLabel.className = "block text-[10px] font-bold text-slate-500 uppercase tracking-widest mb-1.5";
    leftLabel.textContent = "Raw Clinical Notes";
    var rawTextarea = document.createElement("textarea");
    rawTextarea.className = "w-full flex-1 min-h-[140px] p-3 text-[13px] bg-slate-50 border border-slate-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-[#11224A] focus:border-transparent resize-y text-slate-700 font-medium leading-relaxed";
    rawTextarea.placeholder = "Paste patient evaluation, subjective complaints, and objective findings here...";
    leftCol.appendChild(leftLabel);
    leftCol.appendChild(rawTextarea);

    var rightCol = document.createElement("div");
    rightCol.className = "flex flex-col h-full";
    var rightLabel = document.createElement("label");
    rightLabel.className = "block text-[10px] font-bold text-slate-500 uppercase tracking-widest mb-1.5 flex justify-between";
    rightLabel.innerHTML = `<span>Scrubbed Preview (Read-Only)</span><span class="text-blue-500 hidden" id="phiBadge">PHI Detected</span>`;
    var scrubbedTextarea = document.createElement("textarea");
    scrubbedTextarea.className = "w-full flex-1 min-h-[140px] p-3 text-[13px] bg-slate-100 border border-slate-200 rounded-lg focus:outline-none resize-y text-slate-600 font-mono";
    scrubbedTextarea.readOnly = true;
    scrubbedTextarea.placeholder = "Scrubbed notes will appear here...";
    rightCol.appendChild(rightLabel);
    rightCol.appendChild(scrubbedTextarea);

    grid.appendChild(leftCol);
    grid.appendChild(rightCol);

    var actionRow = document.createElement("div");
    actionRow.className = "flex items-center gap-3 pt-2";

    var scrubBtn = document.createElement("button");
    scrubBtn.className = "px-4 py-2 bg-white border-2 border-[#11224A] text-[#11224A] text-[13px] font-bold rounded-lg hover:bg-slate-50 transition shadow-sm";
    scrubBtn.textContent = "Scrub PHI";

    var approveBtn = document.createElement("button");
    approveBtn.className = "px-5 py-2 bg-[#b81d32] text-white text-[13px] font-bold rounded-lg hover:bg-[#9a1829] transition shadow-sm disabled:opacity-50 disabled:cursor-not-allowed";
    approveBtn.textContent = "Approve & Generate Program";

    var statusText = document.createElement("div");
    statusText.className = "text-[12px] font-medium text-slate-500 ml-auto";

    actionRow.appendChild(scrubBtn);
    actionRow.appendChild(approveBtn);
    actionRow.appendChild(statusText);

    bodyPanel.appendChild(grid);
    bodyPanel.appendChild(actionRow);

    var footerNotice = document.createElement("div");
    footerNotice.className = "px-4 py-2 bg-slate-50 border-t border-slate-100 text-[10px] text-slate-400 font-medium";
    footerNotice.textContent = "Automated redaction can miss identifiers. Review the preview before approving; only the scrubbed text is sent.";

    card.appendChild(header);
    card.appendChild(bodyPanel);
    card.appendChild(footerNotice);

    if (target) target.appendChild(card);

    var scrubbedText = null;
    var busy = false;

    function setStatus(msg, type) {
      statusText.textContent = msg;
      statusText.className = "text-[12px] font-bold ml-auto " + (type === "error" ? "text-red-600" : type === "info" ? "text-blue-600" : "text-green-600");
    }

    function setBusy(isBusy) {
      busy = isBusy;
      approveBtn.disabled = isBusy;
      scrubBtn.disabled = isBusy;
      rawTextarea.disabled = isBusy;
      if (isBusy) {
        approveBtn.innerHTML = `<span class="animate-pulse">Reasoning...</span>`;
      } else {
        approveBtn.textContent = "Approve & Generate Program";
      }
    }

    scrubBtn.addEventListener("click", function () {
      if (busy) return;
      var raw = rawTextarea.value.trim();
      if (!raw) {
        setStatus("Please paste clinical notes first.", "error");
        return;
      }
      var clean = typeof scrubPHI === "function" ? scrubPHI(raw) : fallbackScrubPHI(raw);
      scrubbedText = clean;
      scrubbedTextarea.value = clean;
      setStatus("PHI scrubbed. Review the preview.", "info");
    });

    approveBtn.addEventListener("click", function () {
      if (busy || scrubbedText === null) {
        setStatus("Click 'Scrub PHI' first before generating.", "error");
        return;
      }
      var payloadText = scrubbedText;
      setBusy(true);
      setStatus("Reasoning with Gemini...", "info");

      fetch(ENDPOINT, {
        method: "POST",
        redirect: "follow",
        headers: { "Content-Type": "text/plain;charset=utf-8" },
        body: JSON.stringify({ evalText: payloadText })
      })
      .then(function (res) {
        if (!res.ok) throw new Error("Service returned HTTP " + res.status);
        return res.text();
      })
      .then(function (text) {
        var data;
        try {
          data = JSON.parse(text);
        } catch (parseErr) {
          throw new Error("Invalid JSON from Apps Script: " + text.slice(0, 120));
        }

        if (!data || data.success !== true) {
          throw new Error((data && data.error) || "Unknown error from engine");
        }

        hookRenderActiveProgram();
        clearExistingRoutine();

        if (!data.exercises || data.exercises.length === 0) {
          setStatus("No exercises were suggested.", "error");
          setBusy(false);
          return;
        }

        var addedCount = 0;
        var holdCount = 0;

        if (typeof addToProgram === "function") {
          data.exercises.forEach(function (ex) {
            var exId = typeof ex === "string" ? ex : ex.id;
            var addedItem = addToProgram(exId, "Bilateral", null, false);
            if (addedItem) {
              var check = evaluateClinicalHold(addedItem, ex, payloadText);
              addedItem.status = check.status;
              addedItem.note = check.note;
              if (check.status === "hold") holdCount++;
              addedCount++;
            }
          });
        }

        if (typeof renderActiveProgram === "function") renderActiveProgram();
        applyHoldStylingToDOM();

        var msg = "Added " + addedCount + " exercises." + (holdCount ? " (" + holdCount + " Clinical Hold flagged)" : " Safety checks applied.");
        setStatus(msg, holdCount ? "error" : "success");
        setBusy(false);
      })
      .catch(function (err) {
        console.error("Reasoning Engine Fetch Error:", err);
        setBusy(false);
        setStatus("Error: " + err.message, "error");
      });
    });

    return card;
  }

  var api = { mount: mount, ENDPOINT: DEFAULT_ENDPOINT };

  function autoMount() {
    var host = document.getElementById("reasoningEngineMount");
    if (host) mount(host);
  }

  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", autoMount);
  else autoMount();

  root.PhysioReasoningUI = api;
})(window);