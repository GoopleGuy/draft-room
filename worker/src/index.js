/**
 * ESPN draft adapter — Cloudflare Worker
 *
 * Serves the same normalized contract as tools/espn-draft-watch.py, so the
 * board consumes one schema regardless of which adapter is in front of it.
 *
 * Its job is deliberately boring: hold the credentials, call ESPN, validate
 * enough to notice bad upstream state, normalize, return small JSON. It makes
 * no fantasy decisions — all ranking and recommendation logic stays in the
 * browser, where it is fast, free, and testable.
 *
 * WHY A PROXY EXISTS AT ALL
 * ESPN sends no Access-Control-Allow-Origin header, so a page on
 * username.github.io cannot call it directly no matter how the league is
 * configured. Something server-side has to make the request. That is the only
 * reason this file exists.
 *
 * DEPLOY
 *   npm create cloudflare@latest -- espn-draft-adapter
 *   # replace src/index.js with this file, then:
 *   npx wrangler secret put ESPN_SWID     # private leagues only
 *   npx wrangler secret put ESPN_S2       # private leagues only
 *   npx wrangler deploy
 *
 * CONFIG lives in wrangler.toml [vars]; SECRETS via `wrangler secret put`.
 * Never put SWID or espn_s2 in wrangler.toml — that file gets committed.
 *
 * FREE TIER: Workers Free allows 100,000 requests/day and 10ms CPU. A
 * three-hour draft polled every 3 seconds is about 3,600 requests and this
 * handler is well under 10ms, so the whole thing runs at no cost.
 */

const SCHEMA_VERSION = 1;
const HOST = "https://lm-api-reads.fantasy.espn.com";

/* Short cache so several open tabs don't multiply upstream load. Live state,
   so this must stay small — a stale board is worse than a slow one. */
const CACHE_SECONDS = 2;

function cors(env, extra = {}) {
  const origin = env.ALLOWED_ORIGIN || "*";
  return {
    "Access-Control-Allow-Origin": origin,
    "Access-Control-Allow-Methods": "GET, OPTIONS",
    "Access-Control-Allow-Headers": "Content-Type",
    "Vary": "Origin",
    ...extra,
  };
}

function json(body, status, env, extra = {}) {
  return new Response(JSON.stringify(body), {
    status,
    headers: {
      "Content-Type": "application/json; charset=utf-8",
      "Cache-Control": `public, max-age=${CACHE_SECONDS}`,
      ...cors(env, extra),
    },
  });
}

/* Errors are sanitised: the client learns the class of failure so it can show
   the right banner, and nothing about credentials or upstream internals. */
function fail(kind, message, status, env) {
  return json({
    schemaVersion: SCHEMA_VERSION,
    source: "espn",
    healthy: false,
    stale: true,
    error: { kind, message },
    observedAt: new Date().toISOString(),
  }, status, env);
}

function normalize(blob, season, leagueId) {
  const dd = blob && blob.draftDetail;
  if (!dd || typeof dd !== "object") {
    return { err: ["malformed", "Response contained no draftDetail object."] };
  }
  const raw = dd.picks == null ? [] : dd.picks;
  if (!Array.isArray(raw)) {
    return { err: ["malformed", "draftDetail.picks was not a list."] };
  }

  let skipped = 0;
  const picks = [];
  for (const p of raw) {
    if (!p || typeof p !== "object" || p.playerId == null || p.overallPickNumber == null) {
      skipped++;
      continue;
    }
    picks.push({
      id: p.id ?? p.overallPickNumber,
      overall: p.overallPickNumber,
      round: p.roundId ?? null,
      roundPick: p.roundPickNumber ?? null,
      teamId: p.teamId ?? null,
      playerId: p.playerId,
      bidAmount: p.bidAmount ?? 0,
      autoDrafted: Boolean(p.autoDraftTypeId || p.autoDrafted),
    });
  }
  picks.sort((a, b) => (a.overall || 0) - (b.overall || 0));

  // League shape, from mSettings. The browser refuses anything but a
  // zero-keeper snake draft, so these fields must be here to refuse on.
  const st = (blob.settings && blob.settings.draftSettings) || {};
  const league = {
    size: (blob.settings && blob.settings.size) ?? (blob.teams ? blob.teams.length : null),
    draftType: st.type ?? null,               // "SNAKE" | "LINEAR" | "AUCTION" | ...
    keeperCount: st.keeperCount ?? 0,
    auction: /AUCTION|SALARY/i.test(String(st.type || "")) || (st.auctionBudget || 0) > 0,
    pickOrder: Array.isArray(st.pickOrder) ? st.pickOrder : [],
  };

  const teams = {};
  for (const t of blob.teams || []) {
    if (!t || typeof t !== "object") continue;
    const nm = t.name || [t.location, t.nickname].filter(Boolean).join(" ") || `Team ${t.id}`;
    teams[String(t.id)] = { name: String(nm).trim() };
  }

  return {
    snap: {
      schemaVersion: SCHEMA_VERSION,
      source: "espn",
      season: Number(season),
      leagueId: String(leagueId),
      observedAt: new Date().toISOString(),
      healthy: true,
      stale: false,
      draft: {
        drafted: Boolean(dd.drafted),
        inProgress: Boolean(dd.inProgress),
        completeDate: dd.completeDate ?? null,
        pickCount: picks.length,
        nextOverallPick: picks.length ? picks[picks.length - 1].overall + 1 : 1,
      },
      picks,
      teams,
      league,
      skippedPicks: skipped,
    },
  };
}

