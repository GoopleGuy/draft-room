# Draft Room Pro 2026
## Corrected Deployment Runbook

This runbook starts from the exact supplied file:

```text
DraftroomProDeploy.zip
```

The archive is flat. The original `DEPLOY.md` assumes directories that are not present and instructs GitHub Pages to publish from an unsupported `/site` folder. Use this runbook instead.

> **Release gate:** Manual mode can be deployed after the packaging steps below. Do not depend on live ESPN mode in the real draft until the P0 live-state items in `draft-room-pro-final-release-review.md` are fixed and rehearsed.

---

# 1. Target repository structure

Create this layout:

```text
draft-room/
├── README.md
├── DEPLOY.md
├── .gitignore
├── docs/
│   ├── index.html
│   └── .nojekyll
├── worker/
│   ├── src/
│   │   └── index.js
│   ├── wrangler.toml
│   ├── package.json
│   └── package-lock.json
└── tools/
    └── espn-draft-watch.py
```

GitHub Pages will publish `docs/`.

Cloudflare Wrangler will run from `worker/`.

---

# 2. Prerequisites

## macOS version

Current Wrangler supports modern macOS releases. Confirm the Mac is on a supported current release.

## Node

Use an LTS Node release.

Recommended:

```text
Node 24 LTS
```

Node 22 LTS is also suitable.

Do not use Node 18 or Node 20 for a fresh deployment; both are end-of-life as of this review.

Check:

```bash
node --version
npm --version
```

If Node is missing, install the current LTS release from the official Node.js site, then open a new Terminal window.

## Python

Python is optional. It is used only for:

- local static serving in this runbook;
- the ESPN diagnostic script;
- pretty-printing JSON.

Check rather than assuming:

```bash
python3 --version
```

The deployed board and Worker do not require Python.

## Git authentication

Preferred choices:

1. GitHub Desktop;
2. GitHub CLI with `gh auth login`;
3. Git Credential Manager;
4. SSH;
5. a fine-grained personal access token.

Avoid creating a broad classic token solely for this small repository.

---

# 3. Unpack and restructure the supplied ZIP

From Terminal:

```bash
cd ~/Downloads
rm -rf draft-room
mkdir draft-room
cd draft-room
unzip ../DraftroomProDeploy.zip
```

Confirm the six source files:

```bash
ls -la
```

Now create the proper layout:

```bash
mkdir -p docs worker/src tools

mv index.html docs/index.html
mv index.js worker/src/index.js
mv wrangler.toml worker/wrangler.toml
mv espn-draft-watch.py tools/espn-draft-watch.py

touch docs/.nojekyll
```

Create `.gitignore`:

```bash
cat > .gitignore <<'EOF'
.DS_Store
node_modules/
.wrangler/
.dev.vars*
.env*
drafted.txt
*.pyc
__pycache__/
EOF
```

The original README/DEPLOY files are not accurate for the flat export. Replace `DEPLOY.md` with this runbook before publishing, and update README's layout to match the tree above.

Check:

```bash
find . -maxdepth 3 -type f | sort
```

Expected core files:

```text
./.gitignore
./DEPLOY.md
./README.md
./docs/.nojekyll
./docs/index.html
./tools/espn-draft-watch.py
./worker/src/index.js
./worker/wrangler.toml
```

---

# 4. Install Wrangler in the Worker project

Cloudflare recommends a local project installation.

```bash
cd ~/Downloads/draft-room/worker
npm init -y
npm install --save-dev wrangler@latest
```

Add convenient scripts:

```bash
npm pkg set scripts.dev="wrangler dev"
npm pkg set scripts.deploy="wrangler deploy"
```

Check:

```bash
npx wrangler --version
cat package.json
```

Do not run `npm create cloudflare@latest` inside this project. You already have the Worker code and configuration; doing so creates an unnecessary nested starter project.

---

# 5. Run syntax checks

From the repository root:

```bash
cd ~/Downloads/draft-room

python3 -m py_compile tools/espn-draft-watch.py
node --check worker/src/index.js
```

To check the inline board JavaScript:

```bash
python3 - <<'PY'
from pathlib import Path
import re

html = Path("docs/index.html").read_text(encoding="utf-8")
parts = re.findall(r"<script(?:\s[^>]*)?>(.*?)</script>", html, re.I | re.S)
Path("/tmp/draft-room-inline.js").write_text("\n".join(parts), encoding="utf-8")
PY

node --check /tmp/draft-room-inline.js
```

No output means the syntax checks passed.

---

# 6. Run the board locally

When Python 3 is available:

```bash
cd ~/Downloads/draft-room
python3 -m http.server 8000 --directory docs
```

Open in a browser:

```text
http://localhost:8000
```

Check:

