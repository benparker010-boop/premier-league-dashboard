/* Kit Tracker scanner — shared by setup and collection modes.
   Reads its config from #scan-root data attributes. */
(function () {
  "use strict";

  var root = document.getElementById("scan-root");
  if (!root) return;

  var JOB_ID = parseInt(root.dataset.jobId, 10);
  var SCAN_TYPE = root.dataset.scanType; // 'SETUP' | 'COLLECTION'
  var ENDPOINT = root.dataset.endpoint;

  var staffSelect = document.getElementById("staff-select");
  var cameraToggle = document.getElementById("camera-toggle");
  var readerEl = document.getElementById("reader");
  var banner = document.getElementById("scan-banner");
  var manualForm = document.getElementById("manual-form");
  var manualInput = document.getElementById("manual-code");

  if (!staffSelect || !cameraToggle) return; // scanner closed for this job

  var scanner = null;
  var running = false;
  var busy = false; // a scan request is in flight
  var lastCode = "";
  var lastCodeAt = 0;
  var audioCtx = null;
  var bannerTimer = null;

  /* ---------------------------------------------------- staff selection */

  var savedStaff = null;
  try { savedStaff = localStorage.getItem("kitTrackerStaff"); } catch (e) { /* private mode */ }
  if (savedStaff) {
    for (var i = 0; i < staffSelect.options.length; i++) {
      if (staffSelect.options[i].value === savedStaff) {
        staffSelect.value = savedStaff;
        break;
      }
    }
  }

  function updateCameraButton() {
    cameraToggle.disabled = !staffSelect.value;
    cameraToggle.textContent = running ? "⏹ Stop camera" :
      (staffSelect.value ? "📷 Start camera" : "📷 Choose your name first");
  }

  staffSelect.addEventListener("change", function () {
    try { localStorage.setItem("kitTrackerStaff", staffSelect.value); } catch (e) { /* ignore */ }
    updateCameraButton();
  });
  updateCameraButton();

  /* ---------------------------------------------------- feedback */

  function ensureAudio() {
    // Must be called from a user gesture (iOS Safari requirement).
    if (!audioCtx) {
      try {
        audioCtx = new (window.AudioContext || window.webkitAudioContext)();
      } catch (e) { /* no audio, vibration still works */ }
    }
    if (audioCtx && audioCtx.state === "suspended") audioCtx.resume();
  }

  function beep(freq, duration, when) {
    if (!audioCtx) return;
    var osc = audioCtx.createOscillator();
    var gain = audioCtx.createGain();
    osc.type = "sine";
    osc.frequency.value = freq;
    gain.gain.value = 0.25;
    osc.connect(gain);
    gain.connect(audioCtx.destination);
    var t = audioCtx.currentTime + (when || 0);
    osc.start(t);
    osc.stop(t + duration);
  }

  function feedback(kind) {
    if (kind === "good") {
      beep(1046, 0.12);
      if (navigator.vibrate) navigator.vibrate(80);
    } else if (kind === "warn") {
      beep(660, 0.15);
      if (navigator.vibrate) navigator.vibrate([60, 60, 60]);
    } else {
      beep(220, 0.2);
      beep(220, 0.2, 0.28);
      if (navigator.vibrate) navigator.vibrate([120, 80, 120]);
    }
  }

  var BANNER_KIND = {
    added: "good",
    collected: "good",
    duplicate: "warn",
    not_expected: "warn",
    on_other_job: "warn",
    busy: "warn",
    not_recognized: "bad",
    error: "bad"
  };

  var JOB_BADGE_CLASS = {
    "Live": "info",
    "Collection in Progress": "purple",
    "Completed": "ok",
    "Items Missing": "danger"
  };

  function updateJobBadge(status) {
    var badge = document.getElementById("job-badge");
    if (!badge || !status) return;
    badge.textContent = status;
    badge.className = "badge badge-" + (JOB_BADGE_CLASS[status] || "muted");
  }

  function showBanner(result, message) {
    var kind = BANNER_KIND[result] || "bad";
    banner.hidden = false;
    banner.textContent = message;
    banner.className = "scan-banner scan-banner-" + kind;
    if (bannerTimer) clearTimeout(bannerTimer);
    bannerTimer = setTimeout(function () { banner.hidden = true; }, 5000);
    feedback(kind);
  }

  /* ---------------------------------------------------- page updates */

  function nowLabel() {
    return "just now";
  }

  function onSetupAdded(payload) {
    var list = document.getElementById("scan-list");
    var hint = document.getElementById("empty-hint");
    if (hint) hint.remove();
    if (!list) return;
    var li = document.createElement("li");
    li.className = "kit-item just-scanned";
    li.dataset.eqid = String(payload.item.id);

    var state = document.createElement("span");
    state.className = "kit-state";
    state.textContent = "📦";

    var body = document.createElement("span");
    body.className = "kit-body";
    var name = document.createElement("strong");
    name.textContent = payload.item.name;
    var code = document.createElement("span");
    code.className = "mono muted";
    code.textContent = " " + payload.item.kit_id;
    var meta = document.createElement("span");
    meta.className = "muted small";
    meta.textContent = "by " + staffSelect.value + " · " + nowLabel();
    body.appendChild(name);
    body.appendChild(code);
    body.appendChild(document.createElement("br"));
    body.appendChild(meta);

    li.appendChild(state);
    li.appendChild(body);
    list.insertBefore(li, list.firstChild);

    var count = document.getElementById("kit-count");
    if (count && payload.counts) count.textContent = String(payload.counts.expected);
  }

  function onCollected(payload) {
    var row = document.querySelector('#expected-list .kit-item[data-eqid="' + payload.item.id + '"]');
    if (row) {
      row.classList.add("done", "just-scanned");
      var state = row.querySelector(".kit-state");
      if (state) state.textContent = "✅";
      var meta = row.querySelector(".kit-meta");
      if (meta) meta.textContent = "Collected by " + staffSelect.value + " · " + nowLabel();
    }
    updateProgress(payload.counts);
    updateJobBadge(payload.job_status);
  }

  function updateProgress(counts) {
    if (!counts) return;
    var fill = document.getElementById("progress-fill");
    var text = document.getElementById("progress-text");
    if (fill) {
      var pct = counts.expected ? (counts.collected / counts.expected) * 100 : 0;
      fill.style.width = pct + "%";
    }
    if (text) {
      text.dataset.expected = String(counts.expected);
      text.dataset.collected = String(counts.collected);
      text.textContent = counts.collected + " of " + counts.expected + " collected" +
        (counts.collected === counts.expected && counts.expected > 0 ? " — all done! 🎉" : "");
    }
  }

  /* ---------------------------------------------------- scan handling */

  function processCode(code) {
    code = (code || "").trim();
    if (!code || busy) return false;

    // Ignore rapid re-reads of the same label while it's still in frame.
    var now = Date.now();
    if (code === lastCode && now - lastCodeAt < 3000) return false;
    lastCode = code;
    lastCodeAt = now;

    busy = true;
    fetch(ENDPOINT, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        job_id: JOB_ID,
        scan_type: SCAN_TYPE,
        staff_name: staffSelect.value,
        code: code
      })
    })
      .then(function (resp) { return resp.json(); })
      .then(function (payload) {
        showBanner(payload.result, payload.message);
        if (payload.result === "added") onSetupAdded(payload);
        if (payload.result === "collected") onCollected(payload);
        if (payload.result === "duplicate" && SCAN_TYPE === "COLLECTION") {
          updateProgress(payload.counts);
        }
      })
      .catch(function () {
        showBanner("error", "Network error — scan not saved. Try again.");
      })
      .finally(function () {
        busy = false;
      });
    return true;
  }

  /* ---------------------------------------------------- camera */

  function startCamera() {
    if (!window.Html5Qrcode) {
      showBanner("error", "Scanner library failed to load — check your connection.");
      return;
    }
    ensureAudio();
    if (!scanner) scanner = new Html5Qrcode("reader");
    cameraToggle.disabled = true;
    scanner
      .start(
        { facingMode: "environment" },
        { fps: 10, qrbox: { width: 220, height: 220 } },
        function (decodedText) { processCode(decodedText); },
        function () { /* per-frame decode misses — ignore */ }
      )
      .then(function () {
        running = true;
        readerEl.classList.add("live");
        cameraToggle.disabled = false;
        updateCameraButton();
      })
      .catch(function (err) {
        cameraToggle.disabled = false;
        updateCameraButton();
        var msg = String(err || "");
        if (msg.indexOf("NotAllowedError") !== -1 || msg.indexOf("Permission") !== -1) {
          showBanner("error", "Camera permission denied. Allow camera access in your browser settings.");
        } else if (!window.isSecureContext) {
          showBanner("error", "Camera needs HTTPS (or localhost). Open this page over a secure connection.");
        } else {
          showBanner("error", "Could not start camera: " + msg);
        }
      });
  }

  function stopCamera() {
    if (!scanner || !running) return;
    scanner
      .stop()
      .then(function () {
        running = false;
        readerEl.classList.remove("live");
        updateCameraButton();
      })
      .catch(function () {
        running = false;
        updateCameraButton();
      });
  }

  cameraToggle.addEventListener("click", function () {
    if (running) stopCamera();
    else startCamera();
  });

  window.addEventListener("pagehide", stopCamera);

  /* ---------------------------------------------------- manual entry */

  if (manualForm) {
    manualForm.addEventListener("submit", function (event) {
      event.preventDefault();
      ensureAudio();
      if (!staffSelect.value) {
        showBanner("error", "Choose your name before scanning.");
        return;
      }
      var value = manualInput.value.trim();
      if (!value) return;
      if (busy) {
        showBanner("busy", "Still saving the previous scan — try again in a second.");
        return; // keep the typed code so it isn't lost
      }
      if (/^\d+$/.test(value)) value = "KIT-" + value; // allow typing just "42"
      lastCode = ""; // manual entry always goes through
      if (processCode(value)) manualInput.value = "";
    });
  }

  /* ------------------------------------------- collection completion */

  var completeForm = document.getElementById("complete-form");
  if (completeForm) {
    completeForm.addEventListener("submit", function (event) {
      var text = document.getElementById("progress-text");
      var expected = text ? parseInt(text.dataset.expected, 10) : 0;
      var collected = text ? parseInt(text.dataset.collected, 10) : 0;
      var remaining = expected - collected;
      var message = remaining > 0
        ? remaining + " item(s) have NOT been scanned back in and will be flagged as MISSING.\n\nMark collection complete anyway?"
        : "All items collected. Mark this job complete?";
      if (!window.confirm(message)) event.preventDefault();
    });
  }
})();
