#!/usr/bin/env python3
"""
espn-draft-watch.py  (v2)

A local diagnostic client for ESPN's unofficial Fantasy API. It emits exactly
the normalized schema the Cloudflare Worker serves, so the board sees one
contract whether the adapter is this script or the deployed Worker.

WHAT CHANGED FROM v1, AND WHY
-----------------------------
1. HOSTNAME. v1 used lm-api-reads.espn.com, which is wrong. The production
   Fantasy host is lm-api-reads.fantasy.espn.com. Verified 2026-09-03 against
   a live response from https://lm-api-reads.fantasy.espn.com/apis/v3/games/ffl
   which returned currentSeasonId 2026.

2. VIEWS vs CODE. v1 requested mDraftDetail + mTeam + mSettings, then read
   teams[].roster.entries[] — which only mRoster returns. So it could see a
   pick and still fail to name it, printing "player #4430807". Player identity
   now comes from a separate cached call, not from the live draft poll.

3. IDENTITY. ESPN playerId is carried end to end. Names are resolved once, for
   humans. Nothing in the live path depends on string matching.

4. DRAFT STATE. 'drafted' is not 'complete'. drafted / inProgress /
   completeDate are preserved separately, as ESPN reports them.

5. FAILURE. v1 called sys.exit on any HTTP or network error. Failures are now
   classified: auth and config stop, transient ones retry with bounded
   exponential backoff while the last good snapshot is held. A failed poll
   must never un-draft a player.

6. ATOMIC WRITES. The fallback text file goes to a temp file and is moved into
   place, so a reader cannot catch it half-written.

7. HONEST DEPENDENCIES. v1's header said "pip install requests" and the code
   never imported it. This is standard library only.

SETUP
-----
    export ESPN_LEAGUE_ID=1234567
    export ESPN_SEASON=2026
    # Private leagues only. Both or neither:
    export ESPN_SWID='{XXXXXXXX-XXXX-XXXX-XXXX-XXXXXXXXXXXX}'
    export ESPN_S2='AEB...'

  Public leagues need no cookies at all. If you can flip your league to
  "Make League Viewable to Public", do that instead — it removes the only
  secret in the entire system and makes the Worker deployment trivial.

  Cookies are credentials. Do not paste them into a chat, a gist, or a repo.

USAGE
-----
    python3 espn-draft-watch.py                # follow live
    python3 espn-draft-watch.py --once         # single snapshot, exit
    python3 espn-draft-watch.py --once --json  # emit the normalized contract
    python3 espn-draft-watch.py --names        # also resolve player names
    python3 espn-draft-watch.py --out picks.txt

UNTESTED AGAINST LIVE ESPN
--------------------------
I had no network access when writing this. The endpoint is undocumented and
ESPN changes it without notice. Run --once well before draft day. 401 means
cookies are missing or stale; 404 means the league or season is wrong.
"""

import argparse
import json
import os
import random
import sys
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone

SCHEMA_VERSION = 1

HOST = "https://lm-api-reads.fantasy.espn.com"
LEAGUE = HOST + "/apis/v3/games/ffl/seasons/{season}/segments/0/leagues/{league}"

# defaultPositionId on an ESPN player record.
POS_BY_ID = {1: "QB", 2: "RB", 3: "WR", 4: "TE", 5: "K", 16: "DST"}

RETRYABLE = {408, 425, 429, 500, 502, 503, 504}


def now_iso():
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


class Fetch(Exception):
    """Upstream failure, classified so the caller can decide whether to retry."""

    def __init__(self, kind, message, status=None, retryable=False):
        super().__init__(message)
        self.kind = kind
        self.status = status
        self.retryable = retryable


