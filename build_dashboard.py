"""Genererer dashboard/index.html for kommer-for-salg-monitor."""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from scraper.database import (
    get_latest_snapshots, get_recent_changes, get_cached_geocode, _NOT_FOUND,
)

OUT_DIR = Path(__file__).parent / "dashboard"
OUT_FILE = OUT_DIR / "index.html"


def build_data() -> dict:
    snapshots = get_latest_snapshots()

    projects = []
    for s in snapshots:
        lat = lng = None
        if s["address"]:
            cached = get_cached_geocode(s["address"])
            if cached is not None and cached is not _NOT_FOUND:
                lat = cached["lat"]
                lng = cached["lng"]

        projects.append({
            **s,
            "lat": lat,
            "lng": lng,
        })

    projects.sort(key=lambda p: (p["municipality"] or "", p["title"] or ""))

    # Endringer på tvers av alle prosjekter
    changes_week = get_recent_changes(days_back=7)
    changes_month = get_recent_changes(days_back=30)

    return {
        "updated": projects[0]["scraped_at"][:10] if projects else None,
        "projects": projects,
        "changes_week": changes_week,
        "changes_month": changes_month,
    }


HTML_TEMPLATE = r"""<!DOCTYPE html>
<html lang="nb">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Kommer for salg — store byer</title>
<script src="https://cdnjs.cloudflare.com/ajax/libs/xlsx/0.18.5/xlsx.full.min.js"></script>
<link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css" />
<script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
<style>
  :root {
    --bg: #ffffff;
    --bg-secondary: #f5f4ee;
    --bg-tertiary: #faf9f4;
    --text: #1a1a1a;
    --text-muted: #6b6b6b;
    --text-faint: #999;
    --border: #e5e3dc;
    --accent: #185fa5;
    --success: #0f6e56;
    --warning: #854f0b;
    --danger: #a32d2d;
  }
  @media (prefers-color-scheme: dark) {
    :root {
      --bg: #1a1a1a;
      --bg-secondary: #252525;
      --bg-tertiary: #1e1e1e;
      --text: #e8e8e8;
      --text-muted: #a0a0a0;
      --text-faint: #707070;
      --border: #353535;
      --accent: #85B7EB;
      --success: #5DCAA5;
      --warning: #EF9F27;
      --danger: #F09595;
    }
  }
  * { box-sizing: border-box; }
  body {
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", system-ui, sans-serif;
    background: var(--bg); color: var(--text);
    margin: 0; padding: 1.5rem; line-height: 1.5;
  }
  .container { max-width: 1300px; margin: 0 auto; }
  h1 { font-size: 22px; font-weight: 500; margin: 0; }
  h2 { font-size: 16px; font-weight: 500; margin: 0 0 12px; }
  .header { display: flex; align-items: baseline; justify-content: space-between;
            margin-bottom: 1.5rem; flex-wrap: wrap; gap: 8px; }
  .updated { font-size: 13px; color: var(--text-muted); margin: 4px 0 0; }
  .stats { display: grid; grid-template-columns: repeat(auto-fit, minmax(160px, 1fr));
           gap: 12px; margin-bottom: 1.5rem; }
  .stat { background: var(--bg-secondary); border-radius: 8px; padding: 1rem; }
  .stat-label { font-size: 13px; color: var(--text-muted); margin: 0; }
  .stat-value { font-size: 24px; font-weight: 500; margin: 4px 0 0; }
  .card { background: var(--bg); border: 1px solid var(--border); border-radius: 12px;
          padding: 1rem 1.25rem; margin-bottom: 1.5rem; }
  .controls { display: flex; gap: 8px; margin-bottom: 12px; flex-wrap: wrap; }
  .controls select, .controls input {
    font-size: 13px; padding: 6px 10px; background: var(--bg-secondary);
    color: var(--text); border: 1px solid var(--border); border-radius: 6px;
  }
  table { width: 100%; font-size: 13px; border-collapse: collapse; }
  th { text-align: left; padding: 8px 6px; font-weight: 500; color: var(--text-muted);
       border-bottom: 1px solid var(--border); font-size: 11px; text-transform: uppercase;
       letter-spacing: 0.04em; }
  th.num, td.num { text-align: right; font-variant-numeric: tabular-nums; }
  td { padding: 10px 6px; border-bottom: 1px solid var(--border); vertical-align: top; }
  td.muni { font-size: 11px; color: var(--text-faint); text-transform: uppercase;
            letter-spacing: 0.04em; }
  a { color: var(--accent); text-decoration: none; }
  a:hover { text-decoration: underline; }
  .empty { color: var(--text-muted); padding: 2rem; text-align: center; }
  .footer { font-size: 12px; color: var(--text-faint); margin-top: 2rem; text-align: center; }
  .map-toggle {
    font-size: 13px; padding: 6px 12px; background: var(--bg-secondary);
    color: var(--text); border: 1px solid var(--border);
    border-radius: 6px; cursor: pointer;
  }
  .map-toggle:hover { background: var(--bg-tertiary); }
  .download-btn {
    font-size: 12px; padding: 6px 12px; background: var(--bg);
    color: var(--text); border: 1px solid var(--border);
    border-radius: 6px; cursor: pointer; margin-left: 8px;
  }
  #map-card { display: none; }
  #map-card.open { display: block; }
  #map { height: 500px; border-radius: 8px; border: 1px solid var(--border); }
  #changes-card { display: none; }
  #changes-card.open { display: block; }
  .badge {
    display: inline-block; padding: 1px 8px; font-size: 10px;
    border-radius: 8px; margin: 2px;
    background: var(--bg-secondary); color: var(--text-muted);
  }
  .badge-new { background: rgba(15, 110, 86, 0.15); color: var(--success); }
  .badge-gone { background: rgba(133, 79, 11, 0.15); color: var(--warning); }
  .badge-updated { background: rgba(24, 95, 165, 0.15); color: var(--accent); }
  .change-section { margin-bottom: 18px; }
  .change-section:last-child { margin-bottom: 0; }
  .change-section-title {
    font-size: 13px; font-weight: 500; color: var(--text-muted);
    text-transform: uppercase; letter-spacing: 0.04em;
    margin: 0 0 8px;
  }
  .stage-pill { display: inline-block; font-size: 11px; padding: 2px 8px;
                border-radius: 10px; background: var(--bg-secondary);
                color: var(--text-muted); margin-left: 6px; }
  .map-popup { font-size: 13px; min-width: 200px; }
  .map-popup .title { font-weight: 500; margin-bottom: 4px; }
  .map-popup .stat-row { color: #555; margin: 2px 0; font-size: 12px; }
  .timeline-cell { font-size: 11px; line-height: 1.4; color: var(--text-muted); }
  .timeline-cell strong { color: var(--text); font-weight: 500; }
</style>
</head>
<body>
<div class="container">
  <div class="header">
    <div>
      <h1>Kommer for salg — store byer</h1>
      <p class="updated">Oslo, Bergen, Stavanger, Trondheim, Tromsø, Drammen, Kristiansand · Sist oppdatert: <span id="updated-date">—</span></p>
    </div>
  </div>

  <div class="stats" id="stats"></div>

  <div class="card" id="map-card">
    <h2>Kart</h2>
    <div id="map"></div>
  </div>

  <div class="card" id="changes-card">
    <h2 style="display: flex; align-items: center; justify-content: space-between; gap: 8px;">
      <span>Endringer</span>
      <span style="display: flex; gap: 8px;">
        <button class="map-toggle period-btn" data-period="week">Siste uke</button>
        <button class="map-toggle period-btn" data-period="month">Siste måned</button>
        <button class="download-btn" id="changes-export-btn">Last ned (Excel)</button>
      </span>
    </h2>
    <div id="changes-content"></div>
  </div>

  <div class="card">
    <div class="controls">
      <select id="muni-filter">
        <option value="">Alle kommuner</option>
      </select>
      <input id="search" type="search" placeholder="Søk prosjekt..." style="flex: 1; min-width: 180px;">
      <button id="map-toggle" class="map-toggle">Vis kart</button>
      <button id="changes-toggle" class="map-toggle">Vis endringer</button>
      <button class="download-btn" id="all-export-btn">Last ned alle (Excel)</button>
    </div>
    <div style="overflow-x: auto;">
      <table>
        <thead>
          <tr>
            <th>Prosjekt</th>
            <th>Type</th>
            <th class="num">Soverom</th>
            <th class="num">Antall</th>
            <th>Pris</th>
            <th>Tidslinje</th>
          </tr>
        </thead>
        <tbody id="project-table"></tbody>
      </table>
    </div>
    <div id="empty-msg" class="empty" style="display:none;">Ingen prosjekter matcher filteret.</div>
  </div>

  <p class="footer">
    Genereret automatisk fra Finn.no kommer-for-salg-annonser. Endringer detekteres ved å sammenligne snapshots.
  </p>
</div>

<script>
const DATA = __DATA_PLACEHOLDER__;

function fmt(n) {
  if (n === null || n === undefined) return '–';
  return new Intl.NumberFormat('nb-NO').format(Math.round(n));
}

function escapeHtml(text) {
  if (text === null || text === undefined) return '';
  return String(text)
    .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;').replace(/'/g, '&#039;');
}

function projectsFiltered() {
  const muniFilter = document.getElementById('muni-filter').value;
  const search = document.getElementById('search').value.toLowerCase();
  return DATA.projects.filter(p => {
    if (muniFilter && p.municipality !== muniFilter) return false;
    if (search && !(p.title || '').toLowerCase().includes(search)) return false;
    return true;
  });
}

function renderStats() {
  const projects = projectsFiltered();
  const totalProjects = projects.length;
  const totalUnits = projects.reduce((s, p) => s + (p.unit_count_hint || 0), 0);
  const newCount = (DATA.changes_week.new || []).filter(p =>
    !document.getElementById('muni-filter').value || p.municipality === document.getElementById('muni-filter').value
  ).length;
  const updatedCount = (DATA.changes_week.updated || []).filter(p =>
    !document.getElementById('muni-filter').value || p.municipality === document.getElementById('muni-filter').value
  ).length;

  const muniFilter = document.getElementById('muni-filter').value;
  const scopeLabel = muniFilter || 'totalt';

  document.getElementById('stats').innerHTML = `
    <div class="stat"><p class="stat-label">Prosjekter (${escapeHtml(scopeLabel)})</p><p class="stat-value">${totalProjects}</p></div>
    <div class="stat"><p class="stat-label">Planlagte enheter</p><p class="stat-value">${fmt(totalUnits)}</p></div>
    <div class="stat"><p class="stat-label">Nye siste uke</p><p class="stat-value" style="color: var(--success);">${fmt(newCount)}</p></div>
    <div class="stat"><p class="stat-label">Endret siste uke</p><p class="stat-value" style="color: var(--accent);">${fmt(updatedCount)}</p></div>
  `;
}

function renderTable() {
  const projects = projectsFiltered();
  const body = document.getElementById('project-table');
  body.innerHTML = '';

  for (const p of projects) {
    const timeline = [
      p.sale_start ? `<div><strong>Salg:</strong> ${escapeHtml(p.sale_start)}</div>` : '',
      p.construction_start ? `<div><strong>Bygg:</strong> ${escapeHtml(p.construction_start)}</div>` : '',
      p.handover ? `<div><strong>Overtak:</strong> ${escapeHtml(p.handover)}</div>` : '',
    ].filter(Boolean).join('');

    body.insertAdjacentHTML('beforeend', `
      <tr data-finn="${p.finn_code}">
        <td>
          <div class="muni">${escapeHtml(p.municipality || '')}</div>
          <div><a href="${escapeHtml(p.project_url)}" target="_blank" rel="noopener">${escapeHtml(p.title || '—')}</a></div>
          <div style="font-size:12px;color:var(--text-faint);margin-top:2px;">${escapeHtml(p.address || '')}</div>
        </td>
        <td>${escapeHtml(p.home_type || '–')}</td>
        <td class="num">${escapeHtml(p.bedrooms_range || '–')}</td>
        <td class="num">${p.unit_count_hint ? fmt(p.unit_count_hint) : '–'}</td>
        <td>${escapeHtml(p.price_info || '–')}</td>
        <td class="timeline-cell">${timeline || '–'}</td>
      </tr>
    `);
  }

  document.getElementById('empty-msg').style.display = projects.length === 0 ? 'block' : 'none';
}

// === KART ===
let mapInstance = null, markerLayer = null, mapInitialized = false;

function toggleMap() {
  const card = document.getElementById('map-card');
  const btn = document.getElementById('map-toggle');
  if (card.classList.contains('open')) {
    card.classList.remove('open');
    btn.textContent = 'Vis kart';
    return;
  }
  card.classList.add('open');
  btn.textContent = 'Skjul kart';
  if (!mapInitialized) {
    initMap();
    mapInitialized = true;
  } else {
    setTimeout(() => mapInstance.invalidateSize(), 100);
  }
  renderMapMarkers();
}

function initMap() {
  // Senter på Sør-Norge med passende zoom for hele landet
  mapInstance = L.map('map').setView([62.0, 10.5], 5);
  L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
    maxZoom: 19, attribution: '© OpenStreetMap',
  }).addTo(mapInstance);
  markerLayer = L.layerGroup().addTo(mapInstance);
}

function colorForMuni(muni) {
  const colors = {
    'Oslo': '#1e88e5',
    'Bergen': '#43a047',
    'Stavanger': '#fb8c00',
    'Trondheim': '#8e24aa',
    'Tromsø': '#0097a7',
    'Drammen': '#e53935',
    'Kristiansand': '#5e35b1',
  };
  return colors[muni] || '#666';
}

function renderMapMarkers() {
  if (!mapInstance) return;
  markerLayer.clearLayers();
  const projects = projectsFiltered();
  const withCoords = projects.filter(p => p.lat && p.lng);

  const bounds = [];
  for (const p of withCoords) {
    const r = p.unit_count_hint ? Math.max(8, Math.min(28, Math.sqrt(p.unit_count_hint) * 3)) : 8;
    const marker = L.circleMarker([p.lat, p.lng], {
      radius: r, fillColor: colorForMuni(p.municipality),
      color: '#fff', weight: 1.5, opacity: 1, fillOpacity: 0.75,
    });
    marker.bindPopup(`
      <div class="map-popup">
        <div class="title">${escapeHtml(p.title || '')}</div>
        <div class="stat-row"><strong>${escapeHtml(p.municipality || '')}</strong> · ${escapeHtml(p.home_type || '')}</div>
        ${p.unit_count_hint ? `<div class="stat-row">${p.unit_count_hint} planlagte enheter</div>` : ''}
        ${p.sale_start ? `<div class="stat-row">Salgsstart: ${escapeHtml(p.sale_start)}</div>` : ''}
        ${p.handover ? `<div class="stat-row">Overtakelse: ${escapeHtml(p.handover)}</div>` : ''}
        <a href="${escapeHtml(p.project_url)}" target="_blank">Åpne i Finn</a>
      </div>
    `);
    marker.addTo(markerLayer);
    bounds.push([p.lat, p.lng]);
  }

  if (bounds.length > 0) {
    mapInstance.fitBounds(bounds, {padding: [40, 40], maxZoom: 12});
  }
}

// === ENDRINGER ===
let changesOpen = false;
let currentPeriod = 'week';

function toggleChanges() {
  const card = document.getElementById('changes-card');
  const btn = document.getElementById('changes-toggle');
  changesOpen = !card.classList.contains('open');
  card.classList.toggle('open', changesOpen);
  btn.textContent = changesOpen ? 'Skjul endringer' : 'Vis endringer';
  if (changesOpen) renderChanges();
}

function getChangesForPeriod(periodKey) {
  const ch = (periodKey === 'week') ? DATA.changes_week : DATA.changes_month;
  const muniFilter = document.getElementById('muni-filter').value;
  const filterMuni = arr => muniFilter ? arr.filter(p => p.municipality === muniFilter) : arr;
  return {
    new: filterMuni(ch.new || []),
    gone: filterMuni(ch.gone || []),
    updated: filterMuni(ch.updated || []),
  };
}

function renderChanges() {
  const ch = getChangesForPeriod(currentPeriod);
  const container = document.getElementById('changes-content');

  if (!ch.new.length && !ch.gone.length && !ch.updated.length) {
    container.innerHTML = `<div class="empty">
      Ingen endringer i perioden.<br>
      <small style="color: var(--text-faint);">Endringer detekteres ved sammenligning mellom snapshots — krever flere dager med data.</small>
    </div>`;
    return;
  }

  let html = '';

  if (ch.new.length) {
    html += `<div class="change-section">
      <h3 class="change-section-title">Nye prosjekter (${ch.new.length})</h3>
      <table><thead><tr>
        <th>Prosjekt</th><th>Adresse</th><th>Type</th><th class="num">Antall</th><th>Salgsstart</th>
      </tr></thead><tbody>
      ${ch.new.map(p => `<tr>
        <td><div class="muni">${escapeHtml(p.municipality)}</div>
            <a href="${escapeHtml(p.project_url)}" target="_blank">${escapeHtml(p.title)}</a></td>
        <td>${escapeHtml(p.address || '–')}</td>
        <td>${escapeHtml(p.home_type || '–')}</td>
        <td class="num">${p.unit_count_hint || '–'}</td>
        <td>${escapeHtml(p.sale_start || '–')}</td>
      </tr>`).join('')}
      </tbody></table>
    </div>`;
  }

  if (ch.gone.length) {
    html += `<div class="change-section">
      <h3 class="change-section-title">Forsvunnet (${ch.gone.length}) — gått til salgs eller trukket</h3>
      <table><thead><tr>
        <th>Prosjekt</th><th>Adresse</th><th>Type</th><th class="num">Antall</th>
      </tr></thead><tbody>
      ${ch.gone.map(p => `<tr>
        <td><div class="muni">${escapeHtml(p.municipality)}</div>
            ${escapeHtml(p.title)}</td>
        <td>${escapeHtml(p.address || '–')}</td>
        <td>${escapeHtml(p.home_type || '–')}</td>
        <td class="num">${p.unit_count_hint || '–'}</td>
      </tr>`).join('')}
      </tbody></table>
    </div>`;
  }

  if (ch.updated.length) {
    html += `<div class="change-section">
      <h3 class="change-section-title">Oppdaterte (${ch.updated.length})</h3>
      <table><thead><tr>
        <th>Prosjekt</th><th>Felt</th><th>Gammelt</th><th>Nytt</th>
      </tr></thead><tbody>
      ${ch.updated.flatMap(p => p.changes.map(c => `<tr>
        <td><div class="muni">${escapeHtml(p.municipality)}</div>
            <a href="${escapeHtml(p.project_url)}" target="_blank">${escapeHtml(p.title)}</a></td>
        <td>${escapeHtml(c.field)}</td>
        <td>${escapeHtml(c.old || '–')}</td>
        <td><strong>${escapeHtml(c.new || '–')}</strong></td>
      </tr>`)).join('')}
      </tbody></table>
    </div>`;
  }

  container.innerHTML = html;
}

function exportChanges() {
  const wb = XLSX.utils.book_new();
  for (const [key, label] of [['week', 'Siste uke'], ['month', 'Siste måned']]) {
    const ch = getChangesForPeriod(key);

    if (ch.new.length) {
      const rows = [['Kommune', 'Prosjekt', 'Adresse', 'Type', 'Soverom', 'Antall', 'Salgsstart', 'Byggestart', 'Overtakelse']];
      for (const p of ch.new) {
        rows.push([p.municipality, p.title, p.address, p.home_type, p.bedrooms_range,
                   p.unit_count_hint, p.sale_start, p.construction_start, p.handover]);
      }
      const ws = XLSX.utils.aoa_to_sheet(rows);
      ws['!cols'] = [{wch:14},{wch:30},{wch:30},{wch:14},{wch:10},{wch:8},{wch:18},{wch:18},{wch:18}];
      XLSX.utils.book_append_sheet(wb, ws, `Nye - ${label}`);
    }

    if (ch.updated.length) {
      const rows = [['Kommune', 'Prosjekt', 'Felt', 'Gammel verdi', 'Ny verdi']];
      for (const p of ch.updated) {
        for (const c of p.changes) {
          rows.push([p.municipality, p.title, c.field, c.old, c.new]);
        }
      }
      const ws = XLSX.utils.aoa_to_sheet(rows);
      ws['!cols'] = [{wch:14},{wch:30},{wch:18},{wch:24},{wch:24}];
      XLSX.utils.book_append_sheet(wb, ws, `Endringer - ${label}`);
    }
  }
  if (wb.SheetNames.length === 0) {
    alert('Ingen endringer å eksportere.');
    return;
  }
  XLSX.writeFile(wb, `kommer-for-salg-endringer-${DATA.updated || ''}.xlsx`);
}

function exportAll() {
  const projects = projectsFiltered();
  const rows = [['Kommune', 'Prosjekt', 'Undertittel', 'Adresse', 'Type', 'Soverom',
                 'Antall enheter', 'Eieform', 'Pris', 'Salgsstart', 'Byggestart', 'Overtakelse',
                 'Sist endret', 'Finn-kode', 'URL']];
  for (const p of projects) {
    rows.push([p.municipality, p.title, p.subtitle, p.address, p.home_type,
               p.bedrooms_range, p.unit_count_hint, p.ownership, p.price_info,
               p.sale_start, p.construction_start, p.handover, p.last_modified,
               p.finn_code, p.project_url]);
  }
  const wb = XLSX.utils.book_new();
  const ws = XLSX.utils.aoa_to_sheet(rows);
  ws['!cols'] = [{wch:14},{wch:32},{wch:40},{wch:30},{wch:14},{wch:10},
                 {wch:8},{wch:12},{wch:18},{wch:18},{wch:18},{wch:18},{wch:18},{wch:12},{wch:50}];
  XLSX.utils.book_append_sheet(wb, ws, 'Kommer for salg');
  XLSX.writeFile(wb, `kommer-for-salg-${DATA.updated || ''}.xlsx`);
}

function init() {
  document.getElementById('updated-date').textContent = DATA.updated || '—';

  const sel = document.getElementById('muni-filter');
  const munis = [...new Set(DATA.projects.map(p => p.municipality).filter(Boolean))].sort();
  for (const m of munis) {
    sel.insertAdjacentHTML('beforeend', `<option value="${m}">${m}</option>`);
  }

  function update() {
    renderStats();
    renderTable();
    if (mapInitialized) renderMapMarkers();
    if (changesOpen) renderChanges();
  }

  sel.addEventListener('change', update);
  document.getElementById('search').addEventListener('input', update);
  document.getElementById('map-toggle').addEventListener('click', toggleMap);
  document.getElementById('changes-toggle').addEventListener('click', toggleChanges);
  document.getElementById('all-export-btn').addEventListener('click', exportAll);
  document.getElementById('changes-export-btn').addEventListener('click', exportChanges);

  document.querySelectorAll('.period-btn').forEach(btn => {
    btn.addEventListener('click', () => {
      currentPeriod = btn.dataset.period;
      document.querySelectorAll('.period-btn').forEach(b => b.classList.toggle('active', b === btn));
      renderChanges();
    });
  });
  document.querySelector('.period-btn[data-period="week"]').classList.add('active');

  update();
}

document.addEventListener('DOMContentLoaded', init);
</script>
</body>
</html>
"""


def main():
    OUT_DIR.mkdir(exist_ok=True)
    data = build_data()
    html = HTML_TEMPLATE.replace("__DATA_PLACEHOLDER__", json.dumps(data, ensure_ascii=False))
    OUT_FILE.write_text(html, encoding="utf-8")
    print(f"Skrev {OUT_FILE} ({OUT_FILE.stat().st_size:,} bytes)")
    print(f"  {len(data['projects'])} prosjekter, oppdatert {data['updated']}")


if __name__ == "__main__":
    main()
