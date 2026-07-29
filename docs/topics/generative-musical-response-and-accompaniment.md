# Generative Musical Response And Accompaniment

Topic: generative-musical-response-and-accompaniment

Status: proposed research and product direction as of 2026-07-29. This topic
records motivation, product experiences, system boundaries, candidate
approaches, evidence requirements, and a staged experiment plan. It is not
evidence that arrangement, generative music, real-time accompaniment, or any
named model has been integrated, licensed for distribution, or validated with
players.

## Scope And Relationship

This topic owns musical material derived from a player-created melody or
performance:

- deterministic chords, bass lines, percussion, and accompaniment patterns;
- call-and-response phrases and bounded melodic variations;
- symbolic model-assisted harmonization or arrangement;
- full-audio **make my tune sound like...** renders;
- provenance and separation between the performance and generated material;
- offline, latency, and licensing constraints; and
- experiments that determine which forms increase musical agency.

[`playful-piano-learning.md`](playful-piano-learning.md) owns the child and
family experience, readiness continuum, game surface, and studio-discovery
wedge. This topic supplies possible musical-response capabilities without
making a generative model a prerequisite for Play.

[`practice-companion-product-vision.md`](practice-companion-product-vision.md)
owns the musical notebook, moments, analysis, reflection, and collaboration.
A generated arrangement may become an interpretation or related artifact, but
must not replace the captured performance.

[`live-acoustic-transcription.md`](live-acoustic-transcription.md) owns
provisional and corrected acoustic events, source timing, and uncertainty.
[`performance-to-notation.md`](performance-to-notation.md) owns readable score
interpretation. This topic consumes explicit versions of those artifacts
rather than silently correcting them.

[`natural-language-musical-editing.md`](natural-language-musical-editing.md)
owns how a player selects, requests, previews, and accepts a correction,
transformation, accompaniment, or arrangement. The generator supplies
candidate musical material; the editing layer preserves user intent and
version history.

Every bounded implementation or model evaluation should receive a tactical.
This topic does not authorize embedding a large checkpoint, uploading child
audio, or depending on a hosted generation service.

## Motivation

A child who invents even a few notes has made something worth answering.
Hearing those notes become a lullaby, march, dance, or tiny ensemble can make
the piano feel like a place where musical choices have consequences rather
than a controller for passing tests.

The motivating experiences include:

- a child plays a melody and a duck answers it;
- a saved tune gains a simple bass or chord pattern;
- the same tune wears several musical **costumes**;
- instruments join one at a time so the child can hear their roles;
- the player chooses between plausible harmonizations by ear; and
- an older player optionally renders a captured idea as a fuller production.

This can serve ear training, improvisation, form, pulse, harmony, ensemble
awareness, and ownership. It also joins Atpiano Play to the musical notebook:
a fleeting invention can become a named tune, an arrangement, a performance
to play along with, and a later variation.

The central product promise is:

> Play a little tune, hear the musical world respond, and remain the author of
> what made it yours.

The generated result is successful when it sends the player back to listening
and playing. A polished track that makes the original performance feel
irrelevant is a product failure even if the audio is impressive.

## Three Different Technical Products

The phrase **music generator** hides three importantly different systems.

| Lane | Input and output | Strength | Main risk | Recommended role |
| --- | --- | --- | --- | --- |
| Procedural symbolic arranger | Verified notes plus explicit musical settings to MIDI-like parts | Fast, local, deterministic, editable, and explainable | Can sound repetitive or simplistic | Foundation and first experiment |
| Symbolic generative arranger | Notes or MIDI to chords, textures, responses, or variations | More variety while retaining musical structure | Training rights, style control, runtime, and inconsistent quality | Optional research adapter |
| Full-audio generator | Melody audio or symbolic conditioning plus a prompt to rendered audio | Immediate production value and timbral variety | Stochastic drift, heavy runtime, weak editability, licensing, and loss of authorship | Later opt-in studio render |

These lanes should share an artifact contract, not one implementation. The
product should be able to replace one arranger without changing the captured
melody, activity logic, or saved musical history.

An identical seed can make a stochastic model run reproducible in a particular
runtime, but that does not make its musical behavior deterministic or
editable. Conversely, a procedural system can expose exactly why a bass note
or chord was selected and regenerate the same result across ordinary
platforms.

## Product Experiences

### Give My Tune A Band

The player records or plays a short phrase, confirms that the application
heard it, and chooses a mood such as **sleepy**, **bouncy**, **mysterious**, or
**marching**. The first version adds a small chord vocabulary and one
accompaniment pattern, then plays the tune with and without the band.

