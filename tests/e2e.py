import json
from playwright.sync_api import sync_playwright
U='http://localhost:8787/'
errs=[]
def ctx(b):
    c=b.new_context(viewport={'width':1300,'height':900}); pg=c.new_page()
    pg.on('pageerror',lambda x:errs.append('pageerror '+str(x)))
    pg.on('console',lambda m: errs.append('console '+m.text) if m.type=='error' else None)
    return c,pg
def ok(cond,msg): print(('PASS ' if cond else 'FAIL ')+msg)
with sync_playwright() as p:
    b=p.chromium.launch(executable_path='/usr/bin/google-chrome')
    c1,a=ctx(b)
    a.goto(U); a.wait_for_selector('#loginForm')
    ok('First-time setup' in a.inner_text('#login'), 'setup screen shown on empty user table')
    a.fill('[name=name]','Pratik'); a.fill('[name=username]','pratik'); a.fill('[name=password]','secret123'); a.click('#loginForm button')
    a.wait_for_selector('#nav a', timeout=20000); a.wait_for_timeout(500)
    ok('Pratik' in a.inner_text('#who') and 'Super admin' in a.inner_text('#who'), 'signed in as Super admin')
    n=a.evaluate("s => __dbg(s)", "[D.visits.length, D.clients.length, Object.keys(D.plots).length]"); ok(n==[728,133,415], 'all data loaded from database: %s' % n)
    # visit all pages
    for h in ['#/visits','#/clients','#/plots','#/landowners','#/partner','#/contractors','#/expenses','#/incentives','#/history','#/check','#/users']:
        a.evaluate("s => __dbg(s)", f"location.hash='{h}'"); a.wait_for_timeout(350)
    a.evaluate("s => __dbg(s)", "location.hash='#/contractor/'+encodeURIComponent(D.contractors[0].name)") if False else None
    # edit a visit name with the pencil
    a.evaluate("s => __dbg(s)", "location.hash='#/visits'"); a.wait_for_timeout(400)
    vid=a.evaluate("s => __dbg(s)", "document.querySelectorAll('tbody tr')[3].dataset.go.split('/')[2]"); old=a.evaluate("s => __dbg(s)", "IDX.visits['%s'].name"%vid)
    a.click('tbody tr >> nth=3 >> .pen'); a.wait_for_timeout(200)
    a.fill('#dlg_f1','Edited By Test'); a.click('[data-dlgok]'); a.wait_for_timeout(800)
    a.reload(); a.wait_for_selector('#nav a'); a.wait_for_timeout(300)
    ok(a.evaluate("s => __dbg(s)", f"IDX.visits['{vid}'].name")=='Edited By Test', 'pencil edit saved in database and survives reload')
    print(a.evaluate("s => __dbg(s)", "JSON.stringify(store.edits)"));ok(a.evaluate("s => __dbg(s)", "store.edits.length")==1 and a.evaluate("s => __dbg(s)", "store.edits[0].user")=='Pratik', 'edit history records who made the change')
    # follow-up edit keeps followups in sync
    a.evaluate("s => __dbg(s)", f"location.hash='#/visit/{vid}'"); a.wait_for_timeout(300)
    # add users
    a.evaluate("s => __dbg(s)", "location.hash='#/users'"); a.wait_for_timeout(600)
    for nm,un,role in [('Lakshit','lakshit','Agent'),('Sahil Bhai','sahil','Admin')]:
        a.click('[data-uadd]'); a.fill('#u_name',nm); a.fill('#u_user',un); a.select_option('#u_role',role); a.fill('#u_pass','pass1234'); a.click('[data-dlgok]'); a.wait_for_timeout(700)
    ok(a.evaluate("s => __dbg(s)", "USERS && USERS.length")==3, 'Super admin added an Agent and an Admin')
    # agent session
    c2,g=ctx(b)
    g.goto(U); g.wait_for_selector('#loginForm'); g.fill('[name=username]','lakshit'); g.fill('[name=password]','wrong'); g.click('#loginForm button'); g.wait_for_timeout(1200)
    ok('Wrong username or password' in g.inner_text('#loginErr'), 'wrong password is refused')
    g.fill('[name=password]','pass1234'); g.click('#loginForm button'); g.wait_for_selector('#nav a', timeout=20000); g.wait_for_timeout(300)
    ok('Users' not in g.inner_text('#nav'), 'Agent does not see the Users page')
    ok(g.evaluate("s => __dbg(s)", "D.visits.find(v=>v.id==='%s').name"%vid)=='Edited By Test', 'Agent sees the change made by Super admin')
    conv=g.evaluate("s => __dbg(s)", "D.visits.find(v=>isConvertedVisit(v)).id")
    r=g.evaluate("s => __dbg(s)", """fetch('/api/ops',{method:'POST',headers:{'content-type':'application/json'},body:JSON.stringify({ops:[{op:'patch',coll:'visits',id:'%s',field:'status',value:'Follow up'}]})}).then(r=>r.status)"""%conv)
    ok(r==403, 'server blocks an Agent changing a Converted visit (status %s)'%r)
    r=g.evaluate("s => __dbg(s)", "fetch('/api/users').then(r=>r.status)"); ok(r==403, 'server blocks an Agent from the users list')
    r=g.evaluate("s => __dbg(s)", """fetch('/api/users',{method:'POST',headers:{'content-type':'application/json'},body:JSON.stringify({name:'x',username:'hacker',role:'Super admin',password:'123456'})}).then(r=>r.status)"""); ok(r==403, 'Agent cannot create users')
    # agent registers a visit with a hold
    g.evaluate("s => __dbg(s)", "location.hash='#/visits'"); g.wait_for_timeout(300)
    g.click('[data-addvisit]'); g.fill('#nv_name','Agent Walkin'); g.fill('#nv_phone','9111122222'); g.click('.chips[data-group=agents] .chip >> nth=0'); g.click('[data-chip=Hold]')
    plot=g.evaluate("s => __dbg(s)", "freePlots()[0].no"); g.select_option('#nv_plot',plot); g.click('[data-dlgok]'); g.wait_for_timeout(1500)
    cid=g.evaluate("s => __dbg(s)", "location.hash.split('/')[2]")
    ok(cid.startswith('CN'), 'Agent visit+hold created client folder '+cid)
    # admin sees banner then reloads
    a.evaluate("s => __dbg(s)", "checkVersion()"); a.wait_for_timeout(800)
    ok('Someone else has made changes' in a.inner_text('#banner'), 'other screens get a "refresh" notice')
    a.reload(); a.wait_for_selector('#nav a'); a.wait_for_timeout(300)
    ok(a.evaluate("s => __dbg(s)", f"!!clientById['{cid}']") and a.evaluate("s => __dbg(s)", f"D.plots['{plot}'].status")=='HOLD', 'Admin sees the new client and plot on hold after refresh')
    srs=a.evaluate("s => __dbg(s)", f"[clientById['{cid}'].sr, D.visits.find(v=>v.name==='Agent Walkin').sr, D.payments.find(p=>p.clients.includes('{cid}')).sr]")
    ok(srs[0]==134 and srs[1]==729 and srs[2]==253, 'server gave the next Sr. numbers %s'%srs)
    # admin books, adds payment
    a.evaluate("s => __dbg(s)", f"location.hash='#/client/{cid}'"); a.wait_for_timeout(400)
    a.click('[data-flow=book]'); a.fill('#fb_final','1500000'); a.fill('#fb_amt','250000'); a.click('[data-dlgok]'); a.wait_for_timeout(1200)
    a.click('[data-flow=pay]'); a.fill('#fp_amt','100000'); a.fill('#fp_note','2nd instalment'); a.click('[data-dlgok]'); a.wait_for_timeout(1200)
    a.reload(); a.wait_for_selector('#nav a'); a.wait_for_timeout(300)
    st=a.evaluate("s => __dbg(s)", f"[clientStatus(clientById['{cid}'])[0], clientFinal(clientById['{cid}']), paidOf(clientPayments('{cid}')), D.plots['{plot}'].status, D.plotOwners['{plot}'], clientById['{cid}'].docStatus]")
    ok(st==['Booked',1500000,351100,'SOLD OUT',cid,'MOU not done'], 'booking and payment saved: %s'%st)
    vconv=a.evaluate("s => __dbg(s)", "vStatus(D.visits.find(v=>v.name==='Agent Walkin'))[0]"); ok(vconv=='Converted','visit became Converted after booking')
    # agent now cannot change that visit
    r=g.evaluate("s => __dbg(s)", """fetch('/api/ops',{method:'POST',headers:{'content-type':'application/json'},body:JSON.stringify({ops:[{op:'patch',coll:'visits',id:'%s',field:'status',value:'Lapsed'}]})}).then(r=>r.status)"""%a.evaluate("s => __dbg(s)", "D.visits.find(v=>v.name==='Agent Walkin').id"))
    ok(r==403,'Agent blocked from changing the newly Converted visit')
    # hold + lapse
    a.click('[data-flow=hold]'); p2=a.evaluate("s => __dbg(s)", "freePlots()[0].no"); a.select_option('#fh_plot',p2); a.click('[data-dlgok]'); a.wait_for_timeout(1200)
    a.click(f'[data-csel="{p2}"]'); a.wait_for_timeout(200); a.click('[data-flow=lapse]'); a.click('[data-chip=yes]'); a.click('[data-dlgok]'); a.wait_for_timeout(1200)
    a.reload(); a.wait_for_selector('#nav a'); a.wait_for_timeout(300)
    ok(a.evaluate("s => __dbg(s)", f"D.plots['{p2}'].status")=='UNSOLD' and a.evaluate("s => __dbg(s)", f"D.bookings.find(b=>b.plot==='{p2}' && b.cid==='{cid}').refunded")=='Refunded', 'hold lapse saved and plot back to Unsold')
    # undo
    a.evaluate("s => __dbg(s)", "location.hash='#/history'"); a.wait_for_timeout(400)
    ok(a.evaluate("s => __dbg(s)", "store.flows.length")>=5, 'steps list has %d entries'%a.evaluate("s => __dbg(s)", "store.flows.length"))
    a.click('[data-undo]'); a.wait_for_timeout(900); a.reload(); a.wait_for_selector('#nav a'); a.wait_for_timeout(300)
    ok(a.evaluate("s => __dbg(s)", f"IDX.visits['{vid}'].name")==old, 'undo restored the old value in the database')
    # expense
    a.evaluate("s => __dbg(s)", "location.hash='#/expenses'"); a.wait_for_timeout(300)
    a.click('[data-add=expense]'); a.wait_for_timeout(200); a.fill('#ne_part','Cement 50 bags'); a.fill('#ne_amt','18500'); a.click('[data-save=expense]'); a.wait_for_timeout(1200)
    a.reload(); a.wait_for_selector('#nav a'); a.wait_for_timeout(300)
    ok(a.evaluate("s => __dbg(s)", "!!D.expenses.find(e=>e.particulars==='Cement 50 bags' && e.sr===213)"), 'new expense saved with Sr. 213')
    # switch off agent → kicked out
    a.evaluate("s => __dbg(s)", "location.hash='#/users'"); a.wait_for_timeout(700)
    uid=a.evaluate("s => __dbg(s)", "USERS.find(u=>u.username==='lakshit').id"); a.click(f'[data-uedit="{uid}"]'); a.select_option('#u_active','0'); a.click('[data-dlgok]'); a.wait_for_timeout(800)
    g.reload(); g.wait_for_timeout(1500); ok(g.is_visible('#loginForm'), 'switched-off user is signed out')
    g.fill('[name=username]','lakshit'); g.fill('[name=password]','pass1234'); g.click('#loginForm button'); g.wait_for_timeout(1200)
    ok('switched off' in g.inner_text('#loginErr'), 'switched-off user cannot sign in')
    # admin cannot create super admin
    c3,s=ctx(b); s.goto(U); s.wait_for_selector('#loginForm'); s.fill('[name=username]','sahil'); s.fill('[name=password]','pass1234'); s.click('#loginForm button'); s.wait_for_selector('#nav a', timeout=20000)
    r=s.evaluate("s => __dbg(s)", """fetch('/api/users',{method:'POST',headers:{'content-type':'application/json'},body:JSON.stringify({name:'x',username:'xsa',role:'Super admin',password:'123456'})}).then(r=>r.status)"""); ok(r==403,'Admin cannot create a Super admin')
    # change password
    s.click('[data-mypass]'); s.fill('#p_cur','pass1234'); s.fill('#p_new','newpass99'); s.click('[data-dlgok]'); s.wait_for_timeout(1000)
    s.click('[data-logout]'); s.wait_for_selector('#loginForm'); s.fill('[name=username]','sahil'); s.fill('[name=password]','newpass99'); s.click('#loginForm button'); s.wait_for_selector('#nav a', timeout=20000)
    ok(True,'password change and sign out / sign in work')
    # cross-site request blocked
    r=s.evaluate("s => __dbg(s)", """fetch('/api/ops',{method:'POST',headers:{'content-type':'text/plain'},body:'{}'}).then(r=>r.status)"""); ok(r==415,'non-JSON posts are refused')
    # all pages again for errors
    for h in ['#/visits','#/clients','#/plots','#/landowners','#/partner','#/contractors','#/expenses','#/incentives','#/history','#/check','#/users',f'#/client/{cid}',f'#/plot/{plot}']:
        a.evaluate("s => __dbg(s)", f"location.hash='{h}'"); a.wait_for_timeout(300)
    a.evaluate("s => __dbg(s)", "location.hash='#/contractor/'+encodeURIComponent(D.contractors[0].name)"); a.wait_for_timeout(300)
    ok(a.evaluate("s => __dbg(s)", "D.contractors[0].expenses.length")>0,'contractor expenses still linked')
    a.screenshot(path='/tmp/real1.png')
    print('ERRORS', [e for e in errs if 'status of 40' not in e])
