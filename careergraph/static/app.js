"use strict";
const $ = (id) => document.getElementById(id);
const state = { catalog: null, known: new Set(["python", "sql"]), offset: 0, missing: null, token: 0, filters: null };
const el = (tag, text, className) => { const node = document.createElement(tag); if (text !== undefined) node.textContent = text; if (className) node.className = className; return node; };
const skillName = (id) => state.catalog.skills.find((s) => s.id === id)?.label || id;
const number = (n) => new Intl.NumberFormat("en-GB").format(n);
const dateLabel = (value) => value ? new Date(value.slice(0, 10) + "T12:00:00Z").toLocaleDateString("en-GB", { day: "2-digit", month: "short", year: "numeric", timeZone: "UTC" }) : "Not available";
async function api(path, params) {
  const response = await fetch(path + (params ? "?" + new URLSearchParams(params) : ""));
  if (!response.ok) { const error = await response.json(); throw new Error(typeof error.detail === "string" ? error.detail : "Check the filter values and try again."); }
  return response.json();
}
function empty(container, message) { container.replaceChildren(el("p", message, "empty")); }
function filters() { const result = { mode: $("mode").value, country: $("country").value, role: $("role").value, skills: [...state.known].sort().join(",") }; if ($("since").value) result.since = $("since").value; return result; }
function renderSkills(data) {
  const root = $("skill-bars"); root.replaceChildren();
  if (!data.skills.length) return empty(root, data.sample.availability === "not_collected" ? "No offers have been collected for this country. This says nothing about its demand." : "No skill mentions in this filtered sample.");
  data.skills.slice(0, 12).forEach((skill) => {
    const row = el("div", undefined, "skill-row"), track = el("div", undefined, "bar-track"), fill = el("span", undefined, "bar-fill");
    fill.style.width = (skill.share * 100).toFixed(1) + "%"; track.append(fill); track.setAttribute("aria-hidden", "true");
    row.append(el("span", skill.label), track, el("span", `${skill.count} / ${skill.denominator}`, "skill-count"));
    row.title = `${skill.label}: ${(skill.share * 100).toFixed(1)}% of sampled offers`; root.append(row);
  });
}
function renderBridge(bridge) {
  $("covered").textContent = number(bridge.covered_offers);
  $("covered-label").textContent = `of ${number(bridge.eligible_offers)} eligible offers covered`;
  const root = $("bridge-list"); root.replaceChildren();
  bridge.add_one_skill.slice(0, 5).forEach((item) => {
    const button = el("button", undefined, "gain"); button.type = "button";
    button.append(el("strong", skillName(item.skill)), el("small", "Inspect additional covered offers ↗"), el("span", "+" + number(item.additional_offers), "gain-count"));
    button.addEventListener("click", async () => { state.missing = item.skill; state.offset = 0; await refreshEvidence(); $("evidence").scrollIntoView({ behavior: "smooth" }); });
    root.append(button);
  });
  if (!bridge.add_one_skill.length) empty(root, "No single addition completes another detected skill set. Broaden the sample or edit your skills.");
  $("bridge-denominator").textContent = `${number(bridge.eligible_offers)} offers contain at least one recognised skill. ${number(bridge.excluded_without_detected_skills)} without recognised skills are excluded from this calculation.`;
}
function renderRelationships(data) {
  const root = $("relationships"); root.replaceChildren();
  data.relationships.slice(0, 6).forEach((edge) => { const row = el("div", undefined, "edge"); row.append(el("span", `${skillName(edge.left)} + ${skillName(edge.right)}`), el("span", `${edge.support} offers · J ${edge.jaccard.toFixed(2)}`)); root.append(row); });
  if (!data.relationships.length) empty(root, "No skill pair reaches the minimum support of 3 offers.");
}
function renderOverview(data) {
  const demo = state.filters.mode === "demo", s = data.sample;
  $("dataset-note").className = "notice" + (demo ? "" : " live");
  $("dataset-note").textContent = demo ? "ILLUSTRATIVE DEMO · Fictional offers across 16 configured countries, fixed at 01 Oct 2026. Skill patterns are invented for testing; do not draw market conclusions. The Eurostat panel below uses real statistics." : `COLLECTED OFFERS · A bounded keyword-search sample, not a census of vacancies. ${s.countries.length ? "Observed workplace countries: " + s.countries.join(", ") + "." : "No observed offers for this selection."} ${s.stale ? "The latest sample is older than 48 hours; refresh it before using it." : ""}`;
  if (data.latest_attempts.some((r) => r.status === "failed")) $("dataset-note").textContent += " The most recent collection attempt failed; the last successful sample is shown where available.";
  $("sample-n").textContent = s.availability === "not_collected" ? "—" : number(s.offers);
  $("skill-n").textContent = s.availability === "not_collected" ? "—" : number(s.offers_with_skills);
  $("source-n").textContent = number(s.sources.length);
  $("sample-period").textContent = s.publication_min ? dateLabel(s.publication_min) + " – " + dateLabel(s.publication_max) : "No observed period";
  $("sample-status").textContent = s.small_sample && s.offers ? "Small sample (<30). Treat patterns as exploratory." : s.availability === "not_collected" ? "Not collected ≠ no demand" : "Descriptive results within this sample";
  renderSkills(data); renderBridge(data.bridge); renderRelationships(data);
  const q = data.quality;
  $("quality-summary").textContent = `${number(q.input_records)} input records → ${number(q.accepted_offers)} retained offers · ${number(q.duplicates_removed)} duplicates removed · ${number(q.rejected_records)} rejected.`;
  $("run-record").textContent = JSON.stringify({ latest_attempts: data.latest_attempts, successful_samples: data.runs }, null, 2);
}
function renderEvidence(data) {
  const root = $("offer-list"); root.replaceChildren();
  $("clear-evidence").hidden = !state.missing;
  $("evidence-note").textContent = state.missing ? `Offers whose only missing detected skill is ${skillName(state.missing)}. Open a row to inspect the exact mentions.` : "Open an offer to see its detected skills and the text supporting each match.";
  data.offers.forEach((offer) => {
    const box = el("details", undefined, "offer"), summary = el("summary"), title = el("span", offer.title, "offer-title");
    title.append(el("small", `${offer.company} · ${state.catalog.countries[offer.country] || offer.country}`));
    summary.append(title, el("span", offer.skills.map(skillName).join(" · ") || "No detected skills", "offer-skills"), el("span", `${dateLabel(offer.published_at)} · ${offer.source}`, "offer-date"), el("span", "+", "offer-plus"));
    const body = el("div", undefined, "offer-body"), list = el("dl");
    offer.mentions.forEach((m) => { list.append(el("dt", skillName(m.skill)), el("dd", `“${m.excerpt}”`)); });
    body.append(el("p", `Missing from your selection: ${offer.missing_skills.map(skillName).join(", ") || (offer.skills.length ? "none of the detected skills" : "unknown — no recognised skills")}`, "small"), list);
    if (offer.source === "synthetic") body.append(el("p", "Fictional demonstration offer. No application link.", "small"));
    else {
      try { const url = new URL(offer.source_url); if (url.protocol === "https:") { const link = el("a", "Open the original offer ↗"); link.href = url.href; link.target = "_blank"; link.rel = "noopener noreferrer"; body.append(link); } } catch (_) { body.append(el("p", "Source link unavailable", "small")); }
    }
    box.append(summary, body); root.append(box);
  });
  if (!data.total) empty(root, "No matching evidence in this sample.");
  $("page-info").textContent = data.total ? `${data.offset + 1}–${Math.min(data.offset + data.limit, data.total)} of ${number(data.total)}` : "0 offers";
  $("previous").disabled = data.offset === 0; $("next").disabled = data.offset + data.limit >= data.total;
}
function table(headers) { const t = el("table"), head = el("thead"), row = el("tr"), body = el("tbody"); headers.forEach((h) => { const th = el("th", h); th.scope = "col"; row.append(th); }); head.append(row); t.append(head, body); return [t, body]; }
function renderBenchmark(data) {
  const root = $("benchmark-table"); root.replaceChildren();
  if (!data.available) { empty(root, "No official snapshot loaded. Run the benchmark command to load the supplied snapshot or collect a new one."); $("benchmark-period").textContent = "Not loaded"; $("benchmark-source").textContent = ""; return; }
  const quarter = data.metadata.quarters.at(-1), rows = data.rows.filter((r) => r.quarter === quarter);
  $("benchmark-period").textContent = `${quarter} · vacancy rate (%) · seasonally adjusted`;
  const [t, body] = table(["Country", "Rate", "Source flag"]);
  rows.sort((a, b) => state.catalog.countries[a.country].localeCompare(state.catalog.countries[b.country])).forEach((r) => { const row = el("tr"); row.append(el("td", state.catalog.countries[r.country]), el("td", r.vacancy_rate === null ? "Not available" : r.vacancy_rate.toFixed(1) + "%", "numeric"), el("td", r.status_flag || "—", "status")); body.append(row); });
  root.append(t);
  $("benchmark-source").textContent = `${data.attribution} Retrieved ${dateLabel(data.retrieved_at)}; source updated ${dateLabel(data.source_updated_at)}. NACE Rev. 2.1 B–T, total enterprise sizes. Published flags are preserved (for example, p = provisional). Country coverage differs; the source methodology explains exceptions.`;
}
function renderCoverage(data) {
  const [t, body] = table(["Country", "Live offer collection", "Official context"]);
  const statuses = { collected: "Collected · JobTech", connector_ready: "Connector ready · JobTech", not_connected: "Not connected" };
  data.countries.forEach((c) => { const row = el("tr"), status = el("td"), benchmark = el("td"); status.append(el("span", statuses[c.offer_status], "tag" + (c.offer_status === "collected" ? " ok" : ""))); benchmark.append(el("span", c.benchmark_status === "available" ? `Available · ${c.benchmark_quarter}` : "Not available in selected series", "small")); row.append(el("td", `${c.name} / ${c.country}`), status, benchmark); body.append(row); });
  $("coverage-table").replaceChildren(t);
}
let evidenceToken = 0;
async function refreshEvidence() {
  const token = ++evidenceToken;
  try { const params = { ...state.filters, offset: state.offset, limit: 6 }; if (state.missing) params.missing_skill = state.missing; const data = await api("/api/evidence", params); if (token === evidenceToken) renderEvidence(data); }
  catch (error) { $("error").textContent = error.message; $("error").hidden = false; }
}
async function refresh() {
  const token = ++state.token; ++evidenceToken; state.offset = 0; state.missing = null; state.filters = filters();
  $("error").hidden = true; $("report").setAttribute("aria-busy", "true"); $("report").hidden = true; $("refresh").disabled = true;
  $("dataset-note").textContent = "Loading the selected sample…";
  try {
    const [data, benchmark, coverage, evidence] = await Promise.all([api("/api/overview", state.filters), api("/api/benchmark", { country: state.filters.country }), api("/api/coverage"), api("/api/evidence", { ...state.filters, limit: 6 })]);
    if (token !== state.token) return;
    renderOverview(data); renderBenchmark(benchmark); renderCoverage(coverage); renderEvidence(evidence); $("report").hidden = false;
  } catch (error) { if (token === state.token) { $("error").textContent = error.message; $("error").hidden = false; $("dataset-note").textContent = "The selected view could not be loaded. Check the connection or filter values."; } }
  finally { if (token === state.token) { $("report").setAttribute("aria-busy", "false"); $("refresh").disabled = false; } }
}
async function init() {
  try {
    state.catalog = await api("/api/catalog");
    Object.entries(state.catalog.countries).forEach(([code, name]) => { const option = el("option", name); option.value = code; $("country").append(option); });
    Object.entries(state.catalog.roles).forEach(([id, role]) => { const option = el("option", role.label); option.value = id; $("role").append(option); });
    $("role").value = "data_analyst";
    state.catalog.skills.forEach((s) => { const button = el("button", s.label, "skill-option"); button.type = "button"; button.setAttribute("aria-pressed", state.known.has(s.id)); button.addEventListener("click", () => { if (state.known.has(s.id)) state.known.delete(s.id); else state.known.add(s.id); button.setAttribute("aria-pressed", state.known.has(s.id)); refresh(); }); $("known-skills").append(button); });
    $("refresh").addEventListener("click", refresh);
    for (const id of ["mode", "country", "role", "since"]) $(id).addEventListener("change", refresh);
    $("previous").addEventListener("click", () => { state.offset = Math.max(0, state.offset - 6); refreshEvidence(); });
    $("next").addEventListener("click", () => { state.offset += 6; refreshEvidence(); });
    $("clear-evidence").addEventListener("click", () => { state.missing = null; state.offset = 0; refreshEvidence(); });
    await refresh();
  } catch (error) { $("error").textContent = "Application startup failed: " + error.message; $("error").hidden = false; }
}
init();
