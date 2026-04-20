/* Pages 05–12 — appended to window.PAGES */

/* ═══════════════════════ 05 SCRIPTS ═══════════════════════ */
PAGES.scripts = () => `
  ${pageHead({
    eyebrow:'WRITING ROOM · 6 QUEUED · 2 IN REVIEW',
    title:`Script Room`,
    sub:'Draft, generate, and revise shot-level narration.',
    actions:`<button class="btn ghost">Template</button><button class="btn ghost">Voice: Director</button><button class="btn primary">Generate</button>`
  })}

  <div class="split">
    <aside class="side">
      <header><span>Queue · 6</span><span style="font-family:var(--font-display);font-style:italic;font-size:20px">06</span></header>
      ${[
        {t:'Sunset Suite · 04',s:'fpvr',status:'DRAFT',w:'420 WORDS',cur:true},
        {t:'Moonlit Balcony · 02',s:'vrh',status:'REVIEW',w:'612 WORDS'},
        {t:'Atrium · 06',s:'vra',status:'REVIEW',w:'540 WORDS'},
        {t:'Backlot 12 · 01',s:'njoi',status:'QUEUED',w:'—'},
        {t:'Loft Series · 11',s:'fpvr',status:'DRAFT',w:'380 WORDS'},
        {t:'Greenhouse · 03',s:'vrh',status:'QUEUED',w:'—'}
      ].map(i=>`
        <div class="item" ${i.cur?'aria-current':''}>
          <div class="t">${i.t}</div>
          <div class="s">
            <span class="mono-chip ${i.s}">${i.s.toUpperCase()}</span>
            <span>${i.status}</span>
            <span style="margin-left:auto">${i.w}</span>
          </div>
        </div>`).join('')}
    </aside>

    <div class="main">
      <div class="editor-head">
        <div>
          <div style="font-size:9px;letter-spacing:0.22em;text-transform:uppercase;color:var(--ink-muted)">FPVR · SCENE 04 · DRAFT v3</div>
          <div style="font-family:var(--font-display);font-style:italic;font-size:36px;letter-spacing:-0.02em;margin-top:4px">Sunset <em>Suite</em> — Final Trailer</div>
        </div>
        <div style="display:flex;gap:8px">
          <button class="btn ghost">Preview</button>
          <button class="btn ghost">Voice TTS</button>
          <button class="btn primary">Save Draft</button>
          <button class="btn molten">Submit</button>
        </div>
      </div>

      <div class="editor-body">
        <div class="prose">
          <p><span class="speaker">INT · SUITE · GOLDEN HOUR</span>She doesn't know the camera is there. Not really. She knows it the way one knows a clock is in the room.</p>
          <p>The curtain moves — once — and the whole apartment turns the color of warm brass.</p>
          <p><span class="speaker">BEAT · 3S</span>He enters from the hallway. Neither of them speaks. They've been here before; they know the choreography.</p>
          <p><span class="speaker">CUT · BALCONY</span>The city is doing whatever the city does at this hour. It doesn't matter.</p>
          <p><span class="speaker">CLOSE · HANDS</span>A wrist. A clasp. The small negotiation of a borrowed watch.</p>
          <p><span class="speaker">WIDE · BED</span>Everything that follows is already implicit. The edit will take care of the rest.</p>
        </div>
        <div style="padding:16px 20px;border-top:1px solid var(--ink);background:var(--bone-2);display:flex;gap:16px;font-size:11px;letter-spacing:0.12em;text-transform:uppercase;color:var(--ink-muted)">
          <span>420 WORDS</span>
          <span>6 BEATS</span>
          <span>Est. Read · 2:40</span>
          <span style="margin-left:auto;color:var(--ink)">Auto-saved 14s ago</span>
        </div>
      </div>
    </div>
  </div>
`;

