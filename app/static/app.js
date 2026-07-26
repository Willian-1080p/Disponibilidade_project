"use strict";

const state = {
  targets: [],
  targetStatus: [],
  agents: [],
  lastCreatedAgentScript: null
};

const elements = {
  tabs: document.querySelectorAll(".tab"),
  views: document.querySelectorAll(".view"),
  notice: document.getElementById("notice"),
  refreshButton: document.getElementById("refresh-button"),
  targetForm: document.getElementById("target-form"),
  agentForm: document.getElementById("agent-form"),
  targetType: document.getElementById("target-type"),
  portField: document.getElementById("port-field"),
  targetsTable: document.getElementById("targets-table"),
  agentsTable: document.getElementById("agents-table"),
  statusGrid: document.getElementById("status-grid"),
  targetsCount: document.getElementById("targets-count"),
  agentsCount: document.getElementById("agents-count"),
  lastRefresh: document.getElementById("last-refresh"),
  tokenDialog: document.getElementById("token-dialog"),
  createdToken: document.getElementById("created-token"),
  createdApiUrl: document.getElementById("created-api-url"),
  agentApiBaseUrl: document.getElementById("agent-api-base-url"),
  copyToken: document.getElementById("copy-token"),
  downloadAgentScript: document.getElementById("download-agent-script"),
  closeTokenDialog: document.getElementById("close-token-dialog")
};

function setNotice(message, error = false) {
  elements.notice.textContent = message;
  elements.notice.classList.toggle("error", error);
  elements.notice.classList.remove("hidden");
  window.clearTimeout(setNotice.timer);
  setNotice.timer = window.setTimeout(() => elements.notice.classList.add("hidden"), 5000);
}

async function api(path, options = {}) {
  const response = await fetch(path, {
    headers: {
      "Content-Type": "application/json",
      ...(options.headers || {})
    },
    ...options
  });
  if (!response.ok) {
    let detail = `Erro HTTP ${response.status}`;
    try {
      const body = await response.json();
      if (Array.isArray(body.detail)) {
        detail = body.detail.map((item) => item.msg || "Dados inválidos.").join(" ");
      } else {
        detail = body.detail || detail;
      }
    } catch {
      detail = response.statusText || detail;
    }
    throw new Error(detail);
  }
  if (response.status === 204) return null;
  return response.json();
}

function downloadPowerShell(filename, content) {
  const blob = new Blob(["\ufeff", content], { type: "text/plain;charset=utf-8" });
  const objectUrl = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = objectUrl;
  link.download = filename;
  document.body.append(link);
  link.click();
  link.remove();
  window.setTimeout(() => URL.revokeObjectURL(objectUrl), 1000);
}

function statusLabel(status) {
  const labels = {
    online: "ONLINE",
    offline: "OFFLINE",
    warning: "ALERTA",
    unknown: "DESCONHECIDO",
    disabled: "DESATIVADO"
  };
  return labels[status] || "DESCONHECIDO";
}

function statusClass(status) {
  return ["online", "offline", "warning"].includes(status) ? status : "unknown";
}

function formatDate(value) {
  if (!value) return "Nunca";
  return new Intl.DateTimeFormat("pt-BR", {
    dateStyle: "short",
    timeStyle: "medium"
  }).format(new Date(value));
}

function textCell(value, className = "") {
  const cell = document.createElement("td");
  cell.textContent = value ?? "—";
  if (className) cell.className = className;
  return cell;
}

function badge(status) {
  const span = document.createElement("span");
  span.className = `status-badge ${statusClass(status)}`;
  span.textContent = statusLabel(status);
  return span;
}

function deleteButton(label, handler) {
  const button = document.createElement("button");
  button.type = "button";
  button.className = "button button-danger";
  button.textContent = "Excluir";
  button.setAttribute("aria-label", `Excluir ${label}`);
  button.addEventListener("click", handler);
  return button;
}

function renderSummary() {
  const statuses = [
    ...state.targetStatus.map((item) => item.status || "unknown"),
    ...state.agents.map((item) => item.status || "unknown")
  ];
  document.getElementById("metric-total").textContent = statuses.length;
  document.getElementById("metric-online").textContent = statuses.filter((item) => item === "online").length;
  document.getElementById("metric-offline").textContent = statuses.filter((item) => item === "offline").length;
  document.getElementById("metric-warning").textContent = statuses.filter((item) => item === "warning").length;
}

