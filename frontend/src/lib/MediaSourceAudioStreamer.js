/**
 * MediaSource-based audio streamer for progressive TTS playback.
 *
 * Enables audio playback to start within 2-3 seconds instead of waiting
 * for complete audio file generation.
 */
export class MediaSourceAudioStreamer {
    constructor() {
        this.mediaSource = null;
        this.sourceBuffer = null;
        this.audio = null;
        this.queue = [];
        this.isAppending = false;
        this.hasStarted = false;
    }

    /**
     * Initialize MediaSource and Audio element.
     *
     * @returns {Promise<HTMLAudioElement>} Configured audio element
     */
    async initialize() {
        return new Promise((resolve, reject) => {
            // Create MediaSource
            this.mediaSource = new MediaSource();

            // Create Audio element
            this.audio = new Audio();
            this.audio.src = URL.createObjectURL(this.mediaSource);

            // Wait for MediaSource to open
            this.mediaSource.addEventListener('sourceopen', () => {
                try {
                    // Add SourceBuffer for MP3 audio
                    // Note: MIME type must match backend response
                    this.sourceBuffer = this.mediaSource.addSourceBuffer('audio/mpeg');

                    // Handle buffer updates
                    this.sourceBuffer.addEventListener('updateend', () => {
                        this.isAppending = false;
                        this.processQueue();
                    });

                    // Handle errors
                    this.sourceBuffer.addEventListener('error', (e) => {
                        console.error('[MediaSource] SourceBuffer error:', e);
                        reject(e);
                    });

                    resolve(this.audio);

                } catch (err) {
                    console.error('[MediaSource] Failed to add SourceBuffer:', err);
                    reject(err);
                }
            });

            this.mediaSource.addEventListener('sourceended', () => {
                console.log('[MediaSource] Source ended');
            });

            this.mediaSource.addEventListener('error', (e) => {
                console.error('[MediaSource] MediaSource error:', e);
                reject(e);
            });
        });
    }

    /**
     * Append audio chunk to the buffer.
     *
     * @param {Uint8Array} chunk - Audio data chunk
     */
    appendChunk(chunk) {
        // Add to queue
        this.queue.push(chunk);

        // Start playback after first chunk is buffered
        if (!this.hasStarted && this.queue.length === 1) {
            this.processQueue();
        } else if (!this.isAppending) {
            this.processQueue();
        }
    }

    /**
     * Process queued audio chunks.
     */
    processQueue() {
        // Don't process if already appending or queue is empty
        if (this.isAppending || this.queue.length === 0) {
            return;
        }

        // Don't append if source buffer is updating
        if (this.sourceBuffer.updating) {
            return;
        }

        try {
            // Get next chunk
            const chunk = this.queue.shift();

            // Append to buffer
            this.isAppending = true;
            this.sourceBuffer.appendBuffer(chunk);

            // Start playback after first chunk
            if (!this.hasStarted) {
                this.hasStarted = true;
                console.log('[MediaSource] Starting playback with first chunk');
                this.audio.play().catch(err => {
                    console.error('[MediaSource] Play failed:', err);
                });
            }

        } catch (err) {
            console.error('[MediaSource] Failed to append chunk:', err);
            this.isAppending = false;
        }
    }

    /**
     * Signal that all chunks have been sent.
     */
    finalize() {
        // Process any remaining queued chunks
        if (this.queue.length > 0) {
            console.log(`[MediaSource] Finalizing with ${this.queue.length} chunks remaining`);

            // Wait for queue to drain
            const checkQueue = () => {
                if (this.queue.length === 0 && !this.isAppending) {
                    this.endStream();
                } else {
                    setTimeout(checkQueue, 100);
                }
            };
            checkQueue();
        } else {
            this.endStream();
        }
    }

    /**
     * End the MediaSource stream.
     */
    endStream() {
        if (this.mediaSource.readyState === 'open') {
            try {
                this.mediaSource.endOfStream();
                console.log('[MediaSource] Stream ended');
            } catch (err) {
                console.error('[MediaSource] Failed to end stream:', err);
            }
        }
    }

    /**
     * Stop playback and cleanup resources.
     */
    stop() {
        if (this.audio) {
            this.audio.pause();
            this.audio.src = '';
        }

        if (this.mediaSource && this.mediaSource.readyState === 'open') {
            try {
                this.mediaSource.endOfStream();
            } catch (err) {
                // Ignore errors during cleanup
            }
        }

        this.queue = [];
        this.isAppending = false;
        this.hasStarted = false;

        console.log('[MediaSource] Stopped and cleaned up');
    }
}
