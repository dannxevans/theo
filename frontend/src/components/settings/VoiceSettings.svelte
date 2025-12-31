<script>
  import { onMount } from "svelte";
  import { getVoices, textToSpeech } from "../../lib/api.js";

  // Voice settings
  let selectedVoice = localStorage.getItem("theo.voice") || "alloy";
  let speechSpeed = parseFloat(localStorage.getItem("theo.speechSpeed")) || 1.0;
  let availableVoices = [];
  let saveStatus = null;
  let testingVoice = null; // Track which voice is being tested
  let currentAudio = null; // Current playing audio

  // Load available voices
  onMount(async () => {
    try {
      availableVoices = await getVoices();
    } catch (error) {
      console.error("Failed to load voices:", error);
    }
  });

  function saveVoiceSettings() {
    saveStatus = null;

    // Validate speed
    if (speechSpeed < 0.25 || speechSpeed > 4.0) {
      saveStatus = "Speed must be between 0.25 and 4.0";
      return;
    }

    // Save to localStorage
    localStorage.setItem("theo.voice", selectedVoice);
    localStorage.setItem("theo.speechSpeed", speechSpeed.toString());

    saveStatus = "Voice settings saved!";

    // Clear status after 3 seconds
    setTimeout(() => {
      saveStatus = null;
    }, 3000);
  }

  async function testVoice(voiceId) {
    // Stop any currently playing audio
    if (currentAudio) {
      currentAudio.pause();
      currentAudio = null;
    }

    if (testingVoice === voiceId) {
      // If already testing this voice, stop it
      testingVoice = null;
      return;
    }

    try {
      testingVoice = voiceId;

      // Sample text that showcases the voice
      const sampleText = "Hello! This is how I sound. I can help you with various tasks and answer your questions.";

      // Get audio from TTS API
      const audioBlob = await textToSpeech(sampleText, voiceId, speechSpeed);

      // Create audio element and play
      const audioUrl = URL.createObjectURL(audioBlob);
      currentAudio = new Audio(audioUrl);

      currentAudio.addEventListener("ended", () => {
        testingVoice = null;
        URL.revokeObjectURL(audioUrl);
        currentAudio = null;
      });

      currentAudio.addEventListener("error", () => {
        testingVoice = null;
        URL.revokeObjectURL(audioUrl);
        currentAudio = null;
      });

      await currentAudio.play();
    } catch (error) {
      console.error("Voice test error:", error);
      testingVoice = null;
      alert(`Failed to test voice: ${error.message}`);
    }
  }
</script>

