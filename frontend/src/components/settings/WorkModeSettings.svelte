<script>
  import { updateModeSettings, updateWorkSubtabConfig, getPIIConfig, updatePIIConfig } from "../../lib/api";
  import { onMount } from "svelte";

  export let workModeSettings = {
    system_prompt_override: "",
    preferred_provider_id: null,
    tone: "professional"
  };
  export let codeSubtabConfig = {
    language: "servicenow_javascript",
    framework: "",
    additional_context: ""
  };
  export let emailSubtabConfig = {
    tone: "professional",
    signature: ""
  };
  export let providers = [];

  let savingWorkMode = false;
  let savingCodeSubtab = false;
  let savingEmailSubtab = false;
  let savingPII = false;
  let workModeSaveStatus = null;
  let codeSubtabSaveStatus = null;
  let emailSubtabSaveStatus = null;
  let piiSaveStatus = null;

  // PII Configuration
  let piiFilteringEnabled = false;
  let piiRedactionConfig = {
    emails: true,
    phones: true,
    ssns: true,
    creditCards: true,
    names: false,
    addresses: false
  };

  // Load PII config on mount
  onMount(async () => {
    try {
      const config = await getPIIConfig();
      piiFilteringEnabled = config.pii_filtering_enabled || false;
      if (config.pii_redaction_config) {
        // Parse if string, otherwise use as-is
        const redactionConfig = typeof config.pii_redaction_config === 'string'
          ? JSON.parse(config.pii_redaction_config)
          : config.pii_redaction_config;
        piiRedactionConfig = { ...piiRedactionConfig, ...redactionConfig };
      }
    } catch (e) {
      console.error("Failed to load PII config:", e);
    }
  });

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

  async function savePIIConfig() {
    try {
      savingPII = true;
      piiSaveStatus = null;
      await updatePIIConfig({
        pii_filtering_enabled: piiFilteringEnabled,
        pii_redaction_config: piiRedactionConfig
      });
      piiSaveStatus = "PII protection settings saved!";
      setTimeout(() => {
        piiSaveStatus = null;
      }, 3000);
    } catch (e) {
      piiSaveStatus = `Error: ${e.message}`;
    } finally {
      savingPII = false;
    }
  }
</script>

<div class="work-mode-settings">
  <h2>💼 Work Mode</h2>
  <p class="subtitle">Professional tone and optimized for productivity tasks.</p>

  <!-- Work Mode Settings -->
  <div class="section">
    <h3>General Settings</h3>

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

  <!-- PII Protection Settings -->
  <div class="section">
    <h3>🔒 PII Protection (OFFICIAL Mode)</h3>
    <p class="hint">
      Work mode includes PII (Personally Identifiable Information) filtering to protect sensitive data before it's sent to AI models.
      Enable this to automatically redact emails, phone numbers, SSNs, credit cards, and other sensitive information.
    </p>

    <div class="form-group">
      <label class="checkbox-label">
        <input
          type="checkbox"
          bind:checked={piiFilteringEnabled}
        />
        Enable PII Filtering
      </label>
      <p class="hint">When enabled, sensitive information will be redacted before processing</p>
    </div>

    {#if piiFilteringEnabled}
      <div class="pii-config-options">
        <h4>Redaction Options</h4>
        <p class="hint">Select which types of information to redact:</p>

        <div class="checkbox-grid">
          <label class="checkbox-label">
            <input type="checkbox" bind:checked={piiRedactionConfig.emails} />
            Email Addresses
          </label>

          <label class="checkbox-label">
            <input type="checkbox" bind:checked={piiRedactionConfig.phones} />
            Phone Numbers
          </label>

          <label class="checkbox-label">
            <input type="checkbox" bind:checked={piiRedactionConfig.ssns} />
            Social Security Numbers
          </label>

          <label class="checkbox-label">
            <input type="checkbox" bind:checked={piiRedactionConfig.creditCards} />
            Credit Card Numbers
          </label>

          <label class="checkbox-label">
            <input type="checkbox" bind:checked={piiRedactionConfig.names} />
            Personal Names (experimental)
          </label>

          <label class="checkbox-label">
            <input type="checkbox" bind:checked={piiRedactionConfig.addresses} />
            Street Addresses (experimental)
          </label>
        </div>

        <div class="pii-warning">
          <strong>⚠️ Note:</strong> Name and address detection are experimental and may have false positives.
          Use with caution.
        </div>
      </div>
    {/if}

    {#if piiSaveStatus}
      <div class="success-message">{piiSaveStatus}</div>
    {/if}

    <button
      class="btn-primary"
      on:click={savePIIConfig}
      disabled={savingPII}
    >
      {savingPII ? "Saving..." : "Save PII Protection Settings"}
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
</div>

<style>
  .work-mode-settings {
    width: 100%;
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

  .section {
    margin-bottom: var(--space-6);
    padding-bottom: var(--space-6);
    border-bottom: 1px solid var(--gray-200);
  }

  .section:last-child {
    border-bottom: none;
  }

  .subsection {
    margin-top: var(--space-6);
    padding-top: var(--space-4);
    border-top: 1px solid var(--gray-100);
  }

  .subsection:first-child {
    border-top: none;
    padding-top: 0;
  }

  h3 {
    margin-bottom: var(--space-4);
  }

  h4 {
    margin-bottom: var(--space-3);
  }

  .hint {
    font-size: var(--font-size-sm);
    color: var(--gray-500);
    margin-top: var(--space-1);
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
  .form-group select,
  .form-group textarea {
    width: 100%;
    padding: var(--space-2);
    border: 1px solid var(--gray-300);
    border-radius: var(--radius-sm);
    font-family: inherit;
  }

  .form-group p.hint {
    display: block;
    color: var(--gray-500);
    font-size: var(--font-size-xs);
    margin-top: var(--space-1);
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

  .status-message {
    padding: var(--space-3);
    background: #d1fae5;
    border: 1px solid #6ee7b7;
    border-radius: var(--radius-md);
    color: #065f46;
    font-size: var(--font-size-sm);
    margin-bottom: var(--space-3);
  }

  .btn-primary {
    margin-bottom: var(--space-4);
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

  /* PII Configuration */
  .pii-config-options {
    margin-top: var(--space-4);
    padding: var(--space-4);
    background: #f8f9fa;
    border-radius: var(--radius-md);
  }

  .checkbox-grid {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
    gap: var(--space-3);
    margin: var(--space-3) 0;
  }

  .pii-warning {
    margin-top: var(--space-4);
    padding: var(--space-3);
    background: #fff3cd;
    border: 1px solid #ffc107;
    border-radius: var(--radius-sm);
    color: #856404;
    font-size: var(--font-size-sm);
  }
</style>
