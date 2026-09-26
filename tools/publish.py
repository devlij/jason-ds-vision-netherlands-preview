#!/usr/bin/env python3
"""Write manifests, Candidate approvals, and the Netherlands gallery page."""

from __future__ import annotations

import hashlib
import json
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from composite_masters import COPYRIGHT, DESCRIPTION, SOFTWARE, TITLE, COMMENT, composite_one

ROOT = Path(__file__).resolve().parents[1]
SITE = "https://devlij.github.io/jason-ds-vision-netherlands-preview/"
SIG = "Jason D\u2019s Vision"


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    h.update(path.read_bytes())
    return h.hexdigest()


MONTHS = [
    "",
    "January",
    "February",
    "March",
    "April",
    "May",
    "June",
    "July",
    "August",
    "September",
    "October",
    "November",
    "December",
]


def month_name_valid(label: str) -> str:
    # scenario_label is already "25 September 2026 · 18:26 Europe/Amsterdam"
    return label


def valid_display(weather: dict) -> str:
    mt = datetime.fromisoformat(weather["model_time"])
    tz_name = weather.get("timezone") or "Europe/Amsterdam"
    return f"{mt.day} {MONTHS[mt.month]} {mt.year} {mt.strftime('%H:%M')} {tz_name}"


def approval_md(row: dict, weather: dict, sha16: str, sha45: str) -> str:
    refs = "\n".join(f"  {i}. {url}" for i, url in enumerate(row["references"], 1))
    anchors = "\n".join(f"  {i}. {text}" for i, text in enumerate(row["anchors"], 1))
    hour = weather["retrieval_timestamp"][11:13]
    valid_display_text = valid_display(weather)
    sky_words = {
        0: "Clear sky",
        1: "Mainly clear",
        2: "Partly cloudy",
        3: "Overcast",
    }.get(weather["weather_code"], "Model sky")
    return f"""# {row['entry_id']} — {row['caption']}

approval_status: Candidate

This note is an internal checklist for Cosmo QC. It does not approve the scene.

## Evidence card

- **Location / caption:** {row['caption']}
- **Camera viewpoint:** {row['viewpoint']}
- **Reference links:**
{refs}
- **Geometry anchors:**
{anchors}
- **Weather:** Model data from Open-Meteo, retrieved {weather['retrieval_display']}, valid {valid_display_text} (model-valid hour {hour}:00–{hour}:59) — not a verified on-site observation. {sky_words} (WMO code {weather['weather_code']}), cloud cover {weather['cloud_cover']}%, about {weather['temperature_2m']}°C, wind about {weather['wind_speed_10m']} km/h, precipitation {weather['precipitation']} mm, model is_day {weather['is_day']}. Provider: Open-Meteo. Request coordinates: {weather['latitude']}, {weather['longitude']}.
- **Retrieval timestamp (unique to the second):** {weather['retrieval_timestamp']}
- **Model time from this retrieval:** {weather['model_time']} ({weather['timezone']}, interval {weather['model_interval_seconds']} seconds)
- **Scenario:** Scenario: {weather['scenario_label']}. The scenario minute sits inside the model-valid hour of this scene's own retrieval.
- **Solar / time of day:** {row['solar']}
- **Independent description:** {row['description']}
- **Source-use notes:** Text-prompt-only lineage. No photographic reference was supplied to the generator. The two reference links were consulted for arrangement only. Caption, scenario line, disclosure, and the signature {SIG} were drawn onto a gradient scrim after generation. No credit is required. These notes are not a legal certification.

## Gates

1. Visual/location — internal checklist met on review. Still Candidate.
2. Technical — masters are 1920×1080 and 864×1080, with caption, scenario, disclosure, and signature on a gradient scrim.
3. Originality/provenance — text-prompt-only. No photographic input.
4. Commercial/IP — no prominent identifiable people, no focal logos, and no copyrighted artwork as the subject. Internal review only, not a legal certification.
5. Publication readiness — caption, scenario, signature, and disclosure are present. Awaiting Cosmo QC.

## Masters

- `library/world/Netherlands/{row['folder']}/{row['entry_id'].lower()}-16x9.png`
- `library/world/Netherlands/{row['folder']}/{row['entry_id'].lower()}-4x5.png`
- SHA-256 16:9: `{sha16}`
- SHA-256 4:5: `{sha45}`

## EU AI Act Art. 50

Metadata only, on both masters:

- Title (iTXt): {TITLE}
- Description (tEXt): {DESCRIPTION}
- Copyright (iTXt): {COPYRIGHT}
- Software (tEXt): {SOFTWARE}
- Comment (tEXt): {COMMENT}
"""


PAGE = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8"/>
<script async src="https://www.googletagmanager.com/gtag/js?id=G-FPVHCRLKD2"></script>
<script>
  window.dataLayer = window.dataLayer || [];
  function gtag(){dataLayer.push(arguments);}
  gtag('js', new Date());
  gtag('config', 'G-FPVHCRLKD2');