The melody remains foregrounded and unchanged. A later version may let the
player:

- add drums, bass, chords, and a countermelody one at a time;
- mute, solo, replace, or simplify any generated part;
- play the melody live over the accompaniment;
- slow the result without changing pitch;
- save a favored arrangement beside the original tune; and
- return years later to make another arrangement.

### Same Tune, New Clothes

One melody can become a lullaby, march, waltz, or gentle pop pattern while its
identity remains audible. Comparing arrangements makes meter, articulation,
register, harmony, and instrumentation tangible without requiring those words
first.

For early versions, a **style** should be an inspectable set of musical
choices, not an imitation of a named living artist.

### Build The Band

Characters or instruments join one layer at a time:

1. hear the child's melody alone;
2. add a steady pulse;
3. add bass roots;
4. add block chords or an Alberti-bass pattern;
5. take one layer away; and
6. invite the child to supply that role.

This is both playful orchestration and an ear-training activity. It avoids the
common full-track problem in which the learner cannot tell what changed.

### Musical Answers

A character may echo the phrase, finish it, reverse its contour, change its
rhythm, transpose it, or make a contrasting answer. Each transformation
should be bounded and named internally so it can be replayed and compared.
The child should periodically choose the answer or lead the next turn.

### Chord Detective

The application offers two or three deliberately different harmonizations of
the same melody and asks which one feels like home, surprise, night, or
motion. There need not be one graded answer. This develops harmonic listening
and provides preference data without presenting music theory as certainty.

### Studio Render

An older child or adult may optionally ask for a fuller audio interpretation
of a saved tune. This is an asynchronous creative export, not a live game
response and not the authoritative performance. The interface should show
that exact notes, rhythm, harmony, form, and timbre may drift.

## Mario Paint Inspiration

