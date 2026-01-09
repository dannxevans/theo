<script>
  import { onMount } from "svelte";
  import { getWorkModeIPConfig, updateWorkModeIPConfig } from "../../lib/api";

  let enabled = false;
  let allowedRanges = [];
  let newRange = "";
  let loading = true;
  let saving = false;
  let saveStatus = null;
  let error = null;

  onMount(async () => {
    await loadConfig();
  });

  async function loadConfig() {
    try {
      loading = true;
      error = null;
      const config = await getWorkModeIPConfig();
      enabled = config.enabled || false;
      allowedRanges = config.allowed_ranges || [];
    } catch (e) {
      console.error("Failed to load IP config:", e);
      error = `Failed to load configuration: ${e.message}`;
    } finally {
      loading = false;
    }
  }

  async function saveConfig() {
    try {
      saving = true;
      saveStatus = null;
      error = null;

      await updateWorkModeIPConfig({
        enabled,
        allowed_ranges: allowedRanges
      });

      saveStatus = "IP restrictions saved successfully!";
      setTimeout(() => {
        saveStatus = null;
      }, 3000);
    } catch (e) {
      error = `Error: ${e.message}`;
    } finally {
      saving = false;
    }
  }

  function addRange() {
    const trimmed = newRange.trim();
    if (!trimmed) {
      error = "Please enter an IP range";
      return;
    }

    // Basic CIDR validation (format check only, backend will validate fully)
    if (!validateCIDRFormat(trimmed)) {
      error = "Invalid CIDR format. Example: 192.168.1.0/24 or 10.0.0.1/32";
      return;
    }

    if (allowedRanges.includes(trimmed)) {
      error = "This IP range is already in the list";
      return;
    }

    allowedRanges = [...allowedRanges, trimmed];
    newRange = "";
    error = null;
  }

  function removeRange(index) {
    allowedRanges = allowedRanges.filter((_, i) => i !== index);
  }

  function validateCIDRFormat(cidr) {
    // Basic format check: should contain IP address and optional /prefix
    const cidrPattern = /^(\d{1,3}\.){3}\d{1,3}(\/\d{1,2})?$|^([0-9a-fA-F]{0,4}:){2,7}[0-9a-fA-F]{0,4}(\/\d{1,3})?$/;
    return cidrPattern.test(cidr);
  }

  function handleKeyPress(event) {
    if (event.key === "Enter") {
      addRange();
    }
  }
</script>

<div class="tab-panel">
  <h2>Work Mode IP Restrictions</h2>
  <p class="subtitle">Control which IP addresses can access Work Mode.</p>

  {#if loading}
    <p class="hint">Loading configuration...</p>
  {:else}
    <div class="section">
      <h3>IP Restrictions</h3>

      <div class="form-group">
        <label class="checkbox-label">
          <input type="checkbox" bind:checked={enabled} />
          Enable IP Restrictions for Work Mode
        </label>
        <p class="hint">
          When enabled, users can only enter Work Mode from approved IP addresses.
          Personal Mode remains unrestricted.
        </p>
      </div>

      {#if enabled}
        <div class="form-group">
          <label>Allowed IP Ranges (CIDR Notation)</label>

          {#if allowedRanges.length > 0}
            <div class="range-list">
              {#each allowedRanges as range, i}
                <div class="range-item">
                  <code class="range-code">{range}</code>
                  <button
                    type="button"
                    class="btn-danger"
                    on:click={() => removeRange(i)}
                    disabled={saving}
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
              disabled={saving}
            />
            <button
              type="button"
              class="btn-secondary"
              on:click={addRange}
              disabled={saving}
            >
              Add Range
            </button>
          </div>

          <p class="hint">
            <strong>Examples:</strong><br />
            • Single IP: <code>203.0.113.42/32</code><br />
            • Subnet: <code>192.168.1.0/24</code> (256 addresses)<br />
            • Large range: <code>10.0.0.0/8</code> (16.7 million addresses)
          </p>
        </div>
      {/if}

      {#if saveStatus}
        <div class="success-message">{saveStatus}</div>
      {/if}

      {#if error}
        <div class="error-message">{error}</div>
      {/if}

      <button
        type="button"
        class="btn-primary"
        on:click={saveConfig}
        disabled={loading || saving}
      >
        {saving ? "Saving..." : "Save IP Restrictions"}
      </button>
    </div>
  {/if}
</div>

<style>
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

  .hint code {
    background: var(--background-tertiary);
    padding: 2px 6px;
    border-radius: 3px;
    font-size: 0.85rem;
  }
</style>
