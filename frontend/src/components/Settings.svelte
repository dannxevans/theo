<script>
  import { onMount } from "svelte";
  import {
    getProviders,
    getRoutingRules,
    setRoutingRule,
    deleteRoutingRule,
    getDebugFlag,
    setDebugFlag
  } from "../lib/api";

  let providers = [];
  let rules = {};
  let intents = ["general", "coding", "reasoning"];
  let debugEnabled = false;
  let loaded = false;
  let savingDebug = false;

  async function load() {
    providers = await getProviders();
    rules = await getRoutingRules();
    const flag = await getDebugFlag();
    debugEnabled = flag === true || flag === "true" || flag?.enabled === true;
    loaded = true;
  }

  async function updateRule(intent, providerId) {
    if (!providerId) {
      await deleteRoutingRule(intent);
      delete rules[intent];
    } else {
      await setRoutingRule(intent, providerId);
      rules[intent] = providerId;
    }
  }

  async function toggleDebug(value) {
    savingDebug = true;
    await setDebugFlag(value);
    debugEnabled = value;
    savingDebug = false;
  }

  onMount(load);
</script>

<div class="settings">
  <h2>Debugging</h2>

  <div class="rule">
    <label>Debug logs</label>
    <input
      type="checkbox"
      checked={debugEnabled}
      disabled={savingDebug}
      on:change={(e) => toggleDebug(e.target.checked)}
    />
  </div>

  <h2>Routing Rules</h2>

  {#each intents as intent}
    <div class="rule">
      <label>{intent}</label>

      <select
        on:change={(e) => updateRule(intent, e.target.value)}
        value={rules[intent] || ""}
      >
        <option value="">Auto</option>

        {#each providers as p}
          <option value={p.id}>
            {p.name}
          </option>
        {/each}
      </select>
    </div>
  {/each}
</div>

<style>
  .settings {
    padding: 16px;
  }

  .rule {
    display: flex;
    align-items: center;
    gap: 12px;
    margin-bottom: 12px;
  }

  label {
    width: 100px;
    font-weight: 500;
  }

  select {
    flex: 1;
    padding: 6px;
  }

  input[type="checkbox"] {
    transform: scale(1.2);
    cursor: pointer;
  }
</style>