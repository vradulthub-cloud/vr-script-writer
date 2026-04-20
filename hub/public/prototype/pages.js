/* All hub pages as string-returning functions */
window.PAGES = {};

/* ═══════════════════════ HELPERS ═══════════════════════ */
const studios = [
  {k:'fpvr', name:'FuckPassVR', abbr:'FPVR', glyph:'F', c:'var(--fpvr)'},
  {k:'vrh',  name:'VRHush',     abbr:'VRH',  glyph:'V', c:'var(--vrh)'},
  {k:'vra',  name:'VRAllure',   abbr:'VRA',  glyph:'A', c:'var(--vra)'},
  {k:'njoi', name:'NaughtyJOI', abbr:'NJOI', glyph:'N', c:'var(--njoi)'}
];

function pageHead({eyebrow, title, sub, actions=''}) {
  return `
    <section class="page-head">
      <div>
        <div class="eyebrow"><span class="pip"></span><span>${eyebrow}</span></div>
        <h1 class="display t-display">${title}</h1>
        ${sub?`<div class="sub t-body">${sub}</div>`:''}
      </div>
      <div class="actions">${actions}</div>
    </section>`;
}

function monoBlock(s, label) {
  return `<div class="mono-block ${s.k}"><div class="m">${s.glyph}</div><div class="s">${label||s.abbr}</div></div>`;
}

