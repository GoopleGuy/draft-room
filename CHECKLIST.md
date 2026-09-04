# DRAFT ROOM — OPERATIONS CHECKLIST
## Repo update · Worker deploy · Two-league link

**Operator:** paxtonw · **GitHub:** GoopleGuy · **Repo:** draft-room
**League A:** The Notorious NatHab 12 — Fri Sep 4, 5:00 PM MDT — full PPR
**League B:** The Notorious Longmont Twelve — Sun Sep 6, 9:00 AM MDT — half PPR
**Both leagues are private, on one ESPN account.** One set of cookies covers both.

---

### HOW TO READ THIS

Each step has three parts. Do not proceed past a step whose VERIFY line fails.

```
☐ 1.1  ACTION   what you do
       VERIFY   what you must see before moving on
       IF NOT   what to do instead
```

Lines beginning `$` are typed into Terminal (omit the `$`). Everything in a
`code block` is exact — copy it, don't retype it.

Terminal: `⌘Space` → type `Terminal` → `Return`.

Write these down as you obtain them. You will need every one of them.

```
GitHub token (ghp_…)  : ______________________________
Worker URL            : https://espn-draft-adapter.________.workers.dev
NatHab league id      : ______________
Longmont league id    : ______________
SWID cookie           : {________-____-____-____-____________}
espn_s2 cookie        : (very long — keep in a text file, not here)
NatHab   my team id   : ____   (from the board's dropdown, Part G)
Longmont my team id   : ____   (from the board's dropdown, Part H)
NatHab   my slot      : ____   (unknown until 4:00 PM MDT)
```

---

## PART A — PREFLIGHT: WHERE ARE YOU

```
☐ A.1  ACTION   $ cd ~/Downloads/draft-room
       VERIFY   prompt now ends in  draft-room %
       IF NOT   the folder is elsewhere:  $ ls ~/Downloads | grep draft
                then cd into the one that contains docs/ and worker/

☐ A.2  ACTION   $ git status
       VERIFY   first line reads  On branch main
       IF NOT   $ git branch -M main   and repeat

☐ A.3  ACTION   $ git ls-remote origin main
       VERIFY   ONE of two outcomes — note which:
                  (a) a 40-character hash then  refs/heads/main
                      → your first push SUCCEEDED. Go to Part B.
                  (b) "Repository not found" or "Authentication failed"
                      → your push never landed. Go to A.4.

☐ A.4  ACTION   In a browser open  https://github.com/GoopleGuy/draft-room
       VERIFY   a repository page with files, OR a 404
       IF 404   github.com/new → Repository name: draft-room → Public →
                leave ALL checkboxes unticked → Create repository.
                Then continue to A.5.
       IF FILES the repo exists; your auth was the problem. Continue to A.5.

☐ A.5  ACTION   Get a token. github.com → avatar (top right) → Settings →
                scroll left sidebar to bottom → Developer settings →
                Personal access tokens → Tokens (classic) →
                Generate new token (classic).
                Note: draft-room · Expiration: 7 days · tick ONLY  repo  →
                Generate token.
       VERIFY   a string beginning  ghp_  is shown. Copy it NOW.
       IF NOT   it is shown once only. Generate again if you missed it.

☐ A.6  ACTION   $ git push -u origin main
                Username: GoopleGuy
                Password: paste the ghp_ token (nothing will echo) → Return
       VERIFY   output ends with  branch 'main' set up to track 'origin/main'
       IF NOT   "Repository not found" → A.4 again, the repo isn't created
                "Authentication failed" → token lacks  repo  scope; A.5 again

☐ A.7  ACTION   $ git ls-remote origin main
       VERIFY   a hash and  refs/heads/main
                macOS Keychain has now stored the token; you won't be asked again.
```

---

## PART B — BRING IN THE v3 FILES

The zip you downloaded is newer than what you pushed. Three files changed:
`docs/index.html`, `worker/src/index.js`, `DEPLOY.md`.

