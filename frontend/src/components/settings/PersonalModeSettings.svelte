<script>
  import { updateModeSettings } from "../../lib/api";

  export let personalModeSettings = {
    system_prompt_override: "",
    preferred_provider_id: null,
    tone: "casual"
  };
  export let providers = [];

  let savingPersonalMode = false;
  let personalModeSaveStatus = null;

  async function savePersonalMode() {
    try {
      savingPersonalMode = true;
      personalModeSaveStatus = null;
      await updateModeSettings("personal", personalModeSettings);
      personalModeSaveStatus = "Personal mode settings saved!";
      setTimeout(() => {
        personalModeSaveStatus = null;
      }, 3000);
    } catch (e) {
      personalModeSaveStatus = `Error: ${e.message}`;
    } finally {
      savingPersonalMode = false;
    }
  }
</script>

<div class="tab-panel">
  <h2>🏠 Personal Mode</h2>
  <p class="subtitle">Casual tone and optimized for general conversation.</p>

  <div class="section">
    <h3>General Settings</h3>

    <div class="form-group">
      <label for="personal-tone">Tone</label>
      <select id="personal-tone" bind:value={personalModeSettings.tone}>
        <option value="casual">Casual</option>
        <option value="neutral">Neutral</option>
        <option value="professional">Professional</option>
      </select>
    </div>

    <div class="form-group">
      <label for="personal-provider">Preferred Provider (optional)</label>
      <select id="personal-provider" bind:value={personalModeSettings.preferred_provider_id}>
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
      <label for="personal-prompt">Custom System Prompt Override (optional)</label>
      <textarea
        id="personal-prompt"
        bind:value={personalModeSettings.system_prompt_override}
        placeholder="Leave empty to use default system prompt. Add custom instructions specific to personal mode here."
        rows="6"
      ></textarea>
      <p class="hint">
        This will replace the default system prompt when in personal mode. Leave empty to use the standard configuration.
      </p>
    </div>

    {#if personalModeSaveStatus}
      <div class="success-message">{personalModeSaveStatus}</div>
    {/if}

    <button
      class="btn-primary"
      on:click={savePersonalMode}
      disabled={savingPersonalMode}
    >
      {savingPersonalMode ? "Saving..." : "Save Personal Mode Settings"}
    </button>
  </div>
</div>

<style>
  /* All styles now imported from global CSS:
     - .tab-panel from settings.css
     - .section from settings.css
     - .form-group from forms.css
     - .success-message from settings.css
     - .hint from forms.css
  */
</style>
