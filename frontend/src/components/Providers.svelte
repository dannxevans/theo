<script>
  import { onMount } from "svelte";
  import { listProviders, upsertProvider, deleteProvider } from "../lib/api.js";

  let providers = [];
  let error = null;

  // Form state
  let id = "";
  let name = "";
  let type = "";
  let base_url = "";
  let model = "";
  let api_key = "";
  let enabled = true;

  async function loadProviders() {
    try {
      providers = await listProviders();
    } catch (e) {
      error = e.message;
    }
  }

  async function saveProvider() {
    error = null;

    if (!id || !name || !type) {
      error = "id, name and type are required";
      return;
    }

    if (type === "anthropic" && !model) {
      error = "Model is required for Anthropic providers";
      return;
    }

    try {
      await upsertProvider({
        id,
        name,
        type,
        base_url,
        model,
        api_key,
        enabled
      });

      // Reset form
      id = "";
      name = "";
      type = "";
      base_url = "";
      model = "";
      api_key = "";
      enabled = true;

      await loadProviders();
    } catch (e) {
      error = e.message;
    }
  }

  async function removeProvider(providerId) {
    if (!confirm(`Delete provider ${providerId}?`)) return;

    try {
      await deleteProvider(providerId);
      await loadProviders();
    } catch (e) {
      error = e.message;
    }
  }

  function editProvider(p) {
    id = p.id;
    name = p.name;
    type = p.type;
    base_url = p.base_url || "";
    model = p.model || "";
    api_key = ""; // never prefill secrets
    enabled = p.enabled;
  }

  onMount(loadProviders);
</script>

<div class="providers">
  <h2>Providers</h2>

  {#if error}
    <div class="error">{error}</div>
  {/if}

  <table>
    <thead>
      <tr>
        <th>ID</th>
        <th>Name</th>
        <th>Type</th>
        <th>Base URL</th>
        <th>Model</th>
        <th>Enabled</th>
        <th></th>
      </tr>
    </thead>
    <tbody>
      {#each providers as p}
        <tr>
          <td>{p.id}</td>
          <td>{p.name}</td>
          <td>{p.type}</td>
          <td>{p.base_url || "-"}</td>
          <td>{p.model || "-"}</td>
          <td>{p.enabled ? "yes" : "no"}</td>
          <td>
            <button on:click={() => editProvider(p)}>Edit</button>
            <button on:click={() => removeProvider(p.id)}>Delete</button>
          </td>
        </tr>
      {/each}
    </tbody>
  </table>

  <h3>Add / Edit Provider</h3>

  <div class="form">
    <input placeholder="id (e.g. claude-sonnet)" bind:value={id} />
    <input placeholder="name (Claude Sonnet)" bind:value={name} />
    <input placeholder="type (anthropic | openai | mock)" bind:value={type} />
    <input placeholder="base url (optional)" bind:value={base_url} />
    <input
      placeholder="model (required for anthropic, e.g. claude-sonnet-4-5-20250929)"
      bind:value={model}
    />
    <input placeholder="api key" type="password" bind:value={api_key} />

    <label>
      <input type="checkbox" bind:checked={enabled} />
      Enabled
    </label>

    <button
      on:click={saveProvider}
      disabled={type === "anthropic" && !model}
    >
      Save provider
    </button>
  </div>
</div>

<style>
  .providers {
    border: 1px solid #ddd;
    padding: 1rem;
  }

  table {
    width: 100%;
    border-collapse: collapse;
    margin-bottom: 1rem;
  }

  th, td {
    border: 1px solid #ddd;
    padding: 0.4rem;
    text-align: left;
    font-size: 0.9rem;
  }

  .form {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 0.5rem;
  }

  .form input {
    padding: 0.4rem;
  }

  .error {
    color: red;
    margin-bottom: 0.5rem;
  }
</style>