```
☐ B.1  ACTION   $ ls ~/Downloads/*.zip
       VERIFY   you see  draft-room.zip  (may be  draft-room (1).zip  or
                similar if downloaded twice — use the NEWEST one)
       IF NOT   download the zip again from the chat

☐ B.2  ACTION   $ cd ~/Downloads
                $ rm -rf draft-room-new
                $ unzip -q "draft-room.zip" -d draft-room-new
                (substitute the exact filename from B.1 inside the quotes)
       VERIFY   $ ls draft-room-new/draft-room/docs
                shows  fallback.html  index.html
       IF NOT   unzip picked the wrong file; check B.1

☐ B.3  ACTION   $ cp -R draft-room-new/draft-room/. draft-room/
                (note the trailing  /.  — it copies CONTENTS, not the folder)
       VERIFY   $ grep -o 'const BUILD = "[^"]*"' draft-room/docs/index.html
                prints  const BUILD = "pro · v5"
       IF NOT   the copy missed; repeat B.3 exactly

☐ B.4  ACTION   $ cd ~/Downloads/draft-room
                $ git status
       VERIFY   under "Changes not staged" you see at least:
                  modified:   DEPLOY.md
                  modified:   docs/index.html
                  modified:   worker/src/index.js
       IF NOT   nothing modified → B.3 copied into the wrong place

☐ B.5  ACTION   $ git add .
                $ git commit -m "v3: two-league support"
       VERIFY   a line like  3 files changed, NNN insertions(+), NNN deletions(-)

☐ B.6  ACTION   $ git push
       VERIFY   output includes  main -> main
       IF NOT   asks for credentials → paste the ghp_ token as the password

☐ B.7  ACTION   $ git config --global user.name  "Paxton W"
                $ git config --global user.email "YOUR@EMAIL"
       VERIFY   no output (silence is success). Stops the identity warning.
```

---

## PART C — GITHUB PAGES

```
☐ C.1  ACTION   Browser → github.com/GoopleGuy/draft-room → Settings tab →
                left sidebar → Pages
       VERIFY   heading "GitHub Pages"

☐ C.2  ACTION   Under "Build and deployment":
                  Source:  Deploy from a branch
                  Branch:  main
                  Folder:  /docs          ← NOT /(root)
                → Save
       VERIFY   the dropdown OFFERED /docs. (It only offers /(root) and /docs.
                That is why the board lives in a folder called docs.)
       IF NOT   /docs missing from the dropdown → docs/ wasn't pushed; B.6

☐ C.3  ACTION   Wait 60–120 s. Refresh the Pages settings page.
       VERIFY   green banner: "Your site is live at
                https://goopleguy.github.io/draft-room/"
       IF NOT   after 3 minutes → Actions tab; a failed "pages build" job
                will say why. Usually: wrong folder in C.2.

☐ C.4  ACTION   Open  https://goopleguy.github.io/draft-room/
       VERIFY   dark board. Top-left chip ends  pro · v5
                Top-right shows a grey  Manual  badge
       IF OLD   chip says v1 or v2 → hard refresh  ⌘⇧R
                still old → B.6 didn't push docs/index.html

☐ C.5  ACTION   Open  https://goopleguy.github.io/draft-room/#nathab
       VERIFY   top-left chip now BEGINS with  nathab ·
                (this is a separate saved board from the one without #)

☐ C.6  ACTION   Open  https://goopleguy.github.io/draft-room/#longmont
       VERIFY   chip begins  longmont ·
                Bookmark BOTH of these URLs. You will use them Fri and Sun.
```

---

## PART D — ESPN LEAGUE IDS

```
☐ D.1  ACTION   Browser → fantasy.espn.com → open The Notorious NatHab 12
       VERIFY   the address bar contains  leagueId=  followed by digits
       RECORD   NatHab league id = those digits

☐ D.2  ACTION   Same for The Notorious Longmont Twelve
       RECORD   Longmont league id

☐ D.3  ACTION   Still on ESPN, either league → League → Settings → Rosters tab
       VERIFY   starting lineup reads
                  QB 1 · RB 2 · WR 2 · TE 1 · FLEX 1 · D/ST 1 · K 1   (= 9)
       IF NOT   write down the real numbers — you enter them in G.3 / H.3

☐ D.4  ACTION   League → Settings → Draft tab, NatHab
       VERIFY   a line stating the number of ROUNDS
       RECORD   NatHab rounds = ____  (expect 14 or 15)
                Bench for the board = rounds − 9

☐ D.5  ACTION   Same for Longmont
       RECORD   Longmont rounds = ____  (expect 16) → Bench = 7
```

