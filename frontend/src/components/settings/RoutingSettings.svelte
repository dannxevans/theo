<script>
  import { createEventDispatcher } from "svelte";
  import { setRoutingRule, deleteRoutingRule } from "../../lib/api";

  export let intents = [];
  export let rules = {};
  export let providers = [];

  const dispatch = createEventDispatcher();

  // Track fallback providers separately
  let fallbackProviders = {};

  // Initialize fallback providers from rules if they exist
  $: if (rules) {
    Object.keys(rules).forEach(intent => {
      if (typeof rules[intent] === 'object') {
        fallbackProviders[intent] = rules[intent].fallback_provider_id || "";
        rules[intent] = rules[intent].provider_id;
      }
    });
  }

  async function updateRule(intent, providerId) {
    if (!providerId) {
      await deleteRoutingRule(intent);
      delete rules[intent];
      delete fallbackProviders[intent];
    } else {
      const fallbackProviderId = fallbackProviders[intent] || null;
      await setRoutingRule(intent, providerId, fallbackProviderId);
      rules[intent] = providerId;
    }
    // Notify parent of rule update
    dispatch("ruleUpdate", { rules });
  }

  async function updateFallback(intent, fallbackProviderId) {
    const providerId = rules[intent];
    if (providerId) {
      await setRoutingRule(intent, providerId, fallbackProviderId || null);
      fallbackProviders[intent] = fallbackProviderId;
    }
    // Notify parent of rule update
    dispatch("ruleUpdate", { rules });
  }
</script>

<div class="tab-panel">
  <h2>Routing Rules</h2>
  <p class="subtitle">Assign specific AI providers to intents for customized routing. Action intents are not shown here as they have predefined routing.</p>

  <div class="routing-form">
    {#each intents.filter(i => i.enabled && !i.is_action) as intent}
      <div class="form-group">
        <label for="route-{intent.id}">{intent.name}</label>
        <div class="provider-selectors">
          <div class="provider-select">
            <label for="primary-{intent.id}" class="sublabel">Primary Provider</label>
            <select
              id="primary-{intent.id}"
              on:change={(e) => updateRule(intent.id, e.target.value)}
              value={rules[intent.id] || ""}
            >
              <option value="">Auto-select</option>
              {#each providers as p}
                <option value={p.id}>{p.name}</option>
              {/each}
            </select>
          </div>
          <div class="provider-select">
            <label for="fallback-{intent.id}" class="sublabel">Fallback Provider</label>
            <select
              id="fallback-{intent.id}"
              on:change={(e) => updateFallback(intent.id, e.target.value)}
              value={fallbackProviders[intent.id] || ""}
              disabled={!rules[intent.id]}
            >
              <option value="">Auto-select</option>
              {#each providers.filter(p => p.id !== rules[intent.id]) as p}
                <option value={p.id}>{p.name}</option>
              {/each}
            </select>
          </div>
        </div>
      </div>
    {/each}
  </div>
</div>

<style>
  /* All styles now imported from global CSS:
     - .tab-panel from settings.css
     - .routing-form from settings.css
     - .form-group from forms.css
  */

  .provider-selectors {
    display: flex;
    flex-direction: column;
    gap: 0.75rem;
    margin-top: 0.5rem;
  }

  .provider-select {
    display: flex;
    flex-direction: column;
    gap: 0.25rem;
  }

  .sublabel {
    font-size: 0.85rem;
    font-weight: 500;
    color: var(--text-secondary, #666);
    margin: 0;
  }

  .provider-select select {
    width: 100%;
  }

  .provider-select select:disabled {
    opacity: 0.5;
    cursor: not-allowed;
  }
</style>