/* ═══════════════════════ 01 DASHBOARD ═══════════════════════ */
PAGES.dashboard = () => `
  ${pageHead({
    eyebrow: 'SUN · APR 19 · 09:47 PDT · ANDREW',
    title: `Good morning, Andrew<span class="tick">.</span>`,
    sub: 'Four studios, four scenes due soon, nine approvals waiting.',
    actions: `<button class="btn ghost">Today</button><button class="btn primary">New Shoot</button>`
  })}

  <div class="stat-cluster">
    <div class="s"><div class="k">Scenes Live</div><div class="v t-display">1,154</div><div class="d">+24 this week · 38 missing assets</div></div>
    <div class="s"><div class="k">Shoots Active</div><div class="v t-display">7<span class="unit">/ 12</span></div><div class="d">4 due within 7d</div></div>
    <div class="s"><div class="k">Queue Depth</div><div class="v t-display">32</div><div class="d">9 approvals · 6 scripts · 17 tickets</div></div>
    <div class="s"><div class="k">Uptime · win-prod</div><div class="v t-display">99.84<span class="unit">%</span></div><div class="d">Last deploy 3d 06h ago</div></div>
  </div>

  <div style="margin-top:18px"></div>

  <div class="strip">
    <div class="cell" style="border-right:1px solid var(--ink)">
      <div class="label">Production Scope</div>
      <div style="font-family:var(--font-display);font-style:italic;font-size:20px;margin-top:4px;">Q2 · 2026</div>
    </div>
    ${studios.map(s=>`
      <div class="cell ${s.k}">
        <div class="mono">${s.abbr}</div>
        <div class="big">${({fpvr:412,vrh:307,vra:251,njoi:184})[s.k]}<sup>SCN</sup></div>
        <div class="bar" style="background:${s.c}"></div>
      </div>`).join('')}
    <div class="cell" style="align-items:flex-end">
      <div class="label" style="text-align:right">Total</div>
      <div style="font-family:var(--font-display);font-style:italic;font-size:34px;letter-spacing:-0.02em">1,154</div>
    </div>
  </div>

  <div class="cols">
    <div class="col">

      <section class="block">
        <header>
          <h2><span class="num">09</span>Approvals Queue</h2>
          <div class="act"><a href="#/approvals">Open all →</a></div>
        </header>

        <div class="seg" style="border:none;border-bottom:1px solid var(--ink)">
          <button aria-selected="true">Approvals <span class="c">9</span></button>
          <button>Missing <span class="c">8</span></button>
          <button>Scripts <span class="c">6</span></button>
          <button>Shoots <span class="c">3</span></button>
        </div>

        ${[
          {s:'fpvr',code:'FPV-2041',t:'Sunset Suite',n:'04 / Final trailer',who:'jess.k',age:'4h',hot:true},
          {s:'vrh', code:'VRH-1887',t:'Moonlit Balcony',n:'02 / Director cut',who:'marco.t',age:'11h'},
          {s:'vra', code:'VRA-1204',t:'Atrium 6',n:'07 / Color pass v3',who:'jess.k',age:'1d'},
          {s:'njoi',code:'NJO-0833',t:'Backlot 12',n:'01 / Title card',who:'rhea.d',age:'1d'},
          {s:'fpvr',code:'FPV-2039',t:'Loft Series',n:'11 / Compilation master',who:'marco.t',age:'2d'},
          {s:'vrh', code:'VRH-1882',t:'Greenhouse',n:'03 / Teaser',who:'jess.k',age:'3d'}
        ].map(r=>`
          <div class="row triage">
            <div class="tag" style="color:var(--${r.s})">${r.s.toUpperCase()[0]}</div>
            <div class="code">${r.code}</div>
            <div class="title"><em>${r.t}</em><span class="meta">— ${r.n} · ${r.who}</span></div>
            <span class="mono-chip ${r.s}">${r.s.toUpperCase()}</span>
            <span class="age" ${r.hot?'data-hot':''}>${r.age}</span>
            <button class="btn molten">Approve</button>
          </div>`).join('')}
      </section>

      <section class="block">
        <header>
          <h2><span class="num">05</span>This Week on Set</h2>
          <div class="act"><a href="#/shoots">Tracker →</a></div>
        </header>
        <div class="cal">
          <div class="cal-head">
            <div>Studio</div>
            <div><span class="dnum">19</span>SUN</div>
            <div><span class="dnum">20</span>MON</div>
            <div><span class="dnum">21</span>TUE</div>
            <div><span class="dnum">22</span>WED</div>
            <div><span class="dnum">23</span>THU</div>
            <div><span class="dnum">24</span>FRI</div>
            <div><span class="dnum">25</span>SAT</div>
          </div>
          ${[
            {k:'fpvr',name:'FuckPassVR',evs:[{a:14,b:36,t:'Sunset Suite · 04',m:'Pool Villa — 2 talent'}]},
            {k:'vrh',name:'VRHush',evs:[{a:28,b:50,t:'Greenhouse · 02',m:'Night exterior — 3 talent'}]},
            {k:'vra',name:'VRAllure',evs:[{a:57,b:86,t:'Atrium · 06',m:'Color pass + pickups'}]},
            {k:'njoi',name:'NaughtyJOI',evs:[{a:72,b:100,t:'Backlot 12 · 01',m:'Title card + Teaser'}]}
          ].map(l=>`
            <div class="lane">
              <div class="label"><div class="who">${l.name}</div><div>${l.k.toUpperCase()}</div></div>
              <div class="track">
                ${l.evs.map(e=>`<div class="ev ${l.k}" style="left:${e.a}%;right:${100-e.b}%"><div class="t">${e.t}</div><div class="m">${e.m}</div></div>`).join('')}
              </div>
            </div>`).join('')}
        </div>
      </section>

    </div>

    <!-- side rail -->
    <div class="col">
      <section class="block">
        <header>
          <h2><span class="num">03</span>Due Soon</h2>
          <div class="act"><a href="#/catalog">All →</a></div>
        </header>
        ${[
          {s:'vra',code:'VRA-1204',t:'Atrium 06',talent:'Rhea D. / Theo R.',days:2,done:14,total:18,missing:['thumb','script']},
          {s:'fpvr',code:'FPV-2039',t:'Loft Series 11',talent:'Jules F.',days:4,done:9,total:12,missing:['title','thumb','description']},
          {s:'njoi',code:'NJO-0833',t:'Backlot 12',talent:'Jules F. / Mia D.',days:6,done:6,total:10,missing:['script','thumb','title','description']},
          {s:'vrh',code:'VRH-1882',t:'Greenhouse 03',talent:'Nico P. / Theo R.',days:9,done:15,total:18,missing:['description']}
        ].map(x=>`
          <div style="display:grid;grid-template-columns:auto 1fr auto;gap:12px;padding:11px 14px;border-bottom:1px solid var(--rule-soft);align-items:start">
            <div style="min-width:44px;text-align:center">
              <div style="font-weight:800;font-size:20px;line-height:1;${x.days<=3?'color:var(--err)':''}">${x.days}d</div>
              <div style="font-size:9px;font-weight:700;letter-spacing:0.12em;text-transform:uppercase;color:var(--ink-muted);margin-top:2px">LEFT</div>
            </div>
            <div>
              <div style="display:flex;align-items:center;gap:6px">
                <span class="mono-chip ${x.s}">${x.s.toUpperCase()}</span>
                <span style="font-weight:700;font-size:13px">${x.t}</span>
              </div>
              <div style="font-size:11px;color:var(--ink-muted);margin-top:3px">${x.talent}</div>
              <div style="display:flex;gap:4px;margin-top:5px;flex-wrap:wrap">
                ${x.missing.map(m=>`<span style="font-size:9px;font-weight:700;letter-spacing:0.1em;text-transform:uppercase;padding:1px 5px;border:1px solid var(--err);color:var(--err)">${m}</span>`).join('')}
              </div>
            </div>
            <div style="text-align:right">
              <div style="font-weight:800;font-size:14px">${Math.round(x.done/x.total*100)}%</div>
              <div style="font-size:9px;font-weight:600;color:var(--ink-muted);margin-top:1px">${x.done}/${x.total}</div>
            </div>
          </div>`).join('')}
      </section>

      <section class="block inverted">
        <header>
          <h2><span class="num">04</span>Notifications</h2>
          <div class="act"><a href="#">Mark read</a></div>
        </header>
        ${[
          {u:1,m:'<em>jess.k</em> submitted Sunset Suite · 04',t:'4H'},
          {u:1,m:'MEGA sync finished · <em>1,244 files</em>',t:'6H'},
          {u:1,m:'<em>rhea.d</em> reopened TKT-0221',t:'11H'},
          {u:1,m:'Call sheet <em>Backlot 12 · 04/22</em> sent',t:'1D'},
          {u:0,m:'<em>marco.t</em> uploaded 3 new NJOI scenes',t:'1D'},
          {u:0,m:'Director voice model retrained · WER 4.2%',t:'2D'}
        ].map(n=>`
          <div class="notif-row" ${n.u?'data-unread':''}>
            <span class="dot"></span>
            <div class="msg">${n.m}</div>
            <span class="when">${n.t}</span>
          </div>`).join('')}
      </section>

      <section class="block">
        <header><h2><span class="num">06</span>Sync Status</h2><div class="act">6H</div></header>
        <ul class="list">
          <li style="grid-template-columns:10px 1fr auto"><span style="width:6px;height:6px;background:var(--ok)"></span><span>Google Sheets</span><span class="age">24,812 ROWS</span></li>
          <li style="grid-template-columns:10px 1fr auto"><span style="width:6px;height:6px;background:var(--ok)"></span><span>MEGA · Grail</span><span class="age">1,244 FILES</span></li>
          <li style="grid-template-columns:10px 1fr auto"><span style="width:6px;height:6px;background:var(--warn)"></span><span>Platform stats</span><span class="age">RETRY 8M</span></li>
          <li style="grid-template-columns:10px 1fr auto"><span style="width:6px;height:6px;background:var(--ok)"></span><span>Ollama · win-prod</span><span class="age">38MS</span></li>
          <li style="grid-template-columns:10px 1fr auto"><span style="width:6px;height:6px;background:var(--ok)"></span><span>Pixoo calendar</span><span class="age">OK</span></li>
        </ul>
      </section>
    </div>
  </div>
`;

