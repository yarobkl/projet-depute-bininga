#!/bin/bash
# ─────────────────────────────────────────────────────────────
#  setup_ssl.sh — Certificat Let's Encrypt pour bininga.cg
#  À exécuter en tant que root sur le vrai serveur
# ─────────────────────────────────────────────────────────────
set -e

DOMAIN="bininga.cg"
EMAIL="admin@bininga.cg"
CERT_DIR="/etc/letsencrypt/live/$DOMAIN"

echo "======================================================"
echo "  Installation SSL Let's Encrypt pour $DOMAIN"
echo "======================================================"

# 1. Vérifier que le domaine pointe bien vers ce serveur
SERVER_IP=$(hostname -I | awk '{print $1}')
DOMAIN_IP=$(dig +short "$DOMAIN" 2>/dev/null | tail -1)
echo ""
echo "IP de ce serveur : $SERVER_IP"
echo "IP du domaine    : ${DOMAIN_IP:-'(non résolu)'}"
if [ "$SERVER_IP" != "$DOMAIN_IP" ]; then
    echo ""
    echo "⚠️  ATTENTION : Le domaine $DOMAIN ne pointe pas encore vers ce serveur."
    echo "   Configure le DNS chez ton registrar :"
    echo ""
    echo "   Type  Nom                  Valeur"
    echo "   A     bininga.cg           $SERVER_IP"
    echo "   A     www.bininga.cg       $SERVER_IP"
    echo ""
    read -p "Continuer quand même ? (o/N) " -n 1 -r
    echo
    [[ $REPLY =~ ^[Oo]$ ]] || exit 1
fi

# 2. Installer certbot si absent
if ! command -v certbot &>/dev/null; then
    echo ""
    echo "📦 Installation de certbot..."
    apt-get update -q
    apt-get install -y certbot
fi

# 3. Arrêter temporairement le serveur Bininga sur le port 80
BININGA_PID=$(pgrep -f "python.*server.py" || true)
if [ -n "$BININGA_PID" ]; then
    echo "⏸  Arrêt temporaire du serveur Bininga (PID $BININGA_PID)..."
    kill "$BININGA_PID" 2>/dev/null || true
    sleep 2
fi

# 4. Obtenir le certificat
echo ""
echo "🔐 Demande du certificat Let's Encrypt..."
certbot certonly \
    --standalone \
    --non-interactive \
    --agree-tos \
    --email "$EMAIL" \
    -d "$DOMAIN" \
    -d "www.$DOMAIN"

# 5. Vérifier
if [ -f "$CERT_DIR/fullchain.pem" ] && [ -f "$CERT_DIR/privkey.pem" ]; then
    echo ""
    echo "✅ Certificat obtenu avec succès !"
    echo "   fullchain : $CERT_DIR/fullchain.pem"
    echo "   clé privée: $CERT_DIR/privkey.pem"
    echo ""
    echo "   Expiration : $(openssl x509 -enddate -noout -in $CERT_DIR/fullchain.pem)"
else
    echo "❌ Échec : certificat non trouvé dans $CERT_DIR"
    exit 1
fi

# 6. Configurer le renouvellement automatique (cron)
CRON_JOB="0 3 * * * certbot renew --quiet --deploy-hook 'pkill -HUP -f server.py || true'"
( crontab -l 2>/dev/null | grep -v certbot; echo "$CRON_JOB" ) | crontab -
echo "🔄 Renouvellement automatique configuré (tous les jours à 3h)"

# 7. Redémarrer le serveur Bininga
echo ""
echo "🚀 Redémarrage du serveur Bininga..."
cd "$(dirname "$0")"
nohup python3 server.py > server.log 2>&1 &
echo "✅ Serveur redémarré (PID $!)"

echo ""
echo "======================================================"
echo "  Ton site est maintenant sécurisé : https://$DOMAIN"
echo "======================================================"
