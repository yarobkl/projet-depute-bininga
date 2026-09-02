"""Contrats de confidentialité de l'intégration Google Analytics 4."""

from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def read(relative: str) -> str:
    return (ROOT / relative).read_text(encoding="utf-8")


def test_public_page_loads_local_consent_manager_only() -> None:
    html = read("index.html")
    assert "static/analytics-consent.css" in html
    assert 'static/analytics-consent.js' in html
    assert "https://www.googletagmanager.com/gtag/js" not in html


def test_ga4_is_blocked_until_explicit_consent() -> None:
    source = read("static/analytics-consent.js")
    assert 'const MEASUREMENT_ID = "G-N283W7662X"' in source
    for signal in (
        'analytics_storage: "denied"',
        'ad_storage: "denied"',
        'ad_user_data: "denied"',
        'ad_personalization: "denied"',
    ):
        assert signal in source
    assert source.index("if (!analyticsAllowed()) return;") < source.index(
        'script.src = "https://www.googletagmanager.com/gtag/js?id="'
    )
    assert "deleteAnalyticsCookies" in source
    assert 'window["ga-disable-" + MEASUREMENT_ID] = true' in source


def test_consent_is_reversible_and_does_not_collect_form_values() -> None:
    source = read("static/analytics-consent.js")
    assert 'rejectAll: () => applyChoice(false)' in source
    assert "openPreferences: showPreferences" in source
    assert "const blocked = /(email|mail|phone|telephone|name|nom|prenom|address|adresse|message|reason|raison|code)/i" in source
    assert "CONSENT_LIFETIME_MS = 180 * 24 * 60 * 60 * 1000" in source
    assert "ANALYTICS_COOKIE_LIFETIME_SECONDS = 13 * 30 * 24 * 60 * 60" in source


def test_legal_copy_describes_analytics_in_every_language() -> None:
    html = read("index.html")
    translations = read("static/i18n.js")
    assert "Google Analytics 4" in html
    assert "Il n'est pas chargé avant votre consentement" in html
    assert translations.count("Google Analytics 4") >= 5
    assert "ce site n'utilise pas de cookies de mesure d'audience" not in translations
    assert "this site does not use audience measurement" not in translations


def test_operational_tracking_and_leads_respect_consent() -> None:
    core = read("static/index-core.js")
    forms = read("static/public-form-hardening.js")
    assert core.count("BiningaConsent.onAnalytics") >= 2
    assert 'BiningaAnalytics.track("programme_view"' in core
    assert 'BiningaAnalytics.track("book_purchase_click"' in core
    assert 'BiningaAnalytics.track("generate_lead"' in forms
    assert 'BiningaAnalytics.track("sign_up"' in forms
    assert "bininga_livre_clics" not in core


def test_security_policies_allow_only_required_google_endpoints() -> None:
    for relative in ("server.py", "vercel_public_fastpath.py"):
        source = read(relative)
        assert "https://www.googletagmanager.com" in source
        assert "https://www.google-analytics.com" in source
        assert "https://*.google-analytics.com" in source
    fastpath = read("vercel_public_fastpath.py")
    assert '"analytics-consent.css", "analytics-consent.js"' in fastpath


def main() -> None:
    test_public_page_loads_local_consent_manager_only()
    test_ga4_is_blocked_until_explicit_consent()
    test_consent_is_reversible_and_does_not_collect_form_values()
    test_legal_copy_describes_analytics_in_every_language()
    test_operational_tracking_and_leads_respect_consent()
    test_security_policies_allow_only_required_google_endpoints()
    print("✅ Google Analytics 4 — consentement et confidentialité valides")


if __name__ == "__main__":
    main()
