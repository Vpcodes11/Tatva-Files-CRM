# Roles (owner, Nov 27 2026). Agent: Site visits (add, edit, follow-ups, take a hold from a visit) + view-only Clients,
# Plots and their own incentives; office modules hidden and not sent by the server. Admin: everything except delete /
# restore; adds and changes Agents only. Super admin: everything. Needs the Super admin made by tests/e2e.py
# (pratik = Super admin); it adds its own Agent (named "Lakshit", to match his incentive rows) and Admin.
from playwright.sync_api import sync_playwright
import json
U = 'http://localhost:8787/'; E = "s => __dbg(s)"
def ok(c, m): print(('PASS ' if c else 'FAIL ') + m)
with sync_playwright() as p:
    b = p.chromium.launch(executable_path='/usr/bin/google-chrome'); errs = []
    def login(un, pw):
        pg = b.new_context(viewport={'width': 1440, 'height': 900}).new_page(); pg.on('pageerror', lambda x: errs.append(str(x)))
        pg.goto(U); pg.wait_for_selector('#loginForm'); pg.fill('[name=username]', un); pg.fill('[name=password]', pw); pg.click('#loginForm button'); pg.wait_for_selector('#nav a', timeout=20000); return pg
    def post(pg, ops): return pg.evaluate(E, f"fetch('/api/ops', {{method: 'POST', headers: {{'content-type': 'application/json'}}, body: JSON.stringify({{ops: {json.dumps(ops)}}})}}).then(r => r.status)")
    sa = login('pratik', 'secret123'); q = lambda js: sa.evaluate(E, js)
    for nm, un, role in [('Lakshit', 'rolesagent', 'Agent'), ('Role Admin', 'rolesadmin', 'Admin')]:
        q(f"fetch('/api/users',{{method:'POST',headers:{{'content-type':'application/json'}},body:JSON.stringify({{name:'{nm}',username:'{un}',role:'{role}',password:'pass1234'}})}}).then(r=>r.status)")

    # ---------- Agent ----------
    g = login('rolesagent', 'pass1234'); qa = lambda js: g.evaluate(E, js)
    nav = qa("[...document.querySelectorAll('#nav a')].map(a => a.textContent.replace(/\\d+/g, '').trim())")
    ok(nav == ['Site visits', 'Clients', 'Plots', 'My incentives'], 'Agent menu: Site visits, Clients, Plots, My incentives only (%s)' % nav)
    for h in ['#/expenses', '#/contractors', '#/partner', '#/landowners', '#/history', '#/check', '#/users', '#/trash', '#/contractor/Khod%20Bhai']:
        qa(f"location.hash='{h}'"); g.wait_for_timeout(250)
        if 'Not available' not in qa("document.querySelector('#view').innerText"): ok(False, 'Agent cannot open ' + h)
    ok(True, 'Agent gets "Not available" on every office page')
    got = qa("({exp: D.expenses.length, land: D.landowners.length, adv: D.advances.length, con: D.contractors.length, edits: store.edits.length, steps: store.flows.length})")
    ok(all(v == 0 for v in got.values()), 'the server sends no expenses, register, partner, contractors or history to an Agent: %s' % got)
    inc = qa("D.incentives.map(x => x.by)"); all_inc = q("D.incentives.filter(x => /lakshit/i.test(x.by)).length")
    ok(len(inc) == all_inc and all('lakshit' in x.lower() for x in inc), 'Agent gets only their own incentive rows (%s of %s)' % (len(inc), q("D.incentives.length")))
    qa("location.hash='#/incentives'"); g.wait_for_timeout(300)
    ok('My incentives' in qa("document.querySelector('#view h1').innerText") and qa("!document.querySelector('#view .pen, #view [data-addinc]')"), 'My incentives: view only, no add button, no pencils')
    # client folder: view only
    cid = q("D.clients.find(c => clientStatus(c)[0] === 'Booked' && c.bookings.map(i => bookingById[i]).some(b => b && isConvertedBooking(b))).id")
    hid = q("D.clients.find(c => clientStatus(c)[0] === 'On hold').id")
    for c in [cid, hid]:
        qa(f"location.hash='#/client/{c}'"); g.wait_for_timeout(400)
        btns = qa("[...document.querySelectorAll('#view [data-flow], #view [data-note], #view [data-del], #view [data-mkrec], #view [data-fu], #view .pen')].length")
        ok(btns == 0 and qa("!!document.querySelector('#view .moub .tgl[disabled]')"), f'client folder {c}: no pencils or action buttons, MOU switch disabled')
    ok(qa("[...document.querySelectorAll('#view .ed')].length") == 0 and 'Plot' in qa("document.querySelector('#view').innerText"), 'folder values are shown as plain text')
    qa("location.hash='#/clients'"); g.wait_for_timeout(300); ok(qa("!document.querySelector('#view [data-note], #view .pen')"), 'Clients list: no + Remark, no pencils')
    qa("location.hash='#/plots'"); g.wait_for_timeout(300); ok(qa("!document.querySelector('#view .pen')"), 'Plots: view only')
    qa("location.hash='#/plot/109'"); g.wait_for_timeout(300); ok(qa("!document.querySelector('#view .pen, #view [data-mkrec], #view [data-reg]')"), 'Plot page: view only')
    # site visits: full use
    qa("location.hash='#/visits'"); g.wait_for_timeout(300)
    ok(qa("!!document.querySelector('#view [data-addvisit]') && !!document.querySelector('#view [data-fu]') && !!document.querySelector('#view .pen')"), 'Site visits: Add visit, + FU and pencils are there')
    vid = qa("D.visits.find(v => !v.client && !['Booked', 'Lapsed'].includes(vStatus(v)[0])).id")
    qa(f"document.querySelector('[data-fu=\"{vid}\"]').click()"); g.wait_for_timeout(300); g.fill('#fu_note', 'Agent follow-up'); g.click('[data-dlgok]'); g.wait_for_timeout(1500)
    ok('Agent follow-up' in q(f"fetch('/api/data').then(r => r.json()).then(j => j.data.visits.find(v => v.id === '{vid}').remark)"), 'Agent can add a follow-up to a visit')
    qa(f"location.hash='#/visit/{vid}'"); g.wait_for_timeout(300); ok(qa("!!document.querySelector('[data-flow=hold][data-vid]')"), 'Agent can take a hold from a visit not yet in a folder')
    lv = qa("D.visits.find(v => v.client).id"); qa(f"location.hash='#/visit/{lv}'"); g.wait_for_timeout(300)
    ok(qa("!document.querySelector('[data-flow=hold]')"), 'no Take hold on a visit that is already in a client folder')
    # the server refuses everything else
    bid = q(f"clientById['{cid}'].bookings[0]"); pay = q("D.payments[0].id"); pl = q("Object.values(D.plots).find(p => /unsold/i.test(p.status || '')).no")
    tries = {
        'change a client': [{'op': 'patch', 'coll': 'clients', 'id': cid, 'field': 'phone', 'value': '9000000000'}],
        'change a booking': [{'op': 'patch', 'coll': 'bookings', 'id': bid, 'field': 'mouOpted', 'value': 'Opted'}],
        'change a payment': [{'op': 'put', 'coll': 'payments', 'id': pay, 'data': {'id': pay, 'amount': 1}}],
        'add a client remark': [{'op': 'put', 'coll': 'notes', 'id': 'NTX', 'data': {'id': 'NTX', 'client': cid, 'text': 'x'}}],
        'change a plot': [{'op': 'patch', 'coll': 'plots', 'id': pl, 'field': 'status', 'value': 'SOLD OUT'}],
        'add an expense': [{'op': 'put', 'coll': 'expenses', 'id': 'EX1', 'data': {'id': 'EX1', 'amount': 5}}],
        'change an incentive': [{'op': 'patch', 'coll': 'incentives', 'id': 'I3', 'field': 'slab', 'value': 1}],
        'log another step': [{'op': 'step', 'type': 'add', 'data': {}}],
        'delete': [{'op': 'del', 'coll': 'visits', 'id': vid}]}
    res = {k: post(g, v) for k, v in tries.items()}
    ok(all(v == 403 for v in res.values()), 'server refuses an Agent to: ' + ', '.join(k for k, v in res.items() if v == 403) + ('  NOT: ' + str({k: v for k, v in res.items() if v != 403}) if any(v != 403 for v in res.values()) else ''))
    ok(post(g, [{'op': 'put', 'coll': 'plots', 'id': pl, 'data': {**q(f"(({{...D.plots['{pl}']}}))"), 'status': 'HOLD', 'area': 1}}]) == 403, 'server refuses an Agent changing a plot along with a hold')

    # ---------- Admin ----------
    ad = login('rolesadmin', 'pass1234'); qd = lambda js: ad.evaluate(E, js)
    nav = qd("[...document.querySelectorAll('#nav a')].map(a => a.textContent.replace(/\\d+/g, '').trim())")
    ok(all(x in nav for x in ['Contractors', 'Site expenses', 'Land partner', 'Users', 'Edit history', 'Export all to Excel']) and 'Deleted items' not in nav, 'Admin sees every module and Users, no Deleted items')
    mk = lambda role, un: qd(f"fetch('/api/users',{{method:'POST',headers:{{'content-type':'application/json'}},body:JSON.stringify({{name:'R {un}',username:'{un}',role:'{role}',password:'pass1234'}})}}).then(r=>r.status)")
    ok(mk('Admin', 'radmin') == 403 and mk('Super admin', 'rsuper') == 403, 'Admin cannot add an Admin or a Super admin')
    ok(mk('Agent', 'ragent') in (200, 201), 'Admin can add an Agent')
    users = qd("fetch('/api/users').then(r => r.json())"); users = users.get('users', users)
    uid = lambda un: next(u['id'] for u in users if u['username'] == un)
    pt = lambda i, body: qd(f"fetch('/api/users/{i}',{{method:'PATCH',headers:{{'content-type':'application/json'}},body:JSON.stringify({json.dumps(body)})}}).then(r=>r.status)")
    ok(pt(uid('ragent'), {'role': 'Admin'}) == 403, 'Admin cannot make an Agent an Admin')
    ok(pt(uid('ragent'), {'name': 'R Agent 2'}) == 200, 'Admin can change an Agent')
    ok(pt(uid('pratik'), {'active': False}) == 403, 'Admin cannot change a Super admin')
    ok(pt(uid('rolesadmin'), {'name': 'Role Admin', 'role': 'Admin'}) == 200, 'Admin can save their own name')
    qd("location.hash='#/users'"); ad.wait_for_timeout(800); qd("document.querySelector('[data-uadd]').click()"); ad.wait_for_timeout(300)
    ok(qd("[...document.querySelectorAll('#u_role option')].map(o => o.value)") == ['Agent'], 'Admin: the Add user form offers Agent only')
    ok(post(ad, [{'op': 'del', 'coll': 'visits', 'id': vid}]) == 403, 'Admin cannot delete')
    cl = q(f"clientById['{hid}'].phone")
    ok(post(ad, [{'op': 'patch', 'coll': 'clients', 'id': hid, 'field': 'phone', 'value': cl}]) == 200, 'Admin can change a client folder')
    ok(not errs, 'no script errors: %s' % errs)
    print('ERRORS', errs)