</script>
<meta name="viewport" content="width=device-width, initial-scale=1"/>
<title>Jason D’s Vision — Netherlands</title>
<link rel="canonical" href="https://devlij.github.io/jason-ds-vision-netherlands-preview/"/>
<meta name="description" content="AI-generated artistic interpretations of the Netherlands. Free to use, no credit required."/>
<meta name="robots" content="index, follow"/>
<meta property="og:type" content="website"/>
<meta property="og:site_name" content="Jason D's Vision"/>
<meta property="og:title" content="Jason D's Vision — Netherlands"/>
<meta property="og:description" content="AI-generated artistic interpretations of the Netherlands. Free to use, no credit required."/>
<meta property="og:image" content="https://devlij.github.io/jason-ds-vision-netherlands-preview/library/world/Netherlands/Amsterdam/nl-01-001-16x9.png"/>
<meta property="og:url" content="https://devlij.github.io/jason-ds-vision-netherlands-preview/"/>
<meta name="twitter:card" content="summary_large_image"/>
<meta name="twitter:title" content="Jason D's Vision — Netherlands"/>
<meta name="twitter:description" content="AI-generated artistic interpretations of the Netherlands. Free to use, no credit required."/>
<meta name="twitter:image" content="https://devlij.github.io/jason-ds-vision-netherlands-preview/library/world/Netherlands/Amsterdam/nl-01-001-16x9.png"/>
<script type="application/ld+json">
{
  "@context": "https://schema.org",
  "@graph": [
    {
      "@type": "WebSite",
      "name": "Jason D’s Vision — Netherlands",
      "url": "https://devlij.github.io/jason-ds-vision-netherlands-preview/",
      "inLanguage": "en"
    },
    {
      "@type": "Organization",
      "name": "Jason D's Vision",
      "url": "https://jdvision.org/"
    }
  ]
}
</script>
<style>
    :root {
      --bg:#0d1522; --card:#14202f; --text:#eef2f7; --muted:#9db0c6; --accent:#e8722a; --line:#26394f;
    }
    * { box-sizing: border-box; }
    body {
      margin: 0;
      font-family: "Segoe UI", system-ui, -apple-system, sans-serif;
      background: var(--bg);
      color: var(--text);
      line-height: 1.5;
    }
    a { color: var(--accent); }
    header, main, footer, .promise, #license {
      max-width: 1100px;
      margin: 0 auto;
      padding: 1.25rem 1.25rem;
    }
    .pointer {
      font-size: 0.95rem;
      color: var(--muted);
      border-bottom: 1px solid var(--line);
      padding-bottom: 1rem;
    }
    h1 {
      font-size: 1.75rem;
      font-weight: 650;
      margin: 1.25rem 0 0.35rem;
      letter-spacing: 0.01em;
      display: flex;
      align-items: center;
    }
    .country-switch {
      margin: 0.15rem 0 0.85rem;
      font-size: 0.95rem;
      color: var(--muted);
      letter-spacing: 0.01em;
    }
    .country-switch a { color: var(--accent); text-decoration: none; }
    .country-switch a:hover { text-decoration: underline; }
    .country-switch [aria-current="page"] { color: var(--text); font-weight: 600; }
    .country-switch .sep { margin: 0 0.45rem; color: var(--line); }
    .sub { color: var(--muted); margin: 0 0 1.5rem; }
    .promise h2, #license h2 { font-size: 1.2rem; margin-top: 2rem; }
    .promise p, #license p { color: var(--muted); max-width: 70ch; }
    .toolbar {
      display: flex; flex-wrap: wrap; gap: 0.75rem; align-items: center; margin: 1.5rem 0 1rem;
    }
    .toolbar input, .toolbar select {
      background: var(--card); color: var(--text); border: 1px solid var(--line);
      border-radius: 8px; padding: 0.55rem 0.75rem; font: inherit;
    }
    .toolbar input { flex: 1 1 220px; min-width: 180px; }
    .toolbar button {
      background: transparent; color: var(--muted); border: 1px solid var(--line);
      border-radius: 8px; padding: 0.55rem 0.9rem; cursor: pointer; font: inherit;
    }
    .toolbar button:hover { color: var(--text); border-color: var(--muted); }
    #result-count { color: var(--muted); font-size: 0.9rem; }
    #no-results { display: none; color: var(--muted); padding: 2rem 0; text-align: center; }
    .grid {
      display: grid; grid-template-columns: repeat(auto-fill, minmax(320px, 1fr));
      gap: 1.25rem; margin-bottom: 2rem;
    }
    .card {
      background: var(--card); border: 1px solid var(--line); border-radius: 14px;
      overflow: hidden; display: flex; flex-direction: column;
    }
    .preview { position: relative; }
    .fmt-tabs {
      position: absolute; top: 1.05rem; left: 1.05rem; display: flex; gap: 6px; z-index: 2;
    }
    .fmt-tab {
      background: rgba(20, 32, 47, 0.85); color: var(--text); border: 1px solid var(--line);
      border-radius: 8px; padding: 5px 10px; font: inherit; font-size: 12px; line-height: 1.2; cursor: pointer;
    }
    .fmt-tab:hover { border-color: var(--muted); }
    .fmt-tab.is-active {
      background: var(--accent); border-color: var(--accent); color: var(--bg); font-weight: 700;
    }
    .actions button.day-tab {
      display: inline-block; background: #243049; color: var(--text);
      border-radius: 8px; padding: 0.4rem 0.7rem; font-size: 0.85rem; border: 1px solid var(--line);
      cursor: pointer;
    }
    .actions button.day-tab:hover { border-color: var(--accent); }
    .actions button.day-tab.is-active {
      background: #e8b23a; border-color: #e8b23a; color: #1a1405; font-weight: 700;
    }
    .view-affordance {
      position: absolute; top: 1.05rem; right: 1.05rem; z-index: 2;
      padding: 5px 10px; border: 1px solid rgba(255, 255, 255, 0.35); border-radius: 999px;
      background: rgba(20, 32, 47, 0.72); color: var(--text); font-size: 11px; pointer-events: none;
    }
    .thumb {
      display: block; padding: 0.65rem 0.65rem 0; background: #101820; line-height: 0;
    }
    .thumb img {
      width: 100%; height: auto; display: block; border-radius: 8px; background: #000;
      aspect-ratio: 16 / 9; object-fit: contain;
    }
    .thumb.tall img { aspect-ratio: 4 / 5; }
    .card-body { padding: 1rem 1rem 1.15rem; display: flex; flex-direction: column; gap: 0.35rem; flex: 1; }
    .entry-id { font-size: 0.75rem; letter-spacing: 0.06em; text-transform: uppercase; color: var(--accent); }
    .status-row { display: flex; flex-wrap: wrap; gap: 0.45rem; align-items: center; }
    .status {
      display: inline-block; font-size: 0.72rem; letter-spacing: 0.04em; text-transform: uppercase;
      border-radius: 999px; padding: 0.2rem 0.55rem; border: 1px solid var(--line); color: var(--muted);
    }
    .status.approved { color: var(--accent); border-color: var(--accent); }
    .qc-count { font-size: 0.85rem; color: var(--muted); margin: 0.3rem 0 0; }
    .caption { font-size: 1.05rem; font-weight: 600; margin: 0; }
    .scenario, .composition, .detail { font-size: 0.85rem; color: var(--muted); margin: 0; }
    .detail { font-size: 0.92rem; color: #d7dde8; margin: 0.35rem 0 0; }
    .actions { display: flex; flex-wrap: wrap; gap: 0.5rem; margin-top: 0.85rem; align-items: center; }
    .actions a.download {
      display: inline-block; text-decoration: none; background: #1c3148; color: var(--text);
      border-radius: 8px; padding: 0.4rem 0.7rem; font-size: 0.85rem; border: 1px solid var(--line);
    }
    .actions a.download:hover { border-color: var(--accent); }
    .badge {
      display: inline-block; font-size: 0.75rem; color: var(--bg); background: var(--accent);
      border-radius: 999px; padding: 0.25rem 0.6rem; text-decoration: none; font-weight: 600;
    }
    footer {
      border-top: 1px solid var(--line); color: var(--muted); font-size: 0.9rem; padding-bottom: 2.5rem;
    }
    footer .sig { color: var(--text); font-weight: 600; }
    .flag-band{height:6px;background:linear-gradient(to bottom,#AE1C28 0 33.34%,#ffffff 0 66.67%,#21468B 0)}
    .flag{display:inline-block;width:46px;height:31px;border-radius:4px;vertical-align:-6px;margin-right:12px;box-shadow:0 0 0 1px rgba(255,255,255,.25);overflow:hidden;flex:0 0 auto}
    .flag svg{display:block;width:100%;height:100%}
    .flag-chip{display:inline-block;width:22px;height:15px;border-radius:2px;vertical-align:-2px;margin-right:6px;box-shadow:0 0 0 1px rgba(255,255,255,.2);overflow:hidden}
    .flag-chip svg{display:block;width:100%;height:100%}
    .flag-chip.flag-de{background:linear-gradient(to bottom,#000 0 33.34%,#DD0000 0 66.67%,#FFCE00 0)}
    .flag-chip.flag-it{background:linear-gradient(to right,#009246 0 33.34%,#fff 0 66.67%,#CE2B37 0)}
    .flag-chip.flag-fr{background:linear-gradient(to right,#0055A4 0 33.34%,#fff 0 66.67%,#EF4135 0)}
    .flag-chip.flag-es{background:linear-gradient(to bottom,#AA151B 0 25%,#F1BF00 0 75%,#AA151B 0)}
    .flag-chip.flag-gr{background:repeating-linear-gradient(to bottom,#0D5EAF 0 3px,#fff 0 6px)}
    .flag-chip.flag-nl{background:linear-gradient(to bottom,#AE1C28 0 33.34%,#fff 0 66.67%,#21468B 0)}
    .flag-chip.flag-ch{background:#DA291C;position:relative}
    .flag-chip.flag-dk{background:linear-gradient(to bottom,transparent 38%,#fff 38%,#fff 62%,transparent 62%),linear-gradient(to right,transparent 28%,#fff 28%,#fff 44%,transparent 44%),#C8102E}
    .flag-chip.flag-no{background:linear-gradient(#00205B,#00205B) center/100% 20% no-repeat,linear-gradient(#00205B,#00205B) center/22% 100% no-repeat,linear-gradient(#fff,#fff) center/100% 38% no-repeat,linear-gradient(#fff,#fff) center/40% 100% no-repeat,#BA0C2F}
    .lb{position:fixed;inset:0;z-index:60;display:none;align-items:center;justify-content:center;background:rgba(13,21,34,.93)}
    .lb.open{display:flex}
    .lb figure{margin:0;max-width:94vw;display:flex;flex-direction:column;align-items:center}
    .lb img{max-width:94vw;max-height:72vh;display:block;border-radius:6px}
    .lb figcaption{align-self:stretch;color:#eef2f7;font-size:14px;padding:10px 2px 0}
    .lb-nav{display:flex;align-items:center;justify-content:center;gap:20px;margin-bottom:12px}
    .lb-count{color:#9db0c6;white-space:nowrap;font-size:15px;min-width:90px;text-align:center}
    .lb-controls{display:flex;justify-content:center;margin-top:12px}
    .lb-prev,.lb-next,.lb-play{background:rgba(20,32,47,.85);color:#eef2f7;border:1px solid #26394f;border-radius:999px;width:46px;height:46px;font-size:20px;cursor:pointer;line-height:1}
    .lb-play.playing{background:#e8722a;border-color:#e8722a;color:#0d1522}
    .lb-close{position:absolute;top:14px;right:14px;background:rgba(20,32,47,.85);color:#eef2f7;border:1px solid #26394f;border-radius:999px;width:46px;height:46px;font-size:20px;cursor:pointer;line-height:1}
</style>
</head>
<body>
  <div class="flag-band" aria-hidden="true"></div>
  <header>
    <p class="pointer">Every image is free to use — no credit required. See <a href="#license">license</a> below.</p>
    <h1><span class="flag" aria-hidden="true"><svg viewBox="0 0 27 18" xmlns="http://www.w3.org/2000/svg"><rect width="27" height="18" fill="#fff"/><rect width="27" height="6" fill="#AE1C28"/><rect y="12" width="27" height="6" fill="#21468B"/></svg></span>Jason D’s Vision — Netherlands</h1>
    <p class="qc-count" id="qc-count"></p>
    <nav class="country-switch" aria-label="Country galleries">
      <span aria-current="page"><span class="flag-chip" aria-hidden="true"><svg viewBox="0 0 27 18" xmlns="http://www.w3.org/2000/svg"><rect width="27" height="18" fill="#fff"/><rect width="27" height="6" fill="#AE1C28"/><rect y="12" width="27" height="6" fill="#21468B"/></svg></span>Netherlands</span>
      <span class="sep" aria-hidden="true">|</span>
      <a href="https://germany.jdvision.org/"><span class="flag-chip flag-de" aria-hidden="true"></span>Germany</a>
      <span class="sep" aria-hidden="true">|</span>
      <a href="https://italy.jdvision.org/"><span class="flag-chip flag-it" aria-hidden="true"></span>Italy</a>
      <span class="sep" aria-hidden="true">|</span>
      <a href="https://france.jdvision.org/"><span class="flag-chip flag-fr" aria-hidden="true"></span>France</a>
      <span class="sep" aria-hidden="true">|</span>
      <a href="https://greece.jdvision.org/"><span class="flag-chip flag-gr" aria-hidden="true"></span>Greece</a>
      <span class="sep" aria-hidden="true">|</span>
      <a href="https://devlij.github.io/jason-ds-vision-spain-preview/"><span class="flag-chip flag-es" aria-hidden="true"></span>Spain</a>
      <span class="sep" aria-hidden="true">|</span>
      <a href="https://devlij.github.io/jason-ds-vision-norway-preview/"><span class="flag-chip flag-no" aria-hidden="true"></span>Norway</a>
      <span class="sep" aria-hidden="true">|</span>
      <a href="https://devlij.github.io/jason-ds-vision-denmark-preview/"><span class="flag-chip flag-dk" aria-hidden="true"></span>Denmark</a>
      <span class="sep" aria-hidden="true">|</span>
      <a href="https://devlij.github.io/jason-ds-vision-switzerland-preview/"><span class="flag-chip flag-ch" aria-hidden="true"></span>Switzerland</a>
    </nav>
    <p class="sub">The Netherlands · Candidate scenes until an independent QC pass</p>
  </header>

  <section class="promise">
    <h2>Our promise to creators</h2>
    <p>Beautiful, realistic imagery should never stand between a creator and their work. Everything in this gallery is free to use — for any purpose, forever, with no credit required. We make these images so the people doing the work always have something stunning to build on.</p>
    <p><a href="#license">Read the full license</a></p>
  </section>

  <main>
    <div class="toolbar" role="search">
      <input id="q" type="search" placeholder="Search by city, site, or region" aria-label="Search by city, site, or region" />
      <select id="region" aria-label="Filter by region">
        <option value="">All regions</option>
      </select>
      <button type="button" id="clear">Clear</button>
      <span id="result-count"></span>
    </div>
    <div id="no-results">No scenes match that search.</div>
    <div class="grid" id="grid"></div>
  </main>

  <section id="license">
    <h2>License</h2>
    <p>Every image in Jason D's Vision is free to use for any purpose — personal or commercial. No credit is required. If you'd like to credit, 'Jason D's Vision' is appreciated, but it's entirely your choice.</p>
    <p>Jason D's Vision waives its own rights in these images. This doesn't waive anyone else's rights: if an image happens to include a trademark, logo, or other third-party material, those rights still belong to their owners. All images are AI-generated artistic interpretations, not photographs, and use of an image doesn't imply endorsement by Jason D's Vision.</p>
  </section>

  <footer>
    <p>AI-generated artistic interpretations · <span class="sig">Jason D’s Vision</span></p>
  </footer>

  <script>
    const SCENES = __SCENES__;

    const grid = document.getElementById('grid');
    const q = document.getElementById('q');
    const region = document.getElementById('region');
    const clearBtn = document.getElementById('clear');
    const countEl = document.getElementById('result-count');
    const noResults = document.getElementById('no-results');

    const regions = [...new Set(SCENES.map(s => s.region))].sort();
    for (const r of regions) {
      const opt = document.createElement('option');
      opt.value = r; opt.textContent = r; region.appendChild(opt);
    }

    function esc(value) {
      return String(value ?? "").replace(/[&<>"']/g, (ch) => ({
        "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;"
      }[ch]));
    }
    function fileName(url) {
      const path = String(url).split("?")[0];
      const slash = path.lastIndexOf("/");
      return slash >= 0 ? path.slice(slash + 1) : path;
    }

    function render() {
      const query = q.value.trim().toLowerCase();
      const reg = region.value;
      const filtered = SCENES.filter(s => {
        if (reg && s.region !== reg) return false;
        if (!query) return true;
        const hay = (s.city + ' ' + s.caption + ' ' + s.region + ' ' + s.entry_id + ' ' + (s.description || '')).toLowerCase();
        return hay.includes(query);
      });
      grid.innerHTML = '';
      noResults.style.display = filtered.length ? 'none' : 'block';
      countEl.textContent = filtered.length + ' scene' + (filtered.length === 1 ? '' : 's');
      const approvedN = SCENES.filter(function (x) { return x.approval_status === "Approved"; }).length;
      const qcCountEl = document.getElementById("qc-count");
      if (qcCountEl) { qcCountEl.textContent = approvedN + " of " + SCENES.length + " independently approved · " + (SCENES.length - approvedN) + " awaiting QC"; }
      for (const s of filtered) {
        const card = document.createElement('article');
        card.className = 'card';
        const file16 = 'library/world/' + s.file_16x9;
        const file45 = 'library/world/' + s.file_4x5;
        card.innerHTML = `
          <div class="preview">
            <div class="fmt-tabs" role="group" aria-label="Image size">
              <button type="button" class="fmt-tab is-active" data-format="16x9" aria-pressed="true">16:9</button>
              <button type="button" class="fmt-tab" data-format="4x5" aria-pressed="false">4:5</button>
            </div>
            <a class="thumb" href="${esc(file16)}" target="_blank" rel="noopener">
              <img src="${esc(file16)}" alt="${esc(s.alt_text)}" loading="lazy" data-src-16="${esc(file16)}" data-src-45="${esc(file45)}"${s.file_16x9_day ? ` data-src-16-day="${esc('library/world/' + s.file_16x9_day)}" data-src-45-day="${esc('library/world/' + s.file_4x5_day)}"` : ""} />
              <span class="view-affordance">View image</span>
            </a>
          </div>
          <div class="card-body">
            <div class="status-row">
              <div class="entry-id">${esc(s.entry_id)}</div>
              <span class="status ${esc((s.approval_status || 'Candidate').toLowerCase())}">${esc(s.approval_status || 'Candidate')}</span>
            </div>
            <h3 class="caption">${esc(s.caption)}</h3>
            <p class="scenario" data-scenario="${esc(s.scenario_label)}">Scenario: ${esc(s.scenario_label)}</p>
            <p class="composition">${esc(s.composition)}</p>
            ${s.description ? `<p class="detail">${esc(s.description)}</p>` : ""}
            <div class="actions">
              <a class="badge" href="${esc(s.license_anchor)}">${esc(s.license_badge)}</a>
              <a class="download" data-dl="16x9" href="${esc(file16)}" download="${esc(fileName(file16))}">Download 16:9</a>
              <a class="download" data-dl="4x5" href="${esc(file45)}" download="${esc(fileName(file45))}">Download 4:5</a>
              ${s.file_16x9_day ? `<button type="button" class="day-tab" data-daynight="night" aria-pressed="false" title="Toggle the daylight variant">☀ Daylight</button>` : ""}
            </div>
          </div>`;
        grid.appendChild(card);
      }
    }
    grid.addEventListener('click', (event) => {
      const dtab = event.target.closest('.day-tab');
      if (dtab) {
        event.preventDefault();
        const dcard = dtab.closest('.card');
        if (!dcard) return;
        const isDay = !dtab.classList.contains('is-active');
        dtab.classList.toggle('is-active', isDay);
        dtab.setAttribute('aria-pressed', isDay ? 'true' : 'false');
        dtab.setAttribute('data-daynight', isDay ? 'day' : 'night');
        const ftab = dcard.querySelector('.fmt-tab.is-active');
        const dfmt = ftab ? ftab.getAttribute('data-format') : '16x9';
        const dlink = dcard.querySelector('a.thumb');
        const dimg = dlink && dlink.querySelector('img');
        if (dimg && dlink) {
          const dkey = dfmt === '4x5' ? (isDay ? 'data-src-45-day' : 'data-src-45') : (isDay ? 'data-src-16-day' : 'data-src-16');
          const dnext = dimg.getAttribute(dkey);
          if (dnext) { dimg.src = dnext; dlink.href = dnext; }
        }
        dcard.querySelectorAll('a.download').forEach((a) => {
          const f = a.getAttribute('data-dl');
          const dk = f === '4x5' ? (isDay ? 'data-src-45-day' : 'data-src-45') : (isDay ? 'data-src-16-day' : 'data-src-16');
          const u = dimg && dimg.getAttribute(dk);
          if (u) a.href = u;
        });
        const sc = dcard.querySelector('p.scenario');
        if (sc) sc.textContent = isDay ? '\u2600 Daylight variant \u00b7 derived from the night interpretation' : 'Scenario: ' + sc.getAttribute('data-scenario');
        return;
      }
      const tab = event.target.closest('.fmt-tab');
      if (!tab) return;
      event.preventDefault();
      const card = tab.closest('.card');
      if (!card) return;
      const fmt = tab.getAttribute('data-format');
      card.querySelectorAll('.fmt-tab').forEach((item) => {
        const on = item === tab;
        item.classList.toggle('is-active', on);
        item.setAttribute('aria-pressed', on ? 'true' : 'false');
      });
      const link = card.querySelector('a.thumb');
      const img = link && link.querySelector('img');
      if (!img || !link) return;
      const dayOn = card.querySelector('.day-tab.is-active');
      const useDay = dayOn && dayOn.getAttribute('data-daynight') === 'day';
      const next = fmt === "4x5"
        ? (useDay && img.getAttribute("data-src-45-day")) || img.getAttribute("data-src-45")
        : (useDay && img.getAttribute("data-src-16-day")) || img.getAttribute("data-src-16");
      if (next) {
        img.src = next;
        link.href = next;
      }
      link.classList.toggle('tall', fmt === '4x5');
    });
    q.addEventListener('input', render);
    region.addEventListener('change', render);
    clearBtn.addEventListener('click', () => { q.value = ''; region.value = ''; render(); });
    render();
  </script>
  <script>
(function(){
    var overlay=document.createElement('div');
    overlay.className='lb';overlay.setAttribute('aria-hidden','true');
    overlay.innerHTML='<button class="lb-close" aria-label="Close">&times;</button>'
      +'<figure><div class="lb-nav"><button class="lb-prev" aria-label="Previous image">&#8249;</button>'
      +'<span class="lb-count"></span>'
      +'<button class="lb-next" aria-label="Next image">&#8250;</button></div>'
      +'<img alt=""><figcaption><span class="lb-cap"></span></figcaption>'
      +'<div class="lb-controls"><button class="lb-play" aria-label="Play slideshow">&#9654;</button></div></figure>';
    document.body.appendChild(overlay);
    var img=overlay.querySelector('img'),cap=overlay.querySelector('.lb-cap'),count=overlay.querySelector('.lb-count');
    var playBtn=overlay.querySelector('.lb-play');
    var items=[],idx=0;
    var playing=false,timer=null;
    var INTERVAL=6000;
    var lbFormat='16x9';
    var lbDay='night';
    function visibleCards(){return Array.prototype.filter.call(document.querySelectorAll('.card'),function(c){return c.style.display!=='none';});}
    function show(i){
      items=visibleCards().map(function(c){
        var im=c.querySelector('a.thumb img');var t=c.querySelector('h3.caption');
        var src='';
        var daySrc='';
        if(im){
          if(lbDay==='day'){daySrc=(lbFormat==='4x5'?im.getAttribute('data-src-45-day'):im.getAttribute('data-src-16-day'))||'';}
          src=daySrc||(lbFormat==='4x5'?im.getAttribute('data-src-45'):im.getAttribute('data-src-16'));
        }
        if(!src){var a=c.querySelector('a.thumb');src=a?a.href:'';}
        var capT=t?t.textContent:'';
        if(daySrc)capT=capT+' \u2014 \u2600 Daylight variant';
        return{src:src,cap:capT};
      }).filter(function(x){return x.src;});
      if(!items.length)return;
      idx=(i+items.length)%items.length;
      img.src=items[idx].src;img.alt=items[idx].cap;cap.textContent=items[idx].cap;
      count.textContent=(idx+1)+' / '+items.length;
      overlay.classList.add('open');overlay.setAttribute('aria-hidden','false');document.body.style.overflow='hidden';
    }
    function setPlaying(on){playing=on;playBtn.classList.toggle('playing',on);playBtn.innerHTML=on?'&#10074;&#10074;':'&#9654;';playBtn.setAttribute('aria-label',on?'Pause slideshow':'Play slideshow');}
    function restartTimer(){if(timer)clearTimeout(timer);timer=setTimeout(tick,INTERVAL);}
    function tick(){if(!playing)return;show(idx+1);restartTimer();}
    function startSlideshow(){if(playing)return;setPlaying(true);restartTimer();}
    function stopSlideshow(){playing=false;if(timer){clearTimeout(timer);timer=null;}setPlaying(false);}
    function togglePlay(){if(playing)stopSlideshow();else startSlideshow();}
    function nav(d){show(idx+d);if(playing)restartTimer();}
    function hide(){stopSlideshow();overlay.classList.remove('open');overlay.setAttribute('aria-hidden','true');document.body.style.overflow='';}
    document.addEventListener('click',function(e){
      var a=e.target.closest?e.target.closest('a.thumb'):null;
      if(a){e.preventDefault();var cards=visibleCards();var card=a.closest('.card');var tab=card.querySelector('.fmt-tab.is-active');lbFormat=(tab&&tab.getAttribute('data-format')==='4x5')?'4x5':'16x9';var dtab=card.querySelector('.day-tab.is-active');lbDay=(dtab&&dtab.getAttribute('data-daynight')==='day')?'day':'night';show(cards.indexOf(card));return;}
      if(e.target===overlay||(e.target.closest&&e.target.closest('.lb-close')))hide();
      else if(e.target.closest&&e.target.closest('.lb-play'))togglePlay();
      else if(e.target.closest&&e.target.closest('.lb-prev'))nav(-1);
      else if(e.target.closest&&e.target.closest('.lb-next'))nav(1);
    });
    document.addEventListener('keydown',function(e){
      if(!overlay.classList.contains('open'))return;
      if(e.key==='Escape')hide();
      else if(e.key==='ArrowLeft')nav(-1);
      else if(e.key==='ArrowRight')nav(1);
      else if(e.key===' '||e.key==='Spacebar'){
        if(e.target&&e.target.tagName==='BUTTON')return;
        e.preventDefault();togglePlay();
      }
    });
  })();
  </script>
</body>
</html>
"""


def main() -> None:
    catalogue = json.loads((ROOT / "tools" / "catalogue.json").read_text())
    scenes = []
    lines = [
        "# Netherlands sequence log",
        "",
        "NL-01-001 through NL-01-224. IDs are not reused.",
        "NL-01-017 through NL-01-032: no swaps. The suggested North Holland and South Holland anchors were not already used.",
        "NL-01-033 through NL-01-048 swaps:",
        "- NL-01-033: suggested Dom Tower, Utrecht was already NL-01-010. Corrected to Oudegracht, Utrecht.",
        "- NL-01-034: Oudegracht is NL-01-033, so this slot is Schröder House, Utrecht.",
        "- NL-01-038: suggested Cube Houses, Rotterdam was already NL-01-008. Corrected to Evoluon, Eindhoven.",
        "- NL-01-044: Domburg has a beach and the Badpaviljoen, not a pier. No pier was invented.",
        "- The other suggested sites in this batch were not already used.",
        "NL-01-049 through NL-01-064: no site swaps. The suggested Limburg, Flevoland, Friesland, Groningen, Drenthe, and Kralendijk anchors were not already in the catalogue.",
        "- NL-01-053 depiction note: the Batavia replica left the Lelystad berth on 19 September 2026 for a dry dock in Amsterdam and is scheduled to return on a pontoon on 1 October 2026. The scene shows the Bataviawerf harbour without that ship.",
        "- NL-01-064 uses America/Kralendijk. Bonaire is not on Europe/Amsterdam time. The scenario minute sits inside that retrieval's model-valid hour.",
        "NL-01-065 through NL-01-080 swaps:",
        "- NL-01-066: the stepped Mount Scenery trail most visitors use starts in Windwardside, opposite the Trail Shop, not in The Bottom. This scene is the view from the road just above The Bottom, across the crater village toward the mountain. A 2026 tower project closed the Windwardside lookout and the communication-tower path, so the closed summit platform is not shown.",
        "- NL-01-073: the suggested name Berkeltoren is the Berkelpoort (Berkelruïne), a low brick water gate with two small turrets over the Berkel. It is not the tall Drogenapstoren and not the Wijnhuistoren.",
        "- NL-01-079: Madurodam is closed after midnight and the miniature city is not a public night view. Swapped to Kurhaus, The Hague, the Scheveningen beachfront hotel. Scheveningen pier remains NL-01-030 and is not this scene.",
        "- The other suggested sites in this batch were not already used. Sint Eustatius and Saba use America/Kralendijk, the same Atlantic zone as Bonaire.",
        "NL-01-081 through NL-01-096 swaps:",
        "- NL-01-081: Holwerd ferry terminal, not Lauwersoog. The Ameland ferry is not running after midnight, so the quay is empty and no ship name or operator mark is shown.",
        "- NL-01-094: the Dolfinarium facade carries brand marks, so the scene is the Vischpoort and the boulevard harbour on the Wolderwijd, a Veluwe border lake. The Dolfinarium is outside the frame.",
        "- NL-01-096: the Munsterkerk stands on Munsterplein. The Markt is a separate square, so this view is the church front, not the town hall.",
        "- The other suggested sites in this batch were not already used.",
        "NL-01-097 through NL-01-112 swaps:",
        "- NL-01-097: the Markiezenhof stands on Steenbergsestraat, a short walk from the Grote Markt, not on the market itself. The scene is the palace front. The Peperbus is not in the frame.",
        "- NL-01-098: St John's Cathedral remains NL-01-037. This scene is the Bossche Broek from the Dommel dike, with the spire only as a distant skyline. 's-Hertogenbosch has no Maas boulevard; the Dieze and the Dommel are the city waters, so that option was not used.",
        "- NL-01-101: the Sint-Martinusbasiliek stands on Grote Kerkstraat. The Maasboulevard is several streets away and is not in the frame. The tower is the 1953 square brick tower with a copper onion dome, not the lost neo-Gothic spire.",
        "- NL-01-102: the basilica fronts Kerkplein, beside the market streets. The viewpoint is Kerkplein.",
        "- NL-01-103: the square is Pancratiusplein, not a separate Raadhuisplein. The church, the rubble-stone Schelmentoren, and the glass Glaspaleis share that square.",
        "- NL-01-105: the Gevangentoren stands on Boulevard de Ruyter beside the Westerschelde. Koopmanshaven is the inner basin and is not in this frame. No restaurant name is shown.",
        "- NL-01-106: the high light is the former church tower in the village, seen from the sea dike. The nave is gone. An iron lantern replaces the old spire. The tower does not stand in the surf.",
        "- NL-01-109: the frame is the 1983 steel tied-arch railway bridge from the harbour. The 1868 truss is gone. The Binnenpoort is in the walled centre and is not in this frame.",
        "- NL-01-110: the Waterpoort and the Waal dike are the waterfront. The Grote Kerk stands on Kerkplein inside the town and is not on the river.",
        "- NL-01-111: Hotel De Wereld is the red-brick hotel on 5 Mei Plein. The Nederrijn dike is outside the centre and is not in this frame.",
        "- NL-01-112: the Ede / Otterloseweg heath edge sits against the Hoge Veluwe already represented by the Kröller-Müller Museum, Otterlo (NL-01-016), and a bare night heath would also echo Dwingelderveld (NL-01-063). Swapped to Radio Kootwijk Building A, a concrete transmitter hall on open Veluwe heath, which was not already used.",
        "- The other suggested sites in this batch were not already used.",
        "NL-01-113 through NL-01-128 swaps:",
        "- NL-01-113: the Nes ferry dam is in renovation through mid-October 2026. Exact temporary works were not pinned, so no scaffolding was invented. The scene is Waddenhaven, the yacht basin beside the terminal, not the working ferry quay. Holwerd remains NL-01-081.",
        "- NL-01-114: Brandarisplein works are planned from November 2026, so the square is not a construction site. No exterior scaffold on the tower was verified. The tower is unpainted brick with a red lantern roof, in the village, not on the beach.",
        "- NL-01-115: the yacht harbour is about 800 metres east of the village, and the Vuurduin lighthouse is in the dunes. This scene is the veerdam at Oost-Vlieland. No ferry is alongside, and no operator name is shown.",
        "- NL-01-116: the working lighthouse is the red Noordertoren in the dunes, about 3 km from the village. The white Zuidertoren in the village is a different building and is not in the frame.",
        "- NL-01-117: the Stevinsluizen stand east of the village, and the Lely statue has stood by the Vlietermonument since 2007. This frame is the fishing harbour.",
        "- NL-01-118: Breezanddijk is the geographic midpoint. The monument is the Vlietermonument at the 1932 closure, closer to Den Oever. The rest area stays closed through the works due in 2027. The restored tower is the view. The in-dike extension sits behind it and is not shown as a new wing. No scaffold is shown on the tower.",
        "- NL-01-119: the Zuiderzeemuseum remains NL-01-026. This is the Drommedaris at the Oude Haven.",
        "- NL-01-120: the castle is not a complete four-tower square. The exterior is the L-shaped wing, one round tower, and a low stump, from the public moat.",
        "- NL-01-121: the Koemarkt does not hold the carillon tower. The tower belongs to the 1912 former town hall on the Kaasmarkt. Edam’s Speeltoren remains NL-01-091.",
        "- NL-01-122: the Laurenskerk tower and the neoclassical town hall stand on Nieuwstraat, inland. This scene is the Lange Vechtbrug and the Hoogstraat quay.",
        "- NL-01-123: the university grounds are closed at this hour. The viewpoint is the public road across the moat, not the inner court.",
        "- NL-01-125: the Markt and the Gothic Stadhuis remain NL-01-031. This is the classicist Waag in the north wall of the square. The Stadhuis is behind the camera.",
        "- NL-01-126: the Nederwaard brick row remains NL-01-003. This is the thatched pair at Nieuw-Lekkerland, not the Kinderdijk avenue.",
        "- NL-01-127: the Waag stands on the Dam, not on the Haven house-row. No restaurant name is shown.",
        "- NL-01-128: the Grote Kerk fronts the Voorstraat. The Lek quay and the Lekpoort are not in this frame. The church is closed at this hour.",
        "- The other suggested sites in this batch were not already used.",
        "NL-01-129 through NL-01-144 swaps:",
        "- NL-01-129: Grote Markt and St Bavo remain NL-01-012. This is the Teylers Museum facade on the Spaarne, from the opposite quay. The church is outside the frame.",
        "- NL-01-130: the Cuypers palace facade faces Stationsplein, away from the water. This frame is the IJ side: the train-shed roof, De Ruijterkade, and the ferry quay. The twin-tower front is not shown.",
        "- NL-01-131: the lookout closes at 22:00, so the roof swing is empty. Brand letters are not shown. The caption is Overhoeks tower, Amsterdam. The EYE building is outside the frame.",
        "- NL-01-132: the glass courtyard roof is indoors, and the museum is closed at this hour. The scene is the arsenal exterior on the Oosterdok. NEMO remains NL-01-021 and is outside the frame.",
        "- NL-01-133: Hotel New York is the pier-head building. The Erasmus Bridge remains NL-01-007 and is outside the frame. No hotel name is readable.",
        "- NL-01-134: De Rotterdam is the offset glass slabs. Hotel New York is a separate scene and is outside the frame.",
        "- NL-01-135: the museum was the Gemeentemuseum until 2019 and is now the Kunstmuseum. The viewpoint is the pond walk on Stadhouderslaan. Binnenhof, Peace Palace, Scheveningen pier, and Kurhaus are other scenes.",
        "- NL-01-136: Paleis Noordeinde from the street, with the equestrian statue on the axis. Not the Binnenhof.",
        "- NL-01-137: the Burcht is the open brick ring on the mound. Rapenburg remains NL-01-013.",
        "- NL-01-138: Oostpoort is the land gate with octagonal upper stages plus the side water gate. Markt remains NL-01-011 and Oude Kerk remains NL-01-080.",
        "- NL-01-139: Grote Kerk remains NL-01-032. This is Huis Van Gijn, a straight-cornice house on Nieuwe Haven beside Wolwevershaven. The church is outside the frame.",
        "- NL-01-140: the Beatrix Theatre is a hall inside the Beatrixgebouw, whose public face carries changing advertising, so that exterior was not used. Schröder House remains NL-01-034 and the Dom Tower remains NL-01-010. This is Domplein looking east at the Domkerk’s unfinished west wall, with the tower behind the camera.",
        "- NL-01-141: Breda Castle remains NL-01-039. The Begijnhof was unused, and the requested frame is the Mastbos edge near Ginneken. Late September: trees still in leaf, a little early yellow, no flower display.",
        "- NL-01-142: Evoluon remains NL-01-038. The recognizable exterior is the white Lichttoren. No company wordmark is shown.",
        "- NL-01-143: Helpoort is coal sandstone with two round towers, not a brick gate. Vrijthof remains NL-01-014 and Saint Servatius remains NL-01-049.",
        "- NL-01-144: Martinitoren remains NL-01-060. This is Forum from the west side, so the church tower is behind the camera.",
        "- The other suggested sites in this batch were not already used.",
        "NL-01-145 through NL-01-160 swaps:",
        "- NL-01-145: Fort Oranje remains NL-01-065. This is The Quill cone from Lower Town, not the crater trail and not the fort.",
        "- NL-01-146: the salt pans remain NL-01-067. Lac Bay is the lagoon. Night water is dark. No resort name is shown.",
        "- NL-01-147: The Bottom remains NL-01-066. The 2026 tower project closed the Windwardside lookout and the communication-tower path, so the closed summit is not shown. This is the village of white houses and red roofs.",
        "- NL-01-148: the renovation finished and the tower reopened in April 2026, so no scaffold is shown. The tower is octagonal brick with an open lantern, not a church.",
        "- NL-01-149: the house moat was filled and only the main wing plus one reconstructed round tower remain. It is not a four-tower water castle. No hotel name is shown.",
        "- NL-01-150: Dwingelderveld remains NL-01-063. This is the white dish in the forest clearing. The hour's exact pointing was not retrieved, so the elevation is not claimed as a measurement.",
        "- NL-01-151: the view from the footbridge shows the three timber kitchens over the Damsterdiep. The church is not the subject.",
        "- NL-01-152: the stone west tower was taken down in 1842. The scene is the low Bentheimer hall and the small wooden ridge turret. A tall tower was not invented.",
        "- NL-01-153: Kinderdijk remains NL-01-003, Zaanse Schans remains NL-01-004, and the Nieuw-Lekkerland pair remains NL-01-126. These are the tall brick stage mills on the urban canal in Schiedam.",
        "- NL-01-154: the beach remains NL-01-088. The barrier is in its normal open state, with the north arm parked in its dock and the channel clear. It is not shown swung shut. The Keringhuis interior is closed at this hour.",
        "- NL-01-155: Prinsengracht remains NL-01-002. This is the white wooden bridge on the Amstel.",
        "- NL-01-156: Grote Markt remains NL-01-012 and Teylers Museum remains NL-01-129. The mill on the Spaarne is a separate frame. The museum is closed at this hour.",
        "- NL-01-157: John Frost Bridge remains NL-01-046 and Sonsbeek remains NL-01-074. The tower keeps the 1964 octagonal crown and the two glass balconies. The lost 1650 cupola is not restored. No cartoon sculpture is used as a subject. The church is closed, so the balconies are empty.",
        "- NL-01-158: the other Zeeland scenes are on Walcheren, Schouwen, and Zuid-Beveland. This is the Hulst basilica in Zeeuws-Vlaanderen. The crown is the 1957 concrete spire, not a medieval needle.",
        "- NL-01-159: Vrijthof remains NL-01-014, Saint Servatius remains NL-01-049, and Helpoort remains NL-01-143. The bridge has seven limestone arches and a steel lift span at the Wyck end. The old gatehouses are gone. The basilica is behind the camera.",
        "- NL-01-160: the other North Brabant churches and towers are different scenes. This is the neoclassical basilica, dome and columned facade, seen from the market. The interior is closed.",
        "- The other suggested sites in this batch were not already used.",
        "NL-01-161 through NL-01-176 swaps:",
        "- NL-01-161: the Westerkerk vista remains inside Prinsengracht, Amsterdam (NL-01-002). This is the Waterpoort in Sneek, two octagonal towers and the gatehouse over the water, not a land gate.",
        "- NL-01-162: the pumping-station interior is closed. The frame is the brick halls and the separate chimney from the dike. It is not a windmill.",
        "- NL-01-163: the museum is closed. The view is the rectangular baroque house across the moat, not a keep. Late September night: no rose tunnel and no spring bulbs.",
        "- NL-01-164: Martinitoren remains NL-01-060 and Forum remains NL-01-144. This is the canal pavilions from the station side. No exhibition art and no lettering.",
        "- NL-01-165: Giethoorn remains NL-01-006. Orvelte has no canal as the subject. The central brink was reshaped in the 1960s and some farms were moved here. The scene shows the village as it stands, thatched hall-farms, late September leaf, no snow.",
        "- NL-01-166: Twickel estate walks close at sunset, so that castle was not used. This is the Grote Kerk on the public Oude Markt. The spire is the 1926–28 stone spire, not the octagonal lantern added after the 1862 fire. The church windows are the wide round arches from that repair.",
        "- NL-01-167: Huis Doorn is closed at this hour, so the house was not used. This is the Cuneratoren from the church square. The Dom Tower remains NL-01-010. The present brick tower and spire follow the later restorations. A lost crown is not rebuilt.",
        "- NL-01-168: Breda Castle remains NL-01-039. This is the Grote Kerk. The crown is the 1702 slate spire with an open lantern, not the Gothic needle lost in 1694.",
        "- NL-01-169: Erasmus Bridge, Cube Houses, Markthal, Euromast, Hotel New York, and De Rotterdam are other scenes. This is the Laurenskerk. The wooden spire is gone. The stone crown dates from after 1646. The church is closed.",
        "- NL-01-170: the windmill at the head of the harbour is the 1986–87 reconstruction, not a surviving medieval mill. The small church is the Pelgrimvaderskerk on the Aelbrechtskolk. No brewery name is shown.",
        "- NL-01-171: Middelburg Abbey and Lange Jan remain NL-01-040, on Abdijplein. This is the Stadhuis on the Markt. The tower is the one called Malle Betje, with an octagonal lantern.",
        "- NL-01-172: the interior is closed except on heritage days. The frame is the round 13th-century keep and the later wings from the street. No hotel name is shown. The white church across the street is not the subject.",
        "- NL-01-173: Katwijk remains NL-01-089 and Noordwijk remains NL-01-090. This is the white round tower at Egmond aan Zee, with the concrete watch room under a grey lantern and a low memorial base. The demolished south tower is not shown.",
        "- NL-01-174: Valkenburg Castle remains NL-01-050. This is Hoensbroek from the moat. The museum is closed. Two square towers with onion roofs flank the bridge, and the round keep stands at the rear.",
        "- NL-01-175: the restoration finished and the castle reopened on 19 September 2026, so no scaffold is shown. The medieval round tuff donjon is gone. The main tower is square. The round towers are on the outer bailey. The interior collection is not shown.",
        "- NL-01-176: uses America/Kralendijk. The salt pans remain NL-01-067. This is the Willemstoren and the dark sea. The glass lantern house was removed; a small beacon sits on the gallery. Night water is not shown pink. No company mark is shown.",
        "- The other suggested sites in this batch were not already used.",
        "NL-01-177 through NL-01-192 swaps:",
        "- NL-01-177: Poldertoren remains NL-01-148. Nagele is the flat-roof modernist village on the Noordoostpolder. The museum is the former Catholic church on the rectangular green. It is closed at this hour. The houses keep flat roofs. No traditional gables were added.",
        "- NL-01-178: Almere had no earlier scene. This is the Cees Dam city hall from Stadhuisplein. It is not a tower by another architect. The round council chamber sits over the entrance between two five-storey wings. The later curved glass wing is on the far side and is not the front in this frame. The offices are closed. No wordmark is shown.",
        "- NL-01-179: Hunebed D27 remains NL-01-062. This is D53 at Havelte, the long chamber north of Hunebeddenweg, with the porch still in place. D54 across the road is not the subject.",
        "- NL-01-180: Orvelte remains NL-01-165. The museum and the ticketed cottage are closed. The scene is the public colony road, brick fronts and wooden barn rears. Late September leaf, no snow.",
        "- NL-01-181: the canal beside the church was filled, so the tower stands on dry Kerkplein. The cupola replaced the spire in 1827. A needle spire was not restored. The church is closed.",
        "- NL-01-182: Giethoorn remains NL-01-006. This is the Havenkolk, brick merchant houses around the basin, and the 1912–13 lock with its drawbridge. No thatched canal village. No restaurant name is shown.",
        "- NL-01-183: Blokzijl remains NL-01-182. The Oldehuis castle was demolished in the 19th century and is not rebuilt. The oval harbour is the old moat. The Grote Kerk has a detached squat tower on the east side.",
        "- NL-01-184: the Grote Kerk at Enschede remains NL-01-166. This is one Bentheim sandstone west tower, not a pair of towers. The church is closed.",
        "- NL-01-185: Menkemaborg remains NL-01-163. The museum is closed. Two front towers were removed after 1781 and are not restored. The off-centre tower changes from square to octagon, with a wooden spire, and the two bells hang on iron arms outside the tower. No cafe name is shown.",
        "- NL-01-186: the museum is closed. Three medieval brick wings remain. The west front was lost after 1755 and is not drawn as a fourth medieval wing. The viewpoint is the brick south church.",
        "- NL-01-187: the Waterpoort at Sneek remains NL-01-161. This is the Lemsterpoort, a single yellow-brick arch of 1821, not two octagonal towers. The land gates are gone. The octagonal stage mill stands on the bastion beside the gate.",
        "- NL-01-188: the 1610 scroll gable is gone. The street front is the 1835 cornice facade, with the Justitia figure on the pediment and an open bell cupola. The interior is closed.",
        "- NL-01-189: uses America/Kralendijk. The Bottom remains NL-01-066 and Windwardside remains NL-01-147. This is Fort Bay, the only harbour, concrete piers under the cliff. The harbour office is closed. No ferry is alongside, and no operator name is shown.",
        "- NL-01-190: uses America/Kralendijk. Fort Oranje remains NL-01-065 and The Quill remains NL-01-145. This is Lower Town, partial brick and stone warehouse walls along the bay. The row is not restored to a complete 18th-century street. No hotel name is shown.",
        "- NL-01-191: uses America/Kralendijk. The salt pyramids remain NL-01-067 and the Willemstoren remains NL-01-176. These are the small white coral-stone huts at Witte Pan, with the larger overseer’s house. Night pans are dark, not pink.",
        "- NL-01-192: Zoutkamp remains NL-01-082 and Holwerd remains NL-01-081. The last ferry has gone. The quay is empty. No ship name and no operator mark are shown.",
        "- The other suggested sites in this batch were not already used.",
        "NL-01-193 through NL-01-208 swaps:",
        "- NL-01-193: the fishing harbour remains NL-01-054. This is the white lighthouse on the dike, with a red lantern and a copper dome. The basin is not in the frame.",
        "- NL-01-194: Almere already has a city hall. This is the timber visitor barn at Kitsweg in Lelystad, glass gable and a small lookout box. It is not the black wood centre on the Almere side. The centre is closed at this hour.",
        "- NL-01-195: the city hall remains NL-01-178. This is The Wave, the 2004 silver housing block on the Weerwater. No shop name is shown.",
        "- NL-01-196: the Middelbuurt church remains NL-01-055. This is the keeper’s house on the north terp, a low brick house by a small harbour. A tall lighthouse was not invented.",
        "- NL-01-197: Hunebed D27 remains NL-01-062 and D53 remains NL-01-179. This is D49, the Papeloze Kerk. One half is under a restored turf mound and the other half shows the stones.",
        "- NL-01-198: the museum is closed. The view is the U-shaped brick manor across the moat, two lower wings, late September leaf. The inner rooms are not shown.",
        "- NL-01-199: the park is closed. The huts are a museum reconstruction of the early peat hamlet, not an untouched street. No shop name and no train are shown.",
        "- NL-01-200: the Sassenpoort remains NL-01-070. This is the Peperbus. The crown is the octagonal lantern and the copper dome from after 1815, not a needle spire. The gallery is empty.",
        "- NL-01-201: the Lebuinuskerk remains NL-01-045. This is the leaning Waag on the Brink. The museum is closed. The church is outside the frame.",
        "- NL-01-202: the city bridge remains NL-01-071. This is the river gate. The towers are brick. The nineteenth-century whitewash is not the present surface, so it is not shown.",
        "- NL-01-203: Martinitoren remains NL-01-060. This is the Aa-kerk from the canal. The tower crown is the baroque lantern and closed spire, not the open Gothic crown.",
        "- NL-01-204: the bell tower stands apart from the cruciform church and has a saddle roof. A partial moat and an iron gate remain. The church is closed.",
        "- NL-01-205: the lost village was Koudekerke. The nave was taken down in 1583. The tower stands alone in a hollow of the Oosterschelde dike. No nave was rebuilt.",
        "- NL-01-206: Noordhavenpoort remains NL-01-042. This is the unfinished tower. The church burned in 1832. The top is a low roof, not the planned spire.",
        "- NL-01-207: uses America/Kralendijk. Fort Oranje remains NL-01-065 and Lower Town remains NL-01-190. The popular name Fort de Windt is the wrong type. This is Batterij De Windt, a low coastal battery on the south cliff. Night water is dark. No hotel name is shown.",
        "- NL-01-208: uses America/Kralendijk. The Bottom remains NL-01-066 and Windwardside remains NL-01-147. Hell’s Gate is the tourist name; the official name is Zion’s Hill. This is the upper village of white houses and red roofs. The airport runway and the closed summit are not shown.",
        "- The other suggested sites in this batch were not already used.",
        "NL-01-209 through NL-01-224 swaps:",
        "- NL-01-209: Poldertoren remains NL-01-148 and Museum Nagele remains NL-01-177. This is De Meerpaal in Dronten after the atelier PRO rebuild. The roof on columns, the glass front, the oval cinema volume, and the red-tile fly tower are the present building. It is not the fully open 1967 hall. The building is closed at this hour.",
        "- NL-01-210: the city hall remains NL-01-178 and The Wave remains NL-01-195. This is the pumping station on the Oostvaardersdijk. The exterior reads as a ship's bridge, white side blocks and a steel motor hall. The diesels were replaced, so no exhaust plume is shown. Four lines of poetry on the facade are not legible. The interior is closed. It is not a windmill.",
        "- NL-01-211: the fishing harbour remains NL-01-054 and the white lighthouse remains NL-01-193. This is the brick church on the old island height. The tower has the 1955 balustrade, octagonal lantern, and onion spire, not the 1896 needle. The body is brick, not whitewash. The lighthouse is not in the frame.",
        "- NL-01-212: Hunebed D27 remains NL-01-062. This is the Magnuskerk on the brink. The nave is tuff, the tower is brick with a saddle roof and the 1895 crow-stepped gables, plus the small 1757 fleche. The churchyard graves were moved, so no stones are shown in the grass by the church. Late September leaf, no snow.",
        "- NL-01-213: D27 remains NL-01-062 and D53 remains NL-01-179. This is the pair D17 and D18 east of the churchyard, under oaks. The Jacobuskerk is only a distant roof, not the subject. Exact stone counts are not stated because the published counts differ.",
        "- NL-01-214: the circular moat around the churchyard was filled in 1830 and is not shown. The church is a long brick hall with a small ridge turret, not a tall west tower. Houses stand in a ring on the terp. The visitor centre inside the church is closed.",
        "- NL-01-215: Martinitoren remains NL-01-060, the Aa-kerk remains NL-01-203, and Forum remains NL-01-144. This is the Cuypers cathedral on the Radesingel. One hexagonal tower stands beside the front, with an open iron spire. There is no transept and no second tower. The city tower is not the subject.",
        "- NL-01-216: the Sassenpoort remains NL-01-070 and the Peperbus remains NL-01-200. This is the neoclassical court building with the ceramic elliptical volume on the roof, seen from the Blijmarkt so the north window faces the camera. The museum is closed. No artwork is shown.",
        "- NL-01-217: the city bridge remains NL-01-071 and the Koornmarktspoort remains NL-01-202. This is the Gothic church from the church side. The river gate is down the street behind the camera and is not in the frame. The church is closed.",
        "- NL-01-218: the wooden tower top was lifted back into place in June 2021, so no scaffold is shown. The street front is the Frisian scroll gable and the 1768 stair. The offices are closed. No sign is readable.",
        "- NL-01-219: Nes harbour remains NL-01-113. Brandaris remains NL-01-114 and the red Noordertoren remains NL-01-116. This is the cast-iron tower at Hollum, red and white horizontal bands, red lantern, in the dunes. The gallery is empty at this hour.",
        "- NL-01-220: Vrijthof, Saint Servatius, Helpoort, and the Sint Servaasbrug are other Maastricht scenes. This is the brick museum and the zinc dome on the Maas. The museum is closed. No banner text and no cafe name.",
        "- NL-01-221: the house is red brick with marl bands, not a white castle. It is L-shaped and fully moated, with a heavy corner tower, a narrow stair turret, and a gate tower, all with helmet roofs. The viewpoint is the double-arch bridge on the field side. The interior is closed. No coat-of-arms lettering is readable.",
        "- NL-01-222: the Koppelpoort remains NL-01-035. The church was lost after the 1787 explosion and was not rebuilt. The tower stands free. The paving marks the old outline and is not a ruin wall. The crown is the restored lantern and openwork onion, not a needle spire.",
        "- NL-01-223: Willemstad is in North Brabant, on the Hollands Diep. The church is octagonal brick with a dome and an unfinished low square tower. A tall spire was never built and is not invented. The moat around the churchyard remains.",
        "- NL-01-224: uses America/Kralendijk. The Kralendijk waterfront, the salt pans, the slave huts, and the Willemstoren are other scenes. This is the white church in Rincon. The bell tower was added in the 1977-1984 works, so the tower is shown. No sign is readable. Night hills are dark.",
        "- The other suggested sites in this batch were not already used.",
        "",
    ]
    for row in catalogue:
        weather = json.loads((ROOT / "evidence" / "weather" / f"{row['entry_id']}.json").read_text())
        existing_manifest = ROOT / "manifests" / f"{row['entry_id']}.json"
        if existing_manifest.exists():
            old_manifest = json.loads(existing_manifest.read_text())
            if old_manifest.get("approval_status") == "Approved":
                scenes.append(old_manifest)
                lines.append(
                    f"- {row['entry_id']} — {row['caption']} — {weather['scenario_label']} — retrieved {weather['retrieval_timestamp']}"
                )
                print(row["entry_id"], "preserved Cosmo approval")
                continue
        raw16 = Path("/opt/cursor/artifacts/assets") / f"{row['entry_id'].lower()}-16x9-raw.png"
        raw45 = Path("/opt/cursor/artifacts/assets") / f"{row['entry_id'].lower()}-4x5-raw.png"
        # Cosmo-approved masters are skipped above. Never composite them.
        if row["entry_id"] <= "NL-01-010":
            pass
        elif raw16.exists() and raw45.exists():
            composite_one(row["entry_id"], row["folder"], row["caption"], weather["scenario_label"])
        else:
            have16 = (ROOT / "library" / "world" / "Netherlands" / row["folder"] / f"{row['entry_id'].lower()}-16x9.png").exists()
            have45 = (ROOT / "library" / "world" / "Netherlands" / row["folder"] / f"{row['entry_id'].lower()}-4x5.png").exists()
            if not (have16 and have45):
                raise SystemExit(f"missing raw and master for {row['entry_id']}")
        file16 = f"Netherlands/{row['folder']}/{row['entry_id'].lower()}-16x9.png"
        file45 = f"Netherlands/{row['folder']}/{row['entry_id'].lower()}-4x5.png"
        path16 = ROOT / "library" / "world" / file16
        path45 = ROOT / "library" / "world" / file45
        digest16 = sha256(path16)
        digest45 = sha256(path45)
        manifest = {"entry_id": row["entry_id"]}
        existing_manifest = ROOT / "manifests" / f"{row['entry_id']}.json"
        if existing_manifest.exists():
            old = json.loads(existing_manifest.read_text())
            for key in (
                "approval_status",
                "qc_status",
                "approval_basis",
                "approved_at",
                "sha256_16x9",
                "sha256_4x5",
            ):
                if key in old:
                    manifest[key] = old[key]
        manifest.update(
            {
                "country": "Netherlands",
                "region": row["region"],
                "city": row["city"],
                "caption": row["caption"],
                "scenario_label": weather["scenario_label"],
                "composition": row["composition"],
                "description": row["description"],
                "alt_text": row["alt_text"],
                "file_16x9": file16,
                "file_4x5": file45,
                "license_badge": "Free · no credit needed",
                "license_anchor": "#license",
            }
        )
        (ROOT / "manifests" / f"{row['entry_id']}.json").write_text(json.dumps(manifest, indent=2) + "\n")
        (ROOT / "approvals" / f"{row['entry_id']}.md").write_text(
            approval_md(row, weather, digest16, digest45)
        )
        scenes.append(manifest)
        lines.append(
            f"- {row['entry_id']} — {row['caption']} — {weather['scenario_label']} — retrieved {weather['retrieval_timestamp']}"
        )
        print(row["entry_id"], weather["retrieval_timestamp"], digest16[:12])

    (ROOT / "approvals" / "CATALOGUE.md").write_text("\n".join(lines) + "\n")
    payload = json.dumps(scenes, ensure_ascii=False).replace("<", "\\u003c")
    html = PAGE.replace("__SCENES__", payload)
    (ROOT / "index.html").write_text(html)
    (ROOT / "robots.txt").write_text(
        "User-agent: *\nAllow: /\n\nSitemap: https://devlij.github.io/jason-ds-vision-netherlands-preview/sitemap.xml\n"
    )
    (ROOT / "sitemap.xml").write_text(
        """<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
  <url>
    <loc>https://devlij.github.io/jason-ds-vision-netherlands-preview/</loc>
  </url>
</urlset>
"""
    )
    (ROOT / ".nojekyll").write_text("")
    (ROOT / "README.md").write_text(
        "# Jason D’s Vision — Netherlands\n\n"
        "Candidate gallery of AI-generated artistic interpretations. "
        "Scenes stay Candidate until an independent QC pass.\n\n"
        "Live page: https://devlij.github.io/jason-ds-vision-netherlands-preview/\n"
    )
    print(f"published {len(scenes)} scenes")


if __name__ == "__main__":
    main()
