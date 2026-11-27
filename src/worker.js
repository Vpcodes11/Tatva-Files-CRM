// Tatva CRM · Files module · server (Cloudflare Worker + D1)
// Serves the app from /public and a small JSON API under /api.

const ROLES = ['Agent', 'Admin', 'Super admin'];
const SESSION_DAYS = 30;
const MAX_FAILED = 8;          // failed logins before a 15-minute lock
const COLLS = new Set(['visits', 'clients', 'bookings', 'payments', 'plots', 'expenses', 'landowners', 'advances',
  'incentives', 'registry', 'dastavej', 'ledger', 'contractors', 'plotOwners', 'notes']);

// ---------- database tables (created automatically the first time) ----------
const SCHEMA = [
  `CREATE TABLE IF NOT EXISTS records (coll TEXT NOT NULL, id TEXT NOT NULL, sr INTEGER, data TEXT NOT NULL, updated_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')), updated_by TEXT, PRIMARY KEY (coll, id))`,
  `CREATE INDEX IF NOT EXISTS records_coll_sr ON records (coll, sr)`,
  `CREATE TABLE IF NOT EXISTS edits (id INTEGER PRIMARY KEY AUTOINCREMENT, coll TEXT NOT NULL, rec_id TEXT NOT NULL, field TEXT NOT NULL, old TEXT, new TEXT, label TEXT, undone INTEGER NOT NULL DEFAULT 0, undo_of INTEGER, user_id INTEGER, user_name TEXT, role TEXT, at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')))`,
  `CREATE INDEX IF NOT EXISTS edits_rec ON edits (coll, rec_id)`,
  `CREATE TABLE IF NOT EXISTS steps (id INTEGER PRIMARY KEY AUTOINCREMENT, type TEXT NOT NULL, data TEXT NOT NULL, user_id INTEGER, user_name TEXT, role TEXT, at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')))`,
  `CREATE TABLE IF NOT EXISTS users (id INTEGER PRIMARY KEY AUTOINCREMENT, username TEXT NOT NULL UNIQUE COLLATE NOCASE, name TEXT NOT NULL, role TEXT NOT NULL CHECK (role IN ('Agent','Admin','Super admin')), pass_hash TEXT NOT NULL, salt TEXT NOT NULL, active INTEGER NOT NULL DEFAULT 1, failed INTEGER NOT NULL DEFAULT 0, locked_until TEXT, created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')), last_login TEXT)`,
  `CREATE TABLE IF NOT EXISTS sessions (token TEXT PRIMARY KEY, user_id INTEGER NOT NULL, expires_at TEXT NOT NULL)`,
  `CREATE TABLE IF NOT EXISTS meta (key TEXT PRIMARY KEY, value TEXT)`,
  `INSERT OR IGNORE INTO meta (key, value) VALUES ('version', '0')`,
  `CREATE TABLE IF NOT EXISTS trash (id INTEGER PRIMARY KEY AUTOINCREMENT, grp TEXT NOT NULL, coll TEXT NOT NULL, rec_id TEXT NOT NULL, kind TEXT NOT NULL, data TEXT NOT NULL, label TEXT, user_id INTEGER, user_name TEXT, at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')), restored_at TEXT, restored_by TEXT)`,
  `CREATE INDEX IF NOT EXISTS trash_grp ON trash (grp)`
];
let schemaReady = false;
async function ensureSchema(env) {
  if (schemaReady) return;
  await env.DB.batch(SCHEMA.map(s => env.DB.prepare(s)));
  await migrateVisitRemarks(env);
  await migrateBookingAmounts(env);
  await migrateConvertedToBooked(env);
  await migratePayModes(env);
  await migrateMouOpted(env);
  schemaReady = true;
}

// One-time change (Nov 2026): the MOU section starts with "MOU: Opted / Not opted". Bookings whose old MOU column
// (or dastavej status) already mentions the MOU are marked Opted; the rest are left for the admin to choose.
async function migrateMouOpted(env) {
  const done = await env.DB.prepare("SELECT value FROM meta WHERE key = 'migr_mou_opted'").first('value');
  if (done) return;
  const rows = await env.DB.prepare("SELECT id, data FROM records WHERE coll = 'bookings'").all();
  const stmts = [];
  for (const r of rows.results) {
    const b = JSON.parse(r.data);
    if (b.mouOpted || !(/mou/i.test(b.mou || '') || /mou/i.test(b.dastavejStatus || ''))) continue;
    b.mouOpted = 'Opted';
    stmts.push(env.DB.prepare("UPDATE records SET data = ?, updated_by = 'update' WHERE coll = 'bookings' AND id = ?").bind(JSON.stringify(b), b.id));
  }
  for (let i = 0; i < stmts.length; i += 100) await env.DB.batch(stmts.slice(i, i + 100));
  await env.DB.batch([
    env.DB.prepare("INSERT OR REPLACE INTO meta (key, value) VALUES ('migr_mou_opted', ?)").bind(String(stmts.length)),
    env.DB.prepare("UPDATE meta SET value = CAST(value AS INTEGER) + 1 WHERE key = 'version'")
  ]);
}

