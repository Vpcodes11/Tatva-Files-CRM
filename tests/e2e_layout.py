# Layout on different screens: no page is wider than the screen, wide tables scroll inside their card,
# and on a 1366px laptop the main lists fit without sideways scrolling. Also: no yellow "edited" underline.
from playwright.sync_api import sync_playwright
U = 'http://localhost:8787/'; E = "s => __dbg(s)"
def ok(c, m): print(('PASS ' if c else 'FAIL ') + m)
with sync_playwright() as p:
    b = p.chromium.launch(executable_path='/usr/bin/google-chrome'); a = b.new_context(viewport={'width': 1366, 'height': 800}).new_page(); errs = []
    a.on('pageerror', lambda x: errs.append(str(x)))
    a.goto(U); a.wait_for_selector('#loginForm'); a.fill('[name=username]', 'pratik'); a.fill('[name=password]', 'secret123'); a.click('#loginForm button'); a.wait_for_selector('#nav a', timeout=20000)
    cid = a.evaluate(E, "D.clients.find(c => clientStatus(c)[0] === 'Booked').id"); vid = a.evaluate(E, "D.visits.find(v => v.client).id")
    pages = ['#/visits', '#/clients', '#/plots', '#/landowners', '#/expenses', '#/incentives', '#/users', '#/check', f'#/client/{cid}', f'#/visit/{vid}', '#/plot/61']
    for w, h in [(1366, 800), (1024, 768), (768, 1024), (390, 844)]:
        a.set_viewport_size({'width': w, 'height': h}); wide = []
        for pg in pages:
            a.evaluate(E, f"location.hash='{pg}'"); a.wait_for_timeout(250)
            if a.evaluate("document.documentElement.scrollWidth > document.documentElement.clientWidth + 1"): wide.append(pg)
            if a.evaluate("[...document.querySelectorAll('#view table')].some(t => !t.closest('.tscroll, .dpop'))"): wide.append(pg + ' (table not scrollable)')
        ok(not wide, '%dpx: every page fits the screen %s' % (w, wide or ''))
    a.set_viewport_size({'width': 1366, 'height': 800}); cut = []
    for pg in ['#/visits', '#/clients', '#/plots', '#/landowners']:
        a.evaluate(E, f"location.hash='{pg}'"); a.wait_for_timeout(250)
        if a.evaluate("[...document.querySelectorAll('.tscroll')].some(s => s.scrollWidth > s.clientWidth + 2)"): cut.append(pg)
    ok(not cut, '1366px laptop: main lists fit without sideways scrolling %s' % (cut or ''))
    a.evaluate(E, "location.hash='#/landowners'"); a.wait_for_timeout(250)
    ok(a.evaluate("document.querySelector('.tablecard').getBoundingClientRect().width > document.querySelector('#view').getBoundingClientRect().width - 20"), 'Sold plots table uses the full width')
    a.evaluate(E, f"location.hash='#/visit/{vid}'"); a.wait_for_timeout(250)
    ok(a.evaluate("[...document.querySelectorAll('.ed')].every(e => getComputedStyle(e).boxShadow === 'none')"), 'no yellow underline on edited fields')
    ok('in this browser' not in a.inner_text('#view'), 'no leftover "added in this browser" wording')
    print('ERRORS', errs)
