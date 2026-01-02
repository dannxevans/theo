<script>
  import { onMount } from "svelte";

  // Routines state
  let routines = [];
  let loading = false;
  let saveStatus = null;

  // Load routines from backend
  async function loadRoutines() {
    try {
      loading = true;
      const token = localStorage.getItem("auth_token");
      const response = await fetch("/api/routines", {
        headers: {
          Authorization: `Bearer ${token}`,
        },
      });

      if (!response.ok) {
        throw new Error("Failed to load routines");
      }

      const data = await response.json();
      routines = data.routines || [];
    } catch (error) {
      console.error("Failed to load routines:", error);
      // Initialize with default routine if loading fails
      routines = [
        {
          name: "Good Morning",
          trigger: "good morning",
          actions: [
            { type: "calendar_read", description: "Check today's calendar" },
            { type: "email_check", description: "Check important emails" },
            { type: "email_summary", description: "Summarize other emails" },
          ],
          enabled: true,
          editable: false, // System routine
        },
      ];
    } finally {
      loading = false;
    }
  }

  async function saveRoutines() {
    try {
      loading = true;
      saveStatus = null;

      const token = localStorage.getItem("auth_token");
      const response = await fetch("/api/routines", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${token}`,
        },
        body: JSON.stringify({ routines }),
      });

      if (!response.ok) {
        throw new Error("Failed to save routines");
      }

      saveStatus = "Routines saved successfully!";
      setTimeout(() => {
        saveStatus = null;
      }, 3000);
    } catch (error) {
      console.error("Failed to save routines:", error);
      saveStatus = `Error: ${error.message}`;
    } finally {
      loading = false;
    }
  }

  function toggleRoutine(index) {
    routines[index].enabled = !routines[index].enabled;
    routines = [...routines];
  }

  onMount(() => {
    loadRoutines();
  });
</script>

<div class="tab-panel">
  <h2>Routines</h2>
  <p class="subtitle">
    Configure automated workflows that bundle multiple actions together.
  </p>

  <div class="section">
    {#if loading && routines.length === 0}
      <div class="loading-state">
        <p>Loading routines...</p>
      </div>
    {:else if routines.length === 0}
      <div class="empty-state">
        <p>No routines configured yet.</p>
      </div>
    {:else}
      <div class="routines-list">
        {#each routines as routine, index}
          <div class="routine-card" class:disabled={!routine.enabled}>
            <div class="routine-header">
              <div class="routine-title">
                <h3>{routine.name}</h3>
                <span class="routine-trigger">Trigger: "{routine.trigger}"</span>
                {#if !routine.editable}
                  <span class="system-badge">System Routine</span>
                {/if}
              </div>
              <div class="routine-actions-header">
                <label class="toggle-switch">
                  <input
                    type="checkbox"
                    checked={routine.enabled}
                    on:change={() => toggleRoutine(index)}
                  />
                  <span class="slider"></span>
                </label>
              </div>
            </div>

            <div class="routine-actions">
              <h4>Actions:</h4>
              <ol>
                {#each routine.actions as action}
                  <li>
                    <strong>{action.description || action.type}</strong>
                    <span class="action-type">({action.type})</span>
                  </li>
                {/each}
              </ol>
            </div>

            {#if routine.editable}
              <div class="routine-footer">
                <button class="btn-secondary" disabled>Edit (Coming Soon)</button>
                <button class="btn-danger" disabled>Delete (Coming Soon)</button>
              </div>
            {/if}
          </div>
        {/each}
      </div>
    {/if}

    {#if saveStatus}
      <div
        class="save-status"
        class:success={saveStatus.includes("success")}
        class:error={saveStatus.includes("Error")}
      >
        {saveStatus}
      </div>
    {/if}

    <div class="form-actions">
      <button class="btn-primary" on:click={saveRoutines} disabled={loading}>
        {loading ? "Saving..." : "Save Changes"}
      </button>
      <button class="btn-secondary" disabled>Create New Routine (Coming Soon)</button>
    </div>

    <div class="info-box">
      <h4>About Routines</h4>
      <p>
        Routines allow you to bundle multiple actions together into a single
        command. For example, saying "good morning" can automatically check your
        calendar, read important emails, and summarize other messages.
      </p>
      <p>
        Currently, only the "Good Morning" system routine is available. Custom
        routine creation is coming soon!
      </p>
    </div>
  </div>
</div>

<style>
  .routines-list {
    display: flex;
    flex-direction: column;
    gap: 1rem;
  }

  .routine-card {
    background: var(--bg-secondary);
    border: 1px solid var(--border-primary);
    border-radius: var(--radius-md);
    padding: 1.5rem;
    transition: opacity 0.2s;
  }

  .routine-card.disabled {
    opacity: 0.6;
  }

  .routine-header {
    display: flex;
    justify-content: space-between;
    align-items: flex-start;
    margin-bottom: 1rem;
  }

  .routine-title h3 {
    margin: 0 0 0.5rem 0;
    font-size: 1.25rem;
    color: var(--text-primary);
  }

  .routine-trigger {
    display: inline-block;
    background: var(--bg-tertiary);
    color: var(--text-secondary);
    padding: 0.25rem 0.75rem;
    border-radius: var(--radius-sm);
    font-size: 0.875rem;
    font-family: monospace;
    margin-right: 0.5rem;
  }

  .system-badge {
    display: inline-block;
    background: var(--theo-blue);
    color: white;
    padding: 0.25rem 0.75rem;
    border-radius: var(--radius-sm);
    font-size: 0.75rem;
    font-weight: 600;
    text-transform: uppercase;
  }

  .routine-actions h4 {
    margin: 0 0 0.75rem 0;
    font-size: 0.9rem;
    color: var(--text-secondary);
    text-transform: uppercase;
    font-weight: 600;
  }

  .routine-actions ol {
    margin: 0;
    padding-left: 1.5rem;
  }

  .routine-actions li {
    margin-bottom: 0.5rem;
    color: var(--text-primary);
  }

  .action-type {
    color: var(--text-tertiary);
    font-size: 0.875rem;
  }

  .routine-footer {
    margin-top: 1rem;
    padding-top: 1rem;
    border-top: 1px solid var(--border-primary);
    display: flex;
    gap: 0.75rem;
  }

  .toggle-switch {
    position: relative;
    display: inline-block;
    width: 50px;
    height: 24px;
  }

  .toggle-switch input {
    opacity: 0;
    width: 0;
    height: 0;
  }

  .slider {
    position: absolute;
    cursor: pointer;
    top: 0;
    left: 0;
    right: 0;
    bottom: 0;
    background-color: var(--bg-tertiary);
    border: 1px solid var(--border-primary);
    transition: 0.3s;
    border-radius: 24px;
  }

  .slider:before {
    position: absolute;
    content: "";
    height: 16px;
    width: 16px;
    left: 3px;
    bottom: 3px;
    background-color: white;
    transition: 0.3s;
    border-radius: 50%;
  }

  input:checked + .slider {
    background-color: var(--theo-blue);
    border-color: var(--theo-blue);
  }

  input:checked + .slider:before {
    transform: translateX(26px);
  }

  .loading-state,
  .empty-state {
    text-align: center;
    padding: 3rem;
    color: var(--text-secondary);
  }

  .info-box {
    margin-top: 2rem;
    padding: 1.5rem;
    background: var(--bg-info, #e3f2fd);
    border-left: 4px solid var(--theo-blue);
    border-radius: var(--radius-md);
  }

  .info-box h4 {
    margin: 0 0 0.75rem 0;
    color: var(--theo-blue);
  }

  .info-box p {
    margin: 0 0 0.5rem 0;
    color: var(--text-primary);
    line-height: 1.6;
  }

  .info-box p:last-child {
    margin-bottom: 0;
  }

  .btn-danger {
    background: #dc3545;
    color: white;
    border: none;
    padding: 0.5rem 1rem;
    border-radius: var(--radius-sm);
    cursor: pointer;
    font-size: 0.875rem;
  }

  .btn-danger:hover:not(:disabled) {
    background: #c82333;
  }

  .btn-danger:disabled {
    opacity: 0.5;
    cursor: not-allowed;
  }
</style>
