<script>
  import { onMount } from "svelte";
  import { getFeatureProvider, configureFeatureProvider } from "../../lib/api.js";

  // Supported providers
  const PROVIDERS = [
    {
      type: "openweather",
      name: "OpenWeather",
      description: "Weather forecasts and current conditions",
      apiKeyLabel: "OpenWeather API Key",
      signupUrl: "https://openweathermap.org/api",
      docsUrl: "https://openweathermap.org/current"
    },
    {
      type: "here",
      name: "HERE",
      description: "Routing, navigation, and traffic information",
      apiKeyLabel: "HERE API Key",
      appIdLabel: "HERE APP ID",
      requiresAppId: true,
      signupUrl: "https://developer.here.com/",
      docsUrl: "https://developer.here.com/documentation/routing-api/8.16.0/dev_guide/index.html"
    },
    {
      type: "porcupine",
      name: "Porcupine (Picovoice)",
      description: "Wake-word detection for Kiosk Mode",
      apiKeyLabel: "Porcupine Access Key",
      wakeWordLabel: "Wake Word",
      wakeWordPlaceholder: "e.g., Hey Theo, Computer, Jarvis",
      requiresWakeWord: true,
      signupUrl: "https://console.picovoice.ai/",
      docsUrl: "https://picovoice.ai/docs/porcupine/"
    }
  ];

  // Provider state
  let providerStates = {};
  let saveStatus = null;
  let loading = false;

  // Initialize provider states
  PROVIDERS.forEach(provider => {
    providerStates[provider.type] = {
      apiKey: "",
      appId: "",
      wakeWord: "",
      isEnabled: false,
      hasApiKey: false,
      hasAppId: false,
      hasWakeWord: false,
      showApiKey: false,
      showAppId: false,
      saving: false
    };
  });

  onMount(async () => {
    await loadProviders();
  });

  async function loadProviders() {
    loading = true;
    try {
      for (const provider of PROVIDERS) {
        const config = await getFeatureProvider(provider.type, true); // include_key=true to get wake_word
        if (config) {
          providerStates[provider.type].hasApiKey = config.has_api_key;
          providerStates[provider.type].hasAppId = config.has_app_id || false;
          providerStates[provider.type].hasWakeWord = config.has_wake_word || false;
          providerStates[provider.type].isEnabled = config.is_enabled;
          // Load actual wake_word value if present
          if (config.wake_word) {
            providerStates[provider.type].wakeWord = config.wake_word;
          }
        }
      }
    } catch (error) {
      console.error("Failed to load feature providers:", error);
    } finally {
      loading = false;
    }
  }

  async function saveProvider(providerType) {
    const state = providerStates[providerType];
    const provider = PROVIDERS.find(p => p.type === providerType);

    if (!state.apiKey && !state.hasApiKey) {
      alert(`Please enter your ${provider.name} API key`);
      return;
    }

    if (provider.requiresAppId && !state.appId && !state.hasAppId) {
      alert(`Please enter your ${provider.name} APP ID`);
      return;
    }

    if (provider.requiresWakeWord && !state.wakeWord && !state.hasWakeWord) {
      alert(`Please enter a wake word for ${provider.name}`);
      return;
    }

    state.saving = true;
    saveStatus = null;

    try {
      const config = {
        provider_name: provider.name,
        is_enabled: state.isEnabled
      };

      // Only include API key if it was entered/changed
      if (state.apiKey) {
        config.api_key = state.apiKey;
      }

      // Only include APP ID if it was entered/changed
      if (state.appId) {
        config.app_id = state.appId;
      }

      // Only include wake word if it was entered/changed
      if (state.wakeWord) {
        config.wake_word = state.wakeWord;
      }

      await configureFeatureProvider(providerType, config);

      // Update state
      if (state.apiKey) {
        state.hasApiKey = true;
        state.apiKey = ""; // Clear the input after saving
        state.showApiKey = false;
      }

      if (state.appId) {
        state.hasAppId = true;
        state.appId = ""; // Clear the input after saving
        state.showAppId = false;
      }

      if (state.wakeWord) {
        state.hasWakeWord = true;
        // Keep wake word visible (don't clear like API key)
      }

      saveStatus = `${provider.name} configuration saved!`;

      setTimeout(() => {
        saveStatus = null;
      }, 3000);
    } catch (error) {
      console.error("Failed to save provider:", error);
      alert(`Failed to save ${provider.name}: ${error.message}`);
    } finally {
      state.saving = false;
    }
  }

  function toggleApiKeyVisibility(providerType) {
    providerStates[providerType].showApiKey = !providerStates[providerType].showApiKey;
  }

  function toggleAppIdVisibility(providerType) {
    providerStates[providerType].showAppId = !providerStates[providerType].showAppId;
  }
</script>