/* ═══════════════════════ MISSING (QA + MEGA) ═══════════════════════ */
PAGES.missing = () => `
  ${pageHead({
    eyebrow:'QA · 38 MISSING ASSETS · 4 STUDIOS',
    title:`Missing Assets`,
    sub:'Track scene assets against the Grail sheet. Sync with MEGA.',
    actions:`<button class="btn ghost">Sync MEGA</button><button class="btn ghost">Export</button><button class="btn primary">Create Folder</button>`
  })}

  <div class="stat-cluster">
    <div class="s"><div class="k">Total Missing</div><div class="v">38</div><div class="d">Across 4 studios</div></div>
    <div class="s"><div class="k">No Thumbnail</div><div class="v">9</div><div class="d">Blocking publish</div></div>
    <div class="s"><div class="k">No Script</div><div class="v">17</div><div class="d">6 due within 7d</div></div>
    <div class="s"><div class="k">No Title Card</div><div class="v">12</div><div class="d">3 past release date</div></div>
  </div>

  <div class="filters" style="margin-bottom:14px">
    <span class="chip" data-on>ALL <span class="c">38</span></span>
    <span class="chip">FPVR <span class="c">14</span></span>
    <span class="chip">VRH <span class="c">9</span></span>
    <span class="chip">VRA <span class="c">11</span></span>
    <span class="chip">NJOI <span class="c">4</span></span>
    <span style="flex:1"></span>
    <span class="chip">No Thumb</span>
    <span class="chip">No Script</span>
    <span class="chip">No Title</span>
    <span class="chip">No Description</span>
  </div>

  <section class="block">
    <header><h2>Missing Assets by Scene</h2><div class="act"><a>Release date ↓</a></div></header>
    <table class="ctab">
      <thead><tr><th>Studio</th><th>Scene</th><th>Release</th><th>Thumb</th><th>Script</th><th>Title</th><th>Desc</th><th>MEGA</th><th>Status</th><th></th></tr></thead>
      <tbody>
        ${[
          ['fpvr','Sunset Suite · 04','Apr 21','✓','✓','—','—','✓',2],
          ['fpvr','Loft Series · 11','Apr 23','—','—','—','✓','✓',1],
          ['fpvr','Pool Villa · 08','Apr 28','—','—','—','—','✓',0],
          ['vrh','Moonlit Balcony · 02','Apr 22','✓','—','✓','—','✓',2],
          ['vrh','Greenhouse · 03','Apr 25','—','—','✓','✓','—',2],
          ['vra','Atrium · 06','Apr 21','—','—','—','—','✓',0],
          ['vra','Boardwalk · 01','Apr 30','✓','—','—','—','—',1],
          ['njoi','Backlot 12 · 01','Apr 24','✓','—','—','—','✓',2],
          ['fpvr','Harbor · 05','May 02','—','✓','—','—','✓',2],
          ['vrh','Forest Cabin · 02','May 05','✓','✓','—','—','—',2],
          ['vra','Desert Motel · 01','May 08','—','—','—','—','—',0],
          ['njoi','Rainy Alley · 07','May 12','✓','✓','✓','—','✓',3]
        ].map(r=>{
          const check = v => v === '✓' ? '<span style="color:var(--ok);font-weight:700">✓</span>' : '<span style="color:var(--err);font-weight:700">—</span>';
          const pct = Math.round(r[8]/4*100);
          return `
          <tr>
            <td><span class="mono-chip ${r[0]}">${r[0].toUpperCase()}</span></td>
            <td class="serif">${r[1]}</td>
            <td class="dim">${r[2]}</td>
            <td style="text-align:center">${check(r[3])}</td>
            <td style="text-align:center">${check(r[4])}</td>
            <td style="text-align:center">${check(r[5])}</td>
            <td style="text-align:center">${check(r[6])}</td>
            <td style="text-align:center">${check(r[7])}</td>
            <td><div class="bar" style="width:60px"><div class="seg-bar ${r[0]}" style="width:${pct}%"></div></div></td>
            <td><button class="btn ghost" style="padding:5px 10px;font-size:9px">Create</button></td>
          </tr>`;
        }).join('')}
      </tbody>
    </table>
  </section>

  <div class="cols" style="margin-top:20px">
    <section class="block">
      <header><h2>MEGA Sync Status</h2><div class="act">Last sync: 6h ago</div></header>
      <table class="ctab">
        <thead><tr><th>Studio</th><th>Folder</th><th>Files</th><th>Last Scan</th><th>Status</th></tr></thead>
        <tbody>
          ${[
            ['fpvr','Grail/FPVR',412,'6h ago','ok'],
            ['vrh','Grail/VRH',307,'6h ago','ok'],
            ['vra','Grail/VRA',251,'6h ago','warn'],
            ['njoi','Grail/NNJOI',184,'6h ago','ok']
          ].map(r=>`
            <tr>
              <td><span class="mono-chip ${r[0]}">${r[0].toUpperCase()}</span></td>
              <td style="font-family:var(--font-mono);font-size:11px">${r[1]}</td>
              <td>${r[2]}</td>
              <td class="dim">${r[3]}</td>
              <td><span class="pill" data-s="${r[4]}"><span class="d"></span>${r[4]==='ok'?'SYNCED':'RETRY'}</span></td>
            </tr>`).join('')}
        </tbody>
      </table>
    </section>

    <section class="block">
      <header><h2>Quick Create</h2></header>
      <div style="padding:16px;display:flex;flex-direction:column;gap:12px">
        <div style="font-size:12px;color:var(--ink-muted)">Create a MEGA folder structure for a new scene. Adds to Grail sheet automatically.</div>
        <div style="display:flex;gap:8px">
          <select style="flex:1;padding:7px 10px;border:1px solid var(--rule);background:var(--bone);font:inherit;font-size:12px">
            <option>FPVR</option><option>VRH</option><option>VRA</option><option>NJOI</option>
          </select>
          <input type="text" placeholder="Scene name" style="flex:2;padding:7px 10px;border:1px solid var(--rule);background:var(--bone);font:inherit;font-size:12px">
        </div>
        <button class="btn primary" style="align-self:flex-start">Create Folder</button>
      </div>
    </section>
  </div>
`;