// One-time change (Nov 2026): payment modes "Online" and "UPI" are merged into "UPI / Online", and the booking's
// cheque details (chequeName / chequeNumber / chequeBank) become the general proof fields payName / payRef / payBank.
async function migratePayModes(env) {
  const done = await env.DB.prepare("SELECT value FROM meta WHERE key = 'migr_pay_modes'").first('value');
  if (done) return;
  const merge = v => typeof v === 'string' && /^\s*(online|upi)\s*$/i.test(v) ? 'UPI / Online' : v;
  const stmts = [];
  for (const [coll, fields] of [['payments', ['mode']], ['bookings', ['holdMode', 'bookingMode', 'dpMode', 'refundMode']]]) {
    const rows = (await env.DB.prepare('SELECT id, data FROM records WHERE coll = ?').bind(coll).all()).results;
    for (const r of rows) {
      const d = JSON.parse(r.data); let changed = false;
      for (const f of fields) { const v = merge(d[f]); if (v !== d[f]) { d[f] = v; changed = true; } }
      if (coll === 'bookings') for (const [from, to] of [['chequeName', 'payName'], ['chequeNumber', 'payRef'], ['chequeBank', 'payBank']])
        if (from in d) { if (d[from] && !d[to]) d[to] = d[from]; delete d[from]; changed = true; }
      if (changed) stmts.push(env.DB.prepare("UPDATE records SET data = ?, updated_by = 'update' WHERE coll = ? AND id = ?").bind(JSON.stringify(d), coll, r.id));
    }
  }
  for (let i = 0; i < stmts.length; i += 100) await env.DB.batch(stmts.slice(i, i + 100));
  await env.DB.batch([
    env.DB.prepare("INSERT OR REPLACE INTO meta (key, value) VALUES ('migr_pay_modes', ?)").bind(String(stmts.length)),
    env.DB.prepare("UPDATE meta SET value = CAST(value AS INTEGER) + 1 WHERE key = 'version'")
  ]);
}

// One-time change (Nov 2026): the word "Converted" is now "Booked" everywhere. Saved booking statuses
// (Converted → Booked), visit statuses (Converted / DONE → Booked) and the same values in the edit history
// (so Undo puts back "Booked") are renamed.
async function migrateConvertedToBooked(env) {
  const done = await env.DB.prepare("SELECT value FROM meta WHERE key = 'migr_converted_booked'").first('value');
  if (done) return;
  const stmts = [];
  for (const [coll, field, test] of [['bookings', 'outcome', v => /convert/i.test(v)], ['visits', 'status', v => /convert/i.test(v) || /^done$/i.test(v)]]) {
    const rows = (await env.DB.prepare('SELECT id, data FROM records WHERE coll = ?').bind(coll).all()).results;
    for (const r of rows) {
      const d = JSON.parse(r.data);
      if (!test(String(d[field] || ''))) continue;
      d[field] = 'Booked';
      stmts.push(env.DB.prepare("UPDATE records SET data = ?, updated_by = 'update' WHERE coll = ? AND id = ?").bind(JSON.stringify(d), coll, r.id));
    }
  }
  const n = stmts.length;
  stmts.push(env.DB.prepare(`UPDATE edits SET old = '"Booked"' WHERE coll IN ('bookings', 'visits') AND field IN ('outcome', 'status') AND (old LIKE '%onverted%' OR old = '"DONE"')`));
  stmts.push(env.DB.prepare(`UPDATE edits SET new = '"Booked"' WHERE coll IN ('bookings', 'visits') AND field IN ('outcome', 'status') AND (new LIKE '%onverted%' OR new = '"DONE"')`));
  for (let i = 0; i < stmts.length; i += 100) await env.DB.batch(stmts.slice(i, i + 100));
  await env.DB.batch([
    env.DB.prepare("INSERT OR REPLACE INTO meta (key, value) VALUES ('migr_converted_booked', ?)").bind(String(n)),
    env.DB.prepare("UPDATE meta SET value = CAST(value AS INTEGER) + 1 WHERE key = 'version'")
  ]);
}

// One-time change (Nov 2026): the client folder now has separate Booking date / amount / mode. Bookings made in
// the CRM before this saved the booking amount in the down payment fields (dpAmount/dpDate/dpMode). Move it, but
// only where the matching "Booking amount · plot" payment exists, so a down payment typed by hand stays a DP.
async function migrateBookingAmounts(env) {
  const done = await env.DB.prepare("SELECT value FROM meta WHERE key = 'migr_booking_amount'").first('value');
  if (done) return;
  const all = coll => env.DB.prepare('SELECT id, data FROM records WHERE coll = ?').bind(coll).all().then(r => r.results.map(x => JSON.parse(x.data)));
  const [bookings, payments] = [await all('bookings'), await all('payments')];
  const stmts = [];
  for (const b of bookings) {
    if (!b.added || !b.dpAmount || b.bookingAmount != null || !isConvertedOutcome(b.outcome)) continue;
    const paid = payments.some(p => /^booking amount/i.test(p.text || '') && p.amount === b.dpAmount && (p.plots || []).includes(b.plot) && (p.clients || []).includes(b.cid));
    if (!paid) continue;
    Object.assign(b, {bookingAmount: b.dpAmount, bookingDate: b.dpDate ?? null, bookingMode: b.dpMode ?? null, dpAmount: null, dpDate: null, dpMode: null});
    stmts.push(env.DB.prepare("UPDATE records SET data = ?, updated_by = 'update' WHERE coll = 'bookings' AND id = ?").bind(JSON.stringify(b), b.id));
  }
  for (let i = 0; i < stmts.length; i += 100) await env.DB.batch(stmts.slice(i, i + 100));
  await env.DB.batch([
    env.DB.prepare("INSERT OR REPLACE INTO meta (key, value) VALUES ('migr_booking_amount', ?)").bind(String(stmts.length)),
    env.DB.prepare("UPDATE meta SET value = CAST(value AS INTEGER) + 1 WHERE key = 'version'")
  ]);
}

