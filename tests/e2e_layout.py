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
    for w, h in [(1366, 800), (1024, 768), (768, 1024), (390, 844), (320, 640), (280, 653)]:
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
    a.evaluate(E, "location.hash='#/clients'"); a.wait_for_timeout(250)
    heads = a.evaluate("[...document.querySelectorAll('thead th')].map(t => t.innerText.trim().toLowerCase())")
    ok('last hold date' not in heads and 'hold amount' not in heads, 'Clients list has no Last hold date / Hold amount columns: %s' % heads)
    # phones (27 Nov 2026): compact sticky menu, the open page's tab in view, forms open as a bottom sheet with 16px boxes
    a.set_viewport_size({'width': 360, 'height': 740}); a.evaluate(E, "location.hash='#/expenses'"); a.wait_for_timeout(300)
    ok(not a.is_visible('.proto'), 'phone: the long help line under the search box is hidden')
    ok(a.evaluate("(() => { const n = document.querySelector('#nav'), r = n.getBoundingClientRect(), t = n.querySelector('a.on').getBoundingClientRect(); return t.left >= r.left - 1 && t.right <= r.right + 1; })()"), 'phone: the open page (Site expenses) is in view in the menu strip')
    a.evaluate("window.scrollTo(0, 2000)"); a.wait_for_timeout(100)
    ok(a.evaluate("document.querySelector('aside').getBoundingClientRect().top") == 0, 'phone: the menu stays at the top while scrolling')
    a.evaluate(E, f"location.hash='#/client/{cid}'"); a.wait_for_timeout(300); a.click('[data-flow=pay]'); a.wait_for_timeout(400)
    ok(a.evaluate("(() => { const r = document.querySelector('.dlg').getBoundingClientRect(); return Math.round(r.bottom) === innerHeight && Math.round(r.width) === innerWidth; })()"), 'phone: a form opens as a full-width sheet from the bottom')
    ok(a.evaluate("[...document.querySelectorAll('.dlg input, .dlg select')].every(i => parseFloat(getComputedStyle(i).fontSize) >= 16)"), 'phone: form boxes are 16px so iPhones do not zoom in')
    ok(a.evaluate("(() => { const f = document.querySelector('.dlg .df').getBoundingClientRect(); return f.bottom <= innerHeight + 1 && f.top > 0; })()"), 'phone: Save / Cancel are always in reach')
    a.click('[data-dlgclose]')
    # modern forms: big ₹ amount box, payment mode as tap tiles that drive the saved mode and its proof boxes
    a.click('[data-flow=pay]'); a.wait_for_timeout(300)
    ok(a.evaluate("!!document.querySelector('.dlg .hero .money #fp_amt') && document.querySelectorAll('.dlg .money').length >= 1"), 'Add payment: big ₹ amount box on top')
    ok(a.evaluate("[...document.querySelectorAll('.dlg .modes [data-modetile]')].map(b => b.dataset.modetile)") == ['Cash', 'UPI / Online', 'Cheque', 'NEFT', 'RTGS', 'Other'] and a.evaluate("document.querySelector('.dlg .modes .on').dataset.modetile") == 'Cheque', 'Paid by: six mode tiles, Cheque picked')
    a.click('[data-modetile="UPI / Online"]'); a.wait_for_timeout(150)
    ok(a.evaluate("document.querySelector('#fp_mode').value") == 'UPI / Online' and a.is_visible('#fp_mode_payRef') and not a.is_visible('#fp_mode_payBank'), 'tapping UPI / Online picks it and shows its proof boxes only')
    a.click('[data-dlgclose]'); a.set_viewport_size({'width': 1366, 'height': 640}); a.click('[data-flow=pay]'); a.wait_for_timeout(300)
    ok(a.evaluate("document.querySelector('.dlg [data-dlgok]').getBoundingClientRect().bottom <= innerHeight"), 'laptop: Save stays visible in a long form')
    a.click('[data-dlgclose]')
    a.set_viewport_size({'width': 1366, 'height': 800}); a.evaluate(E, "location.hash='#/visits'"); a.wait_for_timeout(300)
    ok(a.is_visible('.proto') and a.evaluate("getComputedStyle(document.querySelector('aside')).height") == '800px', 'laptop: side menu and help line unchanged')
    print('ERRORS', errs)
