# Family Profiles, Spaces, And Recording Attribution

Topic: family-workspaces-and-attribution

Status: **profile-first Family slice implemented and live as of 2026-07-28
under Tactical 042.** The catalog now has generic groups, profiles,
controller relationships, workspace group grants, and separate creator and
performer attribution. The UI deliberately retains one visible shared Family
workspace; multiple content roots and a group/workspace switcher remain
deferred.

## Scope And Relationship

This topic owns the family-facing product model for:

- the distinction between a login account and a performer profile;
- fast performer selection at a shared piano;
- creator and performer attribution on recordings;
- person filters and an aggregate family overview;
- future shareable personal, family, lesson, or studio spaces;
- workspace membership and visibility presentation; and
- the boundary for a later household or studio administration layer.

[`home-hosted-family-sharing.md`](home-hosted-family-sharing.md) continues to
own deployment, authentication, and the Mac/Pi operational boundary.
[`session-workspace-management.md`](session-workspace-management.md) continues
to own selected-versus-active session behavior, recording evidence, session
annotations, and recoverable deletion.
[`practice-companion-product-vision.md`](practice-companion-product-vision.md)
owns the broader trusted-collaboration and teaching direction.
[`multi-tenant-hybrid-service-architecture.md`](multi-tenant-hybrid-service-architecture.md)
retains the much larger deferred PostgreSQL, object-storage, OIDC, worker, and
sync design. The implemented local slice does not require that program.

## Current Evidence

The following is true in the repository and live service on 2026-07-28:

- Alembic head `20260728_0002` adds generic groups, group memberships,
  profiles, profile controllers, group affiliations, explicit workspace group
  grants, and future-ready workspace metadata.
- The existing owner was backfilled into stable Family account/profile rows.
  Existing direct workspace membership survived the SQLite table rebuild.
- The reserved `local` content root is presented as **Family recordings** and
  remains the only materialized filesystem workspace.
- Authenticated group/profile APIs expose only data reachable through the
  current account's workspace and group memberships. Group membership alone
  does not grant content access; an explicit direct membership or workspace
  group grant is required.
- The React top bar distinguishes the signed-in account from the selected
  default performer. Owners/admins can create managed profiles without
  creating credentials.
- New microphone and imported recordings freeze both creator account and
  selected performer at Start. Changing the convenience picker later does not
  retarget that capture.
- The Sessions library labels and filters performers, including
  **Unassigned**, and an editor/owner can explicitly reassign the selected
  session's application metadata.
- All nine retained recordings remain in place and remain unassigned by
  design. Their capture manifests and artifact files were not rewritten.
- The live service passed authenticated capability, retained audio range, and
  retained MusicXML checks after migration. Anonymous capabilities remain
  denied.

The current administrator CLI still creates an account directly in the
Family workspace. It now also creates that account's stable self profile and
Family group membership in the same transaction.

## Product Vocabulary

### Account

An **account** is a security principal. It signs in, receives an authenticated
browser session, has workspace permissions, and is responsible for actions.
Kyle, his brother, an independent student, or a remote teacher may each have
an account.

Fast switching at the piano must not impersonate another account or change
authorization. The signed-in account remains the actor even when a different
performer profile is selected.

### Performer profile

A **profile** is a musical person represented in recordings. It may be:

- linked to the same person's login account;
- managed by one or more adult accounts;
- a child or guest with no login; or
- linked to an account later without replacing its prior attribution.

Examples are Kyle, Brother, Daughter, Nephew, or a student playing at a
teacher's piano.

A profile contains only bounded presentation and attribution metadata:
display name, optional initials or avatar later, enabled state, and controller
relationships. It is not an authorization token and does not automatically
grant access to recordings.

### Space or workspace

A **workspace**, presented as a **space** if that word is friendlier in the
UI, is a recording collection and access boundary. A session belongs to
exactly one space.

Spaces are shareable containers, not inherently private:

- Family may be shared by all family accounts;
- Daughter's space may also be shared with the family by default;
- Kyle's space may be shared, controller-only, or custom;
- Lessons with Ana may be shared by a student and teacher; and
- Studio may collect recordings made at a teacher's piano.

Privacy comes from the workspace membership set. A space with one authorized
account is private from other application accounts; adding members shares all
recordings in that space. This remains application privacy, not encryption
against the administrator of the Mac that stores the SQLite database and
artifacts.