- the Draft Room interface loads;
- the advisor says `Projected` before your slot;
- `/` focuses search;
- Option-click can deliberately override the turn guard;
- a manual mark survives a browser reload.

Stop with:

```text
Control-C
```

Do not test persistence from a `file://` preview. Use an HTTP origin.

---

# 7. Test direct ESPN access locally

Find the ESPN league ID from the league URL.

## Public league

```bash
cd ~/Downloads/draft-room

export ESPN_LEAGUE_ID="1234567"
export ESPN_SEASON="2026"

python3 tools/espn-draft-watch.py --once --json
```

## Private league

Retrieve the `SWID` and `espn_s2` cookies from a browser session already signed into ESPN.

Do not place them in the repository.

```bash
export ESPN_SWID='{PASTE-SWID-WITH-BRACES}'
export ESPN_S2='PASTE-ESPN-S2'

python3 tools/espn-draft-watch.py --once --json
```

Success should show:

- the correct league ID;
- the correct season;
- real team names;
- a draft block;
- zero or more picks.

Record your actual ESPN team ID from the team list.

If only one cookie is available, stop and obtain both.

---

# 8. Create and publish the GitHub repository

## Option A — GitHub Desktop

This is the simplest non-token route:

1. Add the local `draft-room` folder as a repository.
2. Commit all files.
3. Publish to GitHub.
4. A public repository works with GitHub Pages on free accounts; private Pages availability depends on plan.

## Option B — command line

Authenticate first with a supported method, such as:

```bash
gh auth login
```

Then:

```bash
cd ~/Downloads/draft-room

git init
git add .
git commit -m "Draft Room Pro 2026"
git branch -M main
git remote add origin https://github.com/YOURNAME/draft-room.git
git push -u origin main
```

Confirm the repository contains:

```text
docs/index.html
worker/src/index.js
worker/wrangler.toml
```

Confirm it does **not** contain:

```text
SWID
espn_s2
.env
.dev.vars
```

---

# 9. Enable GitHub Pages correctly

In the GitHub repository:

1. Open **Settings**.
2. Open **Pages**.
3. Source: **Deploy from a branch**.
4. Branch: **main**.
5. Folder: **/docs**.
6. Save.

The board URL will normally be:

```text
https://YOURNAME.github.io/draft-room/
```

The browser origin to use in Worker CORS configuration is:

```text
https://YOURNAME.github.io
```

It does not include `/draft-room/`.

Wait for the Pages deployment to complete, then open the site.

Manual persistence check:

1. Option-click a player's Drafted action.
2. Reload the page.
3. Confirm the mark remains.

---

# 10. Configure the Worker

Edit:

```text
worker/wrangler.toml
```

Set:

```toml
name = "espn-draft-adapter"
main = "src/index.js"
compatibility_date = "2026-09-03"

[vars]
ESPN_LEAGUE_ID = "1234567"
ESPN_SEASON = "2026"
ALLOWED_ORIGIN = "https://YOURNAME.github.io"
```

Do not put `SWID` or `espn_s2` in this file.

Check from the repository root:

```bash
grep -RInE 'espn_s2|ESPN_S2|SWID' .
```

References in documentation/code are expected. Actual cookie values are not.

---

# 11. Run the Worker locally

```bash
cd ~/Downloads/draft-room/worker
npx wrangler dev
```

Wrangler normally serves at:

```text
http://localhost:8787
```

In another Terminal:

```bash
curl -i http://localhost:8787/api/draft
curl -i http://localhost:8787/api/players
```

For a private league, local secrets belong in one ignored file, not both:

```bash
cat > .dev.vars <<'EOF'
ESPN_SWID={PASTE-SWID-WITH-BRACES}
ESPN_S2=PASTE-ESPN-S2
EOF
```

Confirm `.dev.vars` is ignored:

```bash
git status --short
```

It must not appear as an untracked file.

Stop local Wrangler with Control-C.

---

# 12. Deploy the Worker

From `worker/`:

```bash
npx wrangler login
npm run deploy
```

Record the generated URL:

```text
https://espn-draft-adapter.YOUR-SUBDOMAIN.workers.dev
```

## Private league secrets

Set both:

```bash
npx wrangler secret put ESPN_SWID
npx wrangler secret put ESPN_S2
```

Each `secret put` creates and deploys a new Worker version. A separate final `wrangler deploy` is not required merely to activate the secrets.

The current Worker should be patched to reject partial cookie configuration before production use.

---

# 13. Verify the deployed Worker

Set a shell variable:

```bash
export WORKER_URL="https://espn-draft-adapter.YOUR-SUBDOMAIN.workers.dev"
```

Check the draft route:

```bash
curl -fsS "$WORKER_URL/api/draft"
```

Check the player identity route:

```bash
curl -fsS "$WORKER_URL/api/players"
```

