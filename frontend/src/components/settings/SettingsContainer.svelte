<script>
  import { onMount } from "svelte";
  import PersonalActions from "../PersonalActions.svelte";
  import ServiceProviders from "../ServiceProviders.svelte";
  import RoutingSettings from "./RoutingSettings.svelte";
  import GeneralSettings from "./GeneralSettings.svelte";
  import IntentsSettings from "./IntentsSettings.svelte";
  import MemorySettings from "./MemorySettings.svelte";
  import AIProvidersSettings from "./AIProvidersSettings.svelte";
  import HealthMonitorSettings from "./HealthMonitorSettings.svelte";
  import WorkModeSettings from "./WorkModeSettings.svelte";
  import PersonalModeSettings from "./PersonalModeSettings.svelte";
  import AccountSettings from "./AccountSettings.svelte";
  import {
    getProviders,
    getIntents,
    getRoutingRules,
    getDebugFlag,
    getSystemPromptConfig,
    getMemories,
    listProviders,
    getProviderHealth,
    getModeSettings,
    getWorkSubtabConfig
  } from "../../lib/api";

  let providers = [];
  let intents = [];
  let rules = {};
  let debugEnabled = false;
  let advancedMode = false;
  let loaded = false;

  // Active tab state
  let activeCategory = "general"; // general, operating-modes, accounts, health
  let activeTab = "general"; // Changes based on category

  // Helper function to switch category and set default tab
  function switchCategory(category) {
    activeCategory = category;
    // Set default tab for each category
    switch (category) {
      case "general":
        activeTab = "general";
        break;
      case "operating-modes":
        activeTab = "personal";
        break;
      case "accounts":
        activeTab = "theo-account";
        break;
      case "health":
        activeTab = "health-monitor";
        break;
      default:
        activeTab = "general";
    }
  }

  // System prompt configuration state
  let systemPromptConfig = {
    persona_name: "THEO",
    tone: "professional, conversational, direct",
    style_rules: "- No em dashes\n- Be concise first, then detailed\n- Provide full working solutions when asked for code\n- Maintain a consistent persona regardless of model",
    custom_instructions: ""
  };

  // Mode configuration state
  let workModeSettings = {
    system_prompt_override: "",
    preferred_provider_id: null,
    tone: "professional"
  };
  let personalModeSettings = {
    system_prompt_override: "",
    preferred_provider_id: null,
    tone: "casual"
  };

  // Work mode subtab configuration state
  let codeSubtabConfig = {
    language: "servicenow_javascript",
    framework: "",
    additional_context: ""
  };
  let emailSubtabConfig = {
    tone: "professional",
    signature: ""
  };

  // Memory state
  let memories = [];
  let loadingMemories = false;
  let filterType = "all";

  // Provider state
  let providersList = [];
  let healthSummary = {};

  // Health Monitor state
  let healthData = {
    ai_providers: [],
    m365_integration: { connected: false },
    service_providers: []
  };

  async function load() {
    providers = await getProviders();
    intents = await getIntents();
    rules = await getRoutingRules();
    const flag = await getDebugFlag();
    debugEnabled = flag === true || flag === "true" || flag?.enabled === true;

    // Load advanced mode from localStorage
    const storedAdvanced = localStorage.getItem("theo.advancedMode");
    advancedMode = storedAdvanced === "true";

    // Load system prompt config
    try {
      const config = await getSystemPromptConfig();
      systemPromptConfig = {
        persona_name: config.persona_name || "THEO",
        tone: config.tone || "professional, conversational, direct",
        style_rules: config.style_rules || "- No em dashes\n- Be concise first, then detailed\n- Provide full working solutions when asked for code\n- Maintain a consistent persona regardless of model",
        custom_instructions: config.custom_instructions || ""
      };
    } catch (e) {
      console.warn("Failed to load system prompt config:", e);
    }

    // Load memories and providers
    await loadMemories();
    await loadProvidersList();

    // Load mode settings
    try {
      const workSettings = await getModeSettings("work");
      if (workSettings && Object.keys(workSettings).length > 0) {
        workModeSettings = {
          system_prompt_override: workSettings.system_prompt_override || "",
          preferred_provider_id: workSettings.preferred_provider_id || null,
          tone: workSettings.tone || "professional"
        };
      }

      const personalSettings = await getModeSettings("personal");
      if (personalSettings && Object.keys(personalSettings).length > 0) {
        personalModeSettings = {
          system_prompt_override: personalSettings.system_prompt_override || "",
          preferred_provider_id: personalSettings.preferred_provider_id || null,
          tone: personalSettings.tone || "casual"
        };
      }
    } catch (e) {
      console.warn("Failed to load mode settings:", e);
    }

    // Load work subtab configs
    try {
      const codeConfig = await getWorkSubtabConfig("code");
      if (codeConfig && codeConfig.config_json) {
        const parsed = JSON.parse(codeConfig.config_json);
        codeSubtabConfig = {
          language: parsed.language || "servicenow_javascript",
          framework: parsed.framework || "",
          additional_context: parsed.additional_context || ""
        };
      }

      const emailConfig = await getWorkSubtabConfig("email");
      if (emailConfig && emailConfig.config_json) {
        const parsed = JSON.parse(emailConfig.config_json);
        emailSubtabConfig = {
          tone: parsed.tone || "professional",
          signature: parsed.signature || ""
        };
      }
    } catch (e) {
      console.warn("Failed to load work subtab configs:", e);
    }

    loaded = true;
  }

  async function loadMemories() {
    try {
      loadingMemories = true;
      const params = filterType !== "all" ? { type: filterType } : {};
      memories = await getMemories(params);
    } catch (err) {
      console.error("Failed to load memories", err);
    } finally {
      loadingMemories = false;
    }
  }

  async function loadProvidersList() {
    try {
      providersList = await listProviders();
      healthSummary = await getProviderHealth();
    } catch (e) {
      console.error("Failed to load providers:", e);
    }
  }

  async function loadHealthData() {
    try {
      const token = localStorage.getItem("auth_token");
      const response = await fetch("/api/health/overview", {
        headers: {
          "Authorization": `Bearer ${token}`
        }
      });

      if (!response.ok) {
        throw new Error("Failed to load health data");
      }

      healthData = await response.json();
    } catch (err) {
      console.error("Failed to load health data:", err);
    }
  }

  $: {
    if (filterType !== undefined) {
      loadMemories();
    }
  }

  onMount(async () => {
    await load();
    await loadHealthData();

    // Set up auto-refresh for health data (every 30 seconds)
    const healthRefreshInterval = setInterval(loadHealthData, 30000);

    // Cleanup on unmount
    return () => {
      if (healthRefreshInterval) {
        clearInterval(healthRefreshInterval);
      }
    };
  });
