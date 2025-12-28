<script>
  
  import DOMPurify from "dompurify";
  import {
  streamMessage,
  fetchSessionSummary,
  deleteSessionApi,
  getSessionMessages,
  getProviders,
  exportSession,
  forkSession,
  generateSessionTitle,
  approveConfirmation,
  rejectConfirmation
} from "../lib/api.js";
  import { marked } from "marked";
  import Prism from "prismjs";
  import "prismjs/components/prism-python";
  import "prismjs/themes/prism-tomorrow.css";
  import { tick, afterUpdate } from "svelte";

  export let sessionId;
  export let currentMode = "personal";
  export let activeWorkSubtab = "conversation";

  function switchWorkSubtab(subtab) {
    activeWorkSubtab = subtab;
    // Save to localStorage
    localStorage.setItem("theo.activeWorkSubtab", subtab);
    // Dispatch event to notify parent
    window.dispatchEvent(new CustomEvent("workSubtabChanged", { detail: { subtab } }));
  }

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

  /**
   * Format model display: "Name · Type · Routing"
   * Examples: "GPT-4o · OpenAI · General", "Sonnet-4.5 · Anthropic · Coding"
   */
  function formatModelDisplay(provider, model, taskType) {
    // Extract friendly name from model or provider
    let modelName = "";
    let providerType = "";

    // Special cases for non-AI responses (don't show model badge)
    if (provider === "memory" || provider === "error" || provider === "action_router") {
      return null;
    }

    // Determine provider type based on model string
    if (model && (model.includes("gpt") || model.includes("o1") || model.includes("o3"))) {
      providerType = "OpenAI";
      // Extract model version from full model name
      if (model.includes("gpt-5.2")) modelName = "GPT-5.2";
      else if (model.includes("gpt-5")) modelName = "GPT-5";
      else if (model.includes("gpt-4o")) modelName = "GPT-4o";
      else if (model.includes("gpt-4-turbo")) modelName = "GPT-4 Turbo";
      else if (model.includes("gpt-4")) modelName = "GPT-4";
      else if (model.includes("gpt-3.5")) modelName = "GPT-3.5";
      else if (model.includes("o3")) modelName = "O3";
      else if (model.includes("o1")) modelName = "O1";
      else modelName = model;
    } else if (model && (model.includes("claude") || model.includes("opus") || model.includes("sonnet") || model.includes("haiku"))) {
      providerType = "Anthropic";
      // Extract model version from full model name
      if (model.includes("opus-4-5")) modelName = "Opus-4.5";
      else if (model.includes("sonnet-4-5")) modelName = "Sonnet-4.5";
      else if (model.includes("haiku-4-5")) modelName = "Haiku-4.5";
      else if (model.includes("opus-4")) modelName = "Opus-4";
      else if (model.includes("sonnet-4")) modelName = "Sonnet-4";
      else if (model.includes("haiku-4")) modelName = "Haiku-4";
      else if (model.includes("opus")) modelName = "Opus";
      else if (model.includes("sonnet")) modelName = "Sonnet";
      else if (model.includes("haiku")) modelName = "Haiku";
      else modelName = model;
    } else {
      // Fallback - try to determine from provider field
      if (provider && (provider.includes("openai") || provider.includes("gpt"))) {
        providerType = "OpenAI";
        modelName = model || provider || "Unknown";
      } else if (provider && (provider.includes("claude") || provider.includes("anthropic"))) {
        providerType = "Anthropic";
        modelName = model || provider || "Unknown";
      } else {
        // Complete fallback for unknown providers
        providerType = provider || "Unknown";
        modelName = model || provider || "Unknown";
      }
    }

    // Format task type (capitalize first letter)
    const routing = taskType
      ? taskType.charAt(0).toUpperCase() + taskType.slice(1).replace(/_/g, " ")
      : "General";

    return `${modelName} · ${providerType} · ${routing}`;
  }

  let input = "";
  let messages = [];
  let loading = false;
  let error = null;
  let summary = "";

  let forcedModel = ""; // empty = automatic routing (model id)
  let providers = [];
  let advancedMode = false;
  let usedProviders = new Set(); // Track providers used in this session

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

    // Load advanced mode from localStorage
    const storedAdvanced = localStorage.getItem("theo.advancedMode");
    advancedMode = storedAdvanced === "true";

    // Listen for advanced mode changes
    window.addEventListener("advancedModeChanged", (e) => {
      advancedMode = e.detail.enabled;
    });
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

  // Auto-scroll after every update
  afterUpdate(() => {
    scrollToBottom();
  });

  function renderMarkdown(text) {
    if (!text) return "";

    // Auto-linkify plain URLs that aren't already in markdown link format
    const urlRegex = /(?<![(\[])(https?:\/\/[^\s<]+[^<.,:;"')\]\s])/g;
    text = text.replace(urlRegex, (url) => {
      return `[${url}](${url})`;
    });

    marked.setOptions({
      langPrefix: "language-"
    });

    const rawHtml = marked.parse(text);

    // Post-process to add target="_blank" and rel="noopener noreferrer" to all links
    const tempDiv = document.createElement('div');
    tempDiv.innerHTML = DOMPurify.sanitize(rawHtml, {
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

    // Add target="_blank" and rel to all links
    const links = tempDiv.querySelectorAll('a');
    links.forEach(link => {
      link.setAttribute('target', '_blank');
      link.setAttribute('rel', 'noopener noreferrer');
    });

    return tempDiv.innerHTML;
  }

  function formatTimestamp(timestamp) {
    if (!timestamp) return "";

    const msgDate = new Date(timestamp);
    const now = new Date();
    const today = new Date(now.getFullYear(), now.getMonth(), now.getDate());
    const yesterday = new Date(today);
    yesterday.setDate(yesterday.getDate() - 1);
    const msgDay = new Date(msgDate.getFullYear(), msgDate.getMonth(), msgDate.getDate());

    // Format time as "9:14am"
    let hours = msgDate.getHours();
    const minutes = msgDate.getMinutes().toString().padStart(2, '0');
    const ampm = hours >= 12 ? 'pm' : 'am';
    hours = hours % 12 || 12;
    const timeStr = `${hours}:${minutes}${ampm}`;

    // Check if today or yesterday
    if (msgDay.getTime() === today.getTime()) {
      return `Today at ${timeStr}`;
    } else if (msgDay.getTime() === yesterday.getTime()) {
      return `Yesterday at ${timeStr}`;
    } else {
      // Format as DD/MM/YY
      const day = msgDate.getDate().toString().padStart(2, '0');
      const month = (msgDate.getMonth() + 1).toString().padStart(2, '0');
      const year = msgDate.getFullYear().toString().slice(-2);
      return `${day}/${month}/${year} at ${timeStr}`;
    }
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
        text: t.content,
        provider: t.provider,
        model: t.model,
        task_type: t.task_type,
        created_at: t.created_at,
        metadata: t.metadata || null
      }));

      // Track unique providers used in this session
      usedProviders = new Set(
        messages
          .filter(m => m.provider)
          .map(m => m.provider)
      );

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
    forcedModel = "";

    // IMPORTANT: App.svelte owns session switching
    // Force a full reload so App.svelte reselects a session cleanly
    window.location.reload();
  }

  async function handleExport(format) {
    try {
      await exportSession(sessionId, format);
    } catch (e) {
      alert(`Failed to export: ${e.message}`);
    }
  }

  async function handleFork() {
    try {
      const result = await forkSession(sessionId);
      alert(`Conversation forked! New session ID: ${result.session_id}`);
      // Reload to show the new session in the sidebar
      window.location.reload();
    } catch (e) {
      alert(`Failed to fork: ${e.message}`);
    }
  }

  async function submit() {
    if (!input || loading) return;

    const userText = input;
    input = "";
    error = null;

    messages = [...messages, { role: "user", text: userText, created_at: new Date().toISOString() }];
    loading = true;
    streaming = true;
    streamedText = "";
    streamBuffer = "";

    try {
      await streamMessage({
        sessionId,
        text: userText,
        forcedProvider: forcedModel,
        workSubtab: currentMode === "work" ? activeWorkSubtab : null,
        onToken(token) {
          streamedText += token;
          scrollToBottom();
        },
        async onEnd(meta) {
          // Add provider to used providers set
          if (meta?.provider) {
            usedProviders = new Set([...usedProviders, meta.provider]);
          }

          streamedText = "";
          streaming = false;
          loading = false;

          // Reload messages from database to get metadata (including confirmation data)
          await loadSessionMessages(sessionId);

          await tick();
          scrollToBottom();
          enhanceCodeBlocks();
          loadSummary();

          // Generate title after first assistant response
          const assistantMessages = messages.filter(m => m.role === "assistant");
          if (assistantMessages.length === 1) {
            // This is the first response, generate a title
            try {
              const result = await generateSessionTitle(sessionId);
              // Dispatch event to App.svelte to refresh sessions list
              window.dispatchEvent(new CustomEvent("sessionTitleGenerated", {
                detail: { sessionId, title: result.title }
              }));
            } catch (e) {
              console.warn("Failed to generate session title:", e);
            }
          }
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

  async function handleApprove(confirmationId) {
    try {
      await approveConfirmation(confirmationId);

      // Update the message metadata to show approved status
      messages = messages.map(m => {
        if (m.metadata && m.metadata.confirmation_id === confirmationId) {
          return {
            ...m,
            metadata: { ...m.metadata, approved: true, rejected: false }
          };
        }
        return m;
      });

      // Reload messages to get any updates
      await loadSessionMessages(sessionId);
    } catch (e) {
      alert("Failed to approve: " + e.message);
    }
  }

  async function handleReject(confirmationId) {
    try {
      await rejectConfirmation(confirmationId);

      // Update the message metadata to show rejected status
      messages = messages.map(m => {
        if (m.metadata && m.metadata.confirmation_id === confirmationId) {
          return {
            ...m,
            metadata: { ...m.metadata, approved: false, rejected: true }
          };
        }
        return m;
      });

      // Reload messages to get any updates
      await loadSessionMessages(sessionId);
    } catch (e) {
      alert("Failed to reject: " + e.message);
    }
  }

  function getTimeRemaining(expiresAt) {
    if (!expiresAt) return "";

    const now = new Date();
    const expiry = new Date(expiresAt);
    const diff = expiry - now;

    if (diff < 0) return "expired";

    const hours = Math.floor(diff / (1000 * 60 * 60));
    const minutes = Math.floor((diff % (1000 * 60 * 60)) / (1000 * 60));

    if (hours > 0) {
      return `${hours}h ${minutes}m`;
    }
    return `${minutes}m`;
  }
</script>

<div class="chat">
    <div class="chat-inner">
      <div class="session-bar">
        <div class="session-title">
          <strong>Chat</strong>
          {#if currentMode === "work"}
            <span class="official-badge">OFFICIAL</span>
          {/if}
          {#if forcedModel}
            <span class="provider-badge forced">Forced: {forcedModel}</span>
          {:else if usedProviders.size > 0}
            <span class="providers-used">
              {#each [...usedProviders] as provider}
                <span class="provider-badge">{provider}</span>
              {/each}
            </span>
          {/if}
        </div>

        <div class="session-actions">
          {#if advancedMode}
            <button class="btn-secondary" on:click={() => handleExport("json")} title="Export as JSON">
              Export JSON
            </button>
            <button class="btn-secondary" on:click={() => handleExport("markdown")} title="Export as Markdown">
              Export MD
            </button>
            <button class="btn-secondary" on:click={handleFork} title="Fork this conversation">
              Fork
            </button>
          {/if}
          <button class="btn-danger" on:click={deleteSession}>
            Delete
          </button>
        </div>
      </div>

      <!-- Work Mode Sub-Tabs (only visible in work mode) -->
      {#if currentMode === "work"}
        <div class="work-subtabs">
          <button
            class="subtab"
            class:active={activeWorkSubtab === "conversation"}
            on:click={() => switchWorkSubtab("conversation")}
          >
            💬 Conversation
          </button>
          <button
            class="subtab"
            class:active={activeWorkSubtab === "email"}
            on:click={() => switchWorkSubtab("email")}
          >
            ✉️ Email Rewrites
          </button>
          <button
            class="subtab"
            class:active={activeWorkSubtab === "code"}
            on:click={() => switchWorkSubtab("code")}
          >
            💻 Code Development
          </button>
        </div>
      {/if}

      <div class="chat-main">
        <div class="messages">
          {#if messages.length === 0 && !loading && !streaming}
            <div class="message assistant">
              <div class="bubble">
                <div class="message-header">
                  <strong>Theo</strong>
                </div>
                <div>Hello, what do you want to do today?</div>
              </div>
            </div>
          {/if}

          {#each messages as m}
            <div class="message {m.role}">
              <div class="bubble">
                <div class="message-header">
                  <strong>{m.role === "user" ? "Me" : "Theo"}</strong>
                  {#if m.created_at}
                    <span class="timestamp">- {formatTimestamp(m.created_at)}</span>
                  {/if}
                </div>

                {#if m.role === "assistant"}
                  <div class="markdown">
                    {@html renderMarkdown(m.text)}
                  </div>

                  {#if m.metadata && m.metadata.requires_confirmation}
                    <div class="confirmation-widget {m.metadata.approved ? 'approved' : ''} {m.metadata.rejected ? 'rejected' : ''}">
                      {#if m.metadata.approved || m.metadata.rejected}
                        <!-- Completed state: show clean status -->
                        <div class="confirmation-header">
                          <span class="confirmation-icon">
                            {#if m.metadata.action_category === "calendar"}
                              📅
                            {:else if m.metadata.action_category === "email"}
                              ✉️
                            {:else}
                              ⚡
                            {/if}
                            {(m.metadata.action_category || 'ACTION').toUpperCase()}
                          </span>
                        </div>
                        <div class="confirmation-result">
                          {#if m.metadata.approved}
                            {m.metadata.confirmation_message.replace('?', '.').replace('Add ', '')}
                          {:else}
                            {#if m.metadata.confirmation_message.includes("'")}
                              {#if m.metadata.action_category === "email"}
                                '{m.metadata.confirmation_message.split("'")[1]}' was not sent.
                              {:else}
                                '{m.metadata.confirmation_message.split("'")[1]}' was not added to your calendar.
                              {/if}
                            {:else}
                              Action was not performed.
                            {/if}
                          {/if}
                        </div>
                        <div class="confirmation-status-final {m.metadata.approved ? 'approved' : 'rejected'}">
                          {m.metadata.approved ? 'Approved' : 'Rejected'}
                        </div>
                      {:else}
                        <!-- Pending state: show approval buttons -->
                        <div class="confirmation-header">
                          <span class="confirmation-icon">
                            {#if m.metadata.action_category === "calendar"}
                              📅
                            {:else if m.metadata.action_category === "email"}
                              ✉️
                            {:else}
                              ⚡
                            {/if}
                            {(m.metadata.action_category || 'ACTION').toUpperCase()} Approval
                          </span>
                          <span class="confirmation-expires">
                            {#if m.metadata.expires_at}
                              Expires in {getTimeRemaining(m.metadata.expires_at)}
                            {/if}
                          </span>
                        </div>
                        <div class="confirmation-message">
                          {m.metadata.confirmation_message}
                        </div>
                        <div class="confirmation-actions">
                          <button
                            class="btn-approve"
                            on:click={() => handleApprove(m.metadata.confirmation_id)}
                          >
                            ✓ Approve
                          </button>
                          <button
                            class="btn-reject"
                            on:click={() => handleReject(m.metadata.confirmation_id)}
                          >
                            × Reject
                          </button>
                        </div>
                      {/if}
                    </div>
                  {/if}

                  {#if m.provider}
                    {@const formattedModel = formatModelDisplay(m.provider, m.model, m.task_type)}
                    {@const isActionRouter = m.provider === 'action_router'}
                    {@const isError = m.provider === 'error'}
                    {@const formattedAction = m.task_type
                      ? m.task_type.charAt(0).toUpperCase() + m.task_type.slice(1).replace(/_/g, " ")
                      : "Action"}
                    <div class="bubble-footer">
                      {#if formattedModel}
                        <span class="provider-badge provider-badge-ai">
                          via {formattedModel}
                        </span>
                      {:else if isActionRouter}
                        <span class="provider-badge provider-badge-action">
                          via Action Router · {formattedAction}
                        </span>
                      {:else if isError}
                        <span class="provider-badge provider-badge-error">
                          Error · {formattedAction}
                        </span>
                      {:else}
                        <span class="provider-badge">
                          via {m.provider}
                          {#if m.model}
                            · {m.model}
                          {/if}
                          {#if m.task_type}
                            ({m.task_type})
                          {/if}
                        </span>
                      {/if}
                      {#if m.fallback_reason}
                        <span class="fallback-reason">
                          {m.fallback_reason}
                        </span>
                      {/if}
                    </div>
                  {/if}
                {:else}
                  <div style="white-space: pre-wrap;">
                    {m.text}
                  </div>
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
            bind:value={forcedModel}
            title="Model"
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

  :global(.markdown a) {
    color: #1f6feb;
    text-decoration: underline;
    cursor: pointer;
  }

  :global(.markdown a:hover) {
    color: #388bfd;
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

  .confirmation-widget {
    margin-top: 1rem;
    padding: 1rem;
    background: #f8f9fa;
    border: 2px solid #007bff;
    border-radius: 8px;
  }

  .confirmation-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 0.75rem;
  }

  .confirmation-icon {
    font-weight: 600;
    font-size: 0.9rem;
    color: #007bff;
  }

  .confirmation-expires {
    font-size: 0.85rem;
    color: #6c757d;
  }

  .confirmation-message {
    margin-bottom: 1rem;
    font-size: 0.95rem;
    color: #495057;
  }

  .confirmation-actions {
    display: flex;
    gap: 0.75rem;
  }

  .btn-approve,
  .btn-reject {
    flex: 1;
    padding: 0.5rem 1rem;
    border: none;
    border-radius: 6px;
    font-weight: 600;
    cursor: pointer;
    transition: all 0.2s;
  }

  .btn-approve {
    background: #28a745;
    color: white;
  }

  .btn-approve:hover:not(:disabled) {
    background: #218838;
  }

  .btn-reject {
    background: #dc3545;
    color: white;
  }

  .btn-reject:hover:not(:disabled) {
    background: #c82333;
  }

  .btn-approve:disabled,
  .btn-reject:disabled {
    opacity: 0.5;
    cursor: not-allowed;
  }

  .confirmation-status {
    margin-top: 0.75rem;
    padding: 0.5rem;
    border-radius: 4px;
    text-align: center;
    font-weight: 600;
  }

  .confirmation-status.approved {
    background: #d4edda;
    color: #155724;
  }

  .confirmation-status.rejected {
    background: #f8d7da;
    color: #721c24;
  }

  /* Completed state styling */
  .confirmation-widget.approved {
    border-color: #28a745;
    background: #f0f9f4;
  }

  .confirmation-widget.rejected {
    border-color: #dc3545;
    background: #fef5f6;
  }

  .confirmation-result {
    margin-bottom: 0.75rem;
    font-size: 0.95rem;
    color: #495057;
    line-height: 1.5;
  }

  .confirmation-status-final {
    padding: 0.5rem;
    border-radius: 4px;
    text-align: center;
    font-weight: 600;
    font-size: 0.9rem;
  }

  .confirmation-status-final.approved {
    background: #d4edda;
    color: #155724;
  }

  .confirmation-status-final.rejected {
    background: #f8d7da;
    color: #721c24;
  }

  /* Provider Badge Styling */
  .provider-badge {
    font-size: 0.75rem;
    padding: 0.25rem 0.5rem;
    border-radius: 4px;
    display: inline-block;
  }

  /* AI responses - baby blue */
  .provider-badge-ai {
    background: #DBEAFE;
    color: #1E40AF;
  }

  /* Action router responses - amber */
  .provider-badge-action {
    background: #FEF3C7;
    color: #92400E;
  }

  /* Error responses - red */
  .provider-badge-error {
    background: #FEE2E2;
    color: #991B1B;
  }

  .bubble-footer {
    margin-top: 0.5rem;
    display: flex;
    gap: 0.5rem;
    align-items: center;
    flex-wrap: wrap;
  }

  .fallback-reason {
    font-size: 0.8rem;
    color: #6c757d;
    font-style: italic;
  }
</style>