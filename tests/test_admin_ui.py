"""
Tests de l'interface admin (admin.html) — vérifications du HTML et du JavaScript
Ces tests s'assurent que les éléments UI ajoutés lors de l'amélioration
de la gestion des utilisateurs sont bien présents et corrects.
"""
import os
import re
import sys

ADMIN_HTML = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "admin.html")


def _html():
    with open(ADMIN_HTML, "r", encoding="utf-8") as f:
        return f.read()


# ── Formulaire utilisateurs ────────────────────────────────────

def test_formulaire_cache_par_defaut():
    """Le conteneur du formulaire doit être caché par défaut (display:none)."""
    html = _html()
    # Chercher l'id user-form-container avec display:none dans la même balise
    match = re.search(r'id="user-form-container"[^>]*style="[^"]*display\s*:\s*none', html)
    assert match, (
        "user-form-container doit avoir style=\"display:none\" par défaut "
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
    # Cherche onclick="toggleUserForm()" sur le bouton btn-add-user
    match = re.search(r'id="btn-add-user"[^>]*onclick="toggleUserForm\(\)"', html)
    if not match:
        # Ou dans l'ordre inverse des attributs
        match = re.search(r'onclick="toggleUserForm\(\)"[^>]*id="btn-add-user"', html)
    assert match, "btn-add-user doit appeler toggleUserForm() dans son onclick"
    print("✅ test_bouton_ajouter_appelle_toggle")


# ── Fonction toggleUserForm ────────────────────────────────────

def test_fonction_toggle_user_form_definie():
    """La fonction toggleUserForm doit être définie dans le script."""
    html = _html()
    assert "function toggleUserForm" in html, "toggleUserForm doit être définie"
    print("✅ test_fonction_toggle_user_form_definie")


def test_toggle_affiche_et_cache_le_formulaire():
    """toggleUserForm doit basculer display du conteneur."""
    html = _html()
    assert "user-form-container" in html, "user-form-container doit être référencé"
    # Vérifie que toggleUserForm manipule bien le style.display
    assert 'container.style.display' in html, \
        "toggleUserForm doit manipuler container.style.display"
    print("✅ test_toggle_affiche_et_cache_le_formulaire")


def test_toggle_change_texte_bouton():
    """toggleUserForm doit changer le texte du bouton selon l'état."""
    html = _html()
    assert "Fermer" in html, "Le texte '✕ Fermer' doit apparaître dans toggleUserForm"
    assert "btn.textContent" in html, "toggleUserForm doit mettre à jour btn.textContent"
    print("✅ test_toggle_change_texte_bouton")


def test_toggle_scroll_vers_formulaire():
    """toggleUserForm doit scroller vers le formulaire à l'ouverture."""
    html = _html()
    assert "scrollIntoView" in html, \
        "toggleUserForm doit appeler scrollIntoView pour positionner le formulaire"
    print("✅ test_toggle_scroll_vers_formulaire")


# ── Fonction editUser ──────────────────────────────────────────

def test_edit_user_appelle_toggle():
    """editUser doit appeler toggleUserForm(true) pour afficher le formulaire."""
    html = _html()
    assert "toggleUserForm(true)" in html, \
        "editUser doit appeler toggleUserForm(true) pour afficher le formulaire"
    print("✅ test_edit_user_appelle_toggle")


def test_edit_user_titre_inclut_username():
    """editUser doit mettre à jour le titre avec le nom de l'utilisateur."""
    html = _html()
    # Le titre doit inclure le username (via concaténation)
    assert "Modifier l'utilisateur · " in html, \
        "Le titre du formulaire doit afficher 'Modifier l'utilisateur · [username]'"
    print("✅ test_edit_user_titre_inclut_username")


def test_edit_user_sans_esc_dans_onclick():
    """editUser ne doit pas utiliser esc() sur les valeurs passées à JSON.stringify (bug XSS corrigé)."""
    html = _html()
    # La version corrigée utilise JSON.stringify(u.username) sans esc()
    # La version buggée utilisait JSON.stringify(esc(u.username))
    assert "JSON.stringify(esc(u.username))" not in html, \
        "editUser ne doit pas passer esc(u.username) à JSON.stringify (correction XSS)"
    assert "JSON.stringify(u.username)" in html, \
        "editUser doit passer u.username directement à JSON.stringify"
    print("✅ test_edit_user_sans_esc_dans_onclick")


# ── Badge utilisateurs dans la sidebar ────────────────────────

def test_badge_users_present_dans_sidebar():
    """Un badge id='badge-users' doit exister dans la sidebar."""
    html = _html()
    assert 'id="badge-users"' in html, \
        "Un élément badge-users doit être présent dans la sidebar"
    print("✅ test_badge_users_present_dans_sidebar")


def test_load_users_met_a_jour_badge():
    """loadUsers doit appeler setBadge('badge-users', ...) après la réponse API."""
    html = _html()
    assert 'setBadge("badge-users"' in html or "setBadge('badge-users'" in html, \
        "loadUsers doit appeler setBadge('badge-users', ...) pour mettre à jour le compteur"
    print("✅ test_load_users_met_a_jour_badge")


# ── Labels d'audit (USER_UPSERT / USER_DELETE) ─────────────────

def test_audit_label_user_upsert_present():
    """Le label de l'action USER_UPSERT doit être défini dans loadAuditLogs."""
    html = _html()
    assert "USER_UPSERT" in html, "USER_UPSERT doit être référencé dans admin.html"
    assert "Utilisateur créé / modifié" in html, \
        "Le label de USER_UPSERT doit être 'Utilisateur créé / modifié'"
    print("✅ test_audit_label_user_upsert_present")


def test_audit_label_user_delete_present():
    """Le label de l'action USER_DELETE doit être défini dans loadAuditLogs."""
    html = _html()
    assert "USER_DELETE" in html, "USER_DELETE doit être référencé dans admin.html"
    assert "Utilisateur supprimé" in html, \
        "Le label de USER_DELETE doit être 'Utilisateur supprimé'"
    print("✅ test_audit_label_user_delete_present")


def test_audit_icone_user_upsert():
    """USER_UPSERT doit avoir une icône dans le mapping."""
    html = _html()
    # Le mapping doit contenir USER_UPSERT avec une icône
    assert re.search(r'USER_UPSERT\s*:\s*"[^"]+?"', html), \
        "USER_UPSERT doit avoir une icône dans le mapping icons de loadAuditLogs"
    print("✅ test_audit_icone_user_upsert")


def test_audit_icone_user_delete():
    """USER_DELETE doit avoir une icône dans le mapping."""
    html = _html()
    assert re.search(r'USER_DELETE\s*:\s*"[^"]+?"', html), \
        "USER_DELETE doit avoir une icône dans le mapping icons de loadAuditLogs"
    print("✅ test_audit_icone_user_delete")


# ── Lancement ──────────────────────────────────────────────────

if __name__ == "__main__":
    print("\n🧪 Tests UI admin.html...\n")

    test_formulaire_cache_par_defaut()
    test_bouton_ajouter_utilisateur_present()
    test_bouton_ajouter_appelle_toggle()
    test_fonction_toggle_user_form_definie()
    test_toggle_affiche_et_cache_le_formulaire()
    test_toggle_change_texte_bouton()
    test_toggle_scroll_vers_formulaire()
    test_edit_user_appelle_toggle()
    test_edit_user_titre_inclut_username()
    test_edit_user_sans_esc_dans_onclick()
    test_badge_users_present_dans_sidebar()
    test_load_users_met_a_jour_badge()
    test_audit_label_user_upsert_present()
    test_audit_label_user_delete_present()
    test_audit_icone_user_upsert()
    test_audit_icone_user_delete()

    print("\n╔══════════════════════════════════════════╗")
    print("  ✅ Tous les tests UI ont réussi !")
    print("╚══════════════════════════════════════════╝\n")
