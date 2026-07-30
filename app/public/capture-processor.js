"use strict";

const OUTPUT_BLOCK_FRAMES = 2048;

class AtpianoCaptureProcessor extends AudioWorkletProcessor {
  constructor() {
    super();
    this.pending = new Float32Array(OUTPUT_BLOCK_FRAMES);
    this.pendingFrames = 0;
    this.emittedFrames = 0;
    this.recording = true;
    this.renderQuantumCount = 0;
    this.renderQuantumFramesMinimum = null;
    this.renderQuantumFramesMaximum = 0;
    this.capturedInputFrames = 0;
    this.missingInputQuantumCount = 0;
    this.missingInputFrames = 0;
    this.expectedRenderFrame = null;
    this.renderClockGapCount = 0;
    this.renderClockMissingFrames = 0;
    this.renderClockRepeatedFrames = 0;
    this.previousSample = null;
    this.boundaryJumpMaximum = 0;
    this.insideQuantumJumpMaximum = 0;
    this.boundaryJumpCounts = {
      ge_0_05: 0,
      ge_0_1: 0,
      ge_0_2: 0,
    };
    this.insideQuantumJumpCounts = {
      ge_0_05: 0,
      ge_0_1: 0,
      ge_0_2: 0,
    };
    this.zeroFrames = new Float32Array(OUTPUT_BLOCK_FRAMES);
    this.port.onmessage = (event) => {
      if (event.data.type !== "stop" || !this.recording) return;
      this.recording = false;
      this.flush();
      this.port.postMessage({
        type: "stopped",
        frameCount: this.emittedFrames,
        diagnostics: this.diagnostics(),
      });
    };
  }

  observeJump(jump, counts) {
    if (jump >= 0.05) counts.ge_0_05 += 1;
    if (jump >= 0.1) counts.ge_0_1 += 1;
    if (jump >= 0.2) counts.ge_0_2 += 1;
  }

  observeSamples(samples) {
    if (samples.length === 0) return;
    if (this.previousSample !== null) {
      const jump = Math.abs(samples[0] - this.previousSample);
      this.boundaryJumpMaximum = Math.max(this.boundaryJumpMaximum, jump);
      this.observeJump(jump, this.boundaryJumpCounts);
    }
    for (let index = 1; index < samples.length; index += 1) {
      const jump = Math.abs(samples[index] - samples[index - 1]);
      this.insideQuantumJumpMaximum = Math.max(
        this.insideQuantumJumpMaximum,
        jump,
      );
      this.observeJump(jump, this.insideQuantumJumpCounts);
    }
    this.previousSample = samples[samples.length - 1];
  }

  append(samples) {
    this.observeSamples(samples);
    let offset = 0;
    while (offset < samples.length) {
      const accepted = Math.min(
        samples.length - offset,
        OUTPUT_BLOCK_FRAMES - this.pendingFrames,
      );
      this.pending.set(
        samples.subarray(offset, offset + accepted),
        this.pendingFrames,
      );
      this.pendingFrames += accepted;
      offset += accepted;
      if (this.pendingFrames === OUTPUT_BLOCK_FRAMES) this.flush();
    }
  }

  diagnostics() {
    return {
      schema_version: "atpiano.browser-audio-worklet.v1",
      sample_rate_hz: sampleRate,
      output_block_frames: OUTPUT_BLOCK_FRAMES,
      render_quantum_count: this.renderQuantumCount,
      render_quantum_frames: {
        minimum: this.renderQuantumFramesMinimum,
        maximum: this.renderQuantumFramesMaximum,
      },
      captured_input_frame_count: this.capturedInputFrames,
      emitted_frame_count: this.emittedFrames,
      missing_input_quantum_count: this.missingInputQuantumCount,
      missing_input_frame_count: this.missingInputFrames,
      render_clock: {
        gap_count: this.renderClockGapCount,
        missing_frame_count: this.renderClockMissingFrames,
        repeated_frame_count: this.renderClockRepeatedFrames,
      },
      absolute_sample_jump: {
        at_quantum_boundary: {
          maximum: this.boundaryJumpMaximum,
          counts: this.boundaryJumpCounts,
        },
        inside_quantum: {
          maximum: this.insideQuantumJumpMaximum,
          counts: this.insideQuantumJumpCounts,
        },
      },
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

  process(inputs, outputs) {
    if (!this.recording) return false;
    const channel = inputs[0]?.[0];
    const quantumFrames = channel?.length ?? outputs[0]?.[0]?.length ?? 0;
    this.renderQuantumCount += 1;
    this.renderQuantumFramesMinimum = Math.min(
      this.renderQuantumFramesMinimum ?? quantumFrames,
      quantumFrames,
    );
    this.renderQuantumFramesMaximum = Math.max(
      this.renderQuantumFramesMaximum,
      quantumFrames,
    );
    if (
      this.expectedRenderFrame !== null &&
      currentFrame !== this.expectedRenderFrame
    ) {
      this.renderClockGapCount += 1;
      if (currentFrame > this.expectedRenderFrame) {
        this.renderClockMissingFrames += currentFrame - this.expectedRenderFrame;
      } else {
        this.renderClockRepeatedFrames += this.expectedRenderFrame - currentFrame;
      }
    }
    this.expectedRenderFrame = currentFrame + quantumFrames;
    if (channel) {
      this.capturedInputFrames += channel.length;
      this.append(channel);
    } else if (quantumFrames > 0) {
      this.missingInputQuantumCount += 1;
      this.missingInputFrames += quantumFrames;
      const silence = quantumFrames <= this.zeroFrames.length
        ? this.zeroFrames.subarray(0, quantumFrames)
        : new Float32Array(quantumFrames);
      this.append(silence);
    }
    return true;
  }
}

registerProcessor("atpiano-capture", AtpianoCaptureProcessor);
