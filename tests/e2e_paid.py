# Paid till now (25 Nov 2026): one rule everywhere = received payments + the DP typed on a booking for the part the
# client's other payments don't already cover. Run against `npm run dev` after tests/e2e.py (pratik / secret123).
from playwright.sync_api import sync_playwright
U = 'http://localhost:8787/'; E = "s => __dbg(s)"
def ok(c, m): print(('PASS ' if c else 'FAIL ') + m)
with sync_playwright() as p:
    b = p.chromium.launch(executable_path='/usr/bin/google-chrome'); errs = []
    a = b.new_context(viewport={'width': 1500, 'height': 1000}).new_page(); a.on('pageerror', lambda x: errs.append(str(x)))
    a.goto(U); a.wait_for_selector('#loginForm'); a.fill('[name=username]', 'pratik'); a.fill('[name=password]', 'secret123'); a.click('#loginForm button'); a.wait_for_selector('#nav a', timeout=20000)
    q = lambda js: a.evaluate(E, js)
    def go(h): q(f"location.hash='{h}'"); a.wait_for_timeout(400)
    def reload(h): a.reload(); a.wait_for_selector('#nav a'); go(h)
    stat = lambda lab: q(f"[...document.querySelectorAll('.stats .stat')].find(s => s.querySelector('small').textContent.startsWith('{lab}')).querySelector('div').innerText.trim()")
    table_total = lambda: q("[...document.querySelectorAll('tfoot')].filter(t => !t.closest('.dpop')).pop().innerText.replace(/\\s+/g, ' ').trim().split(' ').pop()")
    def hold(name, phone, amt):
        go('#/visits'); a.click('[data-addvisit]'); a.fill('#nv_name', name); a.fill('#nv_phone', phone); a.click('.chips[data-group=agents] .chip >> nth=0'); a.click('[data-chip=Hold]')
        pl = q("freePlots()[0].no"); a.select_option('#nv_plot', pl); a.fill('#nv_hamt', amt); a.click('[data-dlgok]'); a.wait_for_timeout(1500)
        cid = q(f"D.clients.find(c => c.phone === '{phone}').id"); return cid, q(f"D.bookings.find(x => x.cid === '{cid}').id")
    def typed_dp(bid, amt):  # what the pencil does when a DP is typed on the booking
        q(f"sendOps([{{op: 'patch', coll: 'bookings', id: '{bid}', field: 'dpAmount', value: {amt}}}, {{op: 'patch', coll: 'bookings', id: '{bid}', field: 'dpDate', value: '2026-11-24'}}])"); a.wait_for_timeout(800)

    # the case from the screenshot: hold ₹51,000 + DP typed on the booking ₹5,00,000 + "+ Add DP" ₹1,00,000
    cid, bid = hold('Paid Test', '9555566666', '51000'); h = f'#/client/{cid}'; typed_dp(bid, 500000); reload(h)
    a.click('[data-flow=dp]'); a.fill('#fd_amt', '100000'); a.click('[data-dlgok]'); a.wait_for_timeout(1300); reload(h)
    ok(stat('Paid till now') == '₹6,51,000', 'Paid till now counts the typed DP: %s (hold 51,000 + DP 5,00,000 + DP 1,00,000)' % stat('Paid till now'))
    ok(table_total() == '₹6,51,000' and 'From booking' in q("[...document.querySelectorAll('tbody')].filter(t => !t.closest('.dpop')).pop().innerText"), 'Payments table shows the typed DP as a row and totals ₹6,51,000 too')
    go('#/clients'); ok(q(f"TABLES.clients.rows.find(c => c.id === '{cid}') && clientPaid(clientById['{cid}'])") == 651000, 'Clients list uses the same number')

    # not counted twice: other payments already cover the typed DP
    cid2, bid2 = hold('Paid Test 2', '9555577777', '1100'); h2 = f'#/client/{cid2}'; go(h2)
    a.click('[data-flow=pay]'); a.fill('#fp_amt', '300000'); a.click('[data-dlgok]'); a.wait_for_timeout(1300)
    typed_dp(bid2, 200000); reload(h2)
    ok(stat('Paid till now') == '₹3,01,100' and table_total() == '₹3,01,100', 'typed DP 2,00,000 already covered by a 3,00,000 payment → not added again (%s)' % stat('Paid till now'))
    typed_dp(bid2, 500000); reload(h2)
    ok(stat('Paid till now') == '₹5,01,100' and table_total() == '₹5,01,100', 'typed DP 5,00,000 with 3,00,000 paid → only the 2,00,000 not covered is added (%s)' % stat('Paid till now'))

    # every folder in the app: Payments table total = Paid till now = Clients list
    bad = q("""D.clients.filter(c => clientPlots(c).length <= 1).filter(c => { const t = clientPayments(c.id).concat(typedDpRows(c)).filter(received).reduce((s, p) => s + (p.amount || 0), 0);
      return Math.round(t) !== clientPaid(c); }).map(c => c.name)""")
    ok(not bad, 'all %d single-plot folders: Payments total = Paid till now (mismatches: %s)' % (q("D.clients.filter(c => clientPlots(c).length <= 1).length"), bad))
    ok(q("D.clients.every(c => clientPaid(c) >= Math.round(paidOf(clientPayments(c.id))))"), 'Paid till now is never less than the payments received')
    lap = q("(D.clients.find(c => clientStatus(c)[0] === 'Lapsed' && c.bookings.some(id => bookingById[id].dpAmount)) || {}).id")
    ok(not lap or q(f"clientPaid(clientById['{lap}']) === Math.round(paidOf(clientPayments('{lap}')))"), 'a lapsed hold’s typed DP is not counted')
    for hh in ['#/clients', '#/check']: go(hh)
    ok(not errs, 'no page errors (%s)' % errs)
