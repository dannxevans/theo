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

  // Idle: 3D Particle Sphere (similar to reference image)
  let idlePulse = 0;
  let particles = [];

  // Initialize particles for sphere
  function initParticles() {
    particles = [];
    const particleCount = 800;
    const radius = 90; // Reduced from 100 to give more space from border

    for (let i = 0; i < particleCount; i++) {
      // Fibonacci sphere distribution for even particle placement
      const phi = Math.acos(1 - 2 * (i + 0.5) / particleCount);
      const theta = Math.PI * (1 + Math.sqrt(5)) * i;

      particles.push({
        x: radius * Math.sin(phi) * Math.cos(theta),
        y: radius * Math.sin(phi) * Math.sin(theta),
        z: radius * Math.cos(phi),
        originalX: radius * Math.sin(phi) * Math.cos(theta),
        originalY: radius * Math.sin(phi) * Math.sin(theta),
        originalZ: radius * Math.cos(phi)
      });
    }
  }

  function drawIdleAnimation() {
    if (particles.length === 0) initParticles();

    const centerX = canvas.width / 2;
    const centerY = canvas.height / 2;
    const time = idlePulse * 0.01;
    idlePulse++;

    const borderRadius = 170; // Even larger circle

    // Draw background circle (more visible dark background)
    ctx.fillStyle = 'rgba(15, 15, 25, 0.6)';
    ctx.beginPath();
    ctx.arc(centerX, centerY, borderRadius, 0, Math.PI * 2);
    ctx.fill();

    // Rotation angles
    const rotationY = time * 0.3;
    const rotationX = Math.sin(time * 0.2) * 0.2;

    // Draw particles
    particles.forEach((p, i) => {
      // Apply wave deformation
      const wave = Math.sin(time * 2 + i * 0.01) * 8;
      const x = p.originalX + wave;
      const y = p.originalY + wave;
      const z = p.originalZ + wave;

      // 3D rotation (Y-axis)
      const rotatedX = x * Math.cos(rotationY) - z * Math.sin(rotationY);
      const rotatedZ = x * Math.sin(rotationY) + z * Math.cos(rotationY);

      // 3D rotation (X-axis)
      const finalY = y * Math.cos(rotationX) - rotatedZ * Math.sin(rotationX);
      const finalZ = y * Math.sin(rotationX) + rotatedZ * Math.cos(rotationX);

      // Perspective projection
      const perspective = 300;
      const scale = perspective / (perspective + finalZ);
      const screenX = centerX + rotatedX * scale;
      const screenY = centerY + finalY * scale;

      // Calculate depth-based color and size
      const depth = (finalZ + 150) / 300; // Normalize 0-1
      const size = 1.2 + depth * 1;

      // Gradient from cyan to purple based on depth
      const cyan = Math.floor(0 + depth * 168);
      const green = Math.floor(255 - depth * 170);
      const blue = Math.floor(255 - depth * 8);
      const alpha = 0.6 + depth * 0.4;

      // Draw sharp particle (solid circle, no gradient for sharpness)
      ctx.fillStyle = `rgba(${cyan}, ${green}, ${blue}, ${alpha})`;
      ctx.beginPath();
      ctx.arc(screenX, screenY, size, 0, Math.PI * 2);
      ctx.fill();
    });

    // Add center glow
    const glowSize = 60 + Math.sin(time * 2) * 10;
    const centerGlow = ctx.createRadialGradient(centerX, centerY, 0, centerX, centerY, glowSize);
    centerGlow.addColorStop(0, 'rgba(99, 102, 241, 0.4)');
    centerGlow.addColorStop(0.5, 'rgba(168, 85, 247, 0.2)');
    centerGlow.addColorStop(1, 'rgba(0, 255, 255, 0)');

    ctx.fillStyle = centerGlow;
    ctx.beginPath();
    ctx.arc(centerX, centerY, glowSize, 0, Math.PI * 2);
    ctx.fill();

    // Draw outer circle border (double thickness)
    ctx.strokeStyle = 'rgba(0, 255, 255, 0.4)';
    ctx.lineWidth = 6;
    ctx.beginPath();
    ctx.arc(centerX, centerY, borderRadius, 0, Math.PI * 2);
    ctx.stroke();
  }

  // Listening: Particle sphere with pulsing (audio reactive)
  function drawListeningAnimation() {
    if (particles.length === 0) initParticles();
    if (!analyser || !dataArray) {
      drawIdleAnimation();
      return;
    }

    analyser.getByteFrequencyData(dataArray);

    const centerX = canvas.width / 2;
    const centerY = canvas.height / 2;
    const time = idlePulse * 0.01;
    idlePulse++;

    // Calculate average audio amplitude
    const avgAmplitude = dataArray.reduce((sum, val) => sum + val, 0) / dataArray.length;
    const pulseScale = 1 + (avgAmplitude / 255) * 0.3;

    const borderRadius = 170 * pulseScale;

    // Draw background circle
    ctx.fillStyle = 'rgba(15, 15, 25, 0.6)';
    ctx.beginPath();
    ctx.arc(centerX, centerY, borderRadius, 0, Math.PI * 2);
    ctx.fill();

    const rotationY = time * 0.4;
    const rotationX = Math.sin(time * 0.3) * 0.2;

    particles.forEach((p, i) => {
      const wave = Math.sin(time * 2 + i * 0.01) * 8 * pulseScale;
      const x = p.originalX * pulseScale + wave;
      const y = p.originalY * pulseScale + wave;
      const z = p.originalZ * pulseScale + wave;

      const rotatedX = x * Math.cos(rotationY) - z * Math.sin(rotationY);
      const rotatedZ = x * Math.sin(rotationY) + z * Math.cos(rotationY);
      const finalY = y * Math.cos(rotationX) - rotatedZ * Math.sin(rotationX);
      const finalZ = y * Math.sin(rotationX) + rotatedZ * Math.cos(rotationX);

      const perspective = 300;
      const scale = perspective / (perspective + finalZ);
      const screenX = centerX + rotatedX * scale;
      const screenY = centerY + finalY * scale;

      const depth = (finalZ + 150) / 300;
      const size = (1.2 + depth * 1) * (1 + avgAmplitude / 512);

      // Green color for listening
      const red = Math.floor(34 + depth * 100);
      const green = Math.floor(197);
      const blue = Math.floor(94 + depth * 50);
      const alpha = 0.6 + depth * 0.4;

      // Draw sharp particle
      ctx.fillStyle = `rgba(${red}, ${green}, ${blue}, ${alpha})`;
      ctx.beginPath();
      ctx.arc(screenX, screenY, size, 0, Math.PI * 2);
      ctx.fill();
    });

    // Glowing center (green)
    const glowSize = (60 + Math.sin(time * 3) * 15) * pulseScale;
    const centerGlow = ctx.createRadialGradient(centerX, centerY, 0, centerX, centerY, glowSize);
    centerGlow.addColorStop(0, 'rgba(34, 197, 94, 0.5)');
    centerGlow.addColorStop(0.5, 'rgba(134, 239, 172, 0.2)');
    centerGlow.addColorStop(1, 'rgba(34, 197, 94, 0)');

    ctx.fillStyle = centerGlow;
    ctx.beginPath();
    ctx.arc(centerX, centerY, glowSize, 0, Math.PI * 2);
    ctx.fill();

    // Draw outer circle border (green, double thickness)
    ctx.strokeStyle = 'rgba(34, 197, 94, 0.5)';
    ctx.lineWidth = 6;
    ctx.beginPath();
    ctx.arc(centerX, centerY, borderRadius, 0, Math.PI * 2);
    ctx.stroke();
  }

  // Processing: Particle sphere with faster rotation (amber/yellow)
  let processingRotation = 0;
  function drawProcessingAnimation() {
    if (particles.length === 0) initParticles();

    const centerX = canvas.width / 2;
    const centerY = canvas.height / 2;
    const time = idlePulse * 0.01;
    idlePulse++;
    processingRotation += 0.05;

    const borderRadius = 170;

    // Draw background circle
    ctx.fillStyle = 'rgba(15, 15, 25, 0.6)';
    ctx.beginPath();
    ctx.arc(centerX, centerY, borderRadius, 0, Math.PI * 2);
    ctx.fill();

    const rotationY = processingRotation;
    const rotationX = Math.sin(time * 0.4) * 0.3;

    particles.forEach((p, i) => {
      const wave = Math.sin(time * 3 + i * 0.02) * 10;
      const x = p.originalX + wave;
      const y = p.originalY + wave;
      const z = p.originalZ + wave;

      const rotatedX = x * Math.cos(rotationY) - z * Math.sin(rotationY);
      const rotatedZ = x * Math.sin(rotationY) + z * Math.cos(rotationY);
      const finalY = y * Math.cos(rotationX) - rotatedZ * Math.sin(rotationX);
      const finalZ = y * Math.sin(rotationX) + rotatedZ * Math.cos(rotationX);

      const perspective = 300;
      const scale = perspective / (perspective + finalZ);
      const screenX = centerX + rotatedX * scale;
      const screenY = centerY + finalY * scale;

      const depth = (finalZ + 150) / 300;
      const size = 1.2 + depth * 1;

      // Amber/yellow color for processing
      const red = Math.floor(251);
      const green = Math.floor(191 - depth * 50);
      const blue = Math.floor(36 + depth * 100);
      const alpha = 0.6 + depth * 0.4;

      // Draw sharp particle
      ctx.fillStyle = `rgba(${red}, ${green}, ${blue}, ${alpha})`;
      ctx.beginPath();
      ctx.arc(screenX, screenY, size, 0, Math.PI * 2);
      ctx.fill();
    });

    // Glowing center (amber)
    const glowSize = 70 + Math.sin(time * 4) * 15;
    const centerGlow = ctx.createRadialGradient(centerX, centerY, 0, centerX, centerY, glowSize);
    centerGlow.addColorStop(0, 'rgba(251, 191, 36, 0.5)');
    centerGlow.addColorStop(0.5, 'rgba(252, 211, 77, 0.3)');
    centerGlow.addColorStop(1, 'rgba(251, 191, 36, 0)');

    ctx.fillStyle = centerGlow;
    ctx.beginPath();
    ctx.arc(centerX, centerY, glowSize, 0, Math.PI * 2);
    ctx.fill();

    // Draw outer circle border (amber, double thickness)
    ctx.strokeStyle = 'rgba(251, 191, 36, 0.5)';
    ctx.lineWidth = 6;
    ctx.beginPath();
    ctx.arc(centerX, centerY, borderRadius, 0, Math.PI * 2);
    ctx.stroke();
  }

  // Speaking: Particle sphere with audio reactive pulse (purple)
  function drawSpeakingAnimation() {
    if (particles.length === 0) initParticles();
    if (!analyser || !dataArray) {
      drawProcessingAnimation();
      return;
    }

    analyser.getByteFrequencyData(dataArray);

    const centerX = canvas.width / 2;
    const centerY = canvas.height / 2;
    const time = idlePulse * 0.01;
    idlePulse++;

    const avgAmplitude = dataArray.reduce((sum, val) => sum + val, 0) / dataArray.length;
    const pulseScale = 1 + (avgAmplitude / 255) * 0.4;

    const borderRadius = 170 * pulseScale;

    // Draw background circle
    ctx.fillStyle = 'rgba(15, 15, 25, 0.6)';
    ctx.beginPath();
    ctx.arc(centerX, centerY, borderRadius, 0, Math.PI * 2);
    ctx.fill();

    const rotationY = time * 0.35;
    const rotationX = Math.sin(time * 0.25) * 0.25;

    particles.forEach((p, i) => {
      const wave = Math.sin(time * 2.5 + i * 0.015) * 10 * pulseScale;
      const x = p.originalX * pulseScale + wave;
      const y = p.originalY * pulseScale + wave;
      const z = p.originalZ * pulseScale + wave;

      const rotatedX = x * Math.cos(rotationY) - z * Math.sin(rotationY);
      const rotatedZ = x * Math.sin(rotationY) + z * Math.cos(rotationY);
      const finalY = y * Math.cos(rotationX) - rotatedZ * Math.sin(rotationX);
      const finalZ = y * Math.sin(rotationX) + rotatedZ * Math.cos(rotationX);

      const perspective = 300;
      const scale = perspective / (perspective + finalZ);
      const screenX = centerX + rotatedX * scale;
      const screenY = centerY + finalY * scale;

      const depth = (finalZ + 150) / 300;
      const size = (1.2 + depth * 1) * (1 + avgAmplitude / 600);

      // Purple color for speaking
      const red = Math.floor(139 + depth * 80);
      const green = Math.floor(92 + depth * 100);
      const blue = Math.floor(246);
      const alpha = 0.6 + depth * 0.4;

      // Draw sharp particle
      ctx.fillStyle = `rgba(${red}, ${green}, ${blue}, ${alpha})`;
      ctx.beginPath();
      ctx.arc(screenX, screenY, size, 0, Math.PI * 2);
      ctx.fill();
    });

    // Glowing center (purple)
    const glowSize = (65 + Math.sin(time * 3.5) * 18) * pulseScale;
    const centerGlow = ctx.createRadialGradient(centerX, centerY, 0, centerX, centerY, glowSize);
    centerGlow.addColorStop(0, 'rgba(139, 92, 246, 0.6)');
    centerGlow.addColorStop(0.5, 'rgba(196, 181, 253, 0.3)');
    centerGlow.addColorStop(1, 'rgba(139, 92, 246, 0)');

    ctx.fillStyle = centerGlow;
    ctx.beginPath();
    ctx.arc(centerX, centerY, glowSize, 0, Math.PI * 2);
    ctx.fill();

    // Draw outer circle border (purple, double thickness)
    ctx.strokeStyle = 'rgba(139, 92, 246, 0.6)';
    ctx.lineWidth = 6;
    ctx.beginPath();
    ctx.arc(centerX, centerY, borderRadius, 0, Math.PI * 2);
    ctx.stroke();
  }
</script>

<canvas bind:this={canvas} width="400" height="400" class="visualizer-canvas" />

<style>
  .visualizer-canvas {
    display: block;
    margin: 0 auto;
    max-width: 100%;
    height: auto;
  }

  /* Responsive scaling for small screens */
  @media (max-width: 1024px) {
    .visualizer-canvas {
      width: 320px;
      height: 320px;
    }
  }

  @media (max-width: 768px) {
    .visualizer-canvas {
      width: 260px;
      height: 260px;
    }
  }

  /* Responsive scaling for short screens (vertical constraint) */
  @media (max-height: 700px) {
    .visualizer-canvas {
      width: 280px;
      height: 280px;
    }
  }

  @media (max-height: 600px) {
    .visualizer-canvas {
      width: 220px;
      height: 220px;
    }
  }
</style>