<div class="tab-panel">
  <h2>Voice Settings</h2>
  <p class="subtitle">Configure text-to-speech and speech-to-text preferences. Powered by OpenAI.</p>

  <div class="section">
    <!-- TTS Voice Selection with Test Button -->
    <div class="form-group">
      <label for="voice-select">Text-to-Speech Voice</label>
      <div class="voice-select-container">
        <select
          id="voice-select"
          bind:value={selectedVoice}
        >
          {#each availableVoices as voice}
            <option value={voice.id}>
              {voice.name} - {voice.description}
            </option>
          {/each}
        </select>
        <button
          class="test-btn"
          class:testing={testingVoice}
          on:click={() => testVoice(selectedVoice)}
          title={testingVoice ? "Stop preview" : "Test voice"}
        >
          {#if testingVoice}
            <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
              <rect x="6" y="4" width="4" height="16"></rect>
              <rect x="14" y="4" width="4" height="16"></rect>
            </svg>
          {:else}
            <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
              <polygon points="5 3 19 12 5 21 5 3"></polygon>
            </svg>
          {/if}
        </button>
      </div>
      <small>Choose the voice for reading messages aloud</small>
    </div>

  <!-- Speech Speed -->
  <div class="form-group">
    <label for="speech-speed">Speech Speed</label>
    <input
      id="speech-speed"
      type="number"
      min="0.25"
      max="4.0"
      step="0.25"
      bind:value={speechSpeed}
    />
    <small>Speed multiplier (0.25 = very slow, 1.0 = normal, 4.0 = very fast)</small>
  </div>

    {#if saveStatus}
      <div class="save-status" class:success={saveStatus.includes("saved")} class:error={saveStatus.includes("must")}>
        {saveStatus}
      </div>
    {/if}

    <div class="form-actions">
      <button class="btn-primary" on:click={saveVoiceSettings}>
        Save Voice Settings
      </button>
    </div>
  </div>

  <!-- Usage Instructions -->
  <div class="section">
    <h3>How to Use Voice Features</h3>

    <div class="info-box">
      <p>
        <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="display: inline-block; vertical-align: middle; margin-right: 0.5rem;">
          <path d="M12 1a3 3 0 0 0-3 3v8a3 3 0 0 0 6 0V4a3 3 0 0 0-3-3z"></path>
          <path d="M19 10v2a7 7 0 0 1-14 0v-2"></path>
          <line x1="12" y1="19" x2="12" y2="23"></line>
          <line x1="8" y1="23" x2="16" y2="23"></line>
        </svg>
        <strong>Voice Input (Speech-to-Text):</strong>
      </p>
      <ul>
        <li>Click the microphone button to start recording</li>
        <li>Speak your message</li>
        <li>Click the stop button to finish</li>
        <li>Your message will be transcribed and sent automatically</li>
      </ul>
    </div>

    <div class="info-box">
      <p>
        <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="display: inline-block; vertical-align: middle; margin-right: 0.5rem;">
          <polygon points="11 5 6 9 2 9 2 15 6 15 11 19 11 5"></polygon>
          <path d="M19.07 4.93a10 10 0 0 1 0 14.14M15.54 8.46a5 5 0 0 1 0 7.07"></path>
        </svg>
        <strong>Voice Output (Text-to-Speech):</strong>
      </p>
      <ul>
        <li>Click the speaker button to toggle auto-read mode</li>
        <li>When enabled (highlighted), all assistant responses will be read aloud</li>
        <li>The voice and speed settings above control how messages sound</li>
      </ul>
    </div>
  </div>
</div>

<style>
  /* Most styles inherited from global CSS (.tab-panel, .section, .form-group, etc.) */

  .section {
    margin-bottom: 2rem;
  }

  h3 {
    font-size: 1.25rem;
    font-weight: 600;
    color: var(--text-primary);
    margin: 0 0 0.75rem 0;
  }

  .voice-select-container {
    display: flex;
    gap: 0.75rem;
    align-items: center;
  }

  select {
    flex: 1;
    max-width: 400px;
    padding: 0.5rem;
    border: 1px solid var(--border-primary);
    border-radius: var(--radius-md);
    background: var(--bg-primary);
    color: var(--text-primary);
    font-size: 0.95rem;
    cursor: pointer;
  }

  select:focus {
    outline: none;
    border-color: var(--primary);
  }

  .test-btn {
    display: flex;
    align-items: center;
    justify-content: center;
    background: var(--bg-tertiary);
    border: 1px solid var(--border-primary);
    padding: 0.5rem 0.75rem;
    border-radius: var(--radius-md);
    cursor: pointer;
    transition: all 0.2s ease;
    min-width: 2.5rem;
    height: 2.5rem;
  }

  .test-btn:hover {
    background: var(--primary);
    border-color: var(--primary);
  }

  .test-btn:hover svg {
    stroke: white;
  }

  .test-btn.testing {
    background: var(--primary);
    border-color: var(--primary);
    animation: pulse 1.5s infinite;
  }

  .test-btn.testing svg {
    stroke: white;
  }

  @keyframes pulse {
    0%, 100% {
      opacity: 1;
    }
    50% {
      opacity: 0.7;
    }
  }

  .info-box {
    background: var(--bg-tertiary);
    padding: 1rem;
    border-radius: var(--radius-md);
    margin-bottom: 1rem;
  }

  .info-box p {
    margin: 0 0 0.5rem 0;
    font-weight: 500;
    color: var(--text-primary);
    display: flex;
    align-items: center;
  }

  .info-box ul {
    margin: 0;
    padding-left: 1.5rem;
  }

  .info-box li {
    margin-bottom: 0.5rem;
    color: var(--text-secondary);
    line-height: 1.5;
  }
</style>