/* ═══════════════════════ 02 SHOOT TRACKER ═══════════════════════ */
PAGES.shoots = () => `
  ${pageHead({
    eyebrow:'SCHEDULE · WEEK 17 · 12 SHOOTS',
    title:`Shoot Tracker`,
    sub:'7 in progress · 3 overdue · 2 wrapped this week',
    actions:`<button class="btn ghost">Week</button><button class="btn ghost">Month</button><button class="btn primary">+ Schedule</button>`
  })}

  <div class="filters" style="margin-bottom:12px">
    <span class="chip" data-on>ALL STUDIOS <span class="c">12</span></span>
    <span class="chip">FPVR <span class="c">3</span></span>
    <span class="chip">VRH <span class="c">4</span></span>
    <span class="chip">VRA <span class="c">3</span></span>
    <span class="chip">NJOI <span class="c">2</span></span>
    <span style="flex:1"></span>
    <span class="chip">In Progress</span>
    <span class="chip">Overdue</span>
    <span class="chip">Wrapped</span>
  </div>

  <section class="block">
    <header><h2><span class="num">04</span>Week 17 · Apr 19 → Apr 25</h2><div class="act"><a>‹ Prev</a><a>Next ›</a></div></header>
    <div class="cal">
      <div class="cal-head">
        <div>Studio / Talent</div>
        <div><span class="dnum">19</span>SUN</div>
        <div><span class="dnum">20</span>MON</div>
        <div><span class="dnum">21</span>TUE</div>
        <div><span class="dnum">22</span>WED</div>
        <div><span class="dnum">23</span>THU</div>
        <div><span class="dnum">24</span>FRI</div>
        <div><span class="dnum">25</span>SAT</div>
      </div>
      ${[
        {k:'fpvr',who:'Sunset Suite',talent:'Mia D. / Kai N.',evs:[{a:0,b:28,t:'Block + Light',m:'Villa exterior'},{a:30,b:60,t:'Principal',m:'Scenes 01–04'}]},
        {k:'fpvr',who:'Loft Series',talent:'Jules F.',evs:[{a:44,b:72,t:'Pickups',m:'Scene 11 reshoots'}]},
        {k:'vrh', who:'Greenhouse',talent:'Nico P. / Theo R.',evs:[{a:14,b:50,t:'Principal',m:'Night int.'},{a:62,b:84,t:'Titles',m:'Director voice ADR'}]},
        {k:'vrh', who:'Moonlit Balcony',talent:'Sasha L.',evs:[{a:72,b:100,t:'Wrap Review',m:'Final QC pass'}]},
        {k:'vra', who:'Atrium · 06',talent:'Rhea D. / Theo R.',evs:[{a:0,b:44,t:'Color + Pickups',m:'HDR pass'},{a:58,b:86,t:'Publish',m:'Upload + metadata'}]},
        {k:'vra', who:'Boardwalk',talent:'Ellie V.',evs:[{a:86,b:100,t:'Prep',m:'Wardrobe fitting'}]},
        {k:'njoi',who:'Backlot 12',talent:'Jules F. / Mia D.',evs:[{a:14,b:36,t:'Principal',m:'2 talent ensemble'},{a:58,b:72,t:'Title',m:'Card shoot'}]}
      ].map(l=>`
        <div class="lane">
          <div class="label"><div class="who">${l.who}</div><div>${l.k.toUpperCase()} · ${l.talent}</div></div>
          <div class="track">
            ${l.evs.map(e=>`<div class="ev ${l.k}" style="left:${e.a}%;right:${100-e.b}%"><div class="t">${e.t}</div><div class="m">${e.m}</div></div>`).join('')}
          </div>
        </div>`).join('')}
    </div>
  </section>

  <div style="margin-top:20px"></div>

  <div class="cols">
    <section class="block">
      <header><h2><span class="num">02</span>Active Shoots · Roster</h2></header>
      <table class="ctab">
        <thead><tr><th>Studio</th><th>Shoot</th><th>Talent</th><th>Day</th><th>Assets</th><th>Overdue</th><th class="num">Progress</th><th></th></tr></thead>
        <tbody>
          ${[
            ['fpvr','Sunset Suite','Mia D. / Kai N.','02 / 04','9 / 12','—',75,'ok'],
            ['fpvr','Loft Series · Pickups','Jules F.','01 / 01','3 / 4','—',75,'ok'],
            ['vrh','Greenhouse','Nico P. / Theo R.','03 / 05','11 / 18','—',61,'ok'],
            ['vrh','Moonlit Balcony','Sasha L.','—','16 / 18','6d','progress',89],
            ['vra','Atrium · 06','Rhea D. / Theo R.','04 / 05','14 / 18','6d','err',78],
            ['vra','Boardwalk · Prep','Ellie V.','PREP','0 / 8','—','ok',0],
            ['njoi','Backlot 12','Jules F. / Mia D.','01 / 02','2 / 10','—','ok',20]
          ].map((r,i)=>`
            <tr>
              <td><span class="mono-chip ${r[0]}">${r[0].toUpperCase()}</span></td>
              <td class="serif">${r[1]}</td>
              <td class="dim">${r[2]}</td>
              <td>${r[3]}</td>
              <td>${r[4]}</td>
              <td>${r[5]==='—'?'<span class="dim">—</span>':`<span class="age" data-hot>${r[5]}</span>`}</td>
              <td class="num" style="min-width:120px">
                <div style="display:flex;align-items:center;gap:8px;justify-content:flex-end">
                  <span>${r[7]||r[6]}%</span>
                  <div class="bar" style="width:80px"><div class="seg-bar ${r[0]}" style="width:${r[7]||r[6]}%"></div></div>
                </div>
              </td>
              <td><button class="btn ghost">Open</button></td>
            </tr>`).join('')}
        </tbody>
      </table>
    </section>
  </div>
`;

