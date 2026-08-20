"""Natural-language understanding layer for DA.

This module complements the hardened chatbot without weakening its security
rules.  It recognises conversational French, paraphrases, short acknowledgements,
common typos and context-dependent follow-ups before the factual answer layer
runs.
"""
from __future__ import annotations

import re
import unicodedata
from difflib import SequenceMatcher
from typing import Any, Callable, Dict, Iterable, Optional, Sequence


DOMAIN_PRIORITY = (
    "journal_officiel",
    "tracking",
    "audience",
    "location",
    "contact",
    "complaint",
    "newsletter",
    "gallery",
    "books",
    "programme",
    "career",
    "biography",
    "news",
    "legal",
)

DOMAIN_PHRASES: Dict[str, Sequence[str]] = {
    "programme": (
        "ce qu il compte faire", "qu est ce qu il propose", "qu est ce qu il veut faire",
        "ses propositions", "ses priorites", "ses promesses", "ses projets pour ewo",
        "son projet pour ewo", "sa vision", "ses mesures", "il propose quoi",
        "il veut changer quoi", "il compte faire quoi",
    ),
    "career": (
        "il faisait quoi avant", "qu a t il fait avant", "ses anciens postes",
        "ses anciennes fonctions", "son experience", "sa carriere", "ses etudes",
        "ses diplomes", "ou a t il travaille", "son parcours professionnel",
    ),
    "biography": (
        "qui est ce monsieur", "qui est cet homme", "presente le moi", "parle moi de lui",
        "son histoire", "sa biographie", "ses origines", "ou est il ne", "quand est il ne",
    ),
    "news": (
        "qu est ce qu il a fait recemment", "qu a t il fait recemment", "quoi de neuf",
        "ses dernieres actions", "ses dernieres nouvelles", "les dernieres nouvelles",
        "ce qu il fait en ce moment", "ses actualites",
    ),
    "audience": (
        "je veux le voir", "je voudrais le voir", "je veux le rencontrer",
        "je voudrais le rencontrer", "je veux lui parler", "prendre rendez vous",
        "prendre un rendez vous", "avoir un rendez vous", "obtenir une audience",
        "rencontrer le ministre", "parler au ministre",
    ),
    "tracking": (
        "ou en est ma demande", "ou en est mon dossier", "suivre ma demande",
        "suivre mon dossier", "avancement de ma demande", "avancement de mon dossier",
        "j ai deja envoye ma demande", "j ai envoye une demande", "statut de ma demande",
        "statut de mon dossier", "ma demande en est ou", "mon dossier en est ou",
    ),
    "contact": (
        "comment je peux lui ecrire", "comment lui ecrire", "comment le joindre",
        "comment les joindre", "je veux lui ecrire", "je voudrais lui ecrire",
        "je veux contacter son equipe", "son numero de telephone", "son adresse mail",
        "son email", "comment le contacter",
    ),
    "location": (
        "c est ou son bureau", "ou est son bureau", "ou se trouve son bureau",
        "ou est le ministere", "ou se trouve le ministere", "je dois aller ou",
        "quelle est l adresse", "donne moi l adresse", "c est ou exactement",
    ),
    "complaint": (
        "je veux signaler un probleme", "je voudrais signaler un probleme",
        "j ai un probleme dans mon quartier", "j ai un souci dans mon quartier",
        "faire une reclamation", "deposer une reclamation", "faire un signalement",
    ),
    "books": (
        "son livre", "ses livres", "acheter son livre", "commander son livre",
        "ses ouvrages", "son ouvrage", "sa publication",
    ),
    "gallery": (
        "voir ses photos", "voir les photos", "voir ses videos", "voir les videos",
        "des images de lui", "sa galerie",
    ),
    "newsletter": (
        "recevoir les nouvelles", "recevoir les actualites", "m inscrire aux actualites",
        "m abonner", "s inscrire a la newsletter",
    ),
    "legal": (
        "ce qu il fait pour la justice", "reforme de la justice", "reformes de la justice",
        "ses reformes", "question juridique", "question de droit", "sur la justice",
    ),
    "journal_officiel": (
        "texte officiel", "publication officielle", "journal officiel", "numero du decret",
        "quel decret", "decret officiel", "nomination officielle",
    ),
}

