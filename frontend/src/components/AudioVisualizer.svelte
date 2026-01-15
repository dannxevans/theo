<script>
  import { onMount, onDestroy } from "svelte";

  export let state = "idle"; // "idle" | "listening" | "processing" | "speaking"
  export let audioStream = null; // MediaStream for listening state
  export let audioElement = null; // Audio element for speaking state

  let canvas;
  let ctx;
  let animationFrameId;
  let analyser = null;
  let dataArray = null;
  let bufferLength = 0;

  // Audio context for visualization
  let audioContext = null;

  // Initialize canvas
  onMount(() => {
    if (!canvas) return;
    ctx = canvas.getContext("2d");
    animate();
  });

  onDestroy(() => {
    if (animationFrameId) {
      cancelAnimationFrame(animationFrameId);
    }
    if (audioContext) {
      audioContext.close();
    }
  });

  // Setup audio analyser when audio stream changes
  $: if (audioStream && state === "listening") {
    setupAnalyser(audioStream);
  } else if (audioElement && state === "speaking") {
    setupAnalyserFromElement(audioElement);
  } else {
    cleanupAnalyser();
  }

  function setupAnalyser(stream) {
    try {
      cleanupAnalyser();
      audioContext = new (window.AudioContext || window.webkitAudioContext)();
      analyser = audioContext.createAnalyser();
      analyser.fftSize = 256;
      bufferLength = analyser.frequencyBinCount;
      dataArray = new Uint8Array(bufferLength);

      const source = audioContext.createMediaStreamSource(stream);
      source.connect(analyser);
    } catch (error) {
      console.error("Failed to setup analyser:", error);
    }
  }

  function setupAnalyserFromElement(element) {
    try {
      cleanupAnalyser();
      audioContext = new (window.AudioContext || window.webkitAudioContext)();
      analyser = audioContext.createAnalyser();
      analyser.fftSize = 256;
      bufferLength = analyser.frequencyBinCount;
      dataArray = new Uint8Array(bufferLength);

      const source = audioContext.createMediaElementSource(element);
      source.connect(analyser);
      analyser.connect(audioContext.destination); // Connect to speakers
    } catch (error) {
      console.error("Failed to setup analyser from element:", error);
    }
  }

  function cleanupAnalyser() {
    if (audioContext) {
      audioContext.close();
      audioContext = null;
    }
    analyser = null;
    dataArray = null;
  }

  // Main animation loop
  function animate() {
    if (!ctx || !canvas) return;

    ctx.clearRect(0, 0, canvas.width, canvas.height);

    switch (state) {
      case "idle":
        drawIdleAnimation();
        break;
      case "listening":
        drawListeningAnimation();
        break;
      case "processing":
        drawProcessingAnimation();
        break;
      case "speaking":
        drawSpeakingAnimation();
        break;
    }

    animationFrameId = requestAnimationFrame(animate);
  }

  // Idle: Gentle pulsing circle
  let idlePulse = 0;
  function drawIdleAnimation() {
    const centerX = canvas.width / 2;
    const centerY = canvas.height / 2;
    const baseRadius = 80;
    const pulse = Math.sin(idlePulse * 0.02) * 10;
    idlePulse++;

    // Draw pulsing circle
    ctx.beginPath();
    ctx.arc(centerX, centerY, baseRadius + pulse, 0, Math.PI * 2);
    ctx.fillStyle = "rgba(99, 102, 241, 0.3)"; // Indigo
    ctx.fill();

    // Inner circle
    ctx.beginPath();
    ctx.arc(centerX, centerY, (baseRadius + pulse) * 0.6, 0, Math.PI * 2);
    ctx.fillStyle = "rgba(99, 102, 241, 0.6)";
    ctx.fill();
  }

  // Listening: Reactive audio bars
  function drawListeningAnimation() {
    if (!analyser || !dataArray) {
      drawIdleAnimation();
      return;
    }

    analyser.getByteFrequencyData(dataArray);

    const centerX = canvas.width / 2;
    const centerY = canvas.height / 2;
    const barCount = 32;
    const radius = 100;

    for (let i = 0; i < barCount; i++) {
      const angle = (i / barCount) * Math.PI * 2;
      const amplitude = dataArray[i * Math.floor(bufferLength / barCount)] || 0;
      const barHeight = (amplitude / 255) * 60 + 20;

      const x1 = centerX + Math.cos(angle) * radius;
      const y1 = centerY + Math.sin(angle) * radius;
      const x2 = centerX + Math.cos(angle) * (radius + barHeight);
      const y2 = centerY + Math.sin(angle) * (radius + barHeight);

      ctx.beginPath();
      ctx.moveTo(x1, y1);
      ctx.lineTo(x2, y2);
      ctx.strokeStyle = `rgba(34, 197, 94, ${0.5 + amplitude / 512})`; // Green
      ctx.lineWidth = 4;
      ctx.stroke();
    }
  }

  // Processing: Rotating spinner
  let processingRotation = 0;
  function drawProcessingAnimation() {
    const centerX = canvas.width / 2;
    const centerY = canvas.height / 2;
    const radius = 80;
    const segments = 12;

    processingRotation += 0.05;

    for (let i = 0; i < segments; i++) {
      const angle = (i / segments) * Math.PI * 2 + processingRotation;
      const opacity = 0.2 + (i / segments) * 0.6;

      ctx.beginPath();
      ctx.arc(
        centerX + Math.cos(angle) * radius,
        centerY + Math.sin(angle) * radius,
        8,
        0,
        Math.PI * 2
      );
      ctx.fillStyle = `rgba(251, 191, 36, ${opacity})`; // Amber
      ctx.fill();
    }
  }

  // Speaking: Reactive audio bars (similar to listening)
  function drawSpeakingAnimation() {
    if (!analyser || !dataArray) {
      drawProcessingAnimation();
      return;
    }

    analyser.getByteFrequencyData(dataArray);

    const centerX = canvas.width / 2;
    const centerY = canvas.height / 2;
    const barCount = 32;
    const radius = 100;

    for (let i = 0; i < barCount; i++) {
      const angle = (i / barCount) * Math.PI * 2;
      const amplitude = dataArray[i * Math.floor(bufferLength / barCount)] || 0;
      const barHeight = (amplitude / 255) * 60 + 20;

      const x1 = centerX + Math.cos(angle) * radius;
      const y1 = centerY + Math.sin(angle) * radius;
      const x2 = centerX + Math.cos(angle) * (radius + barHeight);
      const y2 = centerY + Math.sin(angle) * (radius + barHeight);

      ctx.beginPath();
      ctx.moveTo(x1, y1);
      ctx.lineTo(x2, y2);
      ctx.strokeStyle = `rgba(139, 92, 246, ${0.5 + amplitude / 512})`; // Purple
      ctx.lineWidth = 4;
      ctx.stroke();
    }
  }
</script>

<canvas bind:this={canvas} width="400" height="400" class="visualizer-canvas" />

<style>
  .visualizer-canvas {
    display: block;
    margin: 0 auto;
  }
</style>