</script>

<div class="settings">
  <h1>Settings</h1>

  <!-- Category Navigation -->
  <div class="category-tabs">
    <button
      class="category-tab"
      class:active={activeCategory === "general"}
      on:click={() => switchCategory("general")}
    >
      General
    </button>
    <button
      class="category-tab"
      class:active={activeCategory === "operating-modes"}
      on:click={() => switchCategory("operating-modes")}
    >
      Operating Modes
    </button>
    <button
      class="category-tab"
      class:active={activeCategory === "accounts"}
      on:click={() => switchCategory("accounts")}
    >
      Accounts
    </button>
    <button
      class="category-tab"
      class:active={activeCategory === "health"}
      on:click={() => switchCategory("health")}
    >
      Health
    </button>
  </div>

  <!-- Sub-tab Navigation -->
  <div class="tabs">
    {#if activeCategory === "general"}
      <button class="tab" class:active={activeTab === "general"} on:click={() => activeTab = "general"}>
        General
      </button>
      <button class="tab" class:active={activeTab === "intents"} on:click={() => activeTab = "intents"}>
        Intents
      </button>
      <button class="tab" class:active={activeTab === "routing"} on:click={() => activeTab = "routing"}>
        Routing
      </button>
      <button class="tab" class:active={activeTab === "memory"} on:click={() => activeTab = "memory"}>
        Memory
      </button>
    {/if}

    {#if activeCategory === "operating-modes"}
      <button class="tab" class:active={activeTab === "personal"} on:click={() => activeTab = "personal"}>
        Personal
      </button>
      <button class="tab" class:active={activeTab === "work"} on:click={() => activeTab = "work"}>
        Work
      </button>
    {/if}

    {#if activeCategory === "accounts"}
      <button class="tab" class:active={activeTab === "theo-account"} on:click={() => activeTab = "theo-account"}>
        THEO Account
      </button>
      <button class="tab" class:active={activeTab === "ai-providers"} on:click={() => activeTab = "ai-providers"}>
        AI Providers
      </button>
      <button class="tab" class:active={activeTab === "integrations"} on:click={() => activeTab = "integrations"}>
        Integrations
      </button>
      <button class="tab" class:active={activeTab === "service-providers"} on:click={() => activeTab = "service-providers"}>
        Service Providers
      </button>
    {/if}

    {#if activeCategory === "health"}
      <button class="tab" class:active={activeTab === "health-monitor"} on:click={() => activeTab = "health-monitor"}>
        Health Monitor
      </button>
    {/if}
  </div>

  <!-- Tab Content -->
  <div class="tab-content">
    {#if activeTab === "general"}
      <GeneralSettings bind:systemPromptConfig />
    {/if}

    {#if activeTab === "intents"}
      <IntentsSettings bind:intents on:reload={() => load()} />
    {/if}

    {#if activeTab === "routing"}
      <RoutingSettings {intents} {rules} {providers} on:ruleUpdate={(e) => { rules = e.detail.rules }} />
    {/if}

    {#if activeTab === "memory"}
      <MemorySettings
        bind:memories
        bind:loadingMemories
        bind:filterType
        on:reload={() => loadMemories()}
      />
    {/if}

    {#if activeTab === "ai-providers"}
      <AIProvidersSettings
        bind:providersList
        bind:healthSummary
        on:reload={() => loadProvidersList()}
      />
    {/if}

    {#if activeTab === "health-monitor"}
      <HealthMonitorSettings
        {healthData}
        {debugEnabled}
        {advancedMode}
        on:reload={() => loadHealthData()}
      />
    {/if}

    {#if activeTab === "work"}
      <WorkModeSettings
        bind:workModeSettings
        bind:codeSubtabConfig
        bind:emailSubtabConfig
        {providers}
      />
    {/if}

    {#if activeTab === "personal"}
      <PersonalModeSettings bind:personalModeSettings {providers} />
    {/if}

    {#if activeTab === "theo-account"}
      <AccountSettings />
    {/if}

    {#if activeTab === "integrations"}
      <div class="tab-panel">
        <PersonalActions />
      </div>
    {/if}

    {#if activeTab === "service-providers"}
      <div class="tab-panel">
        <ServiceProviders />
      </div>
    {/if}
  </div>
</div>

<style>
  .settings {
    padding: 0;
    height: 100%;
    display: flex;
    flex-direction: column;
  }

  h1 {
    padding: var(--space-5) var(--space-6);
    margin: 0;
    border-bottom: 1px solid var(--border-primary);
    background: var(--bg-tertiary);
    font-size: var(--font-size-2xl);
    color: var(--text-primary);
  }

  .category-tabs {
    display: flex;
    background: var(--bg-secondary);
    border-bottom: 1px solid var(--border-primary);
    padding: 0 var(--space-6);
    gap: var(--space-2);
  }

  .category-tab {
    padding: var(--space-4) var(--space-6);
    border: none;
    background: transparent;
    cursor: pointer;
    font-size: var(--font-size-base);
    font-weight: 600;
    color: var(--text-secondary);
    border-bottom: 3px solid transparent;
    transition: all 0.2s;
  }

  .category-tab:hover {
    color: var(--text-primary);
    background: var(--bg-hover);
  }

  .category-tab.active {
    color: var(--theo-blue);
    border-bottom-color: var(--theo-blue);
    background: var(--bg-tertiary);
  }

  .tabs {
    display: flex;
    background: var(--bg-tertiary);
    border-bottom: 2px solid var(--border-primary);
    padding: 0 var(--space-6);
    gap: var(--space-1);
  }

  .tab {
    padding: var(--space-3) var(--space-5);
    border: none;
    background: transparent;
    cursor: pointer;
    font-size: var(--font-size-sm);
    font-weight: 500;
    color: var(--text-secondary);
    border-bottom: 3px solid transparent;
    transition: all 0.2s;
  }

  .tab:hover {
    color: var(--text-primary);
    background: var(--bg-hover);
  }

  .tab.active {
    color: var(--theo-blue);
    border-bottom-color: var(--theo-blue);
    background: var(--bg-primary);
  }

  .tab-content {
    flex: 1;
    overflow-y: auto;
    padding: var(--space-6);
  }
</style>
