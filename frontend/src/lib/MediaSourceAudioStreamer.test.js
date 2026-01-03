/**
 * Tests for MediaSourceAudioStreamer.
 *
 * Note: These tests use mocks for MediaSource and Audio APIs
 * since they're not available in Node.js test environment.
 */

import { describe, it, expect, beforeEach, vi } from 'vitest';
import { MediaSourceAudioStreamer } from './MediaSourceAudioStreamer.js';

// Mock MediaSource and SourceBuffer
class MockSourceBuffer extends EventTarget {
    constructor() {
        super();
        this.updating = false;
        this.chunks = [];
    }

    appendBuffer(chunk) {
        this.updating = true;
        this.chunks.push(chunk);

        // Simulate async buffer update
        setTimeout(() => {
            this.updating = false;
            this.dispatchEvent(new Event('updateend'));
        }, 10);
    }
}

class MockMediaSource extends EventTarget {
    constructor() {
        super();
        this.readyState = 'closed';
        this.sourceBuffers = [];
    }

    addSourceBuffer(mimeType) {
        const buffer = new MockSourceBuffer();
        this.sourceBuffers.push(buffer);
        return buffer;
    }

    endOfStream() {
        this.readyState = 'ended';
    }
}

class MockAudio {
    constructor() {
        this.src = '';
        this.paused = true;
    }

    async play() {
        this.paused = false;
        return Promise.resolve();
    }

    pause() {
        this.paused = false;
    }
}

// Mock global objects
global.MediaSource = MockMediaSource;
global.Audio = MockAudio;
global.URL = {
    createObjectURL: () => 'blob:mock-url',
    revokeObjectURL: () => {}
};

describe('MediaSourceAudioStreamer', () => {
    let streamer;

    beforeEach(() => {
        streamer = new MediaSourceAudioStreamer();
    });

    it('initializes successfully', async () => {
        const initPromise = streamer.initialize();

        // Manually trigger sourceopen event
        setTimeout(() => {
            streamer.mediaSource.readyState = 'open';
            streamer.mediaSource.dispatchEvent(new Event('sourceopen'));
        }, 10);

        const audio = await initPromise;

        expect(audio).toBeInstanceOf(MockAudio);
        expect(streamer.mediaSource).toBeTruthy();
        expect(streamer.sourceBuffer).toBeTruthy();
    });

    it('queues chunks when appending', async () => {
        // Initialize first
        const initPromise = streamer.initialize();
        setTimeout(() => {
            streamer.mediaSource.readyState = 'open';
            streamer.mediaSource.dispatchEvent(new Event('sourceopen'));
        }, 10);
        await initPromise;

        // Append chunks
        const chunk1 = new Uint8Array([1, 2, 3]);
        const chunk2 = new Uint8Array([4, 5, 6]);

        streamer.appendChunk(chunk1);
        streamer.appendChunk(chunk2);

        // Initially chunks are queued
        expect(streamer.queue.length).toBeGreaterThan(0);
    });

    it('starts playback after first chunk', async () => {
        // Initialize
        const initPromise = streamer.initialize();
        setTimeout(() => {
            streamer.mediaSource.readyState = 'open';
            streamer.mediaSource.dispatchEvent(new Event('sourceopen'));
        }, 10);
        const audio = await initPromise;

        // Spy on play method
        const playSpy = vi.spyOn(audio, 'play');

        // Append first chunk
        const chunk = new Uint8Array([1, 2, 3]);
        streamer.appendChunk(chunk);

        // Wait for processing
        await new Promise(resolve => setTimeout(resolve, 50));

        // Verify play was called
        expect(playSpy).toHaveBeenCalled();
        expect(streamer.hasStarted).toBe(true);
    });

    it('processes queue correctly', async () => {
        // Initialize
        const initPromise = streamer.initialize();
        setTimeout(() => {
            streamer.mediaSource.readyState = 'open';
            streamer.mediaSource.dispatchEvent(new Event('sourceopen'));
        }, 10);
        await initPromise;

        // Append multiple chunks
        for (let i = 0; i < 5; i++) {
            streamer.appendChunk(new Uint8Array([i]));
        }

        // Wait for all chunks to process
        await new Promise(resolve => setTimeout(resolve, 200));

        // Verify chunks were appended to source buffer
        expect(streamer.sourceBuffer.chunks.length).toBeGreaterThan(0);
    });

    it('finalizes stream correctly', async () => {
        // Initialize
        const initPromise = streamer.initialize();
        setTimeout(() => {
            streamer.mediaSource.readyState = 'open';
            streamer.mediaSource.dispatchEvent(new Event('sourceopen'));
        }, 10);
        await initPromise;

        // Append and finalize
        streamer.appendChunk(new Uint8Array([1, 2, 3]));
        streamer.finalize();

        // Wait for finalization
        await new Promise(resolve => setTimeout(resolve, 200));

        // Verify stream ended
        expect(streamer.mediaSource.readyState).toBe('ended');
    });

    it('stops and cleans up resources', async () => {
        // Initialize
        const initPromise = streamer.initialize();
        setTimeout(() => {
            streamer.mediaSource.readyState = 'open';
            streamer.mediaSource.dispatchEvent(new Event('sourceopen'));
        }, 10);
        const audio = await initPromise;

        // Start playback
        streamer.appendChunk(new Uint8Array([1, 2, 3]));
        await new Promise(resolve => setTimeout(resolve, 50));

        // Stop
        streamer.stop();

        // Verify cleanup
        expect(audio.src).toBe('');
        expect(streamer.queue).toEqual([]);
        expect(streamer.isAppending).toBe(false);
        expect(streamer.hasStarted).toBe(false);
    });

    it('handles errors during initialization', async () => {
        // Create streamer with failing MediaSource
        const failingStreamer = new MediaSourceAudioStreamer();
        const initPromise = failingStreamer.initialize();

        // Simulate error
        setTimeout(() => {
            failingStreamer.mediaSource.dispatchEvent(new Event('error'));
        }, 10);

        // Verify error is propagated
        await expect(initPromise).rejects.toBeTruthy();
    });

    it('does not append when buffer is updating', async () => {
        // Initialize
        const initPromise = streamer.initialize();
        setTimeout(() => {
            streamer.mediaSource.readyState = 'open';
            streamer.mediaSource.dispatchEvent(new Event('sourceopen'));
        }, 10);
        await initPromise;

        // Set buffer to updating state
        streamer.sourceBuffer.updating = true;

        // Try to append chunk
        const initialQueueLength = streamer.queue.length;
        streamer.appendChunk(new Uint8Array([1, 2, 3]));

        // Process should be skipped because buffer is updating
        streamer.processQueue();

        // Queue should still have the chunk
        expect(streamer.queue.length).toBe(initialQueueLength + 1);
    });

    it('waits for queue to drain before ending stream', async () => {
        // Initialize
        const initPromise = streamer.initialize();
        setTimeout(() => {
            streamer.mediaSource.readyState = 'open';
            streamer.mediaSource.dispatchEvent(new Event('sourceopen'));
        }, 10);
        await initPromise;

        // Add multiple chunks and finalize immediately
        streamer.appendChunk(new Uint8Array([1]));
        streamer.appendChunk(new Uint8Array([2]));
        streamer.appendChunk(new Uint8Array([3]));
        streamer.finalize();

        // MediaSource should not end until queue is drained
        // Give it time to process
        await new Promise(resolve => setTimeout(resolve, 300));

        // Now stream should be ended
        expect(streamer.mediaSource.readyState).toBe('ended');
    });
});
