# Playful Piano Learning For Families

Topic: playful-piano-learning

Status: proposed product direction as of 2026-07-29. This topic records
motivation, the separate Play product surface, a studio-discovery wedge,
experience principles, a growth continuum, candidate games, input and offline
contracts, precedents, and open questions. It is not evidence that Web MIDI,
the game runtime, child-oriented progression, mobile packaging, studio mode,
or any activity described here has been implemented or validated with
children or teachers.

## Scope And Relationship

This topic owns a playful family experience in which a physical piano becomes
the controller for musical exploration and learning. It includes:

- shared parent-and-toddler sound play;
- ear-led call and response;
- pitch, interval, rhythm, notation, and five-finger activities;
- improvisation and composition;
- character and world responses driven by real playing;
- a separate full-screen Play shell over shared Atpiano capabilities;
- slow, uncertainty-tolerant acoustic interaction;
- low-latency MIDI interaction;
- browser, tablet, and offline desktop delivery hypotheses;
- piano-studio discovery and teacher feedback;
- readiness-based progression from first cause and effect through independent
  practice; and
- evidence for whether play leads back to voluntary music-making.

[`practice-companion-product-vision.md`](practice-companion-product-vision.md)
owns the broader musical-notebook promise, moments, reflection, analysis,
trusted collaboration, and teaching. This topic adds a child- and
family-oriented route into that notebook; it does not replace the initial
curious-improviser and adult-learner product wedge.

[`live-acoustic-transcription.md`](live-acoustic-transcription.md) owns
microphone transport, sample time, provisional and corrected events, measured
latency, and recognition uncertainty. This topic consumes those events without
weakening their lifecycle contract.

[`family-workspaces-and-attribution.md`](family-workspaces-and-attribution.md)
owns managed child profiles, performer selection, and account-versus-performer
attribution. A child profile may retain readiness and preference metadata
later, but it is not a login or an authorization principal.

[`session-workspace-management.md`](session-workspace-management.md) continues
to own durable performances and annotations. A game may propose a named
musical moment or related take, but must not rewrite source evidence.

[`generative-musical-response-and-accompaniment.md`](generative-musical-response-and-accompaniment.md)
owns deterministic backing parts, generated answers and variations, model
experiments, and the separation between a child's source tune and derived
music. Play may consume those capabilities, but its first experiment does not
depend on them.

[`natural-language-musical-editing.md`](natural-language-musical-editing.md)
owns the shared selection, correction, composer, preview, and versioning
primitives that may sit beneath Play and Notebook. Play should expose those
primitives through direct, age-appropriate manipulation rather than requiring
a child to issue precise verbal commands.

Every bounded implementation should receive a tactical. This topic does not
authorize a broad curriculum, child account system, content marketplace, or
general-purpose game engine.

## Motivation

The motivating observation is not merely that a six-and-a-half-year-old can
play parts of **Twinkle, Twinkle, Little Star** and **Mary Had a Little Lamb**.
More importantly, she:

- has enough key familiarity to recover familiar melodies;
- hears at least some incorrect notes and tries again;
- has engaged with a pitch and solfège ear-training game; and
- sometimes improvises without being asked.

Those behaviors suggest a valuable starting loop:

```text
hear or imagine -> find it on the piano -> notice -> respond -> invent
```

The product should protect the desire to explore while gradually adding
control and vocabulary. A game should not convert an emerging musical
relationship into a sequence of compulsory note-identification tests.

The target age range also includes two-year-olds. The earliest experience
should therefore not be a simplified six-year-old lesson. It should make one
intentional or accidental key press produce a satisfying musical and visual
response, invite a caregiver to answer, and remain enjoyable without concepts
such as correctness, levels, written instructions, or delayed rewards.

The desired family promise is:

> Touch the piano, make something happen, discover a relationship, and
> gradually gain the ability to hear, choose, read, and shape more.

The system should be fun for a child and accompanying adult. An adult should
be able to enjoy the same call-and-response, improvisation, sight-reading, and
rhythm mechanics at a deeper level rather than occupying a separate
administrative surface.

## Product Surface Boundary

Play should be a separate experience over the same musical core, not a
collection of games inserted into the current professional workspace. Working
product-family vocabulary is:

- **Atpiano Notebook:** the current quiet, professional Sessions, capture,
  transcription, review, score, export, and musical-memory experience; and
- **Atpiano Play:** a full-screen world for exploration, games, learning, and
  studio use.

These names describe a boundary and are not selected public brands.