DOMAIN_WORDS: Dict[str, Sequence[str]] = {
    "programme": ("programme", "proposition", "priorite", "promesse", "projet", "vision", "mesure", "engagement"),
    "career": ("parcours", "carriere", "etude", "diplome", "experience", "poste", "fonction", "universite", "doctorat"),
    "biography": ("biographie", "origine", "naissance", "enfance", "presentation"),
    "news": ("actualite", "recent", "derniere", "agenda", "evenement", "nouvelle"),
    "audience": ("audience", "rendezvous", "rdv", "rencontrer", "rencontre"),
    "tracking": ("suivi", "dossier", "avancement", "statut", "demande"),
    "contact": ("contact", "contacter", "joindre", "email", "mail", "telephone", "ecrire"),
    "location": ("adresse", "bureau", "localisation", "ministere", "siege"),
    "complaint": ("reclamation", "plainte", "signalement", "signaler", "sinistre", "probleme"),
    "newsletter": ("newsletter", "abonnement", "abonner"),
    "gallery": ("galerie", "photo", "video", "image", "album"),
    "books": ("livre", "ouvrage", "publication", "commander"),
    "legal": ("justice", "juridique", "loi", "tribunal", "reforme", "legislation", "droit"),
    "journal_officiel": ("decret", "journal", "officiel", "nomination"),
}

CAPABILITY_PATTERNS = (
    r"\ben quoi (?:tu|vous) (?:peux|pouvez) (?:m|nous)[' ]?aider\b",
    r"\b(?:tu|vous) (?:peux|pouvez) (?:m|nous)[' ]?aider (?:a|sur) quoi\b",
    r"\b(?:tu|vous) (?:peux|pouvez) faire quoi\b",
    r"\bqu[' ]?est ce que (?:je|on) (?:peux|peut) (?:te|vous) demander\b",
    r"\ba quoi (?:tu|vous) (?:sers|servez)\b",
    r"\b(?:tes|vos) capacites\b",
    r"\bque sais (?:tu|vous) faire\b",
    r"\bcomment (?:tu|vous) (?:peux|pouvez) (?:m|nous)[' ]?aider\b",
)

ACK_PATTERNS = (
    r"^(?:ok|okay|d accord|dac|entendu|compris|parfait|super|nickel|top|tres bien|tres bien merci|ca marche|je vois|c est clair|bien compris|exact|exactement)[!. ]*$",
    r"^(?:oui|ouais|yes|non|nan)[!. ]*$",
)

META_PATTERNS = (
    r"\b(?:tu|vous) comprends? ce que je veux dire\b",
    r"\b(?:tu|vous) vois ce que je veux dire\b",
    r"\bje peux (?:te|vous) parler normalement\b",
    r"\bje peux parler naturellement\b",
    r"\bcomprends? (?:moi|ma question)\b",
)

SMALLTALK_PATTERNS = (
    r"^(?:ca roule|tranquille|tout va bien|comment ca va|tu vas bien|vous allez bien)[?.! ]*$",
)

FOLLOWUP_PATTERNS = (
    r"^(?:et )?(?:apres|ensuite|pourquoi|comment ca|c est a dire|tu veux dire quoi|vous voulez dire quoi|et lui|et elle|et ca|et cela)[?.! ]*$",
)


def _norm(text: str) -> str:
    value = unicodedata.normalize("NFKD", text or "")
    value = "".join(ch for ch in value if not unicodedata.combining(ch)).lower()
    value = value.replace("’", "'").replace("-", " ")
    value = re.sub(r"[^a-z0-9'\s]", " ", value)
    return re.sub(r"\s+", " ", value).strip()


def _tokens(text: str) -> Sequence[str]:
    return tuple(x for x in _norm(text).replace("'", " ").split() if x)


def _matches_any(text: str, patterns: Iterable[str]) -> bool:
    q = _norm(text)
    return any(re.search(pattern, q, re.I) for pattern in patterns)


def conversation_act(question: str) -> Optional[str]:
    if _matches_any(question, CAPABILITY_PATTERNS):
        return "capability"
    if _matches_any(question, ACK_PATTERNS):
        return "acknowledgement"
    if _matches_any(question, META_PATTERNS):
        return "meta_conversation"
    if _matches_any(question, SMALLTALK_PATTERNS):
        return "greeting"
    if _matches_any(question, FOLLOWUP_PATTERNS):
        return "followup"
    return None


def _fuzzy_word_match(token: str, candidate: str) -> bool:
    if token == candidate:
        return True
    if len(token) < 5 or len(candidate) < 5:
        return False
    return SequenceMatcher(None, token, candidate).ratio() >= 0.86


def domain_intent(question: str) -> Optional[str]:
    q = _norm(question)
    if not q:
        return None

    for intent in DOMAIN_PRIORITY:
        if any(phrase in q for phrase in DOMAIN_PHRASES.get(intent, ())):
            return intent

    tokens = _tokens(q)
    scores: Dict[str, int] = {}
    for intent in DOMAIN_PRIORITY:
        score = 0
        for candidate in DOMAIN_WORDS.get(intent, ()):
            if any(_fuzzy_word_match(token, candidate) for token in tokens):
                score += 1
        if score:
            scores[intent] = score
    if not scores:
        return None
    return max(DOMAIN_PRIORITY, key=lambda name: (scores.get(name, 0), -DOMAIN_PRIORITY.index(name))) if max(scores.values()) > 0 else None


