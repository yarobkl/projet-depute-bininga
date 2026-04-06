#!/usr/bin/env python3
"""
apply_i18n.py — Applique les attributs data-i18n manquants dans index.html
et ajoute les 2 clés manquantes dans i18n.js (toutes langues via deep-translator).
Usage : python3 apply_i18n.py
"""

import re
import sys

# ─── 1. Patch index.html ────────────────────────────────────────────────────

with open("index.html", "r", encoding="utf-8") as f:
    html = f.read()

patches = [

    # ── Hero eyebrow ticker ──────────────────────────────────────────────────
    (
        '<span>Campagne législative · République du Congo &nbsp;·&nbsp; </span>',
        '<span data-i18n="hero.eyebrow">Campagne législative · République du Congo &nbsp;·&nbsp; </span>',
    ),

    # ── Hero scroll ──────────────────────────────────────────────────────────
    (
        '<a href="#about" class="hero-scroll">\n    <div class="hero-scroll-line"></div>\n    <span>Découvrir</span>\n  </a>',
        '<a href="#about" class="hero-scroll">\n    <div class="hero-scroll-line"></div>\n    <span data-i18n="hero.scroll">Découvrir</span>\n  </a>',
    ),

    # ── Programme subtitle ───────────────────────────────────────────────────
    (
        '<p id="dyn-prog-sub" style="font-size:16px;color:rgba(255,255,255,.45);max-width:600px;margin:20px auto 0;font-weight:300;line-height:1.9">Six axes stratégiques pour transformer Ewo et renforcer le Congo.</p>',
        '<p id="dyn-prog-sub" data-i18n="prog.sub" style="font-size:16px;color:rgba(255,255,255,.45);max-width:600px;margin:20px auto 0;font-weight:300;line-height:1.9">Six axes stratégiques pour transformer Ewo et renforcer le Congo.</p>',
    ),

    # ── Vidéo ONU — titre et date ─────────────────────────────────────────────
    (
        '<div style="color:#fff;font-weight:700;font-size:16px;margin-bottom:6px">BININGA devant le Conseil des droits de l\'homme — ONU</div>',
        '<div style="color:#fff;font-weight:700;font-size:16px;margin-bottom:6px" data-i18n="video.un.title">BININGA devant le Conseil des droits de l\'homme — ONU</div>',
    ),
    (
        '<div style="color:rgba(255,255,255,.7);font-size:13px">Examen Périodique Universel · Genève, 30 janvier 2024</div>',
        '<div style="color:rgba(255,255,255,.7);font-size:13px" data-i18n="video.un.date">Examen Périodique Universel · Genève, 30 janvier 2024</div>',
    ),
    (
        '        Ouvrir sur UN WebTV\n      </div>',
        '        <span data-i18n="video.un.open">Ouvrir sur UN WebTV</span>\n      </div>',
    ),

    # ── Formulaire audience — Raison ─────────────────────────────────────────
    (
        '            <label>Raison de la demande *</label>\n            <textarea name="raison" id="raison-text" rows="5" placeholder="Rédigez ici votre requête. Expliquez l\'objet de votre demande, votre situation, et ce que vous attendez du Député…" style="resize:vertical"></textarea>',
        '            <label data-i18n="form.reason">Raison de la demande *</label>\n            <textarea name="raison" id="raison-text" rows="5" placeholder="Rédigez ici votre requête. Expliquez l\'objet de votre demande, votre situation, et ce que vous attendez du Député…" data-i18n-ph="form.reason.ph" style="resize:vertical"></textarea>',
    ),

    # ── Réclamation — badge ───────────────────────────────────────────────────
    (
        '          <div class="recl-badge">⚠️ Signalement officiel</div>',
        '          <div class="recl-badge" data-i18n="form.recl.badge">⚠️ Signalement officiel</div>',
    ),

    # ── Réclamation — description ─────────────────────────────────────────────
    (
        '            <label>Description du sinistre / problème *</label>\n            <textarea name="description" id="desc-sinistre" rows="3" placeholder="Décrivez précisément le problème, le sinistre ou la situation à signaler au Député…"></textarea>',
        '            <label data-i18n="form.recl.desc">Description du sinistre / problème *</label>\n            <textarea name="description" id="desc-sinistre" rows="3" placeholder="Décrivez précisément le problème, le sinistre ou la situation à signaler au Député…" data-i18n-ph="form.recl.desc.ph"></textarea>',
    ),

    # ── Géolocalisation ───────────────────────────────────────────────────────
    (
        '            <div class="geo-box-title">📍 Localisation du sinistre</div>',
        '            <div class="geo-box-title" data-i18n="form.geo.title">📍 Localisation du sinistre</div>',
    ),
    (
        '            <div class="geo-status" id="geo-status"><span class="dot"></span> Non localisé, cliquez pour géolocaliser</div>',
        '            <div class="geo-status" id="geo-status"><span class="dot"></span> <span data-i18n="form.geo.status">Non localisé, cliquez pour géolocaliser</span></div>',
    ),
    (
        '              <span aria-hidden="true">📍</span> Géolocaliser ma position\n            </button>',
        '              <span aria-hidden="true">📍</span> <span data-i18n="form.geo.btn">Géolocaliser ma position</span>\n            </button>',
    ),

    # ── Photo sinistre ────────────────────────────────────────────────────────
    (
        '            <label>📷 Photo du sinistre <span style="font-weight:400;text-transform:none;letter-spacing:0;color:#999">(optionnel, jpg/png, max 3 Mo)</span></label>',
        '            <label><span data-i18n="form.photo.lbl">📷 Photo du sinistre</span> <span style="font-weight:400;text-transform:none;letter-spacing:0;color:#999" data-i18n="form.photo.opt">(optionnel, jpg/png, max 3 Mo)</span></label>',
    ),

    # ── Contact — sidebar title ───────────────────────────────────────────────
    (
        '        <h3 class="ct-title" id="dyn-ct-sidebar-title">Quartier Général<br>de Campagne</h3>',
        '        <h3 class="ct-title" id="dyn-ct-sidebar-title" data-i18n-html="ct.sidebar.title">Quartier Général<br>de Campagne</h3>',
    ),

    # ── Contact — labels info ─────────────────────────────────────────────────
    (
        '<span class="ct-lbl">Adresse</span>',
        '<span class="ct-lbl" data-i18n="ct.lbl.address">Adresse</span>',
    ),
    (
        '<span class="ct-lbl">Téléphone</span>',
        '<span class="ct-lbl" data-i18n="ct.lbl.phone">Téléphone</span>',
    ),
    (
        '<span class="ct-lbl">Email</span><span class="ct-val" id="dyn-ct-email">',
        '<span class="ct-lbl" data-i18n="ct.lbl.email">Email</span><span class="ct-val" id="dyn-ct-email">',
    ),
    (
        '<span class="ct-lbl">Réseaux sociaux</span>',
        '<span class="ct-lbl" data-i18n="ct.lbl.social">Réseaux sociaux</span>',
    ),

    # ── Footer bottom — liens légaux ──────────────────────────────────────────
    (
        '<div class="ft-legal"><a href="#" onclick="event.preventDefault();openLegal(\'mentions\')">Mentions légales</a><a href="#" onclick="event.preventDefault();openLegal(\'confidentialite\')">Confidentialité</a><a href="#" onclick="event.preventDefault();openLegal(\'cookies\')">Cookies</a></div>',
        '<div class="ft-legal"><a href="#" onclick="event.preventDefault();openLegal(\'mentions\')" data-i18n="ft.bottom.mentions">Mentions légales</a><a href="#" onclick="event.preventDefault();openLegal(\'confidentialite\')" data-i18n="ft.bottom.privacy">Confidentialité</a><a href="#" onclick="event.preventDefault();openLegal(\'cookies\')" data-i18n="ft.bottom.cookies">Cookies</a></div>',
    ),

    # ── Mobile tabbar ─────────────────────────────────────────────────────────
    (
        '    <span class="mob-tab-lbl">Accueil</span>',
        '    <span class="mob-tab-lbl" data-i18n="mob.tab.home">Accueil</span>',
    ),
    (
        '    <span class="mob-tab-lbl">Biographie</span>',
        '    <span class="mob-tab-lbl" data-i18n="mob.tab.bio">Biographie</span>',
    ),
    (
        '    <span class="mob-tab-lbl">Actualités</span>',
        '    <span class="mob-tab-lbl" data-i18n="mob.tab.news">Actualités</span>',
    ),
    (
        '    <span class="mob-tab-lbl">Audience</span>',
        '    <span class="mob-tab-lbl" data-i18n="mob.tab.audience">Audience</span>',
    ),
    (
        '    <span class="mob-tab-lbl">Contact</span>',
        '    <span class="mob-tab-lbl" data-i18n="mob.tab.contact">Contact</span>',
    ),

    # ── Modal mentions légales ────────────────────────────────────────────────
    (
        '      <h3>Mentions légales</h3>\n      <button class="lmodal-close" onclick="closeLegal(\'mentions\')" aria-label="Fermer">✕</button>',
        '      <h3 data-i18n="modal.mentions.title">Mentions légales</h3>\n      <button class="lmodal-close" onclick="closeLegal(\'mentions\')" aria-label="Fermer" data-i18n="aria.close" data-i18n-attr="aria-label">✕</button>',
    ),
    (
        '      <h4>Éditeur du site</h4>\n      <p>Ce site est édité par la <strong>Cellule de communication de la campagne d\'Ange Aimé Wilfrid BININGA</strong>, candidat aux élections législatives de 2027 pour la 1re circonscription d\'Ewo (Cuvette-Ouest), République du Congo.</p>\n      <h4>Responsable de la publication</h4>\n      <p><strong>Ange Aimé Wilfrid BININGA</strong>, Garde des Sceaux, Ministre de la Justice, des Droits Humains et de la Promotion des Peuples Autochtones. Député de la 1re circonscription d\'Ewo depuis le 19 août 2017. Membre du Parti Congolais du Travail (PCT).</p>\n      <h4>Contact</h4>\n      <p>Ewo, département de la Cuvette-Ouest, République du Congo.<br>Pour toute demande : via le formulaire de contact disponible sur ce site.</p>\n      <h4>Hébergement</h4>\n      <p>Ce site est hébergé par un prestataire tiers. Les informations relatives à l\'hébergeur sont disponibles sur simple demande auprès de la cellule de communication.</p>\n      <h4>Propriété intellectuelle</h4>\n      <p>L\'ensemble des contenus de ce site (textes, photos, graphismes) est la propriété exclusive de la campagne Aimé BININGA ou de leurs auteurs respectifs. Toute reproduction sans autorisation préalable est interdite.</p>\n      <h4>Limitation de responsabilité</h4>\n      <p>Les informations publiées sur ce site sont fournies à titre indicatif. La campagne ne saurait être tenue responsable des inexactitudes ou omissions qui pourraient y figurer.</p>',
        '      <h4 data-i18n="modal.mentions.publisher.h">Éditeur du site</h4>\n      <p data-i18n-html="modal.mentions.publisher.p">Ce site est édité par la <strong>Cellule de communication de la campagne d\'Ange Aimé Wilfrid BININGA</strong>, candidat aux élections législatives de 2027 pour la 1re circonscription d\'Ewo (Cuvette-Ouest), République du Congo.</p>\n      <h4 data-i18n="modal.mentions.resp.h">Responsable de la publication</h4>\n      <p data-i18n-html="modal.mentions.resp.p"><strong>Ange Aimé Wilfrid BININGA</strong>, Garde des Sceaux, Ministre de la Justice, des Droits Humains et de la Promotion des Peuples Autochtones. Député de la 1re circonscription d\'Ewo depuis le 19 août 2017. Membre du Parti Congolais du Travail (PCT).</p>\n      <h4 data-i18n="modal.mentions.contact.h">Contact</h4>\n      <p data-i18n-html="modal.mentions.contact.p">Ewo, département de la Cuvette-Ouest, République du Congo.<br>Pour toute demande : via le formulaire de contact disponible sur ce site.</p>\n      <h4 data-i18n="modal.mentions.hosting.h">Hébergement</h4>\n      <p data-i18n-html="modal.mentions.hosting.p">Ce site est hébergé par un prestataire tiers. Les informations relatives à l\'hébergeur sont disponibles sur simple demande auprès de la cellule de communication.</p>\n      <h4 data-i18n="modal.mentions.ip.h">Propriété intellectuelle</h4>\n      <p data-i18n-html="modal.mentions.ip.p">L\'ensemble des contenus de ce site (textes, photos, graphismes) est la propriété exclusive de la campagne Aimé BININGA ou de leurs auteurs respectifs. Toute reproduction sans autorisation préalable est interdite.</p>\n      <h4 data-i18n="modal.mentions.liability.h">Limitation de responsabilité</h4>\n      <p data-i18n-html="modal.mentions.liability.p">Les informations publiées sur ce site sont fournies à titre indicatif. La campagne ne saurait être tenue responsable des inexactitudes ou omissions qui pourraient y figurer.</p>',
    ),

    # ── Modal achat — titre + fermer ──────────────────────────────────────────
    (
        '      <h3>Acheter le livre, 40 €</h3>\n      <button class="lmodal-close" onclick="document.getElementById(\'modal-achat\').classList.remove(\'open\');document.body.style.overflow=\'\'" aria-label="Fermer">✕</button>',
        '      <h3 data-i18n="pub.modal.title">Acheter le livre, 40 €</h3>\n      <button class="lmodal-close" onclick="document.getElementById(\'modal-achat\').classList.remove(\'open\');document.body.style.overflow=\'\'" aria-label="Fermer" data-i18n="aria.close" data-i18n-attr="aria-label">✕</button>',
    ),

    # ── Modal achat — "Choisissez votre mode" ─────────────────────────────────
    (
        '      <p style="font-size:12px;color:rgba(255,255,255,.35);margin-bottom:14px;letter-spacing:.5px;text-transform:uppercase">Choisissez votre mode d\'achat</p>',
        '      <p style="font-size:12px;color:rgba(255,255,255,.35);margin-bottom:14px;letter-spacing:.5px;text-transform:uppercase" data-i18n="pub.modal.choose">Choisissez votre mode d\'achat</p>',
    ),

    # ── Modal achat — plateformes ─────────────────────────────────────────────
    (
        '              <div class="buy-platform-name">Fnac</div>\n              <div class="buy-platform-desc">Disponible en ligne · Livraison rapide · Retrait en magasin</div>',
        '              <div class="buy-platform-name" data-i18n="pub.modal.fnac.name">Fnac</div>\n              <div class="buy-platform-desc" data-i18n="pub.modal.fnac.desc">Disponible en ligne · Livraison rapide · Retrait en magasin</div>',
    ),
    (
        '              <div class="buy-platform-name">L\'Harmattan (éditeur officiel)</div>\n              <div class="buy-platform-desc">Paiement sécurisé · Livraison mondiale · Broché ou numérique</div>',
        '              <div class="buy-platform-name" data-i18n="pub.modal.harmattan.name">L\'Harmattan (éditeur officiel)</div>\n              <div class="buy-platform-desc" data-i18n="pub.modal.harmattan.desc">Paiement sécurisé · Livraison mondiale · Broché ou numérique</div>',
    ),
    (
        '              <div class="buy-platform-desc">Livraison rapide · Prime disponible</div>',
        '              <div class="buy-platform-desc" data-i18n="pub.modal.amazon.desc">Livraison rapide · Prime disponible</div>',
    ),
    (
        '        <div class="buy-divider">ou</div>',
        '        <div class="buy-divider" data-i18n="pub.modal.or">ou</div>',
    ),
    (
        '              <div class="buy-platform-name">Commander via le bureau du Député</div>\n              <div class="buy-platform-desc">Livraison au Congo · Paiement à la livraison · Dédicace possible</div>',
        '              <div class="buy-platform-name" data-i18n="pub.modal.deputy.name">Commander via le bureau du Député</div>\n              <div class="buy-platform-desc" data-i18n="pub.modal.deputy.desc">Livraison au Congo · Paiement à la livraison · Dédicace possible</div>',
    ),

    # ── Modal achat — formulaire commande ────────────────────────────────────
    (
        '      <button onclick="showBuyOptions()" style="background:none;border:none;color:rgba(255,255,255,.4);cursor:pointer;font-size:13px;margin-bottom:16px;padding:0">← Retour aux options</button>',
        '      <button onclick="showBuyOptions()" style="background:none;border:none;color:rgba(255,255,255,.4);cursor:pointer;font-size:13px;margin-bottom:16px;padding:0" data-i18n="pub.order.back">← Retour aux options</button>',
    ),
    (
        '      <p style="font-size:13px;color:rgba(255,255,255,.45);margin-bottom:18px">Notre équipe vous contacte sous 48h pour confirmer la commande et organiser la livraison.</p>',
        '      <p style="font-size:13px;color:rgba(255,255,255,.45);margin-bottom:18px" data-i18n="pub.order.note">Notre équipe vous contacte sous 48h pour confirmer la commande et organiser la livraison.</p>',
    ),
    (
        '          <div class="fgrp"><label>Prénom *</label><input type="text" name="prenom" placeholder="Votre prénom" required></div>\n          <div class="fgrp"><label>Nom *</label><input type="text" name="nom" placeholder="Votre nom" required></div>',
        '          <div class="fgrp"><label data-i18n="form.firstname">Prénom *</label><input type="text" name="prenom" placeholder="Votre prénom" required data-i18n-ph="form.firstname.ph"></div>\n          <div class="fgrp"><label data-i18n="form.lastname">Nom *</label><input type="text" name="nom" placeholder="Votre nom" required data-i18n-ph="form.lastname.ph"></div>',
    ),
    (
        '        <div class="fgrp"><label>Téléphone *</label><input type="tel" name="telephone" placeholder="+242 XX XXX XXXX" required></div>\n        <div class="fgrp"><label>Email</label><input type="email" name="email" placeholder="votre@email.com"></div>\n        <div class="fgrp"><label>Ville / Adresse *</label><input type="text" name="adresse" placeholder="Brazzaville, Pointe-Noire, Ewo…" required></div>',
        '        <div class="fgrp"><label data-i18n="form.phone">Téléphone *</label><input type="tel" name="telephone" placeholder="+242 XX XXX XXXX" required></div>\n        <div class="fgrp"><label data-i18n="form.email">Email</label><input type="email" name="email" placeholder="votre@email.com"></div>\n        <div class="fgrp"><label data-i18n="form.address">Ville / Adresse *</label><input type="text" name="adresse" placeholder="Brazzaville, Pointe-Noire, Ewo…" required data-i18n-ph="form.address.ph"></div>',
    ),
    (
        '        <div class="fgrp"><label>Quantité</label>\n          <select name="quantite">\n            <option value="1">1 exemplaire</option>\n            <option value="2">2 exemplaires</option>\n            <option value="3">3 exemplaires</option>\n            <option value="5">5 exemplaires</option>\n            <option value="autre">Autre (préciser en note)</option>\n          </select>\n        </div>',
        '        <div class="fgrp"><label data-i18n="pub.order.qty.lbl">Quantité</label>\n          <select name="quantite">\n            <option value="1" data-i18n="pub.order.qty.1">1 exemplaire</option>\n            <option value="2" data-i18n="pub.order.qty.2">2 exemplaires</option>\n            <option value="3" data-i18n="pub.order.qty.3">3 exemplaires</option>\n            <option value="5" data-i18n="pub.order.qty.5">5 exemplaires</option>\n            <option value="autre" data-i18n="pub.order.qty.other">Autre (préciser en note)</option>\n          </select>\n        </div>',
    ),
    (
        '        <div class="fgrp"><label>Note (dédicace, précision…)</label><textarea name="note" rows="2" placeholder="Ex : dédicace souhaitée, heure de disponibilité…"></textarea></div>',
        '        <div class="fgrp"><label data-i18n="pub.order.notes.lbl">Note (dédicace, précision…)</label><textarea name="note" rows="2" placeholder="Ex : dédicace souhaitée, heure de disponibilité…" data-i18n-ph="pub.order.notes.ph"></textarea></div>',
    ),
    (
        '        <div class="order-note">💳 Paiement à la livraison ou par virement Mobile Money / bancaire. Nos équipes vous confirmeront les détails.</div>',
        '        <div class="order-note" data-i18n="pub.order.payment">💳 Paiement à la livraison ou par virement Mobile Money / bancaire. Nos équipes vous confirmeront les détails.</div>',
    ),
    (
        '        <button type="submit" class="pub-btn-primary" id="order-btn" style="width:100%;margin-top:16px;justify-content:center"><span aria-hidden="true">📦</span> Envoyer ma commande</button>',
        '        <button type="submit" class="pub-btn-primary" id="order-btn" data-i18n="pub.order.submit" style="width:100%;margin-top:16px;justify-content:center"><span aria-hidden="true">📦</span> Envoyer ma commande</button>',
    ),
    (
        '      <div id="order-ok" style="display:none;text-align:center;padding:20px 0;color:#2ecc71;font-size:15px;font-weight:600">✅ Commande enregistrée ! Notre équipe vous contacte sous 48h.</div>',
        '      <div id="order-ok" data-i18n="pub.order.success" style="display:none;text-align:center;padding:20px 0;color:#2ecc71;font-size:15px;font-weight:600">✅ Commande enregistrée ! Notre équipe vous contacte sous 48h.</div>',
    ),

    # ── Modal confidentialité ─────────────────────────────────────────────────
    (
        '      <h3>Politique de confidentialité</h3>\n      <button class="lmodal-close" onclick="closeLegal(\'confidentialite\')" aria-label="Fermer">✕</button>',
        '      <h3 data-i18n="modal.privacy.title">Politique de confidentialité</h3>\n      <button class="lmodal-close" onclick="closeLegal(\'confidentialite\')" aria-label="Fermer" data-i18n="aria.close" data-i18n-attr="aria-label">✕</button>',
    ),
    (
        '      <h4>Données collectées</h4>\n      <p>Ce site collecte des données personnelles uniquement via ses formulaires : <strong>demande d\'audience</strong> (nom, prénom, adresse, téléphone, objet) et <strong>formulaire de contact</strong> (nom, prénom, email, sujet, message).</p>\n      <h4>Finalité du traitement</h4>\n      <p>Les données collectées sont utilisées exclusivement pour <strong>répondre à vos demandes</strong> et assurer le suivi de votre contact avec l\'équipe du Député. Elles ne font l\'objet d\'aucune cession à des tiers ni d\'aucune utilisation commerciale.</p>\n      <h4>Stockage des données</h4>\n      <p>Les soumissions sont conservées dans l\'espace d\'administration sécurisé du site. Elles ne sont accessibles qu\'aux membres habilités de la cellule de communication.</p>\n      <h4>Durée de conservation</h4>\n      <p>Les données sont conservées pour la durée nécessaire au traitement de votre demande, et au maximum <strong>12 mois</strong> à compter de la soumission.</p>\n      <h4>Vos droits</h4>\n      <p>Conformément aux réglementations applicables, vous disposez d\'un droit d\'accès, de rectification et de suppression de vos données. Pour exercer ces droits, contactez-nous via le formulaire du site.</p>\n      <h4>Cookies</h4>\n      <p>Ce site n\'utilise pas de cookies de suivi ou publicitaires. Des cookies techniques essentiels au fonctionnement du site peuvent être utilisés.</p>',
        '      <h4 data-i18n="modal.privacy.collected.h">Données collectées</h4>\n      <p data-i18n-html="modal.privacy.collected.p">Ce site collecte des données personnelles uniquement via ses formulaires : <strong>demande d\'audience</strong> (nom, prénom, adresse, téléphone, objet) et <strong>formulaire de contact</strong> (nom, prénom, email, sujet, message).</p>\n      <h4 data-i18n="modal.privacy.purpose.h">Finalité du traitement</h4>\n      <p data-i18n-html="modal.privacy.purpose.p">Les données collectées sont utilisées exclusivement pour <strong>répondre à vos demandes</strong> et assurer le suivi de votre contact avec l\'équipe du Député. Elles ne font l\'objet d\'aucune cession à des tiers ni d\'aucune utilisation commerciale.</p>\n      <h4 data-i18n="modal.privacy.storage.h">Stockage des données</h4>\n      <p data-i18n-html="modal.privacy.storage.p">Les soumissions sont conservées dans l\'espace d\'administration sécurisé du site. Elles ne sont accessibles qu\'aux membres habilités de la cellule de communication.</p>\n      <h4 data-i18n="modal.privacy.duration.h">Durée de conservation</h4>\n      <p data-i18n-html="modal.privacy.duration.p">Les données sont conservées pour la durée nécessaire au traitement de votre demande, et au maximum <strong>12 mois</strong> à compter de la soumission.</p>\n      <h4 data-i18n="modal.privacy.rights.h">Vos droits</h4>\n      <p data-i18n-html="modal.privacy.rights.p">Conformément aux réglementations applicables, vous disposez d\'un droit d\'accès, de rectification et de suppression de vos données. Pour exercer ces droits, contactez-nous via le formulaire du site.</p>\n      <h4 data-i18n="modal.privacy.cookies.h">Cookies</h4>\n      <p data-i18n-html="modal.privacy.cookies.p">Ce site n\'utilise pas de cookies de suivi ou publicitaires. Des cookies techniques essentiels au fonctionnement du site peuvent être utilisés.</p>',
    ),

    # ── Modal cookies ─────────────────────────────────────────────────────────
    (
        '      <h3>Gestion des cookies</h3>\n      <button class="lmodal-close" onclick="closeLegal(\'cookies\')" aria-label="Fermer">✕</button>',
        '      <h3 data-i18n="modal.cookies.title">Gestion des cookies</h3>\n      <button class="lmodal-close" onclick="closeLegal(\'cookies\')" aria-label="Fermer" data-i18n="aria.close" data-i18n-attr="aria-label">✕</button>',
    ),
    (
        '      <h4>Qu\'est-ce qu\'un cookie ?</h4>\n      <p>Un cookie est un petit fichier déposé sur votre terminal lors de la visite d\'un site. Il permet de mémoriser des informations relatives à votre navigation.</p>\n      <h4>Cookies utilisés sur ce site</h4>\n      <p><strong>Cookies techniques (essentiels) :</strong> nécessaires au fonctionnement du site (navigation, sécurité). Ils ne peuvent pas être désactivés.</p>\n      <p><strong>Cookies de mesure d\'audience :</strong> ce site n\'utilise pas de cookies de mesure d\'audience ou d\'analyse de comportement.</p>\n      <p><strong>Cookies publicitaires :</strong> ce site ne dépose aucun cookie publicitaire ou de reciblage.</p>\n      <h4>Données stockées localement</h4>\n      <p>Ce site utilise le <strong>stockage local (localStorage)</strong> de votre navigateur uniquement pour la gestion interne de l\'administration du site. Ces données ne sont pas transmises à des tiers.</p>\n      <h4>Vos choix</h4>\n      <p>Vous pouvez à tout moment supprimer les données stockées via les paramètres de votre navigateur (<em>Outils → Confidentialité → Effacer les données de navigation</em>).</p>',
        '      <h4 data-i18n="modal.cookies.what.h">Qu\'est-ce qu\'un cookie ?</h4>\n      <p data-i18n-html="modal.cookies.what.p">Un cookie est un petit fichier déposé sur votre terminal lors de la visite d\'un site. Il permet de mémoriser des informations relatives à votre navigation.</p>\n      <h4 data-i18n="modal.cookies.used.h">Cookies utilisés sur ce site</h4>\n      <p data-i18n-html="modal.cookies.technical.p"><strong>Cookies techniques (essentiels) :</strong> nécessaires au fonctionnement du site (navigation, sécurité). Ils ne peuvent pas être désactivés.</p>\n      <p data-i18n-html="modal.cookies.analytics.p"><strong>Cookies de mesure d\'audience :</strong> ce site n\'utilise pas de cookies de mesure d\'audience ou d\'analyse de comportement.</p>\n      <p data-i18n-html="modal.cookies.advertising.p"><strong>Cookies publicitaires :</strong> ce site ne dépose aucun cookie publicitaire ou de reciblage.</p>\n      <h4 data-i18n="modal.cookies.storage.h">Données stockées localement</h4>\n      <p data-i18n-html="modal.cookies.storage.p">Ce site utilise le <strong>stockage local (localStorage)</strong> de votre navigateur uniquement pour la gestion interne de l\'administration du site. Ces données ne sont pas transmises à des tiers.</p>\n      <h4 data-i18n="modal.cookies.choices.h">Vos choix</h4>\n      <p data-i18n-html="modal.cookies.choices.p">Vous pouvez à tout moment supprimer les données stockées via les paramètres de votre navigateur (<em>Outils → Confidentialité → Effacer les données de navigation</em>).</p>',
    ),
]