Entering Play may begin from a clear launcher in the shared application, but
Play owns its own navigation, visual language, feedback vocabulary, activity
state, and caregiver exit. Characters, rewards, lesson choices, and teacher
controls should not accumulate in a selected Notebook session. Conversely,
children should not encounter model horizons, artifact provenance, capture
diagnostics, or professional workspace chrome while playing.

The surfaces may share:

- normalized acoustic and MIDI input adapters;
- the local piano synthesizer;
- performer profiles and authorization;
- optional sessions, moments, and named child-created tunes;
- runtime and storage boundaries; and
- reusable React components whose presentation actually fits both surfaces.

They should not be forced into one information architecture merely because
they share implementation. A later Android or iPad store listing may present
Play independently while still consuming the same contracts and repository.
That decision should follow product evidence rather than precede it.

## Learning Center And The Role Of Notation

The center is musical familiarity: listening, finding, remembering,
answering, varying, and inventing. Staff notation is the written language that
can name and preserve those relationships, but it need not be the entrance or
the spine of the experience.

A representative learning loop is:

```text
hear -> find -> imitate -> invent -> recognize shape -> see symbol -> read back
```

For example, a child can invent a three-note duck call, hear the duck copy it,
notice that it rises and repeats, see the same contour on a staff, and later
read that personally meaningful call back. This joins ear training,
improvisation, keyboard geography, memory, and notation without treating
written-note decoding as a prerequisite for making music.

The product should still support direct sight-reading activities for players
and teachers who want them. The distinction is priority rather than
exclusion:

- sound and musical agency establish meaning;
- spatial and contour views expose relationships;
- notation represents and extends those relationships; and
- reading eventually becomes another route back to sound.

## Why Play Rather Than Cosmetic Gamification

A frog, duck, star, badge, or progress map is not sufficient. The musical
action itself should change the world:

- register changes where or how a character moves;
- pitch relationships determine a path;
- rhythm powers motion;
- dynamics or density change the environment where the input supports them;
- a copied phrase completes a conversation; and
- an improvised phrase becomes something the character can answer or remember.