/* ═══════════════════════ 06 CALL SHEETS ═══════════════════════ */
PAGES.callsheets = () => callSheetPage();
PAGES['call-sheets'] = () => callSheetPage();
function callSheetPage(){ return `
  ${pageHead({
    eyebrow:'CALL SHEET · VRH · WED · APR 22',
    title:`Greenhouse — Day 03`,
    sub:'Night interior · 3 talent · 06:00 crew call',
    actions:`<button class="btn ghost">Duplicate</button><button class="btn ghost">Export PDF</button><button class="btn primary">Send Crew</button>`
  })}

  <div class="sheet-band">
    <div class="stamp">VRH · <span class="m">DAY 03</span> · APR·22</div>
    <div class="kv">
      <div><span class="k">Call</span><span class="v">06:00</span></div>
      <div><span class="k">Shoot</span><span class="v">07:30 → 19:00</span></div>
      <div><span class="k">Wrap</span><span class="v">20:30</span></div>
      <div><span class="k">Weather</span><span class="v">64°F · Clear</span></div>
      <div><span class="k">Sunset</span><span class="v">19:42</span></div>
    </div>
    <div style="font-family:var(--font-display);font-style:italic;font-size:44px;letter-spacing:-0.03em">12.5<span style="font-size:14px;font-family:var(--font-mono);font-style:normal;color:rgba(244,239,230,0.6);margin-left:6px">HRS</span></div>
  </div>

  <div class="cols">
    <div class="col">
      <section class="block">
        <header><h2><span class="num">01</span>Location</h2></header>
        <div style="padding:16px;display:grid;grid-template-columns:1fr 160px;gap:16px">
          <div>
            <div style="font-family:var(--font-display);font-style:italic;font-size:30px;letter-spacing:-0.02em">The <em>Glasshouse</em> Studio</div>
            <div style="font-size:11px;letter-spacing:0.08em;color:var(--ink-muted);margin-top:6px">2418 E. Pico Blvd · Los Angeles · 90021</div>
            <div style="margin-top:14px;font-size:11px;line-height:1.7">
              <div><span style="color:var(--ink-muted)">PARKING</span> &nbsp; Lot B · South entrance · Code #4401</div>
              <div><span style="color:var(--ink-muted)">HOLD AREA</span> &nbsp; Green Room · 2nd floor</div>
              <div><span style="color:var(--ink-muted)">CATERING</span> &nbsp; Full meal 12:30, craft all-day</div>
              <div><span style="color:var(--ink-muted)">MEDIC</span> &nbsp; On-call, 911 / CS standby</div>
            </div>
          </div>
          <div style="background:repeating-linear-gradient(135deg, var(--rule-soft) 0 8px, var(--bone-2) 8px 16px);border:1px solid var(--ink);position:relative">
            <div style="position:absolute;inset:0;display:flex;align-items:center;justify-content:center;font-family:var(--font-display);font-style:italic;font-size:30px;color:var(--molten)">MAP</div>
          </div>
        </div>
      </section>

      <section class="block">
        <header><h2><span class="num">02</span>Schedule</h2></header>
        <table class="ctab">
          <thead><tr><th>Time</th><th>Call</th><th>Scene</th><th>Who</th><th>Loc</th></tr></thead>
          <tbody>
            ${[
              ['06:00','Crew call','—','Director, DP, AC, Gaffer, Sound','Bay 1'],
              ['06:30','Talent call','—','Nico P. · Theo R. · Sasha L.','Green Rm'],
              ['07:30','Block + light','Scene 3A · Night ext.','All','Greenhouse'],
              ['10:30','Roll','3A — principal','Nico · Theo','Greenhouse'],
              ['12:30','Meal','—','—','Catering'],
              ['13:30','Roll','3B — balcony','Sasha · Theo','Upper level'],
              ['16:00','Roll','3C — wide master','All','Atrium'],
              ['18:30','Pickups','—','As needed','—'],
              ['19:00','Wrap','—','—','—']
            ].map(r=>`
              <tr>
                <td class="serif" style="font-size:20px">${r[0]}</td>
                <td class="dim">${r[1]}</td>
                <td>${r[2]}</td>
                <td class="dim">${r[3]}</td>
                <td>${r[4]}</td>
              </tr>`).join('')}
          </tbody>
        </table>
      </section>
    </div>

    <div class="col">
      <section class="block">
        <header><h2><span class="num">08</span>Talent</h2></header>
        ${['Nico P.','Theo R.','Sasha L.'].map((n,i)=>`
          <div style="display:grid;grid-template-columns:auto 1fr auto;gap:12px;padding:12px 14px;border-bottom:1px solid var(--rule-soft)">
            <div style="width:52px;height:52px;border:1px solid var(--ink);background:repeating-linear-gradient(45deg, var(--rule-soft) 0 4px, var(--bone-2) 4px 8px);display:flex;align-items:end;justify-content:start;padding:4px;font-size:8px;letter-spacing:0.1em;color:var(--ink-muted)">PHOTO</div>
            <div>
              <div style="font-family:var(--font-display);font-style:italic;font-size:22px;letter-spacing:-0.01em">${n}</div>
              <div style="font-size:10px;letter-spacing:0.1em;color:var(--ink-muted);text-transform:uppercase;margin-top:2px">Call ${['06:30','06:30','07:15'][i]} · Wardrobe ${['W1','W2','W3'][i]}</div>
            </div>
            <span class="pill" data-s="ok"><span class="d"></span>CONF</span>
          </div>`).join('')}
      </section>

      <section class="block">
        <header><h2><span class="num">05</span>Crew · 12</h2></header>
        <ul class="list">
          ${[['Director','Andrew N.'],['DP','Kei A.'],['AC','Sam O.'],['Gaffer','Mara J.'],['Sound','Vik R.'],['Script','Jess K.'],['PA','Tom L.'],['Medic','Carla S.']].map(c=>`
            <li style="grid-template-columns:90px 1fr auto;font-size:11px"><span style="color:var(--ink-muted);letter-spacing:0.1em;text-transform:uppercase">${c[0]}</span><span class="serif" style="font-size:16px">${c[1]}</span><span class="pill" data-s="ok"><span class="d"></span>CONF</span></li>`).join('')}
        </ul>
      </section>
    </div>
  </div>
`;}