function renderOverview() {
  elements.statusGrid.replaceChildren();
  const cards = [
    ...state.targetStatus.map((item) => ({
      name: item.name,
      subtitle: `${item.check_type.toUpperCase()} · ${item.target}${item.port ? `:${item.port}` : ""}`,
      status: item.status || "unknown",
      detail: item.latency_ms == null ? item.message || "Sem medição" : `${Number(item.latency_ms).toFixed(2)} ms`
    })),
    ...state.agents.map((item) => ({
      name: item.name,
      subtitle: `AGENTE · ${item.location || "Sem local"}`,
      status: item.status || "unknown",
      detail: item.last_seen_at ? `Último sinal: ${formatDate(item.last_seen_at)}` : "Aguardando primeiro sinal"
    }))
  ];

  if (!cards.length) {
    const empty = document.createElement("p");
    empty.textContent = "Nenhum alvo ou agente cadastrado.";
    empty.className = "notice";
    elements.statusGrid.append(empty);
    return;
  }

  cards.forEach((item) => {
    const card = document.createElement("article");
    card.className = `status-card ${statusClass(item.status)}`;
    const title = document.createElement("h3");
    title.textContent = item.name;
    const status = badge(item.status);
    const subtitle = document.createElement("p");
    subtitle.textContent = item.subtitle;
    const detail = document.createElement("p");
    detail.textContent = item.detail;
    card.append(title, status, subtitle, detail);
    elements.statusGrid.append(card);
  });
}

function renderTargets() {
  elements.targetsTable.replaceChildren();
  elements.targetsCount.textContent = `${state.targets.length} ${state.targets.length === 1 ? "item" : "itens"}`;
  const statusById = new Map(state.targetStatus.map((item) => [item.id, item]));

  if (!state.targets.length) {
    const row = document.createElement("tr");
    row.className = "empty-row";
    const cell = document.createElement("td");
    cell.colSpan = 6;
    cell.textContent = "Nenhum alvo cadastrado.";
    row.append(cell);
    elements.targetsTable.append(row);
    return;
  }

  state.targets.forEach((target) => {
    const current = statusById.get(target.id) || {};
    const row = document.createElement("tr");
    row.append(
      textCell(target.name),
      textCell(`${target.target}${target.port ? `:${target.port}` : ""}`, "wrap"),
      textCell(target.check_type.toUpperCase())
    );
    const statusCell = document.createElement("td");
    statusCell.append(badge(current.status || "unknown"));
    row.append(statusCell);
    row.append(textCell(current.latency_ms == null ? "—" : `${Number(current.latency_ms).toFixed(2)} ms`));
    const actionCell = document.createElement("td");
    actionCell.append(deleteButton(target.name, () => removeTarget(target)));
    row.append(actionCell);
    elements.targetsTable.append(row);
  });
}

function renderAgents() {
  elements.agentsTable.replaceChildren();
  elements.agentsCount.textContent = `${state.agents.length} ${state.agents.length === 1 ? "item" : "itens"}`;

  if (!state.agents.length) {
    const row = document.createElement("tr");
    row.className = "empty-row";
    const cell = document.createElement("td");
    cell.colSpan = 7;
    cell.textContent = "Nenhum agente cadastrado.";
    row.append(cell);
    elements.agentsTable.append(row);
    return;
  }

  state.agents.forEach((agent) => {
    const row = document.createElement("tr");
    row.append(
      textCell(agent.name),
      textCell(agent.location || "—"),
      textCell(agent.hostname || "—"),
      textCell(agent.local_ip || "—")
    );
    const statusCell = document.createElement("td");
    statusCell.append(badge(agent.status || "unknown"));
    row.append(statusCell);
    row.append(textCell(formatDate(agent.last_seen_at)));
    const actionCell = document.createElement("td");
    actionCell.append(deleteButton(agent.name, () => removeAgent(agent)));
    row.append(actionCell);
    elements.agentsTable.append(row);
  });
}

function renderAll() {
  renderSummary();
  renderOverview();
  renderTargets();
  renderAgents();
  elements.lastRefresh.textContent = `Atualizado em ${new Date().toLocaleTimeString("pt-BR")}`;
}

