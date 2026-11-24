# Checks for the 24 Nov 2026 changes. Run against `npm run dev` with a freshly loaded local database
# after tests/e2e.py has created the users (pratik / secret123).
from playwright.sync_api import sync_playwright
U = 'http://localhost:8787/'
E = "s => __dbg(s)"
def ok(c, m): print(('PASS ' if c else 'FAIL ') + m)
with sync_playwright() as p:
    b = p.chromium.launch(executable_path='/usr/bin/google-chrome'); a = b.new_context(viewport={'width': 1300, 'height': 900}).new_page(); errs = []
    a.on('pageerror', lambda x: errs.append(str(x)))
    a.goto(U); a.wait_for_selector('#loginForm'); a.fill('[name=username]', 'pratik'); a.fill('[name=password]', 'secret123'); a.click('#loginForm button'); a.wait_for_selector('#nav a', timeout=20000)
    # 1 + 5: one remark, no follow-up fields
    leftover = a.evaluate(E, "D.visits.filter(v => ['extra','followups','fu1Date','fu1Note','fu4Note','fuRemark'].some(k => k in v)).length")
    ok(leftover == 0, 'old Note / follow-up fields are gone from every visit')
    ok(a.evaluate(E, "D.visits.filter(v => /FU1/.test(v.remark || '')).length") > 50, 'follow-up notes were kept inside the Remark')
    a.evaluate(E, "location.hash='#/visits'"); a.wait_for_timeout(400)
    heads = a.evaluate(E, "[...document.querySelectorAll('thead th')].map(t => t.textContent.trim())")
    ok('Remark' in ' '.join(heads) and 'Follow-up' not in ' '.join(heads) and 'Latest note' not in ' '.join(heads), 'Site visits list shows Remark, no follow-up columns: %s' % heads)
    vid = a.evaluate(E, "D.visits.find(v => !isConvertedVisit(v)).id"); a.evaluate(E, f"location.hash='#/visit/{vid}'"); a.wait_for_timeout(400)
    ok('Follow-ups' not in a.inner_text('#view'), 'visit page has no Follow-ups card')
    # 2 + 4: add visit with two agents, one status row with Hold/Book, one remark
    a.evaluate(E, "location.hash='#/visits'"); a.wait_for_timeout(300); a.click('[data-addvisit]'); a.wait_for_timeout(200)
    ids = a.evaluate(E, "[...document.querySelectorAll('.dlg input,.dlg textarea,.dlg select')].map(x => x.id)")
    ok(not any(i in ids for i in ['nv_extra', 'nv_fu1d', 'nv_fu1n', 'nv_by']), 'add-visit form has only one Remark, no Note or follow-up fields')
    chips = a.evaluate(E, "[...document.querySelectorAll('.dlg .chips[data-group=deal] .chip')].map(c => c.dataset.chip)")
    ok(chips == ['Follow up', 'Converted', 'Not interested', 'Hold', 'Book'], 'status row: %s' % chips)
    a.fill('#nv_name', 'Two Agent Test'); a.fill('#nv_phone', '9222233333')
    a.click('.chips[data-group=agents] .chip >> nth=0'); a.click('.chips[data-group=agents] .chip >> nth=1'); a.click('[data-chip="Not interested"]')
    a.fill('#nv_remark', 'came with family, liked corner plots'); a.click('[data-dlgok]'); a.wait_for_timeout(1500)
    a.reload(); a.wait_for_selector('#nav a'); a.wait_for_timeout(300)
    v = a.evaluate(E, "(() => { const v = D.visits.find(x => x.name === 'Two Agent Test'); return [v.by, vStatus(v)[0], v.remark]; })()")
    ok(len(v[0].split(', ')) == 2 and v[1] == 'Not interested' and v[2] == 'came with family, liked corner plots', 'visit saved with 2 agents, status and remark: %s' % v)
    # Book straight from the add-visit form
    a.click('[data-addvisit]'); a.fill('#nv_name', 'Book Test'); a.click('.chips[data-group=agents] .chip >> nth=0'); a.click('[data-chip=Book]')
    pl = a.evaluate(E, "freePlots()[0].no"); a.select_option('#nv_plot', pl); a.fill('#nv_final', '900000'); a.click('[data-dlgok]'); a.wait_for_timeout(1500)
    ok(a.evaluate(E, f"D.plots['{pl}'].status") == 'SOLD OUT' and a.evaluate(E, "vStatus(D.visits.find(x => x.name === 'Book Test'))[0]") == 'Converted', 'Book from the form books the plot and converts the visit')
    # agents can be changed with the pencil (multi)
    a.evaluate(E, "location.hash='#/visits'"); a.wait_for_timeout(300)
    # 3: lapsed visits in their own tab
    nL = a.evaluate(E, "D.visits.filter(v => v.client && clientById[v.client] && clientStatus(clientById[v.client])[0] === 'Lapsed').length")
    shown = a.evaluate(E, "document.querySelector('.tcount, .count') ? 0 : 0")
    a.click('[data-lv=visitsLapsed][data-val="1"]'); a.wait_for_timeout(300)
    rows = a.evaluate(E, "document.querySelectorAll('tbody tr').length"); go = a.evaluate(E, "(document.querySelector('tbody tr') || {dataset: {}}).dataset.go || ''")
    ok(nL > 0 and rows == nL and go.startswith('#/client/'), 'Lapsed tab lists %d lapsed visits and opens the client' % nL)
    a.click('[data-lv=visitsLapsed][data-val=""]'); a.wait_for_timeout(300)
    # 6 + 8: clients
    a.evaluate(E, "location.hash='#/clients'"); a.wait_for_timeout(400)
    nLc = a.evaluate(E, "D.clients.filter(c => clientStatus(c)[0] === 'Lapsed').length")
    statuses = a.evaluate(E, "[...document.querySelectorAll('tbody tr')].map(r => r.innerText).join(' ')")
    ok('Lapsed' not in statuses, 'Clients list hides %d lapsed clients by default' % nLc)
    dates = a.evaluate(E, "[...document.querySelectorAll('tbody tr')].map(r => r.dataset.go.split('/')[2]).map(id => clientDate(clientById[id]) || '')")
    ok(dates[:20] == sorted(dates[:20], reverse=True) and dates[0] >= '2026', 'clients are newest first: %s' % dates[:3])
    heads = a.evaluate(E, "[...document.querySelectorAll('thead th')].map(t => t.textContent.trim())"); ok(any(h.startswith('Date') for h in heads), 'Date column with filter')
    a.click('[data-lv=clientsLapsed]'); a.wait_for_timeout(300)
    ok('Lapsed' in a.evaluate(E, "[...document.querySelectorAll('tbody tr')].map(r => r.innerText).join(' ')"), 'Lapsed button adds lapsed clients to the list')
    # 7: incentives without Pratik
    a.evaluate(E, "location.hash='#/incentives'"); a.wait_for_timeout(400)
    ok('Pratik' not in a.inner_text('#view'), 'Incentives page has no Pratik')
    for h in ['#/visits', '#/clients', '#/plots', '#/history', '#/check', '#/incentives']:
        a.evaluate(E, f"location.hash='{h}'"); a.wait_for_timeout(250)
    a.screenshot(path='/tmp/n24.png')
    print('ERRORS', errs)