/* ═══════════════════════ 07 TITLES ═══════════════════════ */
PAGES.titles = () => `
  ${pageHead({
    eyebrow:'TITLE CARDS · 12 AWAITING',
    title:`Title Cards`,
    sub:'Hero card, meta card, and platform copy for each scene.',
    actions:`<button class="btn ghost">Ollama: llama3</button><button class="btn primary">Generate 6 variants</button>`
  })}

  <div class="cols">
    <div class="col">
      <section class="block">
        <header><h2><span class="num">01</span>FPVR · Sunset Suite 04</h2><div class="act">v3 · 6 VARIANTS</div></header>
        <div style="padding:18px">
          ${[
            {h:'A Suite With A View',s:'The quiet choreography of a room at golden hour.',n:94,hot:true},
            {h:'Nothing Matters Below',s:'Late afternoon, a borrowed watch, a city going soft.',n:88},
            {h:'Golden Hour, Private',s:'The suite knows what is coming. The city does not.',n:82},
            {h:'The City Does Not Know',s:'An apartment full of hum and slow light.',n:79},
            {h:'Warm Brass, Warm Bodies',s:'A sunset-sized metaphor.',n:71},
            {h:'Suite No. 04',s:'Minimal copy · brand-forward.',n:64}
          ].map((t,i)=>`
            <div style="display:grid;grid-template-columns:44px 1fr auto auto;gap:14px;align-items:center;padding:14px 0;border-top:${i?'1px solid var(--rule-soft)':'none'}">
              <div style="font-family:var(--font-display);font-style:italic;font-size:34px;letter-spacing:-0.02em;color:${t.hot?'var(--molten)':'var(--ink-muted)'}">${String.fromCharCode(65+i)}</div>
              <div>
                <div style="font-family:var(--font-display);font-style:italic;font-size:30px;line-height:1.05;letter-spacing:-0.02em">${t.h}</div>
                <div style="font-size:11px;color:var(--ink-muted);letter-spacing:0.02em;margin-top:4px">${t.s}</div>
              </div>
              <div style="text-align:right">
                <div style="font-family:var(--font-display);font-style:italic;font-size:22px">${t.n}</div>
                <div style="font-size:9px;letter-spacing:0.16em;text-transform:uppercase;color:var(--ink-muted)">CTR score</div>
              </div>
              <button class="btn ${t.hot?'molten':'ghost'}">Pick</button>
            </div>`).join('')}
        </div>
      </section>
    </div>

    <div class="col">
      <section class="block inverted">
        <header><h2><span class="num">02</span>Hero Preview</h2><div class="act">16×9</div></header>
        <div style="padding:24px;display:flex;flex-direction:column;gap:16px">
          <div style="aspect-ratio:16/9;background:repeating-linear-gradient(135deg,rgba(255,255,255,0.06) 0 6px,rgba(255,255,255,0.02) 6px 12px);border:1px solid var(--molten);position:relative;padding:20px;display:flex;flex-direction:column;justify-content:space-between">
            <span style="font-size:10px;letter-spacing:0.2em;text-transform:uppercase;color:var(--molten)">FPVR · SCENE 04</span>
            <div>
              <div style="font-family:var(--font-display);font-style:italic;font-size:48px;line-height:0.95;letter-spacing:-0.03em;color:var(--bone)">A Suite<br>With A <em>View</em></div>
              <div style="font-size:11px;color:rgba(244,239,230,0.7);margin-top:10px;letter-spacing:0.04em">04:12 · MIA D. · KAI N. · 04/18/26</div>
            </div>
          </div>
          <div style="display:flex;gap:8px">
            <button class="btn ghost" style="border-color:rgba(244,239,230,0.3);color:var(--bone);flex:1">Export PNG</button>
            <button class="btn molten" style="flex:1">Publish</button>
          </div>
        </div>
      </section>

      <section class="block">
        <header><h2><span class="num">06</span>Platform Copy</h2></header>
        <div style="padding:14px 16px;display:flex;flex-direction:column;gap:12px;font-size:11px">
          <div><span style="font-size:9px;letter-spacing:0.18em;text-transform:uppercase;color:var(--ink-muted)">IG · 125c</span><div style="margin-top:4px">A Suite With A View. Golden hour, borrowed time. FPVR · 04/18</div></div>
          <div><span style="font-size:9px;letter-spacing:0.18em;text-transform:uppercase;color:var(--ink-muted)">X · 220c</span><div style="margin-top:4px">Late afternoon in a suite that already knows what happens next. A Suite With A View · streaming now on FPVR.</div></div>
          <div><span style="font-size:9px;letter-spacing:0.18em;text-transform:uppercase;color:var(--ink-muted)">Reddit · 80c</span><div style="margin-top:4px">A Suite With A View — quiet, slow, sunlit.</div></div>
        </div>
      </section>
    </div>
  </div>
`;