---

## PART E — ESPN COOKIES (both leagues share these)

Both leagues are on the one account, so you do this ONCE.

```
☐ E.1  ACTION   Chrome, logged in at fantasy.espn.com.
                Menu bar: View → Developer → Developer Tools
       VERIFY   a panel opens (usually bottom or right)

☐ E.2  ACTION   In that panel click the  Application  tab
                (if not visible, click  »  to find it)
                Left tree: Storage → Cookies → https://fantasy.espn.com
       VERIFY   a table of cookie names

☐ E.3  ACTION   Find row  SWID  → double-click its Value → ⌘C
       VERIFY   value looks like  {1A2B3C4D-1111-2222-3333-4A5B6C7D8E9F}
                INCLUDING the curly braces
       RECORD   SWID (with braces)

☐ E.4  ACTION   Find row  espn_s2  → double-click its Value → ⌘C
       VERIFY   a very long string of letters, digits, % and +
       RECORD   into a text file (TextEdit) — too long to write by hand

☐ E.5  NOTE     These are your login. Never paste them into a chat, a commit,
                wrangler.toml, or anything that goes to GitHub.
```

---

## PART F — CLOUDFLARE WORKER (once, serves both leagues)

```
☐ F.1  ACTION   $ node --version
       VERIFY   prints  v18  or higher (v20, v22, v24 all fine)
       IF NOT   nodejs.org → download the LTS installer → run it →
                QUIT Terminal, reopen it → repeat F.1

☐ F.2  ACTION   $ cd ~/Downloads/draft-room/worker
                $ ls src
       VERIFY   index.js
       IF NOT   you're in the wrong folder; A.1 then repeat

☐ F.3  ACTION   $ open -e wrangler.toml
       VERIFY   TextEdit opens. Edit exactly three values:

                ESPN_LEAGUE_ID = "PASTE_NATHAB_ID"
                ESPN_SEASON    = "2026"
                ALLOWED_ORIGIN = "https://goopleguy.github.io"

                ALLOWED_ORIGIN is scheme+host ONLY. No /draft-room. No trailing /.
                ⌘S to save. ⌘Q to quit TextEdit.
       NOTE     ESPN_LEAGUE_ID is only the DEFAULT. Longmont will pass its own
                id in the URL. Do not put cookies in this file.

☐ F.4  ACTION   $ npm install
       VERIFY   ends without "ERR!" lines; a  node_modules  folder appears
       IF NOT   read the last red line; usually no internet or Node too old

☐ F.5  ACTION   $ npx wrangler login
       VERIFY   a browser tab opens asking to authorise Wrangler → Allow →
                Terminal prints  Successfully logged in
       IF NOT   no Cloudflare account → cloudflare.com → Sign up (free) →
                repeat F.5

☐ F.6  ACTION   $ npx wrangler deploy
       VERIFY   last lines include a URL:
                  https://espn-draft-adapter.SOMETHING.workers.dev
       RECORD   Worker URL

☐ F.7  ACTION   $ npx wrangler secret put ESPN_SWID
                prompt: Enter a secret value:  → paste SWID incl. braces → Return
       VERIFY   ✨ Success! Uploaded secret ESPN_SWID

☐ F.8  ACTION   $ npx wrangler secret put ESPN_S2
                → paste the long espn_s2 value → Return
       VERIFY   ✨ Success! Uploaded secret ESPN_S2

☐ F.9  ACTION   $ npx wrangler deploy
       VERIFY   deploys again without error (makes certain secrets are live)

☐ F.10 ACTION   $ curl "https://espn-draft-adapter.SOMETHING.workers.dev/api/draft?leagueId=NATHAB_ID"
                (your Worker URL, your NatHab id; keep the quotes)
       VERIFY   JSON containing:
                  "healthy":true
                  "teams":{ ... 12 entries ... }
                  "league":{"size":12,"draftType":"SNAKE","keeperCount":0,...}
                  "pickCount":0     ← correct before the draft
       IF "auth"     → cookies wrong/expired. E.3–E.4, then F.7–F.9.
       IF "config" + "ESPN_SWID / ESPN_S2" → only one secret set. F.7 & F.8.
       IF "config" + "404" → wrong league id in the URL. D.1.

☐ F.11 ACTION   $ curl "https://espn-draft-adapter.SOMETHING.workers.dev/api/draft?leagueId=LONGMONT_ID"
       VERIFY   same shape, 12 teams, SNAKE. Both leagues now served.

☐ F.12 ACTION   $ curl -s "https://espn-draft-adapter.SOMETHING.workers.dev/api/players" | head -c 400
       VERIFY   begins  {"schemaVersion":1,"season":2026,"count":  and lists
                players with playerId / name / pos
       IF NOT   the board cannot match names to ESPN ids and will refuse to arm
```

