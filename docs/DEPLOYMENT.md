# Deployment

The production setup is `docker-compose.prod.yml`. One command runs the whole
system behind a single web server (Caddy) on ports 80 and 443:

```
browser ──► Caddy (web) ──► /          built React app
                       └──► /api, /docs, /health ──► FastAPI (api) ──► Postgres (db)
                                                         │
                                                         └──► Redis ──► Celery (worker) ──► models, LLM
```

It runs anywhere Docker runs: a cloud server with a public HTTPS address, or
your own laptop in "production mode" for a demo.

| | Development (`make up`) | Production (`make prod-up`) |
|---|---|---|
| Frontend | Vite dev server, port 5173 | built once, served by Caddy |
| Address | http://localhost:5173 | http://localhost, or https://your-domain |
| Code | mounted, reloads on save | baked into the images |
| Database, Redis | published on the host | private to the Docker network |
| Secrets | placeholders allowed (warning) | refuses to start with placeholders |
| Restarts | manual | automatic, also after a reboot |
| Data | project `complaint-intelligence` | separate project `cis-prod` |

---

## 1. What you need

- A machine with **at least 4 GB of RAM** and 2 CPUs. The worker holds the
  DistilBERT classifier and the RoBERTa sentiment model in memory; the whole
  stack uses about 3 GB.
- Docker with the Compose plugin.
- The trained classifier in `ml/models/distilbert-v1-512/` (see
  `ml/models/README.md`). Without it the app still runs on the rule-based stub.
- For HTTPS: a domain name pointing at the server. A free option is shown below.

---

## 2. Option A: a free cloud server (Oracle Cloud)

Oracle Cloud's *Always Free* tier includes an Arm (Ampere A1) machine. Since
June 2026 the free allowance is **2 CPUs and 12 GB of RAM** in total, which is
enough. Check the current terms when you sign up; they have changed before.

1. **Create an account** at cloud.oracle.com. It asks for a card to verify
   your identity; Always Free resources are not charged.
2. **Create the server**: *Compute → Instances → Create instance*.
   - Image: **Ubuntu 22.04 or 24.04**
   - Shape: **Ampere → VM.Standard.A1.Flex**, 2 OCPUs, 12 GB memory
   - Add your SSH public key (`~/.ssh/id_ed25519.pub` on your Mac; create one
     with `ssh-keygen -t ed25519` if you have none).
   - If it says *out of capacity*, try another availability domain, or again
     later; free Arm capacity is popular.
3. **Open ports 80 and 443** in two places:
   - In the console: the instance's *Virtual cloud network → Security list →
     Add ingress rules*: source `0.0.0.0/0`, TCP, destination ports `80,443`.
   - On the server itself: Oracle's Ubuntu images block them in the local
     firewall too.
     ```bash
     ssh ubuntu@<server-ip>
     sudo iptables -I INPUT 6 -m state --state NEW -p tcp --dport 80 -j ACCEPT
     sudo iptables -I INPUT 6 -m state --state NEW -p tcp --dport 443 -j ACCEPT
     sudo netfilter-persistent save
     ```
4. **Install Docker** (on the server):
   ```bash
   curl -fsSL https://get.docker.com | sh
   sudo usermod -aG docker $USER
   exit        # log out and back in so the group change applies
   ```

Any other Linux server with 4 GB+ (a college server, DigitalOcean, AWS
Lightsail, a spare PC) works the same from step 3 of the next section.

---

## 3. Install the app

On the server (or your laptop):

```bash
git clone https://github.com/rawatridhima/Customer-Complaint-Intelligence-System.git complaint-intelligence
cd complaint-intelligence
```

**Copy the model** from your laptop (run this on the laptop, in the project folder):

```bash
scp -r ml/models/distilbert-v1-512 ubuntu@<server-ip>:~/complaint-intelligence/ml/models/
```

**Create `.env`**:

```bash
cp .env.example .env
python3 -c "import secrets; print(secrets.token_urlsafe(48))"   # run twice
nano .env
```

Set at least:

```
JWT_SECRET=<first generated value>
POSTGRES_PASSWORD=<second generated value>
SITE_ADDRESS=:80
LLM_PROVIDER=openai
LLM_BASE_URL=https://generativelanguage.googleapis.com/v1beta/openai
LLM_MODEL=gemini-3.5-flash-lite
LLM_API_KEY=<your key>
LLM_TIMEOUT_SECONDS=60
PROMPT_VERSION=v2
```

