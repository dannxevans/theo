<svelte:head>
  <link rel="stylesheet" href="/style.css" />
</svelte:head>

<script>
  
  import DOMPurify from "dompurify";
  import {
  streamMessage,
  fetchSessionSummary,
  rememberMemory,
  forgetMemory,
  deleteSessionApi,
  getSessionMessages,
  getProviders
} from "../lib/api.js";
  import { marked } from "marked";
  import Prism from "prismjs";
  import "prismjs/components/prism-python";
  import "prismjs/themes/prism-tomorrow.css";
  import { tick } from "svelte";

  export let sessionId;

  function generateUUID() {
    if (typeof crypto !== "undefined" && crypto.randomUUID) {
      return crypto.randomUUID();
    }
    return "xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx".replace(/[xy]/g, function (c) {
      const r = (Math.random() * 16) | 0;
      const v = c === "x" ? r : (r & 0x3) | 0x8;
      return v.toString(16);
    });
  }

  let input = "";
  let messages = [];
  let loading = false;
  let error = null;
  let summary = "";

  let memoryKey = "";
  let memoryStatus = null;
  let showMemory = false;
  
  let forcedProvider = ""; // empty = automatic routing
  let providers = [];

  import { onMount } from "svelte";
  onMount(async () => {
    try {
      const result = await getProviders();
      // Only enabled, non-mock providers
      providers = (result || [])
        .filter(p => p.enabled && p.type !== "mock")
        .map(p => ({ id: p.id, name: p.name }));
    } catch (e) {
      // If fails, leave providers empty
    }
  });

  // Reload messages whenever session changes
  $: if (sessionId) {
    loadSessionMessages(sessionId);
  }

  if (!sessionId) {
    sessionId = generateUUID();
  }

  let streaming = false;

  // Raw token buffer (not rendered directly)
  let streamBuffer = "";

  // Text actually shown to the user during streaming
  let streamedText = "";

  function renderMarkdown(text) {
    if (!text) return "";

    marked.setOptions({
      langPrefix: "language-"
    });

    const rawHtml = marked.parse(text);

    return DOMPurify.sanitize(rawHtml, {
      ALLOWED_TAGS: [
        "h1","h2","h3","h4","h5","h6",
        "p","strong","em","ul","ol","li",
        "pre","code","blockquote",
        "a","span","br"
      ],
      ALLOWED_ATTR: {
        "a": ["href", "title", "target", "rel"],
        "span": ["class"],
        "code": ["class"]
      }
    });
  }

  function enhanceCodeBlocks() {
    const blocks = document.querySelectorAll(".markdown pre");

    blocks.forEach((pre) => {
      const code = pre.querySelector("code");
      if (!code) return;

      // Ensure Prism language class exists
      if (
        !code.className.includes("language-") &&
        Prism.languages.python
      ) {
        code.classList.add("language-python");
      }

      // Highlight THIS code block explicitly
      Prism.highlightElement(code);

      // Avoid duplicating copy buttons
      if (pre.querySelector(".copy-btn")) return;

      const button = document.createElement("button");
      button.textContent = "Copy";
      button.className = "copy-btn";

      button.onclick = () => {
        navigator.clipboard.writeText(code.innerText);
        button.textContent = "Copied!";
        setTimeout(() => (button.textContent = "Copy"), 1200);
      };

      pre.style.position = "relative";
      button.style.position = "absolute";
      button.style.top = "6px";
      button.style.right = "6px";

      pre.appendChild(button);
    });
  }

  async function loadSummary() {
    try {
      const res = await fetchSessionSummary(sessionId);
      summary = res.summary || "";
    } catch {
      summary = "";
    }
  }

  async function loadSessionMessages(id) {
    try {
      loading = true;
      error = null;

      const turns = await getSessionMessages(id);

      messages = turns.map(t => ({
        role: t.role,
        text: t.content
      }));

      await tick();
      scrollToBottom();
      enhanceCodeBlocks();
      loadSummary();
    } catch (e) {
      error = "Failed to load messages";
    } finally {
      loading = false;
    }
  }

  async function rememberSummary() {
    if (!memoryKey || !summary) return;

    try {
      await rememberMemory(memoryKey, summary);
      memoryStatus = `Saved memory under key "${memoryKey}"`;
      memoryKey = "";
    } catch (e) {
      memoryStatus = e.message;
    }
  }

  async function forgetSummary() {
    if (!memoryKey) return;

    try {
      await forgetMemory(memoryKey);
      memoryStatus = `Forgot memory "${memoryKey}"`;
      memoryKey = "";
    } catch (e) {
      memoryStatus = e.message;
    }
  }

  async function deleteSession() {
    const confirmed = confirm("Delete this chat? This cannot be undone.");
    if (!confirmed) return;

    try {
      await deleteSessionApi(sessionId);
    } catch (e) {
      alert("Failed to delete session");
      return;
    }

    // Clear UI immediately
    messages = [];
    summary = "";
    error = null;
    forcedProvider = "";

    // IMPORTANT: App.svelte owns session switching
    // Force a full reload so App.svelte reselects a session cleanly
    window.location.reload();
  }

  async function submit() {
    if (!input || loading) return;

    const userText = input;
    input = "";
    error = null;

    messages = [...messages, { role: "user", text: userText }];
    loading = true;
    streaming = true;
    streamedText = "";
    streamBuffer = "";

    try {
      await streamMessage({
        sessionId,
        text: userText,
        forcedProvider,
        onToken(token) {
          streamedText += token;
          scrollToBottom();
        },
        async onEnd(meta) {
          messages = [
            ...messages,
            {
              role: "assistant",
              text: streamedText,
              provider: meta?.provider,
              model: meta?.model,
              task: meta?.task,
              fallback_reason: meta?.fallback_reason
            }
          ];

          streamedText = "";
          streaming = false;
          loading = false;

          await tick();
          scrollToBottom();
          enhanceCodeBlocks();
          loadSummary();
        },
        onError(err) {
          error = err?.message || "Streaming failed";
          streaming = false;
          loading = false;
        }
      });
    } catch (e) {
      error = e.message || "Streaming failed";
      streaming = false;
      loading = false;
    }
  }

  function scrollToBottom() {
    const container = document.querySelector(".messages");
    if (container) {
      container.scrollTop = container.scrollHeight;
    }
  }
