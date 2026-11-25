# Site visits: the Remark shows each follow-up (FU1 21/07/26: … · FU2: …) on its own line (25 Nov 2026).
# The saved text is not changed. Run against `npm run dev` after tests/e2e.py has created pratik / secret123.
from playwright.sync_api import sync_playwright
U = 'http://localhost:8787/'; E = "s => __dbg(s)"
def ok(c, m): print(('PASS ' if c else 'FAIL ') + m)
with sync_playwright() as p:
    b = p.chromium.launch(executable_path='/usr/bin/google-chrome'); errs = []
    a = b.new_context(viewport={'width': 1300, 'height': 900}).new_page(); a.on('pageerror', lambda x: errs.append(str(x)))
    a.goto(U); a.wait_for_selector('#loginForm'); a.fill('[name=username]', 'pratik'); a.fill('[name=password]', 'secret123'); a.click('#loginForm button'); a.wait_for_selector('#nav a', timeout=20000)
    q = lambda js: a.evaluate(E, js)
    def go(h): q(f"location.hash='{h}'"); a.wait_for_timeout(400)

    r = 'Broker client · FU1 21/07/26: Call Not Received · FU2 14/09/26: Call Not Received · FU3: CNR · 3 Calls But Not Received'
    parts = q(f"remarkParts({r!r})")
    ok(parts['before'] == ['Broker client'] and [f['n'] for f in parts['fus']] == [1, 2, 3] and parts['after'] == ['3 Calls But Not Received'], 'remark split into note, FU1–FU3 and closing note')
    ok([f['date'] for f in parts['fus']] == ['21 Jul 26', '14 Sep 26', None] and parts['fus'][2]['text'] == 'CNR', 'follow-up dates and notes read correctly: %s' % parts['fus'])
    ok(q("remarkParts('came with family, liked corner plots').fus.length") == 0, 'a plain remark has no follow-ups')

    # list: only the latest follow-up, full text on hover
    vid = q("D.visits.find(v => /FU1 21\\/07\\/26: Call Not Received/.test(v.remark || '')).id"); raw = q(f"IDX.visits['{vid}'].remark")
    q("listView.visitsLapsed = false"); go('#/visits')
    if not q(f"!!document.querySelector('tr[data-go=\"#/visit/{vid}\"]')"): q("listView.visitsLapsed = true"); go('#/visits')
    cell = f'tr[data-go="#/visit/{vid}"] .rmk'
    ok(q(f"[...document.querySelectorAll('{cell} .fu')].map(x => x.textContent)") == ['FU3'], 'Site visits list shows only the latest follow-up (FU3)')
    ok(q(f"document.querySelector('{cell}').innerText.replace(/\\s+/g, ' ').trim()") == 'FU3 CNR' and q(f"document.querySelector('{cell}').title") == raw, 'only "FU3 CNR" is shown; the full remark shows on hover')
    two = q("D.visits.find(v => /^FU1 [^·]*· FU2 \\d\\d\\/\\d\\d\\/\\d\\d: [^·]*$/.test(v.remark || '') && vStatus(v)[0] !== 'Lapsed').id")
    q("listView.visitsLapsed = false"); go('#/visits')
    ok(q(f"[...document.querySelectorAll('tr[data-go=\"#/visit/{two}\"] .rmk > div')].map(d => d.innerText.replace(/\\s+/g, ' ').trim())") == [q(f"'FU2 ' + remarkParts(IDX.visits['{two}'].remark).fus[1].date + ' ' + remarkParts(IDX.visits['{two}'].remark).fus[1].text")], 'a visit with FU1 and FU2 shows just its FU2 line in the list')

    # visit page: full lines, with who does FU3 / FU4
    go(f'#/visit/{vid}')
    lines = q("[...document.querySelectorAll('#view .rmk.full > div')].map(d => d.innerText.replace(/\\s+/g, ' ').trim())")
    ok(lines == ['FU1 21 Jul 26 Call Not Received', 'FU2 14 Sep 26 Call Not Received', 'FU3 CNR (Sahil Bhai)', '3 Calls But Not Received'], 'visit page lists each follow-up: %s' % lines)

    # editing still works on the plain text, and a new FU line appears straight away
    a.click('.card h2 .pen'); a.wait_for_timeout(200)
    ok(q("document.querySelector('.dlg textarea').value") == raw, 'pencil shows the remark text unchanged')
    a.fill('.dlg textarea', raw + ' · FU4 25/11/26: Pratik Sir called, visiting Sunday'); a.click('[data-dlgok]'); a.wait_for_timeout(1000)
    a.reload(); a.wait_for_selector('#nav a'); go(f'#/visit/{vid}')
    last = q("[...document.querySelectorAll('#view .rmk.full > div')].map(d => d.innerText.replace(/\\s+/g, ' ').trim())")
    ok('FU4 25 Nov 26 Pratik Sir called, visiting Sunday (Pratik Sir)' in last and q(f"IDX.visits['{vid}'].remark").endswith('visiting Sunday'), 'a typed FU4 line is saved and shown as a follow-up')

    # a visit with a plain remark still shows the text
    pv = q("D.visits.find(v => v.remark && !/FU\\d/.test(v.remark)).id"); go(f'#/visit/{pv}')
    ok(q(f"document.querySelector('#view .rmk.full').innerText") == q(f"IDX.visits['{pv}'].remark"), 'plain remark shown as written')
    print('ERRORS', errs)
