import test from 'node:test';
import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
// Load the Worker's ES module without changing the Wrangler package format.
const source = await readFile(new URL('../src/index.js', import.meta.url), 'utf8');
const { default: worker } = await import(`data:text/javascript;base64,${Buffer.from(source).toString('base64')}`);
const baseEnv = { ESPN_LEAGUE_ID: '123', ESPN_SEASON: '2026' };
const privateEnv = { ...baseEnv, ESPN_SWID: 'test-swid', ESPN_S2: 'test-s2' };
const draft = { draftDetail: { picks: [] }, teams: [{id: 1, name: 'Team A'}] };

for (const route of ['/api/draft', '/api/players']) {
  for (const privateMode of [false, true]) {
    test(`${route}: ${privateMode ? 'private' : 'public'} cache policy`, async t => {
      const env = privateMode ? privateEnv : baseEnv;
      const upstream = [];
      t.mock.method(globalThis, 'fetch', async (url, options) => {
        upstream.push({ url, options });
        return Response.json(route === '/api/players' ? [{id: 5, fullName: 'Player', defaultPositionId: 1}] : draft);
      });
      t.mock.method(console, 'log', () => {});
      const res = await worker.fetch(new Request(`https://worker.test${route}?leagueId=456`), env);
      assert.equal(res.status, 200);
      const data = await res.json();
      assert.equal(upstream.length, 1);
      if (privateMode) {
        assert.equal(res.headers.get('Cache-Control'), 'private, no-store');
        assert.equal(upstream[0].options.cache, 'no-store');
        assert.equal(upstream[0].options.cf, undefined);
        assert.equal(upstream[0].options.headers.Cookie, 'SWID=test-swid; espn_s2=test-s2');
      } else {
        assert.equal(res.headers.get('Cache-Control'), route === '/api/players' ? 'public, max-age=3600' : 'public, max-age=2');
        assert.equal(upstream[0].options.headers.Cookie, undefined);
      }
      if (route === '/api/draft') {
        assert.equal(data.leagueId, '456'); // Existing two-league override stays supported.
        assert.equal(data.teams['1'].name, 'Team A');
      } else assert.equal(data.players[0].name, 'Player');
    });
  }
}

test('private upstream errors are not cached and do not disclose secrets', async t => {
  t.mock.method(globalThis, 'fetch', async () => new Response('', {status: 403}));
  const res = await worker.fetch(new Request('https://worker.test/api/draft'), privateEnv);
  assert.equal(res.status, 502);
  assert.equal(res.headers.get('Cache-Control'), 'private, no-store');
  const body = await res.text();
  assert.ok(!body.includes('test-swid') && !body.includes('test-s2'));
});

test('partial credentials fail before fetching and cannot be cached', async t => {
  t.mock.method(globalThis, 'fetch', () => { throw new Error('must not fetch'); });
  const res = await worker.fetch(new Request('https://worker.test/api/draft'), {...baseEnv, ESPN_SWID: 'test-swid'});
  assert.equal(res.status, 500);
  assert.equal(res.headers.get('Cache-Control'), 'private, no-store');
});