Avoid per-recording access-control lists in the first implementation. When one
recording needs a different audience, move it later to a space with the
desired membership. Copying, links, and record-specific grants remain separate
future features.

### Household, studio, or organization

A later **group** may represent a household, studio, school, or other
administrative context. It could:

- collect accounts and managed profiles;
- provide a default audience for newly created profile spaces;
- let an administrator manage profiles and shared-space defaults once; and
- give one account separate Family and Studio contexts.

Do not make the group a recording container or an inherited authorization
shortcut. Workspace membership should remain the enforced content-access
rule. A group sharing default may materialize explicit workspace memberships
rather than adding a second implicit authorization path.

The durable mapping is:

```text
Family                         -> group row named "Graehl Family"
current shared recording root -> workspace row named "Family recordings"
Kyle / Brother accounts       -> user rows plus group memberships
Daughter / Nephew             -> profile rows plus group-profile affiliations
```

Seed one generic group when the profile slice is implemented, but keep it
visually implicit while it is the only group. This gives profiles a proper
scope and gives later spaces a default-sharing source without requiring a
group switcher, invitation system, or multi-organization UI now.

The group kind is a presentation and default-policy hint, never an
authorization shortcut. A distributed family is still one household group
whose accounts happen to use different devices or locations. A piano studio
is a studio group. A set of friends is a friends group. All recording access
still resolves through explicit workspace grants.

## Initial Relational Model

Use generic database names even when the first UI says Family. Preserve the
existing `users`, `workspaces`, `memberships`, and `web_sessions` tables and
extend them through migrations.

### Existing accounts

The existing `users` table continues to represent authenticated accounts:

```text
users
  user_id
  username
  normalized_username
  display_name
  password_hash
  disabled
  created_at
  updated_at
  password_changed_at
```

Do not rename it merely to align code vocabulary. In product and application
logic, treat a `user` row as an account/security principal.

### Groups

```text
groups
  group_id                    opaque stable ID
  name                        user-visible, e.g. "Graehl Family"
  kind                        household | studio | friends | other
  default_space_audience      group | controllers
  default_space_role          editor | viewer
  created_by_user_id          FK users
  created_at
  updated_at
  archived_at                 nullable

group_memberships
  group_id                    FK groups
  user_id                     FK users
  role                        owner | admin | member
  created_at
  PRIMARY KEY (group_id, user_id)
```

`default_space_audience` and `default_space_role` are provisioning defaults,
not live access rules. For the home deployment they can be `group` and
`editor`, making new profile spaces shared with the family by default. When a
space is created, the application writes an explicit group grant. Changing a
later group default does not silently rewrite existing space access.

Group roles govern group administration. They do not replace workspace
owner/editor/viewer roles or grant recording access by themselves.

### Performer profiles

```text
profiles
  profile_id                  opaque stable ID
  display_name
  created_by_user_id          FK users
  disabled
  created_at
  updated_at

profile_controllers
  profile_id                  FK profiles
  user_id                     FK users
  role                        owner | manager
  created_at
  PRIMARY KEY (profile_id, user_id)

group_profiles
  group_id                    FK groups
  profile_id                  FK profiles
  created_at
  PRIMARY KEY (group_id, profile_id)
```

Keep account linkage in `profile_controllers` rather than a single
`profiles.user_id`. This permits two parents to manage one child, one teacher
to manage several studio profiles, and a child to receive their own account
later without changing `profile_id`.

One profile may affiliate with more than one group. Authorization must still
bound which profile metadata an account may enumerate; group affiliation is
not a public profile directory.

### Workspaces and access

The existing `workspaces` table becomes a real content-container catalog:

```text
workspaces
  workspace_id
  administrative_group_id    FK groups
  name
  mode                        local | cloud | synced
  home_profile_id             nullable FK profiles
  storage_key                 validated server-owned relative key
  created_by_user_id          FK users
  created_at
  updated_at
  archived_at                 nullable
```

`administrative_group_id` says which group manages naming, defaults,
retention, and membership administration. It does not let every group member
read the workspace.

Keep the current `memberships` table as direct account-to-workspace access:

```text
memberships
  workspace_id                FK workspaces
  user_id                     FK users
  role                        owner | editor | viewer
  created_at
  PRIMARY KEY (workspace_id, user_id)
```

Add reusable group sharing separately:

```text
workspace_group_grants
  workspace_id                FK workspaces
  group_id                    FK groups
  role                        editor | viewer
  granted_by_user_id          FK users
  created_at
  PRIMARY KEY (workspace_id, group_id)
```

An account's effective workspace role is the strongest authorized direct
membership or group grant. The service computes that role before every
session, artifact, score, import, delete, and WebSocket operation.

Examples:

```text
Daughter's space shared with family
  administrative_group_id = Graehl Family
  direct membership        = Kyle owner
  group grant              = Graehl Family editor

Kyle private space
  administrative_group_id = Graehl Family
  direct membership        = Kyle owner
  group grant              = none

Lessons with Ana
  administrative_group_id = Graehl Family
  direct memberships       = Kyle owner, Ana editor/viewer
  group grant              = none
```

### Recording attribution

Sessions remain authoritative filesystem objects rather than central SQL
rows. Store attribution in the application-owned session metadata:

```text
workspace_id
session_id
created_by_user_id          nullable, immutable after creation
performed_by_profile_id     nullable, editable annotation
```

Moving a recording changes its containing `workspace_id` and storage location
but not its creator or performer identities.

### Public access later

Do not model public access as a fake group membership. Add a separate,
deliberate publication record only when public sharing is implemented:

```text
workspace_publications
  public_id
  workspace_id
  status                     draft | published | revoked
  discoverability            unlisted | listed
  public_slug                 nullable
  access_token_digest         nullable, for unlisted bearer access
  published_by_user_id
  published_at
  revoked_at
```

Public access is read-only unless a later product explicitly defines another
boundary. Invitation tokens, comments, and record-specific share links should
also receive separate tables and tacticals rather than being overloaded into
workspace membership.

## Recording Attribution

Access, action, and musical performance are different facts:

- `workspace_id` says which space contains the recording and therefore who
  may access it;
- `created_by_account_id` says which authenticated account started the
  capture or import; and
- `performed_by_profile_id` says who played the piano.

`created_by_account_id` is recorded automatically for new authenticated work
and does not change when a recording moves. It may be absent for legacy,
desktop-local, fixture, or other unauthenticated creation.

`performed_by_profile_id` is optional, editable application metadata. A new
capture should use the currently selected performer profile. Existing
recordings remain **Unassigned** until somebody explicitly assigns them. Do
not infer the performer from a workspace owner, the signed-in operator, a
capture date, a filename, or the person doing a later migration.

A single performer is enough for the first family slice. If actual duet
evidence appears, evolve this into ordered contributor attributions rather
than encoding several people in one string.

Workspace ownership must never be presented as recording authorship, and
selecting a profile must never grant that profile's linked account access.

## Recommended Immediate Experience

Keep the existing Family workspace as the one shared recording library. Add
profiles, performer selection, and filters before adding more spaces.

### Family overview

```text
Atpiano                         [Kyle account ▾]

Family recordings

People
  [All] [Kyle] [Brother] [Daughter] [Nephew]

  Evening invention
  Performed by Daughter · Recorded Jul 27 · 3:42

  Bass idea
  Performer unassigned · Recorded Jul 26 · 1:18
```

The profile chips filter the same authorized Family library; they do not
change login identity, permissions, or the active server workspace. This
provides the useful unified view without requiring cross-workspace
aggregation.

### Fast performer picker

Present a conspicuous **Who's playing?** control when New recording opens:

```text
Who's playing?

  [Kyle] [Brother] [Daughter] [Nephew] [+ Guest]

Save to
  Family · Shared with family
```

Selecting Daughter means:

- the current authenticated account still performs the capture action;
- the resulting recording is attributed to Daughter's profile; and
- the recording remains in Family, visible according to Family membership.

Keep the selected profile as a device-local convenience, but repeat it
prominently on the capture deck and in the live state. To prevent a stale
selection from misattributing tomorrow's recording, either ask on each new
capture or return to a safe default after a bounded idle period. Changing the
performer during an active capture should affect only future sessions, not
rewrite the one already recording.

A quick guest profile may be useful later, but persistent people should be
created deliberately so spelling variants do not fragment one person's
history.

### Account menu

Keep the actual login separate and visible:

```text
[KG] Kyle account ▼
     Signed in as @kyle
     Managed profiles
     Account settings
     Sign out
```

