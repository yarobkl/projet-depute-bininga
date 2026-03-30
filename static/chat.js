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
  // ── EFFETS VISUELS ─────────────────────────────────────
  // ══════════════════════════════════════════════════════════

  // Injecter les styles des animations
  const fxStyle = document.createElement("style");
  fxStyle.textContent = `
    @keyframes yaro-wave {
      0%   { transform: scale(0.2); opacity: 0.9; }
      100% { transform: scale(4);   opacity: 0;   }
    }
    @keyframes yaro-star {
      0%   { transform: translate(0,0) scale(1) rotate(0deg);   opacity: 1; }
      100% { transform: translate(var(--sx),var(--sy)) scale(0) rotate(180deg); opacity: 0; }
    }
    @keyframes yaro-orb {
      0%   { transform: translate(0,0) scale(1);   opacity: 0.85; filter: blur(0px);   }
      100% { transform: translate(var(--ox),var(--oy)) scale(0); opacity: 0;    filter: blur(6px); }
    }
    @keyframes yaro-pulse-border {
      0%,100% { box-shadow: 0 0 0 0 rgba(100,200,255,0), 0 4px 20px rgba(0,0,0,.35); }
      50%     { box-shadow: 0 0 0 10px rgba(100,200,255,.3), 0 4px 20px rgba(0,0,0,.35); }
    }
    .yaro-dragging {
      animation: yaro-pulse-border 0.6s ease-in-out infinite !important;
      transform: scale(1.12) !important;
    }
  `;
  document.head.appendChild(fxStyle);

  // Vagues concentriques (effet eau) au toucher
  function spawnWaves(x, y) {
    const colors = ["rgba(100,200,255,0.6)", "rgba(180,130,255,0.5)", "rgba(255,200,100,0.4)"];
    for (let i = 0; i < 3; i++) {
      setTimeout(() => {
        const w = document.createElement("div");
        const size = 60;
        w.style.cssText = `
          position:fixed; z-index:99999; pointer-events:none;
          width:${size}px; height:${size}px;
          left:${x - size/2}px; top:${y - size/2}px;
          border-radius:50%;
          border: 3px solid ${colors[i]};
          box-shadow: 0 0 12px ${colors[i]};
          transform: scale(0.2); opacity: 0.9;
          animation: yaro-wave ${0.6 + i * 0.15}s ease-out forwards;
        `;
        document.body.appendChild(w);
        setTimeout(() => w.remove(), 900);
      }, i * 80);
    }
  }

  // Étoiles / étincelles au toucher
  function spawnStars(x, y) {
    const count = 8;
    for (let i = 0; i < count; i++) {
      const angle = (i / count) * Math.PI * 2;
      const dist  = 35 + Math.random() * 25;
      const sx    = Math.cos(angle) * dist;
      const sy    = Math.sin(angle) * dist;
      const colors = ["#FFD700", "#FF6B9D", "#7EB8FF", "#A8FF78", "#FF9F43"];
      const color  = colors[Math.floor(Math.random() * colors.length)];
      const s = document.createElement("div");
      s.style.cssText = `
        position:fixed; z-index:99999; pointer-events:none;
        width:8px; height:8px;
        left:${x - 4}px; top:${y - 4}px;
        background: ${color};
        border-radius: 50%;
        box-shadow: 0 0 6px ${color};
        --sx: ${sx}px; --sy: ${sy}px;
        animation: yaro-star 0.55s ease-out forwards;
      `;
      document.body.appendChild(s);
      setTimeout(() => s.remove(), 600);
    }
  }

  // Orbes colorés pendant le glissement
  function spawnOrb(x, y) {
    const colors = [
      "radial-gradient(circle, #7EB8FF, #3D6FFF)",
      "radial-gradient(circle, #FFB347, #FF6B35)",
      "radial-gradient(circle, #C471ED, #7B68EE)",
      "radial-gradient(circle, #43E97B, #38F9D7)",
    ];
    const size = 14 + Math.random() * 14;
    const ox   = (Math.random() - 0.5) * 40;
    const oy   = -(20 + Math.random() * 30);
    const o = document.createElement("div");
    o.style.cssText = `
      position:fixed; z-index:99998; pointer-events:none;
      width:${size}px; height:${size}px;
      left:${x - size/2}px; top:${y - size/2}px;
      border-radius:50%;
      background: ${colors[Math.floor(Math.random() * colors.length)]};
      --ox:${ox}px; --oy:${oy}px;
      animation: yaro-orb 0.65s ease-out forwards;
    `;
    document.body.appendChild(o);
    setTimeout(() => o.remove(), 700);
  }

  // ── Bouton déplaçable ───────────────────────────────────
  (function makeDraggable() {
    const fab = document.getElementById("chatFab");
    if (!fab) return;

    let dragging  = false;
    let hasMoved  = false;
    let startX, startY, origLeft, origBottom;
    let orbTimer  = null;

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

      // Effet au toucher : vagues + étoiles + vibration
      spawnWaves(pos.x, pos.y);
      spawnStars(pos.x, pos.y);
      if (navigator.vibrate) navigator.vibrate([10, 5, 10]);
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
          if (navigator.vibrate) navigator.vibrate([5, 3, 5]);
        }
      }
      if (!hasMoved) return;
      e.preventDefault();

      const size   = fab.offsetWidth;
      const margin = 8;
      fab.style.left   = Math.max(margin, Math.min(window.innerWidth  - size - margin, origLeft   + dx)) + "px";
      fab.style.bottom = Math.max(margin, Math.min(window.innerHeight - size - margin, origBottom - dy)) + "px";
      fab.style.right  = "auto";

      // Orbes toutes les 60ms
      if (!orbTimer) {
        const rect = fab.getBoundingClientRect();
        const cx   = rect.left + rect.width  / 2;
        const cy   = rect.top  + rect.height / 2;
        spawnOrb(cx, cy);
        spawnOrb(cx, cy); // deux orbes à la fois
        orbTimer = setTimeout(() => { orbTimer = null; }, 60);
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
        if (navigator.vibrate) navigator.vibrate(25);

        // Explosion finale d'étoiles à l'atterrissage
        const rect = fab.getBoundingClientRect();
        const cx   = rect.left + rect.width  / 2;
        const cy   = rect.top  + rect.height / 2;
        spawnWaves(cx, cy);
        spawnStars(cx, cy);

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
