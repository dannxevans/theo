<script>
  import { onDestroy } from "svelte";
  import { createEventDispatcher } from "svelte";
  import AudioVisualizer from "./AudioVisualizer.svelte";
  import DashboardWidgets from "./DashboardWidgets.svelte";
  import { streamMessage, speechToText, textToSpeech } from "../lib/api.js";

  const dispatch = createEventDispatcher();

  export let sessionId = null;

  // State management
  let state = "idle"; // "idle" | "listening" | "processing" | "speaking"
  let statusText = "Tap to Speak";
  let userInput = "";
  let aiResponse = "";
  let isFullScreen = false;
  let emailData = null;

  // Audio handling
  let mediaRecorder = null;
  let audioChunks = [];
  let audioStream = null;
  let ttsAudio = null;
  let recordingTimeout = null;

  // Auto-clear transcript timer (5 minutes)
  let lastActivityTime = Date.now();
  let clearTranscriptTimer = null;
  const AUTO_CLEAR_DELAY = 5 * 60 * 1000; // 5 minutes in milliseconds

  // Dashboard polling control
  let dashboardPaused = false;

  // Reset activity timer and schedule auto-clear
  function resetActivityTimer() {
    lastActivityTime = Date.now();

    // Clear existing timer
    if (clearTranscriptTimer) {
      clearTimeout(clearTranscriptTimer);
    }

    // Schedule new auto-clear
    clearTranscriptTimer = setTimeout(() => {
      // Clear transcript after inactivity
      userInput = "";
      aiResponse = "";
      console.log("[KIOSK] Transcript auto-cleared after 5 minutes of inactivity");
    }, AUTO_CLEAR_DELAY);
  }

  onDestroy(() => {
    // Cleanup
    if (mediaRecorder && mediaRecorder.state !== "inactive") {
      mediaRecorder.stop();
    }
    if (audioStream) {
      audioStream.getTracks().forEach(track => track.stop());
    }
    if (recordingTimeout) {
      clearTimeout(recordingTimeout);
    }
    if (clearTranscriptTimer) {
      clearTimeout(clearTranscriptTimer);
    }
  });

  // Start listening for user input
  async function startListening() {
    try {
      // Clear previous conversation before starting new recording
      userInput = "";
      aiResponse = "";

      // Reset activity timer
      resetActivityTimer();

      // Pause dashboard polling during conversation
      dashboardPaused = true;

      state = "listening";

      // Get microphone access
      audioStream = await navigator.mediaDevices.getUserMedia({ audio: true });

      // Setup media recorder
      mediaRecorder = new MediaRecorder(audioStream);
      audioChunks = [];

      mediaRecorder.ondataavailable = (event) => {
        audioChunks.push(event.data);
      };

      mediaRecorder.onstop = async () => {
        const audioBlob = new Blob(audioChunks, { type: "audio/webm" });
        await transcribeAudio(audioBlob);
      };

      mediaRecorder.start();

      // Auto-stop after 30 seconds
      recordingTimeout = setTimeout(() => {
        stopListening();
      }, 30000);

    } catch (error) {
      console.error("Failed to start listening:", error);
      statusText = "Microphone access denied";
      state = "idle";
    }
  }

  // Stop listening
  function stopListening() {
    if (recordingTimeout) {
      clearTimeout(recordingTimeout);
    }
    if (mediaRecorder && mediaRecorder.state !== "inactive") {
      mediaRecorder.stop();
    }
    if (audioStream) {
      audioStream.getTracks().forEach(track => track.stop());
      audioStream = null;
    }
  }

  // Transcribe audio using STT
  async function transcribeAudio(audioBlob) {
    try {
      state = "processing";
      statusText = "Processing...";

      // Use the existing speechToText API function
      const data = await speechToText(audioBlob, "webm");
      userInput = data.text;

      // Send message to THEO
      await sendMessage(data.text);

    } catch (error) {
      console.error("Transcription error:", error);
      statusText = "Failed to transcribe audio";
      state = "idle";
    }
  }

  // Send message and get response
  async function sendMessage(text) {
    try {
      let fullResponse = "";

      await streamMessage({
        text,
        sessionId,
        onToken: (token) => {
          fullResponse += token;
          aiResponse = fullResponse;
        },
        onEnd: async (meta) => {
          // Response complete, play TTS
          await playTTS(fullResponse);
        },
        onError: (error) => {
          console.error("Message error:", error);
          statusText = "Error getting response";
          state = "idle";
        }
      });

    } catch (error) {
      console.error("Send message error:", error);
      statusText = "Failed to send message";
      state = "idle";
    }
  }

  // Play TTS audio
  async function playTTS(text) {
    try {
      state = "speaking";
      statusText = "Speaking...";

      // Get user's voice preference from localStorage (same as Chat.svelte)
      const voice = localStorage.getItem("theo.voice") || "alloy";
      const speed = parseFloat(localStorage.getItem("theo.speed") || "1.0");

      // Use the existing textToSpeech API function with user preferences
      const audioBlob = await textToSpeech(text, voice, speed);
      const audioUrl = URL.createObjectURL(audioBlob);

      ttsAudio = new Audio(audioUrl);

      ttsAudio.onended = () => {
        // Return to idle state (keep userInput and aiResponse for dialogue persistence)
        state = "idle";

        // Resume dashboard polling
        dashboardPaused = false;

        // Reset activity timer (starts 5-minute countdown to auto-clear)
        resetActivityTimer();
      };

      ttsAudio.play();

    } catch (error) {
      console.error("TTS error:", error);
      statusText = "Failed to play response";
      state = "idle";
    }
  }

  // Exit kiosk mode
  function exitKiosk() {
    dispatch("exit");
  }

  // Toggle full-screen
  function toggleFullScreen() {
    if (!isFullScreen) {
      const elem = document.documentElement;
      if (elem.requestFullscreen) {
        elem.requestFullscreen();
      } else if (elem.webkitRequestFullscreen) {
        elem.webkitRequestFullscreen();
      }
      isFullScreen = true;
    } else {
      if (document.exitFullscreen) {
        document.exitFullscreen();
      } else if (document.webkitExitFullscreen) {
        document.webkitExitFullscreen();
      }
      isFullScreen = false;
    }
  }

  // Handle visualizer click
  function handleVisualizerClick() {
    if (state === "idle") {
      startListening();
    } else if (state === "listening") {
      stopListening();
    }
    // Do nothing if processing or speaking
  }

  // Handle visualizer keyboard interaction (accessibility)
  function handleVisualizerKeydown(event) {
    if (event.key === "Enter" || event.key === " ") {
      event.preventDefault();
      handleVisualizerClick();
    }
  }
