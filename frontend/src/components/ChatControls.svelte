<script>
  import { regenerateMessage, forkSession } from "../lib/api.js";
  import { openOutlookDraft } from "../lib/outlookUtils.js";
  import { createEventDispatcher } from "svelte";

  export let message; // Turn object with { id, role, content, ... }
  export let sessionId;
  export let mode = "personal"; // "work" or "personal"
  export let voiceControls = null; // Reference to VoiceControls component for TTS

  const dispatch = createEventDispatcher();

  let isRegenerating = false;
  let isCopied = false;
  let isSpeaking = false;
  let isOutlookOpening = false;

  /**
   * Copy message content to clipboard
   */
  async function copyMessage() {
    try {
      await navigator.clipboard.writeText(message.content);
      isCopied = true;
      setTimeout(() => {
        isCopied = false;
      }, 2000);
    } catch (error) {
      console.error("Failed to copy:", error);
      alert("Failed to copy message to clipboard");
    }
  }

  /**
   * Regenerate message - re-run the previous user prompt to get a fresh response
   */
  async function regenerateResponse() {
    if (isRegenerating) return;

    try {
      isRegenerating = true;
      dispatch("regenerate", { turnId: message.id });
    } catch (error) {
      console.error("Failed to regenerate:", error);
      alert("Failed to regenerate response");
    } finally {
      isRegenerating = false;
    }
  }

  /**
   * Read message aloud using TTS
   */
  async function readAloud() {
    if (!voiceControls) {
      alert("Voice controls not available");
      return;
    }

    try {
      if (isSpeaking) {
        voiceControls.stopSpeaking();
        isSpeaking = false;
      } else {
        isSpeaking = true;
        await voiceControls.speak(message.content);
        // Reset when done
        isSpeaking = false;
      }
    } catch (error) {
      console.error("Failed to read aloud:", error);
      isSpeaking = false;
    }
  }

  /**
   * Branch conversation at this message
   */
  async function branchConversation() {
    try {
      // Find the index of this turn to fork before it
      dispatch("branch", { turnId: message.id });
    } catch (error) {
      console.error("Failed to branch:", error);
      alert("Failed to branch conversation");
    }
  }

  /**
   * Send message to Outlook Web as draft
   * Only available in Work mode
   */
  async function sendToOutlook() {
    if (mode !== "work") return;

    try {
      isOutlookOpening = true;

      // Try to open Outlook Web draft
      const success = await openOutlookDraft(message.content);

      if (!success) {
        // Fallback was used (popup blocked or error)
        alert(
          "Outlook popup was blocked or unavailable.\n\n" +
          "The message has been copied to your clipboard.\n" +
          "You can paste it into Outlook manually."
        );
      }

      isOutlookOpening = false;
    } catch (error) {
      console.error("Failed to open Outlook draft:", error);
      alert("Failed to open Outlook draft. Please try again.");
      isOutlookOpening = false;
    }
  }
</script>

<div class="chat-controls">
  <!-- Copy Button -->
  <button
    class="control-btn"
    on:click={copyMessage}
    title={isCopied ? "Copied!" : "Copy message"}
    aria-label="Copy message"
  >
    {#if isCopied}
      <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
        <polyline points="20 6 9 17 4 12"/>
      </svg>
    {:else}
      <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
        <rect x="9" y="9" width="13" height="13" rx="2" ry="2"/>
        <path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"/>
      </svg>
    {/if}
  </button>

  <!-- Regenerate Button -->
  <button
    class="control-btn"
    on:click={regenerateResponse}
    disabled={isRegenerating}
    title="Try again"
    aria-label="Regenerate response"
  >
    <svg
      xmlns="http://www.w3.org/2000/svg"
      width="14"
      height="14"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      stroke-width="2"
      stroke-linecap="round"
      stroke-linejoin="round"
      class:spinning={isRegenerating}
    >
      <path d="M21.5 2v6h-6M2.5 22v-6h6M2 11.5a10 10 0 0 1 18.8-4.3M22 12.5a10 10 0 0 1-18.8 4.2"/>
    </svg>
  </button>

  <!-- Read Aloud Button -->
  <button
    class="control-btn"
    on:click={readAloud}
    title={isSpeaking ? "Stop speaking" : "Read aloud"}
    aria-label={isSpeaking ? "Stop speaking" : "Read aloud"}
  >
    {#if isSpeaking}
      <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="currentColor">
        <rect x="6" y="4" width="4" height="16" rx="1">
          <animate attributeName="height" values="16;8;16" dur="1s" repeatCount="indefinite"/>
          <animate attributeName="y" values="4;8;4" dur="1s" repeatCount="indefinite"/>
        </rect>
        <rect x="14" y="4" width="4" height="16" rx="1">
          <animate attributeName="height" values="16;8;16" dur="1s" repeatCount="indefinite" begin="0.3s"/>
          <animate attributeName="y" values="4;8;4" dur="1s" repeatCount="indefinite" begin="0.3s"/>
        </rect>
      </svg>
    {:else}
      <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
        <polygon points="11 5 6 9 2 9 2 15 6 15 11 19 11 5"/>
        <path d="M15.54 8.46a5 5 0 0 1 0 7.07"/>
        <path d="M19.07 4.93a10 10 0 0 1 0 14.14"/>
      </svg>
    {/if}
  </button>

  <!-- Branch Button -->
  <button
    class="control-btn"
    on:click={branchConversation}
    title="Branch conversation"
    aria-label="Branch conversation"
  >
    <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
      <line x1="6" y1="3" x2="6" y2="15"/>
      <circle cx="18" cy="6" r="3"/>
      <circle cx="6" cy="18" r="3"/>
      <path d="M18 9a9 9 0 0 1-9 9"/>
    </svg>
  </button>

  <!-- Send to Outlook Button (Work Mode Only) -->
  {#if mode === "work"}
    <button
      class="control-btn"
      on:click={sendToOutlook}
      disabled={isOutlookOpening}
      title="Open in Outlook Web as draft"
      aria-label="Send to Outlook"
    >
      <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
        <path d="M4 4h16c1.1 0 2 .9 2 2v12c0 1.1-.9 2-2 2H4c-1.1 0-2-.9-2-2V6c0-1.1.9-2 2-2z"/>
        <polyline points="22,6 12,13 2,6"/>
      </svg>
    </button>
  {/if}
</div>

<style>
  .chat-controls {
    display: flex;
    gap: 4px;
    align-items: center;
  }

  .control-btn {
    background: transparent;
    border: none;
    color: var(--text-secondary, #888);
    cursor: pointer;
    padding: 6px;
    border-radius: 4px;
    transition: all 0.2s ease;
    display: flex;
    align-items: center;
    justify-content: center;
  }

  .control-btn:hover {
    background: var(--hover-bg, rgba(255, 255, 255, 0.05));
    color: var(--text-primary, #fff);
  }

  .control-btn:active {
    transform: scale(0.95);
  }

  .control-btn:disabled {
    opacity: 0.5;
    cursor: not-allowed;
  }

  .control-btn:disabled:hover {
    background: transparent;
    color: var(--text-secondary, #888);
  }

  .spinning {
    animation: spin 1s linear infinite;
  }

  @keyframes spin {
    from {
      transform: rotate(0deg);
    }
    to {
      transform: rotate(360deg);
    }
  }

  /* Focus states for accessibility */
  .control-btn:focus {
    outline: 2px solid var(--accent-color, #4a9eff);
    outline-offset: 2px;
  }

  .control-btn:focus:not(:focus-visible) {
    outline: none;
  }
</style>