// One-time change (Nov 2026): site visits keep a single Remark. The old Note, follow-up dates/notes
// and follow-up remark are folded into it so nothing is lost.
async function migrateVisitRemarks(env) {
  const done = await env.DB.prepare("SELECT value FROM meta WHERE key = 'migr_visit_remarks'").first('value');
  if (done) return;
  const rows = (await env.DB.prepare("SELECT id, data FROM records WHERE coll = 'visits'").all()).results;
  const stmts = [];
  const fd = d => { const m = /^(\d{4})-(\d\d)-(\d\d)/.exec(d || ''); return m ? `${m[3]}/${m[2]}/${m[1].slice(2)}` : (d || ''); };
  for (const r of rows) {
    const v = JSON.parse(r.data);
    const old = ['extra', 'fuRemark', 'paymentNote', 'followups', 'fu1Date', 'fu1Note', 'fu2Date', 'fu2Note', 'fu3Date', 'fu3Note', 'fu4Date', 'fu4Note'];
    if (!old.some(k => k in v)) continue;
    const parts = [v.remark, v.extra];
    for (let i = 1; i <= 4; i++) {
      const d = v['fu' + i + 'Date'], n = v['fu' + i + 'Note'];
      if (d || n) parts.push(`FU${i}${d ? ' ' + fd(d) : ''}: ${n || '—'}`);
    }
    parts.push(v.fuRemark, v.paymentNote);
    const seen = new Set();
    const remark = parts.map(x => (x == null ? '' : String(x).trim())).filter(x => x && !seen.has(x) && seen.add(x)).join(' · ') || null;
    old.forEach(k => delete v[k]);
    v.remark = remark;
    stmts.push(env.DB.prepare("UPDATE records SET data = ?, updated_by = 'update' WHERE coll = 'visits' AND id = ?").bind(JSON.stringify(v), r.id));
  }
  for (let i = 0; i < stmts.length; i += 100) await env.DB.batch(stmts.slice(i, i + 100));
  await env.DB.batch([
    env.DB.prepare("INSERT OR REPLACE INTO meta (key, value) VALUES ('migr_visit_remarks', ?)").bind(String(stmts.length)),
    env.DB.prepare("UPDATE meta SET value = CAST(value AS INTEGER) + 1 WHERE key = 'version'")
  ]);
}

// ---------- helpers ----------
const json = (data, status = 200, headers = {}) =>
  new Response(JSON.stringify(data), {status, headers: {'content-type': 'application/json; charset=utf-8', 'cache-control': 'no-store', ...headers}});
const fail = (status, error) => json({error}, status);
const now = () => new Date().toISOString();
const hex = buf => [...new Uint8Array(buf)].map(b => b.toString(16).padStart(2, '0')).join('');
const randomHex = n => hex(crypto.getRandomValues(new Uint8Array(n)));

async function hashPassword(password, saltHex) {
  const key = await crypto.subtle.importKey('raw', new TextEncoder().encode(password), 'PBKDF2', false, ['deriveBits']);
  const salt = new Uint8Array(saltHex.match(/../g).map(h => parseInt(h, 16)));
  const bits = await crypto.subtle.deriveBits({name: 'PBKDF2', hash: 'SHA-256', salt, iterations: 100000}, key, 256);
  return hex(bits);
}
function safeEqual(a, b) {
  if (a.length !== b.length) return false;
  let r = 0; for (let i = 0; i < a.length; i++) r |= a.charCodeAt(i) ^ b.charCodeAt(i);
  return r === 0;
}
const cookieOf = (req, name) => {
  const m = (req.headers.get('cookie') || '').match(new RegExp('(?:^|;\\s*)' + name + '=([^;]+)'));
  return m ? m[1] : null;
};
const sessionCookie = (token, maxAge) =>
  `sid=${token}; Path=/; HttpOnly; Secure; SameSite=Lax; Max-Age=${maxAge}`;
const publicUser = u => u && ({id: u.id, username: u.username, name: u.name, role: u.role, active: !!u.active, last_login: u.last_login, created_at: u.created_at});

function validPassword(p) { return typeof p === 'string' && p.length >= 6 && p.length <= 200; }
function validUsername(u) { return typeof u === 'string' && /^[a-zA-Z0-9._-]{3,40}$/.test(u); }

async function currentUser(env, req) {
  const token = cookieOf(req, 'sid');
  if (!token) return null;
  const row = await env.DB.prepare(
    `SELECT u.* FROM sessions s JOIN users u ON u.id = s.user_id WHERE s.token = ? AND s.expires_at > ? AND u.active = 1`
  ).bind(token, now()).first();
  return row || null;
}