</script>

<div class="kiosk-container">
  <!-- Top Controls: Close, Fullscreen, Email -->
  <div class="kiosk-controls">
    <button class="kiosk-control-btn" on:click={exitKiosk} title="Exit Kiosk Mode">
      ✕
    </button>
    <button class="kiosk-control-btn" on:click={toggleFullScreen} title="Toggle Full Screen">
      {isFullScreen ? "⛶" : "⛶"}
    </button>
    {#if emailData && emailData.unread_count > 0}
      <div class="email-control-badge">
        <svg class="email-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <rect x="2" y="4" width="20" height="16" rx="2"/>
          <path d="m22 7-8.97 5.7a1.94 1.94 0 0 1-2.06 0L2 7"/>
        </svg>
        <span class="email-count">{emailData.unread_count}</span>
      </div>
    {/if}
  </div>

  <!-- Two Column Layout -->
  <div class="main-layout">
    <!-- Left Column: Visualizer + Transcript -->
    <div class="left-panel">
      <!-- Audio Visualizer (clickable) -->
      <div class="kiosk-visualizer" on:click={handleVisualizerClick} role="button" tabindex="0" on:keydown={handleVisualizerKeydown}>
        <AudioVisualizer {state} {audioStream} audioElement={ttsAudio} />
      </div>

      <!-- Transcript Display (shown during speaking and persists after) -->
      {#if userInput || aiResponse}
        <div class="kiosk-transcript fade-in">
          {#if userInput}
            <div class="user-message">
              <strong>You:</strong> {userInput}
            </div>
          {/if}
          {#if aiResponse}
            <div class="ai-message">
              <strong>THEO:</strong> {aiResponse}
            </div>
          {/if}
        </div>
      {/if}
    </div>

    <!-- Right Column: Dashboard Widgets -->
    <div class="right-panel">
      <DashboardWidgets paused={dashboardPaused} bind:emailData />
    </div>
  </div>
</div>

<style>
  .kiosk-container {
    background: var(--kiosk-bg, #0a0a0a);
    color: var(--kiosk-text-primary, #e0e0e0);
    height: 100vh;
    width: 100vw;
    position: fixed;
    top: 0;
    left: 0;
    z-index: 9999;
    overflow: hidden;
    display: flex;
    flex-direction: column;
  }

  .kiosk-controls {
    position: absolute;
    top: 20px;
    left: 20px;
    display: flex;
    gap: 12px;
    z-index: 10000;
  }

  .main-layout {
    flex: 1;
    display: grid;
    grid-template-columns: 1fr 480px;
    gap: 2rem;
    padding: 2rem;
    min-height: 0;
  }

  .left-panel {
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    gap: 2.5rem;
    padding: 1rem;
  }

  .right-panel {
    display: flex;
    flex-direction: column;
    padding: 1rem 0;
    overflow-y: auto;
    overflow-x: hidden;
  }

  /* Custom scrollbar for right panel */
  .right-panel::-webkit-scrollbar {
    width: 6px;
  }

  .right-panel::-webkit-scrollbar-track {
    background: rgba(255, 255, 255, 0.03);
    border-radius: 3px;
  }

  .right-panel::-webkit-scrollbar-thumb {
    background: rgba(0, 255, 255, 0.2);
    border-radius: 3px;
  }

  .right-panel::-webkit-scrollbar-thumb:hover {
    background: rgba(0, 255, 255, 0.3);
  }

  .kiosk-control-btn {
    background: var(--kiosk-card-bg, rgba(20, 20, 30, 0.6));
    border: 1px solid var(--kiosk-card-border, rgba(100, 255, 255, 0.2));
    padding: 12px 20px;
    border-radius: 8px;
    color: #fff;
    cursor: pointer;
    font-size: 1.2rem;
    transition: all 0.3s ease;
    backdrop-filter: blur(10px);
  }

  .kiosk-control-btn:hover {
    background: rgba(255, 255, 255, 0.15);
    border-color: rgba(100, 255, 255, 0.4);
    box-shadow: var(--kiosk-glow, 0 0 20px rgba(0, 255, 255, 0.3));
  }

  .email-control-badge {
    display: flex;
    align-items: center;
    gap: 0.5rem;
    padding: 10px 16px;
    background: rgba(239, 68, 68, 0.15);
    border: 1px solid rgba(239, 68, 68, 0.3);
    border-radius: 8px;
    backdrop-filter: blur(10px);
    animation: email-pulse 2s ease-in-out infinite;
  }

  @keyframes email-pulse {
    0%, 100% {
      box-shadow: 0 0 10px rgba(239, 68, 68, 0.3);
      border-color: rgba(239, 68, 68, 0.3);
    }
    50% {
      box-shadow: 0 0 20px rgba(239, 68, 68, 0.6);
      border-color: rgba(239, 68, 68, 0.6);
    }
  }

  .email-icon {
    width: 18px;
    height: 18px;
    color: #ef4444;
  }

  .email-count {
    font-size: 1rem;
    font-weight: 600;
    color: #ef4444;
    font-family: 'Aptos', monospace;
  }

  .kiosk-visualizer {
    flex-shrink: 0;
    cursor: pointer;
    user-select: none;
    -webkit-user-select: none;
    outline: none;
  }

  .kiosk-visualizer:focus-visible {
    outline: 2px solid var(--kiosk-accent-cyan, #00ffff);
    outline-offset: 4px;
    border-radius: 50%;
  }

  .kiosk-transcript {
    width: 100%;
    padding: 1rem 0;
    max-height: 350px;
    overflow-y: auto;
  }

  /* Custom Scrollbar (minimal) */
  .kiosk-transcript::-webkit-scrollbar {
    width: 4px;
  }

  .kiosk-transcript::-webkit-scrollbar-track {
    background: transparent;
  }

  .kiosk-transcript::-webkit-scrollbar-thumb {
    background: rgba(0, 255, 255, 0.2);
    border-radius: 2px;
  }

  .kiosk-transcript::-webkit-scrollbar-thumb:hover {
    background: rgba(0, 255, 255, 0.4);
  }

  .user-message,
  .ai-message {
    margin: 1rem 0;
    line-height: 1.7;
    font-size: 1.05rem;
    font-family: 'Aptos', sans-serif;
  }

  .user-message {
    color: #34d399; /* Green */
  }

  .user-message strong {
    font-weight: 600;
    color: #10b981;
  }

  .ai-message {
    color: #c4b5fd; /* Light purple */
  }

  .ai-message strong {
    font-weight: 600;
    color: #a78bfa;
  }

  .manual-wake-btn {
    background: rgba(99, 102, 241, 0.2);
    border: 2px solid rgba(99, 102, 241, 0.5);
    padding: 18px 40px;
    border-radius: 12px;
    color: #fff;
    cursor: pointer;
    font-size: 1.3rem;
    font-weight: 500;
    transition: all 0.3s ease;
    backdrop-filter: blur(10px);
    box-shadow: 0 4px 12px rgba(99, 102, 241, 0.2);
  }

  .manual-wake-btn:hover:not(:disabled) {
    background: rgba(99, 102, 241, 0.3);
    border-color: rgba(99, 102, 241, 0.7);
    box-shadow: 0 6px 20px rgba(99, 102, 241, 0.4);
    transform: translateY(-2px);
  }

  .manual-wake-btn:disabled {
    opacity: 0.5;
    cursor: not-allowed;
  }

  .stop-btn {
    background: rgba(239, 68, 68, 0.2);
    border: 2px solid rgba(239, 68, 68, 0.5);
    animation: pulse 1.5s ease-in-out infinite;
  }

  .stop-btn:hover {
    background: rgba(239, 68, 68, 0.3);
    border-color: rgba(239, 68, 68, 0.7);
  }

  @keyframes pulse {
    0%, 100% {
      opacity: 1;
      box-shadow: 0 4px 12px rgba(239, 68, 68, 0.2);
    }
    50% {
      opacity: 0.8;
      box-shadow: 0 6px 20px rgba(239, 68, 68, 0.4);
    }
  }

  @keyframes fade-in {
    from {
      opacity: 0;
      transform: translateY(20px);
    }
    to {
      opacity: 1;
      transform: translateY(0);
    }
  }

  .fade-in {
    animation: fade-in 0.6s cubic-bezier(0.4, 0, 0.2, 1);
  }

  /* Responsive Scaling for Small Screens (7" displays) - Shrink, don't reflow */
  @media (max-width: 1024px) {
    .kiosk-container {
      font-size: 14px; /* Base font scaling */
    }

    .main-layout {
      grid-template-columns: 1fr 360px; /* Narrower right panel */
      gap: 1.5rem;
      padding: 1.5rem;
    }

    .left-panel {
      gap: 1.5rem;
    }
  }

  /* Responsive scaling for short screens (vertical constraint) */
  @media (max-height: 700px) {
    .kiosk-container {
      font-size: 13px;
    }

    .main-layout {
      gap: 1rem;
      padding: 1rem;
    }

    .left-panel {
      gap: 1rem;
    }

    .right-panel {
      overflow-y: auto;
    }

    .kiosk-controls {
      top: 12px;
      left: 12px;
      gap: 8px;
    }

    .kiosk-control-btn {
      padding: 8px 14px;
      font-size: 1rem;
    }

    .email-control-badge {
      padding: 8px 12px;
    }

    .email-count {
      font-size: 0.85rem;
    }

    .kiosk-transcript {
      max-height: 220px;
      padding: 0.75rem 0;
    }

    .user-message,
    .ai-message {
      font-size: 0.95rem;
      margin: 0.75rem 0;
    }
  }

  /* Extra Small Screens (7" displays in landscape) - Further scaling */
  @media (max-width: 768px) {
    .kiosk-container {
      font-size: 12px; /* Even smaller base font */
    }

    .main-layout {
      grid-template-columns: 1fr 300px; /* Even narrower right panel */
      gap: 1rem;
      padding: 1rem;
    }

    .kiosk-controls {
      top: 8px;
      left: 8px;
      gap: 6px;
    }

    .kiosk-control-btn {
      padding: 6px 12px;
      font-size: 0.9rem;
    }

    .email-control-badge {
      padding: 6px 10px;
    }

    .email-count {
      font-size: 0.8rem;
    }

    .kiosk-transcript {
      max-height: 180px;
      padding: 0.5rem 0;
    }

    .user-message,
    .ai-message {
      font-size: 0.9rem;
      line-height: 1.4;
    }
  }
</style>