`ENVIRONMENT=production` and the database address are set by
`docker-compose.prod.yml` itself. The API refuses to start if `JWT_SECRET` is a
placeholder or shorter than 32 characters, or if the database password is a
default; the error says which.

**HTTPS (optional).** With `SITE_ADDRESS=:80` the app is plain HTTP on the
server's IP address. For HTTPS, set `SITE_ADDRESS` to a domain name that points
at the server; Caddy gets and renews a free Let's Encrypt certificate by
itself. With no domain of your own, sslip.io gives one for any IP address:
server `129.153.10.20` → `SITE_ADDRESS=129-153-10-20.sslip.io`. sslip.io is
shared by many users, so if certificate issuance is rate-limited, fall back to
`:80` or use a real domain.

**Start**:

```bash
make prod-up        # first build takes 10-20 minutes (PyTorch is large)
make prod-ps        # wait until api is "healthy"
make prod-logs      # Ctrl+C to stop following
```

Open `http://<server-ip>` (or `https://<your-domain>`).

---

## 4. Accounts and data

A fresh production database is empty.

**Real accounts.** Create the first administrator, then add the others from
the *Users* page:

```bash
make prod-admin user=priya email=priya@example.com     # asks for a password
```

**Demo accounts.** `make prod-seed` creates `agent`, `manager` and `admin`
with the passwords from the README, plus sample complaints and the knowledge
base. Those passwords are public (they are in this repository), so on a server
reachable from the internet, deactivate or change them on the *Users* page as
soon as the demo is over.

The knowledge base articles come with `make prod-seed`. Without the demo
accounts, load them with:

```bash
docker compose -f docker-compose.prod.yml exec api python -m app.seed --knowledge-base-only
```

**Charts.** `make prod-seed-history` adds three months of synthetic complaints
(marked `DEMO-`); remove them with
`docker compose -f docker-compose.prod.yml exec api python -m app.seed_history --clear`.

---

## 5. Before a demo: make it independent of the LLM

AI replies are stored once generated. Generate them for the complaints you
will show, a day ahead:

```bash
make prod-pregenerate n=10          # or: make pregenerate n=10 in development
```

It works through the most urgent open complaints, about one every 13 seconds
to stay inside free-tier limits, and stops cleanly if the daily quota runs out.
Approve the replies you will show. On the day, nothing needs the LLM: if
Gemini is slow or down, every prepared screen still works.

---

## 6. Updating

```bash
git pull
make prod-up        # rebuilds what changed; migrations run automatically
```

Data in the `cis-prod` volumes is kept.

## 7. Backups

```bash
make prod-backup    # writes backups/cis-YYYYMMDD-HHMM.sql.gz
```

Restore into a running stack (this replaces the current data):

```bash
gunzip -c backups/cis-20261026-1900.sql.gz | \
  docker compose -f docker-compose.prod.yml exec -T db psql -U cis -d cis
```

Copy backups off the server, e.g. `scp ubuntu@<server-ip>:~/complaint-intelligence/backups/*.gz .`

---

## 8. Production mode on your laptop

The same setup works locally, which is the safest option for a viva:

```bash
# in .env: SITE_ADDRESS=:80, plus a real JWT_SECRET and POSTGRES_PASSWORD
make prod-up
make prod-seed && make prod-seed-history
```

Open http://localhost. It uses its own database, separate from development,
and can run alongside it. Stop it with `make prod-down`.

---

## 9. Troubleshooting

| Symptom | Cause and fix |
|---|---|
| `api` restarts, log says *Refusing to start in production* | A placeholder secret. Set `JWT_SECRET` and `POSTGRES_PASSWORD` as in section 3. |
| `required variable POSTGRES_PASSWORD is missing` | Add `POSTGRES_PASSWORD=...` to `.env`. |
| Site unreachable from outside | Ports 80/443 closed: check the cloud security list and the server firewall (section 2, step 3). |
| Browser warns about the certificate | `SITE_ADDRESS` is a domain that does not point at this server yet, or issuance was rate-limited; `docker compose -f docker-compose.prod.yml logs web` says which. |
| Worker killed, `Exited (137)` | Out of memory. The machine needs 4 GB+. |
| Complaints stay *analysing…* | `make prod-logs` and look at `worker`. After fixing it, restart the worker: stuck complaints are re-queued automatically on start. |
| Amber *Handle this complaint manually* | The LLM failed; the bracket text says why (quota, key, timeout). Classification and everything else keep working. |
| Changed `.env`, nothing happened | `make prod-up` recreates the containers with the new values. |
