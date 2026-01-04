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
</div>

<style>
  /* All styles now imported from global CSS:
     - .tab-panel from settings.css
     - .section from settings.css
     - .form-group from forms.css
     - .form-actions from settings.css
     - .save-status from settings.css
  */
</style>
