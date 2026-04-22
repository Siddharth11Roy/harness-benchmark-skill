const $ = (sel) => document.querySelector(sel);
let activeId = null;

async function loadSessions() {
  const r = await fetch("/api/sessions");
  const data = await r.json();
  $("#root-path").textContent = data.root;
  const ul = $("#sessions");
  ul.innerHTML = "";
  if (!data.sessions.length) {
    ul.innerHTML = '<li style="color:#888;cursor:default">No sessions found.</li>';
    return;
  }
  for (const s of data.sessions) {
    const li = document.createElement("li");
    li.dataset.id = s.id;
    li.innerHTML = `<div class="sid">${escape(s.id)}</div><div class="meta">${escape(s.model || "?")} · ${escape(s.date || "")}</div>`;
    li.onclick = () => selectSession(s.id);
    if (s.id === activeId) li.classList.add("active");
    ul.appendChild(li);
  }
}

async function selectSession(id) {
  activeId = id;
  document.querySelectorAll("#sessions li").forEach(el => el.classList.toggle("active", el.dataset.id === id));
  const r = await fetch(`/api/sessions/${encodeURIComponent(id)}`);
  if (!r.ok) {
    alert(`Failed to load: ${r.status}`);
    return;
  }
  renderDetail(await r.json());
}

function renderDetail(d) {
  $("#empty").hidden = true;
  $("#detail").hidden = false;
  const meta = d.meta || {};
  const score = d.score || {};
  const m = score.metrics || {};

  $("#detail-header").innerHTML = `
    <h2>${escape(d.session.id)}</h2>
    <div class="sub">${escape(meta.project || "?")} · ${escape(meta.model || "?")} · ${escape(meta.date || "")}</div>
  `;

  $("#metrics").innerHTML = [
    metric("composite", "Score", score.score, score.grade, "", true),
    metric("c", "Completion", m.completion, "", m.completion_detail),
    metric("e", "Efficiency", m.efficiency, "", m.efficiency_detail),
    metric("t", "Tool success", m.tool_success, "", m.tool_success_detail),
    metric("r", "Recovery", m.recovery, "", m.recovery_detail),
    metric("d", "Diff quality", m.diff_quality, "", m.diff_quality_detail),
    metric("p", "Planning", m.planning_quality, "", m.planning_quality_detail),
  ].join("");

  $("#trace").innerHTML = (d.trace || []).map(s => `
    <div class="row ${s.phase === "FAILED" ? "failed" : ""}">
      <span class="step">#${s.step}</span><span class="phase">${escape(s.phase)}</span><span class="goal">${escape(s.goal || "")}</span>
      <div class="detail">${escape(s.result || "")}</div>
    </div>`).join("") || '<div style="color:#888">no trace</div>';

  $("#calls").innerHTML = (d.tool_calls || []).map(t => `
    <div class="row ${t.success ? "" : "failed"}">
      <span class="step">#${t.step}</span><span class="phase">${escape(t.tool)}</span>
      <span class="goal">${escape((t.input || "").slice(0, 80))}</span>
      <div class="detail">${escape((t.output_summary || "").slice(0, 160))}</div>
    </div>`).join("") || '<div style="color:#888">no tool calls</div>';

  $("#diffs").innerHTML = (d.diffs || []).map(x => `
    <div class="row ${x.is_wasted ? "wasted" : ""}">
      <span class="step">#${x.step}</span>
      <span class="goal">+${x.lines_added}/-${x.lines_removed} ${escape((x.files_changed || []).join(", "))}</span>
      <div class="detail">${escape(x.reason || "")}</div>
    </div>`).join("") || '<div style="color:#888">no diffs</div>';
}

function metric(cls, label, value, suffix, detail, composite) {
  const v = typeof value === "number" ? value : 0;
  const display = typeof value === "number" ? v.toFixed(2) : "—";
  const grade = suffix ? ` <span style="font-size:14px;color:#888">${escape(suffix)}</span>` : "";
  return `<div class="metric ${composite ? "composite" : ""}">
    <div class="label">${escape(label)}</div>
    <div class="value">${display}${grade}</div>
    <div class="bar"><div style="width:${Math.round(v * 100)}%"></div></div>
    <div class="detail">${escape(detail || "")}</div>
  </div>`;
}

function escape(s) {
  return String(s ?? "").replace(/[&<>"']/g, c => ({"&":"&amp;","<":"&lt;",">":"&gt;","\"":"&quot;","'":"&#39;"}[c]));
}

$("#refresh").onclick = async () => {
  await fetch("/api/refresh", { method: "POST" });
  await loadSessions();
};

async function refreshBadge() {
  try {
    const r = await fetch("/api/status");
    const { mcp_connected } = await r.json();
    const el = $("#badge");
    el.classList.remove("dim");
    el.classList.toggle("connected", mcp_connected);
    el.classList.toggle("disconnected", !mcp_connected);
    el.textContent = mcp_connected ? "harness MCP · connected" : "harness MCP · standalone";
  } catch {
    $("#badge").textContent = "harness MCP · offline";
  }
}

loadSessions();
refreshBadge();
setInterval(loadSessions, 5000);
setInterval(refreshBadge, 5000);
