/* ── CHATBOT YARO IA ───────────────────────────────────────── */
(function () {
  let _open    = false;
  let _loading = false;
  let _history = [];

  function toggleChat() {
    _open = !_open;
    const win   = document.getElementById("chatWindow");
    const fab   = document.getElementById("chatFab");
    const badge = document.getElementById("chatFabBadge");
    if (win) { win.classList.toggle("open", _open); win.setAttribute("aria-hidden", !_open); }
    if (fab) fab.classList.toggle("open", _open);
    if (_open) {
      if (badge) badge.style.display = "none";
      const isMobile = window.innerWidth <= 600;
      if (!isMobile) {
        setTimeout(() => { const inp = document.getElementById("chatInput"); if (inp) inp.focus(); }, 300);
      }
      scrollMessages();
    } else {
      if (document.activeElement) document.activeElement.blur();
    }
  }

  function scrollMessages() {
    const box = document.getElementById("chatMessages");
    if (box) box.scrollTop = box.scrollHeight;
  }

  function addMessage(role, text) {
    const box = document.getElementById("chatMessages");
    if (!box) return;
    const div = document.createElement("div");
    div.className = "chat-msg " + (role === "user" ? "chat-msg-user" : "chat-msg-bot");
    const bub = document.createElement("div");
    bub.className = "chat-bubble";
    bub.textContent = text;
    div.appendChild(bub);
    box.appendChild(div);
    scrollMessages();
    return div;
  }

  function showTyping() {
    const box = document.getElementById("chatMessages");
    if (!box) return null;
    const div = document.createElement("div");
    div.className = "chat-msg chat-msg-bot chat-typing";
    div.innerHTML = '<div class="chat-bubble"><span class="chat-typing-dot"></span><span class="chat-typing-dot"></span><span class="chat-typing-dot"></span></div>';
    box.appendChild(div);
    scrollMessages();
    return div;
  }

  async function sendChat() {
    if (_loading) return;
    const inp  = document.getElementById("chatInput");
    const btn  = document.getElementById("chatSend");
    const text = inp ? inp.value.trim() : "";
    if (!text) return;
    inp.value = "";
    addMessage("user", text);
    _history.push({ role: "user", content: text });
    _loading = true;
    if (btn) btn.disabled = true;
    const typing = showTyping();
    try {
      const ctrl  = new AbortController();
      const timer = setTimeout(() => ctrl.abort(), 25000);
      const res   = await fetch("/api/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ message: text, history: _history.slice(-6) }),
        signal: ctrl.signal,
      });
      clearTimeout(timer);
      const data = await res.json();
      if (typing) typing.remove();
      const reply = data.reply || "Je n'ai pas pu répondre. Veuillez réessayer.";
      addMessage("bot", reply);
      _history.push({ role: "assistant", content: reply });
      if (_history.length > 20) _history = _history.slice(-20);
      if (!_open) {
        const badge = document.getElementById("chatFabBadge");
        if (badge) badge.style.display = "flex";
      }
    } catch (e) {
      if (typing) typing.remove();
      addMessage("bot", e.name === "AbortError"
        ? "La réponse prend trop de temps. Veuillez réessayer."
        : "Une erreur s'est produite. Veuillez réessayer.");
    } finally {
      _loading = false;
      if (btn) btn.disabled = false;
      if (inp) inp.focus();
    }
  }

  // ══════════════════════════════════════════════════════════
  // ── EFFETS TONNERRE ROUGE & FEU TÉKÉ ──────────────────
  // ══════════════════════════════════════════════════════════

  const fxStyle = document.createElement("style");
  fxStyle.textContent = `
    @keyframes yaro-bolt {
      0%   { transform: translate(0,0) scaleY(1);   opacity: 1; }
      60%  { opacity: 1; }
      100% { transform: translate(var(--bx),var(--by)) scaleY(.4); opacity: 0; }
    }
    @keyframes yaro-ember {
      0%   { transform: translate(0,0) scale(1) rotate(0deg);   opacity: 1; }
      100% { transform: translate(var(--ex),var(--ey)) scale(0) rotate(var(--er));  opacity: 0; }
    }
    @keyframes yaro-flash {
      0%,100% { box-shadow: 0 0 0px 0px rgba(220,30,30,0); }
      30%     { box-shadow: 0 0 30px 12px rgba(220,30,30,.7); }
      60%     { box-shadow: 0 0 15px 6px rgba(255,100,0,.5); }
    }
    @keyframes yaro-fire-trail {
      0%   { transform: translate(0,0) scale(1);   opacity:.9; filter:blur(1px); }
      100% { transform: translate(var(--fx),var(--fy)) scale(0); opacity:0; filter:blur(5px); }
    }
    @keyframes yaro-red-pulse {
      0%,100% { box-shadow: 0 0 8px 2px rgba(200,20,20,.4), 0 4px 20px rgba(0,0,0,.35); }
      50%     { box-shadow: 0 0 24px 10px rgba(220,50,0,.7), 0 4px 20px rgba(0,0,0,.35); }
    }
    .yaro-dragging {
      animation: yaro-red-pulse 0.4s ease-in-out infinite !important;
      transform: scale(1.1) !important;
    }
  `;
  document.head.appendChild(fxStyle);

  // Éclairs qui partent dans toutes les directions
  function spawnLightning(x, y) {
    const count = 10;
    for (let i = 0; i < count; i++) {
      const angle  = (i / count) * Math.PI * 2 + Math.random() * 0.4;
      const dist   = 50 + Math.random() * 40;
      const bx     = Math.cos(angle) * dist;
      const by     = Math.sin(angle) * dist;
      const colors = ["#FF1A1A", "#FF4400", "#FF2200", "#CC0000", "#FF6600"];
      const color  = colors[Math.floor(Math.random() * colors.length)];
      const w      = 2 + Math.random() * 2;
      const h      = 18 + Math.random() * 16;

      const bolt = document.createElement("div");
      bolt.style.cssText = `
        position:fixed; z-index:99999; pointer-events:none;
        width:${w}px; height:${h}px;
        left:${x - w/2}px; top:${y - h/2}px;
        background: linear-gradient(180deg, #FFF 0%, ${color} 40%, #FF0000 100%);
        border-radius: 2px;
        box-shadow: 0 0 8px ${color}, 0 0 3px #FFF;
        transform-origin: center center;
        transform: rotate(${(angle * 180/Math.PI) + 90}deg);
        --bx:${bx}px; --by:${by}px;
        animation: yaro-bolt ${0.3 + Math.random()*.2}s ease-out forwards;
      `;
      document.body.appendChild(bolt);
      setTimeout(() => bolt.remove(), 600);
    }
  }

  // Flash rouge sur le bouton
  function spawnFlash(fab) {
    fab.style.animation = "yaro-flash 0.35s ease-out";
    setTimeout(() => { fab.style.animation = ""; }, 400);
  }

  // Braises / flammèches
  function spawnEmbers(x, y, count) {
    const fireColors = ["#FF1A00", "#FF4400", "#FF7700", "#FF2200", "#FFAA00", "#CC0000", "#FF3300"];
    for (let i = 0; i < count; i++) {
      const angle = Math.random() * Math.PI * 2;
      const dist  = 25 + Math.random() * 45;
      const ex    = Math.cos(angle) * dist;
      const ey    = Math.sin(angle) * dist - 20;
      const er    = (Math.random() - .5) * 360;
      const size  = 4 + Math.random() * 8;
      const color = fireColors[Math.floor(Math.random() * fireColors.length)];

      const ember = document.createElement("div");
      ember.style.cssText = `
        position:fixed; z-index:99998; pointer-events:none;
        width:${size}px; height:${size + 4}px;
        left:${x - size/2}px; top:${y - size/2}px;
        background: radial-gradient(ellipse at 50% 30%, #FFF 0%, ${color} 50%, #AA0000 100%);
        border-radius: 50% 50% 30% 30%;
        box-shadow: 0 0 6px ${color};
        --ex:${ex}px; --ey:${ey}px; --er:${er}deg;
        animation: yaro-ember ${0.4 + Math.random()*.3}s ease-out forwards;
      `;
      document.body.appendChild(ember);
      setTimeout(() => ember.remove(), 750);
    }
  }

  // Traînée de feu pendant le glissement
  function spawnFireTrail(x, y) {
    const fx    = (Math.random() - .5) * 20;
    const fy    = -(15 + Math.random() * 25);
    const size  = 12 + Math.random() * 12;
    const fireColors = ["#FF1A00","#FF4400","#FF6600","#CC2200","#FF3300"];
    const color = fireColors[Math.floor(Math.random() * fireColors.length)];
    const f = document.createElement("div");
    f.style.cssText = `
      position:fixed; z-index:99998; pointer-events:none;
      width:${size}px; height:${size * 1.4}px;
      left:${x - size/2}px; top:${y - size/2}px;
      background: radial-gradient(ellipse at 50% 30%, #FFEE00 0%, ${color} 45%, rgba(150,0,0,0) 100%);
      border-radius: 50% 50% 30% 30%;
      filter: blur(1px);
      --fx:${fx}px; --fy:${fy}px;
      animation: yaro-fire-trail 0.5s ease-out forwards;
    `;
    document.body.appendChild(f);
    setTimeout(() => f.remove(), 550);
  }

  // ── Protection photo ────────────────────────────────────
  function protectImages() {
    const imgs = document.querySelectorAll(".chat-fab-img, .chat-header-img");
    imgs.forEach(img => {
      img.draggable = false;
      img.addEventListener("contextmenu",  e => e.preventDefault());
      img.addEventListener("touchstart",   e => { /* ne pas stopper pour le drag */ }, { passive: true });
      img.style.cssText += "; -webkit-touch-callout:none; user-select:none; pointer-events:none;";
    });
    // Le bouton lui-même garde les pointer-events pour le drag
    const fab = document.getElementById("chatFab");
    if (fab) {
      fab.addEventListener("contextmenu", e => e.preventDefault());
      fab.style.webkitTouchCallout = "none";
    }
  }

  // ── Bouton déplaçable ───────────────────────────────────
  (function makeDraggable() {
    const fab = document.getElementById("chatFab");
    if (!fab) return;

    protectImages();

    let dragging  = false;
    let hasMoved  = false;
    let startX, startY, origLeft, origBottom;
    let trailTimer = null;

    function getPos(e) {
      return e.touches ? { x: e.touches[0].clientX, y: e.touches[0].clientY }
                       : { x: e.clientX, y: e.clientY };
    }

    function onStart(e) {
      const pos  = getPos(e);
      startX     = pos.x;
      startY     = pos.y;
      hasMoved   = false;
      dragging   = true;

      const rect = fab.getBoundingClientRect();
      origLeft   = rect.left;
      origBottom = window.innerHeight - rect.bottom;
      fab.style.transition = "none";

      // Tonnerre au toucher : éclairs + braises + flash + vibration forte
      spawnLightning(pos.x, pos.y);
      spawnEmbers(pos.x, pos.y, 12);
      spawnFlash(fab);
      if (navigator.vibrate) navigator.vibrate([30, 15, 60, 10, 30]);
    }

    function onMove(e) {
      if (!dragging) return;
      const pos = getPos(e);
      const dx  = pos.x - startX;
      const dy  = pos.y - startY;

      if (Math.abs(dx) > 5 || Math.abs(dy) > 5) {
        if (!hasMoved) {
          hasMoved = true;
          fab.classList.add("yaro-dragging");
          if (navigator.vibrate) navigator.vibrate([20, 10, 20]);
        }
      }
      if (!hasMoved) return;
      e.preventDefault();

      const size   = fab.offsetWidth;
      const margin = 8;
      fab.style.left   = Math.max(margin, Math.min(window.innerWidth  - size - margin, origLeft   + dx)) + "px";
      fab.style.bottom = Math.max(margin, Math.min(window.innerHeight - size - margin, origBottom - dy)) + "px";
      fab.style.right  = "auto";

      // Traînée de feu toutes les 50ms
      if (!trailTimer) {
        const rect = fab.getBoundingClientRect();
        const cx   = rect.left + rect.width  / 2;
        const cy   = rect.top  + rect.height / 2;
        spawnFireTrail(cx, cy);
        spawnFireTrail(cx, cy);
        spawnFireTrail(cx, cy);
        trailTimer = setTimeout(() => { trailTimer = null; }, 50);
      }
    }

    function onEnd(e) {
      if (!dragging) return;
      dragging = false;
      fab.style.transition = "";
      fab.classList.remove("yaro-dragging");

      if (hasMoved) {
        e.preventDefault();
        e.stopPropagation();
        // Explosion finale : éclairs + braises + vibration tonnerre
        const rect = fab.getBoundingClientRect();
        const cx   = rect.left + rect.width  / 2;
        const cy   = rect.top  + rect.height / 2;
        spawnLightning(cx, cy);
        spawnEmbers(cx, cy, 18);
        spawnFlash(fab);
        if (navigator.vibrate) navigator.vibrate([80, 20, 40]);

        // Repositionner fenêtre chat
        const win = document.getElementById("chatWindow");
        if (win) {
          const wLeft = Math.max(8, Math.min(window.innerWidth - win.offsetWidth - 8, rect.left - win.offsetWidth + fab.offsetWidth));
          win.style.bottom = (window.innerHeight - rect.top + 8) + "px";
          win.style.left   = wLeft + "px";
          win.style.right  = "auto";
        }
      } else {
        toggleChat();
      }
    }

    fab.removeAttribute("onclick");
    fab.addEventListener("mousedown",  onStart);
    fab.addEventListener("touchstart", onStart, { passive: true });
    window.addEventListener("mousemove",  onMove);
    window.addEventListener("touchmove",  onMove, { passive: false });
    window.addEventListener("mouseup",    onEnd);
    window.addEventListener("touchend",   onEnd);
  })();

  window.toggleChat = toggleChat;
  window.sendChat   = sendChat;
})();
