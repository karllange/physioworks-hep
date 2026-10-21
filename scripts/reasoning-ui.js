(function (root) {
  var DEFAULT_ENDPOINT = "https://script.google.com/macros/s/AKfycbwyIKBPHCatx1zdei0aYv-l3hZt65e7ph8kCvZubh0qFbsCLc4FXjH33yTwtGKyGPFj/exec";

  function fallbackScrubPHI(raw) {
    return String(raw || "")
      .replace(/(\b(?:patient|patient name|name|pt|client)\s*:\s*)([^\n\r]+)/gi, "$1[REDACTED]")
      .replace(/\b(?:pt|patient)\s+is\s+an?\s+/gi, "Individual is ")
      .replace(/\b\d{1,3}\s*(?:yo|y\.o\.|y\/o|yr|year|years)\s*(?:old)?\s*(?:m|f|male|female)?\b/gi, "[AGE/GENDER]")
      .replace(/\b(?:male|female)\b/gi, "[GENDER]")
      .replace(/\b\d{1,2}[\/\-]\d{1,2}[\/\-]\d{2,4}\b/g, "[DATE]")
      .replace(/\b(?:dob|d\.o\.b\.)\s*:\s*[^\n\r,;]+/gi, "[DOB REDACTED]")
      .replace(/\b(?:\+?1[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}\b/g, "[PHONE]")
      .replace(/\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b/gi, "[EMAIL]")
      .replace(/\b\d{3}-\d{2}-\d{4}\b/g, "[SSN]")
      .replace(/\b(?:mrn|acc|id|fin)\s*#?\s*[:\-]?\s*[A-Z0-9\-]+\b/gi, "[MRN REDACTED]");
  }

  function resolveScrubber() {
    if (typeof root.scrubPHI === "function") return root.scrubPHI;
    if (typeof root.sanitizeClinicalText === "function") return root.sanitizeClinicalText;
    if (root.PhysioPhiScrubber && typeof root.PhysioPhiScrubber.sanitize === "function") {
      return function (text) { return root.PhysioPhiScrubber.sanitize(text); };
    }
    return fallbackScrubPHI;
  }

  function initReasoningUI() {
    var rawTextarea = document.getElementById("reasoning-raw-notes") || document.querySelector("textarea[placeholder*='evaluation']");
    var scrubbedTextarea = document.getElementById("reasoning-scrubbed-notes") || document.querySelector("textarea[placeholder*='Scrubbed notes']");
    var scrubBtn = document.getElementById("reasoning-scrub-btn") || (function () {
      var btns = document.querySelectorAll("button");
      for (var i = 0; i < btns.length; i++) {
        if (/scrub\s*phi/i.test(btns[i].textContent)) return btns[i];
      }
      return null;
    })();
    var approveBtn = document.getElementById("reasoning-approve-btn") || (function () {
      var btns = document.querySelectorAll("button");
      for (var i = 0; i < btns.length; i++) {
        if (/approve\s*&\s*generate/i.test(btns[i].textContent)) return btns[i];
      }
      return null;
    })();
    var statusEl = document.getElementById("reasoning-status") || (function () {
      var span = document.createElement("span");
      span.id = "reasoning-status";
      span.style.marginLeft = "12px";
      span.style.fontSize = "13px";
      span.style.fontWeight = "500";
      if (scrubBtn && scrubBtn.parentNode) {
        scrubBtn.parentNode.appendChild(span);
      }
      return span;
    })();

    if (!rawTextarea || !scrubbedTextarea || !scrubBtn) {
      return;
    }

    var busy = false;
    var scrubbedText = "";

    function setStatus(msg, type) {
      if (!statusEl) return;
      statusEl.textContent = msg || "";
      if (type === "error") {
        statusEl.style.color = "#dc2626";
      } else if (type === "success") {
        statusEl.style.color = "#16a34a";
      } else {
        statusEl.style.color = "#2563eb";
      }
    }

    scrubBtn.addEventListener("click", function () {
      if (busy) return;
      var raw = rawTextarea.value.trim();
      if (!raw) {
        setStatus("Please paste clinical notes first.", "error");
        return;
      }
      var scrubFn = resolveScrubber();
      var clean = scrubFn(raw);
      scrubbedText = clean;
      scrubbedTextarea.value = clean;
      setStatus("PHI scrubbed. Review the preview.", "info");
    });

    if (approveBtn) {
      approveBtn.addEventListener("click", function () {
        if (busy) return;
        var textToSend = (scrubbedTextarea.value || scrubbedText || "").trim();
        if (!textToSend) {
          setStatus("Please scrub notes before submitting.", "error");
          return;
        }

        busy = true;
        approveBtn.disabled = true;
        setStatus("Analyzing notes & synthesizing protocol...", "info");

        var endpoint = root.PHYSIO_REASONING_ENDPOINT || DEFAULT_ENDPOINT;

        fetch(endpoint, {
          method: "POST",
          headers: { "Content-Type": "text/plain;charset=utf-8" },
          body: JSON.stringify({
            action: "generate_hep",
            notes: textToSend,
            timestamp: new Date().toISOString()
          })
        })
          .then(function (res) {
            if (!res.ok) throw new Error("HTTP error " + res.status);
            return res.json();
          })
          .then(function (data) {
            busy = false;
            approveBtn.disabled = false;
            setStatus("Program synthesized successfully!", "success");

            if (typeof root.applySynthesizedProgram === "function") {
              root.applySynthesizedProgram(data);
            } else if (root.PhysioHEP && typeof root.PhysioHEP.loadProgram === "function") {
              root.PhysioHEP.loadProgram(data);
            } else {
              window.dispatchEvent(new CustomEvent("physio:program-synthesized", { detail: data }));
            }
          })
          .catch(function (err) {
            busy = false;
            approveBtn.disabled = false;
            setStatus("Generation failed: " + (err.message || "Network error"), "error");
          });
      });
    }
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", initReasoningUI);
  } else 
    initReasoningUI();
  }

  root.fallbackScrubPHI = fallbackScrubPHI;
  root.resolveScrubber = resolveScrubber;
})(typeof window !== "undefined" ? window : this);
