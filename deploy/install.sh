#!/usr/bin/env bash
# Install or update SME Finance Copilot on a fresh Ubuntu 22.04/24.04 VPS.
#
#   sudo bash deploy/install.sh <domain> [source-dir]
#
# <domain>      e.g. copilot.example.com (its DNS A record must already point here)
# [source-dir]  unpacked project copy; default: the directory containing this script's parent
#
# Safe to re-run for updates: the workspace (/var/lib/sme-copilot) and the env file are
# never deleted or overwritten. The app listens on 127.0.0.1:8080 only; Caddy serves HTTPS.
set -euo pipefail

DOMAIN="${1:?usage: sudo bash deploy/install.sh <domain> [source-dir]}"
SRC="$(cd "${2:-$(dirname "$0")/..}" && pwd)"
PREFIX=/opt/sme-copilot
STATE=/var/lib/sme-copilot
ETC=/etc/sme-copilot

[[ $EUID -eq 0 ]] || { echo "Run as root (sudo)." >&2; exit 1; }
[[ "$DOMAIN" =~ ^[A-Za-z0-9]([A-Za-z0-9.-]*[A-Za-z0-9])?$ ]] || { echo "Invalid domain: $DOMAIN" >&2; exit 1; }
[[ -f "$SRC/requirements.lock" && -d "$SRC/finance" ]] || { echo "Not a project copy: $SRC" >&2; exit 1; }

echo "==> Packages (Caddy from its official repository, firewall)"
apt-get update -q
apt-get install -y -q curl ca-certificates gnupg debian-keyring debian-archive-keyring apt-transport-https ufw rsync
if ! command -v caddy >/dev/null; then
  curl -1sLf https://dl.cloudsmith.io/public/caddy/stable/gpg.key | gpg --dearmor -o /usr/share/keyrings/caddy-stable-archive-keyring.gpg
  curl -1sLf https://dl.cloudsmith.io/public/caddy/stable/debian.deb.txt > /etc/apt/sources.list.d/caddy-stable.list
  apt-get update -q && apt-get install -y -q caddy
fi

echo "==> Service users"
id sme >/dev/null 2>&1 || useradd --system --home-dir "$STATE" --shell /usr/sbin/nologin sme
id sme-bridge >/dev/null 2>&1 || useradd --system --no-create-home --shell /usr/sbin/nologin sme-bridge

echo "==> Python 3.11 + pinned dependencies (uv, PyPI)"
if ! command -v uv >/dev/null; then
  curl -LsSf https://astral.sh/uv/install.sh | env UV_INSTALL_DIR=/usr/local/bin sh
fi
mkdir -p "$PREFIX"
export UV_PYTHON_INSTALL_DIR="$PREFIX/python"
uv python install 3.11
[[ -x "$PREFIX/venv/bin/python" ]] || uv venv --python 3.11 "$PREFIX/venv"
uv pip install --python "$PREFIX/venv/bin/python" --index-url https://pypi.org/simple -r "$SRC/requirements.lock"
uv pip install --python "$PREFIX/venv/bin/python" --target "$PREFIX/strata-lib" --index-url https://pypi.org/simple paramiko==4.0.0

echo "==> Application code (read-only for the service users)"
rsync -a --delete --exclude '.git' --exclude '.runtime' --exclude '.venv' --exclude '__pycache__' \
  --exclude 'artifacts' --exclude '*.secret.json' --exclude 'SSH_key.txt' "$SRC/" "$PREFIX/app/"
chown -R root:root "$PREFIX"
chmod -R go-w "$PREFIX"

echo "==> State and configuration (kept on updates)"
install -d -o sme -g sme -m 0700 "$STATE"
install -d -o root -g sme -m 0750 "$ETC"
install -d -o sme-bridge -g sme-bridge -m 0700 "$ETC/strata"
if [[ ! -f "$ETC/sme-copilot.env" ]]; then
  sed "s/__DOMAIN__/$DOMAIN/g" "$SRC/deploy/sme-copilot.env.example" > "$ETC/sme-copilot.env"
  chown root:sme "$ETC/sme-copilot.env"; chmod 0640 "$ETC/sme-copilot.env"
  echo "    created $ETC/sme-copilot.env (MODEL_PROVIDER=mock)"
else
  echo "    kept existing $ETC/sme-copilot.env"
fi

echo "==> systemd units"
install -m 0644 "$SRC/deploy/sme-copilot.service" /etc/systemd/system/sme-copilot.service
install -m 0644 "$SRC/deploy/sme-strata-bridge.service" /etc/systemd/system/sme-strata-bridge.service
systemctl daemon-reload

echo "==> Caddy (HTTPS for $DOMAIN)"
sed "s/__DOMAIN__/$DOMAIN/g" "$SRC/deploy/Caddyfile.template" > /etc/caddy/Caddyfile
caddy validate --config /etc/caddy/Caddyfile --adapter caddyfile
systemctl enable caddy >/dev/null
systemctl reload caddy || systemctl restart caddy

echo "==> Firewall: SSH, HTTP, HTTPS only"
ufw allow OpenSSH >/dev/null
ufw allow 80/tcp >/dev/null
ufw allow 443/tcp >/dev/null
ufw --force enable >/dev/null

echo "==> Start the cabinet"
systemctl enable sme-copilot >/dev/null
systemctl restart sme-copilot
for _ in $(seq 1 60); do
  curl -fsS -o /dev/null http://127.0.0.1:8080/ && break
  sleep 1
done
systemctl --no-pager --lines=5 status sme-copilot || true

cat <<DONE

Done. Open https://$DOMAIN (first certificate can take a minute).
Sign-in tokens (keep private, give each judge only what they need):
  sudo cat $STATE/workspace/local-login.secret.json
LIVE model: see docs/runbooks/deploy.md, section "Enable the LIVE model".
DONE
