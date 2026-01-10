<script>

  import DOMPurify from "dompurify";
  import { fade } from "svelte/transition";
  import {
  streamMessage,
  fetchSessionSummary,
  deleteSessionApi,
  getSessionMessages,
  getProviders,
  exportSession,
  forkSession,
  generateSessionTitle,
  regenerateMessage,
  approveConfirmation,
  rejectConfirmation,
  dismissProactiveNotification
} from "../lib/api.js";
  import { marked } from "marked";
  import Prism from "prismjs";
  import "prismjs/components/prism-python";
  import "prismjs/themes/prism-tomorrow.css";
  import { tick, afterUpdate, onMount, onDestroy } from "svelte";
  import VoiceControls from "./VoiceControls.svelte";
  import ChatControls from "./ChatControls.svelte";

  export let sessionId;
  export let currentMode = "personal";
  export let sessionMode = undefined; // Mode of the current session
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
  function formatModelDisplay(provider, model, taskType, metadata = {}) {
    // Extract friendly name from model or provider
    let modelName = "";
    let providerType = "";

    // Special cases for non-AI responses (don't show model badge)
    // Note: weather, routing, and plex/whoop have special handling below
    if (provider === "memory" || provider === "error" || provider === "confirmation" || provider === "intent_reasoning") {
      return null;
    }

    // If provider_name is available in metadata, use it directly (this is the configured name)
    if (metadata?.provider_name && metadata?.provider_type) {
      const routing = taskType
        ? taskType.charAt(0).toUpperCase() + taskType.slice(1).replace(/_/g, " ")
        : "General";

      // Capitalize provider type
      const formattedType = metadata.provider_type.charAt(0).toUpperCase() + metadata.provider_type.slice(1);

      return `${metadata.provider_name} · ${formattedType} · ${routing}`;
    }

    // Action router responses - check task_type for special handling
    if (provider === "action_router") {
      if (taskType === "whoop") {
        // Extract processing model from metadata if available
        const processingModel = metadata?.llm_provider_name || "Sonnet-4.5";
        return `${processingModel} · WHOOP · Live Data`;
      }
      if (taskType === "plex") {
        // Extract processing model and sub-task from metadata
        const processingModel = metadata?.llm_provider_name || "Sonnet-4.5";
        const service = metadata?.service || "Plex";
        const subTask = metadata?.sub_task || "Media";
        return `${processingModel} · ${service} · ${subTask}`;
      }
      return null; // Other action_router responses don't show footer
    }

    // WHOOP proactive notifications
    if (provider === "whoop") {
      // Extract processing model from metadata if available
      const processingModel = metadata?.llm_provider_name || "Sonnet-4.5";

      if (model === "whoop-stress-notification") {
        return `${processingModel} · WHOOP · Stress/Recovery`;
      } else if (model === "whoop-sleep-notification") {
        return `${processingModel} · WHOOP · Sleep Summary`;
      } else if (model === "whoop-workout-notification") {
        return `${processingModel} · WHOOP · Workout Summary`;
      }
      return `${processingModel} · WHOOP · Proactive notification`;
    }

    // If we have explicit provider info from metadata (e.g., from LLM summarization),
    // use that for display
    if (metadata?.llm_provider_name && metadata?.llm_provider_type) {
      modelName = metadata.llm_provider_name;
      providerType = metadata.llm_provider_type;

      // Format task type
      const routing = taskType
        ? taskType.charAt(0).toUpperCase() + taskType.slice(1).replace(/_/g, " ")
        : "General";

      return `${modelName} · ${providerType} · ${routing}`;
    }

    // Weather provider
    if (provider === "weather") {
      if (model === "openweather") {
        return "OpenWeather · Weather";
      }
      return `${model} · Weather`;
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
    } else if (model && model.includes("grok")) {
      providerType = "xAI";
      if (model.includes("grok-beta")) modelName = "Grok Beta";
      else if (model.includes("grok-vision")) modelName = "Grok Vision";
      else if (model.includes("grok-2")) modelName = "Grok-2";
      else if (model.includes("grok-4")) modelName = "Grok-4";
      else if (model.includes("grok-3")) modelName = "Grok-3";
      else modelName = model;
    } else if (model && (model.includes("mistral") || model.includes("magistral") || model.includes("codestral")) || provider && provider.includes("codestral")) {
      providerType = "Mistral";
      if (model.includes("mistral-large")) modelName = "Mistral Large";
      else if (model.includes("mistral-medium")) modelName = "Mistral Medium";
      else if (model.includes("mistral-small")) modelName = "Mistral Small";
      else if (model.includes("magistral-medium")) modelName = "Magistral Medium";
      else if (model.includes("magistral-small")) modelName = "Magistral Small";
      else if (model.includes("codestral")) modelName = "Codestral";
      else modelName = model;
    } else if (model && model.includes("gemini")) {
      providerType = "Google";
      if (model.includes("gemini-3-pro")) modelName = "Gemini 3 Pro";
      else if (model.includes("gemini-3-flash")) modelName = "Gemini 3 Flash";
      else if (model.includes("gemini-2.5-pro")) modelName = "Gemini 2.5 Pro";
      else if (model.includes("gemini-2.5-flash-lite")) modelName = "Gemini 2.5 Flash Lite";
      else if (model.includes("gemini-2.5-flash")) modelName = "Gemini 2.5 Flash";
      else if (model.includes("gemini-2.0-flash-lite")) modelName = "Gemini 2.0 Flash Lite";
      else if (model.includes("gemini-2.0-flash")) modelName = "Gemini 2.0 Flash";
      else if (model.includes("gemini-1.5-pro")) modelName = "Gemini 1.5 Pro";
      else if (model.includes("gemini-1.5-flash")) modelName = "Gemini 1.5 Flash";
      else modelName = model;
    } else if (model && (model.includes("sonar") || model.includes("llama-3.1-sonar"))) {
      providerType = "Perplexity";
      if (model.includes("sonar-huge")) modelName = "Sonar-Huge";
      else if (model.includes("sonar-large")) modelName = "Sonar-Large";
      else if (model.includes("sonar-small")) modelName = "Sonar-Small";
      else if (model.includes("sonar-medium")) modelName = "Sonar-Medium";
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

  // Debug instruction storage
  let lastDebugInstruction = null;

  // Input textarea reference for height reset
  let inputTextarea = null;

  // Voice controls
  let voiceControls = null;
  let autoReadEnabled = localStorage.getItem("theo.autoRead") !== "false"; // Default to true
  let lastMessageCount = 0;
  let skipNextAutoRead = false; // Flag to prevent auto-read on session load
  let selectedVoice = "alloy";
  let speechSpeed = 1.0;
  let isSpeaking = false; // Track if TTS is currently playing

  // Polling for new proactive notifications
  let pollingInterval = null;
  const POLL_INTERVAL_MS = 30000; // Poll every 30 seconds

  // Track user interaction for autoplay permission
  let hasUserInteracted = false;

  // Load voice settings from localStorage
  function loadVoiceSettings() {
    selectedVoice = localStorage.getItem("theo.voice") || "alloy";
    speechSpeed = parseFloat(localStorage.getItem("theo.speechSpeed")) || 1.0;
  }

  // Save auto-read preference when it changes
  $: {
    localStorage.setItem("theo.autoRead", autoReadEnabled.toString());
  }

  // Watch for new assistant messages and auto-read if enabled
  $: {
    if (skipNextAutoRead) {
      // Skip this auto-read (session was just loaded)
      skipNextAutoRead = false;
      lastMessageCount = messages.length;
    } else if (autoReadEnabled && messages.length > lastMessageCount && lastMessageCount > 0) {
      // New message arrived in current session
      const latestMessage = messages[messages.length - 1];
      // Skip TTS for coding intent - we don't want lines of code read out loud
      const shouldSkipTTS = latestMessage?.task_type === "coding";

      if (latestMessage && latestMessage.role === "assistant" && latestMessage.text && !shouldSkipTTS) {
        // Only attempt autoplay if user has interacted with the page
        // This prevents browser autoplay policy errors
        if (hasUserInteracted) {
          // Reload voice settings in case they were changed
          loadVoiceSettings();
          // Auto-read the latest assistant message
          setTimeout(() => {
            voiceControls?.speak(latestMessage.text);
          }, 100);
        } else {
          console.log("[TTS] Skipping autoplay - waiting for user interaction (browser autoplay policy)");
        }
      }
      // Update count after processing
      lastMessageCount = messages.length;
    } else {
      // Just update the count
      lastMessageCount = messages.length;
    }
  }

  // Mode lock detection
  $: isModeLocked = sessionMode && sessionMode !== currentMode;

  // Mode switch notification
  let modeSwitchNotification = null;

  // Start polling for new messages
  function startPolling() {
    stopPolling(); // Clear any existing interval

    pollingInterval = setInterval(async () => {
      if (!sessionId || loading) return;

      try {
        const turns = await getSessionMessages(sessionId);
        const currentMessageCount = turns.length;

        // If new messages appeared, refresh
        if (currentMessageCount > messages.length) {
          console.log(`[POLLING] New messages detected (${currentMessageCount} vs ${messages.length}), refreshing...`);

          messages = turns.map(t => ({
            id: t.id,
            role: t.role,
            text: t.content,
            provider: t.provider,
            model: t.model,
            task_type: t.task_type,
            created_at: t.created_at,
            metadata: t.metadata || null
          }));

          // Scroll to bottom on new message
          await tick();
          scrollToBottom();
        }
      } catch (e) {
        // Silently fail - don't spam console with poll errors
      }
    }, POLL_INTERVAL_MS);
  }

  // Stop polling
  function stopPolling() {
    if (pollingInterval) {
      clearInterval(pollingInterval);
      pollingInterval = null;
    }
  }

  onMount(async () => {
    try {
      const result = await getProviders();
      // Only enabled, non-mock providers
      providers = (result || [])
        .filter(p => p.enabled && p.type !== "mock")
        .map(p => ({ id: p.id, name: p.name, suitable_for_official: p.suitable_for_official }));
    } catch (e) {
      // If fails, leave providers empty
    }

    // Load voice settings on mount
    loadVoiceSettings();

    // Initialize lastMessageCount to prevent auto-read on page load
    lastMessageCount = messages.length;

    // Load advanced mode from localStorage
    const storedAdvanced = localStorage.getItem("theo.advancedMode");
    advancedMode = storedAdvanced === "true";

    // Listen for advanced mode changes
    window.addEventListener("advancedModeChanged", (e) => {
      advancedMode = e.detail.enabled;
    });

    // Listen for visual streaming preference changes
    window.addEventListener("visualStreamingChanged", (e) => {
      visualStreamingDisabled = e.detail.disabled;
    });

    // Listen for mode switching events
    window.addEventListener("modeSwitching", (e) => {
      const { fromMode, toMode } = e.detail;
      modeSwitchNotification = {
        fromMode,
        toMode,
        message: `Switching from ${fromMode} to ${toMode} mode.`
      };

      // Clear notification after 3 seconds
      setTimeout(() => {
        modeSwitchNotification = null;
      }, 3000);
    });

    // Track user interaction for autoplay permission
    const markUserInteraction = () => {
      if (!hasUserInteracted) {
        hasUserInteracted = true;
        console.log("[TTS] User interaction detected - autoplay enabled");
      }
    };

    // Listen for any user interaction
    document.addEventListener("click", markUserInteraction, { once: false });
    document.addEventListener("keydown", markUserInteraction, { once: false });
    document.addEventListener("touchstart", markUserInteraction, { once: false });

    // Start polling for new proactive notifications
    startPolling();
  });

  onDestroy(() => {
    // Clean up polling on component destroy
    stopPolling();
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

  // Track last text length for smooth CSS transitions
  let lastTextLength = 0;

  // Check if visual streaming is disabled (user preference)
  // Initialize from localStorage
  let visualStreamingDisabled = localStorage.getItem("visual_streaming_disabled") === "true";

  // Auto-scroll after every update
  afterUpdate(() => {
    scrollToBottom();
  });

  function renderMarkdown(text, messageId = null, citations = []) {
    if (!text) return "";

    // Auto-linkify plain URLs that aren't already in markdown link format
    const urlRegex = /(?<![(\[])(https?:\/\/[^\s<]+[^<.,:;"')\]\s])/g;
    text = text.replace(urlRegex, (url) => {
      return `[${url}](${url})`;
    });

    marked.setOptions({
      langPrefix: "language-",
      breaks: true  // Convert single newlines to <br> tags
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
        "a": ["href", "title", "target", "rel", "class"],
        "span": ["class"],
        "code": ["class"]
      }
    });

    // Add target="_blank" and rel to all links (except citation refs)
    const links = tempDiv.querySelectorAll('a');
    links.forEach(link => {
      if (!link.classList.contains('citation-ref')) {
        link.setAttribute('target', '_blank');
        link.setAttribute('rel', 'noopener noreferrer');
      }
    });

    // Replace citation numbers with clickable source titles (do this AFTER markdown parsing)
    if (citations && citations.length > 0) {
      const walker = document.createTreeWalker(tempDiv, NodeFilter.SHOW_TEXT, null);
      const textNodes = [];
      while (walker.nextNode()) {
        textNodes.push(walker.currentNode);
      }

      textNodes.forEach(node => {
        const text = node.textContent;
        // Match [1], [2], etc.
        if (/\[\d+\]/.test(text)) {
          const span = document.createElement('span');
          let lastIndex = 0;
          let html = '';

          text.replace(/\[(\d+)\]/g, (match, num, offset) => {
            const index = parseInt(num) - 1;
            // Add text before citation
            html += document.createTextNode(text.substring(lastIndex, offset)).textContent;

            if (index >= 0 && index < citations.length) {
              const url = citations[index];
              try {
                const urlObj = new URL(url);
                const domain = urlObj.hostname.replace('www.', '');
                const title = domain.split('.')[0];
                // Create citation link
                html += `<a href="${url}" target="_blank" rel="noopener noreferrer" class="citation-ref" title="${domain}">${title}</a>`;
              } catch (e) {
                html += match;
              }
            } else {
              html += match;
            }

            lastIndex = offset + match.length;
            return match;
          });

          // Add remaining text
          html += text.substring(lastIndex);
          span.innerHTML = html;
          node.parentNode.replaceChild(span, node);
        }
      });
    }

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

      // Set flag to prevent auto-read when loading a session
      skipNextAutoRead = true;

      const turns = await getSessionMessages(id);

      messages = turns.map(t => ({
        id: t.id,
        role: t.role,
        text: t.content,
        provider: t.provider,
        model: t.model,
        task_type: t.task_type,
        created_at: t.created_at,
        metadata: t.metadata || null
      }));

      // Track unique AI providers used in this session
      // Only include providers that are in the AI providers list (same as force provider dropdown)
      const aiProviderIds = new Set(providers.map(p => p.id));
      usedProviders = new Set(
        messages
          .filter(m => m.provider && aiProviderIds.has(m.provider))
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

  async function handleRegenerate(event) {
    const { turnId } = event.detail;

    try {
      loading = true;

      // Call regenerate endpoint to delete turns and get user message
      const result = await regenerateMessage(sessionId, turnId);

      // Reload messages to reflect deletion
      await loadSessionMessages(sessionId);

      // Re-submit the user message
      const userText = result.user_message;
      error = null;
      streaming = true;
      streamedText = "";
      streamBuffer = "";
      lastTextLength = 0;

      await streamMessage({
        sessionId,
        text: userText,
        forcedProvider: forcedModel,
        workSubtab: currentMode === "work" ? activeWorkSubtab : null,
        onToken(token) {
          // Add tokens directly - CSS will handle smoothness
          streamedText += token;
          lastTextLength = streamedText.length;
          scrollToBottom();
        },
        async onEnd(meta) {
          // Capture the completed text IMMEDIATELY for TTS
          const completedText = streamedText;
          const shouldSkipTTS = meta?.task_type === "coding";

          if (meta?.provider) {
            usedProviders = new Set([...usedProviders, meta.provider]);
          }

          if (meta?.debug_instruction) {
            lastDebugInstruction = {
              ...meta.debug_instruction,
              expanded: false
            };
          }

          // Clear streaming state IMMEDIATELY (don't wait for DB)
          streamedText = "";
          streaming = false;
          loading = false;

          // Trigger TTS IMMEDIATELY (in parallel with DB reload)
          if (autoReadEnabled && completedText && !shouldSkipTTS && hasUserInteracted) {
            loadVoiceSettings();
            voiceControls?.speak(completedText);
          }

          // Reload messages from database in background
          loadSessionMessages(sessionId).then(async () => {
            await tick();
            scrollToBottom();
            enhanceCodeBlocks();
          });
        },
        onError(err) {
          error = err;
          streaming = false;
          loading = false;
        }
      });
    } catch (e) {
      alert(`Failed to regenerate: ${e.message}`);
      loading = false;
    }
  }

  async function handleBranch(event) {
    const { turnId } = event.detail;

    try {
      // Find the index of the turn to branch at
      const turnIndex = messages.findIndex(m => m.id === turnId);

      if (turnIndex === -1) {
        alert("Could not find message to branch from");
        return;
      }

      // Fork the session at this turn
      const result = await forkSession(sessionId, turnIndex);

      // Reload page to show the new branched session
      window.location.reload();
    } catch (e) {
      alert(`Failed to branch: ${e.message}`);
    }
  }

  async function submit() {
    if (!input || loading) return;

    const userText = input;
    input = "";
    error = null;

    // Reset textarea height to default
    if (inputTextarea) {
      inputTextarea.style.height = 'auto';
    }

    messages = [...messages, { role: "user", text: userText, created_at: new Date().toISOString() }];
    loading = true;
    streaming = true;
    streamedText = "";
    streamBuffer = "";
    lastTextLength = 0;

    try {
      await streamMessage({
        sessionId,
        text: userText,
        forcedProvider: forcedModel,
        workSubtab: currentMode === "work" ? activeWorkSubtab : null,
        onToken(token) {
          // Add tokens directly - CSS will handle smoothness
          streamedText += token;
          lastTextLength = streamedText.length;
          scrollToBottom();
        },
        async onEnd(meta) {
          // Capture the completed text IMMEDIATELY for TTS
          const completedText = streamedText;
          const shouldSkipTTS = meta?.task_type === "coding";

          // Add provider to used providers set
          if (meta?.provider) {
            usedProviders = new Set([...usedProviders, meta.provider]);
          }

          // Capture debug instruction if present
          if (meta?.debug_instruction) {
            lastDebugInstruction = {
              ...meta.debug_instruction,
              expanded: false
            };
          }

          // Clear streaming state IMMEDIATELY (don't wait for DB)
          streamedText = "";
          streaming = false;
          loading = false;

          // Trigger TTS IMMEDIATELY (in parallel with DB reload)
          if (autoReadEnabled && completedText && !shouldSkipTTS && hasUserInteracted) {
            loadVoiceSettings();
            voiceControls?.speak(completedText);
          }

          // Reload messages from database and generate title after loading
          loadSessionMessages(sessionId).then(async () => {
            await tick();
            scrollToBottom();
            enhanceCodeBlocks();

            // Generate title after first assistant response (after messages are loaded)
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
                console.error("Failed to generate session title:", e);
              }
            }
          });

          await tick();
          scrollToBottom();
          enhanceCodeBlocks();
          loadSummary();
        },
        onError(err) {
          streaming = false;
          loading = false;

          // If we received a partial response, show it with a warning
          if (streamedText.length > 0) {
            error = "Stream interrupted. Partial response displayed. You can try sending your message again.";
          } else {
            error = err?.message || "Streaming failed. Please try again.";
          }
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

  async function handleDismissNotification(turnId) {
    try {
      await dismissProactiveNotification(turnId);

      // Update the message metadata to show dismissed status
      messages = messages.map(m => {
        if (m.id === turnId) {
          return {
            ...m,
            metadata: { ...m.metadata, dismissed: true, dismissed_at: new Date().toISOString() }
          };
        }
        return m;
      });
    } catch (e) {
      console.error("Dismiss error:", e);
      alert("Failed to dismiss notification: " + e.message);
    }
  }
</script>

<div class="chat">
    <div class="chat-inner">
      <div class="session-bar">
        <div class="session-title">
          <strong>Chat</strong>
          {#if currentMode === "work"}
            <span class="official-badge">Working at OFFICIAL</span>
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

          <!-- Model selector -->
          <select
            class="provider-select"
            bind:value={forcedModel}
            title="Model"
          >
            <option value="">Auto</option>
            <option value="mock">Mock</option>
            {#each providers as p}
              {#if currentMode !== "work" || p.suitable_for_official}
                <option value={p.id}>{p.name}</option>
              {/if}
            {/each}
          </select>

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

      <!-- Mode Switch Notification -->
      {#if modeSwitchNotification}
        <div class="mode-switch-notification">
          {modeSwitchNotification.message}
        </div>
      {/if}

      <!-- Mode Lock Warning -->
      {#if isModeLocked}
        <div class="mode-lock-warning">
          This is a {sessionMode} chat. To continue, you must switch modes
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
                {#if currentMode === "work"}
                  <div class="security-notice">
                    <strong>Security Notice:</strong> All interactions are recorded and sensitive information such as passwords, personal identification numbers, and other confidential data should not be shared. Please refer to the <a href="https://www.gov.uk/government/publications/government-security-classifications" target="_blank" rel="noopener noreferrer">government classification guidance</a> for more information on handling OFFICIAL data.
                  </div>
                {:else}
                  <div>Hello, what do you want to do today?</div>
                {/if}
              </div>
            </div>
          {/if}

          {#each messages.filter(m => !(m.metadata?.proactive && m.metadata?.dismissed)) as m}
            <div class="message {m.role}" transition:fade={{ duration: m.role === 'assistant' ? 200 : 0 }}>
              <div class="bubble">
                <div class="message-header">
                  <strong>{m.role === "user" ? "Me" : "Theo"}</strong>
                  {#if m.created_at}
                    <span class="timestamp">{formatTimestamp(m.created_at)}</span>
                  {/if}
                </div>

                {#if m.role === "assistant"}
                  {@const citations = m.metadata && m.metadata.citations ? m.metadata.citations : []}
                  <div class="markdown">
                    {@html renderMarkdown(m.text, m.id, citations)}
                  </div>

                  {#if m.metadata && m.metadata.citations && m.metadata.citations.length > 0}
                    <details class="citations-section">
                      <summary class="citations-summary">
                        <span class="citations-icon">🔗</span>
                        Sources ({m.metadata.citations.length})
                      </summary>
                      <div class="citations-list">
                        {#each m.metadata.citations as citation, idx}
                          {@const urlObj = new URL(citation)}
                          {@const domain = urlObj.hostname.replace('www.', '')}
                          {@const title = domain.split('.')[0].toUpperCase()}
                          <div class="citation-item" id="citation-{m.id}-{idx + 1}">
                            <span class="citation-number">[{idx + 1}]</span>
                            <a href={citation} target="_blank" rel="noopener noreferrer" class="citation-link">
                              <span class="citation-title">{title}</span>
                              <span class="citation-domain">{domain}</span>
                            </a>
                          </div>
                        {/each}
                      </div>
                    </details>
                  {/if}

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

                  {#if m.metadata && m.metadata.proactive && !m.metadata.dismissed}
                    <div class="proactive-notification">
                      <button
                        class="btn-dismiss"
                        on:click={() => handleDismissNotification(m.id)}
                        title="Dismiss this notification"
                      >
                        × Dismiss
                      </button>
                    </div>
                  {/if}

                  {#if m.provider}
                    {@const formattedModel = formatModelDisplay(m.provider, m.model, m.task_type, m.metadata)}
                    {@const isActionRouter = m.provider === 'action_router'}
                    {@const isError = m.provider === 'error'}
                    {@const isWeather = m.provider === 'weather'}
                    {@const isRouting = m.provider === 'routing'}
                    {@const isSearch = m.task_type === 'search' || (m.provider && m.provider.includes('perplexity'))}
                    {@const formattedAction = m.task_type
                      ? m.task_type.charAt(0).toUpperCase() + m.task_type.slice(1).replace(/_/g, " ")
                      : "Action"}
                    <div class="bubble-footer-container">
                      <div class="bubble-footer">
                        {#if isWeather}
                          <span class="provider-badge provider-badge-weather">
                            via OpenWeather · Weather
                          </span>
                        {:else if isRouting}
                          <span class="provider-badge provider-badge-routing">
                            via HERE · Routing
                          </span>
                        {:else if isSearch}
                          <span class="provider-badge provider-badge-search">
                            via {formattedModel}
                          </span>
                        {:else if formattedModel}
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

                      <!-- Chat Controls -->
                      <ChatControls
                        message={{
                          id: m.id,
                          role: m.role,
                          content: m.text
                        }}
                        {sessionId}
                        mode={currentMode}
                        {voiceControls}
                        on:regenerate={handleRegenerate}
                        on:branch={handleBranch}
                      />
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

          {#if lastDebugInstruction && messages.length > 0}
            {@const lastMessage = messages[messages.length - 1]}
            {#if lastMessage.role === "assistant"}
              <div class="message system">
                <div class="bubble debug-bubble">
                  <div class="message-header">
                    <strong>System Debug</strong>
                  </div>
                  <div class="debug-content">
                    {#if lastDebugInstruction.expanded}
                      <div class="debug-section">
                        <h4>System Prompt:</h4>
                        <pre class="debug-text">{lastDebugInstruction.system}</pre>
                      </div>
                      <div class="debug-section">
                        <h4>Messages:</h4>
                        <pre class="debug-text">{JSON.stringify(lastDebugInstruction.messages, null, 2)}</pre>
                      </div>
                      <button class="debug-toggle" on:click={() => lastDebugInstruction = {...lastDebugInstruction, expanded: false}}>
                        Show less
                      </button>
                    {:else}
                      <div class="debug-preview">
                        <pre class="debug-text">{lastDebugInstruction.system.split('\n').slice(0, 10).join('\n')}...</pre>
                      </div>
                      <button class="debug-toggle" on:click={() => lastDebugInstruction = {...lastDebugInstruction, expanded: true}}>
                        Show more
                      </button>
                    {/if}
                  </div>
                </div>
              </div>
            {/if}
          {/if}

          {#if streaming}
            <div class="message assistant">
              <div class="bubble streaming-bubble">
                <strong>Theo:</strong>
                {#key visualStreamingDisabled}
                  {#if visualStreamingDisabled}
                    <!-- Instant display - show loading indicator only -->
                    <div class="streaming-placeholder">
                      <span class="loading-dots">Thinking<span class="dot">.</span><span class="dot">.</span><span class="dot">.</span></span>
                    </div>
                  {:else}
                    <!-- Animated typewriter effect -->
                    {#key lastTextLength}
                      <div class="streaming-text" style="white-space: pre-wrap;" data-visual-streaming="enabled">
                        {streamedText || "…"}
                      </div>
                    {/key}
                    <small>streaming</small>
                  {/if}
                {/key}
              </div>
            </div>
          {/if}
        </div>
        <div class="info-banner">
          THEO and the AI providers it uses can make mistakes, so please always double-check responses for accuracy.
        </div>
        <div class="input">
          <textarea
            bind:this={inputTextarea}
            bind:value={input}
            placeholder={isModeLocked ? `This is a ${sessionMode} chat. To continue you must switch modes` : "How can I help you today?"}
            on:keydown={(e) => {
              if (e.key === "Enter" && !e.shiftKey && !isModeLocked) {
                e.preventDefault();
                submit();
              }
            }}
            on:input={(e) => {
              e.target.style.height = 'auto';
              e.target.style.height = Math.min(e.target.scrollHeight, 200) + 'px';
            }}
            disabled={isModeLocked}
            rows="1"
          />

          <div class="input-controls">
            <!-- Voice controls -->
            <VoiceControls
              bind:this={voiceControls}
              bind:autoReadEnabled
              bind:isSpeaking
              selectedVoice={selectedVoice}
              speechSpeed={speechSpeed}
              onTranscript={(text) => {
                input = text;
                submit();
              }}
            />

            {#if streaming}
              <button class="btn-danger" disabled>
                Streaming…
              </button>
            {:else if isSpeaking}
              <button class="btn-warning" on:click={() => voiceControls?.stopSpeaking()}>
                Speaking…
              </button>
            {:else}
              <button class="btn-primary" on:click={submit} disabled={loading || isModeLocked}>
                {loading ? "Thinking…" : "Send"}
              </button>
            {/if}
          </div>
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

  :global(.markdown p code),
  :global(.markdown li code) {
    display: inline;
    white-space: normal;
    word-break: keep-all;
    background: rgba(110, 118, 129, 0.1);
    padding: 0.2em 0.4em;
    border-radius: 3px;
    font-size: 0.9em;
  }

  :global(.markdown strong),
  :global(.markdown b) {
    font-weight: 600;
    font-family: inherit;
    display: inline;
    white-space: normal;
  }

  :global(.markdown em),
  :global(.markdown i) {
    font-style: italic;
    font-family: inherit;
    display: inline;
    white-space: normal;
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
    background: var(--bg-tertiary);
    border: 2px solid var(--theo-blue);
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
    color: var(--theo-blue);
  }

  .confirmation-expires {
    font-size: 0.85rem;
    color: var(--text-secondary);
  }

  .confirmation-message {
    margin-bottom: 1rem;
    font-size: 0.95rem;
    color: var(--text-primary);
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

  .proactive-notification {
    margin-top: 0.75rem;
    display: flex;
    justify-content: flex-start;
  }

  .btn-dismiss {
    padding: 0.4rem 0.8rem;
    background: #dc3545;
    color: white;
    border: none;
    border-radius: 4px;
    font-size: 0.85rem;
    font-weight: 500;
    cursor: pointer;
    transition: all 0.2s;
  }

  .btn-dismiss:hover {
    background: #c82333;
  }

  .confirmation-status {
    margin-top: 0.75rem;
    padding: 0.5rem;
    border-radius: 4px;
    text-align: center;
    font-weight: 600;
  }

  .confirmation-status.approved {
    background: var(--status-success-bg);
    color: var(--status-success-text);
  }

  .confirmation-status.rejected {
    background: var(--status-error-bg);
    color: var(--status-error-text);
  }

  /* Completed state styling */
  .confirmation-widget.approved {
    border-color: var(--success-500);
    background: var(--success-50);
  }

  .confirmation-widget.approved .confirmation-icon {
    color: var(--success-600);
  }

  .confirmation-widget.approved .confirmation-result {
    color: var(--success-600);
  }

  .confirmation-widget.rejected {
    border-color: var(--error-500);
    background: var(--error-50);
  }

  .confirmation-widget.rejected .confirmation-icon {
    color: var(--error-600);
  }

  .confirmation-widget.rejected .confirmation-result {
    color: var(--error-600);
  }

  .confirmation-result {
    margin-bottom: 0.75rem;
    font-size: 0.95rem;
    color: var(--text-primary);
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
    background: var(--success-500);
    color: white;
  }

  .confirmation-status-final.rejected {
    background: var(--error-500);
    color: white;
  }

  /* Provider Badge Styling */
  .provider-badge {
    font-size: 0.75rem;
    padding: 0.25rem 0.5rem;
    border-radius: 4px;
    display: inline-block;
  }

  /* AI responses - blue */
  .provider-badge-ai {
    background: var(--info-100);
    color: var(--info-700);
  }

  /* Action router responses - amber */
  .provider-badge-action {
    background: var(--warning-100);
    color: var(--warning-600);
  }

  /* Error responses - red */
  .provider-badge-error {
    background: var(--error-100);
    color: var(--error-700);
  }

  /* Weather responses - washed out purple */
  .provider-badge-weather {
    background: #f3e8ff;
    color: #7c3aed;
  }

  /* Routing responses - same purple as weather */
  .provider-badge-routing {
    background: #f3e8ff;
    color: #7c3aed;
  }

  /* Search responses - washed out green */
  .provider-badge-search {
    background: #d1fae5;
    color: #047857;
  }

  /* Citations Section */
  .citations-section {
    margin-top: 1rem;
    padding: 0.75rem;
    background: #f9fafb;
    border: 1px solid #e5e7eb;
    border-radius: 6px;
    font-size: 0.875rem;
  }

  .citations-summary {
    cursor: pointer;
    font-weight: 600;
    color: #374151;
    user-select: none;
    list-style: none;
    display: flex;
    align-items: center;
    gap: 0.5rem;
  }

  .citations-summary::-webkit-details-marker {
    display: none;
  }

  .citations-icon {
    font-size: 1rem;
  }

  .citations-list {
    margin-top: 0.75rem;
    padding-top: 0.75rem;
    border-top: 1px solid #e5e7eb;
  }

  .citation-item {
    display: flex;
    align-items: flex-start;
    gap: 0.5rem;
    padding: 0.5rem;
    margin-bottom: 0.5rem;
    background: white;
    border-radius: 4px;
    scroll-margin-top: 4rem;
  }

  .citation-item:last-child {
    margin-bottom: 0;
  }

  .citation-number {
    flex-shrink: 0;
    font-weight: 600;
    color: #047857;
    font-size: 0.875rem;
  }

  .citation-link {
    flex: 1;
    text-decoration: none;
    color: inherit;
    display: flex;
    flex-direction: column;
    gap: 0.25rem;
  }

  .citation-link:hover {
    text-decoration: underline;
  }

  .citation-title {
    font-weight: 600;
    color: #047857;
    font-size: 0.875rem;
  }

  .citation-domain {
    color: #6b7280;
    font-size: 0.75rem;
  }

  /* Citation references in text - badge style */
  :global(.markdown .citation-ref),
  :global(.citation-ref) {
    display: inline-block !important;
    padding: 2px 6px !important;
    margin: 0 2px !important;
    background: #e5e7eb !important;
    color: #374151 !important;
    text-decoration: none !important;
    font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace !important;
    font-size: 0.85em !important;
    font-weight: 500 !important;
    border-radius: 3px !important;
    cursor: pointer !important;
    transition: background 0.2s ease !important;
  }

  :global(.markdown .citation-ref:hover),
  :global(.citation-ref:hover) {
    background: #d1d5db !important;
    color: #374151 !important;
    text-decoration: none !important;
  }

  .bubble-footer-container {
    margin-top: 0.5rem;
    display: flex;
    justify-content: space-between;
    align-items: center;
    gap: 1rem;
  }

  .bubble-footer {
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

  /* Mode Lock Warning */
  .mode-lock-warning {
    background: #dc3545;
    color: white;
    padding: 1rem;
    margin: 0.5rem 1rem;
    border-radius: 6px;
    text-align: center;
    font-weight: 500;
  }

  /* Info Banner */
  .info-banner {
    background: #f9fafb;
    color: #6b7280;
    padding: 0.5rem 1rem;
    text-align: left;
    font-size: 0.75rem;
    border-top: 1px solid #e5e7eb;
    border-bottom: 1px solid #e5e7eb;
  }

  /* Mode Switch Notification */
  .mode-switch-notification {
    background: #ffc107;
    color: #000;
    padding: 1rem;
    margin: 0.5rem 1rem;
    border-radius: 6px;
    text-align: center;
    font-weight: 500;
    animation: slideDown 0.3s ease-out;
  }

  @keyframes slideDown {
    from {
      opacity: 0;
      transform: translateY(-10px);
    }
    to {
      opacity: 1;
      transform: translateY(0);
    }
  }

  /* Disabled input styling for mode lock */
  .input textarea:disabled {
    background: #f5f5f5;
    cursor: not-allowed;
    opacity: 0.7;
  }

  /* Voice controls */
  .speak-btn {
    background: none;
    border: none;
    font-size: 0.9rem;
    cursor: pointer;
    opacity: 0.6;
    padding: 0.25rem;
    margin-left: 0.5rem;
    transition: opacity 0.2s ease;
  }

  .speak-btn:hover {
    opacity: 1;
  }

  .message-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
  }

  /* Debug bubble styles */
  .message.system .bubble.debug-bubble {
    background: #f6f8fa;
    border: 1px solid #d0d7de;
    margin-top: 1rem;
  }

  .debug-content {
    margin-top: 0.75rem;
  }

  .debug-section {
    margin-bottom: 1rem;
  }

  .debug-section h4 {
    margin: 0 0 0.5rem 0;
    font-size: 0.9rem;
    color: #57606a;
    font-weight: 600;
  }

  .debug-text {
    background: #ffffff;
    border: 1px solid #d0d7de;
    border-radius: 6px;
    padding: 0.75rem;
    font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, "Liberation Mono", monospace;
    font-size: 0.85rem;
    color: #24292f;
    overflow-x: auto;
    white-space: pre-wrap;
    word-break: break-word;
    margin: 0;
  }

  .debug-preview {
    margin-bottom: 0.75rem;
  }

  .debug-toggle {
    background: #0969da;
    color: white;
    border: none;
    border-radius: 6px;
    padding: 0.5rem 1rem;
    font-size: 0.875rem;
    font-weight: 600;
    cursor: pointer;
    transition: background 0.2s;
  }

  .debug-toggle:hover {
    background: #0860ca;
  }

  .debug-toggle:active {
    background: #0757ba;
  }

  /* Streaming text smooth flow-in effect */
  .streaming-bubble {
    position: relative;
    /* GPU-accelerated rendering */
    transform: translateZ(0);
    backface-visibility: hidden;
  }

  .streaming-text {
    /* Smooth text rendering (always applied) */
    -webkit-font-smoothing: antialiased;
    -moz-osx-font-smoothing: grayscale;
    text-rendering: optimizeLegibility;
  }

  /* Animated mode - only apply to non-instant elements */
  .streaming-text:not(.streaming-instant) {
    will-change: contents;
    transform: translateZ(0);
    contain: layout style paint;
    transition: opacity 0.05s ease-out;
  }

  /* Smooth appearance for new text chunks - only when NOT instant */
  @keyframes textFlow {
    0% {
      opacity: 0.85;
      transform: translateY(1px);
    }
    100% {
      opacity: 1;
      transform: translateY(0);
    }
  }

  .streaming-text:not(.streaming-instant):not(:empty) {
    animation: textFlow 0.1s ease-out;
  }

  /* Instant mode - explicitly no animations */
  .streaming-instant {
    animation: none;
    transition: none;
    will-change: auto;
    transform: none;
    opacity: 1;
  }

  /* Loading indicator for instant mode */
  .streaming-placeholder {
    color: var(--text-secondary, #666);
    font-style: italic;
  }

  .loading-dots {
    display: inline-block;
  }

  .loading-dots .dot {
    animation: dotPulse 1.4s infinite;
    opacity: 0;
  }

  .loading-dots .dot:nth-child(1) {
    animation-delay: 0s;
  }

  .loading-dots .dot:nth-child(2) {
    animation-delay: 0.2s;
  }

  .loading-dots .dot:nth-child(3) {
    animation-delay: 0.4s;
  }

  @keyframes dotPulse {
    0%, 20%, 100% {
      opacity: 0;
    }
    50% {
      opacity: 1;
    }
  }
</style>