async function loadData() {
  elements.refreshButton.disabled = true;
  try {
    const [targets, targetStatus, agents] = await Promise.all([
      api("/api/targets"),
      api("/api/status"),
      api("/api/agents")
    ]);
    state.targets = targets;
    state.targetStatus = targetStatus;
    state.agents = agents;
    renderAll();
  } catch (error) {
    setNotice(`Não foi possível atualizar: ${error.message}`, true);
  } finally {
    elements.refreshButton.disabled = false;
  }
}

async function removeTarget(target) {
  if (!window.confirm(`Excluir o alvo "${target.name}" e todo o histórico dele?`)) return;
  try {
    await api(`/api/targets/${target.id}`, { method: "DELETE" });
    setNotice(`Alvo "${target.name}" excluído.`);
    await loadData();
  } catch (error) {
    setNotice(`Falha ao excluir: ${error.message}`, true);
  }
}

async function removeAgent(agent) {
  if (!window.confirm(`Excluir o agente "${agent.name}"? O token dele deixará de funcionar.`)) return;
  try {
    await api(`/api/agents/${agent.id}`, { method: "DELETE" });
    setNotice(`Agente "${agent.name}" excluído.`);
    await loadData();
  } catch (error) {
    setNotice(`Falha ao excluir: ${error.message}`, true);
  }
}

elements.targetForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  const form = new FormData(elements.targetForm);
  const type = form.get("check_type");
  const rawPort = form.get("port");
  const payload = {
    name: form.get("name").trim(),
    target: form.get("target").trim(),
    check_type: type,
    port: ["tcp", "ssl"].includes(type) && rawPort ? Number(rawPort) : null
  };
  try {
    await api("/api/targets", { method: "POST", body: JSON.stringify(payload) });
    elements.targetForm.reset();
    updatePortField();
    setNotice(`Alvo "${payload.name}" criado com sucesso.`);
    await loadData();
  } catch (error) {
    setNotice(`Falha ao criar alvo: ${error.message}`, true);
  }
});

elements.agentForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  const form = new FormData(elements.agentForm);
  const payload = {
    name: form.get("name").trim(),
    location: form.get("location").trim() || null,
    client_external_id: form.get("client_external_id").trim() || null,
    api_base_url: form.get("api_base_url").trim()
  };
  try {
    const created = await api("/api/agents", { method: "POST", body: JSON.stringify(payload) });
    state.lastCreatedAgentScript = {
      filename: created.script_filename,
      content: created.script_content
    };
    downloadPowerShell(created.script_filename, created.script_content);
    elements.agentForm.reset();
    elements.agentApiBaseUrl.value = created.api_base_url;
    elements.createdToken.textContent = created.token;
    elements.createdApiUrl.textContent = created.api_base_url;
    elements.tokenDialog.showModal();
    setNotice(`Agente "${payload.name}" criado e PowerShell gerado.`);
    await loadData();
  } catch (error) {
    setNotice(`Falha ao criar agente: ${error.message}`, true);
  }
});

function updatePortField() {
  const required = ["tcp", "ssl"].includes(elements.targetType.value);
  elements.portField.classList.toggle("hidden", !required);
  const input = elements.portField.querySelector("input");
  input.required = required;
  if (!required) input.value = "";
}

elements.tabs.forEach((tab) => {
  tab.addEventListener("click", () => {
    elements.tabs.forEach((item) => {
      const selected = item === tab;
      item.classList.toggle("active", selected);
      item.setAttribute("aria-selected", String(selected));
    });
    elements.views.forEach((view) => view.classList.toggle("active", view.id === `view-${tab.dataset.view}`));
  });
});

elements.refreshButton.addEventListener("click", loadData);
elements.targetType.addEventListener("change", updatePortField);
elements.copyToken.addEventListener("click", async () => {
  await navigator.clipboard.writeText(elements.createdToken.textContent);
  elements.copyToken.textContent = "Copiado";
});
elements.downloadAgentScript.addEventListener("click", () => {
  if (!state.lastCreatedAgentScript) return;
  downloadPowerShell(
    state.lastCreatedAgentScript.filename,
    state.lastCreatedAgentScript.content
  );
});
elements.closeTokenDialog.addEventListener("click", () => {
  elements.createdToken.textContent = "";
  elements.createdApiUrl.textContent = "";
  elements.copyToken.textContent = "Copiar";
  state.lastCreatedAgentScript = null;
  elements.tokenDialog.close();
});

elements.agentApiBaseUrl.value = window.location.origin;
updatePortField();
loadData();
window.setInterval(loadData, 60000);
