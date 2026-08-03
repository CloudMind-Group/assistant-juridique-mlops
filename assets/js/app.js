/* =====================================================================
   CloudMind Group — Couche applicative
   État, filtrage, événements, animations. Dépend de data.js et render.js.
   ===================================================================== */
(() => {
  'use strict';

  const $ = (s, r = document) => r.querySelector(s);
  const $$ = (s, r = document) => [...r.querySelectorAll(s)];
  const { icon } = CM;

  /* ------------------------------------------------------------------ état */
  const state = { q: '', members: new Set(), status: 'all', view: 'grid', open: new Set() };

  /* ------------------------------------------------------------ statistiques */
  const stats = {
    subsTotal: MEMBERS.reduce((a, m) => a + m.subs.length, 0),
    subsDone:  MEMBERS.reduce((a, m) => a + m.subs.filter(s => s[1]).length, 0),
    global:    Math.round(MEMBERS.reduce((a, m) => a + m.progress, 0) / MEMBERS.length),
    tools:     new Set(MEMBERS.flatMap(m => m.tools)).size,
    by:        k => MEMBERS.filter(m => m.status === k).length
  };

  /* ------------------------------------------------------- sections statiques */
  function mountStatic() {
    $('#kpis').innerHTML = [
      ['Avancement global',    stats.global + '%',                        'Moyenne pondérée des 8 modules'],
      ['Sous-tâches livrées',  stats.subsDone + '/' + stats.subsTotal,    'Backlog technique consolidé'],
      ['Modules actifs',       stats.by('progress') + ' en cours',        stats.by('done') + ' terminés · ' + stats.by('planned') + ' planifiés'],
      ['Technologies',         stats.tools + '+',                         'Stack MLOps standardisée']
    ].map(CM.kpiHTML).join('');

    $('#memberFilters').innerHTML = MEMBERS.map(CM.memberFilterHTML).join('');
    $('#raciLegend').innerHTML    = RACI_LEGEND.map(CM.legendHTML).join('');
    $('#raciWrap').innerHTML      = CM.raciHTML();
    $('#stackBody').innerHTML     = STACK.map(CM.stackRowHTML).join('');
    $('#flowRow1').innerHTML      = STAGES.slice(0, 4).map(CM.stageHTML).join('');
    $('#flowRow2').innerHTML      = STAGES.slice(4).map(CM.stageHTML).join('');
    $('#lanes').innerHTML         = LANES.map(CM.laneHTML).join('');
    $('#qualityBars').innerHTML   = QUALITY.map(CM.qualityBarHTML).join('');
    $('#timeline').innerHTML      = TIMELINE.map(CM.timelineHTML).join('');
    $('#delivGrid').innerHTML     = DELIVERABLES.map(CM.deliverableHTML).join('');
    $('#footTeam').innerHTML      = MEMBERS.map(CM.footTeamHTML).join('');

    $('#cDone').textContent = stats.by('done');
    $('#cRun').textContent  = stats.by('progress');
    $('#cPlan').textContent = stats.by('planned');
  }

  /* --------------------------------------------------------------- filtrage */
  function visible() {
    const q = state.q.trim().toLowerCase();
    const words = q ? q.split(/\s+/) : [];
    return MEMBERS.map((m, i) => ({ m, i })).filter(({ m, i }) => {
      if (state.members.size && !state.members.has(i)) return false;
      if (state.status !== 'all' && m.status !== state.status) return false;
      if (!words.length) return true;
      const hay = [
        m.name, m.role, m.module, m.desc, m.collab,
        m.tools.join(' '), m.subs.map(s => s[0]).join(' '), m.deliverables.join(' ')
      ].join(' ').toLowerCase();
      return words.every(w => hay.includes(w));
    });
  }

  /* ----------------------------------------------------------------- rendu */
  function render() {
    const board = $('#board');
    const list = visible();
    board.className = 'board view-' + state.view;

    if (!list.length) {
      board.innerHTML = CM.emptyHTML();
    } else if (state.view === 'grid') {
      board.innerHTML = list.map(({ m, i }) => CM.cardHTML(m, i, state.open.has(m.id))).join('');
    } else {
      board.innerHTML = ['done', 'progress', 'planned'].map(k =>
        CM.columnHTML(k, list.filter(({ m }) => m.status === k)
          .map(({ m, i }) => CM.cardHTML(m, i, state.open.has(m.id))))
      ).join('');
    }

    $('#resultCount').innerHTML =
      `<b>${list.length}</b> module${list.length > 1 ? 's' : ''} affiché${list.length > 1 ? 's' : ''} sur ${MEMBERS.length}`;

    requestAnimationFrame(() => $$('#board .bar').forEach(b => { b.style.width = b.dataset.w + '%'; }));
    syncToggleLabel(list.length);
  }

  function syncToggleLabel(visibleCount) {
    const allOpen = visibleCount > 0 && state.open.size >= visibleCount;
    $('#toggleAll').innerHTML = icon('i-expand', 'width:13px;height:13px') + (allOpen ? ' Tout replier' : ' Tout déplier');
  }

  /* ----------------------------------------------------------- interactions */
  function bindBoard() {
    const board = $('#board');

    board.addEventListener('click', e => {
      const head = e.target.closest('.card-head');
      if (!head) return;
      const card = head.closest('.card');
      const id = MEMBERS[+card.dataset.i].id;
      const willOpen = !card.classList.contains('open');
      card.classList.toggle('open', willOpen);
      head.setAttribute('aria-expanded', willOpen);
      willOpen ? state.open.add(id) : state.open.delete(id);
      syncToggleLabel(visible().length);
    });

    board.addEventListener('pointermove', e => {
      const c = e.target.closest('.card');
      if (!c) return;
      const r = c.getBoundingClientRect();
      c.style.setProperty('--mx', (e.clientX - r.left) + 'px');
      c.style.setProperty('--my', (e.clientY - r.top) + 'px');
    });
  }

  function bindControls() {
    $('#q').addEventListener('input', e => { state.q = e.target.value; render(); });

    $('#memberFilters').addEventListener('click', e => {
      const b = e.target.closest('.fmember');
      if (!b) return;
      const i = +b.dataset.i;
      state.members.has(i) ? state.members.delete(i) : state.members.add(i);
      b.setAttribute('aria-pressed', state.members.has(i));
      render();
    });

    $$('.fstatus').forEach(b => b.addEventListener('click', () => {
      state.status = b.dataset.status;
      $$('.fstatus').forEach(x => x.setAttribute('aria-pressed', x === b));
      render();
    }));

    $('#viewGrid').addEventListener('click', () => setView('grid'));
    $('#viewKanban').addEventListener('click', () => setView('kanban'));

    $('#toggleAll').addEventListener('click', () => {
      const list = visible();
      if (state.open.size >= list.length) state.open.clear();
      else list.forEach(({ m }) => state.open.add(m.id));
      render();
    });

    $('#resetBtn').addEventListener('click', () => {
      state.q = ''; state.members.clear(); state.status = 'all'; state.open.clear();
      $('#q').value = '';
      $$('.fmember').forEach(b => b.setAttribute('aria-pressed', false));
      $$('.fstatus').forEach(b => b.setAttribute('aria-pressed', b.dataset.status === 'all'));
      render();
    });

    document.addEventListener('keydown', e => {
      const typing = /^(INPUT|TEXTAREA)$/.test(document.activeElement.tagName);
      if (e.key === '/' && !typing) { e.preventDefault(); $('#q').focus(); }
      if (e.key === 'Escape' && document.activeElement === $('#q')) {
        $('#q').value = ''; state.q = ''; render(); $('#q').blur();
      }
    });
  }

  function setView(v) {
    state.view = v;
    $('#viewGrid').setAttribute('aria-pressed', v === 'grid');
    $('#viewKanban').setAttribute('aria-pressed', v === 'kanban');
    render();
  }

  /* ------------------------------------------------------------- animations */
  function bindReveal() {
    const io = new IntersectionObserver(entries => entries.forEach(en => {
      if (!en.isIntersecting) return;
      en.target.classList.add('in');
      io.unobserve(en.target);
      $$('.bar', en.target).forEach(b => { b.style.width = b.dataset.w + '%'; });
      if (en.target.querySelector('#gaugeArc')) runGauge();
    }), { threshold: 0.14, rootMargin: '0px 0px -40px 0px' });

    $$('.rv').forEach(el => io.observe(el));
  }

  let gaugeDone = false;
  function runGauge() {
    if (gaugeDone) return;
    gaugeDone = true;
    const arc = $('#gaugeArc');
    const C = 2 * Math.PI * 50;
    arc.style.strokeDashoffset = C * (1 - stats.global / 100);
    let n = 0;
    const step = () => {
      n = Math.min(stats.global, n + 1);
      $('#gaugeVal').textContent = n + '%';
      if (n < stats.global) setTimeout(step, 14);
    };
    step();
  }

  /* ----------------------------------------------------------- thème & chrome */
  function bindChrome() {
    $('#themeBtn').addEventListener('click', () => {
      const t = document.documentElement.dataset.theme === 'dark' ? 'light' : 'dark';
      document.documentElement.dataset.theme = t;
      try { localStorage.setItem('cm-theme', t); } catch (_) {}
    });

    $('#printBtn').addEventListener('click', () => {
      MEMBERS.forEach(m => state.open.add(m.id));
      render();
      setTimeout(() => window.print(), 160);
    });

    const rail = $('#rail'), topbar = $('#topbar'), totop = $('#totop');
    const onScroll = () => {
      const h = document.documentElement.scrollHeight - innerHeight;
      rail.style.width = (h > 0 ? (scrollY / h) * 100 : 0) + '%';
      topbar.classList.toggle('stuck', scrollY > 12);
      totop.classList.toggle('on', scrollY > 600);
    };
    addEventListener('scroll', onScroll, { passive: true });
    onScroll();
    totop.addEventListener('click', () => scrollTo({ top: 0, behavior: 'smooth' }));
  }

  /* ------------------------------------------------------------------- boot */
  mountStatic();
  bindBoard();
  bindControls();
  bindChrome();
  bindReveal();
  render();
})();
