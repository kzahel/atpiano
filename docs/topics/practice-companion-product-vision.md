# Practice Companion Product Vision

Topic: practice-companion-product-vision

Status: proposed product direction as of 2026-07-26. This topic records the
product framing and its boundaries; it is not evidence that the complete
phone, collaboration, teaching, analysis, or hosted experience exists.

## Vision

Atpiano turns fleeting acoustic-piano practice into something a player can
remember, understand, revisit, and discuss.

It is a musical notebook rather than only a transcription utility. It quietly
captures unstructured playing, preserves the performance as source evidence,
makes it visible through several useful interpretations, and lets a player
connect what happened with what they intended. Trusted collaborators can then
listen and respond in words, annotations, or another performance.

A concise product promise is:

> Atpiano is a musical notebook for acoustic piano. It remembers what you
> play, helps make sense of it, and lets people you trust respond.

Possible shorter expressions include **A memory for your piano**, **Make your
playing visible**, and **From musical thought to shared understanding**.
These are working language, not selected marketing copy.

## Product Wedge

The first audience should be curious improvisers and adult learners who play
an acoustic piano and regularly produce ideas they cannot easily name,
reproduce, engrave, or share. This includes the motivating personal workflow:

- record a small jingle or improvisation without preparing a score;
- recover what was played as audio, notes, and readable engraving;
- inspect musical patterns and learn vocabulary for them;
- record what the player was imagining in shapes, sounds, or other mental
  models; and
- exchange the idea and a musical response with a trusted collaborator.

This wedge does not require an existing score, a MIDI-enabled instrument, or
a teacher-assigned exercise. It distinguishes Atpiano from score-following
practice applications and from products whose only outcome is automatic
sheet music.

Teacher-student work is a natural extension of the same reflection and
response loop. A teacher marketplace, curriculum product, generalized social
network, or numeric grading system is not part of the initial promise.

[`playful-piano-learning.md`](playful-piano-learning.md) owns a separate
family-facing route into this notebook: caregiver-and-toddler sound play,
ear-led imitation and invention, notation bridges, forgiving acoustic
turn-taking, and faster MIDI games. That direction can reuse captured moments
and performer profiles without replacing this topic's initial product wedge
or turning the musical notebook into a linear children's curriculum.

## Core Loop

```text
play -> capture -> find a moment -> understand -> reflect -> share -> play again
```

A representative experience is:

1. Put a phone beside the piano and start a session.
2. Practice without needing to operate or watch the application.
3. Mark an interesting passage, potentially with a retroactive **Keep that**
   action that captures the previous several seconds.
4. Review synchronized audio, detected notes, keyboard, piano roll, and an
   optional engraved interpretation.
5. Select a passage and explore what happened musically.
6. Attach a reflection about its sound, shape, emotion, technique, theory,
   intention, or an unresolved question.
7. Share the selected passage with a trusted person, who can comment,
   annotate, or record a musical response.
8. Return to the piano and make a related take.

The product should optimize for a meaningful passage being revisited,
understood, or exchanged, not merely for minutes of audio transcribed.

## Sessions And Moments

A **session** is the durable source record of one practice or performance
period. Its audio sample clock, normalized events, revisions, and provenance
remain authoritative under
[`live-acoustic-transcription.md`](live-acoustic-transcription.md) and
[`session-workspace-management.md`](session-workspace-management.md).

A **moment** is a player- or system-proposed passage within a session that is
worth returning to. A moment identifies a source-time range without copying
or replacing the underlying performance. It can collect:

- a user title and free-form reflection;
- time-aligned text, voice, or visual annotations;
- an engraved snapshot and other versioned interpretations;
- analysis hypotheses and their evidence;
- comments and teacher feedback; and
- related or responding takes.

The session is the evidence container, but the moment may become the primary
unit of learning and collaboration. Automatic moment suggestions should
remain suggestions: the player decides what was meaningful.

Completed performance evidence stays immutable. Editable names, annotations,
relationships, and discussion belong in a separate workspace layer rather
than rewriting capture artifacts.

## Three Complementary Lenses

The application should make three different questions visibly distinct:

| Lens | Question | Representative output |
| --- | --- | --- |
| Performance | What physically happened? | Audio, notes, pedal, expressive source timing, keyboard, and piano roll |
| Engraving | How could a musician read it? | Editable, versioned common music notation |
| Analysis | What patterns might help explain it? | Rhythmic, harmonic, melodic, motivic, and formal hypotheses |

The performance remains authoritative. Engraving and analysis are
interpretations that may be regenerated, compared, corrected, or rejected.

In this product vocabulary, **score** means engraved music notation, not a
numeric assessment of the player. If evaluative feedback is introduced, the
interface should call it feedback, observation, comparison, or a
goal-specific rubric rather than overloading score.

### Performance

Performance review should preserve the expressive timings that were actually
played and retain uncertainty or revisions from acoustic transcription. A
later correction or interpretation must not silently erase the original
audio, source timing, or model evidence.

### Engraving

Engraving is a central product outcome, not a decorative renderer. A useful
score must infer meter, beat, quantization, spelling, hands, voices, rests,
ties, and gestures well enough to be pleasant to read. Literal millisecond
fidelity and musical readability are different goals.

[`performance-to-notation.md`](performance-to-notation.md) owns this
conversion contract. Its current evidence is promising but not yet a public
product capability: the leading local result depends on a converter with an
unconfirmed license, and score interpretations still require explicit
quality and provenance.

### Analysis

Analysis should attach useful names or relationships to the music without
pretending that every passage has one canonical theoretical explanation.
Candidate capabilities include:

- key and local-key estimation;
- chord candidates and harmonic segmentation;
- motif recurrence and transformation;
- melodic contour and interval patterns;
- rhythmic cells and phrase boundaries;
- voice-leading observations;
- repetition and larger-form proposals; and
- evidence-based comparison between takes.

Every material analytical claim should identify the source range and notes
that support it. Where the musical context is ambiguous, the application
should retain plausible alternatives or say that no useful conventional
label is available.

## The Musical Analyst Boundary

A musically informed language model or Codex skill may be useful as an
orchestrator, explainer, and conversational partner around specialized music
analysis tools. Current general-purpose language models should not be treated
as the primary music-perception engine or a reliable source of unsupported
harmonic and formal judgments.

The intended path is:

```text
performance notes and pedal
        |
        v
beat, key, voice, and segmentation hypotheses
        |
        v
specialized symbolic and audio-analysis tools
        |
        v
competing structural interpretations with evidence
        |
        v
language-model explanation and dialogue
```

A musical analyst may:

- select and compose appropriate analysis tools;
- translate measured results into language suited to the player's level;
- compare conflicting tool results and preserve uncertainty;
- relate structural observations to the player's stated intention;
- ask musically productive follow-up questions; and
- suggest a bounded experiment for the next take.

It should not:

- invent exact notes, chords, meter, or form from intuition when the evidence
  or tools do not support them;
- correct the acoustic transcript or engraving merely because another result
  sounds linguistically plausible;
- present ambiguous functional-harmony labels as facts;
- treat the player's mental model as an error to be corrected; or
- become a required dependency for capture, review, or engraving.

Useful feedback can distinguish:

1. **Observed:** a directly measured event or pattern;
2. **Interpreted:** one possible musical explanation; and
3. **Try next:** an experiment derived from the player's goal.

For example, the system might observe that a contour recurs, propose that it
functions as a motif, acknowledge two plausible harmonic contexts, relate
the rising ending to the player's description of a question, and suggest
changing only the ending in the next variation.

## Thought Annotations

Atpiano should preserve a second, human-authored transcript beside the
musical transcript: what the player thought they were doing.

Annotations may express:

- **sound:** bright, dark, open, dense, tense, released;
- **shape:** rising, falling, arch, waves, interruption, question and answer;
- **gesture:** weight, direction, touch, voicing, pedal, fingering;
- **theory:** chord, scale, tonal center, pattern, form;
- **intent:** image, mood, story, experiment, constraint; or
- **uncertainty:** what surprised the player or what they want help hearing.

Free text should remain available. A fixed taxonomy must not force informal
or sensory musical thought into theoretical vocabulary. Visual annotations
could include arcs, circles, phrase boundaries, emphasis, or tension curves
drawn over the piano roll or score.

