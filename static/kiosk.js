/* Kiosk scan logic.
 *
 * The USB reader is in KEYBOARD mode: it "types" the card id into the hidden
 * #capture field and presses Enter. We:
 *   - keep #capture focused at all times (refocus on blur / any click),
 *   - never display the raw number,
 *   - debounce so one physical tap can't fire twice,
 *   - POST to /api/scan, show a big green/red result, then auto-return to neutral.
 */
(function () {
  "use strict";

  var capture = document.getElementById("capture");
  var screen = document.getElementById("screen");
  var bigText = document.getElementById("bigText");
  var subText = document.getElementById("subText");
  var beepToggle = document.getElementById("beepToggle");

  var NEUTRAL_TEXT = "დაადეთ ბარათი";
  var RESET_MS = 2500;          // auto-return to neutral
  var DEBOUNCE_MS = 1200;       // ignore repeat submits within this window

  var resetTimer = null;
  var busy = false;             // a scan request is in flight
  var lastSubmitAt = 0;
  var beepEnabled = false;

  function focusCapture() {
    try { capture.focus(); } catch (e) {}
  }

  function setState(state, big, sub) {
    screen.className = "state-" + state;
    bigText.textContent = big;
    subText.textContent = sub || "";
    // retrigger the pop animation
    screen.classList.remove("flash");
    void screen.offsetWidth;
    screen.classList.add("flash");
  }

  function toNeutral() {
    setState("neutral", NEUTRAL_TEXT, "");
    capture.value = "";
    focusCapture();
  }

  function scheduleReset() {
    if (resetTimer) clearTimeout(resetTimer);
    resetTimer = setTimeout(toNeutral, RESET_MS);
  }

  function beep(ok) {
    if (!beepEnabled) return;
    try {
      var ctx = beep._ctx || (beep._ctx = new (window.AudioContext || window.webkitAudioContext)());
      var osc = ctx.createOscillator();
      var gain = ctx.createGain();
      osc.connect(gain); gain.connect(ctx.destination);
      osc.frequency.value = ok ? 880 : 220;
      gain.gain.value = 0.12;
      osc.start();
      osc.stop(ctx.currentTime + (ok ? 0.12 : 0.30));
    } catch (e) {}
  }

  function showResult(data) {
    if (data && data.status === "ALLOWED") {
      var sub = data.scanned_at ? ("დრო: " + data.scanned_at) : "";
      if (typeof data.remaining === "number") {
        // Show how many meals remain today for this card.
        sub += (sub ? "  •  " : "") + "დარჩა: " + data.remaining;
      }
      setState("allowed", "ნებადართულია", sub);
      beep(true);
    } else {
      var reason = (data && data.reason) ? data.reason : "უარყოფილია";
      setState("denied", "უარყოფილია", reason);
      beep(false);
    }
    scheduleReset();
  }

  function submit(cardId) {
    var now = Date.now();
    if (busy) return;
    if (now - lastSubmitAt < DEBOUNCE_MS) {
      // Same tap bouncing — ignore but keep the field clean.
      capture.value = "";
      return;
    }
    lastSubmitAt = now;
    busy = true;

    fetch("/api/scan", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ card_id: cardId }),
    })
      .then(function (r) { return r.json(); })
      .then(function (data) { showResult(data); })
      .catch(function () {
        setState("denied", "უარყოფილია", "კავშირის შეცდომა");
        scheduleReset();
      })
      .finally(function () {
        busy = false;
        capture.value = "";
        focusCapture();
      });
  }

  // Enter submits the captured id.
  capture.addEventListener("keydown", function (e) {
    if (e.key === "Enter") {
      e.preventDefault();
      var val = (capture.value || "").trim();
      capture.value = "";
      if (val.length > 0) submit(val);
    }
  });

  // Always keep focus on the capture field.
  capture.addEventListener("blur", function () {
    setTimeout(focusCapture, 0);
  });
  document.addEventListener("click", function (e) {
    if (e.target === beepToggle) return;
    focusCapture();
  });
  document.addEventListener("visibilitychange", function () {
    if (!document.hidden) focusCapture();
  });
  window.addEventListener("focus", focusCapture);

  beepToggle.addEventListener("click", function () {
    beepEnabled = !beepEnabled;
    beepToggle.classList.toggle("on", beepEnabled);
    focusCapture();
  });

  // Init
  toNeutral();
  focusCapture();
  setInterval(focusCapture, 1500); // safety net for stubborn focus loss
})();
