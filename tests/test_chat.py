"""
Tests automatiques — Chatbot DA (/api/chat)
Vérifie les réponses du chatbot, la validation, et le rate limiting.
"""
import json
import urllib.request
import urllib.error
import pytest

PORT = 18080
BASE = f"http://127.0.0.1:{PORT}"


def _reset():
    """Remet à zéro les compteurs de sécurité entre les tests (mode BININGA_TEST=1)."""
    try:
        req = urllib.request.Request(f"{BASE}/api/test/reset", data=b"{}", method="POST")
        req.add_header("Content-Type", "application/json")
        with urllib.request.urlopen(req, timeout=5):
            pass
    except Exception:
        pass


def chat(message, history=None):
    """Envoie un message au chatbot, retourne (status, data)."""
    url = f"{BASE}/api/chat"
    payload = {"message": message, "history": history or []}
    body = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url, data=body, method="POST")
    req.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            return r.status, json.loads(r.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        try:
            return e.code, json.loads(e.read().decode("utf-8"))
        except Exception:
            return e.code, {}


@pytest.fixture(autouse=True)
def reset_rate_limit():
    """Remet à zéro les compteurs avant chaque test de chat."""
    _reset()
    yield
    _reset()


# ── Réponses aux salutations ──────────────────────────────

def test_chat_bonjour():
    """Le chatbot répond à 'bonjour' avec une réponse de bienvenue."""
    status, data = chat("Bonjour")
    assert status == 200, f"Attendu 200, reçu {status}"
    assert "reply" in data, "Le champ 'reply' doit être présent"
    reply = data["reply"].lower()
    assert any(w in reply for w in ["da", "bininga", "bonjour", "bienvenue"]), \
        f"Réponse inattendue : {data['reply']}"
    print(f"✅ test_chat_bonjour — '{data['reply'][:80]}…'")


def test_chat_salut():
    """Le chatbot répond à 'salut'."""
    status, data = chat("Salut !")
    assert status == 200
    assert "reply" in data
    print(f"✅ test_chat_salut — '{data['reply'][:80]}…'")


# ── Identité du chatbot ───────────────────────────────────

def test_chat_qui_es_tu():
    """Le chatbot sait qui il est."""
    status, data = chat("Qui es-tu ?")
    assert status == 200
    reply = data["reply"].lower()
    assert "da" in reply, f"Le chatbot doit se présenter comme DA, reçu : {data['reply']}"
    print(f"✅ test_chat_qui_es_tu — '{data['reply'][:80]}…'")


def test_chat_presentation():
    """Le chatbot peut présenter le Ministre BININGA."""
    status, data = chat("Qui est Bininga ?")
    assert status == 200
    reply = data["reply"].lower()
    assert "bininga" in reply, f"Réponse doit mentionner BININGA : {data['reply']}"
    print(f"✅ test_chat_presentation — '{data['reply'][:80]}…'")


# ── Validation des entrées ────────────────────────────────

def test_chat_message_vide():
    """Un message vide doit retourner 400."""
    status, data = chat("")
    assert status == 400, f"Attendu 400 pour message vide, reçu {status}"
    print(f"✅ test_chat_message_vide — status={status}")


def test_chat_message_espaces():
    """Un message contenant uniquement des espaces doit retourner 400."""
    status, data = chat("   ")
    assert status == 400, f"Attendu 400 pour message vide (espaces), reçu {status}"
    print(f"✅ test_chat_message_espaces — status={status}")


def test_chat_message_long():
    """Un message très long est tronqué et traité sans erreur."""
    long_msg = "a" * 2000
    status, data = chat(long_msg)
    assert status in (200, 429), f"Attendu 200 ou 429, reçu {status}"
    if status == 200:
        assert "reply" in data
    print(f"✅ test_chat_message_long — status={status}")


# ── Contenu des réponses thématiques ─────────────────────

def test_chat_programme():
    """Le chatbot parle du programme quand on le demande."""
    status, data = chat("Quel est son programme ?")
    assert status == 200
    assert "reply" in data
    assert len(data["reply"]) > 10, "La réponse doit avoir du contenu"
    print(f"✅ test_chat_programme — '{data['reply'][:80]}…'")


def test_chat_contact():
    """Le chatbot fournit des infos de contact."""
    status, data = chat("Comment le contacter ?")
    assert status == 200
    assert "reply" in data
    print(f"✅ test_chat_contact — '{data['reply'][:80]}…'")


def test_chat_parcours():
    """Le chatbot peut parler du parcours professionnel."""
    status, data = chat("Quel est son parcours professionnel ?")
    assert status == 200
    assert "reply" in data
    print(f"✅ test_chat_parcours — '{data['reply'][:80]}…'")


# ── Format de réponse ─────────────────────────────────────

def test_chat_reply_est_une_chaine():
    """Le champ reply doit toujours être une chaîne de caractères."""
    status, data = chat("Bonjour")
    assert status == 200
    assert isinstance(data.get("reply"), str), "reply doit être une chaîne"
    print("✅ test_chat_reply_est_une_chaine")


def test_chat_avec_historique():
    """Le chatbot accepte un historique de conversation."""
    history = [
        {"role": "user", "content": "Bonjour"},
        {"role": "assistant", "content": "Bonjour ! Je suis DA."},
    ]
    status, data = chat("Qui est Bininga ?", history=history)
    assert status == 200
    assert "reply" in data
    print(f"✅ test_chat_avec_historique — '{data['reply'][:80]}…'")


# ── Rate limiting ─────────────────────────────────────────

def test_chat_rate_limit():
    """Après 10 messages rapides, le rate limiting doit retourner 429."""
    # Envoie 11 messages pour dépasser la limite (10/min)
    last_status = None
    for i in range(11):
        status, _ = chat(f"Question {i}")
        last_status = status
        if status == 429:
            break
    assert last_status == 429, \
        "Le rate limiting doit bloquer après 10 messages avec un 429"
    print("✅ test_chat_rate_limit")