// The same lock rules the screen shows: an Agent cannot change a Booked visit or booking.
// ("Converted" was renamed "Booked" in Nov 2026; both words are understood.)
const isConvertedVisitStatus = s => { const x = String(s || '').toUpperCase(); return !x.includes('NOT') && !x.includes('FOLLOW') && (x === 'DONE' || x === 'BOOKED' || x.includes('CONVERT')); };
const isConvertedOutcome = s => /convert|^booked$/i.test(String(s || ''));
// Same rule as clientStatus() in index.html: Lapsed = has bookings, none Booked and none on hold.
async function clientIsLapsed(client, getRec) {
  const ids = Array.isArray(client.bookings) ? client.bookings : [];
  if (!ids.length) return false;
  for (const id of ids) {
    const o = String(((await getRec('bookings', id)) || {}).outcome || '').toLowerCase();
    if (o.startsWith('convert') || o === 'booked' || o.includes('hold')) return false;
  }
  return true;
}
// A plot can be lapsed at any stage (hold, DP, booked) until the MOU or the dastavej is done — same rule as
// docLock() in index.html. Returns the reason it is refused, or null.
async function lapseRefusal(env, cur, next, getRec) {
  const active = o => /convert|^booked$|hold/i.test(String(o || ''));
  if (!cur || !next || !active(cur.outcome) || !/laps/i.test(String(next.outcome || ''))) return null;
  let client = cur.cid ? await getRec('clients', cur.cid) : null;
  if (!client) { const r = await env.DB.prepare("SELECT data FROM records WHERE coll = 'clients' AND data LIKE ?").bind('%"' + cur.id + '"%').first(); client = r ? JSON.parse(r.data) : null; }
  const ds = String((client && client.docStatus) || ''), dv = cur.plot ? await getRec('dastavej', String(cur.plot)) : null;
  // a dastavej record added in the CRM only counts once its date is filled in
  if ((dv && (!dv.added || dv.date)) || /dastavej done/i.test(ds) || /done & sent/i.test(cur.dastavejStatus || '')) return 'This plot cannot be lapsed: the dastavej is done.';
  if (/^(mou done|dastavej)/i.test(ds) || /mou done/i.test(cur.mou || '') || (cur.mouOpted === 'Opted' && (cur.mouDate || cur.mouNo)) || /done|office/i.test(cur.dastavejStatus || '')) return 'This plot cannot be lapsed: the MOU is done.';
  return null;
}
// What an Agent may save: site visits (add, edit, follow-ups) and a new hold taken from a site visit (a new client
// folder, its hold booking and hold payment, and the plot going from available to Hold). Nothing else: client folders,
// plots and the office modules are view-only for agents.
const AGENT_NO = 'Agents can add and edit site visits and take a hold from a site visit. Everything else is done by an Admin.';
async function agentRefusal(ops, getRec) {
  for (const op of ops) {
    if (op.op === 'step') { if (!['visit', 'hold'].includes(op.type)) return AGENT_NO; continue; }
    if (op.op === 'del') return 'Only a Super admin can delete.';
    if (op.coll === 'visits') continue;
    if (op.op !== 'put') return AGENT_NO;
    const cur = await getRec(op.coll, op.id), d = op.data || {};
    if (['clients', 'payments'].includes(op.coll) && !cur) continue;
    if (op.coll === 'bookings' && !cur && /hold/i.test(d.outcome || '')) continue;
    if (op.coll === 'plots' && cur) {
      // only the status may change (id / sr are bookkeeping and may or may not be stored on the plot)
      const same = [...new Set([...Object.keys(cur), ...Object.keys(d)])].filter(k => !['status', 'id', 'sr'].includes(k)).every(k => JSON.stringify(cur[k] ?? null) === JSON.stringify(d[k] ?? null));
      if (same && /^hold$/i.test(d.status || '') && !/^\s*(sold|hold)/i.test(cur.status || '')) continue; // from available (UNSOLD …), never from Sold / Hold
    }
    return AGENT_NO;
  }
  return null;
}
function lockError(user, coll, current, next) {
  if (user.role !== 'Agent') return null;
  if (coll === 'visits' && current && isConvertedVisitStatus(current.status) && next && !isConvertedVisitStatus(next.status))
    return 'This visit is Booked. Only Admin or Super admin can change it.';
  if (coll === 'bookings' && current && isConvertedOutcome(current.outcome) && next && !isConvertedOutcome(next.outcome))
    return 'This plot is Booked. Only Admin or Super admin can change the booking status.';
  return null;
}

// ---------- API handlers ----------
async function apiMe(env, req) {
  const user = await currentUser(env, req);
  if (user) return json({user: publicUser(user)});
  const count = await env.DB.prepare('SELECT COUNT(*) AS n FROM users').first('n');
  return json({user: null, setup: count === 0});
}

async function apiSetup(env, req) {
  const count = await env.DB.prepare('SELECT COUNT(*) AS n FROM users').first('n');
  if (count > 0) return fail(403, 'Setup is already done. Please sign in.');
  const b = await req.json().catch(() => ({}));
  const name = String(b.name || '').trim();
  if (!name) return fail(400, 'Enter your name.');
  if (!validUsername(b.username)) return fail(400, 'Username: 3–40 letters or numbers (dot, dash and underscore are fine).');
  if (!validPassword(b.password)) return fail(400, 'Password must have at least 6 characters.');
  const salt = randomHex(16);
  await env.DB.prepare('INSERT INTO users (username, name, role, pass_hash, salt) VALUES (?, ?, ?, ?, ?)')
    .bind(b.username, name, 'Super admin', await hashPassword(b.password, salt), salt).run();
  return login(env, b.username, b.password);
}

async function login(env, username, password) {
  const u = await env.DB.prepare('SELECT * FROM users WHERE username = ?').bind(String(username || '')).first();
  const bad = () => fail(401, 'Wrong username or password.');
  if (!u) { await hashPassword(String(password || 'x'), randomHex(16)); return bad(); }
  if (!u.active) return fail(403, 'This user has been switched off. Ask an admin.');
  if (u.locked_until && u.locked_until > now()) return fail(429, 'Too many wrong passwords. Try again in 15 minutes.');
  const h = await hashPassword(String(password || ''), u.salt);
  if (!safeEqual(h, u.pass_hash)) {
    const failed = u.failed + 1;
    const lock = failed >= MAX_FAILED ? new Date(Date.now() + 15 * 60e3).toISOString() : null;
    await env.DB.prepare('UPDATE users SET failed = ?, locked_until = ? WHERE id = ?').bind(lock ? 0 : failed, lock, u.id).run();
    return bad();
  }
  const token = randomHex(32);
  const exp = new Date(Date.now() + SESSION_DAYS * 864e5).toISOString();
  await env.DB.batch([
    env.DB.prepare('INSERT INTO sessions (token, user_id, expires_at) VALUES (?, ?, ?)').bind(token, u.id, exp),
    env.DB.prepare('UPDATE users SET failed = 0, locked_until = NULL, last_login = ? WHERE id = ?').bind(now(), u.id),
    env.DB.prepare('DELETE FROM sessions WHERE expires_at < ?').bind(now())
  ]);
  return json({user: publicUser({...u, last_login: now()})}, 200, {'set-cookie': sessionCookie(token, SESSION_DAYS * 86400)});
}

async function apiLogin(env, req) {
  const b = await req.json().catch(() => ({}));
  return login(env, b.username, b.password);
}

