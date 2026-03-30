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

  // ── Effets visuels ───────────────────────────────────────

  // Ripple (vague) au toucher
  function spawnRipple(x, y) {
    const r = document.createElement("span");
    r.style.cssText = `
      position:fixed; border-radius:50%; pointer-events:none; z-index:99999;
      width:60px; height:60px;
      left:${x - 30}px; top:${y - 30}px;
      background: radial-gradient(circle, rgba(255,255,255,.55) 0%, rgba(100,180,255,.25) 60%, transparent 100%);
      transform: scale(0); opacity:1;
      animation: yaro-ripple .55s ease-out forwards;
    `;
    document.body.appendChild(r);
    setTimeout(() => r.remove(), 600);
  }

  // Particule de fumée pendant le glissement
  function spawnSmoke(x, y) {
    const colors = ["rgba(180,220,255,.55)", "rgba(255,220,180,.45)", "rgba(200,180,255,.45)"];
    const p = document.createElement("span");
    const size = 10 + Math.random() * 14;
    const dx   = (Math.random() - .5) * 24;
    const dy   = -(12 + Math.random() * 18);
    p.style.cssText = `
      position:fixed; border-radius:50%; pointer-events:none; z-index:99998;
      width:${size}px; height:${size}px;
      left:${x - size/2}px; top:${y - size/2}px;
      background:${colors[Math.floor(Math.random()*colors.length)]};
      filter:blur(3px);
      animation: yaro-smoke .7s ease-out forwards;
      --dx:${dx}px; --dy:${dy}px;
    `;
    document.body.appendChild(p);
    setTimeout(() => p.remove(), 750);
  }

  // Inject keyframes une seule fois
  if (!document.getElementById("yaro-fx-style")) {
    const s = document.createElement("style");
    s.id = "yaro-fx-style";
    s.textContent = `
      @keyframes yaro-ripple {
        0%   { transform:scale(0);   opacity:1; }
        100% { transform:scale(2.8); opacity:0; }
      }
      @keyframes yaro-smoke {
        0%   { transform:translate(0,0)               scale(1);   opacity:.8; }
        100% { transform:translate(var(--dx),var(--dy)) scale(2.2); opacity:0; }
      }
    `;
    document.head.appendChild(s);
  }

  // ── Bouton déplaçable + effets ───────────────────────────
  (function makeDraggable() {
    const fab = document.getElementById("chatFab");
    if (!fab) return;

    let dragging  = false;
    let hasMoved  = false;
    let startX, startY, origLeft, origBottom;
    let smokeTimer = null;

    function getPos(e) {
      return e.touches ? { x: e.touches[0].clientX, y: e.touches[0].clientY }
                       : { x: e.clientX,             y: e.clientY };
    }

    function vibrate(pattern) {
      if (navigator.vibrate) navigator.vibrate(pattern);
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

      // Ripple + vibration au toucher
      spawnRipple(pos.x, pos.y);
      vibrate(15);
    }

    function onMove(e) {
      if (!dragging) return;
      const pos = getPos(e);
      const dx  = pos.x - startX;
      const dy  = pos.y - startY;

      if (Math.abs(dx) > 5 || Math.abs(dy) > 5) {
        if (!hasMoved) {
          hasMoved = true;
          fab.style.boxShadow = "0 0 24px 6px rgba(100,180,255,.55)";
          vibrate([8, 4, 8]);
        }
      }
      if (!hasMoved) return;
      e.preventDefault();

      const size   = fab.offsetWidth;
      const margin = 8;
      const newLeft   = Math.max(margin, Math.min(window.innerWidth  - size - margin, origLeft   + dx));
      const newBottom = Math.max(margin, Math.min(window.innerHeight - size - margin, origBottom - dy));

      fab.style.left   = newLeft   + "px";
      fab.style.bottom = newBottom + "px";
      fab.style.right  = "auto";

      // Fumée pendant le déplacement (toutes les 80ms)
      if (!smokeTimer) {
        const rect = fab.getBoundingClientRect();
        spawnSmoke(rect.left + rect.width/2, rect.top + rect.height/2);
        smokeTimer = setTimeout(() => { smokeTimer = null; }, 80);
      }
    }

    function onEnd(e) {
      if (!dragging) return;
      dragging = false;
      fab.style.transition = "";
      fab.style.boxShadow  = "";

      if (hasMoved) {
        e.preventDefault();
        e.stopPropagation();
        vibrate(20);

        // Repositionner la fenêtre chat
        const win = document.getElementById("chatWindow");
        if (win) {
          const rect  = fab.getBoundingClientRect();
          const wLeft = Math.max(8, Math.min(window.innerWidth - win.offsetWidth - 8, rect.left - win.offsetWidth + fab.offsetWidth));
          win.style.bottom = (window.innerHeight - rect.top + 8) + "px";
          win.style.left   = wLeft + "px";
          win.style.right  = "auto";
        }
      } else {
        // Simple tap → ouvrir/fermer
        toggleChat();
      }
    }

    // Supprimer onclick natif pour gérer manuellement
    fab.removeAttribute("onclick");

    fab.addEventListener("mousedown",  onStart);
    fab.addEventListener("touchstart", onStart, { passive: true });
    window.addEventListener("mousemove",  onMove);
    window.addEventListener("touchmove",  onMove, { passive: false });
    window.addEventListener("mouseup",    onEnd);
    window.addEventListener("touchend",   onEnd);
  })();

  // Exposer les fonctions globalement
  window.toggleChat = toggleChat;
  window.sendChat   = sendChat;
})();
