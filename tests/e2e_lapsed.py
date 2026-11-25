# Site visits: "Follow up" and "Lapsed" tabs (25 Nov 2026). "Not interested" is now "Lapsed"; setting a visit to
# Lapsed moves it to the Lapsed tab, and setting it to a Follow up moves it back — also for a lapsed client's visit.
# Run against `npm run dev` with a freshly loaded local database, after tests/e2e.py has created pratik / secret123.
from playwright.sync_api import sync_playwright
U = 'http://localhost:8787/'; E = "s => __dbg(s)"
def ok(c, m): print(('PASS ' if c else 'FAIL ') + m)
def login(pg, user, pw):
    pg.goto(U); pg.wait_for_selector('#loginForm'); pg.fill('[name=username]', user); pg.fill('[name=password]', pw); pg.click('#loginForm button'); pg.wait_for_selector('#nav a', timeout=20000); pg.wait_for_timeout(300)
with sync_playwright() as p:
    b = p.chromium.launch(executable_path='/usr/bin/google-chrome'); errs = []
    a = b.new_context(viewport={'width': 1300, 'height': 900}).new_page(); a.on('pageerror', lambda x: errs.append(str(x)))
    login(a, 'pratik', 'secret123')
    q = lambda js: a.evaluate(E, js)
    def go(h): q(f"location.hash='{h}'"); a.wait_for_timeout(350)
    def tab(lapsed): go('#/visits'); a.click(f'[data-lv=visitsLapsed][data-val="{"1" if lapsed else ""}"]'); a.wait_for_timeout(300)
    in_tab = lambda vid, t: q(f"TABLES['{t}'].rows.some(v => v.id === '{vid}')")
    def set_status(vid, value):  # pencil on the visit page, like a user would
        go(f'#/visit/{vid}'); a.click('.card h2 .pen'); a.wait_for_timeout(200); a.select_option('.dlg select', value); a.click('[data-dlgok]'); a.wait_for_timeout(1000)
    def reload(): a.reload(); a.wait_for_selector('#nav a'); a.wait_for_timeout(300)

    # tabs and names
    tab(False)
    names = q("[...document.querySelectorAll('[data-lv=visitsLapsed]')].map(c => c.childNodes[0].textContent.trim())")
    ok(names == ['Follow up', 'Lapsed'], 'Site visits tabs are Follow up and Lapsed: %s' % names)
    ok('Not interested' not in q("JSON.stringify([...new Set(D.visits.map(v => vStatus(v)[0]))].concat(OPTS.visitStatus, VISIT_STATUSES))"), '"Not interested" is gone from statuses and choices')
    ok('Lapsed' in q("OPTS.visitStatus"), 'Lapsed can be chosen in the status dropdown')
    old = q("D.visits.find(v => !v.client && /NOT/i.test(v.status || '')).id")
    ok(q(f"vStatus(IDX.visits['{old}'])[0]") == 'Lapsed' and not in_tab(old, 'visits'), 'an old "Not interested" visit shows as Lapsed and is not in Follow up')
    tab(True); ok(in_tab(old, 'visits-lapsed'), '… and it is in the Lapsed tab')
    nav = lambda: int(q("document.querySelector('#nav [data-go=\"#/visits\"] .ct').innerText"))
    ok(nav() == q("D.visits.filter(v => vStatus(v)[0] !== 'Lapsed').length"), 'menu count = Follow up tab count (%d)' % nav())

    # each tab has its own Sr. series 1, 2, 3 … (newest at the top)
    def series_ok(lapsed):
        tab(lapsed); t = 'visits-lapsed' if lapsed else 'visits'
        srs = q(f"(() => {{ const m = visitSrs(); return TABLES['{t}'].rows.map(v => m.get(v.id)).sort((a, b) => a - b); }})()")
        top = q("+document.querySelector('tbody tr td').innerText")
        return len(srs) > 0 and srs == list(range(1, len(srs) + 1)) and top == len(srs), len(srs)
    for lapsed in (False, True):
        good, n = series_ok(lapsed); ok(good, '%s tab has its own Sr. 1–%d, newest on top' % ('Lapsed' if lapsed else 'Follow up', n))
    # a follow-up visit set to Lapsed moves to the Lapsed tab, and back again
    fu = q("D.visits.find(v => !v.client && /FOLLOW/i.test(v.status || '')).id"); n0 = nav(); nl0 = q("D.visits.filter(isLapsedVisit).length")
    set_status(fu, 'Lapsed'); reload(); tab(True)
    ok(q(f"vStatus(IDX.visits['{fu}'])[0]") == 'Lapsed' and in_tab(fu, 'visits-lapsed') and nav() == n0 - 1, 'Follow up visit set to Lapsed → in Lapsed tab, menu count down by 1')
    ok(series_ok(False)[0] and series_ok(True) == (True, nl0 + 1), 'after the move both tabs are still numbered 1, 2, 3 … without gaps')
    go(f'#/visit/{fu}'); ok(q("document.querySelector('#view .sub').innerText").startswith('Lapsed Sr. '), 'visit page shows its Lapsed Sr.: %s' % q("document.querySelector('#view .sub').innerText"))
    tab(False); ok(not in_tab(fu, 'visits'), '… and no longer in Follow up')
    set_status(fu, 'Follow up 2'); reload(); tab(False)
    ok(q(f"vStatus(IDX.visits['{fu}'])[0]") == 'Follow up 2' and in_tab(fu, 'visits') and nav() == n0, 'Lapsed visit set to Follow up 2 → back in Follow up')
    tab(True); ok(not in_tab(fu, 'visits-lapsed'), '… and no longer in Lapsed')

    # a lapsed client's visit (follows the folder) can be moved back to Follow up
    lv = q("D.visits.find(v => v.client && clientLapsed(clientById[v.client]) && /NOT/i.test(v.status || '')).id"); cid = q(f"IDX.visits['{lv}'].client")
    ok(q(f"lockReason('visits', IDX.visits['{lv}'], 'status')") is None, 'status of a lapsed client’s visit can be changed (not locked)')
    go(f'#/visit/{lv}'); a.click('.card h2 .pen'); a.wait_for_timeout(200)
    opts = q("[...document.querySelectorAll('.dlg select option')].map(o => o.textContent)"); a.click('[data-dlgclose]')
    ok('Booked' not in opts and 'Follow up 1' in opts and 'Lapsed' in opts, 'its choices are Follow up 1–4 and Lapsed: %s' % opts)
    set_status(lv, 'Follow up 1'); reload(); tab(False)
    ok(q(f"vStatus(IDX.visits['{lv}'])[0]") == 'Follow up 1' and in_tab(lv, 'visits') and q(f"IDX.visits['{lv}'].reopened") is True, 'lapsed client’s visit set to Follow up 1 → in Follow up (saved)')
    ok(q(f"clientStatus(clientById['{cid}'])[0]") == 'Lapsed', '… the client folder itself stays Lapsed (its hold did lapse)')
    set_status(lv, 'Lapsed'); reload(); tab(True)
    ok(q(f"vStatus(IDX.visits['{lv}'])[0]") == 'Lapsed' and in_tab(lv, 'visits-lapsed'), '… and set to Lapsed again → back in Lapsed')

    # server rules
    post = lambda pg, ops: pg.evaluate(E, "fetch('/api/ops',{method:'POST',headers:{'content-type':'application/json'},body:JSON.stringify({ops:%s})}).then(r=>r.status)" % ops)
    ok(post(a, f"[{{op:'patch',coll:'visits',id:'{lv}',field:'status',value:'Booked'}}]") == 403, 'server refuses Booked on a lapsed client’s visit')
    bv = q("D.visits.find(v => v.client && clientStatus(clientById[v.client])[0] === 'Booked').id")
    ok(post(a, f"[{{op:'patch',coll:'visits',id:'{bv}',field:'status',value:'Follow up 1'}}]") == 403, 'server still refuses status changes on a booked client’s visit')
    ok(q("fetch('/api/users',{method:'POST',headers:{'content-type':'application/json'},body:JSON.stringify({name:'Lapse Agent',username:'lapseagent',role:'Agent',password:'pass1234'})}).then(r=>r.status)") in (200, 201), 'added an Agent for the next check')
    g = b.new_context(viewport={'width': 1300, 'height': 900}).new_page(); g.on('pageerror', lambda x: errs.append(str(x))); login(g, 'lapseagent', 'pass1234')
    dv = g.evaluate(E, "(D.visits.find(v => v.client && clientLapsed(clientById[v.client]) && /^Booked$|DONE|CONVERT/i.test(v.status || '')) || {}).id")
    ok(dv and post(g, f"[{{op:'patch',coll:'visits',id:'{dv}',field:'status',value:'Follow up 3'}}]") == 200, 'Agent can move a lapsed client’s visit (sheet status DONE, now Booked) back to Follow up')
    g.reload(); g.wait_for_selector('#nav a'); ok(g.evaluate(E, f"vStatus(IDX.visits['{dv}'])[0]") == 'Follow up 3', '… and it shows Follow up 3')

    # a new hold ends the follow-up; when that hold lapses the visit is Lapsed again
    set_status(lv, 'Follow up 2'); go(f'#/visit/{lv}')
    a.click('[data-flow=hold]'); pl = q("freePlots()[0].no"); a.select_option('#fh_plot', pl); a.click('[data-dlgok]'); a.wait_for_timeout(1500); reload()
    ok(q(f"[vStatus(IDX.visits['{lv}'])[0], !!IDX.visits['{lv}'].reopened, clientStatus(clientById['{cid}'])[0]]") == ['Hold', False, 'On hold'], 'new hold from the visit → visit Hold, client On hold')
    go(f'#/client/{cid}')
    if a.query_selector(f'[data-csel="{pl}"]'): a.click(f'[data-csel="{pl}"]'); a.wait_for_timeout(200)
    a.click(f'[data-flow=lapse][data-bid="{q(f"D.bookings.find(x => x.plot === \'{pl}\' && /hold/i.test(x.outcome)).id")}"]'); a.click('[data-chip=yes]'); a.click('[data-dlgok]'); a.wait_for_timeout(1500); reload(); tab(True)
    ok(q(f"vStatus(IDX.visits['{lv}'])[0]") == 'Lapsed' and in_tab(lv, 'visits-lapsed'), 'that hold lapses → visit back in Lapsed')

    # new visit saved as Lapsed goes straight to the Lapsed tab
    go('#/visits'); a.click('[data-addvisit]'); a.fill('#nv_name', 'Lapsed Walkin'); a.click('.chips[data-group=agents] .chip >> nth=0'); a.click('[data-chip="Lapsed"]'); a.click('[data-dlgok]'); a.wait_for_timeout(1500); reload(); tab(True)
    nv = q("D.visits.find(v => v.name === 'Lapsed Walkin').id"); ok(in_tab(nv, 'visits-lapsed'), 'new visit saved as Lapsed is in the Lapsed tab')
    for h in ['#/visits', '#/clients', '#/check', '#/history']: go(h)
    print('ERRORS', errs)
