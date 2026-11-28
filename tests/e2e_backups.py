# Backups (27 Nov 2026): a full copy of every record is made each night (cron), by hand ("Back up now") and before a
# restore. Admin / Super admin can see and download them; only a Super admin can restore. Run after tests/e2e.py.
import json, urllib.request
from playwright.sync_api import sync_playwright
U = 'http://localhost:8787/'; E = "s => __dbg(s)"
def ok(c, m): print(('PASS ' if c else 'FAIL ') + m)
with sync_playwright() as p:
    b = p.chromium.launch(executable_path='/usr/bin/google-chrome'); errs = []
    def login(u, pw):
        pg = b.new_context(viewport={'width': 1366, 'height': 860}).new_page(); pg.on('pageerror', lambda x: errs.append(str(x)))
        pg.goto(U); pg.wait_for_selector('#loginForm'); pg.fill('[name=username]', u); pg.fill('[name=password]', pw); pg.click('#loginForm button'); pg.wait_for_selector('#nav a', timeout=20000); return pg
    a = login('pratik', 'secret123'); q = lambda js: a.evaluate(E, js)
    get = lambda pg, path: pg.evaluate(f"fetch('{path}').then(async r => [r.status, await r.text()])")
    post = lambda pg, path: pg.evaluate(f"fetch('{path}', {{method: 'POST', headers: {{'content-type': 'application/json'}}, body: '{{}}'}}).then(async r => [r.status, await r.text()])")
    st, body = get(a, '/api/backups'); r = json.loads(body)
    ok(st == 200 and len(r['backups']) >= 1 and r['backups'][-1]['note'] == 'First backup', 'a first backup was made by itself (%d kept)' % len(r['backups']))
    # the nightly job (cron) makes a backup
    n0 = len(r['backups']); urllib.request.urlopen(U + 'cdn-cgi/handler/scheduled?cron=0+21+*+*+*').read(); a.wait_for_timeout(1500)
    r = json.loads(get(a, '/api/backups')[1]); ok(len(r['backups']) == n0 + 1 and r['backups'][0]['kind'] == 'daily' and r['backups'][0]['n_records'] == r['live'], 'the nightly job made a full backup (%d records)' % r['backups'][0]['n_records'])
    # page
    q("location.hash='#/backups'"); a.wait_for_timeout(600)
    ok('every night at 2:30 am' in a.inner_text('#view') and q("document.querySelectorAll('.tablecard tbody tr').length") == len(r['backups']), 'Backups page lists every copy')
    a.click('[data-bknow]'); a.wait_for_timeout(1500)
    r = json.loads(get(a, '/api/backups')[1]); man = r['backups'][0]
    ok(man['kind'] == 'manual' and man['by_name'] not in (None, 'automatic'), '"Back up now" made a copy by hand')
    st, f = get(a, f"/api/backups/{man['id']}"); fj = json.loads(f)
    ok(st == 200 and len(fj['records']) == man['n_records'] and {'coll', 'id', 'sr', 'data'} <= set(fj['records'][0]) and isinstance(fj['records'][0]['data'], dict), 'Download gives the whole copy as a file (%d records)' % len(fj['records']))
    vid = q("D.visits[0].id"); old = q("D.visits[0].name")
    q(f"sendOps([{{op: 'patch', coll: 'visits', id: '{vid}', field: 'name', value: 'Changed After Backup'}}])"); a.wait_for_timeout(800)
    # restore: Admin can't, Super admin can (typing RESTORE)
    ok(q("fetch('/api/users',{method:'POST',headers:{'content-type':'application/json'},body:JSON.stringify({name:'Backup Admin',username:'bkadmin',role:'Admin',password:'pass1234'})}).then(r=>r.status)") in (200, 201), 'added an Admin')
    ok(q("fetch('/api/users',{method:'POST',headers:{'content-type':'application/json'},body:JSON.stringify({name:'Backup Agent',username:'bkagent',role:'Agent',password:'pass1234'})}).then(r=>r.status)") in (200, 201), 'added an Agent')
    ad = login('bkadmin', 'pass1234'); ok(get(ad, '/api/backups')[0] == 200 and post(ad, f"/api/backups/{man['id']}/restore")[0] == 403, 'Admin: can see backups, cannot restore')
    ag = login('bkagent', 'pass1234'); ok(get(ag, '/api/backups')[0] == 403 and get(ag, f"/api/backups/{man['id']}")[0] == 403, 'Agent: no backups at all')
    a.reload(); a.wait_for_selector('#nav a'); q("location.hash='#/backups'"); a.wait_for_timeout(600)
    a.click(f"[data-bkrestore='{man['id']}']"); a.wait_for_timeout(200); a.click('[data-dlgok]'); a.wait_for_timeout(300)
    ok('Type RESTORE' in q("document.querySelector('#dlg_err').textContent"), 'restore asks to type RESTORE')
    a.fill('#bk_ok', 'RESTORE'); a.click('[data-dlgok]'); a.wait_for_timeout(2500); a.wait_for_selector('#nav a')
    ok(q(f"IDX.visits['{vid}'].name") == old, 'restored: the visit name is back to how it was in the backup')
    r = json.loads(get(a, '/api/backups')[1]); br = r['backups'][0]
    fj = json.loads(get(a, f"/api/backups/{br['id']}")[1])
    ok(br['kind'] == 'before-restore' and any(x['id'] == vid and x['data'].get('name') == 'Changed After Backup' for x in fj['records'] if x['coll'] == 'visits'), 'the data just before the restore was backed up first (can be undone)')
    ok(r['live'] == man['n_records'], 'record count matches the restored copy')
    ok(not errs, 'no page errors (%s)' % errs)
