# Cross-module consistency: the same fact must give the same number everywhere. Run after tests/e2e.py (users exist).
from playwright.sync_api import sync_playwright
U = 'http://localhost:8787/'; E = "s => __dbg(s)"
def ok(c, m): print(('PASS ' if c else 'FAIL ') + m)
with sync_playwright() as p:
    b = p.chromium.launch(executable_path='/usr/bin/google-chrome'); a = b.new_context(viewport={'width': 1300, 'height': 900}).new_page(); errs = []
    a.on('pageerror', lambda x: errs.append(str(x)))
    a.goto(U); a.wait_for_selector('#loginForm'); a.fill('[name=username]', 'pratik'); a.fill('[name=password]', 'secret123'); a.click('#loginForm button'); a.wait_for_selector('#nav a', timeout=20000)
    nav = lambda k: int(a.evaluate(E, f"document.querySelector('#nav [data-go=\"#/{k}\"] .ct').innerText"))
    def page_count(h):
        a.evaluate(E, f"location.hash='{h}'"); a.wait_for_timeout(350)
        return int(a.evaluate(E, "document.querySelector('.tmeta').innerText.match(/\\d+/)[0]"))
    ok(nav('visits') == page_count('#/visits'), 'Site visits: menu count = list count (%d)' % nav('visits'))
    ok(nav('clients') == page_count('#/clients'), 'Clients: menu count = list count (%d)' % nav('clients'))
    ok(nav('landowners') == page_count('#/landowners'), 'Sold plots: menu count = list count (%d)' % nav('landowners'))
    sold_plots = a.evaluate(E, "Object.values(D.plots).filter(p => plotClass(p)[1] === 'Sold').length")
    a.evaluate(E, "location.hash='#/landowners'"); a.wait_for_timeout(300)
    ok(a.evaluate(E, "TABLES.landowners.rows.filter(r => r.p && plotClass(r.p)[1] === 'Sold').length") == sold_plots, 'every Sold plot is in Sold plots (%d)' % sold_plots)
    ok(a.evaluate(E, "D.bookings.filter(isConvertedBooking).every(b => !b.plot || !D.plots[b.plot] || plotClass(D.plots[b.plot])[1] === 'Sold')"), 'every Booked booking’s plot shows Sold')
    ok(a.evaluate(E, "Object.values(D.plots).filter(p => plotClass(p)[1] === 'Hold').every(p => D.bookings.some(b => b.plot === p.no && /hold/i.test(b.outcome || '')))"), 'every Hold plot has an active hold')
    ok(a.evaluate(E, "D.bookings.filter(isConvertedBooking).every(b => !b.plot || clientById[plotOwner[b.plot]] && clientById[plotOwner[b.plot]].bookings.includes(b.id))"), 'every Booked booking’s plot belongs to that client')
    held = a.evaluate(E, "new Set(D.clients.filter(c => clientStatus(c)[0] === 'On hold').flatMap(c => c.bookings.map(id => bookingById[id]).filter(b => /hold/i.test(b.outcome || '') && b.plot).map(b => b.plot))).size")
    ok(held == a.evaluate(E, "Object.values(D.plots).filter(p => plotClass(p)[1] === 'Hold').length"), 'plots held by On hold clients = Hold plots (%d)' % held)
    nL = a.evaluate(E, "D.visits.filter(v => vStatus(v)[0] === 'Lapsed').length")
    a.evaluate(E, "location.hash='#/visits'"); a.wait_for_timeout(300); a.click('[data-lv=visitsLapsed][data-val="1"]'); a.wait_for_timeout(300)
    ok(a.evaluate(E, "TABLES['visits-lapsed'].rows.length") == nL and nav('visits') + nL == a.evaluate(E, "D.visits.length"), 'Follow up (%d) + Lapsed (%d) = all visits' % (nav('visits'), nL))
    ok(a.evaluate(E, "D.clients.filter(clientLapsed).every(c => D.visits.filter(v => v.client === c.id).every(v => vStatus(v)[0] === 'Lapsed' || v.reopened))"), 'a lapsed client’s visits are Lapsed unless moved back to Follow up')
    # pencil can't make a plot disagree with its booking
    pl = a.evaluate(E, "D.bookings.find(isConvertedBooking).plot")
    a.evaluate(E, f"location.hash='#/plot/{pl}'"); a.wait_for_timeout(300)
    ok(a.evaluate(E, f"!!lockReason('plots', D.plots['{pl}'], 'status')"), 'plot status of a sold plot follows its booking (pencil locked)')
    # changing a booking to Booked with the pencil makes the plot Sold and gives it to the client
    bk = a.evaluate(E, "D.bookings.find(b => /hold/i.test(b.outcome || '') && b.plot).id")
    a.evaluate(E, f"(async () => {{ await sendOps([{{op: 'patch', coll: 'bookings', id: '{bk}', field: 'outcome', value: 'Booked'}}]); }})()"); a.wait_for_timeout(1200)
    a.reload(); a.wait_for_selector('#nav a'); a.wait_for_timeout(300)
    r = a.evaluate(E, f"(() => {{ const b = IDX.bookings['{bk}']; const c = D.clients.find(x => x.bookings.includes(b.id)); return [plotClass(D.plots[b.plot])[1], plotOwner[b.plot] === c.id, clientStatus(c)[0]]; }})()")
    ok(r == ['Sold', True, 'Booked'], 'booking set to Booked → plot Sold, owned by the client, client Booked: %s' % r)
    a.evaluate(E, "location.hash='#/check'"); a.wait_for_timeout(400)
    ok('Needs a look' in a.inner_text('#view') and 'Plot 313' in a.inner_text('#view'), 'Data check lists the disagreements (e.g. plot 313)')
    for h in ['#/visits', '#/clients', '#/plots', '#/landowners', '#/partner', '#/expenses', '#/incentives', '#/check', '#/history', '#/trash']:
        a.evaluate(E, f"location.hash='{h}'"); a.wait_for_timeout(250)
    print('ERRORS', errs)
