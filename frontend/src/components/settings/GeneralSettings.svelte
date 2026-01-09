<script>
  import { updateSystemPromptConfig, getAuthHeaders, getUserPreference, setUserPreference, getWorkModeIPConfig, updateWorkModeIPConfig } from "../../lib/api";
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

  let sessionTimeoutHours = 8;
  let sessionTimeoutStatus = null;
  let loadingTimeout = true;

  // IP Restrictions
  let ipEnabled = false;
  let ipAllowedRanges = [];
  let newRange = "";
  let savingIP = false;
  let ipSaveStatus = null;
  let ipError = null;
  let loadingIP = true;

  // Check if user is admin
  let isAdmin = false;
  try {
    const user = JSON.parse(localStorage.getItem('user') || '{}');
    isAdmin = user.is_admin || false;
  } catch (e) {
    console.error('Failed to parse user from localStorage:', e);
  }

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

    // Load session timeout from backend
    try {
      const value = await getUserPreference("session_timeout");
      if (value) {
        sessionTimeoutHours = parseInt(value);
      } else {
        // Fallback to localStorage for migration
        const localValue = localStorage.getItem("theo.sessionTimeout");
        if (localValue) {
          sessionTimeoutHours = parseInt(localValue);
        }
      }
    } catch (err) {
      console.warn("Failed to load session timeout from backend:", err);
      // Fallback to localStorage
      const localValue = localStorage.getItem("theo.sessionTimeout");
      if (localValue) {
        sessionTimeoutHours = parseInt(localValue);
      }
    } finally {
      loadingTimeout = false;
    }

    // Load IP restrictions config (admin only)
    if (isAdmin) {
      try {
        const config = await getWorkModeIPConfig();
        ipEnabled = config.enabled || false;
        ipAllowedRanges = config.allowed_ranges || [];
      } catch (e) {
        console.error("Failed to load IP config:", e);
        ipError = `Failed to load configuration: ${e.message}`;
      } finally {
        loadingIP = false;
      }
    } else {
      loadingIP = false;
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

  async function saveSessionTimeout() {
    sessionTimeoutStatus = null;

    // Validation
    if (!sessionTimeoutHours || sessionTimeoutHours < 1 || sessionTimeoutHours > 168) {
      sessionTimeoutStatus = "Please enter a timeout between 1 and 168 hours";
      return;
    }

    try {
      // Save to backend
      await setUserPreference("session_timeout", sessionTimeoutHours.toString());

      // Also save to localStorage for backward compatibility with frontend timeout
      localStorage.setItem("theo.sessionTimeout", sessionTimeoutHours.toString());

      sessionTimeoutStatus = `Session timeout set to ${sessionTimeoutHours} hours. This will take effect immediately for backend session validation.`;
    } catch (err) {
      sessionTimeoutStatus = `Error saving session timeout: ${err.message}`;
    }

    setTimeout(() => {
      sessionTimeoutStatus = null;
    }, 5000);
  }

  async function saveIPConfig() {
    try {
      savingIP = true;
      ipSaveStatus = null;
      ipError = null;

      await updateWorkModeIPConfig({
        enabled: ipEnabled,
        allowed_ranges: ipAllowedRanges
      });

      ipSaveStatus = "IP restrictions saved successfully!";
      setTimeout(() => {
        ipSaveStatus = null;
      }, 3000);
    } catch (e) {
      ipError = `Error: ${e.message}`;
    } finally {
      savingIP = false;
    }
  }

  function addRange() {
    const trimmed = newRange.trim();
    if (!trimmed) {
      ipError = "Please enter an IP range";
      return;
    }

    // Basic CIDR validation
    const cidrPattern = /^(\d{1,3}\.){3}\d{1,3}(\/\d{1,2})?$|^([0-9a-fA-F]{0,4}:){2,7}[0-9a-fA-F]{0,4}(\/\d{1,3})?$/;
    if (!cidrPattern.test(trimmed)) {
      ipError = "Invalid CIDR format. Example: 192.168.1.0/24 or 10.0.0.1/32";
      return;
    }

    if (ipAllowedRanges.includes(trimmed)) {
      ipError = "This IP range is already in the list";
      return;
    }

    ipAllowedRanges = [...ipAllowedRanges, trimmed];
    newRange = "";
    ipError = null;
  }

  function removeRange(index) {
    ipAllowedRanges = ipAllowedRanges.filter((_, i) => i !== index);
  }

  function handleKeyPress(event) {
    if (event.key === "Enter") {
      addRange();
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

  <h2>Session Timeout</h2>
  <p class="subtitle">Configure automatic logout after a period of inactivity.</p>

  <div class="section">
    <div class="form-group">
      <label for="session-timeout">Timeout Duration (hours)</label>
      <input
        id="session-timeout"
        type="number"
        min="1"
        max="168"
        bind:value={sessionTimeoutHours}
        placeholder="8"
      />
      <small>Default: 8 hours. Maximum: 168 hours (1 week)</small>
    </div>

    <button
      class="btn-primary"
      on:click={saveSessionTimeout}
    >
      Save Timeout Setting
    </button>

    {#if sessionTimeoutStatus}
      <div class="success-message">{sessionTimeoutStatus}</div>
    {/if}
  </div>

  {#if isAdmin}
    <h2>Work Mode IP Restrictions</h2>
    <p class="subtitle">Control which IP addresses can access Work Mode (Admin Only).</p>

    <div class="section">
      {#if !loadingIP}
        <div class="form-group">
          <label class="checkbox-label">
            <input type="checkbox" bind:checked={ipEnabled} />
            Enable IP Restrictions for Work Mode
          </label>
          <small>
            When enabled, users can only enter Work Mode from approved IP addresses.
            Personal Mode remains unrestricted.
          </small>
        </div>

        {#if ipEnabled}
          <div class="form-group">
            <label>Allowed IP Ranges (CIDR Notation)</label>

            {#if ipAllowedRanges.length > 0}
              <div class="range-list">
                {#each ipAllowedRanges as range, i}
                  <div class="range-item">
                    <code class="range-code">{range}</code>
                    <button
                      type="button"
                      class="btn-danger"
                      on:click={() => removeRange(i)}
                      disabled={savingIP}
                    >
                      Remove
                    </button>
                  </div>
                {/each}
              </div>
            {:else}
              <p class="hint warning">
                ⚠️ No IP ranges configured. Work Mode will be blocked for all users.
              </p>
            {/if}

            <div class="add-range">
              <input
                type="text"
                class="range-input"
                bind:value={newRange}
                on:keypress={handleKeyPress}
                placeholder="e.g., 192.168.1.0/24 or 10.0.0.1/32"
                disabled={savingIP}
              />
              <button
                type="button"
                class="btn-secondary"
                on:click={addRange}
                disabled={savingIP}
              >
                Add Range
              </button>
            </div>

            <small>
              <strong>Examples:</strong><br />
              • Single IP: <code>203.0.113.42/32</code><br />
              • Subnet: <code>192.168.1.0/24</code> (256 addresses)<br />
              • Large range: <code>10.0.0.0/8</code> (16.7 million addresses)
            </small>
          </div>
        {/if}

        {#if ipSaveStatus}
          <div class="success-message">{ipSaveStatus}</div>
        {/if}

        {#if ipError}
          <div class="error-message">{ipError}</div>
        {/if}

        <button
          type="button"
          class="btn-primary"
          on:click={saveIPConfig}
          disabled={savingIP}
        >
          {savingIP ? "Saving..." : "Save IP Restrictions"}
        </button>
      {:else}
        <p class="hint">Loading IP configuration...</p>
      {/if}
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

  .range-list {
    background: var(--background-secondary);
    border: 1px solid var(--border-color);
    border-radius: 6px;
    padding: 12px;
    margin-bottom: 16px;
    max-height: 300px;
    overflow-y: auto;
  }

  .range-item {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 10px 12px;
    background: var(--background-primary);
    border: 1px solid var(--border-color);
    border-radius: 4px;
    margin-bottom: 8px;
    gap: 10px;
  }

  .range-item:last-child {
    margin-bottom: 0;
  }

  .range-code {
    font-family: 'Monaco', 'Menlo', 'Consolas', monospace;
    font-size: 0.9rem;
    color: var(--accent-color);
    background: transparent;
    padding: 0;
    flex: 1;
  }

  .add-range {
    display: flex;
    gap: 10px;
    margin-bottom: 12px;
  }

  .range-input {
    flex: 1;
    padding: 10px 12px;
    background: white;
    border: 1px solid var(--border-color);
    border-radius: 4px;
    color: #000;
    font-size: 0.95rem;
    font-family: 'Monaco', 'Menlo', 'Consolas', monospace;
  }

  .range-input:focus {
    outline: none;
    border-color: var(--accent-color);
    box-shadow: 0 0 0 2px rgba(var(--accent-color-rgb, 79, 70, 229), 0.1);
  }

  .range-input:disabled {
    opacity: 0.6;
    cursor: not-allowed;
    background: var(--background-secondary);
  }

  .hint.warning {
    color: var(--warning-color, #ff9800);
    font-weight: 500;
  }

  small code {
    background: var(--background-tertiary);
    padding: 2px 6px;
    border-radius: 3px;
    font-size: 0.85rem;
  }
</style>
