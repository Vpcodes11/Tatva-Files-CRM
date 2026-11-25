# "Converted" was renamed "Booked" everywhere (25 Nov 2026): on every page, in the choices, and in the saved data
# (one-time update migrateConvertedToBooked). Run against `npm run dev` after tests/e2e.py has created pratik / secret123.
from playwright.sync_api import sync_playwright
U = 'http://localhost:8787/'; E = "s => __dbg(s)"
def ok(c, m): print(('PASS ' if c else 'FAIL ') + m)
with sync_playwright() as p:
    b = p.chromium.launch(executable_path='/usr/bin/google-chrome'); errs = []
    a = b.new_context(viewport={'width': 1400, 'height': 900}).new_page(); a.on('pageerror', lambda x: errs.append(str(x)))
    a.goto(U); a.wait_for_selector('#loginForm'); a.fill('[name=username]', 'pratik'); a.fill('[name=password]', 'secret123'); a.click('#loginForm button'); a.wait_for_selector('#nav a', timeout=20000)
    q = lambda js: a.evaluate(E, js)
    def go(h): q(f"location.hash='{h}'"); a.wait_for_timeout(350)

    ok(q("D.bookings.filter(b => /convert/i.test(b.outcome || '')).length") == 0 and q("D.bookings.filter(b => b.outcome === 'Booked').length") >= 87, 'saved booking statuses say Booked (%d), none say Converted' % q("D.bookings.filter(b => b.outcome === 'Booked').length"))
    ok(q("D.visits.filter(v => /convert|^done$/i.test(v.status || '')).length") == 0, 'saved visit statuses: no Converted / DONE left')
    ok('onvert' not in q("JSON.stringify([OPTS, VISIT_STATUSES])"), 'no "Converted" in any dropdown or status list')
    cid = q("D.clients.find(c => clientStatus(c)[0] === 'Booked').id"); pl = q("D.bookings.find(isConvertedBooking).plot")
    vid = q("D.visits.find(isConvertedVisit).id")
    seen = []
    for h, lapsed in [('#/visits', False), ('#/visits', True), ('#/clients', None), (f'#/client/{cid}', None), (f'#/plot/{pl}', None), (f'#/visit/{vid}', None),
                      ('#/plots', None), ('#/landowners', None), ('#/incentives', None), ('#/history', None), ('#/check', None), ('#/users', None)]:
        if lapsed is not None: q(f"listView.visitsLapsed = {'true' if lapsed else 'false'}")
        go(h)
        if 'onverted' in q("document.querySelector('#view').innerText") or 'onverted' in q("document.querySelector('#nav').innerText"): seen.append(h)
    ok(not seen, 'the word "Converted" appears on no page (%s)' % (seen or 'checked 12 pages'))
    go(f'#/plot/{pl}'); a.click('.card tbody tr .pen'); a.wait_for_timeout(200)
    opts = q("[...document.querySelectorAll('.dlg select option')].map(o => o.textContent)"); sel = q("document.querySelector('.dlg select').selectedOptions[0].textContent"); a.click('[data-dlgclose]')
    ok('Booked' in opts and not any('onvert' in o for o in opts) and sel == 'Booked', 'booking status choices: %s (selected %s)' % (opts, sel))
    go('#/visits'); a.click('[data-addvisit]'); a.wait_for_timeout(200)
    chips = q("[...document.querySelectorAll('.dlg .chips[data-group=deal] .chip')].map(c => c.dataset.chip)"); a.click('[data-dlgclose]')
    ok('Booked' in chips and 'Converted' not in chips, 'add-visit status row says Booked: %s' % chips)
    ok(q("clientStatus(clientById['%s'])[0]" % cid) == 'Booked' and q(f"vStatus(IDX.visits['{vid}'])[0]") == 'Booked', 'client and visit show Booked')
    go('#/plots'); col = q("[...new Set(TABLES.plots.rows.map(p => TABLES.plots.cols.find(c => c.k === 'booking').get(p)))]")
    ok('Available' in col and 'Lapsed only' not in col, 'Plots → Booking list: plots whose holds all lapsed say "Available" (%s)' % col)
    ok('Lapsed only' not in q("document.querySelector('#view').innerText"), '"Lapsed only" is gone from the Plots page')
    print('ERRORS', errs)
