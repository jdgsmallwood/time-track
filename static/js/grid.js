/**
 * Week grid: renders blocks, handles drag/resize via interact.js,
 * opens HTMX-powered edit panel on click.
 *
 * Expects globals set by the embedding template:
 *   GRID_DATA        - array of block objects
 *   IS_TEMPLATE      - bool
 *   OWNER_PK         - int (template or plan week pk)
 *   BLOCK_CREATE_URL - string
 *   BLOCK_UPDATE_URL_TPL - string prefix for block update (e.g. '/schedule/template-blocks/')
 */

const GRID = (() => {
  const START_HOUR = 6;
  const END_HOUR = 23;
  const TOTAL_MINUTES = (END_HOUR - START_HOUR) * 60;
  const SLOT_PX = 2; // px per minute
  const GRID_HEIGHT = TOTAL_MINUTES * SLOT_PX; // 1020px
  const DAYS = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'];
  const SNAP_MINUTES = 15;

  let blocks = [];
  let gridEl, dayColumns;

  function minutesSinceMidnight(timeStr) {
    const [h, m] = timeStr.split(':').map(Number);
    return h * 60 + m;
  }

  function topForTime(timeStr) {
    const mins = minutesSinceMidnight(timeStr) - START_HOUR * 60;
    return Math.max(0, mins * SLOT_PX);
  }

  function heightForDuration(startStr, endStr) {
    const dur = minutesSinceMidnight(endStr) - minutesSinceMidnight(startStr);
    return Math.max(dur * SLOT_PX, 20);
  }

  function snapToGrid(minutes) {
    return Math.round(minutes / SNAP_MINUTES) * SNAP_MINUTES;
  }

  function minsToTimeStr(totalMins) {
    const h = Math.floor(totalMins / 60).toString().padStart(2, '0');
    const m = (totalMins % 60).toString().padStart(2, '0');
    return `${h}:${m}`;
  }

  function colorWithOpacity(hex, alpha) {
    const r = parseInt(hex.slice(1, 3), 16);
    const g = parseInt(hex.slice(3, 5), 16);
    const b = parseInt(hex.slice(5, 7), 16);
    return `rgba(${r},${g},${b},${alpha})`;
  }

  function getColumnLeft(colIdx) {
    if (!dayColumns.length) return 0;
    const col = dayColumns[colIdx];
    if (!col) return 0;
    const gridRect = gridEl.getBoundingClientRect();
    const colRect = col.getBoundingClientRect();
    return colRect.left - gridRect.left;
  }

  function getColumnWidth() {
    if (!dayColumns.length) return 100;
    return dayColumns[0].offsetWidth;
  }

  function renderBlock(block) {
    const existing = document.getElementById('block-' + block.id);
    if (existing) existing.remove();

    const el = document.createElement('div');
    el.id = 'block-' + block.id;
    el.className = 'absolute rounded-lg px-2 py-1 cursor-pointer shadow-sm border border-white/40 select-none overflow-hidden transition-shadow hover:shadow-md block-chip';
    el.dataset.blockId = block.id;

    const color = block.category_color || '#6366f1';
    el.style.cssText = `
      top: ${topForTime(block.start_time)}px;
      height: ${heightForDuration(block.start_time, block.end_time)}px;
      left: ${getColumnLeft(block.day_of_week) + 2}px;
      width: ${getColumnWidth() - 4}px;
      background: ${colorWithOpacity(color, 0.85)};
      border-left: 3px solid ${color};
      color: #fff;
    `;

    const dur = minutesSinceMidnight(block.end_time) - minutesSinceMidnight(block.start_time);
    el.innerHTML = `
      <div class="font-semibold text-xs leading-tight truncate">${block.title}</div>
      ${dur > 30 ? `<div class="text-xs opacity-80">${block.start_time}–${block.end_time}</div>` : ''}
      ${block.plugin_slug ? `<div class="text-xs opacity-70">${block.plugin_slug}</div>` : ''}
    `;

    el.addEventListener('click', (e) => {
      if (isDragging) return; // drag-end fires click in some browsers; ignore it
      e.stopPropagation();
      openEditPanel(block.id);
    });

    gridEl.appendChild(el);
    attachInteract(el, block);
  }

  function attachInteract(el, block) {
    interact(el)
      .draggable({
        inertia: false,
        modifiers: [
          interact.modifiers.snap({
            targets: [function(x, y) {
              // Snap to actual column left edges (page coords)
              const colWidth = getColumnWidth();
              const firstCol = dayColumns[0];
              const colOriginX = firstCol
                ? firstCol.getBoundingClientRect().left + window.scrollX
                : 0;
              const snapX = colOriginX + Math.round((x - colOriginX) / colWidth) * colWidth;
              // Snap y to 15-min slots relative to the grid top (page coords)
              const gridOriginY = gridEl.getBoundingClientRect().top + window.scrollY;
              const slotPx = SNAP_MINUTES * SLOT_PX;
              const snapY = gridOriginY + Math.round((y - gridOriginY) / slotPx) * slotPx;
              return { x: snapX, y: snapY };
            }],
            range: Infinity,
            relativePoints: [{ x: 0, y: 0 }],
          }),
        ],
        listeners: {
          start(event) { isDragging = true; el.style.opacity = '0.7'; el.style.zIndex = '100'; },
          move(event) {
            const x = (parseFloat(el.getAttribute('data-x') || 0)) + event.dx;
            const y = (parseFloat(el.getAttribute('data-y') || 0)) + event.dy;
            el.style.transform = `translate(${x}px, ${y}px)`;
            el.setAttribute('data-x', x);
            el.setAttribute('data-y', y);
          },
          end(event) {
            // Small delay so the click event fired at drag-end doesn't open the create popover
            setTimeout(() => { isDragging = false; }, 100);
            el.style.opacity = '1';
            el.style.zIndex = '';
            const dx = parseFloat(el.getAttribute('data-x') || 0);
            const dy = parseFloat(el.getAttribute('data-y') || 0);
            el.style.transform = '';
            el.removeAttribute('data-x');
            el.removeAttribute('data-y');

            const colWidth = getColumnWidth();
            const dayDelta = Math.round(dx / colWidth);
            const newDay = Math.max(0, Math.min(6, block.day_of_week + dayDelta));

            const minsDelta = snapToGrid(dy / SLOT_PX);
            const startMins = minutesSinceMidnight(block.start_time) + minsDelta;
            const endMins = minutesSinceMidnight(block.end_time) + minsDelta;
            const newStart = minsToTimeStr(Math.max(START_HOUR * 60, Math.min(END_HOUR * 60 - 15, startMins)));
            const newEnd = minsToTimeStr(Math.max(START_HOUR * 60 + 15, Math.min(END_HOUR * 60, endMins)));

            block.day_of_week = newDay;
            block.start_time = newStart;
            block.end_time = newEnd;

            updateBlockPosition(block);

            // Plan-week blocks are keyed by date not day_of_week; derive the
            // new date from WEEK_START_DATE + day index.
            if (IS_TEMPLATE) {
              patchBlock(block, { day_of_week: newDay, start_time: newStart, end_time: newEnd });
            } else {
              // Use local-date constructor (not toISOString which converts to UTC
              // and can give the wrong day in non-UTC timezones like UTC+10).
              const [y, m, d] = WEEK_START_DATE.split('-').map(Number);
              const dt = new Date(y, m - 1, d + newDay);
              const newDateStr = `${dt.getFullYear()}-${String(dt.getMonth()+1).padStart(2,'0')}-${String(dt.getDate()).padStart(2,'0')}`;
              block.date = newDateStr;
              patchBlock(block, { date: newDateStr, start_time: newStart, end_time: newEnd });
            }
          },
        },
      })
      .resizable({
        edges: { bottom: true },
        modifiers: [
          interact.modifiers.snapSize({
            // Function target: snap height to the nearest multiple of the slot step.
            // A static { height: N } target snaps to exactly N px (not multiples),
            // which collapses every resize attempt to a fixed size.
            targets: [
              (_w, h) => ({ height: Math.round(h / (SNAP_MINUTES * SLOT_PX)) * (SNAP_MINUTES * SLOT_PX) }),
            ],
          }),
        ],
        listeners: {
          move(event) {
            el.style.height = `${event.rect.height}px`;
          },
          end(event) {
            const durationMins = snapToGrid(event.rect.height / SLOT_PX);
            const startMins = minutesSinceMidnight(block.start_time);
            const newEnd = minsToTimeStr(Math.min(END_HOUR * 60, startMins + Math.max(15, durationMins)));
            block.end_time = newEnd;
            el.style.height = `${durationMins * SLOT_PX}px`;
            patchBlock(block, { end_time: newEnd });
          },
        },
      });
  }

  function updateBlockPosition(block) {
    const el = document.getElementById('block-' + block.id);
    if (!el) return;
    el.style.top = topForTime(block.start_time) + 'px';
    el.style.height = heightForDuration(block.start_time, block.end_time) + 'px';
    el.style.left = (getColumnLeft(block.day_of_week) + 2) + 'px';
    el.style.width = (getColumnWidth() - 4) + 'px';
  }

  async function patchBlock(block, fields) {
    const url = `${BLOCK_UPDATE_URL_TPL}${block.id}/`;
    const csrfToken = document.cookie.match(/csrftoken=([^;]+)/)?.[1] || '';
    try {
      await fetch(url, {
        method: 'PATCH',
        headers: {
          'Content-Type': 'application/json',
          'X-CSRFToken': csrfToken,
        },
        body: JSON.stringify(fields),
      });
    } catch (e) {
      console.error('Failed to update block:', e);
    }
  }

  function openEditPanel(blockId) {
    const url = `${BLOCK_UPDATE_URL_TPL}${blockId}/`;
    const panel = document.getElementById('edit-panel');
    const content = document.getElementById('edit-panel-content');
    panel.classList.remove('hidden');
    content.innerHTML = '<p class="text-sm text-gray-400 animate-pulse">Loading…</p>';
    htmx.ajax('GET', url, { target: '#edit-panel-content', swap: 'innerHTML' });
  }

  function renderHourLines() {
    for (let hour = START_HOUR; hour <= END_HOUR; hour++) {
      const top = (hour - START_HOUR) * 60 * SLOT_PX;
      const line = document.createElement('div');
      line.className = 'absolute w-full flex items-center pointer-events-none';
      line.style.top = top + 'px';
      line.innerHTML = `
        <div class="w-14 flex-shrink-0 text-right pr-2 text-xs text-gray-400 -mt-2 select-none">${hour}:00</div>
        <div class="flex-1 border-t border-gray-200"></div>
      `;
      gridEl.appendChild(line);
    }
  }

  function renderDayColumns() {
    const colContainer = document.createElement('div');
    colContainer.className = 'absolute inset-0 ml-14 grid grid-cols-7 pointer-events-none';
    for (let i = 0; i < 7; i++) {
      const col = document.createElement('div');
      col.className = 'border-r border-gray-200 last:border-r-0 h-full';
      col.dataset.col = i;
      colContainer.appendChild(col);
    }
    gridEl.appendChild(colContainer);
    dayColumns = Array.from(colContainer.children);
  }

  function repositionAll() {
    blocks.forEach(b => updateBlockPosition(b));
  }

  // ── Click-to-create popover ──────────────────────────────────────────────

  let isDragging = false;
  // Set to true by showCreatePopover so the document outside-click handler
  // ignores the very click that opened the popover (which also bubbles to document).
  let suppressNextOutsideClose = false;
  let lastCategoryPk = ''; // remember last-used category between popover opens

  function removeCreatePopover() {
    const el = document.getElementById('create-popover');
    if (el) el.remove();
  }

  function showCreatePopover(dayIdx, startMins, endMins, clickClientX, clickClientY) {
    if (!BLOCK_CREATE_URL) {
      // No plan week exists for this week yet
      const tip = document.createElement('div');
      tip.style.cssText = 'position:fixed;bottom:24px;left:50%;transform:translateX(-50%);background:#1e293b;color:#fff;padding:8px 16px;border-radius:8px;font-size:13px;z-index:9999;pointer-events:none;';
      tip.textContent = 'Create a plan week first to add blocks here.';
      document.body.appendChild(tip);
      setTimeout(() => tip.remove(), 3000);
      return;
    }
    removeCreatePopover();

    // Tell the document handler to ignore this bubbling click
    suppressNextOutsideClose = true;

    const startStr = minsToTimeStr(startMins);
    const endStr   = minsToTimeStr(endMins);
    const dayName  = DAYS[dayIdx];

    const pop = document.createElement('div');
    pop.id = 'create-popover';

    // Position at the click point, nudged right; flip left if it would overflow
    const gridRect = gridEl.getBoundingClientRect();
    const popWidth = 230;
    const clickX = clickClientX - gridRect.left;
    const clickY = clickClientY - gridRect.top;
    let leftPx = clickX + 8;
    if (leftPx + popWidth > gridEl.offsetWidth - 4) {
      leftPx = Math.max(4, clickX - popWidth - 8);
    }
    const topPx = Math.max(0, clickY - 10);

    pop.style.cssText = `position:absolute; top:${topPx}px; left:${leftPx}px; width:${popWidth}px; z-index:200;`;
    pop.innerHTML = `
      <div style="background:#fff; border:1px solid #6366f1; border-radius:8px; box-shadow:0 4px 16px rgba(0,0,0,.12); padding:10px;">
        <div style="font-size:11px; color:#6366f1; font-weight:600; margin-bottom:6px;">${dayName} · ${startStr}–${endStr}</div>
        <input id="create-popover-input" type="text" placeholder="Block title"
               style="display:block; width:100%; box-sizing:border-box; border:1px solid #d1d5db; border-radius:6px; padding:5px 8px; font-size:13px; margin-bottom:6px; outline:none;">
        ${(typeof CATEGORIES !== 'undefined' && CATEGORIES.length) ? `
        <select id="create-popover-category"
                style="display:block; width:100%; box-sizing:border-box; border:1px solid #d1d5db; border-radius:6px; padding:5px 8px; font-size:13px; margin-bottom:6px; background:#fff; color:#374151;">
          <option value="">— no category —</option>
          ${CATEGORIES.map(c => `<option value="${c.pk}" ${String(c.pk) === String(lastCategoryPk) ? 'selected' : ''}>${c.icon ? c.icon + ' ' : ''}${c.name}</option>`).join('')}
        </select>` : ''}
        <div style="display:flex; gap:6px;">
          <button id="create-popover-save"
                  style="flex:1; background:#6366f1; color:#fff; border:none; border-radius:6px; padding:5px 0; font-size:12px; font-weight:600; cursor:pointer;">
            Add block
          </button>
          <button id="create-popover-cancel"
                  style="background:none; border:1px solid #d1d5db; border-radius:6px; padding:5px 8px; font-size:12px; color:#6b7280; cursor:pointer;">
            ✕
          </button>
        </div>
      </div>`;

    gridEl.appendChild(pop);
    pop.querySelector('#create-popover-input').focus();

    const doSave = async () => {
      const input = pop.querySelector('#create-popover-input');
      const title = input.value.trim();
      if (!title) { input.style.borderColor = '#f87171'; input.focus(); return; }

      const catEl = pop.querySelector('#create-popover-category');
      if (catEl && catEl.value) lastCategoryPk = catEl.value;

      const body = { title, start_time: startStr, end_time: endStr };
      if (catEl && catEl.value) body.category = catEl.value;
      if (IS_TEMPLATE) {
        body.day_of_week = dayIdx;
      } else {
        const [y, m, d] = WEEK_START_DATE.split('-').map(Number);
        const dt = new Date(y, m - 1, d + dayIdx);
        body.date = `${dt.getFullYear()}-${String(dt.getMonth()+1).padStart(2,'0')}-${String(dt.getDate()).padStart(2,'0')}`;
      }

      const csrf = document.cookie.match(/csrftoken=([^;]+)/)?.[1] || '';
      try {
        const resp = await fetch(BLOCK_CREATE_URL, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json', 'X-CSRFToken': csrf },
          body: JSON.stringify(body),
        });
        if (resp.ok) window.location.reload();
      } catch(e) { console.error('Create block failed', e); }
      removeCreatePopover();
    };

    pop.querySelector('#create-popover-save').addEventListener('click', doSave);
    pop.querySelector('#create-popover-cancel').addEventListener('click', removeCreatePopover);
    pop.querySelector('#create-popover-input').addEventListener('keydown', e => {
      if (e.key === 'Enter') { e.preventDefault(); doSave(); }
      if (e.key === 'Escape') removeCreatePopover();
    });
    // Stop pointer events inside the popover from reaching the grid handler
    pop.addEventListener('pointerdown', e => e.stopPropagation());
    pop.addEventListener('click', e => e.stopPropagation());
  }

  let dragCreate = null; // { dayIdx, startMins, endMins, moved }

  function colAtClientX(clientX) {
    // Primary: check actual column BoundingClientRects
    for (let i = 0; i < dayColumns.length; i++) {
      const cr = dayColumns[i].getBoundingClientRect();
      if (cr.width > 0 && clientX >= cr.left && clientX < cr.right) return i;
    }
    // Fallback: compute mathematically from the grid rect (handles Firefox
    // returning stale zero-width rects for abs-positioned children of scroll containers)
    const gridRect = gridEl.getBoundingClientRect();
    const TIME_LABEL_PX = 56;
    const usable = gridRect.width - TIME_LABEL_PX;
    if (usable <= 0) return -1;
    const x = clientX - gridRect.left - TIME_LABEL_PX;
    if (x < 0) return -1;
    const idx = Math.floor(x / (usable / 7));
    return idx >= 0 && idx < 7 ? idx : -1;
  }

  function addGridClickHandler() {
    // Persistent outside-click handler — closes popover when clicking elsewhere.
    // suppressNextOutsideClose skips the click that bubbles from the same pointerup.
    document.addEventListener('click', e => {
      if (suppressNextOutsideClose) { suppressNextOutsideClose = false; return; }
      const pop = document.getElementById('create-popover');
      if (pop && !pop.contains(e.target)) removeCreatePopover();
    });

    // ── Drag-to-create ────────────────────────────────────────────────────────
    // pointerdown on the grid starts tracking; document-level pointermove/pointerup
    // handle the rest so we don't depend on setPointerCapture (Firefox can cancel it).

    gridEl.addEventListener('pointerdown', e => {
      if (e.button !== 0 || isDragging) return;
      // Ignore presses on existing blocks or the create popover
      if (e.target.closest && (
        e.target.closest('[id^="block-"]') ||
        e.target.closest('#create-popover')
      )) return;

      const dayIdx = colAtClientX(e.clientX);
      if (dayIdx === -1) return;

      const rect = gridEl.getBoundingClientRect();
      const rawMins = START_HOUR * 60 + (e.clientY - rect.top) / SLOT_PX;
      const startMins = Math.max(START_HOUR * 60, Math.min(END_HOUR * 60 - SNAP_MINUTES, snapToGrid(rawMins)));

      dragCreate = { dayIdx, startMins, endMins: startMins + 60, moved: false };
      // Don't call setPointerCapture here — Firefox can cancel it causing missed events.
      // Don't call preventDefault here — it cancels pointer capture in some Firefox builds.
    });

    document.addEventListener('pointermove', e => {
      if (!dragCreate) return;
      e.preventDefault(); // prevent page scroll while drawing

      const rect = gridEl.getBoundingClientRect();
      const rawMins = START_HOUR * 60 + (e.clientY - rect.top) / SLOT_PX;
      const endMins = Math.max(dragCreate.startMins + SNAP_MINUTES, Math.min(END_HOUR * 60, snapToGrid(rawMins)));
      dragCreate.endMins = endMins;

      if (endMins > dragCreate.startMins + SNAP_MINUTES) dragCreate.moved = true;

      let ghost = document.getElementById('create-ghost');
      if (!ghost) {
        ghost = document.createElement('div');
        ghost.id = 'create-ghost';
        ghost.style.cssText = [
          'position:absolute', 'pointer-events:none', 'z-index:50',
          'background:rgba(99,102,241,0.15)', 'border:2px dashed #6366f1',
          'border-radius:6px', 'font-size:10px', 'color:#4f46e5',
          'padding:2px 5px', 'box-sizing:border-box',
          `left:${getColumnLeft(dragCreate.dayIdx) + 2}px`,
          `width:${getColumnWidth() - 4}px`,
        ].join(';');
        gridEl.appendChild(ghost);
      }

      ghost.style.top    = topForTime(minsToTimeStr(dragCreate.startMins)) + 'px';
      ghost.style.height = (endMins - dragCreate.startMins) * SLOT_PX + 'px';
      ghost.textContent  = `${minsToTimeStr(dragCreate.startMins)}–${minsToTimeStr(endMins)}`;
    }, { passive: false });

    document.addEventListener('pointerup', e => {
      if (!dragCreate) return;
      const { dayIdx, startMins, endMins, moved } = dragCreate;
      dragCreate = null;
      const ghost = document.getElementById('create-ghost');
      if (ghost) ghost.remove();
      showCreatePopover(dayIdx, startMins, moved ? endMins : startMins + 60, e.clientX, e.clientY);
    });

    // Escape cancels an in-progress drag
    document.addEventListener('keydown', e => {
      if (e.key === 'Escape' && dragCreate) {
        dragCreate = null;
        const ghost = document.getElementById('create-ghost');
        if (ghost) ghost.remove();
      }
    });
  }

  function init() {
    gridEl = document.getElementById('week-grid');
    if (!gridEl) return;
    gridEl.style.height = GRID_HEIGHT + 'px';
    gridEl.style.position = 'relative';

    renderDayColumns();
    renderHourLines();

    blocks = GRID_DATA;
    // Small delay so layout is settled before computing column positions
    requestAnimationFrame(() => {
      blocks.forEach(renderBlock);
    });

    // Reposition blocks whenever the grid container resizes (e.g. edit panel opening/closing)
    if (typeof ResizeObserver !== 'undefined') {
      new ResizeObserver(() => repositionAll()).observe(gridEl.parentElement || gridEl);
    }

    addGridClickHandler();

    // Keep the sticky day-header in sync when the grid is scrolled horizontally
    const headerOuter = document.getElementById('week-header-outer');
    const gridOuter   = document.getElementById('week-grid-outer');
    if (headerOuter && gridOuter) {
      gridOuter.addEventListener('scroll', () => {
        headerOuter.scrollLeft = gridOuter.scrollLeft;
      }, { passive: true });
    }
  }

  function updateBlock(blockData) {
    const idx = GRID_DATA.findIndex(b => b.id === blockData.id);
    if (idx >= 0) GRID_DATA[idx] = blockData; else GRID_DATA.push(blockData);
    requestAnimationFrame(() => renderBlock(blockData));
  }

  return { init, repositionAll, updateBlock };
})();

document.addEventListener('DOMContentLoaded', () => GRID.init());