The menu makes it clear that **Who's playing? Daughter** is attribution, not
security identity. Account creation, disablement, username management, and
administrative password reset may remain local CLI operations initially.

### Existing recording assignment

Provide an owner/editor organization flow:

1. filter **Performer unassigned**;
2. select one or more recordings;
3. choose **Assign performer**; and
4. confirm the named profile and count.

The nine current recordings should remain in Family and unassigned until this
explicit action. Their audio, event histories, scores, hashes, and capture
manifests do not change.

The selected-session header should also permit one-at-a-time assignment.
Bulk assignment is a convenience over the same explicit
workspace/session-addressed mutation.

## Future Shareable Spaces UX

Add multiple spaces only after profiles and Family attribution are useful.
When they arrive, use a hybrid overview and explicit destination context:

```text
Overview

PEOPLE
  All · Kyle · Daughter · Nephew

SPACES
  Family             Shared with family
  Kyle                Shared with family
  Daughter            Shared with family
  Private             Only Kyle
  Lessons with Ana    Kyle + Ana
```

A profile's home space is a naming and default-destination convention, not a
special privacy type. Daughter's home space may default to **Shared with
family**, which matches the desired open household behavior. Its controllers
may later change the whole space to **Only controllers** or **Custom**.

Every recording card in Overview carries its space and performer:

```text
Evening invention
Daughter's space · Performed by Daughter · Shared with family
```

From a real space, New recording targets that space directly. From Overview,
the capture deck uses the selected profile's remembered home space but shows
the destination and audience before Start:

```text
Who's playing?  Daughter
Save to          Daughter's space
Visible to       Family
```

Do not silently save to the first workspace returned by the API.

Workspace selection and profile filtering remain browser-local. TanStack
Query keys, mutations, playback, score-reader identity, and late-response
rejection must include `workspace_id`. The smallest compatible deep-link
extension is:

```text
?workspace=WORKSPACE_ID
?workspace=WORKSPACE_ID&session=SESSION_ID
```

Existing `?session=...` links resolve against the reserved legacy `local`
workspace during a compatibility window.

## Teacher And Shared-Piano Direction

The account/profile split supports a teacher without turning the first family
slice into a school platform.

At a teacher's piano:

- the teacher signs in with the teacher's account;
- **Who's playing?** selects a managed or visible student profile;
- the recording is created by the teacher account and performed by the
  student profile; and
- the explicit destination is a Studio or lesson space the teacher may write.

For remote review:

- a student may share their home or lesson space with the teacher;
- the teacher's Overview aggregates the spaces explicitly shared with that
  account;
- a teacher filters by student profile rather than impersonating the student;
  and
- a student keeps private work in another space without teacher membership.

If only one take should go to a teacher, a dedicated **Lessons with Teacher**
space plus a later move operation is easier to understand and authorize than
record-level sharing exceptions.

A visible multi-group Studio/Household switcher becomes useful when the
teacher manages many student profiles and spaces, wants separate default
policies, or needs to switch between independent Family and Studio contexts.
It is not required for the first shared-piano workflow; the initial seeded
Family group can remain implicit.

## Persistence And Runtime Direction

### Profile slice

Keep session files and checksummed artifacts authoritative:

1. Add stable profile records and explicit account-controller relationships
   to the SQLite catalog.
2. Let the current Family workspace expose its deliberately associated
   profiles to authorized members.
3. Record creator account provenance when authenticated capture or import
   creates a session.
4. Store editable performer attribution beside other application annotations,
   not in completed transcription evidence.
5. Return profile IDs and bounded display metadata through explicit
   authenticated APIs. Never use a selected profile as authorization input.
6. Preserve disabled or unlinked profiles as historical attribution rather
   than erasing their names from old recordings.

The exact profile-to-workspace association and controller schema belongs in
the implementation tactical. It must permit one profile to appear in more
than one space and one adult account to manage several profiles.

### Multiple-space slice

When multiple spaces are justified:

1. Keep workspace and membership rows authoritative in SQLite.
2. Give each materialized workspace a validated storage key below one
   configured family root. Never persist a client-supplied absolute path.
3. Map reserved workspace `local` to the existing root so the nine retained
   recordings require no bulk filesystem migration.
4. Place new roots where the legacy scanner cannot mistake them for sessions.
5. Compose workspace-addressed session, artifact, score, and storage services
   through a registry.
