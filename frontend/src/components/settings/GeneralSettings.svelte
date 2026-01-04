<script>
  import { updateSystemPromptConfig, getAuthHeaders } from "../../lib/api";
  import { onMount } from "svelte";

  export let systemPromptConfig = {
    persona_name: "THEO",
    tone: "professional, conversational, direct",
    style_rules: "",
    custom_instructions: ""
  };

  let savingPrompt = false;
  let promptSaveStatus = null;
  let visualStreamingDisabled = false;
  let savingVisualStreaming = false;

  // Database restore state
  let showRestoreConfirm = false;
  let restoring = false;
  let restoreStatus = null;

  onMount(async () => {
    // Load visual streaming preference
    try {
      const response = await fetch("/api/settings/visual-streaming", {
        headers: getAuthHeaders()
      });
      if (response.ok) {
        const data = await response.json();
        visualStreamingDisabled = data.disabled;
        // Also update localStorage for immediate Chat.svelte access
        localStorage.setItem("visual_streaming_disabled", data.disabled.toString());
      }
    } catch (e) {
      console.error("Failed to load visual streaming setting:", e);
    }
  });

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

  async function toggleVisualStreaming() {
    try {
      savingVisualStreaming = true;
      const response = await fetch("/api/settings/visual-streaming", {
        method: "POST",
        headers: {
          ...getAuthHeaders(),
          "Content-Type": "application/json"
        },
        body: JSON.stringify({ disabled: visualStreamingDisabled })
      });

      if (!response.ok) {
        throw new Error("Failed to save visual streaming setting");
      }

      // Update localStorage for immediate Chat.svelte access
      localStorage.setItem("visual_streaming_disabled", visualStreamingDisabled.toString());

      // Dispatch event to notify Chat component
      window.dispatchEvent(new CustomEvent("visualStreamingChanged", {
        detail: { disabled: visualStreamingDisabled }
      }));
    } catch (e) {
      console.error("Failed to save visual streaming setting:", e);
      // Revert the toggle on error
      visualStreamingDisabled = !visualStreamingDisabled;
    } finally {
      savingVisualStreaming = false;
    }
  }

  async function restoreFromS3() {
    try {
      restoring = true;
      restoreStatus = null;

      const response = await fetch("/api/settings/database/restore-from-s3", {
        method: "POST",
        headers: {
          ...getAuthHeaders(),
          "Content-Type": "application/json"
        }
      });

      const data = await response.json();

      if (!response.ok) {
        throw new Error(data.error || "Failed to restore database");
      }

      restoreStatus = {
        type: "success",
        message: `Database restored successfully! ${data.message || ""}`
      };

      // Reload page after 2 seconds to pick up new database
      setTimeout(() => {
        window.location.reload();
      }, 2000);

    } catch (e) {
      console.error("Failed to restore database:", e);
      restoreStatus = {
        type: "error",
        message: e.message || "Failed to restore database from S3"
      };
    } finally {
      restoring = false;
      showRestoreConfirm = false;
    }
  }
</script>

<div class="tab-panel">
  <h2>System Prompt Configuration</h2>
  <p class="subtitle">Customize how THEO responds and behaves.</p>

