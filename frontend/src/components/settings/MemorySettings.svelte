<script>
  import { createEventDispatcher } from "svelte";
  import { createMemory, deleteMemory, pinMemory } from "../../lib/api";

  export let memories = [];
  export let loadingMemories = false;
  export let filterType = "all";

  const dispatch = createEventDispatcher();

  let showAddMemoryForm = false;
  let newMemory = {
    type: "fact",
    key: "",
    value: "",
    pinned: false
  };

  async function handleCreateMemory() {
    if (!newMemory.key.trim() || !newMemory.value.trim()) {
      alert("Key and value are required");
      return;
    }

    try {
      await createMemory(newMemory);
      dispatch("reload");
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
      dispatch("reload");
    } catch (err) {
      console.error("Failed to delete memory", err);
    }
  }

  async function handleTogglePin(memoryId, currentlyPinned) {
    try {
      await pinMemory(memoryId, !currentlyPinned);
      dispatch("reload");
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
</script>

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
            <span class="status-badge status-badge--info">
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

<style>
  .tab-panel {
    max-width: 900px;
    margin: 0 auto;
  }

  .memory-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: var(--space-6);
  }

  h2 {
    margin: 0;
  }

  .add-form {
    background: var(--bg-tertiary);
    border: 1px solid var(--border-primary);
    border-radius: var(--radius-lg);
    padding: var(--space-6);
    margin-bottom: var(--space-6);
  }

  /* Form styles now using .form-group from forms.css */
  .form-row {
    margin-bottom: var(--space-4);
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
    border: 1px solid var(--border-secondary);
    background: var(--bg-primary);
    color: var(--text-primary);
    border-radius: var(--radius-md);
    cursor: pointer;
    font-size: var(--font-size-sm);
    transition: all 0.2s;
  }

  .filter-bar button:hover {
    background: var(--bg-hover);
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
    color: var(--text-secondary);
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
    border: 1px solid var(--border-primary);
    border-radius: var(--radius-lg);
    padding: var(--space-4);
    background: var(--bg-tertiary);
    transition: box-shadow 0.2s;
  }

  .memory-item:hover {
    box-shadow: var(--shadow-md);
  }

  .memory-item.pinned {
    border-color: var(--warning-500);
    background: var(--warning-100);
  }

  .memory-header-row {
    display: flex;
    align-items: center;
    gap: var(--space-2);
    margin-bottom: var(--space-2);
    flex-wrap: wrap;
  }

  /* .memory-type replaced with .status-badge--info utility */

  .pin-badge {
    font-size: var(--font-size-xs);
    color: var(--warning-500);
    font-weight: 500;
  }

  .memory-score {
    font-size: var(--font-size-xs);
    color: var(--text-secondary);
    margin-left: auto;
  }

  .memory-content {
    font-size: var(--font-size-sm);
    margin-bottom: var(--space-2);
    line-height: 1.5;
    color: var(--text-primary);
  }

  .memory-content strong {
    color: var(--text-primary);
  }

  .memory-meta {
    font-size: var(--font-size-xs);
    color: var(--text-tertiary);
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
    border: 1px solid var(--border-secondary);
    background: var(--bg-primary);
    color: var(--text-primary);
    border-radius: var(--radius-sm);
    cursor: pointer;
    transition: all 0.2s;
  }

  .btn-pin:hover {
    background: var(--warning-100);
    border-color: var(--warning-500);
  }

  .btn-delete:hover {
    background: var(--error-50);
    border-color: var(--error-500);
    color: var(--error-600);
  }
</style>
