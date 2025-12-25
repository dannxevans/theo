<script>
  import { onMount } from "svelte";
  import { listProviders, upsertProvider, deleteProvider, getProviderHealth } from "../lib/api.js";

  let providers = [];
  let healthSummary = {};
  let error = null;

  // Form state
  let id = "";
  let name = "";
  let type = "";
  let base_url = "";
  let model = "";
  let api_key = "";
  let enabled = true;

  async function loadProviders() {
    try {
      providers = await listProviders();
      healthSummary = await getProviderHealth();
    } catch (e) {
      error = e.message;
    }
  }

  async function refreshHealth() {
    try {
      healthSummary = await getProviderHealth();
    } catch (e) {
      console.error("Failed to refresh health:", e);
    }
  }

  function getHealthBadge(providerId) {
    const health = healthSummary[providerId];
    if (!health) return { label: "Unknown", color: "#9ca3af" };

    if (health.circuit_breaker_open) {
      return { label: "Circuit Open", color: "#ef4444" };
    }

    switch (health.health_status) {
      case "healthy":
        return { label: "Healthy", color: "#10b981" };
      case "degraded":
        return { label: "Degraded", color: "#f59e0b" };
      case "unhealthy":
        return { label: "Unhealthy", color: "#ef4444" };
      default:
        return { label: "Unknown", color: "#9ca3af" };
    }
  }

  function getHealthStats(providerId) {
    const health = healthSummary[providerId];
    if (!health || health.total_requests === 0) return null;

    return {
      requests: health.total_requests,
      failureRate: health.failure_rate,
      avgLatency: health.avg_latency_ms,
    };
  }

  async function saveProvider() {
    error = null;

    if (!id || !name || !type) {
      error = "id, name and type are required";
      return;
    }

    if (type === "anthropic" && !model) {
      error = "Model is required for Anthropic providers";
      return;
    }

    try {
      await upsertProvider({
        id,
        name,
        type,
        base_url,
        model,
        api_key,
        enabled
      });

      // Reset form
      id = "";
      name = "";
      type = "";
      base_url = "";
      model = "";
      api_key = "";
      enabled = true;

      await loadProviders();
    } catch (e) {
      error = e.message;
    }
  }

  async function removeProvider(providerId) {
    if (!confirm(`Delete provider ${providerId}?`)) return;

    try {
      await deleteProvider(providerId);
      await loadProviders();
    } catch (e) {
      error = e.message;
    }
  }

  function editProvider(p) {
    id = p.id;
    name = p.name;
    type = p.type;
    base_url = p.base_url || "";
    model = p.model || "";
    api_key = ""; // never prefill secrets
    enabled = p.enabled;
  }

  onMount(() => {
    loadProviders();

    // Auto-refresh health every 3 seconds
    const interval = setInterval(refreshHealth, 3000);

    return () => clearInterval(interval);
  });
</script>

<div class="providers">
  <h2>Providers</h2>

  {#if error}
    <div class="error">{error}</div>
  {/if}

  <table>
    <thead>
      <tr>
        <th>ID</th>
        <th>Name</th>
        <th>Type</th>
        <th>Health</th>
        <th>Stats</th>
        <th>Model</th>
        <th>Enabled</th>
        <th></th>
      </tr>
    </thead>
    <tbody>
      {#each providers as p}
        {@const badge = getHealthBadge(p.id)}
        {@const health = healthSummary[p.id]}
        <tr>
          <td>{p.id}</td>
          <td>{p.name}</td>
          <td>{p.type}</td>
          <td>
            <span class="health-badge" style="background-color: {badge.color}">
              {badge.label}
            </span>
          </td>
          <td class="stats-cell">
            {#if health && health.total_requests > 0}
              <div class="stat-row">
                <span class="stat-label">Requests:</span>
                <span class="stat-value">{health.total_requests}</span>
              </div>
              <div class="stat-row">
                <span class="stat-label">Failures:</span>
                <span class="stat-value">{health.failure_rate}%</span>
              </div>
              <div class="stat-row">
                <span class="stat-label">Latency:</span>
                <span class="stat-value">{health.avg_latency_ms}ms</span>
              </div>
            {:else}
              <span class="no-data">No data</span>
            {/if}
          </td>
          <td>{p.model || "-"}</td>
          <td>{p.enabled ? "yes" : "no"}</td>
          <td>
            <button on:click={() => editProvider(p)}>Edit</button>
            <button on:click={() => removeProvider(p.id)}>Delete</button>
          </td>
        </tr>
      {/each}
    </tbody>
  </table>

  <h3>Add / Edit Provider</h3>

  <div class="form">
    <input placeholder="id (e.g. claude-sonnet)" bind:value={id} />
    <input placeholder="name (Claude Sonnet)" bind:value={name} />
    <input placeholder="type (anthropic | openai | mock)" bind:value={type} />
    <input placeholder="base url (optional)" bind:value={base_url} />
    <input
      placeholder="model (required for anthropic, e.g. claude-sonnet-4-5-20250929)"
      bind:value={model}
    />
    <input placeholder="api key" type="password" bind:value={api_key} />

    <label>
      <input type="checkbox" bind:checked={enabled} />
      Enabled
    </label>

    <button
      on:click={saveProvider}
      disabled={type === "anthropic" && !model}
    >
      Save provider
    </button>
  </div>
</div>

<style>
  .providers {
    border: 1px solid #ddd;
    padding: 1rem;
  }

  table {
    width: 100%;
    border-collapse: collapse;
    margin-bottom: 1rem;
  }

  th, td {
    border: 1px solid #ddd;
    padding: 0.4rem;
    text-align: left;
    font-size: 0.9rem;
  }

  .form {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 0.5rem;
  }

  .form input {
    padding: 0.4rem;
  }

  .error {
    color: red;
    margin-bottom: 0.5rem;
  }

  .health-badge {
    display: inline-block;
    padding: 0.25rem 0.5rem;
    border-radius: 4px;
    color: white;
    font-size: 0.75rem;
    font-weight: 500;
    text-transform: uppercase;
  }

  .stats-cell {
    font-size: 0.75rem;
  }

  .stat-row {
    display: flex;
    justify-content: space-between;
    gap: 0.5rem;
    margin-bottom: 0.15rem;
  }

  .stat-label {
    color: #6b7280;
  }

  .stat-value {
    font-weight: 500;
  }

  .no-data {
    color: #9ca3af;
    font-style: italic;
  }
</style>