/* ═══════════════════════ 08 DESCRIPTIONS ═══════════════════════ */
PAGES.descriptions = () => `
  ${pageHead({
    eyebrow:'LONG-FORM · 17 AWAITING · 4 PUBLISHED TODAY',
    title:`Scene Descriptions`,
    sub:'Editorial-voice long copy for catalog + platforms.',
    actions:`<button class="btn ghost">Tone: Editorial</button><button class="btn ghost">Length: Standard</button><button class="btn primary">Draft</button>`
  })}

  <div class="split">
    <aside class="side">
      <header><span>Scenes · 17</span><span style="font-family:var(--font-display);font-style:italic;font-size:20px">17</span></header>
      ${[
        {t:'Sunset Suite · 04',s:'fpvr',w:'142w',cur:true},
        {t:'Moonlit Balcony · 02',s:'vrh',w:'168w'},
        {t:'Atrium · 06',s:'vra',w:'—'},
        {t:'Backlot 12 · 01',s:'njoi',w:'—'},
        {t:'Loft Series · 11',s:'fpvr',w:'134w'},
        {t:'Greenhouse · 03',s:'vrh',w:'180w'},
        {t:'Pool Villa · 08',s:'fpvr',w:'—'},
        {t:'Rooftop · 09',s:'njoi',w:'122w'}
      ].map(i=>`
        <div class="item" ${i.cur?'aria-current':''}>
          <div class="t">${i.t}</div>
          <div class="s">
            <span class="mono-chip ${i.s}">${i.s.toUpperCase()}</span>
            <span>${i.w}</span>
            <span style="margin-left:auto">${i.w==='—'?'PENDING':'DRAFT'}</span>
          </div>
        </div>`).join('')}
    </aside>

    <div class="main">
      <div class="editor-head">
        <div>
          <div style="font-size:9px;letter-spacing:0.22em;text-transform:uppercase;color:var(--ink-muted)">FPVR · SCENE 04 · DESCRIPTION</div>
          <div style="font-family:var(--font-display);font-style:italic;font-size:30px;margin-top:4px">Sunset <em>Suite</em></div>
        </div>
        <div style="display:flex;gap:8px">
          <button class="btn ghost">↶ Undo</button>
          <button class="btn ghost">Regen</button>
          <button class="btn primary">Save</button>
        </div>
      </div>
      <div class="editor-body" style="padding:28px 36px;display:grid;grid-template-columns:1fr 280px;gap:28px">
        <div class="prose" style="background:transparent;padding:0">
          <p>A suite on the eighteenth floor, a curtain that moves once, and an apartment full of brass light. Mia arrives the way someone arrives to a room they've lived in their whole life. Kai is already there; the choreography is already underway.</p>
          <p>Outside, the city does whatever the city does at this hour — it doesn't really come up. Inside, a borrowed watch is negotiated off a wrist, and a slow evening proceeds at the pace the suite itself seems to be setting.</p>
          <p>Scene four of the <em>Sunset Suite</em> series is shot almost entirely in practicals and bounced gold. The cut is patient, the wide stays wide, and the score arrives twenty seconds before you notice it has.</p>
        </div>
        <aside style="display:flex;flex-direction:column;gap:12px;font-size:11px">
          <div><div style="font-size:9px;letter-spacing:0.2em;text-transform:uppercase;color:var(--ink-muted)">WORDS</div><div style="font-family:var(--font-display);font-style:italic;font-size:32px">142</div></div>
          <div><div style="font-size:9px;letter-spacing:0.2em;text-transform:uppercase;color:var(--ink-muted)">FLESCH</div><div style="font-family:var(--font-display);font-style:italic;font-size:32px">68<span style="font-size:12px;font-family:var(--font-mono);font-style:normal;color:var(--ink-muted);margin-left:4px">READABLE</span></div></div>
          <div style="border-top:1px solid var(--rule);padding-top:12px">
            <div style="font-size:9px;letter-spacing:0.2em;text-transform:uppercase;color:var(--ink-muted);margin-bottom:8px">SIGNAL</div>
            <div style="display:flex;flex-direction:column;gap:6px">
              ${[['Tone · Editorial',86],['Brand fit',92],['Specificity',78],['Repetition',22]].map(x=>`
                <div style="display:grid;grid-template-columns:1fr 30px;gap:6px;align-items:center">
                  <div class="bar"><div class="seg-bar ok" style="width:${x[1]}%"></div></div>
                  <span style="text-align:right;font-variant-numeric:tabular-nums">${x[1]}</span>
                </div>
                <div style="font-size:9px;letter-spacing:0.14em;text-transform:uppercase;color:var(--ink-muted);margin-top:-4px">${x[0]}</div>`).join('')}
            </div>
          </div>
        </aside>
      </div>
    </div>
  </div>
`;

