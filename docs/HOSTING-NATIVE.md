# Native Linux hosting — no Docker

This is an example deployment for a small pilot on **Ubuntu 24.04 LTS**, one server with persistent local storage and sudo access. It has not been deployed from this workspace. Size the machine with a real PDF export workload; LibreOffice and image processing need working memory. A managed platform must support native dependencies, a persistent disk and a long-running Python process to use an equivalent approach.

The application runs as an unprivileged user. Nginx provides HTTPS access; the API binds only to localhost. The frontend is built on your developer machine and uploaded with the source, so the server does not need Node.js. Operational changes require the server owner's authorization.

## 1. Prepare an accepted release on Windows

Commit reviewed source, run the checks, build frontend and complete the acceptance checklist first. From the project root, create the source archive:

```bat
git archive --format=zip --output=..\valuer-source.zip HEAD
build-frontend.cmd
```

In PowerShell at the project root, archive the compiled interface and upload both files using your actual SSH account/server:

```powershell
Compress-Archive -Path .\frontend\dist -DestinationPath ..\valuer-frontend.zip -Force
scp ..\valuer-source.zip ..\valuer-frontend.zip YOUR_SSH_USER@YOUR_SERVER_IP:~/
```

The source ZIP is flat and the frontend ZIP contains `dist/`. Real settings and data are not in either archive. Use the exact committed source you built and tested. Do not copy a Windows `.venv` to Linux.

## 2. Install native server dependencies

SSH into the server. Commands below use Ubuntu's Bash shell:

```bash
sudo apt update
sudo apt install python3 python3-venv libreoffice-writer fonts-dejavu-core nginx certbot python3-certbot-nginx unzip
sudo adduser --system --group --home /var/lib/valuer valuer
sudo mkdir -p /opt/valuer
sudo unzip ~/valuer-source.zip -d /opt/valuer
sudo unzip ~/valuer-frontend.zip -d /opt/valuer/frontend
sudo chown -R valuer:valuer /opt/valuer
sudo -u valuer python3 -m venv /opt/valuer/backend/.venv
sudo -u valuer /opt/valuer/backend/.venv/bin/python -m pip install --no-cache-dir -r /opt/valuer/backend/requirements.txt
sudo -u valuer /opt/valuer/backend/.venv/bin/python /opt/valuer/scripts/setup.py
```

These commands assume a new installation. Do not unzip updates over a live installation without a backup and update plan. Check `python3 --version` is 3.12 for this guide.

## 3. Create server-only configuration

Edit the generated settings privately:

```bash
sudo -u valuer nano /opt/valuer/backend/.env
```

Keep its generated JWT secret and set:

```dotenv
DATABASE_URL=sqlite:////var/lib/valuer/data/valuer.db
DATA_DIR=/var/lib/valuer/data
ALLOW_REGISTRATION=false
CORS_ORIGINS=["https://reports.example.com"]
SOFFICE_PATH=/usr/bin/soffice
GOOGLE_MAPS_API_KEY=
GOOGLE_MAPS_SIGNING_SECRET=
MAP_REPORT_EXPORT_ALLOWED=false
```

Replace the example domain with yours. Add production Maps credentials only if needed and clear report-image licensing before enabling export. Never reuse the developer key or place these settings in Git. SQLite's absolute Unix URL has four slashes.

```bash
sudo install -d -o valuer -g valuer -m 700 /var/lib/valuer/data
sudo chmod 600 /opt/valuer/backend/.env
cd /opt/valuer/backend
sudo -u valuer .venv/bin/python -m scripts.create_user
```

Use the client's chosen account details and deliver their initial password privately. Do not write it into a command, issue or README. No email is automatically sent.

## 4. Install the service

```bash
sudo cp /opt/valuer/deploy/valuer.service /etc/systemd/system/valuer.service
sudo systemctl daemon-reload
sudo systemctl enable --now valuer
sudo systemctl status valuer --no-pager
curl --fail http://127.0.0.1:8000/api/health
```

If it fails:

```bash
sudo journalctl -u valuer -n 100 --no-pager
```

Do not share logs containing client information or secrets. Confirm `/opt/valuer/frontend/dist/index.html` exists. Service configuration uses one worker because this pilot uses SQLite and in-memory throttling.

## 5. Configure the domain and HTTPS

Set your domain's DNS A record to the server's public IPv4 address. Only add an AAAA record if IPv6 is correctly configured. Allow inbound TCP 80 and 443 through the provider firewall; restrict SSH access as appropriate. Do not expose port 8000. Before enabling/changing an OS firewall, preserve your actual SSH port and an active recovery path.

Copy the provided Nginx configuration and edit `server_name` to your real domain:

```bash
sudo cp /opt/valuer/deploy/nginx.conf /etc/nginx/sites-available/valuer
sudo nano /etc/nginx/sites-available/valuer
sudo ln -s /etc/nginx/sites-available/valuer /etc/nginx/sites-enabled/valuer
sudo nginx -t
sudo systemctl reload nginx
sudo certbot --nginx -d reports.example.com
sudo certbot renew --dry-run
```

Use your real domain in the Certbot command and select HTTPS redirect if prompted. On an existing server, check for conflicting domain configurations first; do not remove unrelated sites. Do not enter credentials into the public HTTP site before HTTPS works. Verify certificate renewal scheduling on your server.

Open your HTTPS URL and test sign-in, persistence across service restart, Word export, real PDF conversion and, when configured, actual map preview. Check the application using the fonts and template intended for the client.

Nginx configuration reference: https://nginx.org/en/docs/http/ngx_http_proxy_module.html
Certbot instructions: https://certbot.eff.org/instructions

## 6. Back up before client work and every update

Schedule protected, off-server backups of `/var/lib/valuer/data`, the template, release identification and separately protected settings. For this small pilot, briefly stop the service before taking a full data snapshot so database rows and file archives stay consistent, then restart it promptly. Agree an acceptable maintenance window with the client.

A manual example, while signed into the server:

```bash
sudo systemctl stop valuer
sudo install -d -m 700 /var/backups/valuer
sudo tar -czf /var/backups/valuer/data-$(date +%Y%m%d-%H%M%S).tar.gz -C /var/lib/valuer data
sudo systemctl start valuer
```

Inspect the tar command's result before considering the backup successful, restrict archive permissions, and copy it to protected off-server storage. This example excludes `.env` and the template: back those up separately. A backup on the same server is not sufficient. Perform a restore drill into a separate installation; see the main README.

## 7. Update from GitHub releases

1. Commit and test a change through a pull request; merge and tag an accepted version.
2. Build the same version locally and create/upload clean source and frontend archives.
3. Back up data/settings/template; stop the service during the maintenance window.
4. Extract the new source into a separate release directory and inspect it. Preserve the live `.env`, any customised template and `/var/lib/valuer/data`.
5. Deploy reviewed code and `frontend/dist`, reinstall Python requirements if changed, and apply an explicitly reviewed database migration if the schema changed.
6. Start the service, verify health and export a synthetic report before resuming work.

The package only creates an initial database schema. It does not automatically migrate existing tables. Add and test Alembic migrations before database schema evolution; `create_all()` is not a migration system. Code rollback after an incompatible data migration also needs a planned restoration strategy.

## Boundaries

These are deployment instructions and sample configurations, not a hosted service or a deployment performed for you. This pilot does not include automatic off-server backups, monitoring, email/password recovery, role-based review teams or a background PDF queue. Complete those as required by the client's usage and service commitments. See `VERIFICATION.md` for acceptance work. Hosting and domain charges depend on your selected providers; using no Docker does not make cloud infrastructure free.
