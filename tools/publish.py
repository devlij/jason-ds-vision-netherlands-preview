#!/usr/bin/env python3
"""Write manifests, Candidate approvals, and the Netherlands gallery page."""

from __future__ import annotations

import hashlib
import json
import sys
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


def month_name_valid(label: str) -> str:
    # scenario_label is already "25 September 2026 · 18:26 Europe/Amsterdam"
    return label


def approval_md(row: dict, weather: dict, sha16: str, sha45: str) -> str:
    refs = "\n".join(f"  {i}. {url}" for i, url in enumerate(row["references"], 1))
    anchors = "\n".join(f"  {i}. {text}" for i, text in enumerate(row["anchors"], 1))
    hour = weather["retrieval_timestamp"][11:13]
    valid_display = (
        "25 September 2026 "
        + weather["model_time"][11:16]
        + " Europe/Amsterdam"
    )
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
- **Weather:** Model data from Open-Meteo, retrieved {weather['retrieval_display']}, valid {valid_display} (model-valid hour {hour}:00–{hour}:59) — not a verified on-site observation. {sky_words} (WMO code {weather['weather_code']}), cloud cover {weather['cloud_cover']}%, about {weather['temperature_2m']}°C, wind about {weather['wind_speed_10m']} km/h, precipitation {weather['precipitation']} mm, model is_day {weather['is_day']}. Provider: Open-Meteo. Request coordinates: {weather['latitude']}, {weather['longitude']}.
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
              <img src="${esc(file16)}" alt="${esc(s.alt_text)}" loading="lazy" data-src-16="${esc(file16)}" data-src-45="${esc(file45)}" />
              <span class="view-affordance">View image</span>
            </a>
          </div>
          <div class="card-body">
            <div class="status-row">
              <div class="entry-id">${esc(s.entry_id)}</div>
              <span class="status ${esc((s.approval_status || 'Candidate').toLowerCase())}">${esc(s.approval_status || 'Candidate')}</span>
            </div>
            <h3 class="caption">${esc(s.caption)}</h3>
            <p class="scenario">Scenario: ${esc(s.scenario_label)}</p>
            <p class="composition">${esc(s.composition)}</p>
            ${s.description ? `<p class="detail">${esc(s.description)}</p>` : ""}
            <div class="actions">
              <a class="badge" href="${esc(s.license_anchor)}">${esc(s.license_badge)}</a>
              <a class="download" href="${esc(file16)}" download="${esc(fileName(file16))}">Download 16:9</a>
              <a class="download" href="${esc(file45)}" download="${esc(fileName(file45))}">Download 4:5</a>
            </div>
          </div>`;
        grid.appendChild(card);
      }
    }
    grid.addEventListener('click', (event) => {
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
      const next = fmt === "4x5" ? img.getAttribute("data-src-45") : img.getAttribute("data-src-16");
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
    function visibleCards(){return Array.prototype.filter.call(document.querySelectorAll('.card'),function(c){return c.style.display!=='none';});}
    function show(i){
      items=visibleCards().map(function(c){
        var im=c.querySelector('a.thumb img');var t=c.querySelector('h3.caption');
        var src='';
        if(im){src=lbFormat==='4x5'?im.getAttribute('data-src-45'):im.getAttribute('data-src-16');}
        if(!src){var a=c.querySelector('a.thumb');src=a?a.href:'';}
        return{src:src,cap:t?t.textContent:''};
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
      if(a){e.preventDefault();var cards=visibleCards();var card=a.closest('.card');var tab=card.querySelector('.fmt-tab.is-active');lbFormat=(tab&&tab.getAttribute('data-format')==='4x5')?'4x5':'16x9';show(cards.indexOf(card));return;}
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
        "NL-01-001 through NL-01-032. IDs are not reused.",
        "NL-01-017 through NL-01-032: no swaps. The suggested North Holland and South Holland anchors were not already used.",
        "",
    ]
    for row in catalogue:
        weather = json.loads((ROOT / "evidence" / "weather" / f"{row['entry_id']}.json").read_text())
        raw16 = Path("/opt/cursor/artifacts/assets") / f"{row['entry_id'].lower()}-16x9-raw.png"
        raw45 = Path("/opt/cursor/artifacts/assets") / f"{row['entry_id'].lower()}-4x5-raw.png"
        if raw16.exists() and raw45.exists():
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
        manifest = {
            "entry_id": row["entry_id"],
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