def _looks_like_followup(question: str) -> bool:
    q = _norm(question)
    if _matches_any(q, FOLLOWUP_PATTERNS):
        return True
    words = q.split()
    if len(words) > 8:
        return False
    return bool(words and words[0] in {"et", "mais", "donc", "alors", "pourquoi", "comment", "quand", "ou", "lequel", "laquelle"})


def _history_intent(history: Optional[Sequence[dict]], base_classifier: Callable[..., str]) -> Optional[str]:
    if not history:
        return None

    # Prefer what the visitor was talking about; then inspect DA's latest reply.
    ordered = [h for h in reversed(history[-8:]) if h.get("role") == "user"]
    ordered += [h for h in reversed(history[-8:]) if h.get("role") != "user"]
    for item in ordered:
        content = str(item.get("content", ""))
        found = domain_intent(content)
        if found:
            return found
        try:
            found = base_classifier(content, None)
        except TypeError:
            found = base_classifier(content)
        if found in DOMAIN_PRIORITY:
            return found
    return None


def detect_intent(question: str, history: Optional[Sequence[dict]] = None, base_classifier: Optional[Callable[..., str]] = None) -> str:
    """Return a human-language intent while preserving the hardened classifier."""
    if base_classifier is not None:
        try:
            base = base_classifier(question, None)
        except TypeError:
            base = base_classifier(question)
        # Security/boundary decisions from the hardened layer always win.
        if base in {"prompt_injection", "out_of_scope", "empty"}:
            return base
    else:
        base = "unknown"

    semantic = domain_intent(question)
    if semantic:
        return semantic

    act = conversation_act(question)
    if act and act != "followup":
        return act

    if base not in {"unknown", "empty"}:
        return base

    if _looks_like_followup(question):
        previous = _history_intent(history, base_classifier) if base_classifier else None
        return previous or "clarification"

    return "unknown"


def install(hardened: Any) -> None:
    """Install the NLU layer once on top of ``chatbot_hardening``."""
    if getattr(hardened, "_human_language_installed", False):
        return

    original_classifier = hardened.classify_intent
    original_deterministic = hardened._deterministic
    original_answer = hardened.answer

    def human_classifier(question: str, history: Optional[Sequence[dict]] = None) -> str:
        return detect_intent(question, history, original_classifier)

    def human_deterministic(intent: str, facts: dict, knowledge: Sequence[dict]) -> Optional[str]:
        name = facts.get("nom") or "Ange Aimé Wilfrid BININGA"
        if intent == "capability":
            return (
                "Vous pouvez me parler naturellement, comme à une personne. Je peux vous renseigner sur "
                f"{name}, sa biographie, son parcours, son programme, ses actualités, ses publications, "
                "les demandes d'audience, le suivi d'un dossier, les contacts et les réclamations. "
                "Si une information n'est pas vérifiée dans mes sources, je vous le dirai clairement."
            )
        if intent == "acknowledgement":
            return "Très bien. Je vous écoute : vous pouvez continuer naturellement, sans chercher les mots-clés exacts."
        if intent == "meta_conversation":
            return "Oui. Vous pouvez formuler votre demande avec vos propres mots ; je tiens compte du sens et du contexte de la conversation, pas seulement de mots-clés isolés."
        if intent == "clarification":
            return "Je vous suis, mais je veux être sûr de répondre au bon point. Dites-moi simplement ce que vous voulez que je précise, avec vos propres mots."
        if intent == "out_of_scope":
            return "Je suis surtout là pour vous aider sur Ange Aimé Wilfrid BININGA, ses actions et les démarches disponibles sur ce site. Si votre question concerne l'un de ces sujets, dites-la simplement comme elle vous vient."
        return original_deterministic(intent, facts, knowledge)

    def human_answer(server: Any, question: str, history: Optional[Sequence[dict]] = None):
        reply, intent, provider = original_answer(server, question, history)
        # When no external provider is available, an unknown human utterance
        # should trigger a natural clarification instead of an irrelevant email fallback.
        if intent == "unknown" and provider in {"none", "disabled"}:
            return (
                "Je ne suis pas certain d'avoir compris ce que vous voulez dire. Reformulez-le simplement comme vous le diriez à quelqu'un ; je vais m'appuyer sur le contexte de notre échange.",
                "clarification",
                "local",
            )
        return reply, intent, provider

    hardened.classify_intent = human_classifier
    hardened._deterministic = human_deterministic
    hardened.answer = human_answer
    hardened._human_language_installed = True
