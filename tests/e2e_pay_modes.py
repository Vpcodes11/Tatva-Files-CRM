# Payment modes (25 Nov 2026): "Online" and "UPI" merged into "UPI / Online"; each mode has its own proof boxes
# (UPI: transaction ID; cheque: name / number / bank; NEFT/RTGS: UTR / bank; cash: received by / receipt), saved on
# the payment and shown in the Payments "Details" column. Run against `npm run dev` after tests/e2e.py.
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
    boxes = lambda sel: q(f"[...document.querySelectorAll('.mdet[data-for={sel}] label')].map(l => l.childNodes[0].textContent)")

    ok(q("OPTS.payMode") == ['Cash', 'UPI / Online', 'Cheque', 'NEFT', 'RTGS', 'Other'], 'one "UPI / Online" mode: %s' % q("OPTS.payMode"))
    ok(q("D.payments.filter(p => /^(online|upi)$/i.test(p.mode || '')).length") == 0 and q("D.bookings.filter(b => ['holdMode', 'bookingMode', 'dpMode', 'refundMode'].some(f => /^(online|upi)$/i.test(b[f] || ''))).length") == 0, 'saved "Online" / "UPI" values were merged into UPI / Online')
    ok(q("D.payments.filter(p => p.mode === 'UPI / Online').length") > 0, 'old payments now say UPI / Online (%d)' % q("D.payments.filter(p => p.mode === 'UPI / Online').length"))

    # Add payment: the boxes follow the mode
    go('#/visits'); a.click('[data-addvisit]'); a.fill('#nv_name', 'Mode Test'); a.fill('#nv_phone', '9777700001'); a.click('.chips[data-group=agents] .chip >> nth=0'); a.click('[data-chip=Hold]')
    pl = q("freePlots()[0].no"); a.select_option('#nv_plot', pl); a.select_option('#nv_hmode', 'Cash'); a.wait_for_timeout(100)
    ok(boxes('nv_hmode') == ['Received by', 'Receipt no.'], 'hold paid in Cash: Received by / Receipt no.')
    a.fill('#nv_hmode_payName', 'Sahil Bhai'); a.click('[data-dlgok]'); a.wait_for_timeout(1500)
    cid = q("D.clients.find(c => c.phone === '9777700001').id"); h = f'#/client/{cid}'; reload(h)
    ok(q(f"clientPayments('{cid}')[0].payName") == 'Sahil Bhai', 'cash hold saved who received it')
    a.click('[data-flow=pay]'); a.wait_for_timeout(200)
    expect = {'UPI / Online': ['Transaction ID / UTR', 'UPI ID / paid from'], 'Cheque': ['Cheque name', 'Cheque number', 'Bank name'], 'NEFT': ['UTR number', 'Bank name'], 'RTGS': ['UTR number', 'Bank name'], 'Cash': ['Received by', 'Receipt no.'], 'Other': ['Details']}
    seen = {}
    for m in expect: a.select_option('#fp_mode', m); a.wait_for_timeout(80); seen[m] = boxes('fp_mode')
    ok(seen == expect, 'each mode shows its own boxes: %s' % seen)
    ok(q("(() => { const r = document.querySelector('.dlg').getBoundingClientRect(); return [...document.querySelectorAll('.dlg input, .dlg select')].every(i => i.getBoundingClientRect().right <= r.right + 1); })()"), 'every box fits inside the form')
    a.select_option('#fp_mode', 'UPI / Online'); a.fill('#fp_amt', '25000'); a.fill('#fp_mode_payRef', '432198765012'); a.fill('#fp_mode_payName', 'mode@okhdfc'); a.click('[data-dlgok]'); a.wait_for_timeout(1300); reload(h)
    pay = q(f"clientPayments('{cid}').find(p => p.amount === 25000)")
    ok(pay['mode'] == 'UPI / Online' and pay['payRef'] == '432198765012' and pay['payName'] == 'mode@okhdfc' and 'payBank' not in pay, 'UPI payment saved with its transaction ID and UPI ID only')
    det = q("[...document.querySelectorAll('tbody')].pop().innerText")
    ok('Transaction ID / UTR: 432198765012' in det and 'Received by: Sahil Bhai' in det, 'Payments → Details column shows the proof of each payment')

    # Book with cheque: booking + its payment keep the cheque details; folder row shows them
    a.click('.acts [data-flow=book]'); a.fill('#fb_final', '1000000'); a.fill('#fb_amt', '50000'); a.select_option('#fb_mode', 'Cheque'); a.wait_for_timeout(80)
    a.fill('#fb_mode_payName', 'Mode Test'); a.fill('#fb_mode_payRef', '556677'); a.fill('#fb_mode_payBank', 'HDFC'); a.click('[data-dlgok]'); a.wait_for_timeout(1500); reload(h)
    bk = q(f"(() => {{ const b = D.bookings.find(x => x.cid === '{cid}'); const p = clientPayments('{cid}').find(x => /^Booking amount/.test(x.text)); return [b.payName, b.payRef, b.payBank, p.payRef, p.payBank]; }})()")
    ok(bk == ['Mode Test', '556677', 'HDFC', '556677', 'HDFC'], 'cheque details saved on the booking and its payment: %s' % bk)
    ok(all(x in q("document.querySelector('.pcols').innerText") for x in ['Cheque name', 'Cheque number', '556677', 'HDFC']), 'folder: cheque row under Booking')
    # pencil: switch the booking to UPI / Online → boxes change, cheque-only box is cleared
    a.click('.pcols > div:first-child .psub .pen'); a.wait_for_timeout(200)
    a.select_option(".dlg label:has-text('Booking mode') select", 'UPI / Online'); a.wait_for_timeout(100)
    vis = q("[...document.querySelectorAll('.dlg label')].filter(l => l.offsetParent !== null).map(l => l.childNodes[0].textContent.trim())")
    ok('Transaction ID / UTR' in vis and 'UPI ID / paid from' in vis and 'Bank name' not in vis and 'Cheque number' not in vis, 'pencil: UPI / Online shows Transaction ID and UPI ID, hides cheque boxes')
    a.click('[data-dlgok]'); a.wait_for_timeout(1000); reload(h)
    ok(q(f"(() => {{ const b = D.bookings.find(x => x.cid === '{cid}'); return [b.bookingMode, b.payName, b.payRef, b.payBank]; }})()") == ['UPI / Online', None, None, None], 'saved: mode UPI / Online; the old cheque details are cleared, not carried over')
    ok('Transaction ID / UTR' in q("document.querySelector('.pcols').innerText") and 'Cheque name' not in q("document.querySelector('.pcols').innerText"), 'folder row now shows the UPI boxes')
    # payment row pencil also follows its mode
    a.click("tr:has-text('432198765012') .pen"); a.wait_for_timeout(200)
    vis = q("[...document.querySelectorAll('.dlg label')].filter(l => l.offsetParent !== null).map(l => l.childNodes[0].textContent.trim())")
    ok('Transaction ID / UTR' in vis and 'Cheque name' not in vis, 'payment pencil shows the boxes for its mode')
    a.click('[data-dlgclose]')
    ok(not errs, 'no page errors (%s)' % errs)