/* ═══════════════════════ 09 COMPILATIONS ═══════════════════════ */
PAGES.compilations = () => `
  ${pageHead({
    eyebrow:'COMP BUILDER · 3 ACTIVE · 1 RENDERING',
    title:`Compilation Builder`,
    sub:'Sequence scenes into thematic compilations.',
    actions:`<button class="btn ghost">Library</button><button class="btn ghost">Template</button><button class="btn primary">+ New Comp</button>`
  })}

  <div class="block" style="margin-bottom:18px">
    <header><h2><span class="num">01</span>Editing · <em style="font-family:var(--font-display);font-style:italic;font-size:20px">Golden Hour Anthology · FPVR</em></h2><div class="act"><a>Preview</a><a style="color:var(--molten)">RENDER 1080p</a></div></header>

    <div style="padding:18px;display:grid;grid-template-columns:auto 1fr;gap:24px;align-items:start">
      <div style="width:240px;aspect-ratio:16/9;border:1px solid var(--ink);background:repeating-linear-gradient(135deg,var(--rule-soft) 0 6px,var(--bone-2) 6px 12px);display:flex;align-items:end;justify-content:space-between;padding:8px;font-size:9px;letter-spacing:0.14em;color:var(--ink-muted);text-transform:uppercase">
        <span>HERO · 16×9</span><span>24:08</span>
      </div>

      <div>
        <div style="display:flex;gap:18px;margin-bottom:16px">
          <div><div style="font-size:9px;letter-spacing:0.2em;text-transform:uppercase;color:var(--ink-muted)">Scenes</div><div style="font-family:var(--font-display);font-style:italic;font-size:32px">6</div></div>
          <div><div style="font-size:9px;letter-spacing:0.2em;text-transform:uppercase;color:var(--ink-muted)">Runtime</div><div style="font-family:var(--font-display);font-style:italic;font-size:32px">24:08</div></div>
          <div><div style="font-size:9px;letter-spacing:0.2em;text-transform:uppercase;color:var(--ink-muted)">Size</div><div style="font-family:var(--font-display);font-style:italic;font-size:32px">3.4<span style="font-size:12px;font-family:var(--font-mono);font-style:normal;color:var(--ink-muted);margin-left:4px">GB</span></div></div>
          <div><div style="font-size:9px;letter-spacing:0.2em;text-transform:uppercase;color:var(--ink-muted)">Status</div><div style="margin-top:6px"><span class="pill" data-s="progress"><span class="d"></span>RENDERING 38%</span></div></div>
        </div>

        <!-- Film strip sequence -->
        <div style="display:grid;grid-template-columns:repeat(6,1fr);gap:8px">
          ${[
            {t:'Sunset Suite 04',d:'04:12'},
            {t:'Pool Villa 08',d:'03:44'},
            {t:'Rooftop 09',d:'04:50'},
            {t:'Loft Series 11',d:'04:06'},
            {t:'Harbor 05',d:'03:22'},
            {t:'Outtake · Suite 04',d:'03:54'}
          ].map((s,i)=>`
            <div style="border:1px solid var(--ink);padding:8px;background:var(--bone)">
              <div style="aspect-ratio:4/3;background:repeating-linear-gradient(135deg,var(--rule-soft) 0 4px,var(--bone-2) 4px 8px);border:1px solid var(--ink);display:flex;align-items:end;justify-content:space-between;padding:4px;font-size:8px;letter-spacing:0.1em;color:var(--ink-muted);text-transform:uppercase"><span>FPVR</span><span>${s.d}</span></div>
              <div style="font-family:var(--font-display);font-style:italic;font-size:15px;line-height:1.1;margin-top:8px;letter-spacing:-0.01em">${s.t}</div>
              <div style="font-size:9px;letter-spacing:0.14em;color:var(--ink-muted);text-transform:uppercase;margin-top:4px">TAKE ${String(i+1).padStart(2,'0')}</div>
            </div>`).join('')}
        </div>
      </div>
    </div>
  </div>

  <div class="cols">
    <section class="block">
      <header><h2><span class="num">07</span>All Compilations</h2></header>
      <table class="ctab">
        <thead><tr><th>Title</th><th>Studio</th><th>Scenes</th><th class="num">Runtime</th><th class="num">Views · 30d</th><th>Status</th><th></th></tr></thead>
        <tbody>
          ${[
            ['Golden Hour Anthology','fpvr',6,'24:08',124000,'progress','RENDERING'],
            ['Night Visitors · Vol 2','vrh',8,'32:14',88000,'ok','LIVE'],
            ['Atrium: A Cycle','vra',4,'18:22',62000,'ok','LIVE'],
            ['Slow Backlot','njoi',5,'21:10',0,'warn','DRAFT'],
            ['Best of Q1 2026','fpvr',12,'48:40',310000,'ok','LIVE']
          ].map(r=>`
            <tr>
              <td class="serif">${r[0]}</td>
              <td><span class="mono-chip ${r[1]}">${r[1].toUpperCase()}</span></td>
              <td>${r[2]}</td>
              <td class="num">${r[3]}</td>
              <td class="num">${r[4] ? (r[4]/1000).toFixed(0)+'K' : '<span class="dim">—</span>'}</td>
              <td><span class="pill" data-s="${r[5]}"><span class="d"></span>${r[6]}</span></td>
              <td><button class="btn ghost">Open</button></td>
            </tr>`).join('')}
        </tbody>
      </table>
    </section>
  </div>
`;

