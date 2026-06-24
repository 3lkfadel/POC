/**
 * context_bar.js — Lot 0
 * Injecte les sélecteurs Entité / Rôle dans la topbar existante.
 * Lit /api/entites, /api/roles, /api/contexte au chargement.
 * POST /api/contexte à chaque changement.
 * Dégrade silencieusement si l'API Flask n'est pas disponible (mode fichier statique).
 */
(function () {
  'use strict';

  const API = {
    entites: '/api/entites',
    roles:   '/api/roles',
    contexte: '/api/contexte',
  };

  let _ctx     = { entite_code: null, role: 'Direction' };
  let _entites = [];
  let _roles   = [];

  // ── Boot ──────────────────────────────────────────────────────────────────
  async function boot() {
    try {
      const [entitesRes, rolesRes, ctxRes] = await Promise.all([
        fetch(API.entites),
        fetch(API.roles),
        fetch(API.contexte),
      ]);
      if (!entitesRes.ok) return; // Flask pas dispo

      _entites = await entitesRes.json();
      _roles   = await rolesRes.json();
      _ctx     = await ctxRes.json();

      // Si aucun contexte en session, initialiser avec "Consolidé" (vue holding)
      if (!_ctx.entite_code && _entites.length) {
        await _postContexte({ entite_code: _entites[0].code, role: 'Direction' });
      }

      inject();
      // Notifier toutes les pages du contexte courant dès le chargement
      window.dispatchEvent(new CustomEvent('alveole:contexte', { detail: _ctx }));
    } catch (_) {
      // Flask non démarré → pas de sélecteurs, HTML reste fonctionnel en standalone
    }
  }

  // ── Injection dans le header ───────────────────────────────────────────────
  function inject() {
    const header = document.querySelector('header.fixed');
    if (!header || document.getElementById('ctx-bar')) return;

    const rightDiv = header.querySelector('.flex.items-center.gap-4');
    if (!rightDiv) return;

    const bar = document.createElement('div');
    bar.id = 'ctx-bar';
    bar.className = 'flex items-center gap-3 pr-4 mr-4 border-r border-outline-variant';
    bar.innerHTML = _renderSelectors();

    // Insérer au début du bloc de droite (avant dark-mode, notif, etc.)
    rightDiv.insertBefore(bar, rightDiv.firstChild);

    _updateBadge();
  }

  function _renderSelectors() {
    const entiteOptions = _entites
      .map(e => `<option value="${e.code}" ${_ctx.entite_code === e.code ? 'selected' : ''}>${_entityLabel(e)}</option>`)
      .join('');

    const roleOptions = _roles
      .map(r => `<option value="${r}" ${_ctx.role === r ? 'selected' : ''}>${r}</option>`)
      .join('');

    return `
      <div class="flex flex-col items-start gap-0.5">
        <span class="text-[9px] font-bold text-on-surface-variant uppercase tracking-widest leading-none">Entité</span>
        <select id="ctx-entite-select"
          onchange="window.__ctxChange('entite_code', this.value)"
          class="text-[12px] font-semibold text-primary bg-primary/5 border border-primary/20
                 rounded-lg px-2 py-1 cursor-pointer focus:outline-none focus:ring-1
                 focus:ring-primary/40 hover:bg-primary/10 transition-all min-w-[140px]">
          ${entiteOptions}
        </select>
      </div>
      <div class="flex flex-col items-start gap-0.5">
        <span class="text-[9px] font-bold text-on-surface-variant uppercase tracking-widest leading-none">Rôle</span>
        <select id="ctx-role-select"
          onchange="window.__ctxChange('role', this.value)"
          class="text-[12px] font-semibold text-secondary bg-secondary/5 border border-secondary/20
                 rounded-lg px-2 py-1 cursor-pointer focus:outline-none focus:ring-1
                 focus:ring-secondary/40 hover:bg-secondary/10 transition-all min-w-[110px]">
          ${roleOptions}
        </select>
      </div>`;
  }

  function _entityLabel(e) {
    if (e.code === 'CONSOLIDE') return '🏢 Consolidé';
    if (e.type === 'holding') return `🏛 ${e.nom}`;
    return e.nom;
  }

  // ── Mise à jour du badge profil (nom entité courante) ─────────────────────
  function _updateBadge() {
    const badge = document.getElementById('ctx-entity-badge');
    if (!badge) return;
    const e = _entites.find(x => x.code === _ctx.entite_code);
    badge.textContent = e ? e.nom : (_ctx.entite_code || '—');
  }

  // ── Handler de changement (exposé globalement pour les onchange inline) ───
  window.__ctxChange = async function (field, value) {
    const payload = { [field]: value };
    const result = await _postContexte(payload);
    if (result) {
      _ctx = result;
      _updateBadge();

      // Actualiser la sélection dans l'autre select si nécessaire
      const entiteEl = document.getElementById('ctx-entite-select');
      const roleEl   = document.getElementById('ctx-role-select');
      if (entiteEl) entiteEl.value = _ctx.entite_code || '';
      if (roleEl)   roleEl.value   = _ctx.role || 'Direction';

      // Émettre un événement custom pour que les pages puissent réagir
      window.dispatchEvent(new CustomEvent('alveole:contexte', { detail: _ctx }));
    }
  };

  async function _postContexte(payload) {
    try {
      const res = await fetch(API.contexte, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      });
      return res.ok ? await res.json() : null;
    } catch (_) {
      return null;
    }
  }

  // ── Démarrage ─────────────────────────────────────────────────────────────
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', boot);
  } else {
    boot();
  }
})();