/* The board needs playerId -> name exactly once, before the draft, to build
   its id map. After that the live path is integer-only. This route is cached
   hard because the player universe barely moves during a season. */
async function playersRoute(env, headers) {
  const season = env.ESPN_SEASON || "2026";
  const url = `${HOST}/apis/v3/games/ffl/seasons/${season}/players?scoringPeriodId=0&view=players_wl`;
  const filter = JSON.stringify({
    players: { limit: 1500, sortPercOwned: { sortPriority: 1, sortAsc: false } },
  });
  const res = await fetch(url, { headers: { ...headers, "X-Fantasy-Filter": filter } });
  if (res.status === 401 || res.status === 403)
    return { err: ["auth", "Player lookup rejected the adapter's credentials."] };
  if (res.status === 404) return { err: ["config", "Player lookup returned 404 — check ESPN_SEASON."] };
  if (res.status === 429) return { err: ["ratelimit", "ESPN is rate limiting the player lookup."] };
  if (!res.ok) return { err: ["upstream", `Player lookup returned HTTP ${res.status}.`] };
  let data;
  try { data = await res.json(); }
  catch (e) { return { err: ["malformed", "Player lookup returned a non-JSON body."] }; }

  const rows = Array.isArray(data) ? data : (data.players || []);
  const players = [];
  for (const row of rows) {
    const rec = (row && row.player) ? row.player : row;
    if (!rec || rec.id == null) continue;
    const name = rec.fullName || rec.name;
    if (!name) continue;
    players.push({
      playerId: rec.id,
      name,
      pos: POS_BY_ID[rec.defaultPositionId] || null,
    });
  }
  return { players };
}

const POS_BY_ID = { 1: "QB", 2: "RB", 3: "WR", 4: "TE", 5: "K", 16: "DST" };

export default {
  async fetch(request, env) {
    if (request.method === "OPTIONS") {
      return new Response(null, { status: 204, headers: cors(env) });
    }
    const url = new URL(request.url);
    const isPlayers = url.pathname.endsWith("/api/players");
    if (!isPlayers && !url.pathname.endsWith("/api/draft") && url.pathname !== "/") {
      return fail("config", "Unknown path. Use /api/draft or /api/players.", 404, env);
    }
    if (request.method !== "GET") {
      return fail("config", "Use GET.", 405, env);
    }

    const season = env.ESPN_SEASON || "2026";
    const leagueId = env.ESPN_LEAGUE_ID;
    if (!leagueId) {
      return fail("config", "ESPN_LEAGUE_ID is not configured on the adapter.", 500, env);
    }
    // Exactly one cookie set is a misconfiguration, not a public league.
    // Treating it as public would turn a typo into a silent 401 later.
    if (Boolean(env.ESPN_SWID) !== Boolean(env.ESPN_S2)) {
      return fail("config",
        "Only one of ESPN_SWID / ESPN_S2 is set. Set both (private league) or neither (public).",
        500, env);
    }

    const upstream =
      `${HOST}/apis/v3/games/ffl/seasons/${season}/segments/0/leagues/${leagueId}` +
      `?view=mDraftDetail&view=mTeam&view=mSettings`;

    const headers = {
      "Accept": "application/json",
      "User-Agent": "Mozilla/5.0 (compatible; draftwm/2.0)",
    };
    // Private leagues only. Public leagues need no credentials at all.
    if (env.ESPN_SWID && env.ESPN_S2) {
      headers["Cookie"] = `SWID=${env.ESPN_SWID}; espn_s2=${env.ESPN_S2}`;
    }

    if (isPlayers) {
      let out;
      try { out = await playersRoute(env, headers); }
      catch (e) { return fail("network", "Could not reach ESPN.", 502, env); }
      if (out.err) return fail(out.err[0], out.err[1], 502, env);
      return json({ schemaVersion: SCHEMA_VERSION, season: Number(season),
                    count: out.players.length, players: out.players },
                  200, env, { "Cache-Control": "public, max-age=3600" });
    }

    let res;
    const started = Date.now();
    try {
      res = await fetch(upstream, {
        headers,
        cf: { cacheTtl: CACHE_SECONDS, cacheEverything: false },
      });
    } catch (e) {
      return fail("network", "Could not reach ESPN.", 502, env);
    }

    if (res.status === 401 || res.status === 403) {
      return fail("auth",
        "ESPN rejected the adapter's credentials. For a private league, SWID and espn_s2 " +
        "must be set as Worker secrets and refreshed when they expire.", 502, env);
    }
    if (res.status === 404) {
      return fail("config", "ESPN returned 404 — check ESPN_LEAGUE_ID and ESPN_SEASON.", 502, env);
    }
    if (res.status === 429) {
      return fail("ratelimit", "ESPN is rate limiting. Back off and retry.", 429, env);
    }
    if (!res.ok) {
      return fail("upstream", `ESPN returned HTTP ${res.status}.`, 502, env);
    }

    let blob;
    try {
      blob = await res.json();
    } catch (e) {
      return fail("malformed", "ESPN returned a non-JSON body.", 502, env);
    }

    const out = normalize(blob, season, leagueId);
    if (out.err) return fail(out.err[0], out.err[1], 502, env);

    // Diagnostics without secrets. Never log cookie values.
    console.log(JSON.stringify({
      at: out.snap.observedAt,
      status: res.status,
      ms: Date.now() - started,
      picks: out.snap.draft.pickCount,
      inProgress: out.snap.draft.inProgress,
      skipped: out.snap.skippedPicks,
    }));

    return json(out.snap, 200, env);
  },
};
