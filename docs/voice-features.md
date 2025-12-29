# Voice Features User Guide

## Overview

THEO includes comprehensive voice capabilities powered by OpenAI:
- **Text-to-Speech (TTS)**: Listen to THEO's responses with 6 premium voices
- **Speech-to-Text (STT)**: Speak your messages instead of typing

## Quick Start

### Configuration

1. Navigate to **Settings** → **Voice**
2. Select your preferred voice from 6 options
3. Adjust speech speed (0.25x - 4.0x)
4. Click **Save Voice Settings**

### Using Voice Features

**Auto-Read Mode:**
- Click the speaker icon in the chat input
- When enabled (sound waves icon), THEO automatically reads responses
- Click "Speaking..." button to stop playback

**Voice Input:**
- Click the microphone icon
- Speak your message
- Click again to stop recording
- Review transcription and send

## Available Voices

| Voice | Type | Description |
|-------|------|-------------|
| Alloy | Neutral | Balanced voice (default) |
| Echo | Male | Clear and articulate |
| Fable | Male | Warm and friendly |
| Onyx | Male | Deep and authoritative |
| Nova | Female | Energetic and engaging |
| Shimmer | Female | Soft and gentle |

## UI Controls

### Voice Buttons

**Microphone (STT):**
- Idle: Microphone icon
- Recording: Stop square icon
- Hover: Icon turns blue

**Speaker (Auto-Read):**
- Disabled: Speaker with X
- Enabled: Speaker with sound waves
- Hover: Icon turns blue

### Send Button States

- **Send** (Blue): Ready to send
- **Thinking...** (Blue): Processing
- **Streaming...** (Red): Receiving response
- **Speaking...** (Orange): Audio playing - click to stop

## Troubleshooting

### Audio Doesn't Play
1. Check browser audio isn't muted
2. Verify OpenAI API key configured
3. Interact with page first (autoplay policy)
4. Refresh page

### Microphone Not Working
1. Grant microphone permissions
2. Check microphone not in use
3. Verify hardware connection
4. Try different browser

### Transcription Inaccurate
1. Speak clearly at normal pace
2. Reduce background noise
3. Move closer to microphone
4. Use quality microphone

## API Costs

- **TTS**: ~$15 per 1 million characters
- **STT**: ~$0.006 per minute
- Typical usage: $1-5/month

## Browser Support

- Chrome 80+ ✓
- Firefox 75+ ✓
- Safari 14+ ✓
- Edge 80+ ✓

## Privacy

- Audio sent to OpenAI for processing
- Not stored by THEO
- Review [OpenAI Privacy Policy](https://openai.com/privacy)

## Technical Details

For implementation details, see `voice-implementation-summary.md`

---

**Last Updated**: December 29, 2025
