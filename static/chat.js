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
      setTimeout(() => { const inp = document.getElementById("chatInput"); if (inp) inp.focus(); }, 300);
      scrollMessages();
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

  // Exposer les fonctions globalement
  window.toggleChat = toggleChat;
  window.sendChat   = sendChat;
})();
