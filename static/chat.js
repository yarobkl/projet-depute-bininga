/* ── CHATBOT DA — Assistant officiel BININGA ──────────────── */
(function () {
  let _open    = false;
  let _loading = false;
  let _history = [];

  function toggleChat() {
    _open = !_open;
    const bubble = document.getElementById("chatBubble");
    if (bubble) bubble.classList.remove("visible");
    const ring = document.getElementById("chatFabRing");
    if (ring) ring.style.display = "none";
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

  // ── Bouton déplaçable ───────────────────────────────────
  (function makeDraggable() {
    const fab = document.getElementById("chatFab");
    if (!fab) return;

    let dragging = false, hasMoved = false;
    let startX, startY, origLeft, origBottom;

    function getPos(e) {
      return e.touches ? {x:e.touches[0].clientX, y:e.touches[0].clientY} : {x:e.clientX, y:e.clientY};
    }

    function onStart(e) {
      e.preventDefault();
      const pos = getPos(e);
      startX = pos.x; startY = pos.y;
      hasMoved = false; dragging = true;
      const rect = fab.getBoundingClientRect();
      origLeft   = rect.left;
      origBottom = window.innerHeight - rect.bottom;
      fab.style.transition = "none";
      fab.style.opacity = ".85";
    }

    function onMove(e) {
      if (!dragging) return;
      const pos = getPos(e);
      const dx = pos.x - startX, dy = pos.y - startY;
      if (Math.abs(dx) > 5 || Math.abs(dy) > 5) hasMoved = true;
      if (!hasMoved) return;
      e.preventDefault();
      const sz = fab.offsetWidth, mg = 8;
      fab.style.left   = Math.max(mg, Math.min(window.innerWidth  - sz - mg, origLeft   + dx)) + "px";
      fab.style.bottom = Math.max(mg, Math.min(window.innerHeight - sz - mg, origBottom - dy)) + "px";
      fab.style.right  = "auto";
    }

    function onEnd(e) {
      if (!dragging) return;
      dragging = false;
      fab.style.transition = "";
      fab.style.opacity = "";

      if (hasMoved) {
        e.preventDefault(); e.stopPropagation();
        if (navigator.vibrate) navigator.vibrate(30);
        const win = document.getElementById("chatWindow");
        if (win) {
          const r = fab.getBoundingClientRect();
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
    const isTouchDevice = ("ontouchstart" in window);
    if (isTouchDevice) {
      fab.addEventListener("touchstart", onStart, { passive: false });
      window.addEventListener("touchmove",  onMove, { passive: false });
      window.addEventListener("touchend",   onEnd);
    } else {
      fab.addEventListener("mousedown",  onStart);
      window.addEventListener("mousemove",  onMove);
      window.addEventListener("mouseup",    onEnd);
    }
  })();

  // ── Bulle d'accueil — apparaît après 3s, reste visible ──
  (function() {
    function showBubble() {
      const bubble = document.getElementById("chatBubble");
      if (!bubble) return;
      setTimeout(() => bubble.classList.add("visible"), 3000);
    }
    if (document.readyState === "loading") {
      document.addEventListener("DOMContentLoaded", showBubble);
    } else {
      showBubble();
    }
  })();

  window.toggleChat = toggleChat;
  window.sendChat   = sendChat;
})();
