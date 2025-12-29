<script>
  import { createEventDispatcher } from "svelte";
  import { upsertProvider, deleteProvider as deleteProviderApi } from "../../lib/api";

  export let providersList = [];
  export let healthSummary = {};

  const dispatch = createEventDispatcher();

  let showAddProviderForm = false;
  let editingProvider = null;
  let providerError = null;
  let providerForm = {
    id: "",
    name: "",
    type: "",
    base_url: "",
    model: "",
    api_key: "",
    enabled: true
  };

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
      avgLatency: health.avg_latency_ms
    };
  }

  async function saveProvider() {
    providerError = null;

    if (!providerForm.id || !providerForm.name || !providerForm.type) {
      providerError = "id, name and type are required";
      return;
    }

    if (providerForm.type === "anthropic" && !providerForm.model) {
      providerError = "Model is required for Anthropic providers";
      return;
    }

    try {
      await upsertProvider(providerForm);
      cancelProviderForm();
      dispatch("reload");
    } catch (e) {
      providerError = e.message;
    }
  }

  async function handleDeleteProvider(providerId) {
    if (!confirm(`Delete provider "${providerId}"? This cannot be undone.`)) {
      return;
    }

    try {
      await deleteProviderApi(providerId);
      dispatch("reload");
    } catch (e) {
      alert(`Failed to delete provider: ${e.message}`);
    }
  }

  function editProvider(p) {
    editingProvider = p.id;
    providerForm = {
      id: p.id,
      name: p.name,
      type: p.type,
      base_url: p.base_url || "",
      model: p.model || "",
      api_key: "", // never prefill secrets
      enabled: p.enabled
    };
    showAddProviderForm = true;
  }

  function cancelProviderForm() {
    showAddProviderForm = false;
    editingProvider = null;
    providerForm = {
      id: "",
      name: "",
      type: "",
      base_url: "",
      model: "",
      api_key: "",
      enabled: true
    };
    providerError = null;
  }
</script>

