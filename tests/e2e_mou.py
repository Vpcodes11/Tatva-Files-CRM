# MOU section of the client folder (Nov 2026): "MOU" Opted / Not opted on its own line; only when Opted: Payment plan
# (Fixed / Variable payment) and six MOU boxes typed by the admin (number, date, received till now, remaining amount,
# tenure, EMI); then Dastavej delivery date / Date of dastavej / Name on dastavej. MOU money is separate from the DP.
from playwright.sync_api import sync_playwright
U = 'http://localhost:8787/'; E = "s => __dbg(s)"
def ok(c, m): print(('PASS ' if c else 'FAIL ') + m)
with sync_playwright() as p:
    b = p.chromium.launch(executable_path='/usr/bin/google-chrome'); a = b.new_context(viewport={'width': 1440, 'height': 900}).new_page(); errs = []
    a.on('pageerror', lambda x: errs.append(str(x)))
    a.goto(U); a.wait_for_selector('#loginForm'); a.fill('[name=username]', 'pratik'); a.fill('[name=password]', 'secret123'); a.click('#loginForm button'); a.wait_for_selector('#nav a', timeout=20000)
    q = lambda js: a.evaluate(E, js)
    def go(h): q(f"location.hash='{h}'"); a.wait_for_timeout(400)
    shown = lambda: q("[...document.querySelectorAll('.moub > .kv')].filter(k => k.offsetParent).map(k => k.querySelector('small').textContent)")
    off = lambda: q("[...document.querySelectorAll('.moub > .kv.off')].map(k => k.querySelector('small').textContent)")
    ALL = ['MOU', 'Payment plan', 'MOU number', 'MOU date', 'MOU received till now', 'MOU remaining amount', 'MOU tenure', 'MOU EMI', 'Dastavej delivery date', 'Date of dastavej', 'Name on dastavej']
    DET = ALL[1:8]

    # old sheet bookings that mention the MOU were marked Opted once
    ok(q("D.bookings.filter(b => /mou/i.test(b.mou || '')).every(b => b.mouOpted === 'Opted')") and q("D.bookings.filter(b => b.mouOpted === 'Opted').length") > 0, 'old bookings with an MOU are marked Opted')

    # a booked plot with no MOU choice yet, that can still be lapsed
    cid, bid = q("(() => { for (const b of D.bookings) { const c = clientById[b.cid] || D.clients.find(c => c.bookings.includes(b.id)); if (c && isConvertedBooking(b) && !b.mou && !b.mouOpted && plotOwner[b.plot] === c.id && canLapse(c, b) && !D.dastavej[b.plot] && clientPlots(c).length === 1) return [c.id, b.id]; } return [null, null]; })()")
    ok(cid is not None, 'found a booked plot with no MOU yet')
    go(f'#/client/{cid}')
    ok(shown() == ALL and off() == DET, 'MOU not chosen: every box shows, the MOU boxes greyed out (%s)' % off())
    ok('Not chosen' in q("document.querySelector('.moub').innerText") and 'Dastavej status' not in q("document.querySelector('.moub').innerText") and 'Online / cheque' not in q("document.querySelector('.moub').innerText"), 'shows "Not chosen"; old Dastavej status / Online / cheque / Cash boxes are gone')
    paid0 = q(f"clientPaid(clientById['{cid}'])")

    # one pencil for the whole block; the MOU boxes appear in the form only when Opted is chosen
    a.click('.moub >> xpath=preceding-sibling::div[contains(@class,"psub")][1] >> .pen'); a.wait_for_timeout(300)
    lab = lambda t: f"[...document.querySelectorAll('.dlg label')].find(l => l.childNodes[0].textContent.trim() === '{t}')"
    vis = lambda t: q(f"(l => !!l && l.style.display !== 'none')({lab(t)})")
    en = lambda t: q(f"(l => !!l && !l.querySelector('select, input').disabled)({lab(t)})")
    ok(vis('MOU number') and not en('MOU number') and not en('Payment plan') and en('MOU'), 'pencil: MOU boxes shown but locked while MOU is not Opted')
    sel = lambda t: q(f"{lab(t)}.querySelector('select, input').id")
    a.select_option('#' + sel('MOU'), 'Opted'); a.wait_for_timeout(100)
    ok(all(en(t) for t in DET), 'choosing Opted unlocks Payment plan and the six MOU boxes in the form')
    ok(q(f"[...{lab('Payment plan')}.querySelectorAll('option')].map(o => o.textContent).slice(1)") == ['Fixed payment', 'Variable payment'], 'Payment plan choices: Fixed payment / Variable payment')
    a.select_option('#' + sel('Payment plan'), 'Fixed payment')
    for t, v in [('MOU number', 'MOU-0142'), ('MOU date', '2026-11-27'), ('MOU received till now', '300000'), ('MOU remaining amount', '851000'), ('MOU tenure', '12 months'), ('MOU EMI', '70917')]:
        a.fill('#' + sel(t), v)
    a.click('[data-dlgok]'); a.wait_for_timeout(1500)
    a.reload(); a.wait_for_selector('#nav a'); go(f'#/client/{cid}')
    ok(shown() == ALL and off() == [], 'Opted: MOU + Payment plan, then 6 MOU boxes, then the dastavej row, none greyed (%s)' % shown())
    bk = q(f"(b => [b.mouOpted, b.mouPlan, b.mouNo, b.mouDate, b.mouReceived, b.mouRemaining, b.mouTenure, b.mouEmi])(bookingById['{bid}'])")
    ok(bk == ['Opted', 'Fixed payment', 'MOU-0142', '2026-11-27', 300000, 851000, '12 months', 70917], 'all MOU values saved (after reload): %s' % bk)
    t = q("document.querySelector('.moub').innerText")
    ok('₹3,00,000' in t and '₹8,51,000' in t and '₹70,917' in t and 'Fixed payment' in t, 'money shown as ₹ amounts')
    ok(q(f"clientPaid(clientById['{cid}'])") == paid0, 'MOU money is separate: Paid till now unchanged')
    # 3 boxes per row: MOU number / MOU date / received on one row
    tops = q("['MOU number', 'MOU date', 'MOU received till now', 'MOU remaining amount'].map(t => Math.round([...document.querySelectorAll('.moub > .kv')].find(k => k.querySelector('small').textContent === t).getBoundingClientRect().top))")
    ok(tops[0] == tops[1] == tops[2] and tops[3] > tops[0], 'six MOU boxes in rows of three (%s)' % tops)
    # phones and tablets keep the rows of three, nothing spills off the screen
    for w in [390, 768]:
        a.set_viewport_size({'width': w, 'height': 900}); a.wait_for_timeout(300)
        t3 = q("['MOU number', 'MOU date', 'MOU received till now'].map(t => Math.round([...document.querySelectorAll('.moub > .kv')].find(k => k.querySelector('small').textContent === t).getBoundingClientRect().top))")
        ok(len(set(t3)) == 1 and q("document.documentElement.scrollWidth <= document.documentElement.clientWidth"), f'{w}px screen: MOU boxes still in rows of three, page fits ({t3})')
    a.set_viewport_size({'width': 1440, 'height': 900}); a.wait_for_timeout(300)
    # MOU done (Opted with a date) -> the plot can no longer be lapsed (screen and server)
    ok(q(f"docLock(clientById['{cid}'], bookingById['{bid}'])") == 'the MOU is done', 'an Opted MOU with a date counts as MOU done: no more lapsing')
    r = q(f"sendOps([{{op: 'patch', coll: 'bookings', id: '{bid}', field: 'outcome', value: 'Lapsed'}}]).then(() => 'saved', e => e.message)")
    a.wait_for_timeout(500)
    ok('cannot be lapsed' in r, 'the server refuses to lapse it too: %s' % r)

    # Not opted hides everything MOU again (values are kept)
    a.click('.moub >> xpath=preceding-sibling::div[contains(@class,"psub")][1] >> .pen'); a.wait_for_timeout(300)
    a.select_option('#' + sel('MOU'), 'Not opted'); a.wait_for_timeout(100)
    ok(not en('MOU number'), 'choosing Not opted locks the MOU boxes in the form')
    a.click('[data-dlgok]'); a.wait_for_timeout(1500)
    ok(off() == DET and 'Not opted' in q("document.querySelector('.moub').innerText") and 'MOU-0142' in q("document.querySelector('.moub').innerText"), 'Not opted: MOU details still shown (kept), greyed out')
    ok(q(f"canLapse(clientById['{cid}'], bookingById['{bid}'])"), 'Not opted: the plot can be lapsed again')

    # empty dastavej details added in the CRM don't count as a done dastavej; a date does
    a.click(f'[data-mkrec="dastavej|{q(f"bookingById[\'{bid}\'].plot")}|{cid}"]'); a.wait_for_timeout(1500)
    ok(en('Dastavej delivery date') and en('Date of dastavej') and en('Name on dastavej'), 'Add dastavej details opens the form with the three dastavej boxes')
    a.click('[data-dlgclose] >> nth=0'); a.wait_for_timeout(200)
    ok(q(f"canLapse(clientById['{cid}'], bookingById['{bid}'])"), 'empty dastavej details do not block lapsing')
    pn = q(f"bookingById['{bid}'].plot")
    q(f"sendOps([{{op: 'patch', coll: 'dastavej', id: '{pn}', field: 'date', value: '2026-11-27'}}]).then(() => {{ setF('dastavej', D.dastavej['{pn}'], 'date', '2026-11-27'); render(); }})"); a.wait_for_timeout(800)
    ok(q(f"docLock(clientById['{cid}'], bookingById['{bid}'])") == 'the dastavej is done', 'with a dastavej date it counts as done')
    for h in [f'#/client/{cid}', f'#/plot/{pn}', '#/clients']:
        go(h)
        if 'undefined' in q("document.querySelector('#view').innerText"): ok(False, 'no undefined on ' + h)
    ok(not errs, 'no script errors: %s' % errs)
    print('ERRORS', errs)
