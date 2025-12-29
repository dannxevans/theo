<script>
  import { textToSpeech, speechToText } from "../lib/api.js";

  // Props
  export let onTranscript = null; // Callback when STT produces text
  export let selectedVoice = "alloy"; // Voice for TTS
  export let speechSpeed = 1.0; // TTS speed
  export let autoReadEnabled = false; // TTS auto-read toggle state
  export let isSpeaking = false; // Export speaking state

  // State
  let isRecording = false;
  let mediaRecorder = null;
  let audioChunks = [];
  let currentAudio = null;

  /**
   * Start recording audio from microphone
   */
  async function startRecording() {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });

      // Create media recorder
      mediaRecorder = new MediaRecorder(stream);
      audioChunks = [];

      mediaRecorder.addEventListener("dataavailable", (event) => {
        audioChunks.push(event.data);
      });

      mediaRecorder.addEventListener("stop", async () => {
        const audioBlob = new Blob(audioChunks, { type: "audio/webm" });

        // Transcribe
        try {
          const result = await speechToText(audioBlob, "webm");

          if (result.text && onTranscript) {
            onTranscript(result.text);
          }
        } catch (error) {
          console.error("Transcription error:", error);
          alert(`Transcription failed: ${error.message}`);
        } finally {
          // Stop all tracks to release microphone
          stream.getTracks().forEach(track => track.stop());
        }
      });

      mediaRecorder.start();
      isRecording = true;
    } catch (error) {
      console.error("Microphone access error:", error);
      alert("Failed to access microphone. Please grant permission.");
    }
  }

  /**
   * Stop recording
   */
  function stopRecording() {
    if (mediaRecorder && isRecording) {
      mediaRecorder.stop();
      isRecording = false;
    }
  }

  /**
   * Toggle TTS auto-read mode
   */
  function toggleAutoRead() {
    autoReadEnabled = !autoReadEnabled;
  }

  /**
   * Speak text using TTS
   */
  export async function speak(text) {
    if (!text || isSpeaking) return;

    try {
      isSpeaking = true;

      // Stop any currently playing audio
      if (currentAudio) {
        currentAudio.pause();
        currentAudio = null;
      }

      // Get audio from TTS API
      const audioBlob = await textToSpeech(text, selectedVoice, speechSpeed);

      // Create audio element and play
      const audioUrl = URL.createObjectURL(audioBlob);
      currentAudio = new Audio(audioUrl);

      currentAudio.addEventListener("ended", () => {
        isSpeaking = false;
        URL.revokeObjectURL(audioUrl);
        currentAudio = null;
      });

      currentAudio.addEventListener("error", () => {
        isSpeaking = false;
        URL.revokeObjectURL(audioUrl);
        currentAudio = null;
      });

      await currentAudio.play();
    } catch (error) {
      console.error("TTS error:", error);
      alert(`Speech synthesis failed: ${error.message}`);
      isSpeaking = false;
    }
  }

  /**
   * Stop speaking
   */
  export function stopSpeaking() {
    if (currentAudio) {
      currentAudio.pause();
      currentAudio = null;
      isSpeaking = false;
    }
  }
</script>

<div class="voice-controls">
  <!-- Microphone button for STT -->
  <button
    class="voice-btn"
    on:click={() => isRecording ? stopRecording() : startRecording()}
    title={isRecording ? "Stop recording" : "Start recording"}
    aria-label={isRecording ? "Stop recording" : "Start recording"}
  >
    {#if isRecording}
      <svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="currentColor">
        <rect x="6" y="6" width="12" height="12" rx="2"/>
      </svg>
    {:else}
      <svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
        <path d="M12 2a3 3 0 0 0-3 3v7a3 3 0 0 0 6 0V5a3 3 0 0 0-3-3Z"/>
        <path d="M19 10v2a7 7 0 0 1-14 0v-2"/>
        <line x1="12" y1="19" x2="12" y2="22"/>
      </svg>
    {/if}
  </button>

  <!-- Speaker toggle button for TTS auto-read -->
  <button
    class="voice-btn"
    on:click={toggleAutoRead}
    title={autoReadEnabled ? "Disable auto-read" : "Enable auto-read"}
    aria-label={autoReadEnabled ? "Disable auto-read" : "Enable auto-read"}
  >
    {#if autoReadEnabled || isSpeaking}
      <svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
        <polygon points="11 5 6 9 2 9 2 15 6 15 11 19 11 5"/>
        <path d="M15.54 8.46a5 5 0 0 1 0 7.07"/>
        <path d="M19.07 4.93a10 10 0 0 1 0 14.14"/>
      </svg>
    {:else}
      <svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
        <polygon points="11 5 6 9 2 9 2 15 6 15 11 19 11 5"/>
        <line x1="22" y1="9" x2="16" y2="15"/>
        <line x1="16" y1="9" x2="22" y2="15"/>
      </svg>
    {/if}
  </button>
</div>

<style>
  .voice-controls {
    display: flex;
    gap: 0.5rem;
    align-items: center;
  }

  .voice-btn {
    background: var(--bg-secondary);
    border: 1px solid var(--border-primary);
    border-radius: var(--radius-md);
    padding: 0.5rem;
    font-size: 1.2rem;
    cursor: pointer;
    transition: all 0.2s ease;
    display: flex;
    align-items: center;
    justify-content: center;
    min-width: 2.5rem;
    height: 2.5rem;
  }

  .voice-btn svg {
    color: var(--text-secondary);
  }

  .voice-btn:hover {
    background: var(--bg-primary);
    border-color: var(--primary);
  }

  .voice-btn:hover svg {
    color: var(--primary);
  }
</style>