/* ═══════════════════════ 10 APPROVALS ═══════════════════════ */
PAGES.approvals = () => `
  ${pageHead({
    eyebrow:'QUEUE · 9 PENDING · 3 OLDER THAN 24H',
    title:`Approvals Queue`,
    sub:'Review, approve, or kick back assets submitted by editors.',
    actions:`<button class="btn ghost">Mine only</button><button class="btn ghost">Bulk</button><button class="btn primary">Approve All Visible</button>`
  })}

  <div class="seg" style="margin-bottom:14px">
    <button aria-selected="true">PENDING <span class="c">9</span></button>
    <button>CHANGES REQUESTED <span class="c">4</span></button>
    <button>RECENTLY APPROVED <span class="c">16</span></button>
    <button>REJECTED <span class="c">2</span></button>
  </div>

  <div class="cols">
    <div class="col">
    ${[
      {s:'fpvr',code:'FPV-2041',t:'Sunset Suite · 04',n:'Final trailer',who:'jess.k',age:'4h',hot:true},
      {s:'vrh', code:'VRH-1887',t:'Moonlit Balcony · 02',n:'Director cut',who:'marco.t',age:'11h'},
      {s:'vra', code:'VRA-1204',t:'Atrium · 06',n:'Color pass v3',who:'jess.k',age:'1d',hot:true},
      {s:'njoi',code:'NJO-0833',t:'Backlot 12 · 01',n:'Title card',who:'rhea.d',age:'1d'},
      {s:'fpvr',code:'FPV-2039',t:'Loft Series · 11',n:'Compilation master',who:'marco.t',age:'2d'},
      {s:'vrh', code:'VRH-1882',t:'Greenhouse · 03',n:'Teaser',who:'jess.k',age:'3d'}
    ].map(r=>`
      <section class="block" style="margin-bottom:14px">
        <div style="display:grid;grid-template-columns:220px 1fr;gap:0;min-height:160px">
          <div style="background:repeating-linear-gradient(135deg, var(--rule-soft) 0 6px, var(--bone-2) 6px 12px);border-right:1px solid var(--ink);display:flex;align-items:end;justify-content:space-between;padding:10px;font-size:9px;letter-spacing:0.14em;text-transform:uppercase;color:var(--ink-muted)">
            <span class="mono-chip ${r.s}">${r.s.toUpperCase()}</span>
            <span>${r.code}</span>
          </div>
          <div style="padding:16px 18px;display:flex;flex-direction:column;gap:10px">
            <div style="display:flex;align-items:baseline;gap:14px">
              <div style="font-family:var(--font-display);font-style:italic;font-size:38px;line-height:0.95;letter-spacing:-0.03em;flex:1"><em>${r.t}</em></div>
              <span class="age" ${r.hot?'data-hot':''}>${r.age.toUpperCase()} AGO</span>
            </div>
            <div style="font-size:11px;letter-spacing:0.08em;color:var(--ink-muted);text-transform:uppercase">${r.n} · SUBMITTED BY ${r.who}</div>
            <div style="display:flex;gap:16px;font-size:11px;color:var(--ink-muted)">
              <span><strong style="color:var(--ink)">6</strong> BEATS</span>
              <span><strong style="color:var(--ink)">04:12</strong> RUNTIME</span>
              <span><strong style="color:var(--ink)">3</strong> ASSETS</span>
              <span><strong style="color:var(--ink)">v3</strong> REVISION</span>
            </div>
            <div style="display:flex;gap:8px;margin-top:auto">
              <button class="btn ghost">Open</button>
              <button class="btn ghost">Comment</button>
              <span style="flex:1"></span>
              <button class="btn danger">Request Changes</button>
              <button class="btn molten">Approve</button>
            </div>
          </div>
        </div>
      </section>`).join('')}
    </div>

    <div class="col">
      <section class="block inverted">
        <header><h2><span class="num">03</span>Queue Health</h2></header>
        <div style="padding:18px;display:flex;flex-direction:column;gap:14px">
          <div><div style="font-size:10px;letter-spacing:0.22em;text-transform:uppercase;color:rgba(244,239,230,0.6)">AVG RESPONSE</div><div style="font-family:var(--font-display);font-style:italic;font-size:40px;letter-spacing:-0.02em">14h 22m</div></div>
          <div><div style="font-size:10px;letter-spacing:0.22em;text-transform:uppercase;color:rgba(244,239,230,0.6)">APPROVAL RATE · 7d</div><div style="font-family:var(--font-display);font-style:italic;font-size:40px;letter-spacing:-0.02em">83%</div></div>
          <div><div style="font-size:10px;letter-spacing:0.22em;text-transform:uppercase;color:rgba(244,239,230,0.6)">SUBMISSIONS · WEEK</div><div style="font-family:var(--font-display);font-style:italic;font-size:40px;letter-spacing:-0.02em">21</div></div>
        </div>
      </section>

      <section class="block">
        <header><h2><span class="num">04</span>Top Submitters</h2></header>
        <ul class="list">
          ${[['jess.k',9,84],['marco.t',7,91],['rhea.d',5,78],['andre.n',2,100]].map(s=>`
            <li style="grid-template-columns:1fr auto">
              <div>
                <div class="serif" style="font-size:18px">${s[0]}</div>
                <div style="font-size:10px;color:var(--ink-muted);letter-spacing:0.1em;text-transform:uppercase">${s[1]} SUBMITTED · ${s[2]}% APPROVED</div>
              </div>
              <div class="bar" style="width:80px"><div class="seg-bar ok" style="width:${s[2]}%"></div></div>
            </li>`).join('')}
        </ul>
      </section>
    </div>
  </div>
`;

