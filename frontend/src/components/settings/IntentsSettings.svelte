<script>
  import { createEventDispatcher } from "svelte";
  import { createIntent, updateIntent, deleteIntent } from "../../lib/api";

  export let intents = [];

  const dispatch = createEventDispatcher();

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
        await updateIntent(editingIntent, {
          name: intentForm.name,
          description: intentForm.description,
          keywords: intentForm.keywords,
          priority: parseInt(intentForm.priority),
          enabled: intentForm.enabled
        });
      } else {
        await createIntent({
          id: intentForm.id,
          name: intentForm.name,
          description: intentForm.description,
          keywords: intentForm.keywords,
          priority: parseInt(intentForm.priority),
          enabled: intentForm.enabled
        });
      }

      dispatch("reload");
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
      dispatch("reload");
    } catch (e) {
      alert(`Failed to delete intent: ${e.message}`);
    }
  }

  async function toggleIntentEnabled(intent) {
    try {
      await updateIntent(intent.id, {
        enabled: !intent.enabled
      });
      dispatch("reload");
    } catch (e) {
      alert(`Failed to toggle intent: ${e.message}`);
    }
  }
</script>

<div class="tab-panel">
  <div class="page-header">
    <div>
      <h2>Intents</h2>
      <p class="subtitle">Define custom intents to classify and route your requests.</p>
    </div>
    <button class="btn-primary" on:click={startNewIntent}>
      + New Intent
    </button>
  </div>

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

  <!-- LLM Routing Intents Section -->
  <div class="section">
    <h3>LLM Routing Intents</h3>
    <p class="subtitle">These intents are used to route requests to appropriate LLM providers via the Routing settings.</p>
    <div class="intents-list">
      {#each intents.filter(i => !i.is_action && i.id !== 'system') as intent}
        <div class="intent-card" class:disabled={!intent.enabled}>
          <div class="intent-header">
            <div class="intent-info">
              <h4>
                {intent.name}
                <span class="intent-id">({intent.id})</span>
                {#if !intent.enabled}
                  <span class="status-badge status-badge--error">Disabled</span>
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

  <!-- Action Intents Section -->
  <div class="section">
    <h3>Action Intents</h3>
    <p class="subtitle">These intents trigger actions (calendar, email, etc.). They have predefined routing but keywords can be customized.</p>
    <div class="intents-list">
      {#each intents.filter(i => i.is_action) as intent}
        <div class="intent-card" class:disabled={!intent.enabled}>
          <div class="intent-header">
            <div class="intent-info">
              <h4>
                {intent.name}
                <span class="intent-id">({intent.id})</span>
                {#if !intent.enabled}
                  <span class="status-badge status-badge--error">Disabled</span>
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
              No keywords
            </div>
          {/if}

          <div class="intent-actions">
            <button class="btn-small" on:click={() => editIntent(intent)}>
              Edit
            </button>
            <button class="btn-small" on:click={() => toggleIntentEnabled(intent)}>
              {intent.enabled ? "Disable" : "Enable"}
            </button>
          </div>
        </div>
      {/each}
    </div>
  </div>
</div>

<style>
  .tab-panel {
    max-width: 900px;
    margin: 0 auto;
  }

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

  h2 {
    margin-top: 0;
    margin-bottom: var(--space-2);
  }

  .subtitle {
    color: var(--text-secondary);
    font-size: var(--font-size-sm);
    margin-bottom: var(--space-4);
  }

  .intent-form {
    background: var(--bg-tertiary);
    border: 1px solid var(--border-primary);
    border-radius: var(--radius-lg);
    padding: var(--space-5);
    margin-bottom: var(--space-6);
  }

  .intent-form h3 {
    margin-top: 0;
    margin-bottom: var(--space-4);
    color: var(--text-primary);
  }

  /* Form styles now imported from forms.css */

  .intents-list {
    display: flex;
    flex-direction: column;
    gap: var(--space-3);
    margin-bottom: var(--space-6);
  }

  .intent-card {
    border: 1px solid var(--border-primary);
    border-radius: var(--radius-lg);
    padding: var(--space-4);
    background: var(--bg-tertiary);
  }

  .intent-card.disabled {
    opacity: 0.6;
    background: var(--bg-secondary);
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
    color: var(--text-primary);
  }

  .intent-id {
    color: var(--text-secondary);
    font-size: var(--font-size-sm);
    font-weight: normal;
  }


  .intent-description {
    margin: 0;
    color: var(--text-secondary);
    font-size: var(--font-size-sm);
  }

  .intent-priority {
    background: var(--bg-active);
    padding: var(--space-1) var(--space-3);
    border-radius: var(--radius-sm);
    font-size: var(--font-size-xs);
    font-weight: 600;
    color: var(--text-primary);
  }

  .intent-keywords {
    background: var(--bg-secondary);
    padding: var(--space-2) var(--space-3);
    border-radius: var(--radius-sm);
    font-size: var(--font-size-sm);
    margin-bottom: var(--space-3);
    color: var(--text-primary);
    word-wrap: break-word;
    overflow-wrap: break-word;
  }

  .intent-keywords.empty {
    font-style: italic;
    color: var(--text-secondary);
  }

  .intent-keywords strong {
    color: var(--text-primary);
  }

  .intent-actions {
    display: flex;
    gap: var(--space-2);
  }

  .btn-small.btn-danger {
    color: var(--error-500);
    border-color: var(--error-500);
  }

  .btn-small.btn-danger:hover {
    background: var(--error-500);
    color: white;
  }
</style>
