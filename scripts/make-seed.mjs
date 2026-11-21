// Builds data/seed.sql from data/normalized.json (the cleaned data from your Excel sheets).
// Usage: node scripts/make-seed.mjs
import {readFileSync, writeFileSync} from 'node:fs';

const D = JSON.parse(readFileSync(new URL('../data/normalized.json', import.meta.url), 'utf8'));
const q = s => "'" + String(s).replace(/'/g, "''") + "'";
const rows = [], recs = [];
const add = (coll, id, sr, data) => (recs.push({coll, id, sr: sr ?? null, data}), rows.push(`(${q(coll)}, ${q(id)}, ${sr == null ? 'NULL' : Number(sr)}, ${q(JSON.stringify(data))})`));

for (const coll of ['visits', 'clients', 'bookings', 'payments', 'expenses', 'landowners', 'advances', 'incentives']) {
  for (const o of D[coll]) add(coll, o.id, o.sr, o);
}
for (const coll of ['plots', 'registry', 'dastavej']) {
  for (const o of Object.values(D[coll])) add(coll, o.id, o.sr, o);
}
for (const [plot, cid] of Object.entries(D.plotOwners)) add('plotOwners', plot, null, cid);
for (const c of D.contractors) {
  // the contractor keeps the rows of the site expenses tagged to it; ledger lines become their own records
  add('contractors', c.name, null, {id: c.name, name: c.name, expenseRows: (c.expenses || []).map(e => e.row)});
  for (const l of c.ledger) add('ledger', l.id, l.sr, {...l, contractor: c.name});
}
add('meta', 'summary', null, D.summary);

let sql = '-- Data from the Excel sheets. Load once into an empty database.\nDELETE FROM records;\n';
for (let i = 0; i < rows.length; i += 50) sql += 'INSERT INTO records (coll, id, sr, data) VALUES\n' + rows.slice(i, i + 50).join(',\n') + ';\n';
writeFileSync(new URL('../data/seed.sql', import.meta.url), sql);
writeFileSync(new URL('../data/tatva-data.json', import.meta.url), JSON.stringify(recs));
console.log(`seed.sql written: ${rows.length} records`);
