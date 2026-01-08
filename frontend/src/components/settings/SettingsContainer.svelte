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
  import ApiKeysSettings from "./ApiKeysSettings.svelte";
  import UserManagement from "./UserManagement.svelte";
  import ThemeSettings from "./ThemeSettings.svelte";
  import VoiceSettings from "./VoiceSettings.svelte";
  import FeatureProvidersSettings from "./FeatureProvidersSettings.svelte";
  import RoutinesSettings from "./RoutinesSettings.svelte";
  import DebugConsole from "./DebugConsole.svelte";
  import DatabaseAuditSettings from "./DatabaseAuditSettings.svelte";
  import {
    getProviders,
    getIntents,
    getRoutingRules,
    getDebugFlag,
    getMessageDebugFlag,
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
  let messageDebugEnabled = false;
  let advancedMode = false;
  let loaded = false;

  // Check if user is admin (for User Management tab)
  let isAdmin = false;
  try {
    const user = JSON.parse(localStorage.getItem('user') || '{}');
    isAdmin = user.is_admin || false;
  } catch (e) {
    console.error('Failed to parse user from localStorage:', e);
  }

  // Active tab state
  let activeCategory = "general"; // general, operating-modes, system, health
  let activeTab = "my-account"; // Changes based on category
  let openDropdown = null; // Track which dropdown is open

  // Helper function to switch category and optionally set a specific tab
  function switchCategory(category, specificTab = null) {
    activeCategory = category;

    // If a specific tab is provided, use it; otherwise set default tab for category
    if (specificTab) {
      activeTab = specificTab;
    } else {
      // Set default tab for each category
      switch (category) {
        case "general":
          activeTab = "my-account";
          break;
        case "operating-modes":
          activeTab = "personal";
          break;
        case "system":
          activeTab = "general";
          break;
        case "health":
          activeTab = "health-monitor";
          break;
        default:
          activeTab = "my-account";
      }
    }
    // Close dropdowns when switching category
    openDropdown = null;
  }

  // Toggle dropdown open/close
  function toggleDropdown(category) {
    if (openDropdown === category) {
      openDropdown = null;
    } else {
      openDropdown = category;
    }
  }

  // Select a tab and close dropdown
  function selectTab(tab) {
    activeTab = tab;
    openDropdown = null;
  }

  // Close dropdown when clicking outside
  function handleClickOutside(event) {
    if (!event.target.closest('.category-dropdown')) {
      openDropdown = null;
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
    additional_context: "",
    preferred_provider_id: null
  };
  let emailSubtabConfig = {
    tone: "professional",
    signature: "",
    preferred_provider_id: null
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

    const messageDebugFlag = await getMessageDebugFlag();
    messageDebugEnabled = messageDebugFlag === true || messageDebugFlag === "true" || messageDebugFlag?.enabled === true;

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
          additional_context: parsed.additional_context || "",
          preferred_provider_id: parsed.preferred_provider_id || null
        };
      }

      const emailConfig = await getWorkSubtabConfig("email");
      if (emailConfig && emailConfig.config_json) {
        const parsed = JSON.parse(emailConfig.config_json);
        emailSubtabConfig = {
          tone: parsed.tone || "professional",
          signature: parsed.signature || "",
          preferred_provider_id: parsed.preferred_provider_id || null
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

    // Add click outside listener
    document.addEventListener('click', handleClickOutside);

    // Cleanup on unmount
    return () => {
      if (healthRefreshInterval) {
        clearInterval(healthRefreshInterval);
      }
      document.removeEventListener('click', handleClickOutside);
    };
  });
</script>

<div class="settings">
  <h1>Settings</h1>

  <!-- Category Navigation with Dropdowns -->
  <div class="category-tabs">
    <!-- General Dropdown -->
    <div class="category-dropdown" class:open={openDropdown === "general"}>
      <button
        class="category-tab"
        class:active={activeCategory === "general"}
        on:click={() => toggleDropdown("general")}
      >
        General
        <span class="dropdown-arrow">{openDropdown === "general" ? "▲" : "▼"}</span>
      </button>
      {#if openDropdown === "general"}
        <div class="dropdown-menu">
          <button class="dropdown-item" class:active={activeTab === "my-account"} on:click={() => switchCategory("general", "my-account")}>
            My Account
          </button>
          <button class="dropdown-item" class:active={activeTab === "memory"} on:click={() => switchCategory("general", "memory")}>
            Memory
          </button>
          <button class="dropdown-item" class:active={activeTab === "voice"} on:click={() => switchCategory("general", "voice")}>
            Voice
          </button>
          <button class="dropdown-item" class:active={activeTab === "theme"} on:click={() => switchCategory("general", "theme")}>
            Theme
          </button>
          <button class="dropdown-item" class:active={activeTab === "routines"} on:click={() => switchCategory("general", "routines")}>
            Routines
          </button>
        </div>
      {/if}
    </div>

    <!-- Operating Modes Dropdown -->
    <div class="category-dropdown" class:open={openDropdown === "operating-modes"}>
      <button
        class="category-tab"
        class:active={activeCategory === "operating-modes"}
        on:click={() => toggleDropdown("operating-modes")}
      >
        Operating Modes
        <span class="dropdown-arrow">{openDropdown === "operating-modes" ? "▲" : "▼"}</span>
      </button>
      {#if openDropdown === "operating-modes"}
        <div class="dropdown-menu">
          <button class="dropdown-item" class:active={activeTab === "personal"} on:click={() => switchCategory("operating-modes", "personal")}>
            Personal Mode
          </button>
          <button class="dropdown-item" class:active={activeTab === "work"} on:click={() => switchCategory("operating-modes", "work")}>
            Work Mode
          </button>
        </div>
      {/if}
    </div>

    <!-- System Dropdown (Admin Only) -->
    {#if isAdmin}
    <div class="category-dropdown" class:open={openDropdown === "system"}>
      <button
        class="category-tab"
        class:active={activeCategory === "system"}
        on:click={() => toggleDropdown("system")}
      >
        System
        <span class="dropdown-arrow">{openDropdown === "system" ? "▲" : "▼"}</span>
      </button>
      {#if openDropdown === "system"}
        <div class="dropdown-menu">
          <button class="dropdown-item" class:active={activeTab === "general"} on:click={() => switchCategory("system", "general")}>
            General Settings
          </button>
          <button class="dropdown-item" class:active={activeTab === "user-management"} on:click={() => switchCategory("system", "user-management")}>
            User Management
          </button>
          <button class="dropdown-item" class:active={activeTab === "ai-providers"} on:click={() => switchCategory("system", "ai-providers")}>
            AI Providers
          </button>
          <button class="dropdown-item" class:active={activeTab === "intents"} on:click={() => switchCategory("system", "intents")}>
            LLM Routing Intents
          </button>
          <button class="dropdown-item" class:active={activeTab === "routing"} on:click={() => switchCategory("system", "routing")}>
            Routing Rules
          </button>
          <button class="dropdown-item" class:active={activeTab === "integrations"} on:click={() => switchCategory("system", "integrations")}>
            Integrations
          </button>
          <button class="dropdown-item" class:active={activeTab === "service-providers"} on:click={() => switchCategory("system", "service-providers")}>
            Service Providers
          </button>
          <button class="dropdown-item" class:active={activeTab === "feature-providers"} on:click={() => switchCategory("system", "feature-providers")}>
            Feature Providers
          </button>
        </div>
      {/if}
    </div>
    {/if}

    <!-- Health Dropdown (Admin Only) -->
    {#if isAdmin}
    <div class="category-dropdown" class:open={openDropdown === "health"}>
      <button
        class="category-tab"
        class:active={activeCategory === "health"}
        on:click={() => toggleDropdown("health")}
      >
        Health
        <span class="dropdown-arrow">{openDropdown === "health" ? "▲" : "▼"}</span>
      </button>
      {#if openDropdown === "health"}
        <div class="dropdown-menu">
          <button class="dropdown-item" class:active={activeTab === "health-monitor"} on:click={() => switchCategory("health", "health-monitor")}>
            Health Monitor
          </button>
          <button class="dropdown-item" class:active={activeTab === "database-audit"} on:click={() => switchCategory("health", "database-audit")}>
            Database Audit
          </button>
          <button class="dropdown-item" class:active={activeTab === "debug-console"} on:click={() => switchCategory("health", "debug-console")}>
            Debug Console
          </button>
        </div>
      {/if}
    </div>
    {/if}
  </div>

  <!-- Current Page Breadcrumb -->
  <div class="page-breadcrumb">
    <span class="breadcrumb-category">{activeCategory === "general" ? "General" : activeCategory === "operating-modes" ? "Operating Modes" : activeCategory === "system" ? "System" : "Health"}</span>
    <span class="breadcrumb-separator">›</span>
    <span class="breadcrumb-page">
      {#if activeTab === "general"}General Settings{/if}
      {#if activeTab === "my-account"}My Account{/if}
      {#if activeTab === "intents"}LLM Routing Intents{/if}
      {#if activeTab === "routing"}Routing Rules{/if}
      {#if activeTab === "memory"}Memory{/if}
      {#if activeTab === "voice"}Voice{/if}
      {#if activeTab === "theme"}Theme{/if}
      {#if activeTab === "routines"}Routines{/if}
      {#if activeTab === "feature-providers"}Feature Providers{/if}
      {#if activeTab === "personal"}Personal Mode{/if}
      {#if activeTab === "work"}Work Mode{/if}
      {#if activeTab === "user-management"}User Management{/if}
      {#if activeTab === "ai-providers"}AI Providers{/if}
      {#if activeTab === "integrations"}Integrations{/if}
      {#if activeTab === "service-providers"}Service Providers{/if}
      {#if activeTab === "health-monitor"}Health Monitor{/if}
      {#if activeTab === "database-audit"}Database Audit{/if}
      {#if activeTab === "debug-console"}Debug Console{/if}
    </span>
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

    {#if activeTab === "voice"}
      <VoiceSettings />
    {/if}

    {#if activeTab === "theme"}
      <ThemeSettings />
    {/if}

    {#if activeTab === "routines"}
      <RoutinesSettings />
    {/if}

    {#if activeTab === "feature-providers"}
      <FeatureProvidersSettings />
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
        {messageDebugEnabled}
        {advancedMode}
        on:reload={() => loadHealthData()}
      />
    {/if}

    {#if activeTab === "database-audit"}
      <DatabaseAuditSettings />
    {/if}

    {#if activeTab === "debug-console"}
      <DebugConsole />
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

    {#if activeTab === "my-account"}
      <AccountSettings />
    {/if}

    {#if activeTab === "user-management"}
      <UserManagement />
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

  .category-dropdown {
    position: relative;
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
    display: flex;
    align-items: center;
    gap: var(--space-2);
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

  .dropdown-arrow {
    font-size: 10px;
    opacity: 0.7;
    transition: transform 0.2s;
  }

  .dropdown-menu {
    position: absolute;
    top: 100%;
    left: 0;
    background: var(--bg-tertiary);
    border: 1px solid var(--border-primary);
    border-radius: var(--radius-md);
    box-shadow: var(--shadow-lg);
    min-width: 200px;
    z-index: 1000;
    margin-top: var(--space-1);
    overflow: hidden;
  }

  .dropdown-item {
    width: 100%;
    padding: var(--space-3) var(--space-4);
    border: none;
    background: transparent;
    cursor: pointer;
    font-size: var(--font-size-sm);
    font-weight: 500;
    color: var(--text-secondary);
    text-align: left;
    transition: all 0.15s;
    border-left: 3px solid transparent;
  }

  .dropdown-item:hover {
    background: var(--bg-hover);
    color: var(--text-primary);
  }

  .dropdown-item.active {
    background: var(--bg-active);
    color: var(--theo-blue);
    border-left-color: var(--theo-blue);
    font-weight: 600;
  }

  .page-breadcrumb {
    display: flex;
    align-items: center;
    gap: var(--space-2);
    padding: var(--space-3) var(--space-6);
    background: var(--bg-tertiary);
    border-bottom: 2px solid var(--border-primary);
    font-size: var(--font-size-sm);
  }

  .breadcrumb-category {
    color: var(--text-tertiary);
    font-weight: 500;
  }

  .breadcrumb-separator {
    color: var(--text-tertiary);
    font-weight: 300;
  }

  .breadcrumb-page {
    color: var(--text-primary);
    font-weight: 600;
  }

  .tab-content {
    flex: 1;
    overflow-y: auto;
    padding: var(--space-6);
  }
</style>