The valuable comparison is among what the player intended, what the
performance evidence contains, and what a listener or analytical system
might call it. A difference among those perspectives can support learning
without implying failure.

## Collaboration And Teaching

Collaboration should be anchored to musical evidence rather than becoming
generic chat or file sharing. A **riff thread** could contain an original
moment, its reflection, comments, another person's performed response, and
later variations. Each response remains attributable and linked to its own
source session.

For teaching, the default review unit should be a student-selected moment or
a compact practice digest rather than hours of undifferentiated monitoring.
A digest might contain:

- moments the student deliberately marked;
- the student's questions and stated intentions;
- representative or compared takes;
- recurring passages the system proposes for attention; and
- progress against a teacher's previous suggestion.

The teacher can comment on exact audio, note, or score ranges and leave a
focused experiment. The student can answer with another take. Full-session
access remains an explicit sharing choice.

Live transcription during a remote lesson is a later extension. It should
augment the participants' audio or video connection and preserve the same
sample-clock, provisional-event, and uncertainty contracts as ordinary
capture. It should not require Atpiano to become a video-conferencing
product.

## Product Surfaces

The phone, hosted web application, and offline desktop application are
surfaces over the same session, moment, interpretation, and collaboration
model rather than independent products.

### Phone capture companion

- one-tap, low-distraction recording beside the piano;
- clear capture health without demanding visual attention;
- retroactive moment marking;
- quick voice or text reflection; and
- an explicit choice to remain local or publish to a workspace.

### Web review and conversation

- zero-install live or uploaded capture;
- synchronized performance review;
- moment selection and annotations;
- engraving and analysis;
- sharing, comments, and teaching workflows.

### Offline desktop

- the shared review experience with local inference and storage;
- long sessions and stronger privacy;
- operation without an account or network; and
- explicit later publication of selected sessions or moments.

The accepted runtime and workspace boundaries for these surfaces live in
[`multi-tenant-hybrid-service-architecture.md`](multi-tenant-hybrid-service-architecture.md).

## Product Principles

1. Capture must be easier than deciding what the music is.
2. The application should interrupt playing as little as possible.
3. Audio and source-timed performance evidence remain authoritative.
4. Engraving and analysis are inspectable, versioned interpretations.
5. Uncertainty and competing interpretations are product information, not
   implementation details to hide.
6. Feedback is conditioned on the player's intention and context.
7. Human conversation remains central; automation should make the musical
   evidence easier to discuss.
8. Local-only and offline use are first-class, not degraded account states.
9. Sharing is explicit and scoped; practice recording is private by default.
10. Success is measured by useful musical return: a remembered idea, a better
    question, a readable score, a response, or a more intentional next take.

## Suggested Product Sequence

1. **Musical notebook:** dependable capture and synchronized review, moments,
   reflections, readable engraving snapshots, and simple sharing.
2. **Understanding:** evidence-linked symbolic analysis, alternative
   interpretations, comparisons between takes, and cautious explanation.
3. **Conversation:** annotations, riff threads, teacher review queues, and
   practice digests.
4. **Live companionship:** restrained live feedback and remote-lesson
   transcription once latency, correction, and interaction quality justify
   it.

This sequence is a product dependency order, not an implementation tactical.
Each bounded implementation slice should receive its own document under
`docs/tactical/`.

## Open Product Questions

- Is **moment** the right user-facing term, and how should it relate to clips,
  takes, phrases, and complete sessions?
- Should **Keep that** be a phone interaction, a pedal or keyboard shortcut,
  a voice command, an automatically proposed moment, or several of these?
- What is the smallest engraving quality bar that makes the notebook useful
  before score correction tools exist?
- Which analytical observations are reliably useful with current tools, and
  which should remain research experiments?
- What provenance and evidence presentation makes a structural hypothesis
  understandable without overwhelming a learner?
- How should a player correct transcription, engraving, and analysis without
  conflating the three layers?
- What collaboration model best supports informal musical exchange without
  creating a general-purpose social network?
- What does a teacher need in a practice digest to save review time while
  preserving student agency?
- Which session and moment information remains device-local by default, and
  what exactly is copied when a player shares?
- What early behavior best predicts durable value: returning to a moment,
  exporting an engraving, writing a reflection, receiving a response, or
  making a related take?