/* ═══════════════════════ 03 STUDIO CATALOG ═══════════════════════ */
PAGES.catalog = () => `
  ${pageHead({
    eyebrow:'1,154 SCENES · 4 STUDIOS · 38 MISSING',
    title:`Studio Catalog`,
    sub:'Browse and audit every scene across every studio.',
    actions:`<button class="btn ghost">Missing only</button><button class="btn ghost">Export CSV</button><button class="btn primary">+ Add Scene</button>`
  })}

  <div class="strip" style="grid-template-columns:repeat(4,1fr)">
    ${studios.map(s=>`
      <div class="cell ${s.k}" style="padding:16px;display:grid;grid-template-columns:auto 1fr;gap:14px;align-items:center">
        ${monoBlock(s)}
        <div>
          <div class="mono" style="color:${s.c}">${s.name}</div>
          <div class="big" style="color:${s.c}">${({fpvr:412,vrh:307,vra:251,njoi:184})[s.k]}<sup>SCN</sup></div>
          <div style="font-size:10px;letter-spacing:0.1em;color:var(--ink-muted);text-transform:uppercase;margin-top:4px">
            ${({fpvr:'14 missing',vrh:'9 missing',vra:'11 missing',njoi:'4 missing'})[s.k]} · <span style="color:${s.c}">${({fpvr:3,vrh:2,vra:3,njoi:1})[s.k]} new</span>
          </div>
        </div>
      </div>`).join('')}
  </div>

  <div class="filters" style="margin:18px 0 12px">
    <span class="chip" data-on>ALL <span class="c">1154</span></span>
    <span class="chip">MISSING <span class="c">38</span></span>
    <span class="chip">NO TITLE <span class="c">12</span></span>
    <span class="chip">NO SCRIPT <span class="c">17</span></span>
    <span class="chip">NO THUMB <span class="c">9</span></span>
    <span class="chip">PUBLISHED <span class="c">1116</span></span>
    <span style="flex:1"></span>
    <span class="chip">↓ Release date</span>
  </div>

  <div class="grid">
    ${Array.from({length:12}, (_,i)=>{
      const s = studios[i%4];
      const titles = ['Sunset Suite 04','Moonlit Balcony 02','Atrium 06','Backlot 12','Loft Series 11','Greenhouse 03','Pool Villa 08','Rooftop 09','Harbor 05','Forest Cabin 02','Desert Motel 01','Rainy Alley 07'];
      const dates = ['APR 18','APR 16','APR 15','APR 12','APR 11','APR 09','APR 06','APR 02','MAR 28','MAR 24','MAR 19','MAR 14'];
      const states = ['missing','published','published','missing','published','published','missing','published','published','published','missing','published'];
      const status = states[i];
      return `
      <div class="card">
        <div class="thumb">
          <span class="tag">${s.abbr}</span>
          <span class="tag">04:${String(12+i).padStart(2,'0')}</span>
        </div>
        <div class="ttl">${titles[i]}</div>
        <div class="meta">
          <span class="mono-chip ${s.k}">${s.abbr}</span>
          <span>${dates[i]}</span>
          ${status==='missing'?'<span class="pill" data-s="err"><span class="d"></span>MISSING</span>':'<span class="pill" data-s="ok"><span class="d"></span>LIVE</span>'}
        </div>
      </div>`;
    }).join('')}
  </div>
`;

