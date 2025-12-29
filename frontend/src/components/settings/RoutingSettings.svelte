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
  .tab-panel {
    max-width: 900px;
    margin: 0 auto;
  }

  h2 {
    margin-top: 0;
    margin-bottom: var(--space-2);
  }

  .subtitle {
    color: var(--text-secondary);
    font-size: var(--font-size-sm);
    margin-bottom: var(--space-4);
  }

  .routing-form {
    display: flex;
    flex-direction: column;
    gap: var(--space-4);
    background: var(--bg-tertiary);
    border: 1px solid var(--border-primary);
    border-radius: var(--radius-lg);
    padding: var(--space-5);
  }

  .form-group {
    margin-bottom: var(--space-4);
  }

  .form-group label {
    display: block;
    width: auto;
    margin-bottom: var(--space-1);
    font-weight: 600;
    color: var(--text-primary);
  }

  .form-group select {
    width: 100%;
    padding: var(--space-2);
    border: 1px solid var(--border-primary);
    border-radius: var(--radius-sm);
    background: var(--bg-primary);
    color: var(--text-primary);
  }

  .form-group select:focus {
    outline: none;
    border-color: var(--border-focus);
  }

  .form-group small {
    display: block;
    color: var(--text-tertiary);
    font-size: var(--font-size-xs);
    margin-top: var(--space-1);
  }
</style>
