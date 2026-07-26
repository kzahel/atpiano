"use strict";

const OUTPUT_BLOCK_FRAMES = 2048;

class AtpianoCaptureProcessor extends AudioWorkletProcessor {
  constructor() {
    super();
    this.pending = new Float32Array(OUTPUT_BLOCK_FRAMES);
    this.pendingFrames = 0;
    this.emittedFrames = 0;
    this.recording = true;
    this.port.onmessage = (event) => {
      if (event.data.type !== "stop" || !this.recording) return;
      this.recording = false;
      this.flush();
      this.port.postMessage({
        type: "stopped",
        frameCount: this.emittedFrames,
      });
    };
  }

  flush() {
    if (this.pendingFrames === 0) return;
    const output = this.pending.slice(0, this.pendingFrames);
    this.port.postMessage(
      {
        type: "chunk",
        firstSample: this.emittedFrames,
        workletTime: currentTime,
        samples: output.buffer,
      },
      [output.buffer],
    );
    this.emittedFrames += this.pendingFrames;
    this.pendingFrames = 0;
  }

  process(inputs) {
    if (!this.recording) return false;
    const channel = inputs[0]?.[0];
    if (!channel) return true;
    let offset = 0;
    while (offset < channel.length) {
      const accepted = Math.min(
        channel.length - offset,
        OUTPUT_BLOCK_FRAMES - this.pendingFrames,
      );
      this.pending.set(
        channel.subarray(offset, offset + accepted),
        this.pendingFrames,
      );
      this.pendingFrames += accepted;
      offset += accepted;
      if (this.pendingFrames === OUTPUT_BLOCK_FRAMES) this.flush();
    }
    return true;
  }
}

registerProcessor("atpiano-capture", AtpianoCaptureProcessor);