/* ═══════════════════════ 04 MODEL RESEARCH ═══════════════════════ */
PAGES.research = () => `
  ${pageHead({
    eyebrow:'ROSTER · 127 MODELS · 8 IN REVIEW',
    title:`Model Research`,
    sub:'Roster performance, platform stats, and comp sets.',
    actions:`<button class="btn ghost">⌘F Search</button><button class="btn ghost">Import list</button><button class="btn primary">+ Add Model</button>`
  })}

  <div class="stat-cluster">
    <div class="s"><div class="k">Roster Size</div><div class="v">127</div><div class="d">+4 this month · 8 in review</div></div>
    <div class="s"><div class="k">Avg Scene Rate</div><div class="v">$1,850</div><div class="d">Top quartile · FPVR</div></div>
    <div class="s"><div class="k">Booked Days</div><div class="v">86<span class="unit">/ 90</span></div><div class="d">Next 90 day forecast</div></div>
    <div class="s"><div class="k">Platform Reach</div><div class="v">4.2<span class="unit">M</span></div><div class="d">Aggregate followers · 6 sources</div></div>
  </div>

  <div style="margin-top:18px"></div>

  <div class="cols">
    <section class="block">
      <header><h2><span class="num">07</span>Active Roster</h2><div class="act"><a>Rank ↓</a></div></header>
      <table class="ctab">
        <thead><tr><th>#</th><th>Model</th><th>Studio Fit</th><th class="num">Score</th><th class="num">Scenes</th><th class="num">Rate</th><th>Last Booked</th><th>Status</th></tr></thead>
        <tbody>
          ${[
            [1,'Mia D.','FPVR · VRH',94,24,1950,'Apr 14','ok'],
            [2,'Sasha L.','VRA · VRH',91,19,2100,'Apr 08','ok'],
            [3,'Jules F.','FPVR · NJOI',89,22,1800,'Apr 18','progress'],
            [4,'Rhea D.','VRA',86,16,1900,'Apr 15','ok'],
            [5,'Ellie V.','NJOI',82,12,1600,'Apr 01','warn'],
            [6,'Kai N.','FPVR',80,18,1750,'Apr 20','ok'],
            [7,'Theo R.','VRH · VRA',78,15,1650,'Apr 17','ok'],
            [8,'Nico P.','VRH',75,9,1500,'Apr 12','ok']
          ].map(r=>`
            <tr>
              <td class="dim">${String(r[0]).padStart(2,'0')}</td>
              <td class="serif">${r[1]}</td>
              <td class="dim">${r[2]}</td>
              <td class="num">${r[3]}</td>
              <td class="num">${r[4]}</td>
              <td class="num">$${r[5].toLocaleString()}</td>
              <td class="dim">${r[6]}</td>
              <td><span class="pill" data-s="${r[7]}"><span class="d"></span>${r[7]==='ok'?'ACTIVE':r[7]==='progress'?'ON SET':r[7]==='warn'?'QUIET':''}</span></td>
            </tr>`).join('')}
        </tbody>
      </table>
    </section>

    <div class="col">
      <section class="block inverted">
        <header><h2><span class="num">02</span>Spotlight</h2><div class="act">TOP RANKED</div></header>
        <div style="padding:22px 20px">
          <div class="thumb" style="aspect-ratio:4/5;background:repeating-linear-gradient(135deg, rgba(255,255,255,0.06) 0 6px, rgba(255,255,255,0.02) 6px 12px);border:1px solid var(--molten);padding:10px;display:flex;align-items:end;justify-content:space-between;margin-bottom:16px">
            <span style="font-size:9px;letter-spacing:0.18em;background:var(--molten);color:var(--molten-ink);padding:2px 6px">MODEL · MIA D.</span>
            <span style="font-size:9px;letter-spacing:0.18em;opacity:0.6">PORTRAIT · 04:3</span>
          </div>
          <div style="font-family:var(--font-display);font-style:italic;font-size:42px;line-height:0.9;letter-spacing:-0.03em">Mia <em>Drescher</em></div>
          <div style="font-size:10px;letter-spacing:0.18em;color:rgba(244,239,230,0.6);margin-top:10px;text-transform:uppercase">FPVR · VRH · 24 scenes · $1,950 avg</div>
          <div style="display:flex;gap:8px;margin-top:14px">
            <button class="btn molten" style="flex:1">Book</button>
            <button class="btn ghost" style="border-color:rgba(244,239,230,0.3);color:var(--bone);flex:1">Profile</button>
          </div>
        </div>
      </section>

      <section class="block">
        <header><h2><span class="num">03</span>Platform Reach</h2></header>
        <div style="padding:14px 16px;display:flex;flex-direction:column;gap:10px">
          ${[['Instagram',1420,72],['TikTok',1180,60],['X / Twitter',740,40],['OnlyFans',420,24],['Reddit',310,18],['YouTube',130,8]].map(p=>`
            <div style="display:grid;grid-template-columns:100px 1fr auto;gap:10px;align-items:center;font-size:11px">
              <span style="letter-spacing:0.12em;text-transform:uppercase;color:var(--ink-muted)">${p[0]}</span>
              <div class="bar"><div class="seg-bar ok" style="width:${p[2]}%"></div></div>
              <span style="font-variant-numeric:tabular-nums">${(p[1]/1000).toFixed(2)}M</span>
            </div>`).join('')}
        </div>
      </section>
    </div>
  </div>
`;