---

## PART G — LINK LEAGUE A: NATHAB 12 (tonight)

```
☐ G.1  ACTION   Open  https://goopleguy.github.io/draft-room/#nathab
       VERIFY   chip begins  nathab ·

☐ G.2  ACTION   Click  Setup  (top right)
       VERIFY   a panel with Palette / League / Starting lineup / Live ESPN feed

☐ G.3  ACTION   Under LEAGUE and STARTING LINEUP enter:
                  Teams 12     My slot (leave for now)    Pool opens 8
                  QB 1  RB 2  WR 2  TE 1  Flex 1  K 1  DST 1
                  Bench = NatHab rounds − 9   (from D.4: 5 or 6)
       VERIFY   each field shows what you typed. Values save on change.
       NOTE     WR must be 2, not the default 3. This single value changes
                which player the advisor recommends first.

☐ G.4  ACTION   Under LIVE ESPN FEED → Adapter URL:
                  https://espn-draft-adapter.SOMETHING.workers.dev/api/draft?leagueId=NATHAB_ID
                Poll seconds: 3
       VERIFY   URL contains  ?leagueId=  followed by the NatHab id

☐ G.5  ACTION   Click  Test once
       VERIFY   status line:  OK — 0 picks, inProgress=false, 12 teams.
                Choose your team above.
                AND the  My ESPN team  dropdown now lists 12 team names
       IF "ESPN reports N teams but this board is set to 12" → G.3 Teams
       IF "Failed"  → F.10 again; the Worker is the problem, not the board

☐ G.6  ACTION   My ESPN team dropdown → select YOUR team name
       RECORD   the number shown before the dash = NatHab my team id
       NOTE     Get this right. Wrong team = every pick you make is filed as
                someone else's and the advisor thinks your roster is empty.

☐ G.7  ACTION   Click  Connect
       VERIFY   status:  Matched N players. Live mode armed as team X.
                Close Setup (✕). Top-right badge is GREEN:  Live 3s
       IF "Identity map unavailable" → F.12 failed; fix, then G.7 again

☐ G.8  ACTION   ⌘R  (reload the page)
       VERIFY   badge returns to green  Live  on its own within ~5 s
                chip still begins  nathab ·
       IF grey  → Setup → Connect again, then re-test G.8

☐ G.9  ACTION   Setup → Export
       VERIFY   a file  draft-board-2026-09-04.json  lands in Downloads.
                This is your backup independent of the browser.
```

---

## PART H — LINK LEAGUE B: LONGMONT TWELVE (Sunday)

Do this now while everything is fresh; it takes three minutes.

```
☐ H.1  ACTION   Open  https://goopleguy.github.io/draft-room/#longmont
       VERIFY   chip begins  longmont ·  and shows DEFAULT settings
                (12T · slot 3) — proving it is a separate board from #nathab

☐ H.2  ACTION   Setup → League / Starting lineup:
                  Teams 12    Pool opens 8
                  QB 1  RB 2  WR 2  TE 1  Flex 1  K 1  DST 1
                  Bench 7
                My slot: leave. Randomised Sun 8:00 AM MDT.

☐ H.3  ACTION   Adapter URL:
                  https://espn-draft-adapter.SOMETHING.workers.dev/api/draft?leagueId=LONGMONT_ID
                → Test once
       VERIFY   OK … 12 teams. Dropdown lists the LONGMONT team names
                (different names from G.5 — confirms the id is right)

☐ H.4  ACTION   Select your Longmont team → Connect
       VERIFY   Live mode armed as team X.  Badge green.
       RECORD   Longmont my team id
       NOTE     Your team id here is almost certainly DIFFERENT from NatHab.

☐ H.5  ACTION   Setup → Disconnect
       VERIFY   badge grey  Manual
       WHY      No point polling an idle league for two days. Reconnect
                Sunday morning (Part J).

☐ H.6  ACTION   Return to  #nathab  tab
       VERIFY   still green  Live, chip  nathab ·
                Both boards configured. They do not share state.
```

