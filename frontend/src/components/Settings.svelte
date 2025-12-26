<script>
  import { onMount } from "svelte";
  import {
    getProviders,
    getIntents,
    createIntent,
    updateIntent,
    deleteIntent,
    getRoutingRules,
    setRoutingRule,
    deleteRoutingRule,
    getDebugFlag,
    setDebugFlag
  } from "../lib/api";

  let providers = [];
  let intents = [];
  let rules = {};
  let debugEnabled = false;
  let loaded = false;
  let savingDebug = false;

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

  onMount(load);
</script>

<div class="settings">
  <h2>Debugging</h2>

  <div class="rule">
    <label>Debug logs</label>
    <input
      type="checkbox"
      checked={debugEnabled}
      disabled={savingDebug}
      on:change={(e) => toggleDebug(e.target.checked)}
    />
  </div>

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

<style>
  .settings {
    padding: 16px;
    max-width: 900px;
    margin: 0 auto;
  }

  h2 {
    margin-top: 24px;
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
</style>