A 2024 review in the
[British Journal of Music Education](https://doi.org/10.1017/S0265051724000123)
describes playful music learning across a continuum of learner ownership and
links playful practices with motivation, engagement, learning, and skill
development. A
[NAfME literature review](https://doi.org/10.1177/8755123317741488)
examines children's music games through autonomy, competence, and relatedness.
These sources support a direction, not a claim that one game mechanic or age
sequence is proven.

The corresponding product interpretation is:

1. **Autonomy:** the player chooses characters, sound worlds, challenges, and
   when to become the musical leader.
2. **Competence:** challenges are short, legible, forgiving, and adjustable
   enough that progress can be felt.
3. **Relatedness:** a caregiver, sibling, teacher, or character can answer the
   player's music.
4. **Ownership:** imitation alternates with improvisation, naming, saving, and
   revisiting the player's own material.

Points, collections, and narrative unlocks may decorate this loop. They must
not become the primary reason to touch the piano. Avoid streak anxiety,
leaderboards, artificial scarcity, energy timers, and rewards that pressure a
child to remain on the screen.

## Experience Principles

1. The real piano is the primary play surface; the screen responds.
2. The musical action, not a tap on the screen, advances the activity.
3. The youngest mode has no wrong notes.
4. A mistaken or uncertain note should invite another musical action rather
   than trigger shame, loss, or an abrasive error sound.
5. Listening, copying, inventing, and reading should reinforce one another.
6. Every directed sequence should periodically offer **your turn to lead**.
7. The system should work in very short encounters and stop gracefully at any
   moment.
8. Difficulty follows demonstrated comfort and the player's choice, not only
   age, grade, or a linear course.
9. Characters should embody musical relationships rather than obscure them.
10. Acoustic uncertainty must remain visible to adults and harmless to the
    child's play.
11. MIDI may make interaction faster; it must not make the acoustic piano feel
    like a deficient version of the product.
12. The experience should lead attention back to listening, moving, singing,
    and playing away from the screen.

For the two-year-old experience, co-play is the default. The
[American Academy of Pediatrics](https://www.healthychildren.org/English/family-life/Media/Pages/why-co-viewing-is-important-tips-to-share-screen-time-with-your-kids.aspx)
recommends co-viewing and co-playing as a way for caregivers to guide and
share digital experiences. The
[World Health Organization](https://www.who.int/news-room/detail/24-04-2019-to-grow-up-healthy-children-need-to-sit-less-and-play-more)
recommends no more than one hour of sedentary screen time for two-year-olds,
with less preferred. Atpiano should therefore behave more like a briefly
animated musical toy shared at the instrument than a toddler video product.
Sound-only prompts, large peripheral reactions, caregiver turns, movement,
and easy screen dimming are product requirements rather than optional
accessibility extras.

## Input And Responsiveness Lanes

The product should expose one musical activity model over inputs with
different timing and certainty. It must not pretend those inputs are
equivalent.

| Input lane | Useful properties | Constraints | Suitable play |
| --- | --- | --- | --- |
| Acoustic provisional | Uses the family piano; early pitch response; can hear polyphony | Current feedback is roughly in the one-second band, can miss or invent onsets, and may revise | Untimed echo, find-a-note, contour, exploration, slow notation |
| Acoustic corrected | Best available retained transcript and audio evidence | Arrives too late for live control | Review, save a tune, compare takes, parent digest |
| Wired Web MIDI | Exact note attacks and releases with low local latency; velocity and pedal may be present | Requires a compatible keyboard, browser path, and permission; not yet implemented | Rhythm, rapid response, platform motion, chords, repeated-note games |
| Bluetooth MIDI | Convenient and exact in pitch | Transport latency and setup vary by device | Most untimed MIDI activities; rhythm only after measurement |
| On-screen or pointer keyboard | No instrument setup | Moves attention off the physical piano and has different motor demands | Demonstration, travel fallback, caregiver authoring |

The current shared application does not implement Web MIDI input. The family
has a MIDI keyboard, which makes a future bounded adapter practical; its
existence is not implementation evidence.

### Optimistic game response

An ephemeral game response and a durable transcript have different jobs:

```text
acoustic provisional or MIDI attack
                |
                v
       normalized game attack
          /             \
         v               v
optimistic world       retained performance
response               evidence when enabled
```

Once a provisional acoustic note makes a frog jump, a later retraction should
not pull the frog backward. The activity may quietly exclude the event from a
saved tune, show an adult-facing recognition warning, or use correction to
improve later adaptation. It should not punish the child for a model revision.

For target-matching activities:

- accept a credible matching provisional pitch immediately;
- treat unrelated provisional pitches as observations, not instant failures;
- wait long enough for a target before offering a hint;
- provide a simple **it heard the wrong thing** escape for the caregiver; and
- preserve recognition and response timing so frustration can be diagnosed.

MIDI attacks can support strict ordering and timing once the browser's
end-to-end event latency has been measured. Wireless MIDI should not receive a
rhythm-quality claim merely because pitch identity is exact.

If audio and MIDI are captured together, the audio sample clock remains the
source timeline for the retained session. MIDI receipt time must be explicitly
mapped to that clock. Fast controller response must not invent a second
unreconciled performance history.

## Delivery And Offline Contract

Play should expose capability honestly instead of promising that every device
runs every model:

| Capability tier | Expected execution | Product role |
| --- | --- | --- |
| Play core | Local activity engine with MIDI, pointer, or authored prompts; no transcription model required | Fast games, exploration, notation, and studio stations |
| Acoustic Play | Provisional pitch or onset input from a capable browser, native adapter, or nearby host | Slower echo, finding, contour, and acoustic-piano play |
| Notebook | Full capture, retained audio, polyphonic transcription, correction, review, and export | Professional musical memory and deeper post-play evidence |

The initial platform hypothesis is:

- **Browser and Chromebook:** zero-install discovery and studio pilots,
  especially on Chromium systems with a compatible wired MIDI path;
- **desktop application:** the strongest fully offline surface, including
  local models, storage, MIDI, and studio operation;
- **Android:** an eventual installed Play surface with offline assets and
  tested native or browser MIDI and audio adapters;
- **iPad:** an eventual installed Play surface whose UI can be shared but
  whose reliable MIDI path will probably require a native adapter; and
- **tablet browser:** a useful acoustic, pointer, or hosted fallback where the
  required device API exists.

[Web MIDI](https://developer.mozilla.org/en-US/docs/Web/API/Web_MIDI_API)
remains a limited-availability, secure-context, permission-gated API. WebKit's
[open Web MIDI implementation issue](https://bugs.webkit.org/show_bug.cgi?id=107250)
means an iPad web page must not be assumed to reach a MIDI keyboard. Android,
ChromeOS, wired USB, Bluetooth, suspend/resume, permission, and event-latency
behavior all require tests on representative devices before support claims.

The repository already uses Tauri 2 for the desktop application, and
[Tauri 2 supports Android and iOS](https://v2.tauri.app/blog/tauri-20/).
That makes shared UI and native Kotlin or Swift input bridges plausible, but
the current desktop bundle is not mobile validation. Packaging, native MIDI,
audio capture, local storage, model execution, signing, store policy, and
upgrades remain separate evidence gates.

For a piano studio, **offline** should mean:

- local play does not require an account or active internet connection;
- previously installed activities and sounds remain available;
- MIDI activities do not call a hosted service;
- local performer selection and bounded progress continue to work;
- a failed update or unavailable server does not interrupt a lesson; and
- data can be explicitly exported or later published rather than being held
  only in a vendor account.

Full acoustic correction can remain a desktop-only capability while lighter
Play activities work on tablets. A future studio desktop may also serve
nearby devices over the LAN, but Play should not require that topology for
ordinary MIDI use.

## Readiness Continuum

The bands below are experience hypotheses, not developmental diagnoses or
hard age gates. A player can move freely among them, and a caregiver can
select a simpler or more complex form at any time.

### Shared sound play

Rough audience: a co-playing toddler or any first encounter.

The system asks for no reading, naming, copying, or steady timing. One sound
causes one understandable response. The caregiver narrates and takes turns.

Possible experiences:

- **Wake the pond:** any key creates a ripple and wakes one creature.
- **Animal registers:** low notes wake a bear, middle notes wake a duck, and
  high notes wake a bird.
- **Musical weather:** individual notes make drops or stars; clusters make a
  splash or cloud.
- **Your turn, my turn:** an adult plays, the character waits, and any child
  response completes the exchange.
- **Stop and go:** any note starts a walking character; silence lets it rest.
- **One special key:** a caregiver chooses one reachable key that makes a
  favorite character appear, without requiring exclusive use of that key.
- **Move with the sound:** a short sound-only prompt invites stomping for low
  notes, tiptoeing for high notes, or freezing in silence.

No activity in this band reports accuracy, misses, lives, a percent score, or
a curriculum level. Repetition is success. The player should be able to
ignore the intended relationship and still produce a coherent response.

[ZERO TO THREE](https://www.zerotothree.org/resource/distillation/beyond-twinkle-twinkle-using-music-with-infants-and-toddlers/)
emphasizes shared musical pleasure, active music-making, movement, props, and
caregiver connection for infants and toddlers. This supports making the adult
part of the activity and the piano action more important than the animation.

### Discovering relationships

Rough audience: a child ready to anticipate, choose, or copy one musical
property.

Candidate relationships include:

- high versus low;
- same versus different;
- louder versus softer where the input is reliable;
- one sound versus many;
- rising versus falling;
- short versus sustained;
- sound versus silence; and
- one-note or two-note echo.

Possible experiences:

- **Bird or bear:** choose a high or low note to guide the matching animal.
- **Same lily pad:** hear one note and find the same pitch, with any octave
  optionally accepted at first.
- **Which way did the frog go?:** hear a rising or falling pair and answer by
  playing any pair in the same direction.
- **Copycat:** the character plays one note, then two; the child echoes.
- **Sound twins:** decide whether two tiny phrases are the same or different
  by answering on the piano.
- **Build a bridge:** each successive note must go higher, lower, or stay the
  same.

The activity can first reward the relationship, then gradually narrow the
accepted pitch or register. It should not introduce letter names merely
because they are easy to display.

### Patterns, familiar tunes, and finger neighborhoods

Rough audience: the motivating six-year-old, beginning students, and playful
adults.

Possible experiences:

- **Pond Echo:** copy two- to five-note animal calls, then become the caller.
- **Finish the song:** hear the start of a familiar melody and supply its next
  note or ending.
- **Fix the silly song:** a character deliberately changes one familiar note;
  the player finds a better version.
- **Five-Finger Garden:** place one hand over a five-note neighborhood and
  wake its five characters through patterns.
- **Woodpecker:** repeat one pitch with an even pulse, then alternate two
  pitches.
- **Mirror pond:** one hand or the game plays a pattern and the other hand
  answers in a different register.
- **Question and answer:** copy a short question and invent an ending.
- **Tune treasure:** record a spontaneous phrase, name it, and find it again
  later.
- **Family echo:** a parent or sibling records a call and another performer
  answers it.

The game can suggest finger numbers or show a hand position, but note input
cannot verify fingering, posture, wrist freedom, tension, or touch. These are
caregiver or teacher observations. Never award a **correct fingering** result
from pitch evidence alone.

### Symbols and notation

Notation should name and organize relationships already heard and played. The
first experience need not be a flash-card quiz.

A possible sequence is:

1. Hear and find a note.
2. Reveal where that successful note lives on the staff.
3. Introduce a few landmarks such as middle C, treble G, and bass F.
4. Let characters walk by staff steps and jump by skips.
5. Associate a played pattern with its notated contour.
6. Alternate ear-only, staff-only, and combined prompts.
7. Read short phrases without a moving timing target.
8. Add pulse and rhythm only when the input lane can respond honestly.

Candidate experiences:

- **Frog Staff:** a frog occupies a line or space and jumps when its note is
  found.
- **Treble bird and bass bear:** register characters introduce the two clefs
  without implying that one clef belongs permanently to one hand.
- **Landmark lanterns:** find a small set of anchor notes, then nearby steps.
- **Draw the tune:** choose which of two contours matches a phrase just
  played.
- **Staff builder:** an improvised phrase becomes notation after the child
  plays it; the child can replay or rearrange it.
- **Sight-reading trail:** each correctly read note advances an untimed path;
  later versions introduce a pulse.

Falling notes may be a useful performance view, especially for MIDI play, but
should not become the only representation. The product should make it easy to
transition from spatial animation to staff notation and eventually to play
without either.

### Timing, coordination, and fast play

This band should prefer measured wired MIDI. It is the appropriate place for
the tighter or “twitch” loop that would feel unfair over the current acoustic
lane.

Possible experiences:

- **Firefly rhythm:** play a target note when a firefly reaches a flower.
- **Duck crossing:** alternate two or more notes to move through obstacles.
- **Rhythm rails:** repeated notes power a train only while the pulse is
  steady.
- **Chord shield:** play a complete target chord to block an incoming object.
- **Scale glider:** ascending and descending patterns control flight.
- **Left-right relay:** the hands alternate registers to pass an object.
- **Tempo garden:** a plant grows with a stable pulse rather than maximum
  speed.
- **Rhythm echo:** copy a rhythm first on one note, then over a short melody.

The design should favor control, recovery, and musical pulse over maximum
reaction speed. A rapid game can be exciting without encouraging tense,
forceful, or careless playing. Technique still requires human observation.

### Independent musical projects

Later progression should not consist only of harder execution targets.
Projects can include:

- compose a tune for a chosen character;
- make three variations of a saved phrase;
- dress the same tune as a lullaby, march, or waltz;
- build a backing band one audible part at a time;
- create a musical question and answer;
- orchestrate registers or dynamics into a scene;
- compare two takes without assigning one universal numeric score;
- turn an improvised moment into a readable score;
- send a family member a call and receive a performed response; and
- revisit a tune made years earlier and create its next version.

This is where playful learning rejoins Atpiano's musical notebook. The durable
outcome is a growing family body of music, not a completed app course.

## A Representative Cross-Age World

One coherent world can expose different depths without requiring separate
products:

| World element | Shared sound play | Pattern learning | Notation | MIDI-speed play |
| --- | --- | --- | --- | --- |
| Frog | Jumps for any note | Echoes a short call | Walks lines and spaces | Crosses timed lily pads |
| Duck | Appears in the middle register | Finishes a familiar melody | Finds landmark notes | Alternates two-note rhythms |
| Bear | Wakes for low notes | Answers in the bass | Introduces bass-clef anchors | Plays left-hand pulse patterns |
| Bird | Flies for high notes | Copies rising contours | Introduces treble anchors | Follows scales and arpeggios |
| Pond | Ripples with every sound | Remembers a child tune | Draws its contour or staff | Visualizes pulse and coordination |

This is preferable to unrelated mini-games if children form attachments to
the world and characters. Each character should retain a stable musical
meaning while activities become more sophisticated.

## The First Product Experiment

The leading first experiment is **Pond Echo** because it matches the existing
acoustic system's strengths and the motivating child's demonstrated interest.

A two- to five-minute loop is:

1. Choose a character and a small pitch neighborhood.
2. Hear a two-note call without notation.
3. Echo it on the physical piano.
4. Let each accepted provisional pitch move the character.
5. Repeat with a small adaptive variation.
6. Switch roles: **Now you make the call.**
7. Capture three or four child-played notes.
8. Play them back through the existing local synthesizer.
9. Let the child name or choose a picture for the tune.
10. Optionally save it as a moment in the selected performer profile.

The first slice should deliberately omit:

- rhythm grading;
- two-hand or fingering claims;
- a general curriculum;
- generative dialogue;
- generated accompaniment or a full-audio music model;
- public sharing;
- purchasable rewards;
- an elaborate map or economy; and
- a requirement to retain every encounter as a recording.

The same activity should then be tested over provisional acoustic input and
wired MIDI. The acoustic version waits and listens; the MIDI version can
animate on the attack. This comparison will validate the shared activity
contract and reveal whether the provisional response is satisfying before a
larger game surface is built.

A second experiment, **Wake the Pond**, should strip the same world down for
co-play with a toddler. It should launch directly, respond to every credible
note, require no target sequence, support sound-only use, and allow the parent
to introduce turn-taking without operating controls.

## Piano-Studio Discovery Wedge

The first external distribution channel should be a small group of piano
teachers reached through the motivating retired teacher's studio network.
These teachers are discovery partners rather than merely a launch audience.
Their studios provide repeated, situated use with different ages, teaching
methods, devices, instruments, and attention spans.

The concrete early workflow is a waiting-sibling station:

1. A teacher or caregiver selects a performer and one bounded activity.
2. The student plays for roughly five to ten minutes while a sibling receives
   a lesson.
3. The station resets cleanly for the next student.
4. The teacher can see or record a tiny musically meaningful observation.
5. Play remains supplemental to the lesson and does not claim to replace the
   teacher.

A minimal studio surface may need:

- fast managed-profile switching without child accounts;
- teacher-selected activity, readiness, pitch range, and input;
- a full-screen or kiosk-like student surface;
- no child-facing setup, purchase, or account controls;
- immediate reset between students;
- local and offline operation;
- a small teacher summary rather than a universal numeric grade; and
- simple authoring of a call, pattern, familiar fragment, or assignment later.

Before or alongside a pilot, interview teachers about:

- what waiting siblings currently do;
- which ages and musical concerns are least well served;
- what computers, tablets, acoustic pianos, and MIDI keyboards already exist;
- which prior games children voluntarily requested again;
- what demanded too much teacher intervention;
- what subscriptions, accounts, updates, or network dependencies failed; and
- what observation would actually affect the next lesson.

An initial cohort might be five to eight studios, intentionally including
teachers beyond one family or pedagogical network. Pilot only Pond Echo, Wake
the Pond, and perhaps one notation bridge rather than presenting a
comprehensive curriculum.

Useful lightweight teacher observations include:

- **engaged**;
- **asked to repeat**;
- **too easy**;
- **too hard**;
- **confusing**;
- **recognition problem**; and
- one optional musical note.

The evidence bar is repeated voluntary use, not favorable concept feedback.
Promising evidence would include several teachers choosing to use the station
again over multiple weeks, children asking to return, low setup and
intervention cost, continued off-screen piano exploration, and teachers
naming a musically useful observation. Do not build a broad teacher portal,
assignment marketplace, or studio billing system before that evidence exists.

## Existing Product Precedents

The category is established but fragmented. Current products show meaningful
investment in lessons, notation, assessment, child presentation, and studio
tools; the absence of one satisfying product in informal search is not proof
of an empty market.

| Product | Relevant precedent | Implication for Atpiano |
| --- | --- | --- |
| [Duolingo Music](https://blog.duolingo.com/music-course/) | Ear, rhythm, note-name, staff, and familiar-song work inside the main Duolingo app using an on-screen keyboard and no required instrument | A polished character-led course exists, but it does not make the family's physical piano the controller |
| [Mussila Music](https://mussila.com/music/) | Learn, play, practice, and create modes; theory, instrument, rhythm, melody, composition, and acoustic tone recognition; designed primarily for ages 5–11 | A broad colorful music world and acoustic feedback are proven product territory |
| [Piano Maestro](https://apps.apple.com/us/app/piano-maestro/id604699751) | Current iPad-only family and teacher product with acoustic recognition, MIDI, a large song/exercise library, teacher reports, and home assignments | This is the closest studio precedent; Android, open-ended play, and a less course-centered learning loop remain possible distinctions |
| [Piano Marvel](https://play.google.com/store/apps/details?id=com.us.pianomarvel.google) | Android and other surfaces, MIDI assessment, teacher use, uploaded music, reading, repertoire, and structured curriculum | Cross-platform studio assessment exists, but it emphasizes practice and evaluation rather than a young child's responsive musical world |
| [Mazaam](https://www.mazaam.com/en/the-mazaam-app/) | Listening games and classical-music concepts designed for younger children, with web and mobile ambitions | Younger-child musical play exists without turning a real piano into the controller; current Android distribution also illustrates platform fragility |
| [Yousician](https://support.yousician.com/hc/en-us/articles/204799551-Choosing-your-set-up-for-Yousician-piano) | Microphone input for acoustic piano plus USB, wired MIDI, and Bluetooth MIDI | Supporting both slower acoustic and more exact MIDI paths is a familiar and understandable setup |
| [Skoove](https://www.skoove.com/en) | Guided lessons and real-time listening feedback for acoustic and digital pianos | Atpiano should not compete first on the size of a linear lesson catalog |
| [Synthesia](https://synthesiagame.com/) | Falling notes, wait-for-the-correct-note practice, MIDI play, notation, hands-separate practice, finger hints, and progression tracking | Fast MIDI performance and spatial note guidance are mature patterns; transition beyond falling notes must be intentional |
| [Chrome Music Lab](https://musiclab.chromeexperiments.com/) | Immediate, accessible, account-free musical experiments and a simple shareable Song Maker | Low-friction exploration and authorship can be valuable without a curriculum or score |
| [Mario Paint](https://www.nintendo.com/fr-ca/whatsnew/mario-paint-sintegre-a-la-collection-de-jeux-super-nes/) | Music composition inside a playful creative suite, using iconic objects, humorous sounds, tight constraints, and immediate replay | Treat creation itself as the reward; let the physical piano feed a playful composer whose underlying music can later open in the serious studio |

The opportunity is the combination and emphasis:

- one experience continuum from caregiver-and-toddler play through adult
  musical projects;
- an acoustic piano treated as the desired family instrument, not merely an
  inferior controller;
- a distinct MIDI lane for interactions whose timing actually requires it;
- alternation between copying and child leadership;
- improvised material retained as a named musical memory;
- family calls, answers, and later variations attached to performers;
- multiple musical views grounded in the same captured evidence;
- a studio-ready local/offline option without requiring every child to hold
  an account or subscription; and
- honest handling of provisional recognition rather than false precision.

This landscape should be revisited before implementation because products,
features, prices, supported platforms, and licensing can change. Product
claims above are limited to the linked official descriptions reviewed on
2026-07-29.

## Progression And Adaptation

Progress should be modeled as several partly independent capabilities:

- willingness to make and repeat sounds;
- auditory discrimination;
- pitch-to-key mapping;
- melodic memory;
- pulse and rhythm;
- keyboard geography;
- movement within a finger neighborhood;
- staff landmarks and interval reading;
- coordination across registers or hands;
- improvisation and variation; and
- ability to describe or intentionally revise a musical idea.

Do not collapse these into one child level. A player may have a strong ear,
little notation knowledge, and emerging motor control. Another may sight-read
but hesitate to improvise.

Adaptation should:

- begin with a tiny observation round or caregiver-selected starting point;
- change only one demand at a time;
- offer an explicit easier, same, or surprising next choice;
- retain familiar material while introducing one new relationship;
- revisit successful child-created tunes as learning material;
- avoid silently accelerating after one lucky response;
- allow an adult to override recognition and difficulty; and
- explain adult-facing adjustments in musical language.

Age can select a safe initial presentation, especially for reading and
co-play, but it should not lock content or become an achievement label.

## Feedback Vocabulary

Child-facing responses should describe music or invite action:

- **The frog heard your note.**
- **That one went higher.**
- **You found the first two. Listen once more.**
- **That sounded different. Want to keep it or try the duck's version?**
- **Now the bird will copy you.**

Avoid:

- **Bad note**
- **Failed**
- **Only 62%**
- **You broke your streak**
- **Too slow**
- claims about fingering, posture, or expression unsupported by input

An unrecognized acoustic event should say what the system experienced, such
as **I didn't hear that clearly**, rather than asserting that the player did
nothing or played incorrectly.

Adult-facing feedback may be more precise:

- expected and observed pitch sequence;
- input lane;
- recognition confidence or lifecycle;
- response latency;
- repetitions and hints;
- chosen pitch range;
- source moment; and
- whether a conclusion came from MIDI, provisional audio, or correction.

## Success Evidence

The primary evidence should concern voluntary musical return:

- Does the child choose to begin?
- Does the child continue touching the piano after an activity stops?
- Does the child ask to repeat or vary a phrase?
- Does the child take the leader role without prompting?
- Does a toddler connect a key press with a sound or character response?
- Does the child sing, move, or play away from the screen?
- Does a saved child-created tune get revisited?
- Does the caregiver enjoy the exchange enough to initiate it again?

Secondary learning evidence can include:

- longest comfortable echo length;
- pitch neighborhoods found without hints;
- same/different, higher/lower, step/skip, and contour responses;
- pulse stability under a declared input and latency condition;
- staff landmarks and interval reading;
- familiar melodies recovered;
- variations deliberately produced; and
- recognition failures that caused visible frustration.

Do not optimize first for daily active use, minutes watched, streak length,
currency earned, or a single aggregate proficiency score. Those measures can
reward screen dependence or repetitive compliance without musical transfer.

Initial validation should include observation rather than only telemetry:

- parent-and-toddler co-play;
- the motivating six-year-old on acoustic piano;
- the same child on wired MIDI;
- an adult using the deeper version of the same activities;
- silence, room noise, sibling noise, clusters, repeated notes, and wandering
  outside the prompted range;
- sessions abandoned at every point without data loss or pressure to finish;
  and
- whether the screen attracts attention away from listening and the keys.

## Child Privacy And Commercial Boundaries

- Recording is explicit and private by default.
- A live game need not retain audio merely because it listens for notes.
- A named tune should identify exactly what will be saved.
- Managed child profiles remain separate from login accounts.
- Do not collect a child's voice, image, free-form conversation, or precise
  behavior history unless a later bounded feature requires it and a
  controlling adult deliberately enables it.
- No advertising, public child profiles, public leaderboards, or unsolicited
  contact.
- No manipulative purchase prompts, randomized paid rewards, or child-facing
  urgency.
- Caregiver controls should be reachable but visually separate from play.
- Sibling and family sharing remains explicit and attributable.

These are product boundaries, not a complete child-privacy or regulatory
review. Any release beyond private family use requires a separate review of
applicable law, store policy, consent, retention, analytics, and account
design.

The commercial model is unresolved, but the recommended studio contract is
that a purchased local core remains usable offline without a recurring
subscription or periodic network license check. Paid major upgrades may fund
continued platform maintenance. Hosted backup, cross-device publication,
remote collaboration, or multi-studio synchronization may be optional
services, but loss of those services should not revoke local activities or
student data.

Perpetual use does not mean frozen software. Android, iPadOS, macOS, browser,
USB, MIDI, signing, and store changes still require maintenance. Updates must
be recoverable and should not make an installed studio station unusable during
a lesson.

## Recommended Sequence

1. **Surface and input experiment:** establish a distinct full-screen Play
   route, define a normalized game-attack boundary, connect the current
   provisional acoustic lane, add a wired Web MIDI spike, and measure
   action-to-paint latency separately without changing Notebook interaction.
2. **Pond Echo:** validate two-note copy and child-led playback with the
   motivating six-year-old on both inputs.
3. **Wake the Pond:** validate no-wrong-answer caregiver-and-toddler play,
   including sound-only and minimal-attention presentation.
4. **Studio discovery:** interview a small teacher cohort, then validate the
   three-activity station, fast performer handoff, reset, offline behavior,
   and lightweight observations in repeated real use.
5. **Musical relationships:** add high/low, same/different, direction, and
   contour activities over the same world.
6. **Platform spikes:** validate browser and Chromebook MIDI, Android
   packaging and device input, iPad native MIDI bridging, and desktop offline
   operation before claiming cross-device parity.
7. **Notation bridge:** add landmarks, steps, skips, and short untimed
   sight-reading without claiming generated score quality.
8. **MIDI timing:** add pulse and fast-response activities only after the
   wired path's latency and browser support pass a tactile review.
9. **Musical memory:** save, name, revisit, vary, and exchange child-created
   moments through the existing family notebook boundaries.

This is a dependency order, not permission to implement all nine slices.

## Open Questions

- Are **Notebook** and **Play** the right product-family names, and should Play
  eventually receive a separate store identity?
- Is a coherent pond or forest world more engaging than a collection of
  unrelated experiments?
- What response latency still feels conversational on the acoustic piano to
  a child?
- Should acoustic play accept a correct pitch immediately from one
  provisional event, or require a short stability check?
- Can a fast browser-local monophonic detector improve single-note games
  without being mistaken for the durable polyphonic transcript?
- Which wired and Bluetooth MIDI paths work across the intended web, desktop,
  phone, and tablet surfaces?
- What native MIDI and audio bridge is required for iPad and Android, and
  which interaction and content code can remain shared?
- What exact functionality must remain available under a perpetual offline
  studio license, and what optional hosted services would teachers value?
- How should MIDI timestamps map to the audio sample clock when both inputs
  are retained?
- Does the toddler attend to the piano and caregiver, or does animation pull
  attention toward the screen?
- Which world reactions remain satisfying after novelty fades?
- When does a child want exact imitation, and when does the child prefer the
  character to accept a musically related response?
- How should a parent author a tiny call, familiar-tune fragment, or playable
  range without entering a lesson editor?
- What is the smallest teacher handoff, reset, assignment, and observation
  surface that works in a real waiting-sibling station?
- Which repeated-use and teacher-intervention evidence is sufficient to move
  beyond a small studio pilot?
- What is the smallest useful notation bridge for the motivating child?
- Can saved improvisations become future echo, reading, and variation
  material without exposing transcription errors as the child's mistakes?
- How should siblings of different readiness share a session without turning
  comparison into competition?
- Which observations belong in a private parent digest, and which should
  disappear after play?
- What tactile or human review is necessary before making claims about
  dexterity, timing, sight-reading, or independent learning?