---

## PART I — REHEARSAL (do before 4:00 PM MDT)

This is the one test nobody has run: whether ESPN's REST feed keeps pace with
a live draft room. Twenty minutes now saves the actual draft.

```
☐ I.1  ACTION   ESPN → any league → Draft → Mock Draft Lobby → join a 12-team mock
                Note the mock's leagueId from the address bar.

☐ I.2  ACTION   New tab: https://goopleguy.github.io/draft-room/#mock
                Setup → Adapter URL with  ?leagueId=MOCK_ID  → Test once →
                pick your team → Connect
       VERIFY   green  Live

☐ I.3  WATCH    as the mock runs. Tick each:
       ☐ another manager picks → that name is struck through on your board
         within ~10 seconds
       ☐ YOU pick → name appears on the My team rail, NOT struck through
         (if struck through → wrong team selected in I.2)
       ☐ the pick track along the top advances
       ☐ pull wifi 20 s → badge  Stale → NO player returns to the board →
         wifi back → badge  Live  and it catches up alone
       ☐ ⌘R mid-draft → everything restores, badge green
       ☐ ⌘Z → refused with "Undo is disabled while the ESPN feed is live"
       ☐ mark someone by hand, let ESPN contradict → toast "ESPN corrected…"

☐ I.4  DECIDE
       IF picks appear within ~10 s    → live mode is GO for tonight
       IF picks lag 30 s or never show → live mode is NO-GO.
                Setup → Disconnect on #nathab. Use manual mode (Part J.5).
                The board is fully functional without the feed.
```

---

## PART J — DRAFT NIGHT: NATHAB, FRIDAY

```
☐ J.1  4:00 PM  ESPN publishes the randomised draft order.
                #nathab → Setup → My slot = your position 1–12 → close
       VERIFY   chip shows  slot N ; advisor panel now says
                Projected · 1.0N  with your pick number

☐ J.2  4:40 PM  Setup → Export.  Fresh backup with the slot set.

☐ J.3  4:50 PM  Board open, badge green Live, ESPN draft room open in a
                separate window. Do NOT run the board and ESPN in the same
                tab — you need both visible.

☐ J.4  5:00 PM  60 seconds per pick. On your turn:
                  Space              drafts the advisor's top pick
                  click Draft        on any row
                  /  name  ⇧Return   drafts a specific player by name
                The feed marks other managers' picks for you.

☐ J.5  MANUAL FALLBACK (if I.4 was NO-GO or the badge turns red):
                  /  name  Return    marks a player unavailable (~2 s)
                  /  name  ⇧Return   drafts him to you
                  Option-click Draft overrides the turn guard if the clock
                  has drifted

☐ J.6  AFTER    Setup → Export.  Your final roster, saved.
```

## PART K — DRAFT MORNING: LONGMONT, SUNDAY

```
☐ K.1  8:00 AM  #longmont → Setup → My slot → Adapter URL is already there →
                Test once → confirm your team still selected → Connect
       VERIFY   green Live, chip  longmont · slot N

☐ K.2  8:15     Cookies from Friday MAY have expired (they last days, not
                weeks — usually fine). If the badge says  Auth error:
                  E.3–E.4 (fresh cookies) → F.7–F.9 → K.1 again

☐ K.3  8:45     Export.  9:00 draft. 90 s per pick — more room than Friday.
```

---

## ABORT CRITERIA — when to stop using live mode

Any of these → Setup → Disconnect → manual mode. Nothing is lost.

- badge red  Auth error  or  Config error  and 60 s to fix isn't there
- a player you KNOW was drafted is still on the board after 30 s
- a player appears on YOUR roster that you did not draft
- the pick counter in the chip disagrees with ESPN's by more than one
- badge  Suspicious  for more than two polls

The board was a complete manual product before the feed existed. Two seconds a
pick by keyboard is slower than the feed and faster than thinking.
