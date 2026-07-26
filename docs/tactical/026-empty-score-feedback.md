# 026 — Empty Score Feedback

Topic: performance-to-notation

Status: **implemented on 2026-07-26.**

## Outcome

Explain an empty corrected piano result directly instead of presenting it as
an unexplained score-rendering failure.

## Retained Evidence

Public microphone session `20260726T180605-f9d34a1edc29` contains 13.096
seconds of humming. Basic Pitch produced provisional pitch feedback, but the
after-Stop piano-specific Transkun decode completed successfully with zero
native events. It retracted the remaining provisional notes, leaving a valid
empty committed MIDI. MIDI2ScoreTransformer did not run because there were no
closed committed notes to convert.

## Implementation

- Raise a user-facing empty-input explanation at the score snapshot boundary:
  **No completed piano notes were detected, so there is nothing to score.**
- Preserve and display the score job's actual error message in the score card.
- Retain the generic fallback only when a failed job has no message.
- Leave the current piano-only corrected-model boundary unchanged.

## Validation

- The score snapshot test covers an empty committed prefix.
- The shared React application test covers the exact failed-job message and
  proves the generic rendering-failed copy is absent.
- The existing polling-failure test proves other score-job errors also reach
  the card without trapping the rest of session review.
- The retained humming session is used for a public API check after restarting
  the live service.
