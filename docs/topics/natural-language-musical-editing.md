# Natural-Language Musical Editing

Topic: natural-language-musical-editing

Status: proposed product and interaction direction as of 2026-07-29. This
topic records a shared, selection-scoped correction and composition workflow
for Atpiano Notebook and Play. It is not evidence that manual note editing,
score editing, speech recognition, natural-language command parsing, or
model-assisted correction has been implemented or validated.

## Scope And Relationship

This topic owns the user-facing operation:

```text
select musical context
        |
        v
say, type, play, or choose the intended change
        |
        v
inspect and audition a structured proposal
        |
        v
accept a new version or reject it
```

It includes:

- selection of notes, score symbols, source-time ranges, measures, or parts;
- typed or spoken musical instructions;
- deterministic and model-assisted parsing into structured edit operations;
- explicit separation of performance correction, notation interpretation,
  and creative arrangement;
- before-and-after visual and audible preview;
- ambiguity, undo, provenance, and versioning; and
- progressive disclosure between playful and professional composer surfaces.

[`live-acoustic-transcription.md`](live-acoustic-transcription.md) owns raw
audio, model-native events, revisions, source time, and automated correction.
A user correction may add another evidence layer but never rewrites that
history.

[`performance-to-notation.md`](performance-to-notation.md) owns beat, meter,
quantization, tuplets, spelling, staff, voice, and MusicXML interpretation.
This topic supplies user intent and structured overrides to that pipeline; it
does not make a language model the notation engine.

[`generative-musical-response-and-accompaniment.md`](generative-musical-response-and-accompaniment.md)
owns generated answers, accompaniments, variations, and renders. This topic
owns how the player requests and revises them.

[`playful-piano-learning.md`](playful-piano-learning.md) owns the child-facing
world and learning progression.
[`practice-companion-product-vision.md`](practice-companion-product-vision.md)
owns the professional musical notebook. The two surfaces may share selection,
edit, artifact, audition, and undo primitives without sharing the same chrome
or vocabulary.

Every implementation slice should receive a tactical. This topic does not
authorize uploading source audio to a language-model service or permitting
free-form commands to mutate stored artifacts.

## Motivation

Automatic transcription and notation will sometimes be wrong. A conventional
score editor can correct the result, but it asks the player to translate a
musical intention into tool modes, palettes, voices, durations, and cursor
operations before fixing a small local problem.

A more direct adult-studio interaction is:

1. highlight the questionable note or passage;
2. say **This should be a triplet; I think the middle note is missing**;
3. let Atpiano inspect the selection, source audio, transcript, beat grid, and
   score mapping;
4. show the one or two concrete interpretations it can support;
5. audition the source and proposed result; and
6. accept one as a new correction or score version.

If the player knows the exact answer, an instruction such as **Insert E4
between these two notes** should be even more direct. The application need not
pretend to infer what the user has already supplied.

The same interaction can become a composer:

- **Make these notes a question and let the duck answer.**
- **Put a gentle Alberti bass under these four measures.**
- **Try this melody as a waltz.**
- **Move the bird's answer up an octave.**
- **Keep my timing, but make the accompaniment simpler.**

The promise is not general conversation. It is low-friction, inspectable
musical editing grounded in a concrete selection.

## Three Different Edit Targets

The first design question is not what the sentence means. It is which layer
the player intends to change.

| Target | User claim | Representative operation | Authority |
| --- | --- | --- | --- |
| Performance correction | The captured note evidence does not match what I played | Insert, delete, repitch, retime, or resize a corrected event | User-authored correction beside immutable raw evidence |
| Notation interpretation | The performance is right but the written representation is wrong | Set triplet grouping, meter, beat, spelling, voice, hand, clef, tie, or gesture | New score interpretation mapped to the same source |
| Creative composition | I want to change or add music | Add, move, transform, harmonize, orchestrate, or generate material | New user-authored or generated derivative |

These operations may look similar. **It is missing the middle note** could
mean:

- the acoustic model failed to detect a note that was performed;
- all performed notes exist, but the score omitted or grouped one
  incorrectly;
- the player wants to add a note now, regardless of the original
  performance; or
- the player wants the system to propose a musically plausible note.

Atpiano must not collapse those meanings. When the selection and words do not
resolve the target confidently, it should present a small choice such as
**Correct what I played**, **Rewrite the score**, or **Change the music**.

## Selection Is The Primary Prompt

Natural language becomes substantially safer and more useful when most
context is selected rather than described.

A selection may contain:

- source session and moment;
- exact source-sample range;
- transcript event identities and revisions;
- score artifact, measure, voice, and score-note identities;
- arrangement part and generated-artifact identity;
- current playback position;
- neighboring notes, beat, key, and meter hypotheses; and
- the active performer and editing surface.

