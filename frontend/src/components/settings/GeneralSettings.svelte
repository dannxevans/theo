<script>
  import { updateSystemPromptConfig } from "../../lib/api";

  export let systemPromptConfig = {
    persona_name: "THEO",
    tone: "professional, conversational, direct",
    style_rules: "",
    custom_instructions: ""
  };

  let savingPrompt = false;
  let promptSaveStatus = null;

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
</script>

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
    color: var(--text-secondary);
    font-size: var(--font-size-sm);
    margin-bottom: var(--space-4);
  }

  .system-prompt-form {
    background: var(--bg-tertiary);
    border: 1px solid var(--border-primary);
    border-radius: var(--radius-lg);
    padding: var(--space-5);
    margin-bottom: var(--space-6);
  }

  .form-group {
    margin-bottom: var(--space-4);
  }

  .form-group label {
    display: block;
    width: auto;
    margin-bottom: var(--space-1);
    font-weight: 600;
    color: var(--text-primary);
  }

  .form-group input[type="text"],
  .form-group textarea {
    width: 100%;
    padding: var(--space-2);
    border: 1px solid var(--border-primary);
    border-radius: var(--radius-sm);
    font-family: inherit;
    background: var(--bg-primary);
    color: var(--text-primary);
  }

  .form-group input[type="text"]:focus,
  .form-group textarea:focus {
    outline: none;
    border-color: var(--border-focus);
  }

  .form-group small {
    display: block;
    color: var(--text-tertiary);
    font-size: var(--font-size-xs);
    margin-top: var(--space-1);
  }

  .form-actions {
    display: flex;
    gap: var(--space-3);
    margin-top: var(--space-5);
  }

  .save-status {
    margin-top: var(--space-3);
    padding: var(--space-3) var(--space-4);
    border-radius: var(--radius-sm);
    font-size: var(--font-size-sm);
  }

  .save-status.success {
    background: var(--status-success-bg);
    color: var(--status-success-text);
    border: 1px solid var(--status-success-border);
  }

  .save-status.error {
    background: var(--status-error-bg);
    color: var(--status-error-text);
    border: 1px solid var(--status-error-border);
  }
</style>
