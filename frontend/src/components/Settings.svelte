<script>
  import { onMount } from "svelte";
  import {
    getProviders,
    listProviders,
    upsertProvider,
    deleteProvider as deleteProviderApi,
    getProviderHealth,
    getIntents,
    createIntent,
    updateIntent,
    deleteIntent,
    getRoutingRules,
    setRoutingRule,
    deleteRoutingRule,
    getDebugFlag,
    setDebugFlag,
    getSystemPromptConfig,
    updateSystemPromptConfig,
    getMemories,
    createMemory,
    deleteMemory,
    pinMemory
  } from "../lib/api";

  let providers = [];
  let intents = [];
  let rules = {};
  let debugEnabled = false;
  let loaded = false;
  let savingDebug = false;

  // System prompt configuration state
  let systemPromptConfig = {
    persona_name: "THEO",
    tone: "professional, conversational, direct",
    style_rules: "- No em dashes\n- Be concise first, then detailed\n- Provide full working solutions when asked for code\n- Maintain a consistent persona regardless of model",
    custom_instructions: ""
  };
  let savingPrompt = false;
  let promptSaveStatus = null;

  // Active tab state
  let activeTab = "system-prompt";

  // Memory state
  let memories = [];
  let loadingMemories = false;
  let filterType = "all";
  let newMemory = {
    type: "fact",
    key: "",
    value: "",
    pinned: false
  };
  let showAddMemoryForm = false;

  // Provider state
  let providersList = [];
  let healthSummary = {};
  let providerForm = {
    id: "",
    name: "",
    type: "",
    base_url: "",
    model: "",
    api_key: "",
    enabled: true
  };
  let showAddProviderForm = false;
  let providerError = null;

  // Intent editor state
  let editingIntent = null;
  let showIntentForm = false;
  let intentForm = {
    id: "",
    name: "",
    description: "",
    keywords: "",
    priority: 50,
    enabled: true
  };

  async function load() {
    providers = await getProviders();
    intents = await getIntents();
    rules = await getRoutingRules();
    const flag = await getDebugFlag();
    debugEnabled = flag === true || flag === "true" || flag?.enabled === true;

    // Load system prompt config
    try {
      const config = await getSystemPromptConfig();
      systemPromptConfig = {
        persona_name: config.persona_name || "THEO",
        tone: config.tone || "professional, conversational, direct",
        style_rules: config.style_rules || "- No em dashes\n- Be concise first, then detailed\n- Provide full working solutions when asked for code\n- Maintain a consistent persona regardless of model",
        custom_instructions: config.custom_instructions || ""
      };
    } catch (e) {
      console.warn("Failed to load system prompt config:", e);
    }

    // Load memories and providers
    await loadMemories();
    await loadProvidersList();

    loaded = true;
  }

  async function updateRule(intent, providerId) {
    if (!providerId) {
      await deleteRoutingRule(intent);
      delete rules[intent];
    } else {
      await setRoutingRule(intent, providerId);
      rules[intent] = providerId;
    }
  }

  async function toggleDebug(value) {
    savingDebug = true;
    await setDebugFlag(value);
    debugEnabled = value;
    savingDebug = false;
  }

  async function saveSystemPrompt() {
    try {
      savingPrompt = true;
      promptSaveStatus = null;
      await updateSystemPromptConfig(systemPromptConfig);
      promptSaveStatus = "Settings saved successfully!";
      setTimeout(() => {
        promptSaveStatus = null;
      }, 3000);
    } catch (e) {
      promptSaveStatus = `Error: ${e.message}`;
    } finally {
      savingPrompt = false;
    }
  }

  function startNewIntent() {
    editingIntent = null;
    intentForm = {
      id: "",
      name: "",
      description: "",
      keywords: "",
      priority: 50,
      enabled: true
    };
    showIntentForm = true;
  }

  function editIntent(intent) {
    editingIntent = intent.id;
    intentForm = {
      id: intent.id,
      name: intent.name,
      description: intent.description || "",
      keywords: intent.keywords || "",
      priority: intent.priority || 50,
      enabled: intent.enabled !== false
    };
    showIntentForm = true;
  }

  function cancelIntentForm() {
    showIntentForm = false;
    editingIntent = null;
    intentForm = {
      id: "",
      name: "",
      description: "",
      keywords: "",
      priority: 50,
      enabled: true
    };
  }

  async function saveIntent() {
    try {
      if (editingIntent) {
        // Update existing intent
        await updateIntent(editingIntent, {
          name: intentForm.name,
          description: intentForm.description,
          keywords: intentForm.keywords,
          priority: parseInt(intentForm.priority),
          enabled: intentForm.enabled
        });
      } else {
        // Create new intent
        await createIntent({
          id: intentForm.id,
          name: intentForm.name,
          description: intentForm.description,
          keywords: intentForm.keywords,
          priority: parseInt(intentForm.priority),
          enabled: intentForm.enabled
        });
      }

      // Reload intents
      intents = await getIntents();
      cancelIntentForm();
    } catch (e) {
      alert(`Failed to save intent: ${e.message}`);
    }
  }

  async function removeIntent(intentId) {
    if (!confirm(`Delete intent "${intentId}"? This will also remove its routing rule.`)) {
      return;
    }

    try {
      await deleteIntent(intentId);
      intents = await getIntents();
      // Remove routing rule if it exists
      if (rules[intentId]) {
        delete rules[intentId];
      }
    } catch (e) {
      alert(`Failed to delete intent: ${e.message}`);
    }
  }

  async function toggleIntentEnabled(intent) {
    try {
      await updateIntent(intent.id, {
        enabled: !intent.enabled
      });
      intents = await getIntents();
    } catch (e) {
      alert(`Failed to toggle intent: ${e.message}`);
    }
  }

  // Memory management functions
  async function loadMemories() {
    try {
      loadingMemories = true;
      const params = filterType !== "all" ? { type: filterType } : {};
      memories = await getMemories(params);
    } catch (err) {
      console.error("Failed to load memories", err);
    } finally {
      loadingMemories = false;
    }
  }

  async function handleCreateMemory() {
    if (!newMemory.key.trim() || !newMemory.value.trim()) {
      alert("Key and value are required");
      return;
    }

    try {
      await createMemory(newMemory);
      await loadMemories();
      newMemory = { type: "fact", key: "", value: "", pinned: false };
      showAddMemoryForm = false;
    } catch (err) {
      console.error("Failed to create memory", err);
      alert("Failed to create memory");
    }
  }

  async function handleDeleteMemory(memoryId) {
    if (!confirm("Delete this memory?")) return;

    try {
      await deleteMemory(memoryId);
      await loadMemories();
    } catch (err) {
      console.error("Failed to delete memory", err);
    }
  }

  async function handleTogglePin(memoryId, currentlyPinned) {
    try {
      await pinMemory(memoryId, !currentlyPinned);
      await loadMemories();
    } catch (err) {
      console.error("Failed to toggle pin", err);
    }
  }

  function formatDate(dateString) {
    if (!dateString) return "";
    const date = new Date(dateString);
    const now = new Date();
    const diffMs = now - date;
    const diffDays = Math.floor(diffMs / (1000 * 60 * 60 * 24));

    if (diffDays === 0) return "Today";
    if (diffDays === 1) return "Yesterday";
    if (diffDays < 7) return `${diffDays} days ago`;
    if (diffDays < 30) return `${Math.floor(diffDays / 7)} weeks ago`;
    return `${Math.floor(diffDays / 30)} months ago`;
  }

  function getTypeColor(type) {
    const colors = {
      fact: "#3b82f6",
      preference: "#8b5cf6",
      goal: "#10b981",
      context: "#f59e0b"
    };
    return colors[type] || "#6b7280";
  }

  // Provider management functions
  async function loadProvidersList() {
    try {
      providersList = await listProviders();
      healthSummary = await getProviderHealth();
    } catch (e) {
      providerError = e.message;
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
      providerForm = {
        id: "",
        name: "",
        type: "",
        base_url: "",
        model: "",
        api_key: "",
        enabled: true
      };
      showAddProviderForm = false;
      await loadProvidersList();
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
      await loadProvidersList();
    } catch (e) {
      alert(`Failed to delete provider: ${e.message}`);
    }
  }

  $: {
    if (filterType !== undefined) {
      loadMemories();
    }
  }

  onMount(load);