With Python available:

```bash
curl -fsS "$WORKER_URL/api/draft" | python3 -m json.tool
```

Expected draft response fields include:

```text
schemaVersion
source
season
leagueId
healthy
draft
picks
teams
```

Do not proceed if:

- the league ID is wrong;
- the team list is wrong;
- the team count differs from the board;
- `/api/players` fails;
- the response reports auth/config error.

---

# 14. Connect the board

After the live P0 fixes are applied:

1. Open the GitHub Pages board.
2. Open Setup.
3. Under Live ESPN feed, enter:

```text
https://espn-draft-adapter.YOUR-SUBDOMAIN.workers.dev/api/draft
```

4. Press **Test once**.
5. Verify the team count.
6. Select your team by name.
7. Press **Connect**.
8. Confirm the visible feed badge changes from Manual to Connecting and then Live.
9. Reload the page.
10. Confirm live mode resumes without rebuilding the identity map manually.

Do not connect if the selected team is not present in the current tested snapshot.

---

# 15. Rehearse end to end

A generic mock lobby may not necessarily update the exact real-league endpoint configured in the Worker.

Use one of these:

1. ESPN's league-specific practice-draft feature, after confirming the configured league endpoint actually changes;
2. a disposable ESPN test league using the same settings;
3. the real league draft with manual mode ready during the opening picks.

Test all of the following:

- opponent selection disappears from the board;
- your selection enters My Team;
- clock advances for an out-of-board player;
- an out-of-board selection by your team counts toward roster size and position;
- duplicate snapshot changes nothing;
- page reload reconnects;
- disconnect during a slow request stays disconnected;
- wrong team count blocks live mode;
- wrong team ID blocks live mode;
- 20-second network outage produces Stale without restoring players;
- recovery catches up from the full snapshot;
- manual provisional entry is reconciled when ESPN catches up;
- an ESPN correction removes the old player;
- an unsupported draft type fails closed.

Do not rely on live mode until this deployed rehearsal passes.

---

# 16. Draft-day checklist

## The day before

- test both Worker routes;
- refresh private cookies if used;
- verify Pages loads;
- export a board backup;
- verify the exact ESPN team selection;
- confirm league size and draft slot;
- run the direct Python diagnostic;
- confirm manual mode works.

## One hour before

```bash
curl -fsS "$WORKER_URL/api/draft"
curl -fsS "$WORKER_URL/api/players" > /dev/null
```

Open the board and press Test once.

## During the draft

Keep ESPN and Draft Room in separate windows.

Use the live feed as assistance, not as the only path until it has passed a rehearsal.

Manual shortcuts:

```text
/             focus player search
Enter         mark opponent selection unavailable
Shift+Enter   draft to your team when on the clock
Option        deliberate turn-guard override
Space         advisor action: queue before turn, draft on turn
Command-Z     undo manual operation
```

If live state appears wrong:

1. Disconnect.
2. Continue in manual mode.
3. Do not repeatedly reconnect while picks are occurring.
4. Export the current board after the draft.

---

# 17. Updating the application

## Frontend

Edit:

```text
docs/index.html
```

Then:

```bash
git add docs/index.html
git commit -m "Update Draft Room"
git push
```

GitHub Pages redeploys from `main /docs`.

## Worker

Edit:

```text
worker/src/index.js
worker/wrangler.toml
```

Then:

```bash
cd worker
npm test        # after a test suite is added
npm run deploy
```

Commit source/config changes, but never secret values.

## Rankings

Until the parser is fixed:

- use integer ADP;
- do not expect pasted tiers to update;
- expect the current build to reset positional display order after a rankings refresh.

---

# 18. Rollback

## Frontend

```bash
git log --oneline
git revert <bad-commit>
git push
```

## Worker

List deployments:

```bash
cd worker
npx wrangler deployments list
```

Use Cloudflare's deployment/version controls to restore a known-good version.

## Board state

Use Setup → Export before the draft.

Use Import to restore the JSON backup.

Remember that Undo currently snapshots the full board and should not be trusted to preserve authoritative live-feed state until that interaction is fixed.

---

# 19. Final deployment status

## Safe now after packaging correction

```text
GitHub Pages manual board
localStorage persistence
manual draft tracking
deterministic advisor
Python diagnostic
Worker development deployment
```

## Must pass before real live use

```text
feed badge mounted
reload restores runtime identity
manual/ESPN conflicts reconcile
external user picks count
league/team mismatch fails closed
keeper/auction/linear validation
disconnect aborts active poll
deployed ESPN rehearsal
```

Once those checks pass, the intended architecture is sound:

```text
GitHub Pages
    |
    | normalized HTTPS JSON
    v
Cloudflare Worker
    |
    | private ESPN credentials
    v
ESPN Fantasy API
```
