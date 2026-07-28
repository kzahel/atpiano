# 042 — Family Profile Schema And UI

Topic: family-workspaces-and-attribution

Status: **complete and live on 2026-07-28.** The user accepted the generic
group/profile/shareable-space schema and asked to migrate to it while keeping
the first UI simple enough to prove the model.

## Outcome

Migrate the authenticated home catalog from accounts plus one implicit
workspace to a generic but bounded family composition:

- one seeded `household` group, hidden as a switchable context while it is the
  only group;
- existing authenticated users attached as group members and self-managed
  performer profiles;
- managed child, guest, or family profiles that do not require login;
- the existing `local` workspace attached to the group without moving any
  recording directory;
- future-ready explicit group workspace grants and validated storage metadata;
- creator-account and performer-profile attribution kept distinct; and
- a profile-first React experience over the existing Family recording root.

The proving UI includes:

- a distinct signed-in account menu;
- group-owner profile creation;
- a conspicuous **Who's playing?** picker before capture or import;
- the chosen performer retained for the session started by that action;
- performer labels and person/unassigned filters in the Sessions library; and
- selected-session performer reassignment for owner/editor users.

This tactical does not add multiple filesystem workspace roots, a group
switcher, invitations, public publication, comments, or per-recording ACLs.

## Schema And Migration

Add Alembic head `20260728_0002` with:

- `groups`;
- `group_memberships`;
- `profiles`;
- `profile_controllers`;
- `group_profiles`;
- `workspace_group_grants`; and
- compatible workspace columns for administrative group, home profile,
  storage key, creator, update, and archive metadata.

Migration behavior:

1. Seed stable group `group:home` as `Family`, kind `household`.
2. Attach reserved workspace `local` to that group and map its existing root
   through a reserved legacy storage key.
3. Convert each existing workspace membership into a group membership without
   weakening the direct workspace role.
4. Create one stable self profile for every existing user, with a controller
   link and group affiliation.
5. Leave every existing recording's performer unassigned.
6. Make repeated catalog initialization and migration safe.

The migration must not move or rewrite any existing session, recording,
event, score, or artifact file.

## Application And API

Extend the framework-independent identity boundary with:

- group, group-membership, profile, controller, and affiliation value types;
- list-visible-groups and list-workspace-profiles queries;
- owner/admin managed-profile creation;
- effective workspace authorization across direct memberships and explicit
  group grants; and
- account creation that joins the seeded group while preserving the requested
  direct workspace role.

Add versioned contracts and authenticated routes for:

- listing the current account's groups;
- listing profiles available in an authorized workspace; and
- creating a managed profile in a group.

Extend session contracts and application annotations with nullable
`created_by_user_id` and `performed_by_profile_id`. Authenticated capture and
recording import validate and freeze the selected profile at Start. Legacy,
fixture, desktop-local, and unauthenticated-compatible paths may leave creator
or performer absent according to their declared identity boundary.

Session annotation mutation may change performer attribution separately from
the human session title. It may not alter completed capture evidence.

## UI Contract

Keep the current root library and one physical workspace:

```text
Family recordings                         [Kyle account ▾]

People
  [All] [Kyle] [Daughter] [Nephew] [Unassigned]
```

New capture/import shows:

```text
Who's playing?
  [Kyle] [Daughter] [Nephew]

Save to
  Family recordings · Shared workspace
```

The active capture repeats the frozen performer. Profile selection is
browser/device convenience only and never replaces the authenticated
principal.

Profile creation lives behind the account menu or an adjacent manage action.
It creates a bounded display name, immediately refreshes the picker and
filters, and does not create an account or credential.

Session cards and selected-session identity show the resolved performer or
**Performer unassigned**. An editor/owner may reassign the selected session
through an explicit profile control.

## Invariants

- The signed-in user remains the actor after every performer switch.
- Profile IDs are never accepted as authorization principals.
- Existing workspace owner/editor/viewer behavior does not weaken.
- A group membership alone grants no recording access without an explicit
  workspace grant.
