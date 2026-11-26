# Clients list: no Last hold date / Hold amount; a Remark column (last column) with the newest of the hold remark and the
# remarks added with "+ Remark" (payment calls etc.). A payment's own note is not a remark.
from playwright.sync_api import sync_playwright
U = 'http://localhost:8787/'; E = "s => __dbg(s)"
def ok(c, m): print(('PASS ' if c else 'FAIL ') + m)
with sync_playwright() as p:
    b = p.chromium.launch(executable_path='/usr/bin/google-chrome'); a = b.new_context(viewport={'width': 1366, 'height': 800}).new_page(); errs = []
    a.on('pageerror', lambda x: errs.append(str(x)))
    a.goto(U); a.wait_for_selector('#loginForm'); a.fill('[name=username]', 'pratik'); a.fill('[name=password]', 'secret123'); a.click('#loginForm button'); a.wait_for_selector('#nav a', timeout=20000)
    a.evaluate(E, "location.hash='#/clients'"); a.wait_for_timeout(300)
    heads = a.evaluate("[...document.querySelectorAll('thead th')].map(t => t.innerText.trim().toLowerCase())")
    ok('remark' in heads and 'last hold date' not in heads and 'hold amount' not in heads, 'columns: %s' % heads)
    ok([h for h in heads if h][-1] == 'remark', 'Remark is the last column of the row')
    # take a hold with a remark (today), then check it shows
    a.evaluate(E, "location.hash='#/visits'"); a.wait_for_timeout(300)
    a.click('[data-addvisit]'); a.fill('#nv_name', 'Remark Test'); a.fill('#nv_phone', '9871203456'); a.click('.chips[data-group=agents] .chip >> nth=0'); a.click('[data-chip=Hold]')
    pl = a.evaluate(E, "freePlots()[0].no"); a.select_option('#nv_plot', pl); a.wait_for_timeout(100)
    cid = None
    a.click('[data-dlgok]'); a.wait_for_timeout(1500); cid = a.evaluate(E, "location.hash.split('/')[2]")
    bid = a.evaluate(E, f"clientById['{cid}'].bookings[0]")
    a.evaluate(E, f"sendOps([{{op: 'patch', coll: 'bookings', id: '{bid}', field: 'remarks', value: 'Will pay DP after Diwali'}}, {{op: 'patch', coll: 'bookings', id: '{bid}', field: 'holdDate', value: '2026-11-01'}}])"); a.wait_for_timeout(1000)
    a.reload(); a.wait_for_selector('#nav a'); a.wait_for_timeout(300)
    r = a.evaluate(E, f"(r => r && {{date: r.date, text: r.text, kind: r.kind, by: r.by}})(clientRemark(clientById['{cid}']))")
    ok(r and r['text'] == 'Will pay DP after Diwali' and r['kind'] == 'At hold', 'hold remark shown when it is the newest: %s' % r)
    # a payment's note is not a remark
    a.evaluate(E, f"location.hash='#/client/{cid}'"); a.wait_for_timeout(300); a.click('[data-flow=pay]'); a.wait_for_timeout(300)
    a.fill('#fp_amt', '5000'); a.fill('#fp_date', '2026-11-20'); a.fill('#fp_note', 'NEFT from HDFC'); a.click('[data-dlgok]'); a.wait_for_timeout(1500)
    r = a.evaluate(E, f"(r => r && {{date: r.date, text: r.text, kind: r.kind, by: r.by}})(clientRemark(clientById['{cid}']))")
    ok(r and r['kind'] == 'At hold', 'a payment note does not replace the remark: %s' % (r and r['text']))
    # "+ Add remark" in the folder: a newer payment-call remark wins
    a.click('button[data-note]'); a.wait_for_timeout(300)
    ok(a.evaluate("document.querySelector('#nt_kind').value") == 'Call', 'remark type starts as Call for a client on hold')
    a.select_option('#nt_kind', 'Payment call'); a.fill('#nt_date', '2026-11-20'); a.fill('#nt_text', 'Called: rest after loan sanction'); a.click('[data-dlgok]'); a.wait_for_timeout(1500)
    a.reload(); a.wait_for_selector('#nav a'); a.wait_for_timeout(300)
    r = a.evaluate(E, f"(r => r && {{date: r.date, text: r.text, kind: r.kind, by: r.by}})(clientRemark(clientById['{cid}']))")
    ok(r and r['text'] == 'Called: rest after loan sanction' and r['kind'] == 'Payment call' and r['by'], 'newer payment-call remark wins, with who added it: %s' % r)
    a.evaluate(E, f"location.hash='#/client/{cid}'"); a.wait_for_timeout(300)
    rows = a.evaluate("[...document.querySelectorAll('table')].find(t => t.innerText.toLowerCase().includes('what the client said')).querySelectorAll('tbody tr').length")
    ok(rows == 2, 'folder Remarks table lists the hold remark and the call remark: %s' % rows)
    # "+ Remark" straight from the Clients list
    a.evaluate(E, "location.hash='#/clients'"); a.wait_for_timeout(300)
    a.evaluate(E, f"document.querySelector('[data-note=\"{cid}\"]').click()"); a.wait_for_timeout(300)
    ok(a.evaluate("location.hash") == '#/clients' and a.evaluate("!!document.querySelector('#nt_text')"), '+ Remark in the list opens the form without leaving the list')
    a.fill('#nt_date', '2026-11-25'); a.fill('#nt_text', 'Loan sanctioned, will pay Monday'); a.click('[data-dlgok]'); a.wait_for_timeout(1500)
    r = a.evaluate(E, f"(r => r && {{date: r.date, text: r.text, kind: r.kind, by: r.by}})(clientRemark(clientById['{cid}']))")
    ok(r and r['text'] == 'Loan sanctioned, will pay Monday', 'remark added from the list is the newest: %s' % (r and r['text']))
    a.evaluate(E, "location.hash='#/clients'"); a.wait_for_timeout(300)
    ok('Loan sanctioned, will pay Monday' in a.inner_text('#view'), 'Remark is visible in the Clients list')
    ok(a.evaluate("[...document.querySelectorAll('.tscroll')].every(s => s.scrollWidth <= s.clientWidth + 2)"), 'Clients list still fits a 1366px laptop')
    print('ERRORS', errs)
