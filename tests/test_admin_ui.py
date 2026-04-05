"""
Tests de l'interface admin — vérifications du HTML (admin.html) et du JavaScript (static/admin.js)
Ces tests s'assurent que les éléments UI et les fonctions JS de gestion des
utilisateurs sont bien présents et corrects.
"""
import os
import re

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ADMIN_HTML = os.path.join(ROOT, "admin.html")
ADMIN_JS   = os.path.join(ROOT, "static", "admin.js")


def _html():
    """Contenu de admin.html uniquement (structure HTML)."""
    with open(ADMIN_HTML, "r", encoding="utf-8") as f:
        return f.read()


def _js():
    """Contenu de static/admin.js (logique JavaScript)."""
    with open(ADMIN_JS, "r", encoding="utf-8") as f:
        return f.read()


def _all():
    """HTML + JS combinés pour les vérifications croisées."""
    return _html() + _js()


# ── Formulaire utilisateurs (HTML) ──────────────────────────

def test_formulaire_cache_par_defaut():
    """Le conteneur du formulaire doit être caché par défaut (display:none)."""
    html = _html()
    match = re.search(r'id="user-form-container"[^>]*style="[^"]*display\s*:\s*none', html)
    assert match, (
        'user-form-container doit avoir style="display:none" par défaut '
        "(formulaire caché au chargement)"
    )
    print("✅ test_formulaire_cache_par_defaut")


def test_bouton_ajouter_utilisateur_present():
    """Le bouton '+ Ajouter un utilisateur' doit exister dans le panel users."""
    html = _html()
    assert 'id="btn-add-user"' in html, "Le bouton btn-add-user doit être présent"
    assert "Ajouter un utilisateur" in html, "Le texte 'Ajouter un utilisateur' doit être présent"
    print("✅ test_bouton_ajouter_utilisateur_present")


def test_bouton_ajouter_appelle_toggle():
    """Le bouton Ajouter doit appeler toggleUserForm()."""
    html = _html()
    match = re.search(r'id="btn-add-user"[^>]*onclick="toggleUserForm\(\)"', html)
    if not match:
        match = re.search(r'onclick="toggleUserForm\(\)"[^>]*id="btn-add-user"', html)
    assert match, "btn-add-user doit appeler toggleUserForm() dans son onclick"
    print("✅ test_bouton_ajouter_appelle_toggle")


# ── Fonction toggleUserForm (JS) ────────────────────────────

def test_fonction_toggle_user_form_definie():
    """La fonction toggleUserForm doit être définie dans admin.js."""
    assert "function toggleUserForm" in _js(), "toggleUserForm doit être définie dans admin.js"
    print("✅ test_fonction_toggle_user_form_definie")


def test_toggle_affiche_et_cache_le_formulaire():
    """toggleUserForm doit basculer display du conteneur."""
    js = _js()
    assert "user-form-container" in js, "user-form-container doit être référencé dans admin.js"
    assert "container.style.display" in js, \
        "toggleUserForm doit manipuler container.style.display"
    print("✅ test_toggle_affiche_et_cache_le_formulaire")


def test_toggle_change_texte_bouton():
    """toggleUserForm doit changer le texte du bouton selon l'état."""
    js = _js()
    assert "Fermer" in js, "Le texte 'Fermer' doit apparaître dans toggleUserForm"
    assert "btn.textContent" in js, "toggleUserForm doit mettre à jour btn.textContent"
    print("✅ test_toggle_change_texte_bouton")


def test_toggle_scroll_vers_formulaire():
    """toggleUserForm doit scroller vers le formulaire à l'ouverture."""
    assert "scrollIntoView" in _js(), \
        "toggleUserForm doit appeler scrollIntoView pour positionner le formulaire"
    print("✅ test_toggle_scroll_vers_formulaire")


# ── Fonction editUser (JS) ──────────────────────────────────

def test_edit_user_appelle_toggle():
    """editUser doit appeler toggleUserForm(true) pour afficher le formulaire."""
    assert "toggleUserForm(true)" in _js(), \
        "editUser doit appeler toggleUserForm(true) pour afficher le formulaire"
    print("✅ test_edit_user_appelle_toggle")


def test_edit_user_titre_inclut_username():
    """editUser doit mettre à jour le titre avec le nom de l'utilisateur."""
    assert "Modifier l'utilisateur · " in _js(), \
        "Le titre du formulaire doit afficher 'Modifier l'utilisateur · [username]'"
    print("✅ test_edit_user_titre_inclut_username")