/* ═══════════════════════ 11 TICKETS ═══════════════════════ */
PAGES.tickets = () => `
  ${pageHead({
    eyebrow:'32 ITEMS · 9 APPROVALS · 23 TICKETS',
    title:`Tickets`,
    sub:'Approvals, asset tracking, and issue management.',
    actions:`<button class="btn ghost">Mine only</button><button class="btn primary">+ New Ticket</button>`
  })}

  <div class="seg" style="margin-bottom:14px">
    <button aria-selected="true">APPROVALS <span class="c">9</span></button>
    <button>OPEN TICKETS <span class="c">23</span></button>
    <button>IN REVIEW <span class="c">4</span></button>
    <button>CLOSED <span class="c">16</span></button>
  </div>

  <div class="cols">
    <div class="col">
      <section class="block">
        <header><h2>Pending Approvals</h2><div class="act"><a style="color:var(--molten);cursor:pointer">Approve all visible</a></div></header>
        <table class="ctab">
          <thead><tr><th></th><th>Code</th><th>Scene</th><th>Step</th><th>By</th><th>Age</th><th></th><th></th></tr></thead>
          <tbody>
          ${[
            {s:'fpvr',code:'FPV-2041',t:'Sunset Suite · 04',n:'Final trailer',who:'jess.k',age:'4h',hot:true},
            {s:'vrh', code:'VRH-1887',t:'Moonlit Balcony · 02',n:'Director cut',who:'marco.t',age:'11h'},
            {s:'vra', code:'VRA-1204',t:'Atrium · 06',n:'Color pass v3',who:'jess.k',age:'1d',hot:true},
            {s:'njoi',code:'NJO-0833',t:'Backlot 12 · 01',n:'Title card',who:'rhea.d',age:'1d'},
            {s:'fpvr',code:'FPV-2039',t:'Loft Series · 11',n:'Comp master',who:'marco.t',age:'2d'},
            {s:'vrh', code:'VRH-1882',t:'Greenhouse · 03',n:'Teaser',who:'jess.k',age:'3d'}
          ].map(r=>`
            <tr>
              <td><span class="mono-chip ${r.s}">${r.s.toUpperCase()}</span></td>
              <td style="font-family:var(--font-mono);font-size:11px;color:var(--ink-muted)">${r.code}</td>
              <td class="serif">${r.t}</td>
              <td class="dim">${r.n}</td>
              <td class="dim">${r.who}</td>
              <td class="age" ${r.hot?'data-hot':''}>${r.age}</td>
              <td><button class="btn danger" style="padding:5px 10px;font-size:9px">Changes</button></td>
              <td><button class="btn molten" style="padding:5px 10px;font-size:9px">Approve</button></td>
            </tr>`).join('')}
          </tbody>
        </table>
      </section>

      <section class="block">
        <header><h2>Open Tickets</h2><div class="act"><a>Priority ↓</a></div></header>
        <table class="ctab">
          <thead><tr><th>ID</th><th>P</th><th>Title</th><th>Area</th><th>Assignee</th><th>Age</th><th>Status</th></tr></thead>
          <tbody>
            ${[
              ['TKT-0231','P0','MEGA rclone orphaned on win-prod','INFRA','andre.n','2h','err','BLOCKED'],
              ['TKT-0230','P1','Color pass rejected · VRA-1204','CONTENT','rhea.d','11h','progress','REVIEW'],
              ['TKT-0229','P1','Director voice ADR — WER spike','AUDIO','andre.n','1d','ok','OPEN'],
              ['TKT-0228','P2','Title gen truncated copy','AI','jess.k','2d','ok','OPEN'],
              ['TKT-0227','P2','Scene grid view-transition flicker','UI','marco.t','2d','progress','REVIEW'],
              ['TKT-0226','P1','Sheets quota warning · scripts','SYNC','andre.n','3d','ok','OPEN'],
              ['TKT-0225','P3','Mobile: panel overflow','UI','marco.t','4d','ok','OPEN'],
              ['TKT-0224','P2','Approval SSE disconnects','INFRA','andre.n','5d','progress','REVIEW'],
              ['TKT-0223','P2','Comp render stalls at 38%','RENDER','andre.n','6d','err','BLOCKED'],
              ['TKT-0221','P1','Color pass signals out of range','CONTENT','rhea.d','10d','ok','OPEN']
            ].map(r=>`
              <tr>
                <td style="font-family:var(--font-mono);font-size:11px;color:var(--ink-muted)">${r[0]}</td>
                <td><span class="pill" data-s="${r[1]==='P0'?'err':r[1]==='P1'?'warn':'ok'}"><span class="d"></span>${r[1]}</span></td>
                <td class="serif">${r[2]}</td>
                <td class="dim" style="font-size:10px;letter-spacing:0.1em;text-transform:uppercase">${r[3]}</td>
                <td class="dim">${r[4]}</td>
                <td class="dim">${r[5]}</td>
                <td><span class="pill" data-s="${r[6]}"><span class="d"></span>${r[7]}</span></td>
              </tr>`).join('')}
          </tbody>
        </table>
      </section>
    </div>

    <div class="col">
      <section class="block inverted">
        <header><h2>Queue Health</h2></header>
        <div style="padding:16px;display:flex;flex-direction:column;gap:14px">
          <div><div style="font-size:9px;font-weight:700;letter-spacing:0.18em;text-transform:uppercase;color:rgba(255,255,255,0.45)">Avg Response</div><div style="font-weight:800;font-size:36px;letter-spacing:-0.03em;margin-top:4px">14h 22m</div></div>
          <div><div style="font-size:9px;font-weight:700;letter-spacing:0.18em;text-transform:uppercase;color:rgba(255,255,255,0.45)">Approval Rate · 7d</div><div style="font-weight:800;font-size:36px;letter-spacing:-0.03em;margin-top:4px">83%</div></div>
          <div><div style="font-size:9px;font-weight:700;letter-spacing:0.18em;text-transform:uppercase;color:rgba(255,255,255,0.45)">Submissions · Week</div><div style="font-weight:800;font-size:36px;letter-spacing:-0.03em;margin-top:4px">21</div></div>
        </div>
      </section>

      <section class="block">
        <header><h2>Submit Ticket</h2></header>
        <div style="padding:14px;display:flex;flex-direction:column;gap:10px">
          <input type="text" placeholder="Title" style="padding:7px 10px;border:1px solid var(--rule);background:var(--bone);font:inherit;font-size:12px">
          <div style="display:flex;gap:8px">
            <select style="flex:1;padding:7px 10px;border:1px solid var(--rule);background:var(--bone);font:inherit;font-size:12px">
              <option>P2 — Normal</option><option>P0 — Critical</option><option>P1 — High</option><option>P3 — Low</option>
            </select>
            <select style="flex:1;padding:7px 10px;border:1px solid var(--rule);background:var(--bone);font:inherit;font-size:12px">
              <option>UI</option><option>INFRA</option><option>CONTENT</option><option>SYNC</option><option>AI</option><option>RENDER</option><option>AUDIO</option>
            </select>
          </div>
          <textarea placeholder="Description..." style="padding:7px 10px;border:1px solid var(--rule);background:var(--bone);font:inherit;font-size:12px;min-height:80px;resize:vertical"></textarea>
          <button class="btn primary" style="align-self:flex-start">Submit</button>
        </div>
      </section>
    </div>
  </div>
`;

