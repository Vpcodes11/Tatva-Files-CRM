# Checks for: plot Sr. series, Excel/CSV export, Super admin delete + restore. Run after tests/e2e.py (users exist).
import openpyxl, csv, io, os, tempfile
def xl(d):
    f = os.path.join(tempfile.mkdtemp(), 'x.xlsx'); d.value.save_as(f); return f
from playwright.sync_api import sync_playwright
U = 'http://localhost:8787/'; E = "s => __dbg(s)"
def ok(c, m): print(('PASS ' if c else 'FAIL ') + m)
def login(b, user, pw):
    pg = b.new_context(viewport={'width': 1300, 'height': 900}, accept_downloads=True).new_page(); errs = []
    pg.on('pageerror', lambda x: errs.append(str(x)))
    pg.goto(U); pg.wait_for_selector('#loginForm'); pg.fill('[name=username]', user); pg.fill('[name=password]', pw); pg.click('#loginForm button'); pg.wait_for_selector('#nav a', timeout=20000)
    return pg, errs
with sync_playwright() as p:
    b = p.chromium.launch(executable_path='/usr/bin/google-chrome')
    a, errs = login(b, 'pratik', 'secret123')
    # --- plot Sr. series
    a.evaluate(E, "location.hash='#/plots'"); a.wait_for_timeout(400)
    srs = a.evaluate(E, "[...document.querySelectorAll('tbody tr')].slice(0,3).map(r => r.children[0].innerText.trim())")
    ok(srs == ['1', '2', '3'], 'TRPL plots start at Sr. 1: %s' % srs)
    n_after = a.evaluate(E, "Object.values(D.plots).filter(p => !isPrePlot(p)).length")
    ok(a.evaluate(E, "Math.max(...Object.values(D.plots).filter(p => !isPrePlot(p)).map(p => plotSr.get(p.no)))") == n_after, 'TRPL series runs 1–%d' % n_after)
    a.click('[data-phase=before]'); a.click('[data-phase=after]'); a.wait_for_timeout(300)
    srs = a.evaluate(E, "[...document.querySelectorAll('tbody tr')].slice(0,2).map(r => r.children[0].innerText.trim())")
    ok(srs == ['1', '2'], 'Before TRPL plots have their own series starting at 1: %s' % srs)
    a.click('[data-phase=after]'); a.wait_for_timeout(200)
    # --- export one list (Clients) to Excel + CSV
    a.evaluate(E, "location.hash='#/clients'"); a.wait_for_timeout(400)
    with a.expect_download() as d: a.click('[data-exp=clients][data-fmt=xlsx]')
    path = xl(d); wb = openpyxl.load_workbook(path); ws = wb.active
    head = [c.value for c in ws[1]]; nrows = ws.max_row - 1
    shown = a.evaluate(E, "TABLES.clients.shown.length")
    ok(head[:3] == ['Sr.', 'Date', 'Client'] and nrows == shown, 'Clients Excel: %d rows, header %s' % (nrows, head[:5]))
    dt = ws.cell(row=2, column=2).value; amt = [c.value for c in ws[2]][head.index('Final amount')]
    ok(hasattr(dt, 'year') and (amt is None or isinstance(amt, (int, float))), 'dates are real dates, amounts are numbers (%r, %r)' % (dt, amt))
    with a.expect_download() as d: a.click('[data-exp=clients][data-fmt=csv]')
    rows = list(csv.reader(io.StringIO(open(d.value.path(), encoding='utf-8-sig').read())))
    ok(rows[0][:3] == ['Sr.', 'Date', 'Client'] and len(rows) - 1 == shown, 'Clients CSV ok (%d rows)' % (len(rows) - 1))
    # filtered export
    a.click('[data-cgroup="Booked"]'); a.wait_for_timeout(300)
    with a.expect_download() as d: a.click('[data-exp=clients][data-fmt=xlsx]')
    ok(openpyxl.load_workbook(xl(d)).active.max_row - 1 == a.evaluate(E, "TABLES.clients.shown.length"), 'export follows what is on screen (On hold only)')
    a.click('[data-cgroup="Booked"]'); a.wait_for_timeout(200)
    # --- export all
    with a.expect_download() as d: a.click('[data-expall]')
    wb = openpyxl.load_workbook(xl(d)); names = wb.sheetnames
    ok(names[:3] == ['Site visits', 'Clients', 'Plots'] and 'Payments' in names and 'Bookings' in names, 'Export all sheets: %s' % names)
    ok(wb['Site visits'].max_row - 1 == a.evaluate(E, "D.visits.length") and wb['Plots'].max_row - 1 == 415 and wb['Clients'].max_row - 1 == a.evaluate(E, "D.clients.length"),
       'Export all has every visit, every client and all 415 plots')
    # --- delete a visit, a client folder, then restore
    nv = a.evaluate(E, "D.visits.length"); vid = a.evaluate(E, "D.visits.find(v => !v.client).id"); vname = a.evaluate(E, f"IDX.visits['{vid}'].name")
    a.evaluate(E, f"location.hash='#/visit/{vid}'"); a.wait_for_timeout(300); a.click('[data-del]'); a.wait_for_timeout(200); a.click('[data-dlgok]'); a.wait_for_timeout(1500)
    a.reload(); a.wait_for_selector('#nav a'); a.wait_for_timeout(300)
    ok(a.evaluate(E, "D.visits.length") == nv - 1 and not a.evaluate(E, f"!!IDX.visits['{vid}']"), 'visit deleted from the database')
    # client with bookings + payments
    cid = a.evaluate(E, "D.clients.find(c => clientStatus(c)[0] === 'Booked' && clientPayments(c.id).length && c.bookings.length).id")
    before = a.evaluate(E, f"(() => {{ const c = clientById['{cid}']; return {{b: c.bookings.length, p: clientPayments(c.id).length, nb: D.bookings.length, np: D.payments.length, nc: D.clients.length, owned: Object.keys(D.plotOwners).filter(k => D.plotOwners[k] === c.id)}}; }})()")
    a.evaluate(E, f"location.hash='#/client/{cid}'"); a.wait_for_timeout(300); a.click('[data-del]'); a.wait_for_timeout(200)
    ok('booking' in a.inner_text('.dlg'), 'delete dialog explains what else goes with the folder')
    a.click('[data-dlgok]'); a.wait_for_timeout(2000); a.reload(); a.wait_for_selector('#nav a'); a.wait_for_timeout(300)
    after = a.evaluate(E, "({nb: D.bookings.length, np: D.payments.length, nc: D.clients.length})")
    ok(after['nc'] == before['nc'] - 1 and after['nb'] == before['nb'] - before['b'] and after['np'] <= before['np'] - 1, 'client folder deleted with its bookings and payments %s → %s' % (before, after))
    ok(all(not a.evaluate(E, f"'{k}' in D.plotOwners") for k in before['owned']), 'plot ownership cleared')
    # deleted items page + restore both
    a.evaluate(E, "location.hash='#/trash'"); a.wait_for_timeout(1200)
    txt = a.inner_text('#view'); ok(vname in txt and 'Pratik' in txt, 'Deleted items lists what was deleted, by whom')
    for _ in range(2):
        a.click('[data-restore] >> nth=0'); a.wait_for_timeout(2500); a.wait_for_selector('#nav a'); a.evaluate(E, "location.hash='#/trash'"); a.wait_for_timeout(1200)
    a.reload(); a.wait_for_selector('#nav a'); a.wait_for_timeout(300)
    back = a.evaluate(E, f"({{nb: D.bookings.length, np: D.payments.length, nc: D.clients.length, nv: D.visits.length, owned: Object.keys(D.plotOwners).filter(k => D.plotOwners[k] === '{cid}')}})")
    ok(back['nc'] == before['nc'] and back['nb'] == before['nb'] and back['np'] == before['np'] and back['nv'] == nv and back['owned'] == before['owned'], 'restore brought everything back exactly: %s' % back)
    a.evaluate(E, "location.hash='#/trash'"); a.wait_for_timeout(1200)
    ok(a.inner_text('#view').count('Restored') >= 2, 'Deleted items shows both as Restored')
    # pencil-dialog delete of an expense
    ne = a.evaluate(E, "D.expenses.length"); a.evaluate(E, "location.hash='#/expenses'"); a.wait_for_timeout(400)
    a.click('tbody tr >> nth=0 >> .pen'); a.wait_for_timeout(200); a.click('[data-dlgdel]'); a.wait_for_timeout(200); a.click('[data-dlgok]'); a.wait_for_timeout(1500)
    a.reload(); a.wait_for_selector('#nav a'); ok(a.evaluate(E, "D.expenses.length") == ne - 1, 'expense row deleted from its edit dialog')
    # Admin (not Super admin) cannot delete — server check
    s_, serr = login(b, 'sahil', 'newpass99')
    r = s_.evaluate(E, """fetch('/api/ops',{method:'POST',headers:{'content-type':'application/json'},body:JSON.stringify({ops:[{op:'del',coll:'visits',id:D.visits[0].id,grp:'Gtest123'}]})}).then(r=>r.status)""")
    ok(r == 403, 'Admin cannot delete (server says %s)' % r)
    ok(s_.evaluate(E, "canExport()") is True, 'Admin can export')
    print('ERRORS', errs + serr)
