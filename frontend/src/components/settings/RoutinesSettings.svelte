<script>
  import { onMount } from "svelte";

  // Routines state
  let routines = [];
  let loading = false;
  let saveStatus = null;

  // Editor state
  let showEditor = false;
  let editingRoutine = null;
  let editorMode = "create"; // "create" or "edit"

  // Form state
  let formName = "";
  let formTrigger = "";
  let formActions = [];
  let formConsolidationPrompt = "";

  // Action types available
  // These come from the available action handlers in the backend
  // (CalendarHandlers, EmailHandlers, WeatherService, TrafficService, etc.)
  const ACTION_TYPES = [
    // Calendar actions
    {
      type: "calendar_read",
      label: "Read Calendar",
      description: "Check calendar events",
      defaultParams: { timeframe: "today" },
    },
    {
      type: "book_appointment",
      label: "Book Appointment",
      description: "Schedule a calendar event",
      defaultParams: {},
    },
    {
      type: "update_appointment",
      label: "Update Appointment",
      description: "Modify an existing calendar event",
      defaultParams: {},
    },
    {
      type: "cancel_appointment",
      label: "Cancel Appointment",
      description: "Delete a calendar event",
      defaultParams: {},
    },
    // Email actions
    {
      type: "email_check",
      label: "Check Emails",
      description: "Check for emails",
      defaultParams: { filter: "all", unread_only: false },
    },
    {
      type: "email_summary",
      label: "Summarize Emails",
      description: "Summarize unread emails",
      defaultParams: { filter: "unread", exclude_important: false },
    },
    {
      type: "read_email",
      label: "Read Email",
      description: "Read specific email(s)",
      defaultParams: {},
    },
    {
      type: "compose_email",
      label: "Compose Email",
      description: "Draft a new email",
      defaultParams: {},
    },
    {
      type: "email_reply",
      label: "Reply to Email",
      description: "Reply to an email",
      defaultParams: {},
    },
    {
      type: "send_email",
      label: "Send Email",
      description: "Send an email message",
      defaultParams: {},
    },
    // Task actions
    {
      type: "tasks_read",
      label: "Read All Tasks",
      description: "Show all tasks",
      defaultParams: {},
    },
    {
      type: "tasks_today",
      label: "Today's Tasks",
      description: "Show tasks due today",
      defaultParams: {},
    },
    {
      type: "tasks_week",
      label: "This Week's Tasks",
      description: "Show tasks due this week",
      defaultParams: {},
    },
    {
      type: "create_task",
      label: "Create Task",
      description: "Create a new task",
      defaultParams: {},
    },
    {
      type: "complete_task",
      label: "Complete Task",
      description: "Mark a task as complete",
      defaultParams: {},
    },
    // Weather actions
    {
      type: "weather",
      label: "Weather",
      description: "Get weather forecast",
      defaultParams: {},
    },
    // Routing actions
    {
      type: "route",
      label: "Route/Traffic",
      description: "Get route and traffic information",
      defaultParams: {},
    },
    // WHOOP health & fitness actions
    {
      type: "whoop_sleep",
      label: "WHOOP Sleep",
      description: "Check last night's sleep data",
      defaultParams: {},
    },
    {
      type: "whoop_recovery",
      label: "WHOOP Recovery",
      description: "Check recovery status",
      defaultParams: {},
    },
    {
      type: "whoop_workout",
      label: "WHOOP Workout",
      description: "Check last workout data",
      defaultParams: {},
    },
    // Custom action
    {
      type: "custom_action",
      label: "Custom Action",
      description: "Custom LLM prompt",
      defaultParams: {},
      isCustom: true,
    },
  ];

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
      saveStatus = `Error loading routines: ${error.message}`;
    } finally {
      loading = false;
    }
  }

  async function saveRoutine() {
    try {
      loading = true;
      saveStatus = null;

      const token = localStorage.getItem("auth_token");

      // Validate form
      if (!formName.trim()) {
        saveStatus = "Error: Routine name is required";
        return;
      }

      if (!formTrigger.trim()) {
        saveStatus = "Error: Trigger phrase is required";
        return;
      }

      if (formActions.length === 0) {
        saveStatus = "Error: At least one action is required";
        return;
      }

      const routineData = {
        name: formName,
        triggers: [formTrigger],
        actions: formActions,
        consolidation_prompt: formConsolidationPrompt || `Summarize the results of the ${formName} routine in a concise and friendly manner.`,
      };

      let response;

      if (editorMode === "create") {
        // Create new routine
        response = await fetch("/api/routines", {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            Authorization: `Bearer ${token}`,
          },
          body: JSON.stringify(routineData),
        });
      } else {
        // Update existing routine
        response = await fetch(`/api/routines/${editingRoutine.id}`, {
          method: "PUT",
          headers: {
            "Content-Type": "application/json",
            Authorization: `Bearer ${token}`,
          },
          body: JSON.stringify({
            ...routineData,
            enabled: editingRoutine.enabled,
          }),
        });
      }

      if (!response.ok) {
        const error = await response.json();
        throw new Error(error.error || "Failed to save routine");
      }

      saveStatus = `Routine ${editorMode === "create" ? "created" : "updated"} successfully!`;
      setTimeout(() => {
        saveStatus = null;
      }, 3000);

      // Reload routines and close editor
      await loadRoutines();
      closeEditor();
    } catch (error) {
      console.error("Failed to save routine:", error);
      saveStatus = `Error: ${error.message}`;
    } finally {
      loading = false;
    }
  }

  async function deleteRoutine(routine) {
    if (!confirm(`Are you sure you want to delete "${routine.name}"?`)) {
      return;
    }

    try {
      loading = true;
      saveStatus = null;

      const token = localStorage.getItem("auth_token");
      const response = await fetch(`/api/routines/${routine.id}`, {
        method: "DELETE",
        headers: {
          Authorization: `Bearer ${token}`,
        },
      });

      if (!response.ok) {
        const error = await response.json();
        throw new Error(error.error || "Failed to delete routine");
      }

      saveStatus = "Routine deleted successfully!";
      setTimeout(() => {
        saveStatus = null;
      }, 3000);

      // Reload routines
      await loadRoutines();
    } catch (error) {
      console.error("Failed to delete routine:", error);
      saveStatus = `Error: ${error.message}`;
    } finally {
      loading = false;
    }
  }

  async function toggleRoutine(routine) {
    try {
      const token = localStorage.getItem("auth_token");
      const response = await fetch(`/api/routines/${routine.id}`, {
        method: "PUT",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${token}`,
        },
        body: JSON.stringify({
          enabled: !routine.enabled,
        }),
      });

      if (!response.ok) {
        throw new Error("Failed to toggle routine");
      }

      // Update local state
      routine.enabled = !routine.enabled;
      routines = [...routines];
    } catch (error) {
      console.error("Failed to toggle routine:", error);
      saveStatus = `Error: ${error.message}`;
    }
  }

  function openCreateEditor() {
    editorMode = "create";
    formName = "";
    formTrigger = "";
    formActions = [];
    formConsolidationPrompt = "";
    editingRoutine = null;
    showEditor = true;
  }

  function openEditEditor(routine) {
    editorMode = "edit";
    formName = routine.name;
    formTrigger = routine.trigger;
    formActions = JSON.parse(JSON.stringify(routine.actions)); // Deep copy
    formConsolidationPrompt = routine.consolidation_prompt || "";
    editingRoutine = routine;
    showEditor = true;
  }

  function closeEditor() {
    showEditor = false;
    editingRoutine = null;
  }

  function addAction() {
    formActions = [
      ...formActions,
      {
        type: "calendar_read",
        description: "Check today's calendar",
        params: { timeframe: "today" },
      },
    ];
  }

  function removeAction(index) {
    formActions = formActions.filter((_, i) => i !== index);
  }

  function updateActionType(index, type) {
    const actionDef = ACTION_TYPES.find((a) => a.type === type);
    formActions[index] = {
      type,
      description: actionDef.description,
      params: actionDef.defaultParams,
      customPrompt: actionDef.isCustom ? "" : undefined,
    };
    formActions = [...formActions];
  }

  function updateCustomPrompt(index, prompt) {
    formActions[index].customPrompt = prompt;
    formActions[index].description = prompt || "Custom LLM prompt";
    formActions = [...formActions];
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
    {:else if showEditor}
      <!-- Routine Editor -->
      <div class="routine-editor">
        <div class="editor-header">
          <h3>
            {editorMode === "create" ? "Create New Routine" : `Edit ${editingRoutine?.name || "Routine"}`}
          </h3>
          <button class="btn-secondary" on:click={closeEditor}>Cancel</button>
        </div>

        <div class="form-group">
          <label for="routine-name">Routine Name</label>
          <input
            id="routine-name"
            type="text"
            bind:value={formName}
            placeholder="e.g., Good Morning"
          />
        </div>

        <div class="form-group">
          <label for="routine-trigger">Trigger Phrase</label>
          <input
            id="routine-trigger"
            type="text"
            bind:value={formTrigger}
            placeholder="e.g., good morning"
          />
          <small>The phrase that will trigger this routine</small>
        </div>

        <div class="form-group">
          <label>Actions</label>
          <small class="action-help">Actions are executed from the backend action handlers (calendar, email, etc.)</small>
          <div class="actions-list">
            {#each formActions as action, index}
              <div class="action-item" class:custom={action.type === "custom_action"}>
                <span class="action-number">{index + 1}.</span>
                <div class="action-fields">
                  <select
                    bind:value={action.type}
                    on:change={() => updateActionType(index, action.type)}
                  >
                    {#each ACTION_TYPES as actionType}
                      <option value={actionType.type}>{actionType.label}</option>
                    {/each}
                  </select>
                  {#if action.type === "custom_action"}
                    <input
                      type="text"
                      bind:value={action.customPrompt}
                      on:input={(e) => updateCustomPrompt(index, e.target.value)}
                      placeholder="Enter custom prompt (e.g., 'Tell me a joke')"
                      class="custom-prompt-input"
                    />
                  {:else}
                    <input
                      type="text"
                      bind:value={action.description}
                      placeholder="Description"
                    />
                  {/if}
                </div>
                <button
                  class="btn-icon btn-remove"
                  on:click={() => removeAction(index)}
                  title="Remove action"
                >
                  ✕
                </button>
              </div>
            {/each}
          </div>
          <button
            class="btn-secondary btn-add-action"
            on:click={addAction}
          >
            + Add Action
          </button>
        </div>

        <div class="form-group">
          <label for="routine-consolidation">Consolidation Prompt (Optional)</label>
          <textarea
            id="routine-consolidation"
            bind:value={formConsolidationPrompt}
            placeholder="Instructions for how to combine the action results into a single response..."
            rows="4"
          />
          <small>How should the results be combined into a response?</small>
        </div>

        <div class="editor-actions">
          <button
            class="btn-primary"
            on:click={saveRoutine}
            disabled={loading}
          >
            {loading ? "Saving..." : editorMode === "create" ? "Create Routine" : "Save Changes"}
          </button>
          <button class="btn-secondary" on:click={closeEditor}>Cancel</button>
        </div>
      </div>
    {:else}
      <!-- Routines List -->
      <div class="routines-actions">
        <button class="btn-primary" on:click={openCreateEditor}>
          + Create New Routine
        </button>
      </div>

      {#if routines.length === 0}
        <div class="empty-state">
          <p>No routines configured yet. Create your first routine!</p>
        </div>
      {:else}
        <div class="routines-list">
          {#each routines as routine}
            <div class="routine-card" class:disabled={!routine.enabled}>
              <div class="routine-header">
                <div class="routine-title">
                  <h3>{routine.name}</h3>
                  <span class="routine-trigger">Trigger: "{routine.trigger}"</span>
                </div>
                <div class="routine-actions-header">
                  <label class="toggle-switch">
                    <input
                      type="checkbox"
                      checked={routine.enabled}
                      on:change={() => toggleRoutine(routine)}
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

              <div class="routine-footer">
                <button class="btn-secondary" on:click={() => openEditEditor(routine)}>
                  Edit
                </button>
                <button class="btn-danger" on:click={() => deleteRoutine(routine)}>
                  Delete
                </button>
              </div>
            </div>
          {/each}
        </div>
      {/if}

      <div class="info-box">
        <h4>About Routines</h4>
        <p>
          Routines allow you to bundle multiple actions together into a single
          command. For example, saying "good morning" can automatically check your
          calendar, read important emails, and summarize other messages.
        </p>
        <p>
          Create custom routines with your own trigger phrases and action sequences!
        </p>
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
  </div>
</div>

<style>
  .routines-actions {
    display: flex;
    justify-content: flex-end;
    margin-bottom: 1.5rem;
  }

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

  /* Routine Editor */
  .routine-editor {
    background: var(--bg-secondary);
    border: 1px solid var(--border-primary);
    border-radius: var(--radius-md);
    padding: 2rem;
  }

  .editor-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 2rem;
    padding-bottom: 1rem;
    border-bottom: 2px solid var(--border-primary);
  }

  .editor-header h3 {
    margin: 0;
    font-size: 1.5rem;
    color: var(--text-primary);
  }

  .action-help {
    display: block;
    margin-top: 0.25rem;
    margin-bottom: 0.75rem;
    color: var(--text-secondary);
  }

  .actions-list {
    display: flex;
    flex-direction: column;
    gap: 0.75rem;
    margin-bottom: 1rem;
  }

  .action-item {
    display: flex;
    align-items: center;
    gap: 0.75rem;
    padding: 0.75rem;
    background: var(--bg-tertiary);
    border: 1px solid var(--border-primary);
    border-radius: var(--radius-sm);
  }

  .action-item.custom {
    background: linear-gradient(135deg, var(--bg-tertiary) 0%, rgba(var(--theo-blue-rgb, 59, 130, 246), 0.05) 100%);
    border-color: var(--theo-blue);
  }

  .action-number {
    font-weight: 600;
    color: var(--text-secondary);
    min-width: 2rem;
  }

  .action-fields {
    flex: 1;
    display: flex;
    gap: 0.75rem;
  }

  .action-fields select,
  .action-fields input {
    flex: 1;
  }

  .custom-prompt-input {
    font-style: italic;
    border-color: var(--theo-blue) !important;
  }

  .custom-prompt-input::placeholder {
    font-style: italic;
    opacity: 0.6;
  }

  .btn-icon {
    background: transparent;
    border: none;
    cursor: pointer;
    padding: 0.5rem;
    color: var(--text-secondary);
    font-size: 1.25rem;
    line-height: 1;
    transition: all 0.2s;
  }

  .btn-icon:hover:not(:disabled) {
    color: var(--text-primary);
    transform: scale(1.1);
  }

  .btn-remove:hover:not(:disabled) {
    color: #dc3545;
  }

  .btn-add-action {
    width: 100%;
  }

  .editor-actions {
    display: flex;
    gap: 1rem;
    margin-top: 2rem;
    padding-top: 1.5rem;
    border-top: 1px solid var(--border-primary);
  }
</style>