</script>

<div class="chat">
    <div class="chat-inner">
      <div class="session-bar">
        <div class="session-title">
          <strong>Chat</strong>
          {#if forcedProvider}
            <span class="provider-badge">{forcedProvider}</span>
          {/if}
        </div>

        <div class="session-actions">
          <button class="btn-secondary" on:click={() => showMemory = !showMemory}>
            Memory
          </button>
          <button class="btn-danger" on:click={deleteSession}>
            Delete
          </button>
        </div>
      </div>

      {#if showMemory}
        <div class="summary">
          <strong>Session summary</strong>

          {#if summary}
            <p>{summary}</p>
          {:else}
            <p style="opacity:0.6">No summary yet for this chat.</p>
          {/if}

          <div class="memory-controls">
            <input
              placeholder="memory key (e.g. preferences.writing)"
              bind:value={memoryKey}
            />
            <button on:click={rememberSummary} disabled={!summary || !memoryKey}>
              Remember
            </button>
            <button on:click={forgetSummary} disabled={!memoryKey}>
              Forget
            </button>
          </div>

          {#if memoryStatus}
            <div class="memory-status">{memoryStatus}</div>
          {/if}
        </div>
      {/if}

      <div class="chat-main">
        <div class="messages">
          {#each messages as m}
            <div class="message {m.role}">
              <div class="bubble">
                <strong>{m.role === "user" ? "Me" : "Theo"}:</strong>
                {#if m.role === "assistant"}
                  <div class="markdown">
                    {@html renderMarkdown(m.text)}
                  </div>
                {:else}
                  <div style="white-space: pre-wrap;">
                    {m.text}
                  </div>
                {/if}
                {#if m.provider}
                  <small>
                    via {m.provider}
                    {#if m.model}
                      · {m.model}
                    {/if}
                    {#if m.task}
                      ({m.task})
                    {/if}
                  </small>
                {/if}

                {#if m.fallback_reason}
                  <small style="color:#a33">
                    {m.fallback_reason}
                  </small>
                {/if}
              </div>
            </div>
          {/each}

          {#if streaming}
            <div class="message assistant">
              <div class="bubble">
                <strong>Theo:</strong>
                <div style="white-space: pre-wrap;">
                  {streamedText || "…"}
                </div>
                <small>streaming</small>
              </div>
            </div>
          {/if}
        </div>
        <div class="input">
          <input
            bind:value={input}
            placeholder="Talk to THEO"
            on:keydown={(e) => e.key === "Enter" && submit()}
          />

          {#if streaming}
            <button class="btn-danger" disabled>
              Streaming…
            </button>
          {:else}
            <button class="btn-primary" on:click={submit} disabled={loading}>
              {loading ? "Thinking…" : "Send"}
            </button>
          {/if}

          <select
            class="provider-select"
            bind:value={forcedProvider}
            title="Provider"
          >
            <option value="">Auto</option>
            <option value="mock">Mock</option>
            {#each providers as p}
              <option value={p.id}>{p.name}</option>
            {/each}
          </select>
        </div>
      </div>
    </div>
  </div>

<style>

  :global(.markdown h1) {
    font-size: 1.5rem;
    margin: 1rem 0 0.5rem;
  }

  :global(.markdown h2) {
    font-size: 1.25rem;
    margin: 1rem 0 0.4rem;
  }

  :global(.markdown h3) {
    font-size: 1.1rem;
    margin: 0.75rem 0 0.3rem;
  }

  :global(.markdown p) {
    margin: 0.5rem 0;
  }

  :global(.markdown ul) {
    padding-left: 1.25rem;
  }

  :global(.markdown pre) {
    background: #0d1117;
    color: #e6edf3;
    padding: 0.75rem;
    overflow-x: auto;
    border-radius: 6px;
  }

  :global(.markdown code) {
    font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, "Liberation Mono", monospace;
  }

  :global(.copy-btn) {
    background: #1f6feb;
    color: #fff;
    border: none;
    font-size: 0.7rem;
    padding: 0.25rem 0.5rem;
    border-radius: 4px;
    cursor: pointer;
  }

  :global(.copy-btn:hover) {
    background: #388bfd;
  }  
</style>