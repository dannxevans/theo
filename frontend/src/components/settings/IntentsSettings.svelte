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

<style>
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

  .btn-small.btn-danger {
    color: var(--error-500);
    border-color: var(--error-500);
  }

  .btn-small.btn-danger:hover {
    background: var(--error-500);
    color: white;
  }
</style>
