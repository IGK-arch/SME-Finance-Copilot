# Deploy the cabinet to a VPS under your .com domain

Result: `https://<your-domain>` serves the synthetic SME Finance Copilot cabinet
(sandbox bank, synthetic data) with an automatic Let's Encrypt certificate. The app
itself still listens on `127.0.0.1:8080` only; Caddy is the only public listener.
The model is MOCK by default; the LIVE Strata model is an explicit second step.

```
browser ──HTTPS──> Caddy :443 ──> 127.0.0.1:8080 scripts.serve (user sme)
                                     ├─ sandbox bank  127.0.0.1:<random>
                                     ├─ worker
                                     └─ LIVE only: 127.0.0.1:18443 strata_bridge (user sme-bridge) ──SSH──> GPU server
```

## 0. Requirements

- Ubuntu 22.04 or 24.04 VPS, x86_64, 2 vCPU / 4 GB RAM / 20 GB disk, root or sudo.
- DNS: an `A` record `<your-domain> → <VPS IPv4>` (and `www` if you want the redirect).
  Check with `nslookup <your-domain>` before installing: the certificate needs it.
- Ports 80 and 443 reachable from the internet (also open them in the provider's panel).

## 1. Copy the project to the server

On your Windows machine, from the project folder, make a clean copy without
infrastructure details and send it:

```powershell
.venv\Scripts\python.exe -m scripts.submission_copy --out ..\sme-release
tar -czf ..\sme-release.tgz -C .. sme-release
scp ..\sme-release.tgz <user>@<VPS-IP>:/tmp/
```

Only git-tracked files are copied: no `.runtime`, tokens, `SSH_key.txt` or `.venv`.

## 2. Install

```bash
ssh <user>@<VPS-IP>
cd /tmp && tar -xzf sme-release.tgz
sudo bash /tmp/sme-release/deploy/install.sh <your-domain> /tmp/sme-release
```

The script installs Caddy and Python 3.11 (via uv), the pinned `requirements.lock`,
creates users `sme` / `sme-bridge`, the systemd services, the HTTPS site and the
firewall (22, 80, 443 only), then starts the cabinet. It never deletes
`/var/lib/sme-copilot` or overwrites `/etc/sme-copilot/sme-copilot.env`.

## 3. Sign in

```bash
sudo cat /var/lib/sme-copilot/workspace/local-login.secret.json
```

Open `https://<your-domain>` and paste the `OWNER` value. Approving a payment asks for
the same token again. Give judges only the role they need (e.g. `OWNER` for the full
demo, `AUDITOR` for read-only). Everyone with the same token sees and changes the same
synthetic company.

## 4. Enable the LIVE model (optional)

Prompts with the synthetic company's data then go over SSH to the GPU server; the
cabinet shows this in Copilot and in Settings → *Data & integrity*.

1. Copy from your Windows machine (never commit them):
   `SSH_key.txt` and the pinned `known_hosts` used by `.runtime/strata-client`.
   ```bash
   sudo install -o sme-bridge -g sme-bridge -m 0600 SSH_key.txt /etc/sme-copilot/strata/ssh_key
   sudo install -o sme-bridge -g sme-bridge -m 0600 known_hosts /etc/sme-copilot/strata/known_hosts
   ```
2. Create the bridge config from `deploy/bridge.example.json` with the real SSH
   host/port/user and a new token (`openssl rand -hex 32`):
   ```bash
   sudo install -o sme-bridge -g sme-bridge -m 0600 bridge.secret.json /etc/sme-copilot/strata/bridge.secret.json
   sudo systemctl enable --now sme-strata-bridge
   sudo journalctl -u sme-strata-bridge -n 20   # expect "Strata SSH bridge ready"
   ```
3. In `/etc/sme-copilot/sme-copilot.env` comment `MODEL_PROVIDER=mock`, uncomment the
   LIVE block and set `SME_MODEL_SECRET` to the same bridge token. Then
   `sudo systemctl restart sme-copilot`. The badge in the top bar shows `MODEL LIVE`.

The bridge refuses unknown host keys (no accept-new), so a missing or wrong
`known_hosts` stops it instead of connecting to an impostor. If the GPU server is down,
Copilot runs fail visibly (FAILED with a reason); there is no silent fallback to MOCK.
To switch back: restore `MODEL_PROVIDER=mock` and restart `sme-copilot`.

## 5. Check

```bash
curl -sI https://<your-domain> | grep -iE "^HTTP|strict-transport|content-security"
curl -s -o /dev/null -w "%{http_code}\n" https://<your-domain>/legacy   # 404
sudo -u sme /opt/sme-copilot/venv/bin/python -m scripts.verify_audit --directory /var/lib/sme-copilot/workspace
```

## Operate

| Task | Command |
| --- | --- |
| Logs | `sudo journalctl -u sme-copilot -f` (and `-u sme-strata-bridge`, `-u caddy`) |
| Restart | `sudo systemctl restart sme-copilot` |
| Update code | copy a new release to `/tmp`, re-run `install.sh` with the same domain (data kept) |
| Reset the demo company | `sudo systemctl stop sme-copilot && sudo mv /var/lib/sme-copilot/workspace /var/lib/sme-copilot/workspace.$(date +%s) && sudo systemctl start sme-copilot` (new tokens are generated) |
| Back up | `sudo tar -czf sme-backup.tgz -C /var/lib/sme-copilot workspace` while stopped |

## Security notes for the submission

- Data is synthetic and the bank is a sandbox; `install.sh` keeps `DATA_MODE=synthetic`,
  `EXECUTION_BACKEND=sandbox` and all `ALLOW_*` switches false (startup refuses others).
- Public perimeter: TLS by Caddy, HSTS, CSP, `nosniff`, `frame-ancestors 'none'`,
  `no-referrer`; exact `SME_PUBLIC_ORIGIN` check + SameSite=Strict, `Secure`, `HttpOnly`
  session cookie; failed sign-ins limited per client IP; step-up lockout per user;
  `/legacy` and `/hooks` not exposed; request bodies capped at 2 MB.
- The services run as unprivileged users with systemd sandboxing (`ProtectSystem=strict`,
  writable only `/var/lib/sme-copilot`); the SSH key is readable only by `sme-bridge`.
- Tokens do not expire; rotate by resetting the demo company after judging.