The language command adds intent to that context. **Make this a triplet** over
three selected score notes is tractable. The same sentence with no selection
inside a forty-minute session is not.

Selection should work from synchronized audio, piano roll, keyboard, score,
and composer views. A player may lasso a passage on the piano roll, click a
notehead in the score, mark a time range while listening, or select an icon in
Play. Each view should resolve to shared musical identities when the evidence
supports that mapping.

## Structured Proposal Contract

A language model may help interpret words, but the application should execute
only a bounded structured proposal. A conceptual proposal contains:

```text
target layer
selected artifact and musical identities
operation kind
explicit parameters
inferred parameters and alternatives
source evidence inspected
confidence and unresolved questions
before/after audible preview
before/after visual diff
provenance
```

Representative operation kinds include:

- `performance.insert_note`;
- `performance.change_pitch`;
- `performance.delete_event`;
- `notation.group_as_tuplet`;
- `notation.set_meter`;
- `notation.respell_pitch`;
- `notation.assign_voice`;
- `composition.insert_note`;
- `composition.transform_selection`;
- `arrangement.add_pattern`; and
- `arrangement.replace_part`.

These names are illustrative, not an accepted API.

Every proposal should state its effect in direct language:

> Add a user-supplied E4 halfway between these two source attacks, then
> regenerate the score from a new corrected-event version. Raw audio and
> model events remain unchanged.

or:

> Keep all performed notes unchanged. Write the selected three notes as an
> eighth-note triplet in the current score interpretation.

The default action is **Preview**, not **Apply**. Acceptance creates a new
artifact version with ordinary undo or return-to-version behavior. A rejected
proposal should leave no musical mutation.

## Performance Correction

A manual correction is a claim by the player about the performance. It should
retain:

- author and creation time;
- selected source range;
- raw events it supersedes or supplements;
- exact user-supplied values;
- any model-proposed values;
- the source audio reviewed;
- the accepted operation; and
- downstream artifacts derived from that correction version.

If a note was genuinely played but missed, a specialized pitch/onset process
may inspect the selected audio window and rank candidates. The language model
may orchestrate that tool and explain the result; it must not invent acoustic
evidence.

When the user supplies **F-sharp 4**, that pitch is a manual assertion rather
than a newly detected model event. If the time remains ambiguous, Atpiano can
ask the player to place it, infer one or more positions from neighboring
onsets, or let the player press the intended note during looped playback.

Spoken note names require confirmation because short names such as B, C, D,
and E are easily confused. Playing the desired pitch on a MIDI keyboard or
auditioning the proposed piano key can be faster and safer than another
spoken exchange.

## Notation Correction

Notation commands change an interpretation, not the source performance.
Useful commands include:

- **These three notes are a triplet.**
- **The first note is a pickup.**
- **This passage is in six-eight, not three-four.**
- **Keep these notes in the right hand but use two voices.**
- **Spell that as G-flat.**
- **That was a rolled chord, not four separate voices.**
- **Start the bass clef at this measure.**

The converter should receive explicit structured overrides and regenerate a
versioned score. It should preserve source-to-score mappings, mark inserted or
unmatched score notes honestly, and show which automatic assumptions the
override displaced.

Not every change should require regeneration of the entire score. The future
edit algebra should distinguish:

- safe local MusicXML transformations;
- local semantic edits that require measure-level reflow;
- passage-level reinterpretation with overlap and reconciliation; and
- global assumptions such as meter or first downbeat that may invalidate the
  remainder.

That distinction must be established by implementation evidence. Natural
language does not make a structurally global edit local.

## Creative And Arrangement Editing

A composer surface may start from a captured phrase, corrected transcript,
score selection, MIDI performance, or newly placed notes. Creative edits
produce a derivative and never claim to be corrections unless the player
explicitly changes target.

Useful shared operations include:

- move, copy, delete, or resize a note;
- replay or loop a phrase;
- transpose a selection;
- change one rhythm or ending;
- add a chord, bass, percussion, or countermelody part;
- apply a named deterministic accompaniment pattern;
- ask for bounded alternatives; and
- return to the source melody alone.

The Play surface may present notes as characters, creatures, colored shapes,
or instrument icons. Notebook may present the same material as score,
piano-roll, parts, source alignment, and detailed properties. The underlying
musical identities and edit history can be shared even when progressive
disclosure makes the two experiences feel very different.

This provides a bridge rather than two unrelated editors:

```text
Play composer                       Notebook studio
-------------                       ---------------
creatures and funny sounds   <-->   notes, voices, and instruments
drag and tap                 <-->   score and piano-roll selection
musical costumes             <-->   arrangement patterns and parameters
simple replay               <-->   source-aligned audition and comparison
```

A tune created in Play can therefore open later in Notebook without being
flattened into audio. An adult can correct recognition, inspect notation, or
develop the arrangement; a child returning to Play still sees the familiar
version rather than professional editing controls.

## Language-Model Boundary

The language model is an intent parser, tool orchestrator, and explainer. It
may:

- resolve selection-aware references such as **this note** or **the middle
  one**;
- map ordinary language to supported operations;
- identify that two interpretations remain plausible;
- request specialized audio or symbolic analysis;
- populate a structured proposal;
- explain the audible and notational difference; and
- remember user-approved terminology or interaction preferences.

It must not:

- mutate a source, correction, score, or arrangement directly;
- invent notes that it claims were present in the recording;
- silently choose between performance, notation, and composition;
- output unchecked MusicXML as the sole edit representation;
- infer an exact pitch from ambiguous speech without confirmation;
- hide a global re-engraving behind a seemingly local command; or
- make capture, playback, ordinary selection, or deterministic editing depend
  on a hosted language service.

Common exact operations should work without a language model. Menu actions,
keyboard commands, direct manipulation, and a small local grammar provide an
offline baseline and an accessible fallback. A model should earn its place on
commands that are genuinely easier to express conversationally.

## Voice And Privacy

Speech is optional. The same command field should accept typing, and direct
musical manipulation may be preferable for many edits.

For voice input:

- push-to-talk should make capture boundaries obvious;
- local speech recognition is preferred for private sessions;
- the interface must distinguish command audio from piano source audio;
- command recordings should not be retained by default;
- hosted recognition requires explicit disclosure and consent; and
- the recognized text must be visible and editable before it becomes intent.

A child-facing surface should not invite open-ended conversation or retain a
voice history merely to enable composer commands. Caregiver and studio
policies remain controlling.

## Recommended Experiments

1. **Direct note correction:** select one piano-roll event, change its pitch
   through a keyboard, note-name field, or MIDI key, preview it against the
   source, and save a new manual-correction version without language.
2. **Missing-note insertion:** select two neighboring attacks, insert an exact
   pitch between them, adjust or infer its time, and validate raw-versus-
   corrected provenance and downstream regeneration.
3. **Triplet interpretation:** select three mapped score notes, apply a
   structured tuplet override, regenerate a score variant, and confirm that
   source events remain unchanged.
4. **Command grammar:** add a small typed grammar for exact selection-scoped
   operations such as pitch change, deletion, triplet grouping, transposition,
   and deterministic accompaniment.
5. **Natural-language adapter:** translate broader typed commands into the
   same proposal schema, compare them with the grammar, and require preview
   and explicit acceptance.
6. **Voice adapter:** only after typed value is demonstrated, measure musical
   note-name accuracy, correction burden, privacy behavior, and end-to-end
   command latency.
7. **Shared composer view:** open one tune in a Play presentation and a
   Notebook presentation, apply edits through both, and prove common artifact
   identity, version history, and reversible progressive disclosure.

Each experiment should test ambiguous cases and rejected proposals, not only
successful commands.

## Success Evidence

Promising evidence includes:

- a player fixes a local error faster than in an external notation editor;
- the player can predict which layer will change;
- before-and-after audition catches a wrong proposal before acceptance;
- raw performance, correction, score, and arrangement remain distinguishable;
- accepted changes survive regeneration and export;
- ambiguous commands produce useful bounded choices rather than silent edits;
- common exact edits remain available fully offline; and
- the Play-to-Notebook transition preserves both delight and inspectability.

Measure command attempts, clarification count, time to accepted edit, undo
rate, wrong-layer rate, source-mapping preservation, and subjective trust.
Language-model fluency by itself is not success.

## Open Questions

- What selection gestures work equally well on score, piano roll, audio, and
  a playful composer?
- Which performance corrections should affect future score generation by
  default, and which should remain an alternative take on the evidence?
- How should inserted-note timing be proposed from a triplet instruction
  without treating a musical guess as an acoustic fact?
- Which operations form the smallest stable edit algebra?
- Can local grammar and direct manipulation cover most real correction work?
- When should the system ask one clarifying question versus presenting
  several preview cards?
- How should version history appear to a six-year-old, an adult improviser,
  and a piano teacher?
- Can a source-linked MusicXML edit survive later score-model regeneration?
- Which spoken pitch and rhythm vocabulary is reliable across accents and
  languages?
- Does natural-language editing reduce friction after the novelty wears off?