[Mario Paint](https://www.nintendo.com/fr-ca/whatsnew/mario-paint-sintegre-a-la-collection-de-jeux-super-nes/)
is a product-feeling precedent rather than a feature specification. Its
creative suite placed music composition beside drawing and animation, and
made authored material immediately playful through iconic objects, surprising
sounds, tight constraints, replay, and experimentation.

The relevant qualities for Atpiano are:

- creation is the reward rather than a prerequisite for earning one;
- funny sounds invite curiosity without making the music itself a joke;
- an approachable composer makes notes visible and revisable;
- a small palette lowers the cost of beginning;
- immediate replay makes experimentation legible; and
- several media can feel like parts of one creative toy.

Atpiano should not clone Mario Paint's grid, sounds, characters, or limits.
Its opportunity is to make the physical piano the input and let a child layer
on visible notes, characters, instruments, patterns, and backing parts. The
same structured composition can later open in Notebook with a score, piano
roll, source audio, provenance, and professional correction tools.

This suggests a shared composer artifact and editing core with two
presentations:

- **Play:** characters, humorous timbres, large direct manipulation, simple
  layering, and immediate audition; and
- **Notebook:** score and piano-roll selection, precise parts, source
  alignment, natural-language correction, and detailed version control.

The playful surface should remain musically real enough to grow into the
studio surface. The studio surface should retain some delight rather than
turning the same tune into an unrelated administrative object.

## Readiness And Agency

For a two-year-old, generation should be almost invisible. One or two notes
can produce a friendly echo, drone, pulse, or complementary sound while a
caregiver controls duration and complexity. The system should not make a long
track from an accidental key press or demand that the child wait for one.

For the motivating six-year-old, a useful phrase may be two to eight bars or
even three memorable notes. Good controls are concrete and auditory:

- choose a character or mood;
- add or remove one band member;
- choose between two answers;
- play the tune again;
- change the ending; and
- decide whether to keep it.

Later players may control key, meter, chord vocabulary, phrase boundaries,
texture density, instrumentation, variation distance, and arrangement form.
The same artifact can therefore grow from a toy-like response into material
for theory, composition, score, and ensemble practice.

The player must always be able to hear the source melody alone. Generation
must not silently **fix**, decorate, quantize, or replace it.

## Source And Artifact Contract

Generated music is derived evidence. A minimal relationship is:

```text
captured performance
        |
        v
selected and verified source melody
        |
        +------------+----------------+
        v            v                v
analysis         symbolic          full-audio
hypotheses       arrangement       render
                     |
                     v
               synthesized audio
```

The saved source should retain:

- the performance or moment identifier and source-time range;
- the exact event-revision or corrected transcript used;
- the player's explicit edits or verification;
- expressive timing and any separate quantized interpretation; and
- uncertainty that remained unresolved.

Each derived artifact should retain:

- arranger or model name and version;
- method category and execution environment;
- input-artifact identifiers;
- settings, prompt, seed, and random state where applicable;
- generated symbolic parts before rendering when available;
- sound bank or renderer version;
- creation time and creator;
- applicable code, checkpoint, and output-license metadata; and
- whether the result is deterministic under the recorded contract.

The original and generated parts need separate identities. Deleting an
arrangement must not delete the performance; correcting a transcript must not
silently mutate an earlier arrangement; and publishing a generated render
must not imply that it is raw performance audio.

For microphone input, the player or caregiver should first hear and, when
necessary, correct the recognized phrase. Otherwise a polished arrangement
can reinforce a transcription error and make its source difficult to inspect.
MIDI can shorten this step but does not solve phrase, key, meter, or intention
ambiguity.

## Deterministic Foundation

The recommended first arranger does not require a trained model. It can:

1. accept a short, verified monophonic melody;
2. use a player-selected tonic, mode, meter, tempo, and phrase length at
   first;
3. score a small set of diatonic chord candidates against melody tones;
4. choose a progression with explicit cadence and voice-leading preferences;
5. render roots, block chords, broken chords, Alberti bass, a waltz pattern,
   or bass-plus-pad; and
6. synthesize locally through a bounded sound set.

[music21](https://www.music21.org/music21docs/) is a Python toolkit for
symbolic music analysis and generation that may accelerate a desktop
prototype. It is not itself an automatic arranger, and a small shared
TypeScript or Rust engine may ultimately fit offline Play better. The
important first contract is the symbolic input and output, not the library.

This baseline provides:

- response fast enough for turn-based play;
- exact repeatability;
- offline desktop operation and plausible offline web/mobile operation;
- transposition, tempo change, notation, and per-part playback;
- understandable failure cases;
- test fixtures with exact expected notes; and
- a reference against which learned systems can earn their complexity.

The first version should prefer a deliberately small harmonic world over
pretending to infer one correct sophisticated arrangement.

## Candidate Research Systems

Candidate status is time-sensitive. Before any integration, audit the exact
code revision, checkpoint, training-data disclosures, dependency licenses,
output terms, resource requirements, and supported platforms.

### Symbolic arrangement

[AccoMontage2](https://github.com/billyblu2000/AccoMontage2) is a useful
research precedent because it takes lead-melody MIDI and produces chord and
textured accompaniment MIDI with style and texture controls. Its current
repository documents four-beat meter and four- or eight-bar phrase
assumptions. The code repository is MIT-licensed, but that alone does not
establish that its data, checkpoints, dependencies, or generated outputs meet
Atpiano's distribution requirements.

[Magenta](https://github.com/magenta/magenta) contains influential symbolic
music work such as MelodyRNN and MusicVAE, but the main repository was
archived in January 2026 and is built around an older TensorFlow ecosystem.
It is better treated as research and design precedent than as the first
production dependency.

### Audio conditioned on melody

Meta's [AudioCraft](https://github.com/facebookresearch/audiocraft) includes
MusicGen with text and melody conditioning and JASCO with chord, melody, and
drum conditioning. The code is MIT-licensed, but released model weights are
CC BY-NC 4.0. The
[MusicGen Melody model card](https://huggingface.co/facebook/musicgen-melody)
also documents chromagram-based audio melody conditioning. This makes it an
interesting private research comparison, not a commercially deployable
default.

[ACE-Step 1.5](https://github.com/ace-step/ACE-Step-1.5) advertises local
generation, reference-audio, cover, repaint, and vocal-to-accompaniment
workflows across several hardware families. Its repository currently carries
an MIT license. Marketing claims and a repository license are not a complete
checkpoint, training-source, dependency, or output-rights audit, so any
Atpiano use should begin as a replaceable offline experiment.

[YuE](https://github.com/digitalapplied/yue) is a full-song research system
oriented toward lyrics-to-song generation. Its released weights are
noncommercial and its interaction is less aligned with short instrumental
melody response. It is relevant landscape evidence, not a leading candidate.

Full-audio systems are likely to behave more like stochastic renderers than
editable arrangers. Melody conditioning may encourage contour and harmony
without preserving every onset, duration, octave, or phrase boundary. Exact
melody adherence must be measured rather than inferred from a **cover** or
**melody-conditioned** feature label.

## Timing And Interaction

The current acoustic path is best suited to:

```text
play a phrase -> wait -> verify -> hear a response -> play again
```

It is not yet suited to a band following every beat. A convincing live
accompanist needs causal estimates of onset, beat, tempo, phrase position,
key, harmony, and recovery from mistakes in addition to low transport and
synthesis latency. Audio generation adds model look-ahead and render latency.
Throughput faster than real time does not establish a playable response loop.

Wired MIDI can support tighter experiments:

- a metronomic or pattern accompaniment started by an explicit count-in;
- chord changes scheduled from an authored form;
- a band that follows note attacks within a known phrase;
- pause and recovery policies; and
- eventually tempo-following with measured action-to-sound latency.

These should not be described as real-time accompaniment until full
capture-to-sound delay, jitter, synchronization, and recovery have been
measured with representative devices. A turn-based arranger remains valuable
even if live following never becomes robust.

## Privacy, Rights, And Safety

Child audio and performances remain private by default. A hosted generator
must not receive them without an explicit caregiver action that identifies
what leaves the device, how long it is retained, whether it trains a model,
and how the result can be deleted. Local processing is strongly preferred for
the first experiments.

The experience should avoid:

- prompts that imitate a named living artist;
- presenting generated music as authored solely by the child;
- teaching that one harmonization is universally correct;
- uninspectable correction of a child's melody;
- infinite one-click generation as the main reward loop;
- long waits disguised as live interaction; and
- shipping code-license compliance as a substitute for checkpoint,
  training-data, output-rights, and content-policy review.

Any released model must pass a fresh legal and product review. A
noncommercial checkpoint may be useful for private evaluation but cannot
define a feature whose eventual distribution depends on unavailable rights.

## Recommended Experiments

1. **Deterministic tune dresser:** accept a verified two- to eight-bar MIDI
   melody; provide block chords, Alberti bass, waltz, and bass-plus-pad;
   expose three concrete moods; render locally; and save symbolic parts with
   provenance.
2. **Build the band:** let a child add and remove pulse, bass, and chords,
   compare the source alone, and play over the result. Test whether the child
   asks to repeat the activity and returns to the keyboard.
3. **Musical answers:** implement a small catalog of named transformations
   before any generative model: echo, transpose, rhythmic change, contrasting
   register, changed ending, and question-to-answer cadence.
4. **Symbolic black-box comparison:** run the same verified melody set through
   AccoMontage2 or a later candidate offline. Compare adherence, musical
   usefulness, control, runtime, artifact inspectability, and rights against
   the deterministic baseline.
5. **Audio-render comparison:** privately evaluate MusicGen Melody and one
   actively maintained, licensable candidate on the same melodies. Record
   end-to-end generation time, hardware, memory, melody drift, reproducibility,
   editability, child and adult preference, and complete provenance. Do not
   embed a checkpoint in this slice.
6. **Live MIDI spike:** only after turn-based value is demonstrated, measure a
   fixed-pattern accompaniment with count-in, tempo following, pause, and
   recovery. Keep it separate from acoustic claims.

Each experiment should be independently removable. The deterministic
arranger should remain usable when no model, network, or account is present.

## Success Evidence

Promising evidence is musical behavior:

- a child asks to hear or play the tune again;
- the player can still identify their own melody;
- the arrangement leads to another performance or variation;
- adding or removing parts improves listening to musical roles;
- a player expresses a preference and can say or demonstrate why;
- teachers find the output useful without intervening to repair it;
- source and generated material remain understandable and recoverable; and
- local response remains reliable in an ordinary family or studio setup.

Generation count, render duration, novelty ratings, or production polish are
insufficient. Compare the experiences against simple melody playback and the
deterministic baseline, not only against one another.

## Open Questions

- Does accompaniment increase voluntary piano play, or does it move attention
  from the instrument to passive listening?
- What phrase length is satisfying for young children without creating a
  frustrating capture and verification step?
- Should the first harmonic choices be selected by the player, inferred, or
  presented as alternatives?
- Which transformations feel like a character responding rather than a
  machine demonstrating technique?
- How simple can an arrangement remain while still feeling magical?
- What source corrections can a child make without entering a score editor?
- Can a common symbolic contract serve web, Android, iPad, desktop, score,
  synthesis, and later model adapters?
- Which parts of tempo following can remain deterministic and local?
- Can any full-audio system preserve a child's exact melody and agency well
  enough to justify its runtime and rights complexity?
- What labels make the difference between performed, arranged, synthesized,
  and model-generated material understandable to families?
