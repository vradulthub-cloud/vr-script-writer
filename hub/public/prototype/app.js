/* Router + boot + tweaks for Eclatech Hub */
(function(){
  const view   = document.getElementById('view');
  const crumb  = document.getElementById('crumb');
  const clock  = document.getElementById('railClock');

  const ROUTES = {
    'dashboard':    { label: 'Dashboard' },
    'missing':      { label: 'Missing' },
    'shoots':       { label: 'Shoot Tracker' },
    'catalog':      { label: 'Studio Catalog' },
    'research':     { label: 'Model Research' },
    'scripts':      { label: 'Scripts' },
    'call-sheets':  { label: 'Call Sheets' },
    'titles':       { label: 'Titles' },
    'descriptions': { label: 'Descriptions' },
    'compilations': { label: 'Compilations' },
    'tickets':      { label: 'Tickets' },
    'admin':        { label: 'Admin' }
  };

  function route(){
    const hash = location.hash.replace('#/','') || 'dashboard';
    const key  = ROUTES[hash] ? hash : 'dashboard';
    const info = ROUTES[key];
    crumb.textContent = info.label;

    // persist
    localStorage.setItem('hub:route', key);

    // active nav
    document.querySelectorAll('.rail nav a').forEach(a => {
      if (a.dataset.route === key) a.setAttribute('aria-current','page');
      else a.removeAttribute('aria-current');
    });

    // render
    const fn = window.PAGES && window.PAGES[key];
    view.innerHTML = fn ? fn() : '<div class="empty">Not built yet</div>';
    window.scrollTo({top: 0});
  }

  // restore route
  if (!location.hash && localStorage.getItem('hub:route')) {
    location.hash = '#/' + localStorage.getItem('hub:route');
  }
  window.addEventListener('hashchange', route);
  route();

  // clock
  function tick(){
    const d = new Date();
    const p = n => String(n).padStart(2,'0');
    clock.textContent = `${p(d.getHours())}:${p(d.getMinutes())}:${p(d.getSeconds())}`;
  }
  tick(); setInterval(tick, 1000);

  // ─── Tweaks ───
  const tweaks = document.getElementById('tweaks');
  const tweaksClose = document.getElementById('tweaksClose');

  // Tweakable defaults (persisted)
  const TWEAK_DEFAULTS = /*EDITMODE-BEGIN*/{
    "paper": "bone",
    "accent": "molten",
    "mode": "light"
  }/*EDITMODE-END*/;

  const PAPERS = {
    bone:  { bone:'#F4EFE6', bone2:'#ECE6DA', bone3:'#DED6C5', rule:'#C8BFA9', ruleSoft:'#DED6C5' },
    cream: { bone:'#FAF4E1', bone2:'#F1E9CF', bone3:'#E4D9B3', rule:'#CFC189', ruleSoft:'#E4D9B3' },
    steel: { bone:'#E3E6E8', bone2:'#D5D9DC', bone3:'#BFC5C9', rule:'#A8B0B5', ruleSoft:'#C7CDD1' },
    rose:  { bone:'#F0E1DE', bone2:'#E6D2CD', bone3:'#D4B9B2', rule:'#B89E96', ruleSoft:'#D4B9B2' }
  };
  const ACCENTS = {
    molten:  { c:'#FF4500', ink:'#2A0E00' },
    acid:    { c:'#BED62F', ink:'#1E2500' },
    electric:{ c:'#2B4BFF', ink:'#00103A' },
    blood:   { c:'#B3200F', ink:'#1A0000' }
  };

  function applyTweaks(t){
    const p = PAPERS[t.paper] || PAPERS.bone;
    const a = ACCENTS[t.accent] || ACCENTS.molten;
    const r = document.documentElement.style;

    if (t.mode === 'dark') {
      r.setProperty('--bone',   '#141311');
      r.setProperty('--bone-2', '#1C1A17');
      r.setProperty('--bone-3', '#23201C');
      r.setProperty('--ink',    '#F4EFE6');
      r.setProperty('--ink-2',  '#EDE7D8');
      r.setProperty('--ink-muted','#A59C8C');
      r.setProperty('--ink-faint','#756D60');
      r.setProperty('--rule',   '#3A342D');
      r.setProperty('--rule-soft','#2A2622');
    } else {
      r.setProperty('--bone',   p.bone);
      r.setProperty('--bone-2', p.bone2);
      r.setProperty('--bone-3', p.bone3);
      r.setProperty('--ink',    '#0A0A0A');
      r.setProperty('--ink-2',  '#1F1D1B');
      r.setProperty('--ink-muted', '#6A6258');
      r.setProperty('--ink-faint', '#9A9286');
      r.setProperty('--rule',   p.rule);
      r.setProperty('--rule-soft', p.ruleSoft);
    }
    r.setProperty('--molten', a.c);
    r.setProperty('--molten-ink', a.ink);

    // swatch buttons
    document.querySelectorAll('.tweaks [data-paper]').forEach(b=>{
      b.setAttribute('aria-pressed', b.dataset.paper === t.paper ? 'true':'false');
    });
    document.querySelectorAll('.tweaks [data-accent]').forEach(b=>{
      b.setAttribute('aria-pressed', b.dataset.accent === t.accent ? 'true':'false');
    });
    document.getElementById('modeLight').setAttribute('aria-pressed', t.mode==='light'?'true':'false');
    document.getElementById('modeDark').setAttribute('aria-pressed',  t.mode==='dark'?'true':'false');
  }

  // wire swatches
  document.querySelectorAll('.tweaks [data-paper]').forEach(b=>{
    b.addEventListener('click', ()=>{
      TWEAK_DEFAULTS.paper = b.dataset.paper;
      applyTweaks(TWEAK_DEFAULTS);
      persist();
    });
  });
  document.querySelectorAll('.tweaks [data-accent]').forEach(b=>{
    b.addEventListener('click', ()=>{
      TWEAK_DEFAULTS.accent = b.dataset.accent;
      applyTweaks(TWEAK_DEFAULTS);
      persist();
    });
  });
  document.getElementById('modeLight').addEventListener('click', ()=>{
    TWEAK_DEFAULTS.mode = 'light'; applyTweaks(TWEAK_DEFAULTS); persist();
  });
  document.getElementById('modeDark').addEventListener('click', ()=>{
    TWEAK_DEFAULTS.mode = 'dark'; applyTweaks(TWEAK_DEFAULTS); persist();
  });

  function persist(){
    window.parent.postMessage({type:'__edit_mode_set_keys', edits: TWEAK_DEFAULTS},'*');
  }

  // restore tweaks from storage
  try {
    const saved = JSON.parse(localStorage.getItem('hub:tweaks')||'null');
    if (saved) Object.assign(TWEAK_DEFAULTS, saved);
  } catch(e){}
  applyTweaks(TWEAK_DEFAULTS);

  // Tweaks host integration
  window.addEventListener('message', e=>{
    if (!e.data || typeof e.data !== 'object') return;
    if (e.data.type === '__activate_edit_mode') tweaks.setAttribute('data-open','');
    if (e.data.type === '__deactivate_edit_mode') tweaks.removeAttribute('data-open');
  });
  tweaksClose.addEventListener('click', ()=>tweaks.removeAttribute('data-open'));
  window.parent.postMessage({type:'__edit_mode_available'},'*');
})();
