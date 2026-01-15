<script>
  import { onDestroy } from "svelte";
  import { createEventDispatcher } from "svelte";
  import AudioVisualizer from "./AudioVisualizer.svelte";
  import { streamMessage, speechToText, textToSpeech } from "../lib/api.js";

  const dispatch = createEventDispatcher();

  export let sessionId = null;

  // State management
  let state = "idle"; // "idle" | "listening" | "processing" | "speaking"
  let statusText = "Tap to Speak";
  let userInput = "";
  let aiResponse = "";
  let isFullScreen = false;

  // Audio handling
  let mediaRecorder = null;
  let audioChunks = [];
  let audioStream = null;
  let ttsAudio = null;
  let recordingTimeout = null;

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
  });

  // Start listening for user input
  async function startListening() {
    try {
      // Clear previous conversation before starting new recording
      userInput = "";
      aiResponse = "";

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

  // Handle tap to speak
  function handleTapToSpeak() {
    if (state === "idle") {
      startListening();
    }
  }
</script>

<div class="kiosk-container">
  <!-- Exit and Fullscreen buttons -->
  <div class="kiosk-controls">
    <button class="kiosk-control-btn" on:click={toggleFullScreen} title="Toggle Full Screen">
      {isFullScreen ? "⛶" : "⛶"}
    </button>
    <button class="kiosk-control-btn" on:click={exitKiosk} title="Exit Kiosk Mode">
      ✕
    </button>
  </div>

  <!-- Audio Visualizer -->
  <div class="kiosk-visualizer">
    <AudioVisualizer {state} {audioStream} audioElement={ttsAudio} />
  </div>

  <!-- Tap to speak / Stop button (above transcript, hidden when speaking) -->
  {#if state !== "speaking"}
    {#if state === "listening"}
      <button class="manual-wake-btn stop-btn" on:click={stopListening}>
        Stop Recording
      </button>
    {:else}
      <button class="manual-wake-btn" on:click={handleTapToSpeak} disabled={state !== "idle"}>
        Tap to Speak
      </button>
    {/if}
  {/if}

  <!-- Transcript Display (shown during speaking and persists after) -->
  {#if userInput || aiResponse}
    <div class="kiosk-transcript">
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

<style>
  .kiosk-container {
    background: #0a0a0a;
    color: #e0e0e0;
    height: 100vh;
    width: 100vw;
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    position: fixed;
    top: 0;
    left: 0;
    z-index: 9999;
    overflow: hidden;
  }

  .kiosk-controls {
    position: absolute;
    top: 20px;
    left: 20px;
    display: flex;
    gap: 12px;
    z-index: 10000;
  }

  .kiosk-control-btn {
    background: rgba(255, 255, 255, 0.1);
    border: none;
    padding: 12px 20px;
    border-radius: 8px;
    color: #fff;
    cursor: pointer;
    font-size: 1.2rem;
    transition: background 0.2s;
  }

  .kiosk-control-btn:hover {
    background: rgba(255, 255, 255, 0.2);
  }

  .kiosk-visualizer {
    margin: 2rem;
  }

  .kiosk-transcript {
    max-width: 800px;
    padding: 2rem;
    background: rgba(255, 255, 255, 0.05);
    border-radius: 16px;
    opacity: 0.95;
    margin: 2rem auto;
    max-height: 300px;
    overflow-y: auto;
  }

  .user-message,
  .ai-message {
    margin: 0.75rem 0;
    line-height: 1.6;
    font-size: 1.1rem;
  }

  .user-message {
    color: #34d399; /* Green */
  }

  .ai-message {
    color: #a78bfa; /* Purple */
  }

  .manual-wake-btn {
    background: rgba(99, 102, 241, 0.2);
    border: 2px solid rgba(99, 102, 241, 0.5);
    padding: 18px 40px;
    border-radius: 12px;
    color: #fff;
    cursor: pointer;
    font-size: 1.3rem;
    transition: all 0.2s;
    margin-bottom: 2rem;
  }

  .manual-wake-btn:hover:not(:disabled) {
    background: rgba(99, 102, 241, 0.3);
    border-color: rgba(99, 102, 241, 0.7);
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
    }
    50% {
      opacity: 0.7;
    }
  }
</style>
