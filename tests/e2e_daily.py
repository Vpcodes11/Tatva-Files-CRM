# Daily-use actions (Nov 2026): things the team adds every day, not only what came from the old sheets.
# Site visit follow-ups with a tag (FU1–FU4), new agents, contractors and their ledger payments, incentive rows,
# the Dastavej register / payments to Anjanee, and dastavej / registry details for plots booked in the CRM.
from playwright.sync_api import sync_playwright
U = 'http://localhost:8787/'; E = "s => __dbg(s)"
def ok(c, m): print(('PASS ' if c else 'FAIL ') + m)
def go(a, h): a.evaluate(E, f"location.hash='{h}'"); a.wait_for_timeout(350)
def reload(a): a.reload(); a.wait_for_selector('#nav a', timeout=20000); a.wait_for_timeout(300)
with sync_playwright() as p:
    b = p.chromium.launch(executable_path='/usr/bin/google-chrome'); a = b.new_context(viewport={'width': 1366, 'height': 800}).new_page(); errs = []
    a.on('pageerror', lambda x: errs.append(str(x)))
    a.goto(U); a.wait_for_selector('#loginForm'); a.fill('[name=username]', 'pratik'); a.fill('[name=password]', 'secret123'); a.click('#loginForm button'); a.wait_for_selector('#nav a', timeout=20000)

    # ---- new visit with a NEW agent, plain remark tagged "Visit"
    go(a, '#/visits'); a.click('[data-addvisit]'); a.wait_for_timeout(200)
    a.fill('#nv_name', 'Daily FU Test'); a.fill('#nv_phone', '9811122233')
    a.fill('[data-newag-in]', 'Ketan Bhai'); a.press('[data-newag-in]', 'Enter'); a.wait_for_timeout(100)
    ok(a.evaluate("!!document.querySelector('#dlg [data-chip=\"Ketan Bhai\"].on')"), 'a new agent can be typed in the visit form and is chosen')
    a.fill('#nv_remark', 'Came with wife, liked plots near the club'); a.click('[data-dlgok]'); a.wait_for_timeout(1500)
    vid = a.evaluate(E, "D.visits.find(v => v.name === 'Daily FU Test').id")
    reload(a)
    ok('Ketan Bhai' in a.evaluate(E, "OPTS.agents"), 'the new agent is now in every agent list (after reload too)')
    go(a, '#/visits')
    row = a.evaluate(E, f"(() => {{ const tr = document.querySelector('[data-fu=\"{vid}\"]').closest('tr'); return tr.innerText; }})()")
    ok('Visit' in row and 'liked plots' in row, 'a plain remark shows with a "Visit" tag: %r' % row[-80:])

    # ---- + FU from the list: tag, date, note -> remark + status
    a.evaluate(E, f"document.querySelector('[data-fu=\"{vid}\"]').click()"); a.wait_for_timeout(300)
    ok(a.evaluate("location.hash") == '#/visits', '+ FU opens the form without leaving the list')
    ok(a.evaluate("document.querySelector('#dlg .chips[data-group=fu] .chip.on').dataset.chip") == '1', 'the first follow-up starts on FU1')
    a.click('[data-dlgok]'); a.wait_for_timeout(200)
    ok('Write what the client said' in a.inner_text('#dlg_err'), 'a follow-up needs a note')
    a.fill('#fu_date', '2026-11-26'); a.fill('#fu_note', 'Will come Sunday · with brother'); a.click('[data-dlgok]'); a.wait_for_timeout(1500)
    v = a.evaluate(E, f"(v => ({{remark: v.remark, status: vStatus(v)[0]}}))(IDX.visits['{vid}'])")
    ok(v['remark'] == 'Came with wife, liked plots near the club · FU1 26/11/26: Will come Sunday, with brother' and v['status'] == 'Follow up 1', 'FU1 is added to the remark and the status is Follow up 1: %s' % v)
    row = a.evaluate(E, f"document.querySelector('[data-fu=\"{vid}\"]').closest('tr').innerText")
    ok('FU1' in row and 'Will come Sunday' in row, 'the list shows the FU1 tag and the note')
    # second follow-up from the visit page: starts on FU2; choose FU3 (Sahil Bhai)
    go(a, f'#/visit/{vid}'); a.click('button[data-fu]'); a.wait_for_timeout(300)
    ok(a.evaluate("document.querySelector('#dlg .chips[data-group=fu] .chip.on').dataset.chip") == '2', 'the next follow-up starts on FU2')
    a.click('#dlg [data-chip="3"]'); a.fill('#fu_note', 'Sahil Bhai called, wants 10% discount'); a.click('[data-dlgok]'); a.wait_for_timeout(1500)
    reload(a)
    v = a.evaluate(E, f"(v => ({{remark: v.remark, status: vStatus(v)[0]}}))(IDX.visits['{vid}'])")
    ok(v['remark'].endswith('FU3 ' + a.evaluate(E, "fuStamp(today())") + ': Sahil Bhai called, wants 10% discount') and v['status'] == 'Follow up 3', 'FU3 saved and kept after reload: %s' % v['status'])
    go(a, f'#/visit/{vid}'); txt = a.inner_text('#view')
    ok('FU1' in txt and 'FU3' in txt and 'Sahil Bhai' in txt, 'the visit page shows every follow-up on its own line')
    # a follow-up can also mark the visit Lapsed
    a.click('button[data-fu]'); a.wait_for_timeout(300); a.fill('#fu_note', 'Not interested any more'); a.select_option('#fu_status', 'Lapsed'); a.click('[data-dlgok]'); a.wait_for_timeout(1500)
    ok(a.evaluate(E, f"vStatus(IDX.visits['{vid}'])[0]") == 'Lapsed', 'a follow-up can move the visit to Lapsed')
    # a visit in a client folder keeps the folder's status
    lv = a.evaluate(E, "D.visits.find(v => v.client && clientStatus(clientById[v.client])[0] === 'Booked').id")
    go(a, f'#/visit/{lv}'); a.click('button[data-fu]'); a.wait_for_timeout(300)
    ok(a.evaluate("!document.querySelector('#fu_status')") and 'Status stays' in a.inner_text('#dlg'), 'a Booked folder visit gets the note but keeps Booked')
    a.fill('#fu_note', 'Asked about registry date'); a.click('[data-dlgok]'); a.wait_for_timeout(1500)
    ok(a.evaluate(E, f"vStatus(IDX.visits['{lv}'])[0]") == 'Booked' and 'Asked about registry date' in a.evaluate(E, f"IDX.visits['{lv}'].remark"), 'its remark got the follow-up, status still Booked')

    # ---- contractors: new contractor, ledger payment, expense tagged with them
    go(a, '#/contractors'); a.click('[data-addcon]'); a.fill('#nc_name', 'Khod Bhai'); a.click('[data-dlgok]'); a.wait_for_timeout(200)
    ok('already in the list' in a.inner_text('#dlg_err'), 'the same contractor cannot be added twice')
    a.fill('#nc_name', 'Ramesh Bhai'); a.click('[data-dlgok]'); a.wait_for_timeout(1500)
    ok(a.evaluate("location.hash") == '#/contractor/Ramesh%20Bhai', 'a new contractor opens their own page')
    a.click('[data-ledger]'); a.wait_for_timeout(200); a.fill('#nl_amt', '25000'); a.fill('#nl_part', 'Boundary wall labour'); a.click('[data-dlgok]'); a.wait_for_timeout(1500)
    reload(a)
    c = a.evaluate(E, "(c => c && {n: c.ledger.length, amt: c.ledger[0] && c.ledger[0].amount, sr: c.ledger[0] && c.ledger[0].sr})(D.contractors.find(c => c.name === 'Ramesh Bhai'))")
    ok(c and c['n'] == 1 and c['amt'] == 25000 and c['sr'] == 1, 'contractor and ledger payment saved (after reload): %s' % c)
    go(a, '#/expenses'); a.click('[data-add=expense]'); a.wait_for_timeout(200)
    a.fill('#ne_part', 'Cement for wall'); a.fill('#ne_amt', '8000'); a.select_option('#ne_con', 'Ramesh Bhai'); a.fill('#ne_rem', 'Bill no 44'); a.click('[data-save=expense]'); a.wait_for_timeout(1500)
    e = a.evaluate(E, "(e => ({who: expWho(e), cats: expCats(e), rem: e.remarks}))(D.expenses.find(e => e.particulars === 'Cement for wall'))")
    ok(e['who'] == ['Ramesh Bhai'] and 'Ramesh Bhai' not in e['cats'] and e['rem'] == 'Bill no 44', 'expense: new contractor recognised, remarks saved: %s' % e)
    ok(a.evaluate(E, "D.contractors.find(c => c.name === 'Ramesh Bhai').expenses.length") == 1, 'the expense shows in the contractor folder')

    # ---- incentives: formula, live Final, new row from a booking
    f = a.evaluate(E, "incFinal(D.incentives.find(x => x.id === 'I3'))")
    ok(abs(f - 39568.57) < 0.01, 'Final follows the sheet formula: %s' % f)
    go(a, '#/incentives'); miss = a.evaluate(E, "incMissing().length")
    ok(miss > 0 and 'no incentive row yet' in a.inner_text('#view'), 'booked plots without an incentive row are pointed out: %s' % miss)
    a.click('[data-addinc]'); a.wait_for_timeout(200)
    bk = a.evaluate(E, "incMissing()[0].id"); a.select_option('#ni_bk', bk); a.wait_for_timeout(150)
    if not a.evaluate("document.querySelector('#ni_by').value"): a.select_option('#ni_by', index=1)
    a.fill('#ni_slab', '30000'); a.wait_for_timeout(100)
    ok('Final incentive' in a.inner_text('#ni_sum'), 'the form shows the Final incentive before saving')
    a.click('[data-dlgok]'); a.wait_for_timeout(1500); reload(a)
    x = a.evaluate(E, f"(b => (x => x && {{final: x.final, calc: incFinal(x), slab: x.slab}})(D.incentives.find(i => String(i.plot) === String(b.plot))))(bookingById['{bk}'])")
    ok(x and x['slab'] == 30000 and x['final'] and abs(x['final'] - x['calc']) < 0.05, 'incentive row saved with the worked-out Final: %s' % x)
    ok(a.evaluate(E, "incMissing().length") == miss - 1, 'one less booked plot without an incentive row')

    # ---- Dastavej register + payments to Anjanee
    no = a.evaluate(E, "(() => { const reg = landByPlot(); return Object.values(D.plots).find(p => plotClass(p)[1] === 'Sold' && !reg[p.no] && plotOwner[p.no]).no; })()")
    go(a, '#/landowners'); a.evaluate(E, f"document.querySelector('[data-reg=\"{no}\"]').click()"); a.wait_for_timeout(300)
    ok(a.evaluate("document.querySelector('#nr_owner').value") != '', 'register form is filled in from the client folder')
    a.click('[data-dlgok]'); a.wait_for_timeout(1500)
    ok(a.evaluate(E, f"!!landReg('{no}')"), 'plot %s added to the Dastavej register' % no)
    go(a, '#/partner'); a.click('[data-anjpay]'); a.wait_for_timeout(200); a.select_option('#na_plot', '138'); a.fill('#na_amt', '50000'); a.click('[data-dlgok]'); a.wait_for_timeout(1500)
    reload(a)
    l = a.evaluate(E, "(l => ({paid: l.anjaneePaid, n: (l.anjaneePays || []).length}))(landReg('138'))")
    ok(l['paid'] == 290000 and l['n'] == 1, 'payment to Anjanee adds to the plot total and is listed: %s' % l)
    go(a, '#/partner'); ok('Last payment' in a.inner_text('#view').title() or 'LAST PAYMENT' in a.inner_text('#view'), 'Land partner shows the last payment column')

    # ---- dastavej / registry details for a plot booked in the CRM
    cid, pn = a.evaluate(E, "(() => { for (const c of D.clients) for (const p of c.plots) { const b = c.bookings.map(i => bookingById[i]).find(b => b.plot === p && isConvertedBooking(b)); if (b && plotOwner[p] === c.id && !D.dastavej[p] && !D.registry[p]) return [c.id, p]; } return [null, null]; })()")
    ok(cid is not None, 'found a booked plot with no dastavej / registry yet: %s' % pn)
    go(a, f'#/client/{cid}')
    a.click(f'[data-mkrec="dastavej|{pn}|{cid}"]'); a.wait_for_timeout(1500)
    ok(a.evaluate(E, f"!!D.dastavej['{pn}']") and a.evaluate("!!document.querySelector('#dlg .dlg')"), 'dastavej details added and the edit form opens')
    a.click('[data-dlgclose] >> nth=0'); a.wait_for_timeout(200)
    a.click(f'[data-mkrec="registry|{pn}|{cid}"]'); a.wait_for_timeout(1500); a.click('[data-dlgclose] >> nth=0'); a.wait_for_timeout(200)
    reload(a)
    ok(a.evaluate(E, f"!!D.dastavej['{pn}'] && !!D.registry['{pn}']"), 'both are saved (after reload)')
    go(a, f'#/client/{cid}'); txt = a.inner_text('#view').lower()
    ok('vakil fee' in txt and f'data-mkrec="dastavej|{pn}' not in a.inner_html('#view'), 'the folder now shows the registry block and no more add button')

    # ---- history lists every new action, no "undefined"
    go(a, '#/history'); h = a.inner_text('#view')
    ok(all(w in h for w in ['Contractor added', 'Contractor payment added', 'Incentive added', 'Payment to Anjanee', 'Added to Dastavej register', 'Dastavej details added']) and 'undefined' not in h, 'Edit history lists the new actions')
    for hsh in ['#/visits', '#/clients', '#/contractors', '#/contractor/Ramesh%20Bhai', '#/expenses', '#/incentives', '#/partner', '#/landowners', f'#/plot/{pn}', f'#/client/{cid}', f'#/visit/{vid}']:
        go(a, hsh); t = a.inner_text('#view')
        if 'undefined' in t or 'NaN' in t: ok(False, 'no undefined/NaN on ' + hsh)
    ok(not errs, 'no script errors: %s' % errs)
    print('ERRORS', errs)