def test_edit_user_sans_esc_dans_payload():
    """editUser/submitUserForm ne doivent pas utiliser esc() sur les données JSON."""
    js = _js()
    # La version buggée utilisait JSON.stringify(esc(u.username))
    assert "JSON.stringify(esc(" not in js, \
        "submitUserForm ne doit pas passer esc() à JSON.stringify (correction XSS)"
    # Le payload est bien passé via JSON.stringify
    assert "JSON.stringify" in js, \
        "submitUserForm doit utiliser JSON.stringify pour envoyer les données"
    print("✅ test_edit_user_sans_esc_dans_payload")


# ── Badge utilisateurs dans la sidebar ─────────────────────

def test_badge_users_present_dans_sidebar():
    """Un badge id='badge-users' doit exister dans la sidebar."""
    assert 'id="badge-users"' in _html(), \
        "Un élément badge-users doit être présent dans la sidebar"
    print("✅ test_badge_users_present_dans_sidebar")


def test_load_users_met_a_jour_badge():
    """loadUsers doit appeler setBadge('badge-users', ...) après la réponse API."""
    js = _js()
    assert 'setBadge("badge-users"' in js or "setBadge('badge-users'" in js, \
        "loadUsers doit appeler setBadge('badge-users', ...) pour mettre à jour le compteur"
    print("✅ test_load_users_met_a_jour_badge")


# ── Labels d'audit (USER_UPSERT / USER_DELETE) ─────────────

def test_audit_label_user_upsert_present():
    """Le label de l'action USER_UPSERT doit être défini dans loadAuditLogs."""
    js = _js()
    assert "USER_UPSERT" in js, "USER_UPSERT doit être référencé dans admin.js"
    assert "Utilisateur créé / modifié" in js, \
        "Le label de USER_UPSERT doit être 'Utilisateur créé / modifié'"
    print("✅ test_audit_label_user_upsert_present")


def test_audit_label_user_delete_present():
    """Le label de l'action USER_DELETE doit être défini dans loadAuditLogs."""
    js = _js()
    assert "USER_DELETE" in js, "USER_DELETE doit être référencé dans admin.js"
    assert "Utilisateur supprimé" in js, \
        "Le label de USER_DELETE doit être 'Utilisateur supprimé'"
    print("✅ test_audit_label_user_delete_present")


def test_audit_icone_user_upsert():
    """USER_UPSERT doit avoir une icône dans le mapping."""
    assert re.search(r'USER_UPSERT\s*:\s*"[^"]+?"', _js()), \
        "USER_UPSERT doit avoir une icône dans le mapping icons de loadAuditLogs"
    print("✅ test_audit_icone_user_upsert")


def test_audit_icone_user_delete():
    """USER_DELETE doit avoir une icône dans le mapping."""
    assert re.search(r'USER_DELETE\s*:\s*"[^"]+?"', _js()), \
        "USER_DELETE doit avoir une icône dans le mapping icons de loadAuditLogs"
    print("✅ test_audit_icone_user_delete")


# ── Lancement autonome ──────────────────────────────────────

if __name__ == "__main__":
    print("\n🧪 Tests UI admin.html + admin.js...\n")
    tests = [
        test_formulaire_cache_par_defaut,
        test_bouton_ajouter_utilisateur_present,
        test_bouton_ajouter_appelle_toggle,
        test_fonction_toggle_user_form_definie,
        test_toggle_affiche_et_cache_le_formulaire,
        test_toggle_change_texte_bouton,
        test_toggle_scroll_vers_formulaire,
        test_edit_user_appelle_toggle,
        test_edit_user_titre_inclut_username,
        test_edit_user_sans_esc_dans_payload,
        test_badge_users_present_dans_sidebar,
        test_load_users_met_a_jour_badge,
        test_audit_label_user_upsert_present,
        test_audit_label_user_delete_present,
        test_audit_icone_user_upsert,
        test_audit_icone_user_delete,
    ]
    passed = failed = 0
    for t in tests:
        try:
            t()
            passed += 1
        except AssertionError as e:
            print(f"❌ {t.__name__}: {e}")
            failed += 1
    print(f"\n{'✅ Tous les tests UI ont réussi !' if not failed else f'❌ {failed} test(s) échoué(s)'}")
    print(f"  {passed} passé(s), {failed} échoué(s)\n")
