# "Book plot" form (25 Nov 2026): numbers-only money boxes, loan fields only when a loan is availed, price per sq yd,
# booking note, optional first DP, bank name and a live summary. Run against `npm run dev` after tests/e2e.py.
from playwright.sync_api import sync_playwright
U = 'http://localhost:8787/'; E = "s => __dbg(s)"
def ok(c, m): print(('PASS ' if c else 'FAIL ') + m)
with sync_playwright() as p:
    b = p.chromium.launch(executable_path='/usr/bin/google-chrome'); errs = []
    a = b.new_context(viewport={'width': 1500, 'height': 1000}).new_page(); a.on('pageerror', lambda x: errs.append(str(x)))
    a.goto(U); a.wait_for_selector('#loginForm'); a.fill('[name=username]', 'pratik'); a.fill('[name=password]', 'secret123'); a.click('#loginForm button'); a.wait_for_selector('#nav a', timeout=20000)
    q = lambda js: a.evaluate(E, js)
    def go(h): q(f"location.hash='{h}'"); a.wait_for_timeout(400)
    vis = lambda sel: q(f"(() => {{ const e = document.querySelector('{sel}'); return !!e && e.offsetParent !== null; }})()")

    # a client on hold
    go('#/visits'); a.click('[data-addvisit]'); a.fill('#nv_name', 'Book Form Test'); a.fill('#nv_phone', '9444455555'); a.click('.chips[data-group=agents] .chip >> nth=0'); a.click('[data-chip=Hold]')
    pl = q("freePlots()[0].no"); a.select_option('#nv_plot', pl); a.click('[data-dlgok]'); a.wait_for_timeout(1500)
    cid = q("D.clients.find(c => c.phone === '9444455555').id"); area = q(f"D.plots['{pl}'].area"); go(f'#/client/{cid}')
    a.click('.acts [data-flow=book]'); a.wait_for_timeout(200)
    secs = q("[...document.querySelectorAll('.dlg .sec2')].map(x => x.childNodes[0].textContent.trim())")
    ok(secs == ['Price', 'Booking payment', 'First down payment (DP)', 'Loan'], 'form is split into Price · Booking payment · First DP · Loan: %s' % secs)

    # numbers only, with ₹ shown under the box
    a.type('#fb_amt', 'ab1,00,000-x'); ok(q("document.querySelector('#fb_amt').value") == '100000' and q("document.querySelector('#fb_amt').nextElementSibling.textContent") == '₹1,00,000', 'Booking amount keeps only numbers and shows ₹1,00,000 under it')
    a.type('#fb_final', '1200000'); ok(q("document.querySelector('#fb_rate').value") == q(f"inr(Math.round(1200000 / {area}))"), 'Price per sq yd worked out: %s' % q("document.querySelector('#fb_rate').value"))

    # loan fields only when Loan Availed
    ok(not vis('#fb_lamt') and not vis('#fb_emi') and not vis('#fb_bank'), 'Loan amount, EMI and Bank are hidden while Loan = Not Availed')
    a.select_option('#fb_loan', 'Loan Availed'); a.wait_for_timeout(100)
    ok(vis('#fb_lamt') and vis('#fb_emi') and vis('#fb_bank'), 'they appear when Loan Availed is chosen')
    a.select_option('#fb_loan', 'Not Availed'); a.wait_for_timeout(100); ok(not vis('#fb_lamt'), 'and hide again for Not Availed')
    a.select_option('#fb_loan', 'Loan Availed'); a.fill('#fb_bank', 'SBI'); a.type('#fb_lamt', '700000'); a.type('#fb_emi', '9250')

    # summary + check against the final amount
    a.type('#fb_dpamt', '2000000'); a.wait_for_timeout(100)
    ok('Balance' in q("document.querySelector('#fb_sum').innerText") and '-' in q("document.querySelector('#fb_sum').innerText.split('Balance')[1]"), 'summary shows a negative balance when too much is entered')
    a.click('[data-dlgok]'); a.wait_for_timeout(300); ok('more than the final amount' in q("document.querySelector('#dlg_err').textContent"), 'saving is refused when hold + booking + DP > final amount')
    a.fill('#fb_dpamt', '200000'); a.select_option('#fb_dpmode', 'Cash'); a.fill('#fb_note', 'cheque 004512'); a.wait_for_timeout(100)
    summ = q("document.querySelector('#fb_sum').innerText.replace(/\\s+/g, ' ')")
    ok('₹1,100' in summ and '₹3,00,000' in summ and '₹3,01,100' in summ and '₹8,98,900' in summ, 'summary: paid so far, paid now, total, balance: %s' % summ)
    a.click('[data-dlgok]'); a.wait_for_timeout(1500); a.reload(); a.wait_for_selector('#nav a'); go(f'#/client/{cid}')

    bk = q(f"(() => {{ const b = D.bookings.find(x => x.cid === '{cid}'); return [b.outcome, b.finalAmount, b.bookingAmount, b.loan, b.loanBank, b.loanAmount, b.emi]; }})()")
    ok(bk == ['Booked', 1200000, 100000, 'Loan Availed', 'SBI', 700000, 9250], 'booking saved: %s' % bk)
    pays = q(f"clientPayments('{cid}').map(p => [p.text.split(' · ')[0], p.amount, p.mode, p.note, !!p.dpOf])")
    ok(['Booking amount', 100000, 'Cheque', 'cheque 004512', False] in pays and ['Down payment (DP)', 200000, 'Cash', None, True] in pays, 'booking payment (with note) and first DP saved as payments: %s' % pays)
    ok('Bank: SBI' in q("document.querySelector('.pcols').innerText") and q("document.querySelector('.dpw').innerText").startswith('₹2,00,000'), 'folder shows Bank: SBI and the first DP')
    ok(q("[...document.querySelectorAll('.stats .stat')].find(s => s.innerText.startsWith('Remaining')).querySelector('div').innerText") == '₹8,98,900', 'Remaining balance matches the summary')

    # pencil money boxes are numbers-only too
    a.click('.stats .stat small .pen >> nth=0'); a.wait_for_timeout(200)
    ok(q("document.querySelector('.dlg input').classList.contains('amt')") and q("document.querySelector('.dlg input').nextElementSibling.textContent") == '₹12,00,000', 'pencil money boxes are numbers-only and show ₹ too')
    a.click('[data-dlgclose]')
    a.click('[data-flow=pay]'); a.type('#fp_amt', '5000'); a.click('[data-dlgclose]'); a.wait_for_timeout(200)
    ok(not errs, 'no page errors, also when typing in another form after the Book form (%s)' % errs)
    print('ERRORS', errs)
