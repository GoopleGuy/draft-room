# DRAFT-DAY PROCEDURE — NATHAB 12
## Friday Sep 4 · Draft 5:00 PM MDT · 60 s per pick

**Read this first.** Every value below is yours — nothing to substitute.

```
League id      286283793
Worker URL     https://espn-draft-adapter.draft-room-pro.workers.dev
Board (live)   https://goopleguy.github.io/draft-room/#nathab
Lineup         QB 1 · RB 2 · WR 2 · TE 1 · Flex 1 · K 1 · DST 1 · Bench 6
Rounds         15  (180 slots ÷ 12 teams)
Cookies        SET and WORKING — confirmed by your healthy:true response
Draft order    PUBLISHED — see the slot table in Section 0
```

Format: **ACTION** → **VERIFY** → **IF NOT**. Do not pass a step whose VERIFY fails.
Commands are exact; copy them. `$` means "type this in Terminal" — omit the `$`.

---

## SECTION 0 — YOUR SLOT (do this before anything else, 30 seconds)

ESPN randomised early. This is the order from your own Worker's response.

| Slot | Team | | Slot | Team |
|---|---|---|---|---|
| **1** | Central Office Ceiling Rats | | **7** | The Besaid Aurochs |
| **2** | The Yellowstoners | | **8** | Hell Dwellers |
| **3** | Fourth and Farquaad | | **9** | Oops! All Kickers |
| **4** | Harry Squatter, Boy Who Lifted | | **10** | The Portland Powerhouse |
| **5** | Fantasy Team Portal | | **11** | The Spleen of Paraguay |
| **6** | General Sherman's Finest | | **12** | Blue-Footed Ballers |

```
☐ 0.1  Find your team. Write your slot here:  ____
       Everything the advisor says depends on this number.
       If the rest of this procedure fails, this table alone gets you drafting.
```

---

## SECTION 1 — LOCAL FILES → v5 (2 min)

```
☐ 1.1  ACTION   $ cd ~/Downloads
                $ ls *.zip
       VERIFY   draft-room.zip is present. If a newer copy has a different
                name, use that name in 1.2.

☐ 1.2  ACTION   $ rm -rf draft-room-new
                $ unzip -q draft-room.zip -d draft-room-new
                $ cp -R draft-room-new/draft-room/. draft-room/
       VERIFY   $ grep -o 'const BUILD = "[^"]*"' draft-room/docs/index.html
                prints   const BUILD = "pro · v5"
       IF NOT   the copy missed. Check 1.1's filename and repeat 1.2 exactly.
```

---

## SECTION 2 — WORKER → v5 (2 min)

Your deployed Worker is still the old code — you deployed before copying the
fix. That is why the board said "drafted twice."

```
☐ 2.1  ACTION   $ cd ~/Downloads/draft-room/worker
                $ npx wrangler deploy
       VERIFY   Uploaded espn-draft-adapter … Current Version ID: (new id)
       IF NOT   read the last line. If it mentions login: $ npx wrangler login

☐ 2.2  ACTION   $ curl -s "https://espn-draft-adapter.draft-room-pro.workers.dev/api/draft?leagueId=286283793" | head -c 400
       VERIFY   contains  "healthy":true
                contains  "pickCount":0        ← was 180. Must be 0.
                contains  "slotCount":180
       IF NOT   "pickCount":180 → the deploy didn't take; repeat 2.1
                "auth"          → cookies expired; see APPENDIX A

☐ 2.3  ACTION   $ curl -s "https://espn-draft-adapter.draft-room-pro.workers.dev/api/draft?leagueId=286283793" | grep -o '"auction":[a-z]*'
       VERIFY   "auction":false          ← was true. Must be false.

☐ 2.4  ACTION   $ curl -s "https://espn-draft-adapter.draft-room-pro.workers.dev/api/players" | head -c 200
       VERIFY   begins  {"schemaVersion":1,"season":2026,"count":
       IF NOT   the board cannot resolve names → live mode will refuse to arm.
                Not fatal: manual mode still works. Continue.
```

---

## SECTION 3 — BOARD → v5 ON PAGES (3 min, mostly waiting)

```
☐ 3.1  ACTION   $ cd ~/Downloads/draft-room
                $ git add .
                $ git commit -m "v5: slots, auction fix, auto-slot"
                $ git push
       VERIFY   output includes  main -> main
       IF NOT   asks for password → paste the ghp_ token
                "Repository not found" → Pages was never set up; skip to
                SECTION 6 (manual mode) — there is no time to fix Git now

☐ 3.2  ACTION   Wait 60–90 seconds.
                Open  https://goopleguy.github.io/draft-room/#nathab
                Hard refresh:  ⌘⇧R
       VERIFY   top-left chip ends   pro · v5
                top-right badge reads  Manual  (grey)
       IF NOT   chip says v4 or older → wait 60 s more, ⌘⇧R again
                still old after 3 min → SECTION 6 (manual) with the LOCAL
                file: double-click  ~/Downloads/draft-room/docs/index.html
```

---

## SECTION 4 — CONFIGURE THE BOARD (2 min)

```
☐ 4.1  ACTION   Setup (top right)
       VERIFY   panel opens with Palette / League / Starting lineup

☐ 4.2  ACTION   Under LEAGUE:
                  Teams  12     Pool opens  8
                Under STARTING LINEUP:
                  QB 1   RB 2   WR 2   TE 1   Flex 1   K 1   DST 1   Bench 6
       VERIFY   each field shows the value typed. They save on change.
       NOTE     WR is 2, not the default 3. Bench is 6 (15 rounds − 9).
                My slot: leave it — Section 5 fills it from ESPN. If you end
                up in manual mode, type it from Section 0.
```