applied = 0
failed = []
for old, new in patches:
    if old in html:
        html = html.replace(old, new, 1)
        applied += 1
    else:
        failed.append(old[:80].replace('\n', '↵'))

with open("index.html", "w", encoding="utf-8") as f:
    f.write(html)

print(f"✅ index.html — {applied}/{len(patches)} patches appliqués")
if failed:
    print(f"⚠️  {len(failed)} patches non trouvés :")
    for s in failed:
        print(f"   · {s}")

# ─── 2. Ajouter les 2 clés manquantes dans i18n.js (via deep-translator) ────

NEW_KEYS_FR = {
    "hero.eyebrow": "Campagne législative · République du Congo",
    "prog.sub":     "Six axes stratégiques pour transformer Ewo et renforcer le Congo.",
}

LANG_CODES = {
    "en": "en",
    "es": "es",
    "zh": "zh-CN",
    "ru": "ru",
}

try:
    from deep_translator import GoogleTranslator
    HAS_TRANSLATOR = True
except ImportError:
    HAS_TRANSLATOR = False
    print("⚠️  deep_translator non installé — traduction auto ignorée")
    print("   Installez avec : pip install deep-translator")

with open("static/i18n.js", "r", encoding="utf-8") as f:
    js = f.read()

# Vérifie si les clés existent déjà
already_exist = all(f'"{k}"' in js for k in NEW_KEYS_FR)
if already_exist:
    print("✅ i18n.js — toutes les clés existent déjà, rien à ajouter")