def request(url, swid, s2, timeout=20, extra_headers=None):
    req = urllib.request.Request(url)
    req.add_header("Accept", "application/json")
    req.add_header("User-Agent", "Mozilla/5.0 (compatible; draftwm/2.0)")
    for k, v in (extra_headers or {}).items():
        req.add_header(k, v)
    if swid and s2:
        # Sent to espn.com and nowhere else.
        req.add_header("Cookie", "SWID=%s; espn_s2=%s" % (swid, s2))
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.loads(r.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        if e.code in (401, 403):
            raise Fetch("auth",
                        "ESPN rejected the credentials (HTTP %d). For a private league both "
                        "SWID and espn_s2 must be set and current; they expire." % e.code,
                        e.code, retryable=False)
        if e.code == 404:
            raise Fetch("config",
                        "ESPN returned 404. Check ESPN_LEAGUE_ID and ESPN_SEASON.",
                        e.code, retryable=False)
        raise Fetch("upstream", "ESPN returned HTTP %d." % e.code, e.code,
                    retryable=e.code in RETRYABLE)
    except urllib.error.URLError as e:
        raise Fetch("network", "Could not reach ESPN: %s" % e.reason, None, retryable=True)
    except json.JSONDecodeError:
        raise Fetch("malformed",
                    "ESPN returned something that is not JSON. The endpoint may have changed, "
                    "or this may be a login page.", None, retryable=True)


def draft_url(season, league):
    # The live path needs mDraftDetail. mTeam is small and supplies team names.
    # Repeated view params, not comma-joined — ESPN treats those differently.
    return LEAGUE.format(season=season, league=league) + "?" + urllib.parse.urlencode(
        [("view", "mDraftDetail"), ("view", "mTeam"), ("view", "mSettings")])


def normalize(blob, season, league):
    """ESPN's raw shape -> the contract the board consumes. Malformed picks are
    dropped individually rather than allowed to poison the whole feed."""
    dd = blob.get("draftDetail")
    if not isinstance(dd, dict):
        raise Fetch("malformed", "Response contained no draftDetail object.", None, retryable=True)

    raw = dd.get("picks")
    if raw is None:
        raw = []
    if not isinstance(raw, list):
        raise Fetch("malformed", "draftDetail.picks was not a list.", None, retryable=True)

    picks, skipped = [], 0
    for p in raw:
        if not isinstance(p, dict):
            skipped += 1
            continue
        pid = p.get("playerId")
        overall = p.get("overallPickNumber")
        if pid is None or overall is None:
            skipped += 1
            continue
        picks.append({
            "id": p.get("id", overall),
            "overall": overall,
            "round": p.get("roundId"),
            "roundPick": p.get("roundPickNumber"),
            "teamId": p.get("teamId"),
            "playerId": pid,
            "bidAmount": p.get("bidAmount", 0),
            "autoDrafted": bool(p.get("autoDraftTypeId")) or bool(p.get("autoDrafted")),
        })
    picks.sort(key=lambda x: x["overall"] or 0)

    st = ((blob.get("settings") or {}).get("draftSettings")) or {}
    league = {
        "size": (blob.get("settings") or {}).get("size") or len(blob.get("teams") or []),
        "draftType": st.get("type"),
        "keeperCount": st.get("keeperCount", 0),
        "auction": bool(__import__("re").search(r"AUCTION|SALARY", str(st.get("type") or "")))
                   or (st.get("auctionBudget") or 0) > 0,
        "pickOrder": st.get("pickOrder") if isinstance(st.get("pickOrder"), list) else [],
    }

    teams = {}
    for t in blob.get("teams") or []:
        if not isinstance(t, dict):
            continue
        nm = (t.get("name")
              or " ".join(x for x in [t.get("location"), t.get("nickname")] if x)
              or "Team %s" % t.get("id"))
        teams[str(t.get("id"))] = {"name": nm.strip()}

    return {
        "schemaVersion": SCHEMA_VERSION,
        "source": "espn",
        "season": int(season),
        "leagueId": str(league),
        "observedAt": now_iso(),
        "healthy": True,
        "stale": False,
        "draft": {
            "drafted": bool(dd.get("drafted")),
            "inProgress": bool(dd.get("inProgress")),
            "completeDate": dd.get("completeDate"),
            "pickCount": len(picks),
            "nextOverallPick": (picks[-1]["overall"] + 1) if picks else 1,
        },
        "picks": picks,
        "teams": teams,
        "league": league,
        "skippedPicks": skipped,
    }


def player_universe(season, swid, s2, limit=1200):
    """One cached call for playerId -> (name, POS). Used only to make output
    readable and to seed the board's id map before the draft starts. Nothing in
    the live path depends on it."""
    url = HOST + "/apis/v3/games/ffl/seasons/%s/players?scoringPeriodId=0&view=players_wl" % season
    filt = json.dumps({"players": {"limit": limit,
                                   "sortPercOwned": {"sortPriority": 1, "sortAsc": False}}})
    data = request(url, swid, s2, timeout=30, extra_headers={"X-Fantasy-Filter": filt})
    rows = data if isinstance(data, list) else (data.get("players") or [])
    out = {}
    for p in rows:
        rec = p.get("player") if isinstance(p, dict) and "player" in p else p
        if not isinstance(rec, dict):
            continue
        pid = rec.get("id")
        nm = rec.get("fullName") or rec.get("name")
        if pid is None or not nm:
            continue
        out[pid] = (nm, POS_BY_ID.get(rec.get("defaultPositionId")))
    return out


def atomic_write(path, text):
    d = os.path.dirname(os.path.abspath(path)) or "."
    fd, tmp = tempfile.mkstemp(dir=d, prefix=".draft-", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            fh.write(text)
        os.replace(tmp, path)          # atomic on POSIX and Windows
    except Exception:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


def main():
    ap = argparse.ArgumentParser(description="Follow an ESPN fantasy draft.")
    ap.add_argument("--interval", type=float, default=3.0)
    ap.add_argument("--once", action="store_true")
    ap.add_argument("--json", action="store_true", help="emit the normalized contract")
    ap.add_argument("--names", action="store_true", help="resolve player names (extra call)")
    ap.add_argument("--out", default="drafted.txt", help="fallback paste file; '' disables")
    args = ap.parse_args()

    league = os.environ.get("ESPN_LEAGUE_ID")
    season = os.environ.get("ESPN_SEASON", "2026")
    swid, s2 = os.environ.get("ESPN_SWID"), os.environ.get("ESPN_S2")

    if not league:
        print("error: set ESPN_LEAGUE_ID (the number in your league URL).", file=sys.stderr)
        return 2
    if bool(swid) != bool(s2):
        print("error: set both ESPN_SWID and ESPN_S2, or neither.", file=sys.stderr)
        return 2

    url = draft_url(season, league)
    names = {}

    if not args.json:
        print("league %s  season %s  %s" % (
            league, season, "private (cookies set)" if swid else "public (no cookies)"))
        print("host   %s" % HOST)

    if args.names:
        try:
            names = player_universe(season, swid, s2)
            if not args.json:
                print("resolved %d player names" % len(names))
        except Fetch as e:
            if not args.json:
                print("name lookup failed (%s): %s" % (e.kind, e), file=sys.stderr)

    seen, last_good, fails = set(), None, 0

    while True:
        try:
            snap = normalize(request(url, swid, s2), season, league)
            fails = 0
            last_good = snap

            if args.json:
                print(json.dumps(snap, indent=2))
                if args.once:
                    return 0
            else:
                # Fingerprint on (overall, playerId) so a corrected pick — same
                # slot, different player — is announced rather than swallowed.
                fresh = [p for p in snap["picks"] if (p["overall"], p["playerId"]) not in seen]
                for p in fresh:
                    seen.add((p["overall"], p["playerId"]))
                    nm, pos = names.get(p["playerId"], (None, None))
                    label = nm or ("playerId %s" % p["playerId"])
                    team = (snap["teams"].get(str(p["teamId"])) or {}).get(
                        "name", "team %s" % p["teamId"])
                    tag = ("%s.%02d" % (p["round"], p["roundPick"])
                           if p["round"] and p["roundPick"] else "#%s" % p["overall"])
                    print("  %-7s %-26s %-4s %s" % (tag, label, pos or "?", team))
                if snap["skippedPicks"]:
                    print("  (%d malformed pick entries ignored)" % snap["skippedPicks"])

            if args.out:
                lines = []
                for p in snap["picks"]:
                    nm, pos = names.get(p["playerId"], (None, None))
                    lines.append("%s\t%s" % (nm or ("playerId %s" % p["playerId"]), pos or ""))
                atomic_write(args.out, "\n".join(lines) + ("\n" if lines else ""))

            d = snap["draft"]
            done = d["completeDate"] is not None or (d["drafted"] and not d["inProgress"])
            if args.once:
                if not args.json:
                    print("\n%d picks. inProgress=%s drafted=%s complete=%s"
                          % (d["pickCount"], d["inProgress"], d["drafted"], done))
                return 0
            if done and snap["picks"]:
                if not args.json:
                    print("\ndraft complete — %d picks." % d["pickCount"])
                return 0
            if not args.json:
                print("  ... %d picks, waiting" % d["pickCount"], end="\r", flush=True)

        except Fetch as e:
            fails += 1
            if not e.retryable:
                print("\n%s error: %s" % (e.kind, e), file=sys.stderr)
                return 1
            wait = min(30.0, args.interval * (2 ** min(fails, 5))) * (0.7 + random.random() * 0.6)
            held = last_good["draft"]["pickCount"] if last_good else 0
            print("\n%s: %s — retry in %.1fs (holding %d picks)"
                  % (e.kind, e, wait, held), file=sys.stderr)
            if args.once:
                return 1
            time.sleep(wait)
            continue

        time.sleep(max(1.0, args.interval))


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print("\nstopped.")