---

## SECTION 5 — CONNECT THE FEED (2 min)

```
☐ 5.1  ACTION   Under LIVE ESPN FEED → Adapter URL, paste exactly:
                https://espn-draft-adapter.draft-room-pro.workers.dev/api/draft?leagueId=286283793
                Poll seconds: 3

☐ 5.2  ACTION   Click  Test once
       VERIFY   status:  OK — 0 picks, 12 teams. Draft order is set — your
                slot fills in when you choose your team and Connect.
                My ESPN team dropdown now lists the 12 names from Section 0.
       IF NOT   "Failed: …"  → Section 2 didn't land; recheck 2.2
                "ESPN reports N teams but this board is set to 12" → 4.2 Teams

☐ 5.3  ACTION   My ESPN team dropdown → select YOUR team
       VERIFY   your team name is shown in the dropdown
       NOTE     Wrong team = every one of your picks is filed as someone
                else's. Match the NAME, not a number you remember.

☐ 5.4  ACTION   Click  Connect
       VERIFY   status:  Matched N players. Live mode armed as team X.
                A toast:  ESPN draft order: you pick Nth — slot set automatically.
                Close Setup. Badge is GREEN:  Live 3s
                Chip shows  slot N  — the SAME N as your Section 0 lookup.
       IF slot differs from Section 0 → you selected the wrong team. 5.3.
       IF "Identity map unavailable" → 2.4 failed. Manual mode: SECTION 6.

☐ 5.5  ACTION   ⌘R  (reload)
       VERIFY   badge returns to green Live on its own within ~5 s
       IF NOT   Setup → Connect once more

☐ 5.6  ACTION   Setup → Export
       VERIFY   draft-board-2026-09-04.json in Downloads. Your backup.
```

---

## SECTION 6 — MANUAL MODE (if Sections 2–5 fail, or at 4:55 regardless of state)

The board is a complete product without the feed. Two seconds a pick.

```
☐ 6.1  ACTION   Open the board — Pages URL, or double-click
                ~/Downloads/draft-room/docs/index.html if Pages is not live
                Setup → Disconnect (if a feed was armed)
                Setup → Teams 12 · lineup from 4.2 · Bench 6
                Setup → My slot = your number from SECTION 0
       VERIFY   chip shows  slot N ; badge grey  Manual
                Advisor panel says  Projected · 1.0N  (your first pick)

☐ 6.2  ACTION   Setup → Export.
```

---

## SECTION 7 — READINESS, 4:50 PM

```
☐ 7.1  Board open in one window. ESPN draft room in ANOTHER window. Both visible.
☐ 7.2  Chip:  nathab · 12T · slot N · … · pro · v5
☐ 7.3  Badge:  Live  (green)  — OR you are deliberately in manual mode
☐ 7.4  Advisor panel shows a projected pick with a reason underneath it
☐ 7.5  Export done (5.6 or 6.2)
☐ 7.6  Phone away. Water. 60 seconds per pick is fast.
```

---

## SECTION 8 — IN-DRAFT OPERATIONS

### On your pick
```
Space              draft the advisor's top recommendation
click Draft        on any row
/  name  ⇧Return   draft a specific player by name
```
The advisor shows **The pick** on your turn and **Projected** otherwise. Space
only drafts when it is actually your turn — otherwise it queues.

### Other managers' picks
```
FEED LIVE     nothing — they disappear on their own, ~3 s
MANUAL MODE   /  name  Return      about two seconds
```

### If the feed misbehaves mid-draft
```
Badge Stale        keep going; it is holding state and will catch up
Badge Suspicious   if it persists 2+ polls → Setup → Disconnect → manual
Badge red          Setup → Disconnect → manual. Do not troubleshoot on the clock.
Player you KNOW is gone still showing after 30 s → Disconnect → manual
```
Disconnecting loses nothing. Every pick already on the board stays.

### Corrections
```
⌘Z                 undo — DISABLED while the feed is live (ESPN owns the picks)
Option-click Draft override the turn guard if the clock has drifted
Return button      on a struck-through row puts him back
```

### After the last pick
```
Setup → Export.  Your final roster, saved.
```

---

## APPENDIX A — cookies expired ("auth" error)

Chrome, logged in to fantasy.espn.com → View → Developer → Developer Tools →
Application → Cookies → https://fantasy.espn.com. Copy **SWID** (with braces)
and **espn_s2**. Then:

```
$ cd ~/Downloads/draft-room/worker
$ npx wrangler secret put ESPN_SWID     ← paste, Return
$ npx wrangler secret put ESPN_S2       ← paste, Return
```
Then 2.2 again. If this eats more than three minutes, go to SECTION 6.

## APPENDIX B — Sunday (Longmont)

Same Worker. Different URL and board:
```
Board    https://goopleguy.github.io/draft-room/#longmont
Adapter  https://espn-draft-adapter.draft-room-pro.workers.dev/api/draft?leagueId=LONGMONT_ID
Lineup   QB 1 · RB 2 · WR 2 · TE 1 · Flex 1 · K 1 · DST 1 · Bench 7
```
Sections 4–7 apply unchanged. Your team id and slot will be different; the
dropdown and the auto-slot handle both. Half PPR — lean pass-catchers slightly
less than tonight.
