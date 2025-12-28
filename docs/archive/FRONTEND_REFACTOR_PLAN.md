# Frontend Refactoring Plan - Settings.svelte

**Date:** December 28, 2025
**Status:** Ready to Start
**File:** `frontend/src/components/Settings.svelte` (2,777 lines)

## Component Breakdown

Based on analysis of Settings.svelte, here are the components to extract:

### 1. GeneralSettings.svelte (~70 lines)
- **Lines:** 876-945
- **Responsibility:** System prompt configuration (persona, tone, style rules)
- **State:** `systemPromptConfig`, `savingPrompt`, `promptSaveStatus`
- **Functions:** `saveSystemPrompt()`
- **API Calls:** `updateSystemPromptConfig()`

### 2. IntentsSettings.svelte (~140 lines)
- **Lines:** 946-1085
- **Responsibility:** Intent management (create, edit, delete intents)
- **State:** `intents`, intent form state
- **Functions:** Intent CRUD operations
- **API Calls:** `getIntents()`, `createIntent()`, `updateIntent()`, `deleteIntent()`

### 3. RoutingSettings.svelte (~27 lines)
- **Lines:** 1086-1112
- **Responsibility:** Intent-to-provider routing rules
- **State:** `rules`, `providers`
- **Functions:** Routing rule management
- **API Calls:** `getRoutingRules()`, `setRoutingRule()`, `deleteRoutingRule()`

### 4. MemorySettings.svelte (~139 lines)
- **Lines:** 1113-1251
- **Responsibility:** Memory/preference management
- **State:** Memories list
- **Functions:** Memory CRUD, pin/unpin
- **API Calls:** `getMemories()`, `createMemory()`, `deleteMemory()`, `pinMemory()`

### 5. AIProvidersSettings.svelte (~101 lines)
- **Lines:** 1252-1352
- **Responsibility:** AI provider configuration
- **State:** `providers`, provider form state
- **Functions:** Provider CRUD, enable/disable
- **API Calls:** `listProviders()`, `upsertProvider()`, `deleteProvider()`

### 6. HealthMonitorSettings.svelte (~257 lines)
- **Lines:** 1353-1609
- **Responsibility:** System health monitoring dashboard
- **State:** Health data, metrics
- **Functions:** Health data loading, M365 testing
- **API Calls:** `getProviderHealth()`, health endpoints

### 7. WorkModeSettings.svelte (~154 lines)
- **Lines:** 1610-1763
- **Responsibility:** Work mode configuration with subtabs
- **State:** `workModeSettings`, subtab configs
- **Functions:** Mode settings save, subtab management
- **API Calls:** `updateModeSettings()`, `updateWorkSubtabConfig()`

### 8. PersonalModeSettings.svelte (~59 lines)
- **Lines:** 1764-1822
- **Responsibility:** Personal mode configuration
- **State:** `personalModeSettings`
- **Functions:** Personal mode save
- **API Calls:** `updateModeSettings()`

### 9. AccountSettings.svelte (~92 lines)
- **Lines:** 1823-1914
- **Responsibility:** Account management, password change
- **State:** Password change form state
- **Functions:** Password change
- **API Calls:** `changePassword()`

### 10. IntegrationsSettings.svelte (~6 lines)
- **Lines:** 1915-1920
- **Responsibility:** Placeholder for M365/other integrations
- **State:** None currently
- **Note:** May need expansion or removal

### 11. ServiceProvidersSettings.svelte (remaining lines)
- **Lines:** 1921+
- **Responsibility:** External service provider management
- **Uses:** Existing `ServiceProviders.svelte` component
- **State:** Passed through to child component

### 12. SettingsContainer.svelte (new, ~200 lines)
- **Responsibility:** Main container, tab management, state coordination
- **Components:** All above components
- **State:** `activeCategory`, `activeTab`, shared state
- **Functions:** Tab switching, state loading on mount

## Implementation Strategy

### Phase 1: Infrastructure (Estimated: 1-2 hours)
1. Create directory structure
2. Create base container with tab navigation
3. Set up shared state management approach

### Phase 2: Extract Components (Estimated: 3-4 hours)
Extract in this order (simple → complex):
1. RoutingSettings (simplest, 27 lines)
2. GeneralSettings (70 lines, simple form)
3. PersonalModeSettings (59 lines)
4. AccountSettings (92 lines)
5. MemorySettings (139 lines)
6. IntentsSettings (140 lines)
7. AIProvidersSettings (101 lines)
8. WorkModeSettings (154 lines, has subtabs)
9. HealthMonitorSettings (257 lines, most complex)
10. ServiceProvidersSettings (wrapper)
11. IntegrationsSettings (placeholder)

### Phase 3: Integration & Testing (Estimated: 1-2 hours)
1. Wire up all components in container
2. Test all functionality
3. Fix any state synchronization issues
4. Verify no regressions

## Technical Approach

### State Management
**Option A: Props + Events (Recommended)**
- Container holds all state
- Pass state and event handlers as props to children
- Children emit events for state changes
- Simple, explicit, easy to debug

**Option B: Svelte Stores**
- Create settings stores
- Components subscribe to stores
- More complex but better for deeply nested state

**Decision:** Use Option A for simplicity

### Component Template
```svelte
<script>
  export let config;         // Input prop
  export let saving = false; // State prop
  export let onSave;         // Event handler

  // Component-local state if needed
  let localState = {};

  function handleSave() {
    onSave(config);
  }
</script>

<div class="tab-panel">
  <h2>Title</h2>
  <!-- Content -->
  <button on:click={handleSave} disabled={saving}>
    {saving ? "Saving..." : "Save"}
  </button>
</div>

<style>
  /* Component-scoped styles */
</style>
```

### File Structure
```
frontend/src/components/settings/
├── SettingsContainer.svelte     # Main container
├── GeneralSettings.svelte
├── IntentsSettings.svelte
├── RoutingSettings.svelte
├── MemorySettings.svelte
├── AIProvidersSettings.svelte
├── HealthMonitorSettings.svelte
├── WorkModeSettings.svelte
├── PersonalModeSettings.svelte
├── AccountSettings.svelte
├── IntegrationsSettings.svelte
└── ServiceProvidersSettings.svelte
```

## Success Criteria
- [ ] All 12 components created
- [ ] No component exceeds 300 lines
- [ ] SettingsContainer < 250 lines
- [ ] All existing functionality preserved
- [ ] All settings load correctly
- [ ] All save operations work
- [ ] Tab navigation works
- [ ] No console errors
- [ ] Styles preserved

## Risks & Mitigation
**Risk:** State synchronization issues between components
**Mitigation:** Keep state in container, pass as props

**Risk:** Breaking existing functionality
**Mitigation:** Extract incrementally, test after each component

**Risk:** CSS conflicts or missing styles
**Mitigation:** Keep component-scoped styles, test visually

## Next Steps
1. Create SettingsContainer with basic structure
2. Extract simplest component first (RoutingSettings)
3. Test it works
4. Continue with remaining components
5. Final integration testing

---

**Status:** Ready to implement
**Priority:** HIGH
**Estimated Total Time:** 6-8 hours