6. Keep one host-wide capture/model coordinator initially. It may target any
   authorized workspace but still grants one active writer across the Mac.
7. Let a space's sharing UI change explicit workspace memberships.

Moving a completed recording between spaces is a later explicit operation. It
requires write authority in both source and destination, validates paths and
hashes, preserves creator/performer provenance, updates application metadata
atomically, and retains a recoverable failure path.

## Bounded Delivery Sequence

### Slice 1: managed profiles in the current Family workspace

- seed one generic household group and attach the existing account and
  reserved `local` workspace without exposing a group switcher;
- add stable performer profiles and account-controller relationships;
- add **Who's playing?** to New recording and show it during capture;
- record creator account and editable performer profile separately;
- add profile chips, unassigned filtering, and bounded bulk assignment;
- surface the real signed-in account as a distinct account menu;
- add CLI or owner UI to create Daughter and Nephew as managed profiles; and
- keep every recording in the existing Family workspace.

This slice is implemented. It addresses the immediate shared-piano family use
without multi-workspace storage, workspace switching, group inheritance, or
per-recording permissions. Bulk assignment was deliberately left out; the
first UI supports explicit selected-session reassignment.

### Slice 2: shareable spaces

- materialize multiple local workspace roots through a registry;
- add workspace creation, explicit membership management, and share labels;
- add Overview plus explicit space URL and capture destination;
- allow a profile to have a default home space;
- default new family profile spaces to the accepted family audience;
- add controller-only and custom membership choices; and
- prove cross-space default-deny authorization.

### Slice 3: multi-group organization and teaching from observed need

- expose additional Household, Studio, or friends groups when several spaces
  need shared administration or one account belongs to multiple contexts;
- materialize group sharing defaults into auditable workspace memberships;
- add external teacher membership and a teacher overview;
- add explicit session movement for one-take sharing; and
- add comments, teaching permissions, or invitations only through their own
  bounded product tacticals.

## Validation Contract

The profile slice must prove:

- switching performer never changes the authenticated principal or permission;
- a child/guest profile with no login can receive attribution;
- a later account link preserves existing profile and recording identity;
- creator account and performer profile may differ and are both retained;
- only authorized account controllers can edit profile metadata;
- Family members see only the profiles intended for that workspace;
- legacy recordings remain readable and unassigned until edited;
- selected-session reassignment changes only application metadata;
- disabling an account blocks access without erasing creator provenance;
- disabling a profile prevents future selection without erasing history;
- stale device selection cannot silently misattribute an unreviewed capture;
- active capture retains the performer and destination chosen at Start; and
- fixture, local browser, family, and desktop compositions preserve their
  declared account behavior.

The later multiple-space slice must additionally prove:

- an account sees exactly the spaces in its memberships;
- aggregate views cannot leak titles, profiles, previews, or timing from
  inaccessible spaces;
- owner/editor/viewer permissions apply to the requested workspace, not a
  hard-coded ID;
- a controller-only space is unreadable through session, artifact, score,
  import, delete, and WebSocket paths by other family accounts;
- New recording names and uses its explicit destination;
- a host-wide capture conflict leaks no inaccessible workspace metadata;
- browser-local workspace and profile selection cannot retarget active work;
- the nine existing roots work without migration; and
- the active-service restart and public verification contract passes after
  application changes.

## Immediate Account-Creation Boundary

The brother's account can be created now as an editor in the existing shared
workspace:

```text
uv run atpiano users --workspace results/workbench-v3 create USERNAME \
  --display-name "DISPLAY NAME" --role editor
```

The command prompts twice for a password of at least 12 characters and does
not put it in shell history. It does not require a service restart.

Creating that account now grants access to all nine current recordings and
the existing editor mutation set. Daughter and Nephew do not need login
accounts for the recommended profile-first slice.

## Recommended Direction

Use the profile-first Family library before expanding the container model.
Create the brother's editor account through the existing password-prompting
CLI, then add Daughter or Nephew as managed profiles through the account menu.
Assign older recordings only when their performer is known.

Later, make all spaces shareable through explicit memberships. A person's
home space should default to the family's accepted audience rather than being
private by definition. Add a Household or Studio switcher only when real
cross-space administration makes it valuable.

Do not use profile switching as authentication, do not add per-recording ACLs
to the first slices, and do not reopen managed OIDC, PostgreSQL, object
storage, or multi-host sync for this family need.
