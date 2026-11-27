# Phones (27 Nov 2026): every list shows one card per row (title, status, labelled fields, empty fields hidden) with the
# column filters as a strip of chips; laptops keep the table. No "from folder" / "locked" tags anywhere (owner).
from playwright.sync_api import sync_playwright
U = 'http://localhost:8787/'; E = "s => __dbg(s)"
def ok(c, m): print(('PASS ' if c else 'FAIL ') + m)
with sync_playwright() as p:
    b = p.chromium.launch(executable_path='/usr/bin/google-chrome'); errs = []
    a = b.new_context(**p.devices['Pixel 7']).new_page(); a.on('pageerror', lambda x: errs.append(str(x)))
    a.goto(U); a.wait_for_selector('#loginForm'); a.fill('[name=username]', 'pratik'); a.fill('[name=password]', 'secret123'); a.click('#loginForm button'); a.wait_for_selector('#nav a', state='attached', timeout=20000)
    q = lambda js: a.evaluate(E, js)
    def go(h): q(f"location.hash='{h}'"); a.wait_for_timeout(350)
    cid = q("D.clients.find(c => clientStatus(c)[0] === 'Booked' && clientPayments(c.id).length > 1).id")
    tags = []
    for h in ['#/visits', '#/clients', '#/plots', f'#/client/{cid}', '#/landowners', '#/expenses']:
        go(h)
        if 'from folder' in a.inner_text('#view') or q("!!document.querySelector('#view .lock')"): tags.append(h)
    ok(not tags, 'no "from folder" / "locked" tags on any page %s' % (tags or ''))
    go('#/visits'); card = "document.querySelector('.tablecard tbody tr')"
    ok(q(f"getComputedStyle({card}).display") == 'grid' and q(f"getComputedStyle({card}).borderRadius") == '16px', 'phone: each visit is a card')
    ok(q(f"{card}.querySelector('td.c-ttl').innerText.trim()") == q("TABLES.visits.shown[0].name") and q(f"parseFloat(getComputedStyle({card}.querySelector('td.c-ttl')).fontSize)") >= 17, 'card title is the visitor name, in large type')
    ok(q(f"getComputedStyle({card}.querySelector('td[data-l=Phone]'), '::before').content") == '"Phone"', 'each field has its label above the value')
    ok(q("[...document.querySelectorAll('.tablecard tbody td.blank')].every(td => getComputedStyle(td).display === 'none')") and q("document.querySelectorAll('.tablecard tbody td.blank').length") > 0, 'empty fields are hidden in the card')
    ok(q("getComputedStyle(document.querySelector('.tablecard thead tr')).display") == 'flex' and a.is_visible('.tablecard thead .fbtn'), 'filters: a strip of chips above the cards')
    a.click('.tablecard thead th:has-text("Status") .fbtn'); a.wait_for_timeout(250); ok(q("!!document.querySelector('#popBox').innerText.trim()"), 'tapping a chip opens the sort / filter box'); a.keyboard.press('Escape'); a.mouse.click(5, 300); a.wait_for_timeout(200)
    a.click('.tablecard tbody tr >> nth=0'); a.wait_for_timeout(400); ok(q("location.hash").startswith('#/visit/'), 'tapping a card opens the visit')
    go(f'#/client/{cid}')
    ok(q("[...document.querySelectorAll('.tablecard tbody tr')].pop().querySelector('td.c-amt') !== null") and q("getComputedStyle(document.querySelector('.tablecard tfoot tr')).display") == 'flex', 'payments: amount in bold, total as its own card')
    ok(q("document.documentElement.scrollWidth <= document.documentElement.clientWidth + 1"), 'nothing wider than the phone screen')
    a.set_viewport_size({'width': 1366, 'height': 800}); go('#/visits')
    ok(q("getComputedStyle(document.querySelector('.tablecard tbody tr')).display") == 'table-row', 'laptop: still a normal table')
    print('ERRORS', errs); ok(not errs, 'no page errors')
