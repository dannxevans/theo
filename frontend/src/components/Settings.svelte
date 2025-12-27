<script>
  import { onMount } from "svelte";
  import PersonalActions from "./PersonalActions.svelte";
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
    pinMemory,
    changePassword,
    getAllModeSettings,
    getModeSettings,
    updateModeSettings,
    getWorkSubtabConfig,
    updateWorkSubtabConfig
  } from "../lib/api";

  let providers = [];
  let intents = [];
  let rules = {};
  let debugEnabled = false;
  let advancedMode = false;
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

  // Mode configuration state
  let workModeSettings = {
    system_prompt_override: "",
    preferred_provider_id: null,
    tone: "professional"
  };
  let personalModeSettings = {
    system_prompt_override: "",
    preferred_provider_id: null,
    tone: "casual"
  };
  let savingWorkMode = false;
  let savingPersonalMode = false;
  let workModeSaveStatus = null;
  let personalModeSaveStatus = null;

  // Work mode subtab configuration state
  let codeSubtabConfig = {
    language: "servicenow_javascript",
    framework: "",
    additional_context: ""
  };
  let emailSubtabConfig = {
    tone: "professional",
    signature: ""
  };
  let conversationSubtabConfig = {
    context: ""
  };
  let savingCodeSubtab = false;
  let savingEmailSubtab = false;
  let codeSubtabSaveStatus = null;
  let emailSubtabSaveStatus = null;

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
  let editingProvider = null;
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

  // Account/Security state
  let passwordForm = {
    current: "",
    new: "",
    confirm: ""
  };
  let passwordError = null;
  let passwordSuccess = null;
  let changingPassword = false;

  async function load() {
    providers = await getProviders();
    intents = await getIntents();
    rules = await getRoutingRules();
    const flag = await getDebugFlag();
    debugEnabled = flag === true || flag === "true" || flag?.enabled === true;

    // Load advanced mode from localStorage
    const storedAdvanced = localStorage.getItem("theo.advancedMode");
    advancedMode = storedAdvanced === "true";

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

    // Load mode settings
    try {
      const workSettings = await getModeSettings("work");
      if (workSettings && Object.keys(workSettings).length > 0) {
        workModeSettings = {
          system_prompt_override: workSettings.system_prompt_override || "",
          preferred_provider_id: workSettings.preferred_provider_id || null,
          tone: workSettings.tone || "professional"
        };
      }

      const personalSettings = await getModeSettings("personal");
      if (personalSettings && Object.keys(personalSettings).length > 0) {
        personalModeSettings = {
          system_prompt_override: personalSettings.system_prompt_override || "",
          preferred_provider_id: personalSettings.preferred_provider_id || null,
          tone: personalSettings.tone || "casual"
        };
      }
    } catch (e) {
      console.warn("Failed to load mode settings:", e);
    }

    // Load work subtab configs
    try {
      const codeConfig = await getWorkSubtabConfig("code");
      if (codeConfig && codeConfig.config_json) {
        const parsed = JSON.parse(codeConfig.config_json);
        codeSubtabConfig = {
          language: parsed.language || "servicenow_javascript",
          framework: parsed.framework || "",
          additional_context: parsed.additional_context || ""
        };
      }

      const emailConfig = await getWorkSubtabConfig("email");
      if (emailConfig && emailConfig.config_json) {
        const parsed = JSON.parse(emailConfig.config_json);
        emailSubtabConfig = {
          tone: parsed.tone || "professional",
          signature: parsed.signature || ""
        };
      }
    } catch (e) {
      console.warn("Failed to load work subtab configs:", e);
    }

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

  function toggleAdvancedMode(value) {
    advancedMode = value;
    localStorage.setItem("theo.advancedMode", value.toString());
    // Dispatch event so Chat component can listen
    window.dispatchEvent(new CustomEvent("advancedModeChanged", { detail: { enabled: value } }));
  }

  async function handleChangePassword() {
    passwordError = null;
    passwordSuccess = null;

    // Validation
    if (!passwordForm.current || !passwordForm.new || !passwordForm.confirm) {
      passwordError = "All fields are required";
      return;
    }

    if (passwordForm.new !== passwordForm.confirm) {
      passwordError = "New passwords do not match";
      return;
    }

    if (passwordForm.new.length < 4) {
      passwordError = "Password must be at least 4 characters";
      return;
    }

    changingPassword = true;

    try {
      await changePassword(passwordForm.current, passwordForm.new);
      passwordSuccess = "Password changed successfully!";
      passwordForm = { current: "", new: "", confirm: "" };
    } catch (err) {
      passwordError = err.message || "Failed to change password";
    } finally {
      changingPassword = false;
    }
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

  async function saveWorkMode() {
    try {
      savingWorkMode = true;
      workModeSaveStatus = null;
      await updateModeSettings("work", workModeSettings);
      workModeSaveStatus = "Work mode settings saved!";
      setTimeout(() => {
        workModeSaveStatus = null;
      }, 3000);
    } catch (e) {
      workModeSaveStatus = `Error: ${e.message}`;
    } finally {
      savingWorkMode = false;
    }
  }

  async function saveCodeSubtab() {
    try {
      savingCodeSubtab = true;
      codeSubtabSaveStatus = null;
      await updateWorkSubtabConfig("code", codeSubtabConfig);
      codeSubtabSaveStatus = "Code Development settings saved!";
      setTimeout(() => {
        codeSubtabSaveStatus = null;
      }, 3000);
    } catch (e) {
      codeSubtabSaveStatus = `Error: ${e.message}`;
    } finally {
      savingCodeSubtab = false;
    }
  }

  async function saveEmailSubtab() {
    try {
      savingEmailSubtab = true;
      emailSubtabSaveStatus = null;
      await updateWorkSubtabConfig("email", emailSubtabConfig);
      emailSubtabSaveStatus = "Email Rewrites settings saved!";
      setTimeout(() => {
        emailSubtabSaveStatus = null;
      }, 3000);
    } catch (e) {
      emailSubtabSaveStatus = `Error: ${e.message}`;
    } finally {
      savingEmailSubtab = false;
    }
  }

  async function savePersonalMode() {
    try {
      savingPersonalMode = true;
      personalModeSaveStatus = null;
      await updateModeSettings("personal", personalModeSettings);
      personalModeSaveStatus = "Personal mode settings saved!";
      setTimeout(() => {
        personalModeSaveStatus = null;
      }, 3000);
    } catch (e) {
      personalModeSaveStatus = `Error: ${e.message}`;
    } finally {
      savingPersonalMode = false;
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
      cancelProviderForm();
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
    <button
      class="tab"
      class:active={activeTab === "modes"}
      on:click={() => activeTab = "modes"}
    >
      Modes
    </button>
    <button
      class="tab"
      class:active={activeTab === "account"}
      on:click={() => activeTab = "account"}
    >
      Account
    </button>
    <button
      class="tab"
      class:active={activeTab === "integrations"}
      on:click={() => activeTab = "integrations"}
    >
      Integrations
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
          <button class="{showAddMemoryForm ? 'btn-secondary' : 'btn-primary'}" on:click={() => showAddMemoryForm = !showAddMemoryForm}>
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

        <button class="btn-primary" on:click={() => {
          if (showAddProviderForm) {
            cancelProviderForm();
          } else {
            showAddProviderForm = true;
            loadProvidersList();
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
    {/if}

    <!-- Debug Tab -->
    {#if activeTab === "debug"}
      <div class="tab-panel">
        <h2>Debugging</h2>
        <p class="subtitle">Enable debug logging and advanced features.</p>

        <div class="rule">
          <label>Debug logs</label>
          <input
            type="checkbox"
            checked={debugEnabled}
            disabled={savingDebug}
            on:change={(e) => toggleDebug(e.target.checked)}
          />
        </div>

        <div class="rule">
          <label>Advanced mode</label>
          <input
            type="checkbox"
            checked={advancedMode}
            on:change={(e) => toggleAdvancedMode(e.target.checked)}
          />
          <small style="display: block; margin-top: 0.5rem; color: #6b7280;">
            Shows Export and Fork features in chat interface
          </small>
        </div>
      </div>
    {/if}

    <!-- Modes Tab -->
    {#if activeTab === "modes"}
      <div class="tab-panel">
        <h2>Work & Personal Modes</h2>
        <p class="subtitle">Configure different behavior and preferences for work and personal contexts.</p>

        <!-- Work Mode Section -->
        <div class="section">
          <h3>💼 Work Mode</h3>
          <p class="hint">Professional tone and optimized for productivity tasks</p>

          <div class="form-group">
            <label for="work-tone">Tone</label>
            <select id="work-tone" bind:value={workModeSettings.tone}>
              <option value="professional">Professional</option>
              <option value="neutral">Neutral</option>
              <option value="casual">Casual</option>
            </select>
          </div>

          <div class="form-group">
            <label for="work-provider">Preferred Provider (optional)</label>
            <select id="work-provider" bind:value={workModeSettings.preferred_provider_id}>
              <option value={null}>Auto-select based on intent</option>
              {#each providers as provider}
                {#if provider.enabled}
                  <option value={provider.id}>{provider.name} ({provider.type})</option>
                {/if}
              {/each}
            </select>
            <p class="hint">Override automatic provider selection for this mode</p>
          </div>

          <div class="form-group">
            <label for="work-prompt">Custom System Prompt Override (optional)</label>
            <textarea
              id="work-prompt"
              bind:value={workModeSettings.system_prompt_override}
              placeholder="Leave empty to use default system prompt. Add custom instructions specific to work mode here."
              rows="6"
            ></textarea>
            <p class="hint">
              This will replace the default system prompt when in work mode. Leave empty to use the standard configuration.
            </p>
          </div>

          {#if workModeSaveStatus}
            <div class="success-message">{workModeSaveStatus}</div>
          {/if}

          <button
            class="btn-primary"
            on:click={saveWorkMode}
            disabled={savingWorkMode}
          >
            {savingWorkMode ? "Saving..." : "Save Work Mode Settings"}
          </button>
        </div>

        <!-- Work Mode Sub-Tabs Configuration -->
        <div class="section">
          <h3>💼 Work Mode Sub-Tabs</h3>
          <p class="hint">Configure automatic context injection for work mode sub-tabs</p>

          <!-- Code Development Sub-Tab -->
          <div class="subsection">
            <h4>💻 Code Development</h4>

            <div class="form-group">
              <label for="code-language">Programming Language</label>
              <select id="code-language" bind:value={codeSubtabConfig.language}>
                <option value="servicenow_javascript">ServiceNow JavaScript</option>
                <option value="javascript">JavaScript</option>
                <option value="typescript">TypeScript</option>
                <option value="python">Python</option>
                <option value="java">Java</option>
                <option value="csharp">C#</option>
              </select>
            </div>

            <div class="form-group">
              <label for="code-framework">Framework (optional)</label>
              <input
                id="code-framework"
                type="text"
                bind:value={codeSubtabConfig.framework}
                placeholder="e.g., React, Vue, Django"
              />
              <p class="hint">Specify a framework to add specialized context</p>
            </div>

            <div class="form-group">
              <label for="code-additional">Additional Context (optional)</label>
              <textarea
                id="code-additional"
                bind:value={codeSubtabConfig.additional_context}
                placeholder="Any additional context or coding standards for code development"
                rows="3"
              ></textarea>
            </div>

            {#if codeSubtabSaveStatus}
              <p class="status-message">{codeSubtabSaveStatus}</p>
            {/if}

            <button
              class="btn-primary"
              on:click={saveCodeSubtab}
              disabled={savingCodeSubtab}
            >
              {savingCodeSubtab ? "Saving..." : "Save Code Development Settings"}
            </button>
          </div>

          <!-- Email Rewrites Sub-Tab -->
          <div class="subsection">
            <h4>✉️ Email Rewrites</h4>

            <div class="form-group">
              <label for="email-tone">Email Tone</label>
              <select id="email-tone" bind:value={emailSubtabConfig.tone}>
                <option value="professional">Professional</option>
                <option value="friendly">Friendly</option>
                <option value="formal">Formal</option>
                <option value="casual">Casual</option>
              </select>
            </div>

            <div class="form-group">
              <label for="email-signature">Email Signature (optional)</label>
              <textarea
                id="email-signature"
                bind:value={emailSubtabConfig.signature}
                placeholder="Your default email signature"
                rows="3"
              ></textarea>
              <p class="hint">This signature will be suggested when rewriting emails</p>
            </div>

            {#if emailSubtabSaveStatus}
              <p class="status-message">{emailSubtabSaveStatus}</p>
            {/if}

            <button
              class="btn-primary"
              on:click={saveEmailSubtab}
              disabled={savingEmailSubtab}
            >
              {savingEmailSubtab ? "Saving..." : "Save Email Rewrite Settings"}
            </button>
          </div>
        </div>

        <!-- Personal Mode Section -->
        <div class="section">
          <h3>🏠 Personal Mode</h3>
          <p class="hint">Casual tone and optimized for general conversation</p>

          <div class="form-group">
            <label for="personal-tone">Tone</label>
            <select id="personal-tone" bind:value={personalModeSettings.tone}>
              <option value="casual">Casual</option>
              <option value="neutral">Neutral</option>
              <option value="professional">Professional</option>
            </select>
          </div>

          <div class="form-group">
            <label for="personal-provider">Preferred Provider (optional)</label>
            <select id="personal-provider" bind:value={personalModeSettings.preferred_provider_id}>
              <option value={null}>Auto-select based on intent</option>
              {#each providers as provider}
                {#if provider.enabled}
                  <option value={provider.id}>{provider.name} ({provider.type})</option>
                {/if}
              {/each}
            </select>
            <p class="hint">Override automatic provider selection for this mode</p>
          </div>

          <div class="form-group">
            <label for="personal-prompt">Custom System Prompt Override (optional)</label>
            <textarea
              id="personal-prompt"
              bind:value={personalModeSettings.system_prompt_override}
              placeholder="Leave empty to use default system prompt. Add custom instructions specific to personal mode here."
              rows="6"
            ></textarea>
            <p class="hint">
              This will replace the default system prompt when in personal mode. Leave empty to use the standard configuration.
            </p>
          </div>

          {#if personalModeSaveStatus}
            <div class="success-message">{personalModeSaveStatus}</div>
          {/if}

          <button
            class="btn-primary"
            on:click={savePersonalMode}
            disabled={savingPersonalMode}
          >
            {savingPersonalMode ? "Saving..." : "Save Personal Mode Settings"}
          </button>
        </div>
      </div>
    {/if}

    <!-- Account Tab -->
    {#if activeTab === "account"}
      <div class="tab-panel">
        <h2>Account & Security</h2>
        <p class="subtitle">Manage your password and security settings.</p>

        <!-- Change Password Section -->
        <div class="section">
          <h3>Change Password</h3>

          {#if passwordError}
            <div class="error-message">{passwordError}</div>
          {/if}

          {#if passwordSuccess}
            <div class="success-message">{passwordSuccess}</div>
          {/if}

          <div class="form-group">
            <label for="current-password">Current Password</label>
            <input
              id="current-password"
              type="password"
              bind:value={passwordForm.current}
              disabled={changingPassword}
              placeholder="Enter current password"
            />
          </div>

          <div class="form-group">
            <label for="new-password">New Password</label>
            <input
              id="new-password"
              type="password"
              bind:value={passwordForm.new}
              disabled={changingPassword}
              placeholder="Enter new password (min 4 characters)"
            />
          </div>

          <div class="form-group">
            <label for="confirm-password">Confirm New Password</label>
            <input
              id="confirm-password"
              type="password"
              bind:value={passwordForm.confirm}
              disabled={changingPassword}
              placeholder="Confirm new password"
            />
          </div>

          <button
            class="btn-primary"
            on:click={handleChangePassword}
            disabled={changingPassword}
          >
            {changingPassword ? "Changing Password..." : "Change Password"}
          </button>
        </div>
      </div>
    {/if}

    <!-- Integrations Tab -->
    {#if activeTab === "integrations"}
      <div class="tab-panel">
        <PersonalActions />
      </div>
    {/if}
  </div>
</div>

<style>
  .settings {
    padding: 0;
    height: 100%;
    display: flex;
    flex-direction: column;
  }

  h1 {
    padding: var(--space-5) var(--space-6);
    margin: 0;
    border-bottom: 1px solid var(--gray-200);
    background: var(--gray-50);
    font-size: var(--font-size-2xl);
  }

  .tabs {
    display: flex;
    background: var(--gray-50);
    border-bottom: 2px solid var(--gray-200);
    padding: 0 var(--space-6);
    gap: var(--space-1);
  }

  .tab {
    padding: var(--space-3) var(--space-6);
    border: none;
    background: transparent;
    cursor: pointer;
    font-size: var(--font-size-sm);
    font-weight: 500;
    color: var(--gray-500);
    border-bottom: 3px solid transparent;
    transition: all 0.2s;
  }

  .tab:hover {
    color: var(--gray-700);
    background: rgba(0, 0, 0, 0.03);
  }

  .tab.active {
    color: var(--info-500);
    border-bottom-color: var(--info-500);
    background: white;
  }

  .tab-content {
    flex: 1;
    overflow-y: auto;
    padding: var(--space-6);
  }

  .tab-panel {
    max-width: 900px;
    margin: 0 auto;
  }

  h2 {
    margin-top: 0;
    margin-bottom: var(--space-2);
  }

  .subtitle {
    color: var(--gray-600);
    font-size: var(--font-size-sm);
    margin-bottom: var(--space-4);
  }

  .rule {
    display: flex;
    align-items: center;
    gap: var(--space-3);
    margin-bottom: var(--space-3);
  }

  label {
    width: 140px;
    font-weight: 500;
  }

  select {
    flex: 1;
    padding: var(--space-2);
    border: 1px solid var(--gray-300);
    border-radius: var(--radius-sm);
  }

  input[type="checkbox"] {
    transform: scale(1.2);
    cursor: pointer;
  }

  /* Button overrides for Settings context - these buttons already inherit from global styles */
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

  .intent-form {
    background: var(--gray-50);
    border: 1px solid var(--gray-200);
    border-radius: var(--radius-lg);
    padding: var(--space-5);
    margin-bottom: var(--space-6);
  }

  .intent-form h3 {
    margin-top: 0;
    margin-bottom: var(--space-4);
  }

  .form-group {
    margin-bottom: var(--space-4);
  }

  .form-group label {
    display: block;
    width: auto;
    margin-bottom: var(--space-1);
    font-weight: 600;
  }

  .form-group input[type="text"],
  .form-group input[type="number"],
  .form-group textarea {
    width: 100%;
    padding: var(--space-2);
    border: 1px solid var(--gray-300);
    border-radius: var(--radius-sm);
    font-family: inherit;
  }

  .form-group small {
    display: block;
    color: var(--gray-500);
    font-size: var(--font-size-xs);
    margin-top: var(--space-1);
  }

  .form-actions {
    display: flex;
    gap: var(--space-3);
    margin-top: var(--space-5);
  }

  .intents-list {
    display: flex;
    flex-direction: column;
    gap: var(--space-3);
    margin-bottom: var(--space-6);
  }

  .intent-card {
    border: 1px solid var(--gray-200);
    border-radius: var(--radius-lg);
    padding: var(--space-4);
    background: white;
  }

  .intent-card.disabled {
    opacity: 0.6;
    background: var(--gray-50);
  }

  .intent-header {
    display: flex;
    justify-content: space-between;
    align-items: flex-start;
    margin-bottom: var(--space-3);
  }

  .intent-info h4 {
    margin: 0 0 var(--space-1) 0;
    display: flex;
    align-items: center;
    gap: var(--space-2);
  }

  .intent-id {
    color: var(--gray-500);
    font-size: var(--font-size-sm);
    font-weight: normal;
  }

  .badge-disabled {
    background: var(--error-500);
    color: white;
    padding: var(--space-1) var(--space-2);
    border-radius: var(--radius-sm);
    font-size: var(--font-size-xs);
    font-weight: normal;
  }

  .intent-description {
    margin: 0;
    color: var(--gray-600);
    font-size: var(--font-size-sm);
  }

  .intent-priority {
    background: var(--gray-100);
    padding: var(--space-1) var(--space-3);
    border-radius: var(--radius-sm);
    font-size: var(--font-size-xs);
    font-weight: 600;
    color: var(--gray-700);
  }

  .intent-keywords {
    background: var(--gray-50);
    padding: var(--space-2) var(--space-3);
    border-radius: var(--radius-sm);
    font-size: var(--font-size-sm);
    margin-bottom: var(--space-3);
  }

  .intent-keywords.empty {
    font-style: italic;
    color: var(--gray-500);
  }

  .intent-keywords strong {
    color: var(--gray-700);
  }

  .intent-actions {
    display: flex;
    gap: var(--space-2);
  }

  .system-prompt-form {
    background: var(--gray-50);
    border: 1px solid var(--gray-200);
    border-radius: var(--radius-lg);
    padding: var(--space-5);
    margin-bottom: var(--space-6);
  }

  .save-status {
    margin-top: var(--space-3);
    padding: var(--space-3) var(--space-4);
    border-radius: var(--radius-sm);
    font-size: var(--font-size-sm);
  }

  .save-status.success {
    background: var(--success-50);
    color: #155724;
    border: 1px solid var(--success-500);
  }

  .save-status.error {
    background: var(--error-50);
    color: #721c24;
    border: 1px solid var(--error-500);
  }

  .memory-form {
    background: var(--gray-50);
    border: 1px solid var(--gray-200);
    border-radius: var(--radius-lg);
    padding: var(--space-5);
    margin-bottom: var(--space-6);
  }

  .memory-help {
    background: var(--warning-50);
    border: 1px solid var(--warning-500);
    border-radius: var(--radius-lg);
    padding: var(--space-5);
  }

  .memory-help h3 {
    margin-top: 0;
    margin-bottom: var(--space-3);
    font-size: var(--font-size-base);
    color: #856404;
  }

  .memory-help ul {
    margin: 0;
    padding-left: var(--space-5);
    color: #856404;
  }

  .memory-help li {
    margin-bottom: var(--space-2);
  }

  /* Memory component styles */
  .memory-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: var(--space-6);
  }

  .add-form {
    background: var(--gray-50);
    border: 1px solid var(--gray-200);
    border-radius: var(--radius-lg);
    padding: var(--space-6);
    margin-bottom: var(--space-6);
  }

  .form-row {
    margin-bottom: var(--space-4);
  }

  .form-row label {
    display: block;
    font-size: var(--font-size-sm);
    font-weight: 500;
    margin-bottom: var(--space-1);
  }

  .form-row input[type="text"],
  .form-row input[type="password"],
  .form-row select {
    width: 100%;
    max-width: 100%;
    padding: var(--space-2);
    border: 1px solid var(--gray-300);
    border-radius: var(--radius-sm);
    font-size: var(--font-size-sm);
  }

  .form-row input[type="checkbox"] {
    margin-right: var(--space-2);
  }

  .filter-bar {
    display: flex;
    gap: var(--space-2);
    margin-bottom: var(--space-6);
    flex-wrap: wrap;
  }

  .filter-bar button {
    padding: var(--space-2) var(--space-4);
    border: 1px solid var(--gray-300);
    background: white;
    border-radius: var(--radius-md);
    cursor: pointer;
    font-size: var(--font-size-sm);
    transition: all 0.2s;
  }

  .filter-bar button:hover {
    background: var(--gray-100);
  }

  .filter-bar button.active {
    background: var(--info-500);
    color: white;
    border-color: var(--info-500);
  }

  .loading,
  .empty-state {
    text-align: center;
    padding: var(--space-12) var(--space-4);
    color: var(--gray-500);
  }

  .empty-state .hint {
    font-size: var(--font-size-sm);
    margin-top: var(--space-2);
    opacity: 0.7;
  }

  .memory-list {
    display: flex;
    flex-direction: column;
    gap: var(--space-4);
  }

  .memory-item {
    border: 1px solid var(--gray-200);
    border-radius: var(--radius-lg);
    padding: var(--space-4);
    background: white;
    transition: box-shadow 0.2s;
  }

  .memory-item:hover {
    box-shadow: var(--shadow-md);
  }

  .memory-item.pinned {
    border-color: var(--warning-500);
    background: var(--warning-50);
  }

  .memory-header-row {
    display: flex;
    align-items: center;
    gap: var(--space-2);
    margin-bottom: var(--space-2);
    flex-wrap: wrap;
  }

  .memory-type {
    font-size: var(--font-size-xs);
    padding: var(--space-1) var(--space-2);
    border-radius: var(--radius-sm);
    color: white;
    font-weight: 500;
    text-transform: uppercase;
  }

  .pin-badge {
    font-size: var(--font-size-xs);
    color: var(--warning-500);
    font-weight: 500;
  }

  .memory-score {
    font-size: var(--font-size-xs);
    color: var(--gray-500);
    margin-left: auto;
  }

  .memory-content {
    font-size: var(--font-size-sm);
    margin-bottom: var(--space-2);
    line-height: 1.5;
  }

  .memory-content strong {
    color: var(--gray-900);
  }

  .memory-meta {
    font-size: var(--font-size-xs);
    color: var(--gray-400);
    display: flex;
    gap: var(--space-2);
    margin-bottom: var(--space-3);
    flex-wrap: wrap;
  }

  .memory-actions {
    display: flex;
    gap: var(--space-2);
  }

  .btn-pin,
  .btn-delete {
    padding: var(--space-1) var(--space-3);
    font-size: var(--font-size-xs);
    border: 1px solid var(--gray-300);
    background: white;
    border-radius: var(--radius-sm);
    cursor: pointer;
    transition: all 0.2s;
  }

  .btn-pin:hover {
    background: #fef3c7;
    border-color: var(--warning-500);
  }

  .btn-delete:hover {
    background: var(--error-50);
    border-color: var(--error-500);
    color: var(--error-600);
  }

  /* Provider component styles */
  .providers-list {
    display: flex;
    flex-direction: column;
    gap: var(--space-4);
    margin-top: var(--space-6);
  }

  .provider-card {
    border: 1px solid var(--gray-200);
    border-radius: var(--radius-lg);
    padding: var(--space-4);
    background: white;
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
  }

  .provider-details div {
    margin-bottom: var(--space-2);
  }

  .health-stats {
    display: flex;
    gap: var(--space-4);
    margin-top: var(--space-2);
    color: var(--gray-500);
  }

  .provider-actions {
    display: flex;
    gap: var(--space-2);
  }

  /* Account tab styles */
  .error-message {
    padding: var(--space-3);
    background: var(--error-50);
    border: 1px solid var(--error-200);
    border-radius: var(--radius-md);
    color: var(--error-700);
    font-size: var(--font-size-sm);
    margin-bottom: var(--space-4);
  }

  .success-message {
    padding: var(--space-3);
    background: #d1fae5;
    border: 1px solid #6ee7b7;
    border-radius: var(--radius-md);
    color: #065f46;
    font-size: var(--font-size-sm);
    margin-bottom: var(--space-4);
  }

  .confirm-box {
    padding: var(--space-4);
    background: var(--gray-50);
    border: 1px solid var(--gray-300);
    border-radius: var(--radius-md);
    margin-top: var(--space-3);
  }

  .confirm-box p {
    margin: 0 0 var(--space-3) 0;
  }

  .button-group {
    display: flex;
    gap: var(--space-2);
  }

  .section {
    margin-bottom: var(--space-6);
    padding-bottom: var(--space-6);
    border-bottom: 1px solid var(--gray-200);
  }

  .section:last-child {
    border-bottom: none;
  }
</style>
