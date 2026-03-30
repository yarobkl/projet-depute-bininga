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
      if (window.innerWidth > 600) setTimeout(() => { const i = document.getElementById("chatInput"); if(i) i.focus(); }, 300);
      scrollMessages();
    } else {
      if (document.activeElement) document.activeElement.blur();
    }
  }

  function scrollMessages() {
    const b = document.getElementById("chatMessages");
    if (b) b.scrollTop = b.scrollHeight;
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
    const inp = document.getElementById("chatInput");
    const btn = document.getElementById("chatSend");
    const text = inp ? inp.value.trim() : "";
    if (!text) return;
    inp.value = "";
    addMessage("user", text);
    _history.push({ role: "user", content: text });
    _loading = true;
    if (btn) btn.disabled = true;
    const typing = showTyping();
    try {
      const ctrl = new AbortController();
      const timer = setTimeout(() => ctrl.abort(), 25000);
      const res = await fetch("/api/chat", {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ message: text, history: _history.slice(-6) }), signal: ctrl.signal,
      });
      clearTimeout(timer);
      const data = await res.json();
      if (typing) typing.remove();
      const reply = data.reply || "Je n'ai pas pu répondre. Veuillez réessayer.";
      addMessage("bot", reply);
      _history.push({ role: "assistant", content: reply });
      if (_history.length > 20) _history = _history.slice(-20);
      if (!_open) { const b = document.getElementById("chatFabBadge"); if(b) b.style.display="flex"; }
    } catch(e) {
      if (typing) typing.remove();
      addMessage("bot", e.name === "AbortError" ? "La réponse prend trop de temps." : "Une erreur s'est produite.");
    } finally {
      _loading = false;
      if (btn) btn.disabled = false;
      if (inp) inp.focus();
    }
  }

  // ══════════════════════════════════════════════════════════
  // ── FEU PUR — EFFETS TÉKÉ ─────────────────────────────
  // ══════════════════════════════════════════════════════════

  // Keyframes feu
  const s = document.createElement("style");
  s.textContent = `
    @keyframes yaro-flame {
      0%   { transform:translate(0,0) scale(1) rotate(0deg);   opacity:.95; }
      50%  { opacity:.7; }
      100% { transform:translate(var(--fx),var(--fy)) scale(0) rotate(var(--fr)); opacity:0; }
    }
    @keyframes yaro-spark {
      0%   { transform:translate(0,0) scale(1);   opacity:1; }
      100% { transform:translate(var(--sx),var(--sy)) scale(0); opacity:0; }
    }
    @keyframes yaro-fire-pulse {
      0%,100% { box-shadow:0 0 10px 3px rgba(200,30,0,.5), 0 4px 20px rgba(0,0,0,.35); }
      50%     { box-shadow:0 0 28px 10px rgba(255,80,0,.75), 0 4px 20px rgba(0,0,0,.35); }
    }
    .yaro-on-fire {
      animation: yaro-fire-pulse .35s ease-in-out infinite !important;
      transform: scale(1.08) !important;
    }
  `;
  document.head.appendChild(s);

  function spawnFlame(x, y) {
    // Palette feu : rouge profond → orange → jaune au centre
    const palettes = [
      ["#FF0000","#CC0000"],
      ["#FF3300","#AA0000"],
      ["#FF5500","#DD2200"],
      ["#FF7700","#FF3300"],
      ["#FFAA00","#FF5500"],
    ];
    const pal  = palettes[Math.floor(Math.random() * palettes.length)];
    const w    = 10 + Math.random() * 14;
    const h    = w * (1.5 + Math.random());
    const fx   = (Math.random() - .5) * 22;
    const fy   = -(28 + Math.random() * 35); // monte vers le haut
    const fr   = (Math.random() - .5) * 30;
    const dur  = 0.45 + Math.random() * .3;

    const f = document.createElement("div");
    f.style.cssText = `
      position:fixed;z-index:99999;pointer-events:none;
      width:${w}px;height:${h}px;
      left:${x - w/2}px;top:${y - h*.6}px;
      background:radial-gradient(ellipse at 50% 80%, #FFEE44 0%, ${pal[0]} 45%, ${pal[1]} 80%, rgba(80,0,0,0) 100%);
      border-radius:50% 50% 35% 35%;
      filter:blur(.5px);
      --fx:${fx}px;--fy:${fy}px;--fr:${fr}deg;
      animation:yaro-flame ${dur}s ease-out forwards;
    `;
    document.body.appendChild(f);
    setTimeout(() => f.remove(), (dur + .05) * 1000);
  }

  function spawnSpark(x, y) {
    const count = 8;
    for (let i = 0; i < count; i++) {
      const angle = (i / count) * Math.PI * 2;
      const dist  = 30 + Math.random() * 40;
      const sparkColors = ["#FF0000","#FF4400","#FF7700","#FFAA00","#FFD700","#CC0000"];
      const color = sparkColors[Math.floor(Math.random() * sparkColors.length)];
      const size  = 3 + Math.random() * 5;
      const e = document.createElement("div");
      e.style.cssText = `
        position:fixed;z-index:99999;pointer-events:none;
        width:${size}px;height:${size}px;
        left:${x - size/2}px;top:${y - size/2}px;
        background:${color};border-radius:50%;
        box-shadow:0 0 5px ${color};
        --sx:${Math.cos(angle)*dist}px;--sy:${Math.sin(angle)*dist - 15}px;
        animation:yaro-spark .5s ease-out forwards;
      `;
      document.body.appendChild(e);
      setTimeout(() => e.remove(), 550);
    }
  }

  // ── Protection photo ────────────────────────────────────
  function protectPhoto() {
    // CSS global anti-longpress
    const ps = document.createElement("style");
    ps.textContent = `
      .chat-fab-img, .chat-header-img {
        -webkit-touch-callout: none !important;
        -webkit-user-select: none !important;
        user-select: none !important;
        pointer-events: none !important;
      }
      #chatFab {
        -webkit-touch-callout: none !important;
      }
    `;
    document.head.appendChild(ps);

    // Bloquer contextmenu sur tout le widget
    ["chatFab","chatWindow"].forEach(id => {
      const el = document.getElementById(id);
      if (el) el.addEventListener("contextmenu", e => e.preventDefault());
    });
  }

  // ── Bouton déplaçable ───────────────────────────────────
  (function makeDraggable() {
    const fab = document.getElementById("chatFab");
    if (!fab) return;

    protectPhoto();

    let dragging = false, hasMoved = false;
    let startX, startY, origLeft, origBottom;
    let flameTimer = null;

    function getPos(e) {
      return e.touches ? {x:e.touches[0].clientX, y:e.touches[0].clientY} : {x:e.clientX, y:e.clientY};
    }

    function onStart(e) {
      const pos = getPos(e);
      startX = pos.x; startY = pos.y;
      hasMoved = false; dragging = true;
      const rect = fab.getBoundingClientRect();
      origLeft   = rect.left;
      origBottom = window.innerHeight - rect.bottom;
      fab.style.transition = "none";

      // Explosion de feu au toucher
      for (let i = 0; i < 8; i++) spawnFlame(pos.x, pos.y);
      spawnSpark(pos.x, pos.y);
      if (navigator.vibrate) navigator.vibrate([25, 10, 50]);
    }

    function onMove(e) {
      if (!dragging) return;
      const pos = getPos(e);
      const dx = pos.x - startX, dy = pos.y - startY;

      if (Math.abs(dx) > 5 || Math.abs(dy) > 5) {
        if (!hasMoved) {
          hasMoved = true;
          fab.classList.add("yaro-on-fire");
          if (navigator.vibrate) navigator.vibrate([15, 5, 15]);
        }
      }
      if (!hasMoved) return;
      e.preventDefault();

      const sz = fab.offsetWidth, mg = 8;
      fab.style.left   = Math.max(mg, Math.min(window.innerWidth  - sz - mg, origLeft   + dx)) + "px";
      fab.style.bottom = Math.max(mg, Math.min(window.innerHeight - sz - mg, origBottom - dy)) + "px";
      fab.style.right  = "auto";

      // Flammes en continu (50ms)
      if (!flameTimer) {
        const r = fab.getBoundingClientRect();
        const cx = r.left + r.width/2, cy = r.top + r.height/2;
        spawnFlame(cx, cy - 10);
        spawnFlame(cx + (Math.random()-.5)*20, cy);
        spawnFlame(cx + (Math.random()-.5)*20, cy - 5);
        flameTimer = setTimeout(() => { flameTimer = null; }, 50);
      }
    }

    function onEnd(e) {
      if (!dragging) return;
      dragging = false;
      fab.style.transition = "";
      fab.classList.remove("yaro-on-fire");

      if (hasMoved) {
        e.preventDefault(); e.stopPropagation();
        const r = fab.getBoundingClientRect();
        const cx = r.left + r.width/2, cy = r.top + r.height/2;
        for (let i = 0; i < 12; i++) spawnFlame(cx + (Math.random()-.5)*30, cy - Math.random()*20);
        spawnSpark(cx, cy);
        if (navigator.vibrate) navigator.vibrate([60, 15, 30]);

        const win = document.getElementById("chatWindow");
        if (win) {
          const wLeft = Math.max(8, Math.min(window.innerWidth - win.offsetWidth - 8, r.left - win.offsetWidth + fab.offsetWidth));
          win.style.bottom = (window.innerHeight - r.top + 8) + "px";
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