- A disabled account loses access without losing creator history.
- A disabled profile cannot be selected for new work but remains visible on
  attributed history.
- Capture Start freezes creator, performer, workspace, session, and capture
  identity together.
- A late response or later picker change cannot retarget an active session.
- Existing recordings remain readable and unassigned until explicitly edited.
- Title and performer edits remain application metadata.
- The current session root and all existing artifact hashes remain unchanged.
- Fixture, local browser, authenticated family, and desktop compositions keep
  their declared identity behavior.

## Validation

- Migration tests cover empty catalogs, upgrade from `20260728_0001`,
  backfill, idempotent initialization, constraints, and unchanged session
  roots.
- Identity tests cover seeded group/profile relationships, managed-profile
  authorization, profile visibility, direct and group-grant effective roles,
  and account creation.
- Application and adapter tests cover creator/performer absence, capture-time
  persistence, explicit reassignment, old application documents, and title
  preservation.
- FastAPI tests cover anonymous denial, member reads, owner/admin profile
  creation, viewer denial, invalid profile/workspace targets, capture/import
  attribution, and protected profile enumeration.
- Generated OpenAPI and TypeScript remain in sync.
- React tests cover account-menu separation, profile creation, picker
  selection, capture freeze, person filters, unassigned legacy sessions,
  performer labels, and reassignment.
- Run focused tests, TypeScript, the production build, Ruff, Git whitespace,
  and the complete migration regression.
- If the shared macOS service is active, restart it and verify the public
  homepage, anonymous API protection, authenticated family check, seeded
  profile visibility, and unchanged retained session/artifact access.

## Execution Record

Implemented:

- Alembic `20260728_0002` adds the generic relational model and safely
  backfills the existing account, direct membership, self profile, controller,
  Family group affiliation, and reserved workspace metadata.
- The migration snapshots and restores membership rows around SQLite batch
  table recreation. A v1-to-v2 regression reproduces this boundary and checks
  the resulting controller/profile/group links.
- Identity application and SQLAlchemy adapters now resolve direct and
  explicit group-grant workspace roles, enumerate bounded profiles, create
  managed profiles for group owners/admins, and validate performer selection.
- Session application metadata stores creator account provenance and editable
  performer attribution without changing capture manifests or artifact
  evidence.
- Family and loopback adapters expose the generated group/profile/performer
  API, propagate the profile through microphone Start and recording import,
  and keep legacy/local paths explicitly nullable.
- The React app distinguishes account from performer, persists a per-browser
  default performer, adds the capture picker, managed-profile form,
  performer labels and filtering, and selected-session reassignment.

Validation:

- Complete Python suite: `222 passed` after the explicit group-grant
  regression was added; the only output is the two pre-existing dependency
  warnings.
- React/TypeScript: `93 passed`, Node contract fixtures `6 passed`,
  `tsc --noEmit` clean, production Vite build complete, and generated OpenAPI
  and TypeScript contracts in sync.
- Ruff and Git whitespace checks pass.
- Browser QA at 1440px and 390px covered the Sessions filter, New-performance
  picker, authenticated account/profile menu, and managed-profile form with
  no console errors or horizontal overflow.

Live migration:

- A SQLite online backup of catalog revision `20260728_0001` was written
  before restart with mode `0600` and passed `PRAGMA integrity_check`.
- The active macOS service was restarted onto revision `20260728_0002`.
- The catalog passes `PRAGMA integrity_check`; one account, one direct
  membership, one Family group, and one self profile are present.
- All nine pre-existing session roots remain present and intentionally
  unassigned.
- The public homepage returns HTTP 200; anonymous capabilities return 401;
  authenticated workspace/group/profile/capability routes return the new
  Family contract.
- The retained live smoke test read a 1,024-byte audio range and a 701,346-byte
  MusicXML score, and revoked its temporary operator session.

Deliberately deferred:

- multiple physical workspace roots and context switching;
- invitations or browser account creation;
- bulk legacy assignment;
- profile editing/disabling and account-to-existing-profile linking;
- public publishing, per-recording ACLs, comments, and teacher workflows.
