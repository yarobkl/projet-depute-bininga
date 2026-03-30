/* ── CHATBOT BININGA ──────────────────────────────────────── */
(function () {
  let _open    = false;
  let _loading = false;
  let _history = [];   // [{role, content}]

  function toggleChat() {
    _open = !_open;
    const win = document.getElementById("chatWindow");
    const fab = document.getElementById("chatFab");
    const badge = document.getElementById("chatFabBadge");
    if (win) { win.classList.toggle("open", _open); win.setAttribute("aria-hidden", !_open); }
    if (fab) fab.classList.toggle("open", _open);
    if (_open) {
      if (badge) badge.style.display = "none";
      // Sur mobile on ne force pas le focus pour éviter le saut de page au clavier
      const isMobile = window.innerWidth <= 600;
      if (!isMobile) {
        setTimeout(() => { const inp = document.getElementById("chatInput"); if (inp) inp.focus(); }, 300);
      }
      scrollMessages();
    } else {
      // Fermeture : enlever le focus pour cacher le clavier mobile
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
      const ctrl = new AbortController();
      const timer = setTimeout(() => ctrl.abort(), 25000);
      const res  = await fetch("/api/chat", {
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

      // Badge si fenêtre fermée
      if (!_open) {
        const badge = document.getElementById("chatFabBadge");
        if (badge) badge.style.display = "flex";
      }
    } catch (e) {
      if (typing) typing.remove();
      const msg = e.name === "AbortError"
        ? "La réponse prend trop de temps. Veuillez réessayer."
        : "Une erreur s'est produite. Veuillez réessayer.";
      addMessage("bot", msg);
    } finally {
      _loading = false;
      if (btn) btn.disabled = false;
      if (inp) inp.focus();
    }
  }

  // ── Bouton déplaçable ────────────────────────────────────
  (function makeDraggable() {
    const fab = document.getElementById("chatFab");
    if (!fab) return;

    let dragging  = false;
    let hasMoved  = false;
    let startX, startY, origLeft, origBottom;

    function getPos(e) {
      return e.touches ? { x: e.touches[0].clientX, y: e.touches[0].clientY }
                       : { x: e.clientX,             y: e.clientY };
    }

    function onStart(e) {
      const pos = getPos(e);
      startX  = pos.x;
      startY  = pos.y;
      hasMoved = false;

      const rect = fab.getBoundingClientRect();
      origLeft   = rect.left;
      origBottom = window.innerHeight - rect.bottom;

      dragging = true;
      fab.style.transition = "none";
    }

    function onMove(e) {
      if (!dragging) return;
      const pos  = getPos(e);
      const dx   = pos.x - startX;
      const dy   = pos.y - startY;

      if (Math.abs(dx) > 4 || Math.abs(dy) > 4) hasMoved = true;
      if (!hasMoved) return;

      e.preventDefault();

      const size   = fab.offsetWidth;
      const margin = 8;
      let newLeft   = Math.max(margin, Math.min(window.innerWidth  - size - margin, origLeft   + dx));
      let newBottom = Math.max(margin, Math.min(window.innerHeight - size - margin, origBottom - dy));

      fab.style.left   = newLeft   + "px";
      fab.style.bottom = newBottom + "px";
      fab.style.right  = "auto";
    }

    function onEnd(e) {
      if (!dragging) return;
      dragging = false;
      fab.style.transition = "";
      if (hasMoved) {
        e.preventDefault();
        e.stopPropagation();
        // Repositionner la fenêtre chat à côté du bouton
        const win = document.getElementById("chatWindow");
        if (win) {
          const rect   = fab.getBoundingClientRect();
          const wLeft  = Math.max(8, Math.min(window.innerWidth - win.offsetWidth - 8, rect.left - win.offsetWidth + fab.offsetWidth));
          const wBott  = Math.max(8, rect.bottom + 8 > window.innerHeight - win.offsetHeight - 8
                          ? window.innerHeight - rect.top + 8
                          : window.innerHeight - rect.top + 8);
          win.style.bottom = (window.innerHeight - rect.top + 8) + "px";
          win.style.left   = wLeft + "px";
          win.style.right  = "auto";
        }
      }
    }

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