</script>

<div class="settings">
  <h1>Settings</h1>

  <!-- Tab Navigation -->
  <div class="tabs">
    <button
      class="tab"
      class:active={activeTab === "system-prompt"}
      on:click={() => activeTab = "system-prompt"}
    >
      System Prompt
    </button>
    <button
      class="tab"
      class:active={activeTab === "intents"}
      on:click={() => activeTab = "intents"}
    >
      Intents
    </button>
    <button
      class="tab"
      class:active={activeTab === "routing"}
      on:click={() => activeTab = "routing"}
    >
      Routing
    </button>
    <button
      class="tab"
      class:active={activeTab === "memory"}
      on:click={() => activeTab = "memory"}
    >
      Memory
    </button>
    <button
      class="tab"
      class:active={activeTab === "providers"}
      on:click={() => activeTab = "providers"}
    >
      Providers
    </button>
    <button
      class="tab"
      class:active={activeTab === "debug"}
      on:click={() => activeTab = "debug"}
    >
      Debug
    </button>
  </div>

  <!-- Tab Content -->
  <div class="tab-content">
    <!-- System Prompt Tab -->
    {#if activeTab === "system-prompt"}
      <div class="tab-panel">
        <h2>System Prompt Configuration</h2>
        <p class="subtitle">Customize how THEO responds and behaves.</p>

  <div class="system-prompt-form">
    <div class="form-group">
      <label for="persona-name">Persona Name</label>
      <input
        id="persona-name"
        type="text"
        bind:value={systemPromptConfig.persona_name}
        placeholder="e.g., THEO"
      />
      <small>The name your AI assistant will identify as</small>
    </div>

    <div class="form-group">
      <label for="tone">Tone</label>
      <input
        id="tone"
        type="text"
        bind:value={systemPromptConfig.tone}
        placeholder="e.g., professional, conversational, direct"
      />
      <small>The overall tone and style of responses</small>
    </div>

    <div class="form-group">
      <label for="style-rules">Style Rules</label>
      <textarea
        id="style-rules"
        bind:value={systemPromptConfig.style_rules}
        placeholder="- No em dashes&#10;- Be concise first, then detailed&#10;- Provide full working solutions when asked for code"
        rows="6"
      />
      <small>Bullet-pointed list of style guidelines (one per line)</small>
    </div>

    <div class="form-group">
      <label for="custom-instructions">Custom Instructions (Optional)</label>
      <textarea
        id="custom-instructions"
        bind:value={systemPromptConfig.custom_instructions}
        placeholder="Add any additional instructions or context..."
        rows="4"
      />
      <small>Any extra instructions or preferences for your AI assistant</small>
    </div>

    <div class="form-actions">
      <button
        class="btn-primary"
        on:click={saveSystemPrompt}
        disabled={savingPrompt}
      >
        {savingPrompt ? "Saving..." : "Save Settings"}
      </button>
    </div>

    {#if promptSaveStatus}
      <div class="save-status" class:success={promptSaveStatus.includes("success")} class:error={promptSaveStatus.includes("Error")}>
        {promptSaveStatus}
      </div>
    {/if}
        </div>
      </div>
    {/if}

    <!-- Intents Tab -->
    {#if activeTab === "intents"}
      <div class="tab-panel">
        <h2>Intents</h2>
        <p class="subtitle">Define custom intents to classify and route your requests.</p>

        <button class="btn-primary" on:click={startNewIntent}>
          + New Intent
        </button>

  {#if showIntentForm}
    <div class="intent-form">
      <h3>{editingIntent ? "Edit Intent" : "New Intent"}</h3>

      <div class="form-group">
        <label for="intent-id">ID</label>
        <input
          id="intent-id"
          type="text"
          bind:value={intentForm.id}
          placeholder="e.g., data-analysis"
          disabled={!!editingIntent}
          required
        />
        <small>Unique identifier (lowercase, hyphens allowed)</small>
      </div>

      <div class="form-group">
        <label for="intent-name">Name</label>
        <input
          id="intent-name"
          type="text"
          bind:value={intentForm.name}
          placeholder="e.g., Data Analysis"
          required
        />
      </div>

      <div class="form-group">
        <label for="intent-description">Description</label>
        <textarea
          id="intent-description"
          bind:value={intentForm.description}
          placeholder="What is this intent used for?"
          rows="2"
        />
      </div>

      <div class="form-group">
        <label for="intent-keywords">Keywords (comma-separated)</label>
        <textarea
          id="intent-keywords"
          bind:value={intentForm.keywords}
          placeholder="e.g., analyze,data,chart,graph,statistics"
          rows="2"
        />
        <small>Messages matching any keyword will use this intent</small>
      </div>

      <div class="form-group">
        <label for="intent-priority">Priority</label>
        <input
          id="intent-priority"
          type="number"
          bind:value={intentForm.priority}
          min="0"
          max="100"
        />
        <small>Higher priority intents are checked first (0-100)</small>
      </div>

      <div class="form-group">
        <label>
          <input
            type="checkbox"
            bind:checked={intentForm.enabled}
          />
          Enabled
        </label>
      </div>

      <div class="form-actions">
        <button class="btn-primary" on:click={saveIntent}>
          {editingIntent ? "Save Changes" : "Create Intent"}
        </button>
        <button class="btn-secondary" on:click={cancelIntentForm}>
          Cancel
        </button>
      </div>
    </div>
  {/if}

  <div class="intents-list">
    {#each intents as intent}
      <div class="intent-card" class:disabled={!intent.enabled}>
        <div class="intent-header">
          <div class="intent-info">
            <h4>
              {intent.name}
              <span class="intent-id">({intent.id})</span>
              {#if !intent.enabled}
                <span class="badge-disabled">Disabled</span>
              {/if}
            </h4>
            {#if intent.description}
              <p class="intent-description">{intent.description}</p>
            {/if}
          </div>
          <div class="intent-priority">
            Priority: {intent.priority}
          </div>
        </div>

        {#if intent.keywords}
          <div class="intent-keywords">
            <strong>Keywords:</strong> {intent.keywords}
          </div>
        {:else}
          <div class="intent-keywords empty">
            No keywords (fallback intent)
          </div>
        {/if}

        <div class="intent-actions">
          <button class="btn-small" on:click={() => editIntent(intent)}>
            Edit
          </button>
          <button class="btn-small" on:click={() => toggleIntentEnabled(intent)}>
            {intent.enabled ? "Disable" : "Enable"}
          </button>
          <button class="btn-small btn-danger" on:click={() => removeIntent(intent.id)}>
            Delete
          </button>
        </div>
      </div>
    {/each}
        </div>
      </div>
    {/if}

    <!-- Routing Tab -->
    {#if activeTab === "routing"}
      <div class="tab-panel">
        <h2>Routing Rules</h2>
        <p class="subtitle">Assign specific providers to intents (optional).</p>

        {#each intents.filter(i => i.enabled) as intent}
    <div class="rule">
      <label>{intent.name}</label>

      <select
        on:change={(e) => updateRule(intent.id, e.target.value)}
        value={rules[intent.id] || ""}
      >
        <option value="">Auto</option>

        {#each providers as p}
          <option value={p.id}>
            {p.name}
          </option>
        {/each}
      </select>
    </div>
        {/each}
      </div>
    {/if}

    <!-- Memory Tab -->
    {#if activeTab === "memory"}
      <div class="tab-panel">
        <div class="memory-header">
          <h2>Memory</h2>
          <button class="btn-add" on:click={() => showAddMemoryForm = !showAddMemoryForm}>
            {showAddMemoryForm ? "Cancel" : "+ Add Memory"}
          </button>
        </div>

        {#if showAddMemoryForm}
          <div class="add-form">
            <div class="form-row">
              <label>
                Type
                <select bind:value={newMemory.type}>
                  <option value="fact">Fact</option>
                  <option value="preference">Preference</option>
                  <option value="goal">Goal</option>
                  <option value="context">Context</option>
                </select>
              </label>
            </div>

            <div class="form-row">
              <label>
                Key
                <input type="text" bind:value={newMemory.key} placeholder="e.g., project" />
              </label>
            </div>

            <div class="form-row">
              <label>
                Value
                <input type="text" bind:value={newMemory.value} placeholder="e.g., Atlas" />
              </label>
            </div>

            <div class="form-row">
              <label>
                <input type="checkbox" bind:checked={newMemory.pinned} />
                Pin this memory (always included)
              </label>
            </div>

            <div class="form-actions">
              <button class="btn-primary" on:click={handleCreateMemory}>Save</button>
              <button class="btn-secondary" on:click={() => showAddMemoryForm = false}>Cancel</button>
            </div>
          </div>
        {/if}

        <div class="filter-bar">
          <button
            class:active={filterType === "all"}
            on:click={() => filterType = "all"}
          >
            All
          </button>
          <button
            class:active={filterType === "fact"}
            on:click={() => filterType = "fact"}
          >
            Facts
          </button>
          <button
            class:active={filterType === "preference"}
            on:click={() => filterType = "preference"}
          >
            Preferences
          </button>
          <button
            class:active={filterType === "goal"}
            on:click={() => filterType = "goal"}
          >
            Goals
          </button>
          <button
            class:active={filterType === "context"}
            on:click={() => filterType = "context"}
          >
            Context
          </button>
        </div>

        {#if loadingMemories}
          <div class="loading">Loading memories...</div>
        {:else if memories.length === 0}
          <div class="empty-state">
            <p>No memories stored yet.</p>
            <p class="hint">Use the form above to add a memory.</p>
          </div>
        {:else}
          <div class="memory-list">
            {#each memories as mem (mem.id)}
              <div class="memory-item" class:pinned={mem.pinned}>
                <div class="memory-header-row">
                  <span class="memory-type" style="background-color: {getTypeColor(mem.type)}">
                    {mem.type}
                  </span>
                  {#if mem.pinned}
                    <span class="pin-badge">📌 Pinned</span>
                  {/if}
                  <span class="memory-score">Score: {mem.relevance_score}</span>
                </div>

                <div class="memory-content">
                  <strong>{mem.key}:</strong> {mem.value}
                </div>

                <div class="memory-meta">
                  <span>Created {formatDate(mem.created_at)}</span>
                  <span>•</span>
                  <span>Used {mem.access_count} times</span>
                  <span>•</span>
                  <span>Last accessed {formatDate(mem.last_accessed_at)}</span>
                </div>

                <div class="memory-actions">
                  <button
                    class="btn-pin"
                    on:click={() => handleTogglePin(mem.id, mem.pinned)}
                  >
                    {mem.pinned ? "Unpin" : "Pin"}
                  </button>
                  <button
                    class="btn-delete"
                    on:click={() => handleDeleteMemory(mem.id)}
                  >
                    Delete
                  </button>
                </div>
              </div>
            {/each}
          </div>
        {/if}
      </div>
    {/if}

    <!-- Providers Tab -->
    {#if activeTab === "providers"}
      <div class="tab-panel">
        <h2>Providers</h2>
        <p class="subtitle">Manage AI provider configurations and health status.</p>

        <button class="btn-primary" on:click={() => {showAddProviderForm = !showAddProviderForm; loadProvidersList();}}>
          {showAddProviderForm ? "Cancel" : "+ Add Provider"}
        </button>

        {#if showAddProviderForm}
          <div class="add-form">
            <div class="form-row">
              <label>ID <input type="text" bind:value={providerForm.id} placeholder="e.g., anthropic-claude"/></label>
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
              <button class="btn-primary" on:click={saveProvider}>Save</button>
              <button class="btn-secondary" on:click={() => showAddProviderForm = false}>Cancel</button>
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
    {/if}

    <!-- Debug Tab -->
    {#if activeTab === "debug"}
      <div class="tab-panel">
        <h2>Debugging</h2>
        <p class="subtitle">Enable debug logging for troubleshooting.</p>

        <div class="rule">
          <label>Debug logs</label>
          <input
            type="checkbox"
            checked={debugEnabled}
            disabled={savingDebug}
            on:change={(e) => toggleDebug(e.target.checked)}
          />
        </div>
      </div>
    {/if}
  </div>
</div>

<style>
  .settings {
    padding: 0;
    max-width: 1200px;
    margin: 0 auto;
    height: 100%;
    display: flex;
    flex-direction: column;
  }

  h1 {
    padding: 20px 24px;
    margin: 0;
    border-bottom: 1px solid #dee2e6;
    background: #f8f9fa;
    font-size: 24px;
  }

  .tabs {
    display: flex;
    background: #f8f9fa;
    border-bottom: 2px solid #dee2e6;
    padding: 0 24px;
    gap: 4px;
  }

  .tab {
    padding: 12px 24px;
    border: none;
    background: transparent;
    cursor: pointer;
    font-size: 14px;
    font-weight: 500;
    color: #6c757d;
    border-bottom: 3px solid transparent;
    transition: all 0.2s;
  }

  .tab:hover {
    color: #495057;
    background: rgba(0, 0, 0, 0.03);
  }

  .tab.active {
    color: #007bff;
    border-bottom-color: #007bff;
    background: white;
  }

  .tab-content {
    flex: 1;
    overflow-y: auto;
    padding: 24px;
  }

  .tab-panel {
    max-width: 900px;
    margin: 0 auto;
  }

  h2 {
    margin-top: 0;
    margin-bottom: 8px;
  }

  .subtitle {
    color: #666;
    font-size: 14px;
    margin-bottom: 16px;
  }

  .rule {
    display: flex;
    align-items: center;
    gap: 12px;
    margin-bottom: 12px;
  }

  label {
    width: 140px;
    font-weight: 500;
  }

  select {
    flex: 1;
    padding: 6px;
    border: 1px solid #ccc;
    border-radius: 4px;
  }

  input[type="checkbox"] {
    transform: scale(1.2);
    cursor: pointer;
  }

  .btn-primary {
    background: #007bff;
    color: white;
    border: none;
    padding: 10px 20px;
    border-radius: 4px;
    cursor: pointer;
    font-size: 14px;
    margin-bottom: 16px;
  }

  .btn-primary:hover {
    background: #0056b3;
  }

  .btn-secondary {
    background: #6c757d;
    color: white;
    border: none;
    padding: 10px 20px;
    border-radius: 4px;
    cursor: pointer;
    font-size: 14px;
  }

  .btn-secondary:hover {
    background: #5a6268;
  }

  .btn-small {
    padding: 4px 12px;
    font-size: 12px;
    border: 1px solid #ccc;
    background: white;
    border-radius: 4px;
    cursor: pointer;
  }

  .btn-small:hover {
    background: #f0f0f0;
  }

  .btn-small.btn-danger {
    color: #dc3545;
    border-color: #dc3545;
  }

  .btn-small.btn-danger:hover {
    background: #dc3545;
    color: white;
  }

  .intent-form {
    background: #f8f9fa;
    border: 1px solid #dee2e6;
    border-radius: 8px;
    padding: 20px;
    margin-bottom: 24px;
  }

  .intent-form h3 {
    margin-top: 0;
    margin-bottom: 16px;
  }

  .form-group {
    margin-bottom: 16px;
  }

  .form-group label {
    display: block;
    width: auto;
    margin-bottom: 4px;
    font-weight: 600;
  }

  .form-group input[type="text"],
  .form-group input[type="number"],
  .form-group textarea {
    width: 100%;
    padding: 8px;
    border: 1px solid #ced4da;
    border-radius: 4px;
    font-family: inherit;
  }

  .form-group small {
    display: block;
    color: #6c757d;
    font-size: 12px;
    margin-top: 4px;
  }

  .form-actions {
    display: flex;
    gap: 12px;
    margin-top: 20px;
  }

  .intents-list {
    display: flex;
    flex-direction: column;
    gap: 12px;
    margin-bottom: 24px;
  }

  .intent-card {
    border: 1px solid #dee2e6;
    border-radius: 8px;
    padding: 16px;
    background: white;
  }

  .intent-card.disabled {
    opacity: 0.6;
    background: #f8f9fa;
  }

  .intent-header {
    display: flex;
    justify-content: space-between;
    align-items: flex-start;
    margin-bottom: 12px;
  }

  .intent-info h4 {
    margin: 0 0 4px 0;
    display: flex;
    align-items: center;
    gap: 8px;
  }

  .intent-id {
    color: #6c757d;
    font-size: 14px;
    font-weight: normal;
  }

  .badge-disabled {
    background: #dc3545;
    color: white;
    padding: 2px 8px;
    border-radius: 4px;
    font-size: 12px;
    font-weight: normal;
  }

  .intent-description {
    margin: 0;
    color: #666;
    font-size: 14px;
  }

  .intent-priority {
    background: #e9ecef;
    padding: 4px 12px;
    border-radius: 4px;
    font-size: 12px;
    font-weight: 600;
    color: #495057;
  }

  .intent-keywords {
    background: #f8f9fa;
    padding: 8px 12px;
    border-radius: 4px;
    font-size: 13px;
    margin-bottom: 12px;
  }

  .intent-keywords.empty {
    font-style: italic;
    color: #6c757d;
  }

  .intent-keywords strong {
    color: #495057;
  }

  .intent-actions {
    display: flex;
    gap: 8px;
  }

  .system-prompt-form {
    background: #f8f9fa;
    border: 1px solid #dee2e6;
    border-radius: 8px;
    padding: 20px;
    margin-bottom: 24px;
  }

  .save-status {
    margin-top: 12px;
    padding: 10px 16px;
    border-radius: 4px;
    font-size: 14px;
  }

  .save-status.success {
    background: #d4edda;
    color: #155724;
    border: 1px solid #c3e6cb;
  }

  .save-status.error {
    background: #f8d7da;
    color: #721c24;
    border: 1px solid #f5c6cb;
  }

  .memory-form {
    background: #f8f9fa;
    border: 1px solid #dee2e6;
    border-radius: 8px;
    padding: 20px;
    margin-bottom: 24px;
  }

  .memory-help {
    background: #fff3cd;
    border: 1px solid #ffeaa7;
    border-radius: 8px;
    padding: 20px;
  }

  .memory-help h3 {
    margin-top: 0;
    margin-bottom: 12px;
    font-size: 16px;
    color: #856404;
  }

  .memory-help ul {
    margin: 0;
    padding-left: 20px;
    color: #856404;
  }

  .memory-help li {
    margin-bottom: 8px;
  }

  /* Memory component styles */
  .memory-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 1.5rem;
  }

  .btn-add {
    padding: 0.5rem 1rem;
    background: #3b82f6;
    color: white;
    border: none;
    border-radius: 6px;
    cursor: pointer;
    font-size: 0.875rem;
  }

  .btn-add:hover {
    background: #2563eb;
  }

  .add-form {
    background: #f9fafb;
    border: 1px solid #e5e7eb;
    border-radius: 8px;
    padding: 1.5rem;
    margin-bottom: 1.5rem;
  }

  .form-row {
    margin-bottom: 1rem;
  }

  .form-row label {
    display: block;
    font-size: 0.875rem;
    font-weight: 500;
    margin-bottom: 0.25rem;
  }

  .form-row input[type="text"],
  .form-row input[type="password"],
  .form-row select {
    width: 100%;
    padding: 0.5rem;
    border: 1px solid #d1d5db;
    border-radius: 4px;
    font-size: 0.875rem;
  }

  .form-row input[type="checkbox"] {
    margin-right: 0.5rem;
  }

  .filter-bar {
    display: flex;
    gap: 0.5rem;
    margin-bottom: 1.5rem;
    flex-wrap: wrap;
  }

  .filter-bar button {
    padding: 0.5rem 1rem;
    border: 1px solid #d1d5db;
    background: white;
    border-radius: 6px;
    cursor: pointer;
    font-size: 0.875rem;
    transition: all 0.2s;
  }

  .filter-bar button:hover {
    background: #f3f4f6;
  }

  .filter-bar button.active {
    background: #3b82f6;
    color: white;
    border-color: #3b82f6;
  }

  .loading,
  .empty-state {
    text-align: center;
    padding: 3rem 1rem;
    color: #6b7280;
  }

  .empty-state .hint {
    font-size: 0.875rem;
    margin-top: 0.5rem;
    opacity: 0.7;
  }

  .memory-list {
    display: flex;
    flex-direction: column;
    gap: 1rem;
  }

  .memory-item {
    border: 1px solid #e5e7eb;
    border-radius: 8px;
    padding: 1rem;
    background: white;
    transition: box-shadow 0.2s;
  }

  .memory-item:hover {
    box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1);
  }

  .memory-item.pinned {
    border-color: #fbbf24;
    background: #fffbeb;
  }

  .memory-header-row {
    display: flex;
    align-items: center;
    gap: 0.5rem;
    margin-bottom: 0.5rem;
    flex-wrap: wrap;
  }

  .memory-type {
    font-size: 0.75rem;
    padding: 0.25rem 0.5rem;
    border-radius: 4px;
    color: white;
    font-weight: 500;
    text-transform: uppercase;
  }

  .pin-badge {
    font-size: 0.75rem;
    color: #f59e0b;
    font-weight: 500;
  }

  .memory-score {
    font-size: 0.75rem;
    color: #6b7280;
    margin-left: auto;
  }

  .memory-content {
    font-size: 0.875rem;
    margin-bottom: 0.5rem;
    line-height: 1.5;
  }

  .memory-content strong {
    color: #1f2937;
  }

  .memory-meta {
    font-size: 0.75rem;
    color: #9ca3af;
    display: flex;
    gap: 0.5rem;
    margin-bottom: 0.75rem;
    flex-wrap: wrap;
  }

  .memory-actions {
    display: flex;
    gap: 0.5rem;
  }

  .btn-pin,
  .btn-delete {
    padding: 0.25rem 0.75rem;
    font-size: 0.75rem;
    border: 1px solid #d1d5db;
    background: white;
    border-radius: 4px;
    cursor: pointer;
    transition: all 0.2s;
  }

  .btn-pin:hover {
    background: #fef3c7;
    border-color: #fbbf24;
  }

  .btn-delete:hover {
    background: #fee2e2;
    border-color: #f87171;
    color: #dc2626;
  }

  /* Provider component styles */
  .providers-list {
    display: flex;
    flex-direction: column;
    gap: 1rem;
    margin-top: 1.5rem;
  }

  .provider-card {
    border: 1px solid #dee2e6;
    border-radius: 8px;
    padding: 1rem;
    background: white;
  }

  .provider-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 1rem;
  }

  .provider-header h3 {
    margin: 0;
    font-size: 1.1rem;
  }

  .health-badge {
    padding: 0.25rem 0.75rem;
    border-radius: 4px;
    color: white;
    font-size: 0.75rem;
    font-weight: 500;
  }

  .provider-details {
    margin-bottom: 1rem;
    font-size: 0.875rem;
  }

  .provider-details div {
    margin-bottom: 0.5rem;
  }

  .health-stats {
    display: flex;
    gap: 1rem;
    margin-top: 0.5rem;
    color: #6b7280;
  }

  .provider-actions {
    display: flex;
    gap: 0.5rem;
  }
</style>
