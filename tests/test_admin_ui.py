"""
Tests de l'interface admin — vérifications du HTML (admin.html) et du JavaScript (static/admin.js)
Ces tests s'assurent que les éléments UI et les fonctions JS de gestion des
utilisateurs sont bien présents et corrects.
"""
import json
import os
import re
import subprocess
import sys
import tempfile

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

# ── Résolution d'identifiant de dossier (setStatus / addNote / pingDepute) ──

def test_find_entry_idx_matches_real_hex_ids():
    """Les vrais _id serveur (secrets.token_hex, sans tiret) doivent être
    trouvés par correspondance exacte, jamais retomber sur un index de
    tableau arbitraire — régression du bug qui bloquait la mise à jour de
    statut (KPI "En attente" bloqué) car _id ne contient jamais de '-'."""
    js = _js()
    match = re.search(r"function _findEntryIdx\(all, idOrIdx\) \{.*?\n\}", js, re.S)
    assert match, "_findEntryIdx doit être défini dans admin.js"
    fn_src = match.group(0)

    harness = fn_src + """
    const assert = require('assert');
    // _id réel : hex sans tiret (comme secrets.token_hex côté serveur).
    const all = [
      { _id: '9f1a2b3c4d5e6f708192a3b4', label: 'zero' },
      { _id: 'a3f9e21b4c5d6e7f8091a2b3', label: 'un' },
      { _id: 'd8e7f6a5b4c3d2e1f0091827', label: 'deux' },
    ];
    // Doit trouver l'entrée par _id exact, quelle que soit sa position ou
    // son premier caractère (chiffre ou lettre).
    assert.strictEqual(_findEntryIdx(all, 'a3f9e21b4c5d6e7f8091a2b3'), 1,
      "doit matcher l'entrée 'un' par son _id réel, pas un index déduit");
    assert.strictEqual(_findEntryIdx(all, 'd8e7f6a5b4c3d2e1f0091827'), 2,
      "doit matcher l'entrée 'deux' même si son id ne parse pas comme nombre");
    assert.strictEqual(_findEntryIdx(all, 'inconnu'), -1,
      "un id absent ne doit correspondre à aucune entrée");
    console.log('OK');
    """
    with tempfile.NamedTemporaryFile(mode="w", suffix=".js", delete=False, encoding="utf-8") as f:
        f.write(harness)
        path = f.name
    try:
        result = subprocess.run(["node", path], capture_output=True, text=True, timeout=10)
        assert result.returncode == 0 and "OK" in result.stdout, (
            f"_findEntryIdx doit résoudre les vrais _id hex sans tiret : "
            f"stdout={result.stdout!r} stderr={result.stderr!r}"
        )
    finally:
        os.unlink(path)


def test_sync_messages_discards_stale_ghost_after_id_repair():
    """Un dossier synchronisé AVANT que le serveur lui répare son _id
    (localStorage garde alors un id synthétique 'bininga_audiences-XXXX')
    ne doit pas créer de doublon fantôme une fois que le serveur renvoie le
    même dossier avec son vrai _id — sinon l'admin clique sur la carte
    fantôme, dont l'id ne correspond à rien côté serveur, et le statut ne
    bouge jamais malgré le toast de confirmation."""
    js = _js()
    match = re.search(r"async function syncMessages\(\) \{.*?\n\}", js, re.S)
    assert match, "syncMessages doit être défini dans admin.js"
    fn_src = match.group(0)

    harness = fn_src + """
    const assert = require('assert');

    // État AVANT réparation serveur : le client avait généré un id
    // synthétique (comme le faisait normalizeMessage avant que le serveur
    // garantisse toujours un _id réel).
    global.localStorage = {
      _store: {
        bininga_audiences: JSON.stringify([{
          _id: 'bininga_audiences-Z2hvc3RfaWQ',
          nom: 'Goma', prenom: 'Jude', _date: '2026-06-06 10:46:12',
          _status: 'en_attente'
        }])
      },
      getItem(k) { return this._store[k] ?? null; },
      setItem(k, v) { this._store[k] = v; }
    };

    // Réponse serveur : même dossier, désormais avec un vrai _id (réparé
    // par load_contacts()/_heal_missing_contact_ids côté serveur).
    global.fetch = async () => ({
      json: async () => ({
        ok: true,
        audiences: [{
          _id: 'd1063ceb512bbda0672d3b87',
          nom: 'Goma', prenom: 'Jude', _date: '2026-06-06 10:46:12',
          _status: 'en_attente'
        }],
        contacts: []
      })
    });
    global.apiFetch = global.fetch;
    global.SESSION_TOKEN = 'tok';

    syncMessages().then(() => {
      const merged = JSON.parse(global.localStorage.getItem('bininga_audiences'));
      assert.strictEqual(merged.length, 1,
        'un seul enregistrement doit subsister, pas de doublon fantôme : ' + JSON.stringify(merged));
      assert.strictEqual(merged[0]._id, 'd1063ceb512bbda0672d3b87',
        "l'entrée survivante doit porter le vrai _id serveur");
      console.log('OK');
    }).catch(e => { console.error(e); process.exit(1); });
    """
    with tempfile.NamedTemporaryFile(mode="w", suffix=".js", delete=False, encoding="utf-8") as f:
        f.write(harness)
        path = f.name
    try:
        result = subprocess.run(["node", path], capture_output=True, text=True, timeout=10)
        assert result.returncode == 0 and "OK" in result.stdout, (
            f"syncMessages doit éliminer le doublon fantôme après réparation du _id : "
            f"stdout={result.stdout!r} stderr={result.stderr!r}"
        )
    finally:
        os.unlink(path)


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
        test_find_entry_idx_matches_real_hex_ids,
        test_sync_messages_discards_stale_ghost_after_id_repair,
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