<div class="section">
    <!--   <div class="form-group">
      <label for="persona-name">Persona Name</label>
      <input
        id="persona-name"
        type="text"
        bind:value={systemPromptConfig.persona_name}
        placeholder="e.g., THEO"
      />
      <small>The name your AI assistant will identify as</small>
    </div> -->

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

    {#if promptSaveStatus}
      <div class="save-status" class:success={promptSaveStatus.includes("success")} class:error={promptSaveStatus.includes("Error")}>
        {promptSaveStatus}
      </div>
    {/if}

    <div class="form-actions">
      <button
        class="btn-primary"
        on:click={saveSystemPrompt}
        disabled={savingPrompt}
      >
        {savingPrompt ? "Saving..." : "Save Settings"}
      </button>
    </div>
  </div>

  <h2>Display Preferences</h2>
  <p class="subtitle">Customize how messages appear in the chat interface.</p>

  <div class="section">
    <div class="form-group">
      <div class="toggle-container">
        <label class="toggle-label">
          <input
            type="checkbox"
            bind:checked={visualStreamingDisabled}
            on:change={toggleVisualStreaming}
            disabled={savingVisualStreaming}
          />
          <span class="toggle-text">Disable Visual Streaming</span>
        </label>
        <small>When enabled, messages will appear instantly instead of with a typewriter effect. Reduces CPU usage and may improve accessibility.</small>
      </div>
    </div>
  </div>

  <h2>Database Management</h2>
  <p class="subtitle">Advanced database operations for Unraid deployments.</p>

  <div class="section">
    <div class="warning-box">
      <strong>⚠️ Warning:</strong> Only use this feature when running THEO on Unraid. This will replace your current database with the latest backup from AWS S3.
    </div>

    <div class="form-group">
      <button
        class="btn-danger"
        on:click={() => showRestoreConfirm = true}
        disabled={restoring}
      >
        Restore Database from S3
      </button>
      <small>Download and restore the latest database backup from AWS S3</small>
    </div>

    {#if restoreStatus}
      <div class="restore-status" class:success={restoreStatus.type === "success"} class:error={restoreStatus.type === "error"}>
        {restoreStatus.message}
      </div>
    {/if}
  </div>

  <!-- Confirmation Modal -->
  {#if showRestoreConfirm}
    <div class="modal-overlay" on:click={() => showRestoreConfirm = false}>
      <div class="modal" on:click|stopPropagation>
        <h3>Confirm Database Restore</h3>
        <p>Are you sure you want to restore the database from S3?</p>
        <p class="warning-text">
          <strong>This will:</strong>
        </p>
        <ul class="warning-list">
          <li>Back up your current database</li>
          <li>Download the latest database from AWS S3</li>
          <li>Replace your current database</li>
          <li>Reload the application</li>
        </ul>
        <p class="warning-text">
          <strong>⚠️ Any unsaved local changes will be lost!</strong>
        </p>
        <div class="modal-actions">
          <button
            class="btn-secondary"
            on:click={() => showRestoreConfirm = false}
            disabled={restoring}
          >
            Cancel
          </button>
          <button
            class="btn-danger"
            on:click={restoreFromS3}
            disabled={restoring}
          >
            {restoring ? "Restoring..." : "Yes, Restore from S3"}
          </button>
        </div>
      </div>
    </div>
  {/if}
</div>

<style>
  /* All styles now imported from global CSS:
     - .tab-panel from settings.css
     - .section from settings.css
     - .form-group from forms.css
     - .form-actions from settings.css
     - .save-status from settings.css
  */

  .warning-box {
    background: #fff3cd;
    border: 1px solid #ffc107;
    border-radius: 6px;
    padding: 12px;
    margin-bottom: 16px;
    color: #856404;
  }

  .btn-danger {
    background: #dc3545;
    color: white;
    border: none;
    padding: 10px 20px;
    border-radius: 6px;
    cursor: pointer;
    font-size: 14px;
    font-weight: 500;
    transition: background 0.2s;
  }

  .btn-danger:hover:not(:disabled) {
    background: #c82333;
  }

  .btn-danger:disabled {
    opacity: 0.5;
    cursor: not-allowed;
  }

  .btn-secondary {
    background: #6c757d;
    color: white;
    border: none;
    padding: 10px 20px;
    border-radius: 6px;
    cursor: pointer;
    font-size: 14px;
    font-weight: 500;
    transition: background 0.2s;
  }

  .btn-secondary:hover:not(:disabled) {
    background: #5a6268;
  }

  .btn-secondary:disabled {
    opacity: 0.5;
    cursor: not-allowed;
  }

  .restore-status {
    padding: 12px;
    border-radius: 6px;
    margin-top: 12px;
  }

  .restore-status.success {
    background: #d4edda;
    border: 1px solid #c3e6cb;
    color: #155724;
  }

  .restore-status.error {
    background: #f8d7da;
    border: 1px solid #f5c6cb;
    color: #721c24;
  }

  /* Modal styles */
  .modal-overlay {
    position: fixed;
    top: 0;
    left: 0;
    right: 0;
    bottom: 0;
    background: rgba(0, 0, 0, 0.5);
    display: flex;
    align-items: center;
    justify-content: center;
    z-index: 1000;
  }

  .modal {
    background: white;
    border-radius: 8px;
    padding: 24px;
    max-width: 500px;
    width: 90%;
    box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15);
  }

  .modal h3 {
    margin-top: 0;
    margin-bottom: 16px;
    color: #333;
  }

  .modal p {
    margin-bottom: 12px;
    color: #666;
  }

  .warning-text {
    color: #856404;
    font-weight: 500;
  }

  .warning-list {
    margin: 12px 0;
    padding-left: 24px;
    color: #666;
  }

  .warning-list li {
    margin-bottom: 8px;
  }

  .modal-actions {
    display: flex;
    justify-content: flex-end;
    gap: 12px;
    margin-top: 24px;
  }
</style>
