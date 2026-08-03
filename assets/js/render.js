/* =====================================================================
   CloudMind Group — Couche de rendu
   Fonctions pures : données -> chaîne HTML. Aucun effet de bord, aucun
   accès au DOM. Toute la logique d'état vit dans app.js.
   ===================================================================== */
const CM = (() => {
  'use strict';

  /* ---------------------------------------------------------------- outils */
  const esc = s => String(s).replace(/[&<>"]/g, c => ({ '&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;' }[c]));
  const ini = n => n.split(' ').filter(Boolean).slice(0, 2).map(w => w[0]).join('').toUpperCase();
  const icon = (id, style = '') => `<svg${style ? ` style="${style}"` : ''} aria-hidden="true"><use href="#${id}"/></svg>`;
  const grad = m => `linear-gradient(140deg,${m.c1},${m.c2})`;
  const avatar = (m, cls = 'av') => `<span class="${cls}" style="background:${grad(m)}">${ini(m.name)}</span>`;

  /* ------------------------------------------------------------ indicateurs */
  const kpiHTML = ([label, value, note]) => `
    <div class="kpi glass rv">
      <div class="kpi-val grad-text">${esc(value)}</div>
      <div class="kpi-lbl">${esc(label)}</div>
      <div class="kpi-note">${esc(note)}</div>
    </div>`;

  const memberFilterHTML = (m, i) => `
    <button class="fchip fmember" data-i="${i}" aria-pressed="false" title="${esc(m.module)}">
      ${avatar(m)}${esc(m.name)}
    </button>`;

  /* ----------------------------------------------------------- carte membre */
  const cardHTML = (m, i, isOpen) => {
    const st = STATUS[m.status];
    const done = m.subs.filter(s => s[1]).length;
    return `
    <article class="card glass ${isOpen ? 'open' : ''}" data-i="${i}" id="card-${m.id}" style="--c1:${m.c1};--c2:${m.c2}">
      <button class="card-head" aria-expanded="${isOpen}" aria-controls="body-${m.id}">
        <span class="avatar">${ini(m.name)}</span>
        <span style="flex:1;min-width:0">
          <span class="card-id">${icon(m.icon, 'width:12px;height:12px')} ${m.id} · Pilote (A)</span>
          <span class="card-name" style="display:block">${esc(m.name)}</span>
          <span class="card-role" style="display:block">${esc(m.role)}</span>
          <span class="card-mod" style="display:block"><span class="m-ico">▚</span> ${esc(m.module)}</span>
          <span class="card-desc" style="display:block">${esc(m.desc)}</span>
        </span>
        <span style="display:flex;flex-direction:column;align-items:flex-end;gap:10px;flex:none">
          <span class="status-pill ${st.pill}"><i class="dot${m.status === 'progress' ? ' pulse' : ''}"></i>${st.label}</span>
          <span class="card-chev">${icon('i-chev')}</span>
        </span>
      </button>

      <div class="prog-wrap">
        <div class="prog-top"><span>Avancement du module</span><b>${m.progress}%</b></div>
        <div class="track"><div class="bar" data-w="${m.progress}"></div></div>
      </div>

      <div class="card-body" id="body-${m.id}">
        <div class="card-body-in"><div class="card-body-pad">

          <div class="blk">
            <div class="blk-t">${icon('i-check')} Sous-tâches · ${done}/${m.subs.length} complétées</div>
            <ul class="subs">${m.subs.map(([t, d]) =>
              `<li data-done="${d}"><span class="tick">${d ? icon('i-check') : ''}</span><span>${t}</span></li>`).join('')}</ul>
          </div>

          <div class="blk">
            <div class="blk-t">${icon('i-cpu')} Outils &amp; technologies</div>
            <div class="tools">${m.tools.map(t => `<span class="tool"><i></i>${esc(t)}</span>`).join('')}</div>
          </div>

          <div class="blk">
            <div class="blk-t">${icon('i-users')} Rôle transverse · contribue à ${m.supports.length} autres modules</div>
            <div class="tools">${m.supports.map(id => {
              const o = MEMBERS.find(x => x.id === id);
              return `<span class="tool" title="${esc(o.module)}"><b class="raci-c">C</b> ${esc(id)} — ${esc(o.module.split('· ')[1] || o.module)}</span>`;
            }).join('')}</div>
          </div>

          <div class="blk">
            <div class="blk-t">${icon('i-link')} Collaboration inter-modules</div>
            <div class="collab">${icon('i-info')}<span>${m.collab}</span></div>
          </div>

          <div class="blk">
            <div class="blk-t">${icon('i-box')} Livrables du module</div>
            <div class="deliv">${m.deliverables.map(d => `<div>${icon('i-file')}<span>${d}</span></div>`).join('')}</div>
          </div>

        </div></div>
      </div>
    </article>`;
  };

  const columnHTML = (statusKey, cards) => {
    const st = STATUS[statusKey];
    return `
    <section class="col">
      <header class="col-head">
        <span class="status-pill ${st.pill}"><i class="dot${statusKey === 'progress' ? ' pulse' : ''}"></i>${st.label}</span>
        <span class="n">${cards.length}</span>
      </header>
      ${cards.length ? cards.join('') : '<div class="col-empty">Aucun module dans cette colonne</div>'}
    </section>`;
  };

  const emptyHTML = () => `
    <div class="empty glass">${icon('i-search')}
      <b>Aucun module ne correspond</b>Ajustez la recherche ou réinitialisez les filtres actifs.
    </div>`;

  /* ------------------------------------------------------------ matrice RACI */
  const raciHTML = () => `
    <table class="raci-table">
      <thead>
        <tr>
          <th class="raci-corner">Membre \\ Module</th>
          ${MEMBERS.map(m => `<th class="raci-h" title="${esc(m.module)}"><span>${esc(m.id)}</span><small>${esc((m.module.split('· ')[1] || '').split(' &')[0])}</small></th>`).join('')}
          <th class="raci-h"><span>Charge</span><small>modules</small></th>
        </tr>
      </thead>
      <tbody>
        ${MEMBERS.map(m => `
        <tr>
          <th scope="row" class="raci-row">
            <div class="raci-row-in">${avatar(m)}<span><b>${esc(m.name)}</b><small>${esc(m.role.split(' — ')[0])}</small></span></div>
          </th>
          ${MEMBERS.map(o => {
            const r = raciRole(m, o.id);
            return `<td><span class="raci raci-${r.toLowerCase()}" title="${esc(m.name)} · ${esc(o.module)}">${r}</span></td>`;
          }).join('')}
          <td><span class="raci-load">${1 + m.supports.length}</span></td>
        </tr>`).join('')}
      </tbody>
    </table>`;

  /* ------------------------------------------------------- workflow & stack */
  const stageHTML = s => {
    const o = MEMBERS[s.owner];
    return `
    <div class="stage" style="--c1:${o.c1};--c2:${o.c2}">
      <span class="stage-n">${s.n}</span>
      <span class="stage-ico">${icon(s.icon)}</span>
      <h4>${esc(s.t)}</h4><p>${esc(s.d)}</p>
      <span class="stage-owner">${avatar(o)}${esc(o.name)}</span>
      <div class="stage-tools">${s.tools.map(t => `<span>${esc(t)}</span>`).join('')}</div>
    </div>`;
  };

  const laneHTML = l => {
    const o = MEMBERS[l.owner];
    return `
    <div class="lane" style="--c1:${l.c1};--c2:${l.c2}">
      <span class="lico">${icon(l.icon)}</span>
      <div>
        <h5>${esc(l.t)}</h5><p>${esc(l.d)}</p>
        <span class="stage-owner" style="margin-top:8px">${avatar(o)}${esc(o.name)}</span>
      </div>
    </div>`;
  };

  const stackRowHTML = ([layer, tech, role, ownerIndex]) => {
    const o = MEMBERS[ownerIndex];
    return `<tr>
      <td>${esc(layer)}</td>
      <td class="mono">${esc(tech)}</td>
      <td>${esc(role)}</td>
      <td><span class="stage-owner">${avatar(o)}${esc(o.name.split(' ')[0])}</span></td>
    </tr>`;
  };

  /* ------------------------------------------------------------- métriques */
  const qualityBarHTML = ([label, value, pct]) => `
    <div class="mini-b">
      <div class="mb-t"><span>${esc(label)}</span><b>${esc(value)}</b></div>
      <div class="track"><div class="bar" data-w="${pct}" style="--c1:var(--accent-2);--c2:var(--accent-3)"></div></div>
    </div>`;

  const timelineHTML = ([meta, title, desc, color]) => `
    <div class="tl">
      <span class="tl-dot" style="background:${color};box-shadow:0 0 0 3px color-mix(in srgb,${color} 22%,transparent)"></span>
      <div><span class="tl-meta">${esc(meta)}</span><h5>${esc(title)}</h5><p>${esc(desc)}</p></div>
    </div>`;

  const deliverableHTML = ([tag, title, desc]) => `
    <div class="dcard"><div class="dt">${esc(tag)}</div><h5>${esc(title)}</h5><p>${esc(desc)}</p></div>`;

  const footTeamHTML = m => `<li>${avatar(m)}${esc(m.name)}</li>`;

  const legendHTML = ([letter, label, color]) =>
    `<span class="chip"><b class="raci raci-${letter.toLowerCase()}" style="--rc:${color}">${letter}</b> ${esc(label)}</span>`;

  return {
    esc, ini, icon, avatar,
    kpiHTML, memberFilterHTML, cardHTML, columnHTML, emptyHTML,
    raciHTML, legendHTML, stageHTML, laneHTML, stackRowHTML,
    qualityBarHTML, timelineHTML, deliverableHTML, footTeamHTML
  };
})();
