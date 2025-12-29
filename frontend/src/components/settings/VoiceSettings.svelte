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

<div class="section">
  <h3>Voice Settings</h3>
  <p class="hint">Configure text-to-speech and speech-to-text preferences. Powered by OpenAI.</p>

  <!-- TTS Voice Selection with Test Buttons -->
  <div class="form-group">
    <label>Text-to-Speech Voice</label>
    <div class="voice-options">
      {#each availableVoices as voice}
        <div class="voice-option" class:selected={selectedVoice === voice.id}>
          <div class="voice-info">
            <label class="voice-radio">
              <input
                type="radio"
                name="voice"
                value={voice.id}
                bind:group={selectedVoice}
              />
              <span class="voice-details">
                <strong>{voice.name}</strong>
                <small>{voice.description}</small>
              </span>
            </label>
          </div>
          <button
            class="test-btn"
            class:testing={testingVoice === voice.id}
            on:click={() => testVoice(voice.id)}
            title={testingVoice === voice.id ? "Stop preview" : "Test voice"}
          >
            {testingVoice === voice.id ? "⏹️" : "▶️"}
          </button>
        </div>
      {/each}
    </div>
    <small>Choose the voice for reading messages aloud and test each one</small>
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

  <!-- Save Button -->
  <button class="btn-primary" on:click={saveVoiceSettings}>
    Save Voice Settings
  </button>

  {#if saveStatus}
    <div class="status-message" class:error={saveStatus.includes("must")}>
      {saveStatus}
    </div>
  {/if}
</div>

<!-- Usage Instructions -->
<div class="section">
  <h3>How to Use Voice Features</h3>

  <div class="info-box">
    <p><strong>🎤 Voice Input (Speech-to-Text):</strong></p>
    <ul>
      <li>Click the microphone button to start recording</li>
      <li>Speak your message</li>
      <li>Click the stop button (⏹️) to finish</li>
      <li>Your message will be transcribed and sent automatically</li>
    </ul>
  </div>

  <div class="info-box">
    <p><strong>🔊 Voice Output (Text-to-Speech):</strong></p>
    <ul>
      <li>Click the speaker button to toggle auto-read mode</li>
      <li>When enabled (highlighted), all assistant responses will be read aloud</li>
      <li>The voice and speed settings above control how messages sound</li>
    </ul>
  </div>
</div>

<style>
  .section {
    margin-bottom: 2rem;
  }

  h3 {
    font-size: 1.25rem;
    font-weight: 600;
    color: var(--text-primary);
    margin: 0 0 0.5rem 0;
  }

  .hint {
    font-size: 0.9rem;
    color: var(--text-secondary);
    margin: 0 0 1.5rem 0;
  }

  .form-group {
    margin-bottom: 1.5rem;
  }

  .form-group label {
    display: block;
    font-size: 0.95rem;
    font-weight: 500;
    color: var(--text-primary);
    margin-bottom: 0.5rem;
  }

  .form-group input[type="number"] {
    width: 100%;
    max-width: 400px;
    padding: 0.5rem;
    border: 1px solid var(--border-primary);
    border-radius: var(--radius-md);
    background: var(--bg-primary);
    color: var(--text-primary);
    font-size: 0.95rem;
  }

  .form-group small {
    display: block;
    margin-top: 0.25rem;
    font-size: 0.85rem;
    color: var(--text-secondary);
  }

  .voice-options {
    display: flex;
    flex-direction: column;
    gap: 0.75rem;
    margin-bottom: 0.5rem;
  }

  .voice-option {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 0.75rem;
    border: 2px solid var(--border-primary);
    border-radius: var(--radius-md);
    background: var(--bg-primary);
    transition: all 0.2s ease;
  }

  .voice-option:hover {
    border-color: var(--primary);
    background: var(--bg-secondary);
  }

  .voice-option.selected {
    border-color: var(--primary);
    background: var(--bg-secondary);
  }

  .voice-info {
    flex: 1;
  }

  .voice-radio {
    display: flex;
    align-items: center;
    gap: 0.75rem;
    cursor: pointer;
  }

  .voice-radio input[type="radio"] {
    width: 18px;
    height: 18px;
    cursor: pointer;
  }

  .voice-details {
    display: flex;
    flex-direction: column;
    gap: 0.25rem;
  }

  .voice-details strong {
    color: var(--text-primary);
    font-size: 0.95rem;
  }

  .voice-details small {
    color: var(--text-secondary);
    font-size: 0.85rem;
  }

  .test-btn {
    background: var(--bg-tertiary);
    border: 1px solid var(--border-primary);
    padding: 0.5rem 1rem;
    border-radius: var(--radius-md);
    font-size: 1.1rem;
    cursor: pointer;
    transition: all 0.2s ease;
    min-width: 3rem;
  }

  .test-btn:hover {
    background: var(--primary);
    border-color: var(--primary);
    color: white;
  }

  .test-btn.testing {
    background: var(--primary);
    border-color: var(--primary);
    color: white;
    animation: pulse 1.5s infinite;
  }

  @keyframes pulse {
    0%, 100% {
      opacity: 1;
    }
    50% {
      opacity: 0.7;
    }
  }

  .status-message {
    margin-top: 1rem;
    padding: 0.75rem;
    background: #d4edda;
    color: #155724;
    border-radius: var(--radius-md);
    font-size: 0.9rem;
  }

  .status-message.error {
    background: #f8d7da;
    color: #721c24;
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
