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

  function getProviderRiskAssessment(providerType, baseUrl) {
    // Provider risk assessment for OFFICIAL classification
    const riskProfiles = {
      'openai': {
        dataLocation: 'United States',
        riskLevel: 'MEDIUM',
        suitableForOfficial: true,
        notes: 'Data processed in US data centers. OpenAI has enterprise-grade security but data leaves UK jurisdiction.',
        recommendation: 'Suitable for OFFICIAL. For UK-hosted alternatives, consider Azure OpenAI with UK regions.'
      },
      'anthropic': {
        dataLocation: 'United States',
        riskLevel: 'MEDIUM',
        suitableForOfficial: true,
        notes: 'Data processed in US data centers. Anthropic has strong privacy commitments but data leaves UK jurisdiction.',
        recommendation: 'Suitable for OFFICIAL. Monitor for UK/EU hosting options as they become available.'
      },
      'openrouter': {
        dataLocation: 'Various (depends on model)',
        riskLevel: 'HIGH',
        suitableForOfficial: false,
        notes: 'Routes requests through multiple providers. Data location and processing varies by model selected.',
        recommendation: 'Not recommended for OFFICIAL data. Use direct provider connections for better control.'
      },
      'mock': {
        dataLocation: 'Local (no external API)',
        riskLevel: 'LOW',
        suitableForOfficial: true,
        notes: 'Test provider only. No data sent to external services.',
        recommendation: 'Safe for testing. Not suitable for production use.'
      }
    };

    // Check for Azure OpenAI (UK region)
    if (providerType === 'openai' && baseUrl && (baseUrl.includes('uksouth') || baseUrl.includes('ukwest'))) {
      return {
        dataLocation: 'United Kingdom',
        riskLevel: 'LOW',
        suitableForOfficial: true,
        notes: 'Azure OpenAI with UK region selected. Data stays within UK jurisdiction.',
        recommendation: 'Recommended for OFFICIAL data. UK Government approved service.'
      };
    }

    return riskProfiles[providerType] || {
      dataLocation: 'Unknown',
      riskLevel: 'UNKNOWN',
      suitableForOfficial: false,
      notes: 'Unknown provider type. Data location and security controls not assessed.',
      recommendation: 'Review provider documentation before using with OFFICIAL data.'
    };
  }

  function getRiskLevelColor(riskLevel) {
    const colors = {
      'LOW': '#10b981',
      'MEDIUM': '#f59e0b',
      'HIGH': '#ef4444',
      'UNKNOWN': '#9ca3af'
    };
    return colors[riskLevel] || colors.UNKNOWN;
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

<div class="tab-panel">
  <div class="page-header">
    <div>
      <h2>Providers</h2>
      <p class="subtitle">Manage AI provider configurations and health status.</p>
    </div>
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
  </div>

  {#if showAddProviderForm}
    <div class="add-form">
      <h3>{editingProvider ? "Edit Provider" : "New Provider"}</h3>
      <div class="form-group">
        <label for="provider-id">ID</label>
        <input id="provider-id" type="text" bind:value={providerForm.id} placeholder="e.g., anthropic-claude" disabled={!!editingProvider}/>
      </div>
      <div class="form-group">
        <label for="provider-name">Name</label>
        <input id="provider-name" type="text" bind:value={providerForm.name} placeholder="e.g., Anthropic Claude"/>
      </div>
      <div class="form-group">
        <label for="provider-type">Type</label>
        <select id="provider-type" bind:value={providerForm.type}>
          <option value="">Select type...</option>
          <option value="anthropic">Anthropic</option>
          <option value="openai">OpenAI</option>
          <option value="openrouter">OpenRouter</option>
          <option value="mock">Mock (for testing)</option>
        </select>
      </div>
      <div class="form-group">
        <label for="provider-model">Model</label>
        <input id="provider-model" type="text" bind:value={providerForm.model} placeholder="e.g., claude-3-5-sonnet-20241022"/>
      </div>
      <div class="form-group">
        <label for="provider-base-url">Base URL (optional)</label>
        <input id="provider-base-url" type="text" bind:value={providerForm.base_url} placeholder="Custom API endpoint"/>
      </div>
      <div class="form-group">
        <label for="provider-api-key">API Key (leave empty to keep existing)</label>
        <input id="provider-api-key" type="password" bind:value={providerForm.api_key} placeholder="sk-..."/>
      </div>
      <div class="form-group">
        <label class="checkbox-label">
          <input type="checkbox" bind:checked={providerForm.enabled}/> Enabled
        </label>
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

          <!-- OFFICIAL Classification Risk Assessment -->
          {#if p.type !== 'mock'}
            {@const riskAssessment = getProviderRiskAssessment(p.type, p.base_url)}
            <div class="risk-assessment">
              <div class="risk-header">
                <strong>OFFICIAL Classification Risk Assessment</strong>
                <span class="risk-badge" style="background-color: {getRiskLevelColor(riskAssessment.riskLevel)}">
                  {riskAssessment.riskLevel} RISK
                </span>
              </div>
              <div class="risk-details">
                <div class="risk-row">
                  <span class="risk-label">Data Location:</span>
                  <span class="risk-value">{riskAssessment.dataLocation}</span>
                </div>
                <div class="risk-row">
                  <span class="risk-label">Suitable for OFFICIAL:</span>
                  <span class="risk-value" style="color: {riskAssessment.suitableForOfficial ? '#10b981' : '#ef4444'}">
                    {riskAssessment.suitableForOfficial ? 'Yes' : 'No'}
                  </span>
                </div>
                <div class="risk-notes">
                  <p><strong>Notes:</strong> {riskAssessment.notes}</p>
                  <p><strong>Recommendation:</strong> {riskAssessment.recommendation}</p>
                </div>
              </div>
            </div>
          {/if}

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
  /* Global styles used (.form-group, .form-actions imported from forms.css/.section from settings.css)
     Only component-specific styles below */

  .page-header {
    display: flex;
    justify-content: space-between;
    align-items: flex-start;
    margin-bottom: var(--space-6);
    gap: var(--space-4);
  }

  .page-header h2 {
    margin: 0 0 var(--space-2) 0;
  }

  .page-header .subtitle {
    margin: 0;
  }

  /* Form container */
  .add-form {
    background: var(--bg-tertiary);
    border: 1px solid var(--border-primary);
    border-radius: var(--radius-lg);
    padding: var(--space-5) var(--space-6);
    margin-bottom: var(--space-6);
  }

  .add-form h3 {
    margin: 0 0 var(--space-4) 0;
    color: var(--text-primary);
  }

  /* Checkbox styling */
  .checkbox-label {
    display: flex;
    align-items: center;
    gap: var(--space-2);
    cursor: pointer;
    font-weight: 500;
  }

  .checkbox-label input[type="checkbox"] {
    width: auto;
    cursor: pointer;
  }

  /* Provider card styling (unique to this page) */
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

  /* Risk Assessment Styling */
  .risk-assessment {
    margin: var(--space-4) 0;
    padding: var(--space-4);
    background: var(--bg-secondary);
    border: 1px solid var(--border-primary);
    border-radius: var(--radius-md);
  }

  .risk-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: var(--space-3);
    padding-bottom: var(--space-2);
    border-bottom: 1px solid var(--border-primary);
  }

  .risk-header strong {
    color: var(--text-primary);
    font-size: var(--font-size-sm);
  }

  .risk-badge {
    padding: var(--space-1) var(--space-3);
    border-radius: var(--radius-sm);
    color: white;
    font-size: var(--font-size-xs);
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.5px;
  }

  .risk-details {
    font-size: var(--font-size-sm);
  }

  .risk-row {
    display: flex;
    justify-content: space-between;
    margin-bottom: var(--space-2);
    padding: var(--space-1) 0;
  }

  .risk-label {
    color: var(--text-secondary);
    font-weight: 500;
  }

  .risk-value {
    color: var(--text-primary);
    font-weight: 500;
  }

  .risk-notes {
    margin-top: var(--space-3);
    padding-top: var(--space-3);
    border-top: 1px solid var(--border-primary);
  }

  .risk-notes p {
    margin: 0 0 var(--space-2) 0;
    color: var(--text-secondary);
    line-height: 1.5;
  }

  .risk-notes p:last-child {
    margin-bottom: 0;
  }

  .risk-notes strong {
    color: var(--text-primary);
  }
</style>