<div class="ai-providers-settings">
  <h2>Providers</h2>
  <p class="subtitle">Manage AI provider configurations and health status.</p>

  <button class="btn-primary" on:click={() => {
    if (showAddProviderForm) {
      cancelProviderForm();
    } else {
      showAddProviderForm = true;
      dispatch("reload");
    }
  }}>
    {showAddProviderForm ? "Cancel" : "+ Add Provider"}
  </button>

  {#if showAddProviderForm}
    <div class="add-form">
      <h3>{editingProvider ? "Edit Provider" : "New Provider"}</h3>
      <div class="form-row">
        <label>ID <input type="text" bind:value={providerForm.id} placeholder="e.g., anthropic-claude" disabled={!!editingProvider}/></label>
      </div>
      <div class="form-row">
        <label>Name <input type="text" bind:value={providerForm.name} placeholder="e.g., Anthropic Claude"/></label>
      </div>
      <div class="form-row">
        <label>Type
          <select bind:value={providerForm.type}>
            <option value="">Select type...</option>
            <option value="anthropic">Anthropic</option>
            <option value="openai">OpenAI</option>
            <option value="openrouter">OpenRouter</option>
            <option value="mock">Mock (for testing)</option>
          </select>
        </label>
      </div>
      <div class="form-row">
        <label>Model <input type="text" bind:value={providerForm.model} placeholder="e.g., claude-3-5-sonnet-20241022"/></label>
      </div>
      <div class="form-row">
        <label>Base URL (optional) <input type="text" bind:value={providerForm.base_url} placeholder="Custom API endpoint"/></label>
      </div>
      <div class="form-row">
        <label>API Key (leave empty to keep existing) <input type="password" bind:value={providerForm.api_key} placeholder="sk-..."/></label>
      </div>
      <div class="form-row">
        <label><input type="checkbox" bind:checked={providerForm.enabled}/> Enabled</label>
      </div>
      <div class="form-actions">
        <button class="btn-primary" on:click={saveProvider}>{editingProvider ? "Update" : "Save"}</button>
        <button class="btn-secondary" on:click={cancelProviderForm}>Cancel</button>
      </div>
      {#if providerError}
        <div class="save-status error">{providerError}</div>
      {/if}
    </div>
  {/if}

  {#if providersList.length > 0}
    <div class="providers-list">
      {#each providersList as p (p.id)}
        <div class="provider-card">
          <div class="provider-header">
            <h3>{p.name}</h3>
            <span class="health-badge" style="background-color: {getHealthBadge(p.id).color}">
              {getHealthBadge(p.id).label}
            </span>
          </div>
          <div class="provider-details">
            <div><strong>ID:</strong> {p.id}</div>
            <div><strong>Type:</strong> {p.type}</div>
            {#if p.model}
              <div><strong>Model:</strong> {p.model}</div>
            {/if}
            <div><strong>Status:</strong> {p.enabled ? "Enabled" : "Disabled"}</div>
            {#if getHealthStats(p.id)}
              <div class="health-stats">
                <span>Requests: {getHealthStats(p.id).requests}</span>
                <span>Failures: {getHealthStats(p.id).failureRate}%</span>
                <span>Latency: {getHealthStats(p.id).avgLatency}ms</span>
              </div>
            {/if}
          </div>
          <div class="provider-actions">
            <button class="btn-small" on:click={() => editProvider(p)}>Edit</button>
            <button class="btn-small btn-danger" on:click={() => handleDeleteProvider(p.id)}>Delete</button>
          </div>
        </div>
      {/each}
    </div>
  {:else}
    <div class="empty-state">
      <p>No providers configured yet.</p>
      <p class="hint">Add a provider to get started.</p>
    </div>
  {/if}
</div>

<style>
  .ai-providers-settings {
    width: 100%;
  }

  h2 {
    margin-top: 0;
    margin-bottom: var(--space-2);
  }

  .subtitle {
    color: var(--text-secondary);
    font-size: var(--font-size-sm);
    margin-bottom: var(--space-4);
  }

  .btn-primary {
    margin-bottom: var(--space-4);
  }

  .btn-small.btn-danger {
    color: var(--error-500);
    border-color: var(--error-500);
  }

  .btn-small.btn-danger:hover {
    background: var(--error-500);
    color: white;
  }

  .add-form {
    background: var(--bg-tertiary);
    border: 1px solid var(--border-primary);
    border-radius: var(--radius-lg);
    padding: var(--space-6);
    margin-bottom: var(--space-6);
  }

  .add-form h3 {
    margin-top: 0;
    margin-bottom: var(--space-4);
    color: var(--text-primary);
  }

  .form-row {
    margin-bottom: var(--space-4);
  }

  .form-row label {
    display: block;
    font-size: var(--font-size-sm);
    font-weight: 500;
    margin-bottom: var(--space-1);
    color: var(--text-primary);
  }

  .form-row input[type="text"],
  .form-row input[type="password"],
  .form-row select {
    width: 100%;
    max-width: 100%;
    padding: var(--space-2);
    border: 1px solid var(--border-primary);
    border-radius: var(--radius-sm);
    font-size: var(--font-size-sm);
    background: var(--bg-primary);
    color: var(--text-primary);
  }

  .form-row input[type="text"]:focus,
  .form-row input[type="password"]:focus,
  .form-row select:focus {
    outline: none;
    border-color: var(--border-focus);
  }

  .form-row input[type="checkbox"] {
    margin-right: var(--space-2);
  }

  .form-actions {
    display: flex;
    gap: var(--space-3);
    margin-top: var(--space-5);
  }

  .save-status {
    margin-top: var(--space-3);
    padding: var(--space-3) var(--space-4);
    border-radius: var(--radius-sm);
    font-size: var(--font-size-sm);
  }

  .save-status.error {
    background: var(--error-50);
    color: #721c24;
    border: 1px solid var(--error-500);
  }

  .providers-list {
    display: flex;
    flex-direction: column;
    gap: var(--space-4);
    margin-top: var(--space-6);
  }

  .provider-card {
    border: 1px solid var(--border-primary);
    border-radius: var(--radius-lg);
    padding: var(--space-4);
    background: var(--bg-tertiary);
  }

  .provider-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: var(--space-4);
  }

  .provider-header h3 {
    margin: 0;
    font-size: var(--font-size-lg);
    color: var(--text-primary);
  }

  .health-badge {
    padding: var(--space-1) var(--space-3);
    border-radius: var(--radius-sm);
    color: white;
    font-size: var(--font-size-xs);
    font-weight: 500;
  }

  .provider-details {
    margin-bottom: var(--space-4);
    font-size: var(--font-size-sm);
    color: var(--text-primary);
  }

  .provider-details div {
    margin-bottom: var(--space-2);
  }

  .health-stats {
    display: flex;
    gap: var(--space-4);
    margin-top: var(--space-2);
    color: var(--text-secondary);
  }

  .provider-actions {
    display: flex;
    gap: var(--space-2);
  }

  .btn-small {
    padding: 6px 12px;
    font-size: var(--font-size-sm);
    border: 1px solid var(--border-secondary);
    background: var(--bg-primary);
    color: var(--text-primary);
    border-radius: 4px;
    cursor: pointer;
    transition: all 0.15s;
  }

  .btn-small:hover:not(:disabled) {
    background: var(--bg-hover);
    border-color: var(--border-primary);
  }

  .empty-state {
    text-align: center;
    padding: var(--space-12) var(--space-4);
    color: var(--text-secondary);
  }

  .empty-state .hint {
    font-size: var(--font-size-sm);
    margin-top: var(--space-2);
    opacity: 0.7;
  }
</style>
