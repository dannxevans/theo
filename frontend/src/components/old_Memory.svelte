<script>
  import { onMount } from "svelte";
  import { getMemories, createMemory, deleteMemory, pinMemory, updateMemory } from "../lib/api.js";

  let memories = [];
  let loading = true;
  let filterType = "all";
  let newMemory = {
    type: "fact",
    key: "",
    value: "",
    pinned: false,
  };

  let showAddForm = false;
  let editingMemoryId = null;
  let editMemory = null;

  onMount(async () => {
    await loadMemories();
  });

  async function loadMemories() {
    try {
      loading = true;
      const params = filterType !== "all" ? { type: filterType } : {};
      memories = await getMemories(params);
    } catch (err) {
      console.error("Failed to load memories", err);
    } finally {
      loading = false;
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
      showAddForm = false;
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

  function startEditMemory(mem) {
    editingMemoryId = mem.id;
    editMemory = {
      type: mem.type,
      key: mem.key,
      value: mem.value
    };
  }

  function cancelEdit() {
    editingMemoryId = null;
    editMemory = null;
  }

  async function saveEdit(memoryId) {
    if (!editMemory.key.trim() || !editMemory.value.trim()) {
      alert("Key and value are required");
      return;
    }

    try {
      await updateMemory(memoryId, editMemory);
      await loadMemories();
      editingMemoryId = null;
      editMemory = null;
    } catch (err) {
      console.error("Failed to update memory", err);
      alert("Failed to update memory");
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
      context: "#f59e0b",
    };
    return colors[type] || "#6b7280";
  }

  $: {
    if (filterType) {
      loadMemories();
    }
  }
</script>

<div class="memory-container memory-page">
  <div class="memory-header">
    <h2>Memory</h2>
    <button class="btn-add" on:click={() => showAddForm = !showAddForm}>
      {showAddForm ? "Cancel" : "+ Add Memory"}
    </button>
  </div>

  {#if showAddForm}
    <div class="add-form">
      <div class="form-group">
        <label for="memory-type">Type</label>
        <select id="memory-type" bind:value={newMemory.type}>
          <option value="fact">Fact</option>
          <option value="preference">Preference</option>
          <option value="goal">Goal</option>
          <option value="context">Context</option>
        </select>
      </div>

      <div class="form-group">
        <label for="memory-key">Key</label>
        <input id="memory-key" type="text" bind:value={newMemory.key} placeholder="e.g., project" />
      </div>

      <div class="form-group">
        <label for="memory-value">Value</label>
        <input id="memory-value" type="text" bind:value={newMemory.value} placeholder="e.g., Atlas" />
      </div>

      <div class="form-group">
        <label class="checkbox-label">
          <input type="checkbox" bind:checked={newMemory.pinned} />
          Pin this memory (always included)
        </label>
      </div>

      <div class="form-actions">
        <button class="btn-primary" on:click={handleCreateMemory}>Save</button>
        <button class="btn-secondary" on:click={() => showAddForm = false}>Cancel</button>
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

  {#if loading}
    <div class="loading">Loading memories...</div>
  {:else if memories.length === 0}
    <div class="empty-state">
      <p>No memories stored yet.</p>
      <p class="hint">Say "remember that [key] is [value]" in chat, or use the form above.</p>
    </div>
  {:else}
    <div class="memory-list">
      {#each memories as mem (mem.id)}
        <div class="memory-item" class:pinned={mem.pinned} class:editing={editingMemoryId === mem.id}>
          <div class="memory-header-row">
            {#if editingMemoryId === mem.id}
              <select bind:value={editMemory.type} class="edit-type-select">
                <option value="fact">fact</option>
                <option value="preference">preference</option>
                <option value="goal">goal</option>
                <option value="context">context</option>
              </select>
            {:else}
              <span class="memory-type" style="background-color: {getTypeColor(mem.type)}">
                {mem.type}
              </span>
            {/if}
            {#if mem.pinned}
              <span class="pin-badge">📌 Pinned</span>
            {/if}
            <span class="memory-score">Score: {mem.relevance_score}</span>
          </div>

          {#if editingMemoryId === mem.id}
            <div class="memory-edit-form">
              <div class="edit-field">
                <label>Key:</label>
                <input
                  type="text"
                  bind:value={editMemory.key}
                  class="edit-input"
                  placeholder="Memory key"
                />
              </div>
              <div class="edit-field">
                <label>Value:</label>
                <textarea
                  bind:value={editMemory.value}
                  class="edit-textarea"
                  placeholder="Memory value"
                  rows="3"
                ></textarea>
              </div>
            </div>
          {:else}
            <div class="memory-content">
              <strong>{mem.key}:</strong> {mem.value}
            </div>
          {/if}

          <div class="memory-meta">
            <span>Created {formatDate(mem.created_at)}</span>
            <span>•</span>
            <span>Used {mem.access_count} times</span>
            <span>•</span>
            <span>Last accessed {formatDate(mem.last_accessed_at)}</span>
          </div>

          <div class="memory-actions">
            {#if editingMemoryId === mem.id}
              <button
                class="btn-save"
                on:click={() => saveEdit(mem.id)}
              >
                Save
              </button>
              <button
                class="btn-cancel"
                on:click={cancelEdit}
              >
                Cancel
              </button>
            {:else}
              <button
                class="btn-edit"
                on:click={() => startEditMemory(mem)}
              >
                Edit
              </button>
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
            {/if}
          </div>
        </div>
      {/each}
    </div>
  {/if}
</div>

<style>
  .memory-container {
    max-width: 800px;
    margin: 0 auto;
    padding: 2rem;
  }

  .memory-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 1.5rem;
  }

  .memory-header h2 {
    margin: 0;
    font-size: 1.5rem;
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
    background: var(--bg-tertiary);
    border: 1px solid var(--border-primary);
    border-radius: var(--radius-lg);
    padding: var(--space-5) var(--space-6);
    margin-bottom: var(--space-6);
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

  .btn-secondary {
    padding: 0.5rem 1rem;
    background: #e5e7eb;
    color: #374151;
    border: none;
    border-radius: 6px;
    cursor: pointer;
  }

  .btn-secondary:hover {
    background: #d1d5db;
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

  .btn-edit {
    padding: 0.25rem 0.75rem;
    font-size: 0.75rem;
    border: 1px solid #d1d5db;
    background: white;
    border-radius: 4px;
    cursor: pointer;
    transition: all 0.2s;
  }

  .btn-edit:hover {
    background: #dbeafe;
    border-color: #3b82f6;
    color: #1e40af;
  }

  .btn-save {
    padding: 0.25rem 0.75rem;
    font-size: 0.75rem;
    border: 1px solid #10b981;
    background: #10b981;
    color: white;
    border-radius: 4px;
    cursor: pointer;
    transition: all 0.2s;
  }

  .btn-save:hover {
    background: #059669;
    border-color: #059669;
  }

  .btn-cancel {
    padding: 0.25rem 0.75rem;
    font-size: 0.75rem;
    border: 1px solid #d1d5db;
    background: white;
    border-radius: 4px;
    cursor: pointer;
    transition: all 0.2s;
  }

  .btn-cancel:hover {
    background: #f3f4f6;
    border-color: #9ca3af;
  }

  .memory-item.editing {
    border-color: #3b82f6;
    background: #eff6ff;
  }

  .edit-type-select {
    font-size: 0.75rem;
    padding: 0.25rem 0.5rem;
    border-radius: 4px;
    border: 1px solid #d1d5db;
    background: white;
    font-weight: 500;
    text-transform: uppercase;
    cursor: pointer;
  }

  .memory-edit-form {
    display: flex;
    flex-direction: column;
    gap: 0.75rem;
    margin-bottom: 0.5rem;
  }

  .edit-field {
    display: flex;
    flex-direction: column;
    gap: 0.25rem;
  }

  .edit-field label {
    font-size: 0.75rem;
    font-weight: 500;
    color: #374151;
  }

  .edit-input,
  .edit-textarea {
    padding: 0.5rem;
    border: 1px solid #d1d5db;
    border-radius: 4px;
    font-size: 0.875rem;
    font-family: inherit;
    transition: border-color 0.2s;
  }

  .edit-input:focus,
  .edit-textarea:focus {
    outline: none;
    border-color: #3b82f6;
    box-shadow: 0 0 0 3px rgba(59, 130, 246, 0.1);
  }

  .edit-textarea {
    resize: vertical;
    min-height: 60px;
  }

  @media (max-width: 640px) {
    .memory-container {
      padding: 1rem;
    }

    .memory-header {
      flex-direction: column;
      align-items: flex-start;
      gap: 1rem;
    }

    .filter-bar {
      overflow-x: auto;
      padding-bottom: 0.5rem;
    }

    .memory-meta {
      flex-direction: column;
      gap: 0.25rem;
    }

    .memory-meta span:nth-child(2n) {
      display: none;
    }
  }
</style>