<div class="tab-panel">
  <h2>Feature Providers</h2>
  <p class="subtitle">
    Configure external service providers for weather, traffic, and other features.
    API keys are stored securely and never shared.
  </p>

  {#if loading}
    <p>Loading providers...</p>
  {:else}
    {#each PROVIDERS as provider}
      <div class="provider-section">
        <div class="provider-header">
          <div class="provider-info">
            <h3>{provider.name}</h3>
            <p>{provider.description}</p>
          </div>
          <div class="provider-status">
            {#if providerStates[provider.type].hasApiKey}
              <span class="status-badge configured">Configured</span>
            {:else}
              <span class="status-badge not-configured">Not Configured</span>
            {/if}
          </div>
        </div>

        <div class="provider-config">
          {#if provider.requiresAppId}
            <div class="form-group">
              <label for="{provider.type}-app-id">{provider.appIdLabel}</label>
              <div class="api-key-input-group">
                {#if providerStates[provider.type].showAppId}
                  <input
                    id="{provider.type}-app-id"
                    type="text"
                    bind:value={providerStates[provider.type].appId}
                    placeholder={providerStates[provider.type].hasAppId ? "••••••••••••••••" : "Enter your APP ID"}
                    disabled={providerStates[provider.type].saving}
                  />
                {:else}
                  <input
                    id="{provider.type}-app-id"
                    type="password"
                    bind:value={providerStates[provider.type].appId}
                    placeholder={providerStates[provider.type].hasAppId ? "••••••••••••••••" : "Enter your APP ID"}
                    disabled={providerStates[provider.type].saving}
                  />
                {/if}
                <button
                  type="button"
                  class="toggle-visibility"
                  on:click={() => toggleAppIdVisibility(provider.type)}
                  disabled={providerStates[provider.type].saving}
                >
                  {providerStates[provider.type].showAppId ? "Hide" : "Show"}
                </button>
              </div>
            </div>
          {/if}

          <div class="form-group">
            <label for="{provider.type}-api-key">{provider.apiKeyLabel}</label>
            <div class="api-key-input-group">
              {#if providerStates[provider.type].showApiKey}
                <input
                  id="{provider.type}-api-key"
                  type="text"
                  bind:value={providerStates[provider.type].apiKey}
                  placeholder={providerStates[provider.type].hasApiKey ? "••••••••••••••••" : "Enter your API key"}
                  disabled={providerStates[provider.type].saving}
                />
              {:else}
                <input
                  id="{provider.type}-api-key"
                  type="password"
                  bind:value={providerStates[provider.type].apiKey}
                  placeholder={providerStates[provider.type].hasApiKey ? "••••••••••••••••" : "Enter your API key"}
                  disabled={providerStates[provider.type].saving}
                />
              {/if}
              <button
                type="button"
                class="toggle-visibility"
                on:click={() => toggleApiKeyVisibility(provider.type)}
                disabled={providerStates[provider.type].saving}
              >
                {providerStates[provider.type].showApiKey ? "Hide" : "Show"}
              </button>
            </div>
            <small class="form-help">
              Get your API key from <a href={provider.signupUrl} target="_blank" rel="noopener noreferrer">{provider.name}</a>
              {#if provider.docsUrl}
                • <a href={provider.docsUrl} target="_blank" rel="noopener noreferrer">Documentation</a>
              {/if}
            </small>
          </div>

          {#if provider.requiresWakeWord}
            <div class="form-group">
              <label for="{provider.type}-wake-word">{provider.wakeWordLabel}</label>
              <input
                id="{provider.type}-wake-word"
                type="text"
                bind:value={providerStates[provider.type].wakeWord}
                placeholder={provider.wakeWordPlaceholder || "Enter wake word"}
                disabled={providerStates[provider.type].saving}
              />
              <small class="form-help">
                Built-in keywords: Alexa, Americano, Blueberry, Bumblebee, Computer, Grapefruit, Grasshopper, Hey Google, Hey Siri, Jarvis, Okay Google, Picovoice, Porcupine, Terminator. Custom wake words like "Hey Theo" are supported - train your model at console.picovoice.ai and place the .ppn file in /frontend/public/wake/Hey-Theo_en_wasm_v4_0_0.ppn
              </small>
            </div>
          {/if}

          <div class="form-group">
            <label class="checkbox-label">
              <input
                type="checkbox"
                bind:checked={providerStates[provider.type].isEnabled}
                disabled={providerStates[provider.type].saving || !providerStates[provider.type].hasApiKey || (provider.requiresAppId && !providerStates[provider.type].hasAppId) || (provider.requiresWakeWord && !providerStates[provider.type].hasWakeWord)}
              />
              <span>Enable {provider.name} integration</span>
            </label>
            {#if !providerStates[provider.type].hasApiKey || (provider.requiresAppId && !providerStates[provider.type].hasAppId) || (provider.requiresWakeWord && !providerStates[provider.type].hasWakeWord)}
              <small class="form-help">Configure credentials first to enable</small>
            {/if}
          </div>

          <button
            class="save-button"
            on:click={() => saveProvider(provider.type)}
            disabled={providerStates[provider.type].saving}
          >
            {providerStates[provider.type].saving ? "Saving..." : "Save Configuration"}
          </button>
        </div>
      </div>
    {/each}
  {/if}

  {#if saveStatus}
    <div class="save-status success">{saveStatus}</div>
  {/if}
</div>

<style>
  .tab-panel {
    padding: 2rem;
    max-width: 900px;
  }

  h2 {
    margin: 0 0 0.5rem 0;
    font-size: 1.75rem;
    font-weight: 600;
  }

  .subtitle {
    color: #6b7280;
    margin: 0 0 2rem 0;
    font-size: 0.95rem;
  }

  .provider-section {
    background: #f9fafb;
    border: 1px solid #e5e7eb;
    border-radius: 8px;
    padding: 1.5rem;
    margin-bottom: 1.5rem;
  }

  .provider-header {
    display: flex;
    justify-content: space-between;
    align-items: flex-start;
    margin-bottom: 1.5rem;
  }

  .provider-info h3 {
    margin: 0 0 0.25rem 0;
    font-size: 1.25rem;
    font-weight: 600;
  }

  .provider-info p {
    margin: 0;
    color: #6b7280;
    font-size: 0.9rem;
  }

  .status-badge {
    display: inline-block;
    padding: 0.25rem 0.75rem;
    border-radius: 12px;
    font-size: 0.8rem;
    font-weight: 500;
  }

  .status-badge.configured {
    background: #d1fae5;
    color: #065f46;
  }

  .status-badge.not-configured {
    background: #fee2e2;
    color: #991b1b;
  }

  .provider-config {
    border-top: 1px solid #e5e7eb;
    padding-top: 1.5rem;
  }

  .form-group {
    margin-bottom: 1.25rem;
  }

  .form-group label {
    display: block;
    margin-bottom: 0.5rem;
    font-weight: 500;
    font-size: 0.9rem;
    color: #374151;
  }

  .form-group input[type="text"]:not(.api-key-input-group input) {
    width: 100%;
    padding: 0.625rem;
    border: 1px solid #d1d5db;
    border-radius: 6px;
    font-size: 0.9rem;
  }

  .form-group input[type="text"]:focus {
    outline: none;
    border-color: #3b82f6;
    box-shadow: 0 0 0 3px rgba(59, 130, 246, 0.1);
  }

  .form-group input[type="text"]:disabled {
    background: #f3f4f6;
    cursor: not-allowed;
  }

  .api-key-input-group {
    display: flex;
    gap: 0.5rem;
  }

  .api-key-input-group input {
    flex: 1;
    padding: 0.625rem;
    border: 1px solid #d1d5db;
    border-radius: 6px;
    font-size: 0.9rem;
    font-family: monospace;
  }

  .api-key-input-group input:focus {
    outline: none;
    border-color: #3b82f6;
    box-shadow: 0 0 0 3px rgba(59, 130, 246, 0.1);
  }

  .api-key-input-group input:disabled {
    background: #f3f4f6;
    cursor: not-allowed;
  }

  .toggle-visibility {
    padding: 0.625rem 1rem;
    background: #fff;
    border: 1px solid #d1d5db;
    border-radius: 6px;
    font-size: 0.875rem;
    font-weight: 500;
    cursor: pointer;
    white-space: nowrap;
  }

  .toggle-visibility:hover:not(:disabled) {
    background: #f9fafb;
  }

  .toggle-visibility:disabled {
    cursor: not-allowed;
    opacity: 0.5;
  }

  .form-help {
    display: block;
    margin-top: 0.375rem;
    font-size: 0.8rem;
    color: #6b7280;
  }

  .form-help a {
    color: #3b82f6;
    text-decoration: none;
  }

  .form-help a:hover {
    text-decoration: underline;
  }

  .checkbox-label {
    display: flex;
    align-items: center;
    gap: 0.5rem;
    cursor: pointer;
    font-weight: normal;
  }

  .checkbox-label input[type="checkbox"] {
    width: 18px;
    height: 18px;
    cursor: pointer;
  }

  .checkbox-label input[type="checkbox"]:disabled {
    cursor: not-allowed;
  }

  .save-button {
    padding: 0.75rem 1.5rem;
    background: #3b82f6;
    color: white;
    border: none;
    border-radius: 6px;
    font-size: 0.9rem;
    font-weight: 500;
    cursor: pointer;
  }

  .save-button:hover:not(:disabled) {
    background: #2563eb;
  }

  .save-button:disabled {
    background: #9ca3af;
    cursor: not-allowed;
  }

  .save-status {
    margin-top: 1rem;
    padding: 0.75rem 1rem;
    border-radius: 6px;
    font-size: 0.9rem;
    font-weight: 500;
  }

  .save-status.success {
    background: #d1fae5;
    color: #065f46;
    border: 1px solid #6ee7b7;
  }
</style>
