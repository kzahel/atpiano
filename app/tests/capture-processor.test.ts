import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";
import vm from "node:vm";

test("capture processor retains source time and reports quantum defects", async () => {
  const posted: unknown[] = [];
  let Processor: (new () => {
    port: {
      onmessage: ((event: { data: { type: string } }) => void) | null;
    };
    process(inputs: Float32Array[][], outputs: Float32Array[][]): boolean;
  }) | null = null;
  class AudioWorkletProcessor {
    readonly port = {
      onmessage: null as ((event: { data: { type: string } }) => void) | null,
      postMessage(message: unknown) {
        posted.push(message);
      },
    };
  }
  const scope = vm.createContext({
    AudioWorkletProcessor,
    Float32Array,
    Math,
    currentFrame: 0,
    currentTime: 0,
    sampleRate: 48_000,
    registerProcessor(
      name: string,
      constructor: typeof Processor,
    ) {
      assert.equal(name, "atpiano-capture");
      Processor = constructor;
    },
  });
  const source = await readFile(
    new URL("../public/capture-processor.js", import.meta.url),
    "utf8",
  );
  vm.runInContext(source, scope);
  assert.notEqual(Processor, null);
  const processor = new Processor!();
  const output = () => [[new Float32Array(128)]];

  processor.process([[new Float32Array(128)]], output());
  scope.currentFrame = 128;
  processor.process(
    [[Float32Array.from({ length: 128 }, () => 0.25)]],
    output(),
  );
  scope.currentFrame = 384;
  processor.process(
    [[Float32Array.from({ length: 128 }, () => 0.25)]],
    output(),
  );
  scope.currentFrame = 512;
  processor.process([], output());
  processor.port.onmessage?.({ data: { type: "stop" } });

  const stopped = posted.at(-1) as {
    type: string;
    frameCount: number;
    diagnostics: {
      captured_input_frame_count: number;
      emitted_frame_count: number;
      missing_input_quantum_count: number;
      missing_input_frame_count: number;
      render_clock: {
        gap_count: number;
        missing_frame_count: number;
      };
      absolute_sample_jump: {
        at_quantum_boundary: {
          maximum: number;
          counts: { ge_0_2: number };
        };
        inside_quantum: {
          counts: { ge_0_05: number };
        };
      };
    };
  };
  assert.equal(stopped.type, "stopped");
  assert.equal(stopped.frameCount, 512);
  assert.equal(stopped.diagnostics.captured_input_frame_count, 384);
  assert.equal(stopped.diagnostics.emitted_frame_count, 512);
  assert.equal(stopped.diagnostics.missing_input_quantum_count, 1);
  assert.equal(stopped.diagnostics.missing_input_frame_count, 128);
  assert.equal(stopped.diagnostics.render_clock.gap_count, 1);
  assert.equal(stopped.diagnostics.render_clock.missing_frame_count, 128);
  assert.equal(
    stopped.diagnostics.absolute_sample_jump.at_quantum_boundary.maximum,
    0.25,
  );
  assert.equal(
    stopped.diagnostics.absolute_sample_jump.at_quantum_boundary.counts.ge_0_2,
    2,
  );
  assert.equal(
    stopped.diagnostics.absolute_sample_jump.inside_quantum.counts.ge_0_05,
    0,
  );
});