PAGES.admin = () => `
  ${pageHead({
    eyebrow:'ADMIN · 7 USERS · 3 ADMINS · 4 EDITORS',
    title:`System Admin`,
    sub:'Users, access, infra, and deploy state.',
    actions:`<button class="btn ghost">Logs</button><button class="btn ghost">Audit</button><button class="btn primary">+ Add User</button>`
  })}

  <div class="cols">
    <section class="block">
      <header><h2><span class="num">01</span>Users · 7</h2></header>
      <table class="ctab">
        <thead><tr><th></th><th>Name</th><th>Role</th><th>Allowed Tabs</th><th>Last Seen</th><th>Status</th><th></th></tr></thead>
        <tbody>
          ${[
            ['AN','Andrew Ninn','admin','ALL','2m','ok','ONLINE'],
            ['JK','Jess Katz','editor','Approvals · Tickets · Scripts','18m','ok','ONLINE'],
            ['MT','Marco Tolo','editor','Comps · Titles · Approvals','1h','ok','AWAY'],
            ['RD','Rhea Das','editor','Approvals · Tickets · Research','4h','ok','AWAY'],
            ['CS','Carla Soto','admin','ALL','1d','ok','OFFLINE'],
            ['VL','Vera Loeb','admin','ALL','3d','warn','STALE'],
            ['PJ','Petra Jansen','editor','Call Sheets · Shoots','7d','warn','STALE']
          ].map(u=>`
            <tr>
              <td><div style="width:32px;height:32px;border:1px solid var(--ink);display:flex;align-items:center;justify-content:center;font-family:var(--font-display);font-style:italic;font-size:18px;letter-spacing:-0.01em">${u[0]}</div></td>
              <td class="serif">${u[1]}</td>
              <td><span class="pill" data-s="${u[2]==='admin'?'progress':'ok'}"><span class="d"></span>${u[2].toUpperCase()}</span></td>
              <td class="dim" style="font-size:11px">${u[3]}</td>
              <td class="dim">${u[4]}</td>
              <td><span class="pill" data-s="${u[5]}"><span class="d"></span>${u[6]}</span></td>
              <td><button class="btn ghost">Edit</button></td>
            </tr>`).join('')}
        </tbody>
      </table>
    </section>

    <div class="col">
      <section class="block inverted">
        <header><h2><span class="num">02</span>Infra · win-prod</h2></header>
        <div style="padding:16px;display:flex;flex-direction:column;gap:0">
          ${[
            ['UPTIME',    '6d 14h',      true],
            ['SERVICE',   'EclatechHub · running', false],
            ['PORT',      '8501',        true],
            ['LAST DEPLOY','3d 06h · v4.12', false],
            ['CPU / MEM', '18% · 42%',  false]
          ].map(r=>`
            <div style="display:grid;grid-template-columns:100px 1fr;gap:8px;padding:9px 0;border-bottom:1px solid rgba(255,255,255,0.08);align-items:center">
              <span style="font-family:var(--font-sans);font-size:9px;font-weight:700;letter-spacing:0.18em;text-transform:uppercase;color:rgba(255,255,255,0.38)">${r[0]}</span>
              <span style="${r[2]?'font-family:var(--font-mono);font-size:13px;':'font-size:12px;'}color:rgba(244,239,230,0.82)">${r[1]}</span>
            </div>`).join('')}
          <button class="btn molten" style="margin-top:14px;width:100%;justify-content:center">Deploy · 4.13-rc1</button>
        </div>
      </section>

      <section class="block">
        <header><h2><span class="num">04</span>Tab Permissions</h2></header>
        <ul class="list">
          ${['Shoots','Tickets','Model Research','Scripts','Call Sheets','Titles','Descriptions','Compilations'].map((t,i)=>`
            <li style="grid-template-columns:1fr auto;font-size:11px">
              <span>${t}</span>
              <span class="dim" style="letter-spacing:0.1em;text-transform:uppercase">${[7,7,4,5,3,4,4,3][i]} / 7 USERS</span>
            </li>`).join('')}
        </ul>
      </section>

      <section class="block">
        <header><h2><span class="num">05</span>Deploy Log</h2></header>
        <ul class="list" style="font-family:var(--font-mono);font-size:10px;line-height:1.7">
          ${[
            ['4.12','3d 06h ago','ok'],
            ['4.11','7d 14h ago','ok'],
            ['4.10','12d ago','warn'],
            ['4.09','19d ago','ok'],
            ['4.08','26d ago','ok']
          ].map(d=>`<li style="grid-template-columns:60px 1fr auto;padding:8px 14px"><span class="serif" style="font-size:14px">v${d[0]}</span><span class="dim" style="font-size:10px;letter-spacing:0.12em;text-transform:uppercase">${d[1]}</span><span class="pill" data-s="${d[2]}"><span class="d"></span>${d[2].toUpperCase()}</span></li>`).join('')}
        </ul>
      </section>
    </div>
  </div>
`;