async function apiLogout(env, req) {
  const token = cookieOf(req, 'sid');
  if (token) await env.DB.prepare('DELETE FROM sessions WHERE token = ?').bind(token).run();
  return json({ok: true}, 200, {'set-cookie': sessionCookie('', 0)});
}

// Agents (owner's rule, Nov 2026): they see Site visits, Clients and Plots, and only their own incentives. The office
// modules (sold plot register, land partner, contractors, site expenses), the edit history and other agents'
// incentives are not sent to them at all.
const agentNames = by => String(by || '').split(/,|&|\//).map(s => s.trim().toLowerCase()).filter(Boolean);
const isOwnAgent = (user, by) => { const me = String(user.name || '').trim().toLowerCase(), first = me.split(/\s+/)[0];
  return !!me && agentNames(by).some(a => a === me || a.split(/\s+/)[0] === first); };
function agentView(D, user) {
  for (const k of ['expenses', 'landowners', 'advances', 'contractors']) D[k] = [];
  D.incentives = D.incentives.filter(x => isOwnAgent(user, x.by));
  D.bookings.forEach(b => { if (!isOwnAgent(user, b.by)) for (const f of ['incentiveStatus', 'incentiveReleased', 'incentivePending']) delete b[f]; });
}
async function apiData(env, user) {
  const [recs, edits, steps, version] = await env.DB.batch([
    env.DB.prepare('SELECT coll, id, sr, data FROM records'),
    env.DB.prepare('SELECT id, coll, rec_id, field, old, new, label, undone, undo_of, user_name, role, at FROM edits ORDER BY id'),
    env.DB.prepare('SELECT id, type, data, user_name, role, at FROM steps ORDER BY id'),
    env.DB.prepare("SELECT value FROM meta WHERE key = 'version'")
  ]);
  const D = {visits: [], clients: [], bookings: [], payments: [], expenses: [], landowners: [], advances: [], incentives: [],
    contractors: [], notes: [], plots: {}, registry: {}, dastavej: {}, plotOwners: {}, summary: {}};
  const ledger = [];
  for (const r of recs.results) {
    const o = JSON.parse(r.data);
    if (r.coll === 'plotOwners') { D.plotOwners[r.id] = o; continue; }
    if (r.coll === 'meta') { D[r.id] = o; continue; }
    if (r.coll === 'ledger') { ledger.push(o); continue; }
    if (D[r.coll] && Array.isArray(D[r.coll])) D[r.coll].push(o);
    else if (D[r.coll]) D[r.coll][r.id] = o;
  }
  const byRow = (a, b) => (a.row || 0) - (b.row || 0) || (a.sr || 0) - (b.sr || 0);
  ['visits', 'bookings', 'payments', 'expenses', 'landowners', 'advances', 'incentives', 'notes'].forEach(k => D[k].sort(byRow));
  D.clients.sort((a, b) => (a.sr || 0) - (b.sr || 0));
  D.contractors.forEach(c => { c.ledger = ledger.filter(l => l.contractor === c.name).sort(byRow); });
  const agent = user && user.role === 'Agent';
  if (agent) agentView(D, user);
  return json({
    empty: recs.results.length === 0,
    data: D,
    edits: agent ? [] : edits.results.map(e => ({...e, old: JSON.parse(e.old), new: JSON.parse(e.new), undone: !!e.undone})),
    steps: agent ? [] : steps.results.map(s => ({...s, data: JSON.parse(s.data)})),
    version: Number(version.results[0] ? version.results[0].value : 0)
  });
}

async function apiVersion(env) {
  const v = await env.DB.prepare("SELECT value FROM meta WHERE key = 'version'").first('value');
  return json({version: Number(v || 0)});
}

// Apply a list of changes in one go (all or nothing).
// patch: {op:'patch', coll, id, field, value, label, undoOf?}
// put:   {op:'put', coll, id, data, newSr?}   (create or replace a whole record)
// step:  {op:'step', type, data}               (a hold / booking / payment / lapse / new visit, for the history list)
async function apiOps(env, req, user) {
  const b = await req.json().catch(() => null);
  const ops = b && Array.isArray(b.ops) ? b.ops : null;
  if (!ops || !ops.length || ops.length > 400) return fail(400, 'Nothing to save.');
  const stmts = [];
  const assigned = {};
  const maxSr = {};
  const getRec = async (coll, id) => {
    const r = await env.DB.prepare('SELECT data FROM records WHERE coll = ? AND id = ?').bind(coll, id).first();
    return r ? JSON.parse(r.data) : null;
  };
  const working = {}; // records changed earlier in this same request
  if (user.role === 'Agent') { const no = await agentRefusal(ops, getRec); if (no) return fail(403, no); }
  for (const op of ops) {
    if (op.op === 'patch' || op.op === 'put' || op.op === 'del') {
      if (!COLLS.has(op.coll) || typeof op.id !== 'string' || !op.id || op.id.length > 100) return fail(400, 'Unknown record.');
    }
    if (op.op === 'patch') {
      if (typeof op.field !== 'string' || !/^[A-Za-z0-9_]{1,40}$/.test(op.field) || ['id', 'sr'].includes(op.field)) return fail(400, 'This field cannot be changed.');
      const key = op.coll + '|' + op.id;
      const cur = working[key] || await getRec(op.coll, op.id);
      if (!cur) return fail(404, 'This record no longer exists. Refresh the page.');
      const next = {...cur, [op.field]: op.value === undefined ? null : op.value};
      let lapsedVisit = false; // a lapsed client's visit shows as Lapsed, whatever the old sheet status (e.g. DONE) says
      if (op.coll === 'visits' && op.field === 'status' && cur.client) {
        // A visit in a client folder follows the folder. Only a lapsed client's visit can be moved
        // back to Follow up (or to Lapsed again); `reopened` records that choice.
        const client = await getRec('clients', cur.client);
        if (client) {
          if (!(await clientIsLapsed(client, getRec)))
            return fail(403, 'This visit is linked to a client folder, so its status follows the folder. Change it from the client folder.');
          if (!/^(follow up [1-4]|lapsed)$/i.test(String(op.value || '')))
            return fail(403, 'This client\'s hold lapsed. Their visit can only be set to a Follow up or Lapsed.');
          next.reopened = /^follow/i.test(op.value);
          lapsedVisit = true;
        }
      }
      const lock = lapsedVisit ? null : lockError(user, op.coll, cur, next);
      if (lock) return fail(403, lock);
      if (op.coll === 'bookings') { const no = await lapseRefusal(env, cur, next, getRec); if (no) return fail(403, no); }
      working[key] = next;
      stmts.push(env.DB.prepare('UPDATE records SET data = ?, updated_at = ?, updated_by = ? WHERE coll = ? AND id = ?')
        .bind(JSON.stringify(next), now(), user.name, op.coll, op.id));
      if (!op.silent) stmts.push(env.DB.prepare('INSERT INTO edits (coll, rec_id, field, old, new, label, undo_of, user_id, user_name, role) VALUES (?,?,?,?,?,?,?,?,?,?)')
        .bind(op.coll, op.id, op.field, JSON.stringify(cur[op.field] ?? null), JSON.stringify(next[op.field]), String(op.label || '').slice(0, 300), op.undoOf || null, user.id, user.name, user.role));
      if (op.undoOf) stmts.push(env.DB.prepare('UPDATE edits SET undone = 1 WHERE id = ?').bind(op.undoOf));
    } else if (op.op === 'put') {
      const data = op.data;
      if (op.coll === 'plotOwners' ? typeof data !== 'string' : (!data || typeof data !== 'object' || Array.isArray(data))) return fail(400, 'Bad record.');
      const key = op.coll + '|' + op.id;
      const cur = working[key] || await getRec(op.coll, op.id);
      const lock = lockError(user, op.coll, cur, data);
      if (lock) return fail(403, lock);
      if (op.coll === 'bookings') { const no = await lapseRefusal(env, cur, data, getRec); if (no) return fail(403, no); }
      if (op.grp && cur != null) {
        if (user.role !== 'Super admin') return fail(403, 'Only a Super admin can delete.');
        stmts.push(env.DB.prepare('INSERT INTO trash (grp, coll, rec_id, kind, data, label, user_id, user_name) VALUES (?,?,?,?,?,?,?,?)')
          .bind(op.grp, op.coll, op.id, 'before', JSON.stringify(cur), String(op.label || '').slice(0, 300), user.id, user.name));
      }
      if (op.coll === 'plotOwners') {
        stmts.push(env.DB.prepare(`INSERT INTO records (coll, id, sr, data, updated_at, updated_by) VALUES (?,?,NULL,?,?,?)
          ON CONFLICT (coll, id) DO UPDATE SET data = excluded.data, updated_at = excluded.updated_at, updated_by = excluded.updated_by`)
          .bind(op.coll, op.id, JSON.stringify(data), now(), user.name));
        continue;
      }
      let sr = data.sr ?? null;
      if (op.newSr && !cur) {
        if (maxSr[op.coll] === undefined) maxSr[op.coll] = Number(await env.DB.prepare('SELECT COALESCE(MAX(sr), 0) AS m FROM records WHERE coll = ?').bind(op.coll).first('m'));
        sr = ++maxSr[op.coll];
        data.sr = sr; assigned[key] = sr;
      } else if (cur && cur.sr != null) { sr = cur.sr; data.sr = cur.sr; }
      if (op.coll !== 'plotOwners') data.id = op.id;
      working[key] = data;
      stmts.push(env.DB.prepare(`INSERT INTO records (coll, id, sr, data, updated_at, updated_by) VALUES (?,?,?,?,?,?)
        ON CONFLICT (coll, id) DO UPDATE SET sr = excluded.sr, data = excluded.data, updated_at = excluded.updated_at, updated_by = excluded.updated_by`)
        .bind(op.coll, op.id, sr, JSON.stringify(data), now(), user.name));
    } else if (op.op === 'del') {
      if (user.role !== 'Super admin') return fail(403, 'Only a Super admin can delete.');
      if (!COLLS.has(op.coll) || op.coll === 'plots' || typeof op.id !== 'string' || !op.id) return fail(400, 'This cannot be deleted.');
      if (typeof op.grp !== 'string' || !/^[A-Za-z0-9_-]{6,40}$/.test(op.grp)) return fail(400, 'Missing delete group.');
      const key = op.coll + '|' + op.id;
      const cur = working[key] !== undefined ? working[key] : await getRec(op.coll, op.id);
      if (cur == null) return fail(404, 'This record no longer exists. Refresh the page.');
      working[key] = null;
      stmts.push(env.DB.prepare('INSERT INTO trash (grp, coll, rec_id, kind, data, label, user_id, user_name) VALUES (?,?,?,?,?,?,?,?)')
        .bind(op.grp, op.coll, op.id, 'deleted', JSON.stringify(cur), String(op.label || '').slice(0, 300), user.id, user.name));
      stmts.push(env.DB.prepare('DELETE FROM records WHERE coll = ? AND id = ?').bind(op.coll, op.id));
    } else if (op.op === 'step') {
      if (!['hold', 'book', 'pay', 'lapse', 'visit', 'expense', 'delete', 'add'].includes(op.type)) return fail(400, 'Unknown step.');
      stmts.push(env.DB.prepare('INSERT INTO steps (type, data, user_id, user_name, role) VALUES (?,?,?,?,?)')
        .bind(op.type, JSON.stringify(op.data || {}), user.id, user.name, user.role));
    } else return fail(400, 'Unknown change.');
  }
  stmts.push(env.DB.prepare("UPDATE meta SET value = CAST(value AS INTEGER) + 1 WHERE key = 'version'"));
  await env.DB.batch(stmts);
  const version = await env.DB.prepare("SELECT value FROM meta WHERE key = 'version'").first('value');
  const edits = await env.DB.prepare('SELECT id, coll, rec_id, field, old, new, label, undone, undo_of, user_name, role, at FROM edits WHERE user_id = ? ORDER BY id DESC LIMIT ?')
    .bind(user.id, ops.filter(o => o.op === 'patch' && !o.silent).length || 0).all();
  return json({ok: true, sr: assigned, version: Number(version),
    edits: edits.results.reverse().map(e => ({...e, old: JSON.parse(e.old), new: JSON.parse(e.new), undone: !!e.undone}))});
}

// ---------- one-time import of the sheet data (Super admin, empty database only) ----------
async function apiImport(env, req, user) {
  if (user.role !== 'Super admin') return fail(403, 'Only a Super admin can load the sheet data.');
  const n = await env.DB.prepare('SELECT COUNT(*) AS n FROM records').first('n');
  if (n > 0) return fail(409, 'The data is already loaded.');
  const b = await req.json().catch(() => null);
  const recs = b && Array.isArray(b.records) ? b.records : null;
  if (!recs || !recs.length) return fail(400, 'This file has no records.');
  for (const r of recs) if (!r || typeof r.coll !== 'string' || typeof r.id !== 'string' || r.data === undefined) return fail(400, 'This is not the Tatva data file.');
  const stmts = [];
  for (let i = 0; i < recs.length; i += 20) {
    const chunk = recs.slice(i, i + 20);
    stmts.push(env.DB.prepare('INSERT INTO records (coll, id, sr, data, updated_by) VALUES ' + chunk.map(() => "(?,?,?,?,'import')").join(','))
      .bind(...chunk.flatMap(r => [r.coll, r.id, r.sr ?? null, JSON.stringify(r.data)])));
  }
  for (let i = 0; i < stmts.length; i += 40) await env.DB.batch(stmts.slice(i, i + 40));
  await env.DB.prepare("UPDATE meta SET value = CAST(value AS INTEGER) + 1 WHERE key = 'version'").run();
  return json({ok: true, records: recs.length});
}

// ---------- deleted items (Super admin) ----------
async function apiTrash(env, user) {
  if (user.role !== 'Super admin') return fail(403, 'Only a Super admin can see deleted items.');
  const r = await env.DB.prepare(`SELECT grp, MIN(at) AS at, MAX(user_name) AS user_name, MAX(restored_at) AS restored_at, MAX(restored_by) AS restored_by,
      SUM(kind = 'deleted') AS deleted, SUM(kind = 'before') AS changed,
      (SELECT label FROM trash t2 WHERE t2.grp = trash.grp ORDER BY t2.id LIMIT 1) AS label,
      GROUP_CONCAT(CASE WHEN kind = 'deleted' THEN coll END) AS colls
    FROM trash GROUP BY grp ORDER BY MIN(id) DESC LIMIT 500`).all();
  return json({groups: r.results});
}
async function apiRestore(env, req, user) {
  if (user.role !== 'Super admin') return fail(403, 'Only a Super admin can restore.');
  const b = await req.json().catch(() => ({}));
  const rows = (await env.DB.prepare('SELECT * FROM trash WHERE grp = ? ORDER BY id').bind(String(b.grp || '')).all()).results;
  if (!rows.length) return fail(404, 'Nothing to restore.');
  if (rows.some(r => r.restored_at)) return fail(409, 'This was already restored.');
  const stmts = rows.map(r => {
    const data = JSON.parse(r.data);
    return env.DB.prepare(`INSERT INTO records (coll, id, sr, data, updated_at, updated_by) VALUES (?,?,?,?,?,?)
      ON CONFLICT (coll, id) DO UPDATE SET sr = excluded.sr, data = excluded.data, updated_at = excluded.updated_at, updated_by = excluded.updated_by`)
      .bind(r.coll, r.rec_id, data && typeof data === 'object' ? (data.sr ?? null) : null, r.data, now(), user.name);
  });
  stmts.push(env.DB.prepare('UPDATE trash SET restored_at = ?, restored_by = ? WHERE grp = ?').bind(now(), user.name, rows[0].grp));
  stmts.push(env.DB.prepare('INSERT INTO steps (type, data, user_id, user_name, role) VALUES (?,?,?,?,?)')
    .bind('restore', JSON.stringify({grp: rows[0].grp, label: rows[0].label}), user.id, user.name, user.role));
  stmts.push(env.DB.prepare("UPDATE meta SET value = CAST(value AS INTEGER) + 1 WHERE key = 'version'"));
  await env.DB.batch(stmts);
  return json({ok: true, restored: rows.filter(r => r.kind === 'deleted').length});
}

// ---------- users ----------
const canManageUsers = u => u.role === 'Admin' || u.role === 'Super admin';

async function apiUsers(env, req, user) {
  if (!canManageUsers(user)) return fail(403, 'Only Admin or Super admin can manage users.');
  if (req.method === 'GET') {
    const r = await env.DB.prepare('SELECT * FROM users ORDER BY active DESC, name').all();
    return json({users: r.results.map(publicUser)});
  }
  if (req.method === 'POST') {
    const b = await req.json().catch(() => ({}));
    const name = String(b.name || '').trim();
    if (!name) return fail(400, 'Enter the name.');
    if (!validUsername(b.username)) return fail(400, 'Username: 3–40 letters or numbers (dot, dash and underscore are fine).');
    if (!ROLES.includes(b.role)) return fail(400, 'Choose a role.');
    if (b.role !== 'Agent' && user.role !== 'Super admin') return fail(403, 'An Admin can add Agents only. Ask a Super admin to add an Admin or Super admin.');
    if (!validPassword(b.password)) return fail(400, 'Password must have at least 6 characters.');
    const exists = await env.DB.prepare('SELECT id FROM users WHERE username = ?').bind(b.username).first();
    if (exists) return fail(409, 'This username is already taken.');
    const salt = randomHex(16);
    await env.DB.prepare('INSERT INTO users (username, name, role, pass_hash, salt) VALUES (?,?,?,?,?)')
      .bind(b.username, name, b.role, await hashPassword(b.password, salt), salt).run();
    return json({ok: true});
  }
  return fail(405, 'Not allowed.');
}

async function apiUserUpdate(env, req, user, id) {
  if (!canManageUsers(user)) return fail(403, 'Only Admin or Super admin can manage users.');
  const target = await env.DB.prepare('SELECT * FROM users WHERE id = ?').bind(id).first();
  if (!target) return fail(404, 'User not found.');
  if (target.role !== 'Agent' && user.role !== 'Super admin' && target.id !== user.id) return fail(403, 'An Admin can change Agents only. Ask a Super admin.');
  const b = await req.json().catch(() => ({}));
  const sets = [], vals = [];
  if (b.name !== undefined) { const n = String(b.name).trim(); if (!n) return fail(400, 'Enter the name.'); sets.push('name = ?'); vals.push(n); }
  if (b.role !== undefined) {
    if (!ROLES.includes(b.role)) return fail(400, 'Choose a role.');
    if (b.role !== target.role && b.role !== 'Agent' && user.role !== 'Super admin') return fail(403, 'Only a Super admin can make someone Admin or Super admin.');
    if (target.id === user.id && b.role !== user.role) return fail(400, 'You cannot change your own role.');
    sets.push('role = ?'); vals.push(b.role);
  }
  if (b.active !== undefined) {
    if (target.id === user.id && !b.active) return fail(400, 'You cannot switch off your own user.');
    sets.push('active = ?'); vals.push(b.active ? 1 : 0);
  }
  if (b.password) {
    if (!validPassword(b.password)) return fail(400, 'Password must have at least 6 characters.');
    const salt = randomHex(16);
    sets.push('pass_hash = ?', 'salt = ?', 'failed = 0', 'locked_until = NULL'); vals.push(await hashPassword(b.password, salt), salt);
  }
  if (!sets.length) return json({ok: true});
  const stmts = [env.DB.prepare(`UPDATE users SET ${sets.join(', ')} WHERE id = ?`).bind(...vals, id)];
  if (b.active === false || b.password) stmts.push(env.DB.prepare('DELETE FROM sessions WHERE user_id = ?').bind(id));
  if (target.role === 'Super admin' && (b.active === false || (b.role && b.role !== 'Super admin'))) {
    const others = await env.DB.prepare("SELECT COUNT(*) AS n FROM users WHERE role = 'Super admin' AND active = 1 AND id != ?").bind(id).first('n');
    if (!others) return fail(400, 'There must always be at least one active Super admin.');
  }
  await env.DB.batch(stmts);
  return json({ok: true});
}

async function apiPassword(env, req, user) {
  const b = await req.json().catch(() => ({}));
  const h = await hashPassword(String(b.current || ''), user.salt);
  if (!safeEqual(h, user.pass_hash)) return fail(400, 'Your current password is wrong.');
  if (!validPassword(b.password)) return fail(400, 'New password must have at least 6 characters.');
  const salt = randomHex(16);
  const token = cookieOf(req, 'sid');
  await env.DB.batch([
    env.DB.prepare('UPDATE users SET pass_hash = ?, salt = ? WHERE id = ?').bind(await hashPassword(b.password, salt), salt, user.id),
    env.DB.prepare('DELETE FROM sessions WHERE user_id = ? AND token != ?').bind(user.id, token)
  ]);
  return json({ok: true});
}

// ---------- router ----------
export default {
  async fetch(req, env) {
    const url = new URL(req.url);
    const path = url.pathname;
    if (!path.startsWith('/api/')) return env.ASSETS.fetch(req);
    try {
      await ensureSchema(env);
      if (req.method !== 'GET') {
        // basic protection against requests sent from other websites
        const origin = req.headers.get('origin');
        if (origin && new URL(origin).host !== url.host) return fail(403, 'Request from another website was blocked.');
        if (!(req.headers.get('content-type') || '').includes('application/json')) return fail(415, 'Send JSON.');
      }
      if (path === '/api/me' && req.method === 'GET') return apiMe(env, req);
      if (path === '/api/setup' && req.method === 'POST') return apiSetup(env, req);
      if (path === '/api/login' && req.method === 'POST') return apiLogin(env, req);
      if (path === '/api/logout' && req.method === 'POST') return apiLogout(env, req);

      const user = await currentUser(env, req);
      if (!user) return fail(401, 'Please sign in again.');
      if (path === '/api/data' && req.method === 'GET') return apiData(env, user);
      if (path === '/api/version' && req.method === 'GET') return apiVersion(env);
      if (path === '/api/ops' && req.method === 'POST') return apiOps(env, req, user);
      if (path === '/api/password' && req.method === 'POST') return apiPassword(env, req, user);
      if (path === '/api/import' && req.method === 'POST') return apiImport(env, req, user);
      if (path === '/api/trash' && req.method === 'GET') return apiTrash(env, user);
      if (path === '/api/restore' && req.method === 'POST') return apiRestore(env, req, user);
      if (path === '/api/users') return apiUsers(env, req, user);
      const m = path.match(/^\/api\/users\/(\d+)$/);
      if (m && req.method === 'PATCH') return apiUserUpdate(env, req, user, Number(m[1]));
      return fail(404, 'Not found.');
    } catch (e) {
      console.error(e);
      return fail(500, 'Something went wrong on the server. Please try again.');
    }
  }
};