else:
    translations = {"fr": NEW_KEYS_FR}

    if HAS_TRANSLATOR:
        for lang, code in LANG_CODES.items():
            translations[lang] = {}
            for key, text in NEW_KEYS_FR.items():
                try:
                    tr = GoogleTranslator(source="fr", target=code).translate(text)
                    translations[lang][key] = tr
                    print(f"  [{lang}] {key} → {tr}")
                except Exception as e:
                    translations[lang][key] = text  # fallback FR
                    print(f"  ⚠️ [{lang}] {key} — échec: {e}")
    else:
        for lang in LANG_CODES:
            translations[lang] = {k: v for k, v in NEW_KEYS_FR.items()}

    def inject_keys(js_content, lang, keys_dict):
        """Injecte les clés dans la section de la langue donnée."""
        # Cherche la ligne "hero.scroll" dans la bonne section et insère après
        # On identifie la section par son marqueur (ex: fr: { ... hero.scroll: ...
        # On insère après "hero.scroll" dans la bonne section
        anchor = f'"hero.scroll"'
        # Trouve la Nème occurrence selon la langue
        lang_order = ["fr", "en", "es", "zh", "ru"]
        idx = lang_order.index(lang)
        pos = 0
        for _ in range(idx + 1):
            pos = js_content.find(anchor, pos)
            if pos == -1:
                return js_content
            if _ < idx:
                pos += 1
        # Trouve la fin de cette ligne
        eol = js_content.find('\n', pos)
        insert_str = ""
        for key, val in keys_dict.items():
            if f'"{key}"' not in js_content[pos-500:pos+2000]:
                # Échappe les guillemets dans la valeur
                val_escaped = val.replace('"', '\\"')
                insert_str += f'\n    "{key}":      "{val_escaped}",'
        if insert_str:
            return js_content[:eol] + insert_str + js_content[eol:]
        return js_content

    for lang in ["fr", "en", "es", "zh", "ru"]:
        if lang in translations:
            js = inject_keys(js, lang, translations[lang])

    with open("static/i18n.js", "w", encoding="utf-8") as f:
        f.write(js)
    print(f"✅ i18n.js — clés {list(NEW_KEYS_FR.keys())} ajoutées (5 langues)")

print("\n🎉 Terminé ! Vérifiez les fichiers puis commitez.")
