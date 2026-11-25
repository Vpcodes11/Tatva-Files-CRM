# Client folder layout (25 Nov 2026): 7 top blocks, Booked / Lapsed buttons, Hold and booking in rows of 3
# (hold · refund · booking · DP), refund switch for a lapsed hold, and several DP payments with a hover list.
# Run against `npm run dev` after tests/e2e.py has created pratik / secret123.
from playwright.sync_api import sync_playwright
U = 'http://localhost:8787/'; E = "s => __dbg(s)"
def ok(c, m): print(('PASS ' if c else 'FAIL ') + m)
with sync_playwright() as p:
    b = p.chromium.launch(executable_path='/usr/bin/google-chrome'); errs = []
    a = b.new_context(viewport={'width': 1600, 'height': 1000}).new_page(); a.on('pageerror', lambda x: errs.append(str(x)))
    a.goto(U); a.wait_for_selector('#loginForm'); a.fill('[name=username]', 'pratik'); a.fill('[name=password]', 'secret123'); a.click('#loginForm button'); a.wait_for_selector('#nav a', timeout=20000)
    q = lambda js: a.evaluate(E, js)
    def go(h): q(f"location.hash='{h}'"); a.wait_for_timeout(400)
    def reload(h): a.reload(); a.wait_for_selector('#nav a'); go(h)
    def hold_from_visit(name, phone):
        go('#/visits'); a.click('[data-addvisit]'); a.fill('#nv_name', name); a.fill('#nv_phone', phone); a.click('.chips[data-group=agents] .chip >> nth=0'); a.click('[data-chip=Hold]')
        pl = q("freePlots()[0].no"); a.select_option('#nv_plot', pl); a.click('[data-dlgok]'); a.wait_for_timeout(1500)
        return pl, q(f"D.clients.find(c => c.phone === '{phone}').id")
    labels = lambda sel: q(f"[...document.querySelectorAll('{sel}')].map(x => x.textContent.trim())")
    stat = lambda lab: q(f"[...document.querySelectorAll('.stats .stat')].find(s => s.querySelector('small').textContent === '{lab}').querySelector('div').innerText.replace(/\\s+/g, ' ').trim()")

    pl, cid = hold_from_visit('Folder Test', '9333344444'); h = f'#/client/{cid}'; reload(h)
    ok(labels('.stats .stat small') == ['Plot no.', 'Plot size', 'Price per sq yd', 'Final amount', 'Paid till now', 'Remaining balance', 'Document status'], 'top blocks in the agreed order: %s' % labels('.stats .stat small'))
    ok(labels('.acts button') == ['Booked', 'Lapsed'], 'hold buttons are now "Booked" and "Lapsed"')
    grids = q("[...document.querySelectorAll('.pcols > div:first-child .grid2.g3')].map(g => [...g.querySelectorAll('.kv small')].map(s => s.textContent))")
    ok(grids[0] == ['Hold date', 'Hold amount', 'Hold mode', 'Refund', 'Refund amount', 'Refund mode', 'Booking date', 'Booking amount', 'Booking mode'] and grids[1] == ['DP date', 'DP amount', 'DP mode'], 'Hold and booking rows: hold · refund · booking · DP (%s)' % grids[:2])
    ok(q("getComputedStyle(document.querySelector('.grid2.g3')).gridTemplateColumns.split(' ').length") == 3, 'rows are 3 columns wide')
    ok(q("!!document.querySelector('.pcols > div:last-child .psub') && document.querySelector('.pcols > div:last-child .psub').textContent.includes('MOU')"), 'MOU and dastavej sit on the right side')
    ok(q("document.querySelector('[data-refund]').disabled") and q(f"!!lockReason('bookings', D.bookings.find(x => x.cid === '{cid}'), 'refundAmount')"), 'refund switch is off and locked while the plot is on hold')

    # book it: booking amount goes into Booking date / amount / mode, not DP
    a.click('.acts [data-flow=book]'); a.fill('#fb_final', '1100000'); a.fill('#fb_amt', '100000'); a.select_option('#fb_mode', 'UPI'); a.click('[data-dlgok]'); a.wait_for_timeout(1500); reload(h)
    bk = q(f"(() => {{ const b = D.bookings.find(x => x.cid === '{cid}'); return [b.bookingAmount, b.bookingMode, !!b.bookingDate, b.dpAmount]; }})()")
    ok(bk == [100000, 'UPI', True, None], 'Booked: booking amount saved as Booking amount / mode / date, DP left empty: %s' % bk)
    area = q(f"D.plots['{pl}'].area")
    ok(stat('Final amount') == '₹11,00,000' and stat('Price per sq yd') == q(f"inr(Math.round(1100000 / {area}))"), 'Price per sq yd = final amount ÷ plot size (%s for %s sq yd)' % (stat('Price per sq yd'), area))
    ok(stat('Paid till now') == '₹1,01,100' and stat('Remaining balance') == '₹9,98,900', 'Paid till now (hold + booking) and Remaining balance: %s / %s' % (stat('Paid till now'), stat('Remaining balance')))

    # two DP payments: total shown, hover lists them, they count as payments
    for amt, mode, note in [('200000', 'Cheque', '1st instalment'), ('150000', 'Cash', '2nd instalment')]:
        a.click('[data-flow=dp]'); a.fill('#fd_amt', amt); a.select_option('#fd_mode', mode); a.fill('#fd_note', note); a.click('[data-dlgok]'); a.wait_for_timeout(1300)
    reload(h)
    dp = q("[...document.querySelectorAll('.pcols .grid2.g3')[1].querySelectorAll('.kv > div')].map(d => d.childNodes[0].textContent.trim())")
    ok(q("document.querySelector('.dpw').innerText.split('\\n')[0].replace(/\\s+/g, ' ')").startswith('₹3,50,000') and '2 payments' in q("document.querySelector('.dpn').textContent"), 'DP amount shows the total ₹3,50,000 of 2 payments')
    ok(q("[...document.querySelectorAll('.pcols .grid2.g3')[1].querySelectorAll('.kv')][2].innerText").endswith('Cheque, Cash'), 'DP mode lists the modes used')
    ok(not a.is_visible('.dpop'), 'payment history is hidden until you hover')
    a.hover('.dpw'); a.wait_for_timeout(200)
    rows = q("[...document.querySelectorAll('.dpop tbody tr')].map(r => r.innerText.replace(/\\s+/g, ' ').trim())")
    ok(a.is_visible('.dpop') and len(rows) == 2 and '1st instalment' in rows[0] and '₹1,50,000' in rows[1] and '₹3,50,000' in q("document.querySelector('.dpop tfoot').innerText"), 'hover shows each DP payment and the total: %s' % rows)
    ok(stat('Paid till now') == '₹4,51,100' and stat('Remaining balance') == '₹6,48,900', 'DP payments count in Paid till now / Remaining balance')
    ok(q(f"clientPayments('{cid}').filter(p => p.dpOf).length") == 2 and q("[...document.querySelectorAll('tbody tr')].filter(r => r.innerText.includes('Down payment (DP)')).length") == 2, 'both DPs are in the Payments list')

    # a lapsed hold: refund switch
    pl2, cid2 = hold_from_visit('Refund Test', '9333355555'); h2 = f'#/client/{cid2}'; reload(h2)
    a.click('.acts [data-flow=lapse]'); a.click('[data-dlgok]'); a.wait_for_timeout(1500); reload(h2)
    ok(not q("document.querySelector('[data-refund]').disabled") and q("document.querySelector('[data-refund]').innerText") == 'Not refunded', 'lapsed hold: refund switch can be used, starts off')
    ok(stat('Final amount') == '—' and stat('Remaining balance') == '—', 'a lapsed hold shows no final amount or balance')
    a.click('[data-refund]'); a.wait_for_timeout(1200); reload(h2)
    r = q(f"(() => {{ const b = D.bookings.find(x => x.cid === '{cid2}'); return [b.refunded, b.refundAmount, b.refundMode, !!lockReason('bookings', b, 'refundAmount')]; }})()")
    ok(r == ['Refunded', 1100, 'Cash', False], 'switch on → Refunded; refund amount / mode filled from the hold and editable: %s' % r)
    a.click('.pcols > div:first-child .psub .pen'); a.wait_for_timeout(200)
    ok(len(q("[...document.querySelectorAll('.dlg label')].filter(l => /Refund (amount|mode)/.test(l.textContent) && !l.querySelector('.lk'))")) == 2, 'refund amount and mode can be changed with the pencil'); a.click('[data-dlgclose]')
    a.click('[data-refund]'); a.wait_for_timeout(1200); reload(h2)
    ok(q(f"D.bookings.find(x => x.cid === '{cid2}').refunded") == 'Not Refunded' and q(f"!!lockReason('bookings', D.bookings.find(x => x.cid === '{cid2}'), 'refundMode')"), 'switch off → Not refunded, refund amount / mode locked again')
    # "How this folder was put together": no longer a card on the side, a closed line at the bottom
    go(h)
    ok(not q("[...document.querySelectorAll('.card h2')].some(x => x.textContent.includes('How this folder'))"), '"How this folder was put together" is no longer a card')
    ok(q("(() => { const d = document.querySelector('details.srcinfo'); return !!d && !d.open && d.closest('.split > div:first-child') !== null && !d.nextElementSibling; })()"), 'it is a closed line at the bottom of the folder, under Payments')
    a.click('details.srcinfo summary'); a.wait_for_timeout(150)
    ok(a.is_visible('details.srcinfo > div') and 'Added in CRM' in q("document.querySelector('details.srcinfo').innerText"), 'click opens it and shows where the folder came from')
    nov = q("(D.clients.find(c => !D.visits.some(v => v.client === c.id)) || {}).id")
    go(f'#/client/{nov}'); ok(not q("!!document.querySelector('#view .split')"), 'a folder with nothing for the side column uses the full width')
    for hh in ['#/clients', '#/history', '#/check']: go(hh)
    print('ERRORS', errs)
