<script>
  import { createEventDispatcher } from "svelte";
  import { setRoutingRule, deleteRoutingRule } from "../../lib/api";

  export let intents = [];
  export let rules = {};
  export let providers = [];

  const dispatch = createEventDispatcher();

  async function updateRule(intent, providerId) {
    if (!providerId) {
      await deleteRoutingRule(intent);
      delete rules[intent];
    } else {
      await setRoutingRule(intent, providerId);
      rules[intent] = providerId;
    }
    // Notify parent of rule update
    dispatch("ruleUpdate", { rules });
  }
</script>

<div class="tab-panel">
  <h2>Routing Rules</h2>
  <p class="subtitle">Assign specific AI providers to intents for customized routing.</p>

  <div class="routing-form">
    {#each intents.filter(i => i.enabled) as intent}
      <div class="form-group">
        <label for="route-{intent.id}">{intent.name}</label>
        <select
          id="route-{intent.id}"
          on:change={(e) => updateRule(intent.id, e.target.value)}
          value={rules[intent.id] || ""}
        >
          <option value="">Auto-select</option>
          {#each providers as p}
            <option value={p.id}>{p.name}</option>
          {/each}
        </select>
        <small>Select a specific provider or leave as auto-select</small>
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
</style>
