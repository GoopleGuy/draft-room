# Deploying tonight — macOS, step by step

Written for a MacBook with nothing installed. Every step has a **check** so you
find out immediately if something is wrong, rather than at 7pm tomorrow.

Budget about 35 minutes. Phases 1–3 (~10 min) get you a working public board.
Phases 4–6 add the live ESPN feed and are optional — **the board is fully usable
without them.**

Throughout: `⌘Space` → type `Terminal` → Enter opens a terminal. Lines starting
with `$` are things you type (don't type the `$`).

---

## Phase 0 — Decide one thing first

**Can you make your ESPN league public?** In ESPN: League → Settings → Basic
Settings → *Make League Viewable to Public* → Yes.

If yes, the entire cookie problem disappears. No secrets, no expiry, no 401 at
the worst possible moment. If your league-mates object, you can flip it back
after the draft. I'd strongly take this option.

---

## Phase 1 — Get the files onto your Mac (3 min)

Download the project and unzip it. Then:

```
$ cd ~/Downloads/draft-room        # wherever you unzipped it
$ ls
```

**Check** — you should see exactly:

```
README.md   DEPLOY.md   .gitignore
docs/       worker/     tools/      research/   reviews/
```

If `docs/` is missing you have the wrong folder. `cd` into the one containing it.

`docs/` is the folder GitHub Pages publishes — it holds the board, not
documentation. That name is forced by GitHub: branch-mode Pages can only
publish from `/(root)` or `/docs`, nothing else. Review documents live in
`reviews/`.

---

## Phase 2 — Run it locally before publishing anything (3 min)

macOS ships with Python, so no install needed.

```
$ cd docs
$ python3 -m http.server 8000
```

Open **http://localhost:8000** in Chrome or Safari.

**Check:**
- Top-left reads `Draft Room` with `12T · slot 3 · Sep 3 · pro · v3`
- Far right of the top bar shows a grey **Manual** badge — that's the live-feed
  status indicator, off until you connect it
- Six position columns plus a My team rail on the right
- The advisor band shows **`Projected · 1.03`** (not "The pick") — correct,
  because pick 1.01 isn't yours
- Press `/` — the search box focuses

**Test persistence, which is the thing that actually matters:**
1. Click **Drafted** on any player *(you'll get "Not your pick" — that's the
   turn guard. Hold **Option** and click again to override.)*
2. Press `⌘R` to reload
3. The player should still be marked

If he isn't, the browser is blocking storage — check you're on
`http://localhost:8000` and not a `file://` path.

Stop the server with `Control-C` when done.

---

## Phase 3 — Publish to GitHub Pages (5 min)

### 3a. Create the repo

Go to **github.com/new**. Name it `draft-room`. **Public** (Pages is free only
on public repos for free accounts). Don't add a README. Click *Create*.

### 3b. Push

macOS may prompt to install developer tools the first time you run `git` — accept it.

```
$ cd ~/Downloads/draft-room
$ git init
$ git add .
$ git commit -m "Draft Room Pro"
$ git branch -M main
$ git remote add origin https://github.com/YOURNAME/draft-room.git
$ git push -u origin main
```

If it asks for a password, GitHub wants a **Personal Access Token**, not your
password: github.com → Settings → Developer settings → Personal access tokens →
Tokens (classic) → Generate new token → tick `repo` → copy it and paste as the
password.

**Check:** `git log --oneline` shows your commit, and the files appear on GitHub.

### 3c. Turn on Pages

Repo → **Settings** → **Pages** (left sidebar) →
Source: **Deploy from a branch** → Branch: **main**, Folder: **/docs** → **Save**.

`/docs` is the only subfolder GitHub offers here — that's why the board lives
there. The `.nojekyll` file inside it stops GitHub from running the folder
through its Jekyll processor, which would otherwise mangle the file.

Wait 1–2 minutes. Refresh the Settings→Pages screen until it shows a green
"Your site is live at…" banner.

Your URL: **`https://YOURNAME.github.io/draft-room/`**

**Check:** open it. Same board as local. Draft someone (Option-click), reload,
he's still marked.

> **Write these two down**, you need both later:
> - Board URL: `https://YOURNAME.github.io/draft-room/`
> - **Origin**: `https://YOURNAME.github.io` — scheme and host only.
>   **Not** the `/draft-room` part. Origins never include a path.

**You now have a working, free, public draft board.** Everything below is the
optional live ESPN feed.

---

## Phase 4 — Prove ESPN will talk to you (5 min)

Do this *before* deploying anything. If it fails, you've lost five minutes
instead of your draft.

### 4a. Find your league ID

Open your league on ESPN. The URL contains `leagueId=1234567`. That number.

### 4b. Public league

```
$ cd ~/Downloads/draft-room
$ export ESPN_LEAGUE_ID=1234567
$ export ESPN_SEASON=2026
$ python3 tools/espn-draft-watch.py --once --json
```

### 4c. Private league — get the cookies

Chrome, logged in to ESPN:
`View → Developer → Developer Tools` → **Application** tab → left sidebar
**Storage → Cookies → https://fantasy.espn.com** → find **`SWID`** and
**`espn_s2`**. Copy each value.

`SWID` looks like `{1A2B3C4D-...}` — **include the braces**. `espn_s2` is a very
long string.

```
$ export ESPN_SWID='{PASTE-INCLUDING-BRACES}'
$ export ESPN_S2='PASTE-THE-LONG-STRING'
$ python3 tools/espn-draft-watch.py --once --json
```

Use **single quotes** — the values contain characters the shell would otherwise
mangle.

**Check — success looks like:**

```json
{
  "schemaVersion": 1,
  "draft": { "pickCount": 0, "inProgress": false, ... },
  "picks": [],
  "teams": { "1": {"name": "..."}, "2": {"name": "..."} }
}
```

`pickCount: 0` before your draft is correct. What matters is that `teams` lists
your league.

**Now find your team ID** — in that `teams` block, note the number next to your
own team name. Write it down.

**If it fails:**
- `401` → cookies missing, wrong, or expired. Re-copy them.
- `404` → wrong league ID or season.
- `Could not reach ESPN` → check your internet.

> Cookies are credentials. Don't paste them into a chat, a gist, or a commit.

---

## Phase 5 — Deploy the Worker (10 min)

**Why this exists:** ESPN sends no CORS header, so a page on `github.io` cannot
call it directly. Something server-side has to. Cloudflare's free tier allows
100,000 requests/day; a 3-hour draft polled every 3s is ~3,600.

### 5a. Install Node

Check first — you may already have it:

```
$ node --version
```

If that prints `v18` or higher, skip ahead. Otherwise download the **LTS**
installer from **nodejs.org**, run it, then **open a new Terminal window** and
check again.

### 5b. Configure

```
$ cd ~/Downloads/draft-room/worker
$ ls src/
```

**Check:** you see `index.js`. `wrangler.toml` points at `src/index.js`; if
that file isn't there the deploy fails immediately.

```
$ open -e wrangler.toml
```

TextEdit opens. Change three lines:

```toml
ESPN_LEAGUE_ID = "1234567"                    # your league id
ESPN_SEASON = "2026"
ALLOWED_ORIGIN = "https://YOURNAME.github.io" # origin only, no /draft-room
```

Save (`⌘S`) and close.

### 5c. Deploy

```
$ npm install
$ npx wrangler login
```

`npm install` pulls Wrangler locally from `package.json` so `npx` uses a known
version rather than fetching whatever is newest. It writes a
`package-lock.json` — commit that too.

A browser opens — authorise it. (Free Cloudflare account required; sign up at
cloudflare.com if you don't have one.)

```
$ npx wrangler deploy
```

**Check:** it prints a URL like
`https://espn-draft-adapter.YOURNAME.workers.dev`. Write it down.

### 5d. Secrets — private leagues only

```
$ npx wrangler secret put ESPN_SWID
```
Paste the SWID value (with braces), press Enter. Then:
```
$ npx wrangler secret put ESPN_S2
```

Redeploy so they take effect:
```
$ npx wrangler deploy
```

> These go in as **secrets**, never into `wrangler.toml` — that file is committed
> to a public repo.

### 5e. Verify the Worker

```
$ curl https://espn-draft-adapter.YOURNAME.workers.dev/api/draft
```

**Check:** same JSON shape as Phase 4, now with a `league` block:

```json
"league": { "size": 12, "draftType": "SNAKE", "keeperCount": 0, "auction": false }
```

`draftType` must read `SNAKE` and `keeperCount` must be `0`. The board refuses
anything else — linear, auction, and keeper formats are not implemented, and
it fails closed rather than quietly miscounting your turns.

If you see `{"error":{"kind":"auth"...}}` the secrets didn't take — redeploy.
If you see `kind: "config"` mentioning `ESPN_SWID / ESPN_S2`, you set one
cookie but not the other. Set both or neither.

Also check the identity route:

```
$ curl -s https://espn-draft-adapter.YOURNAME.workers.dev/api/players | head -c 300
```

**Check:** a list of players with `playerId`, `name`, `pos`. The board needs this
to match names to ESPN ids **once**, before the draft.

---

## Phase 5½ — Configure the board for YOUR league (2 min, do not skip)

The board ships with `WR: 3`. ESPN's standard lineup is `WR: 2` plus a FLEX,
and that one number changes replacement level for every wide receiver and
therefore the first recommendation the advisor gives you. Confirm on ESPN:
League → Settings → **Rosters** tab shows the exact starter breakdown, and the
**Draft** tab shows the number of rounds.

Open the board → **Setup** → set:

| | NatHab 12 (tonight) | Longmont Twelve (Sunday) |
|---|---|---|
| Teams | 12 | 12 |
| QB / RB / WR / TE / Flex / K / DST | 1 / 2 / **2** / 1 / 1 / 1 / 1 | 1 / 2 / **2** / 1 / 1 / 1 / 1 |
| Bench | 5 if the Draft tab says 14 rounds, 6 if it says 15 | 7 |
| My slot | **unknown until 4:00 PM MDT** — ESPN randomises one hour before | set Sunday at 8:00 AM |

Use a separate board per league so their picks never mix:

- Tonight: `https://googleguy.github.io/draft-room/#nathab`
- Sunday: `https://googleguy.github.io/draft-room/#longmont`

The word after `#` shows in the top-left chip so you always know which one is
open. Each remembers its own settings and picks independently.

## Phase 6 — Connect the board (3 min)

Open your Pages URL. **Setup** → **Live ESPN feed**.

1. **Adapter URL** — one Worker serves both leagues; the league id rides on
   the URL:
   - NatHab: `https://espn-draft-adapter.YOURNAME.workers.dev/api/draft?leagueId=NATHAB_ID`
   - Longmont: `https://espn-draft-adapter.YOURNAME.workers.dev/api/draft?leagueId=LONGMONT_ID`

   Both leagues are on your one ESPN account, so the same two cookies cover both.
2. Press **Test once**

   **Check:** the status line reads `OK — 0 picks, inProgress=false, 12 teams.
   Choose your team above.` and the **My ESPN team** dropdown fills with real
   team names.

   If it warns *"ESPN reports 10 teams but this board is set to 12"* — fix
   **Teams** in Setup first. A size mismatch makes every snake calculation wrong.

3. **Choose your team** from the dropdown.
4. Press **Connect**

   **Check:** `Matched N players. Live mode armed as team X.` and the
   **Manual** badge at the top right turns green: **`Live 2s`**. Click that
   badge any time to reopen this panel.

   **Reload the page.** The badge should come back green on its own — live
   mode persists across reloads. If it comes back grey, the identity map
   didn't save; press Connect again.

If it says *"Identity map unavailable — live mode not armed"*, the `/api/players`
route failed. The board deliberately refuses to run blind rather than polling
forever and matching nothing. Manual mode still works.

---

## Phase 7 — Rehearse with an ESPN mock draft (20 min, do this tonight)

This is the only step that tests the thing I could never test: whether ESPN's
REST view updates promptly during a live draft.

ESPN → your league → **Draft** → **Mock Draft Lobby**. Join one.

Watch for:

- [ ] Picks disappear from your board within a few seconds of happening in ESPN
- [ ] **Your** picks land on the My team rail (not struck through as "gone").
      If they show as gone, your team dropdown is set to the wrong team.
- [ ] Other managers' picks show struck through
- [ ] The pick track advances and the clock keeps up
- [ ] **Pull your wifi for 20 seconds.** Badge goes `Stale`. **No player comes
      back to the board.** Reconnect — it catches up on its own.
- [ ] **Reload the page mid-draft.** State restores.
- [ ] Late in the draft, an out-of-pool player gets taken. The clock should
      still advance, and the badge should show `N unmatched`.
- [ ] **Take an out-of-pool player yourself.** He won't appear on the board,
      but the My team counter should still go up by one and the advisor
      should stop trying to fill that slot.
- [ ] **Mark someone by hand, then let ESPN contradict you.** You should get a
      toast saying ESPN corrected your mark, and the board should show ESPN's
      version. ESPN wins every disagreement while the feed is healthy.
- [ ] **Try ⌘Z while live.** It should refuse — undo is disabled while ESPN
      owns the picks. Disconnect first if you genuinely need it.

If the picks *don't* appear within ~10 seconds, ESPN's REST view is lagging
behind their draft room. **Disconnect the feed and use manual mode** — search a
name, press Enter, done in about two seconds.

---

## Draft-day operating notes

**Before you start:** Setup → **Export**. That's a JSON file on your Mac,
independent of the browser. If anything goes wrong you can Import it back.

**Keyboard, on the clock:**
- `/` — jump to search
- type a name + `Enter` — mark unavailable (someone else took him)
- type a name + `Shift+Enter` — draft to your team
- `Space` — draft the advisor's top pick
- `⌘Z` — undo *(disabled while the live feed is on; ESPN owns the picks)*
- **Option-click** — override the turn guard when you genuinely need to

**Badge meanings:** `Live 2s` good · `Stale` holding last good state, no data
lost · `Suspicious` ESPN sent fewer picks than before, refused · `Auth error`
cookies expired, re-run Phase 5d · `Manual` feed off.

**If anything feels wrong, disconnect the feed.** The board with manual entry is
the reliable path, and it was the whole product two versions ago.

---

## Pushing a fix after you've deployed

Board changes: edit `docs/index.html`, then

```
$ git add docs/index.html && git commit -m "update board" && git push
```

Pages redeploys in about a minute. Hard-refresh (`⌘⇧R`) to bypass the cache.
Your saved picks live in the browser, not the file, so they survive.

Worker changes: `cd worker && npx wrangler deploy`.

## Updating rankings on the morning of the draft

Setup → **Refresh rankings** → paste a table → **Apply as rankings**.

Format: `rank · name · pos · team · bye · adp`, tab/comma/pipe/markdown all
parse. Your picks and your column ordering survive the refresh.

---

## Known limits, stated plainly

- **The board holds 156 players; a 12-team × 16-round draft is 192 picks.** Late
  selections outside the pool show as `unmatched`. The clock still advances,
  and if *you* take one it still counts against your roster — but he was never
  on your board and the advisor knows nothing about him. Add depth before the
  draft by pasting a deeper ranking list (250+ is comfortable).
- **ESPN's API is undocumented.** The hostname was verified 3 Sep 2026 against a
  live response. It can change without notice.
- **`mDraftDetail` latency during a live draft is untested.** Phase 7 is how you
  find out.
- **Auction and keeper leagues are rejected**, not silently mishandled.
- **CORS is not authentication.** Anyone with your Worker URL can call it and see
  your league's pick list. For a personal board that's usually fine — but it is
  a real tradeoff, not a non-issue.
