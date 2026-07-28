import { useEffect, useRef, useState, type FormEvent } from "react";

import type {
  Group,
  Profile,
} from "../runtime/atpiano-runtime.js";

export function PerformerSelect({
  profiles,
  value,
  includeUnassigned = false,
  disabled = false,
  label = "Who’s playing?",
  onChange,
}: {
  readonly profiles: readonly Profile[];
  readonly value: string | null;
  readonly includeUnassigned?: boolean;
  readonly disabled?: boolean;
  readonly label?: string;
  readonly onChange: (profileId: string | null) => void;
}) {
  return (
    <label className="performer-select">
      <span>{label}</span>
      <select
        value={value ?? ""}
        disabled={disabled || profiles.length === 0}
        onChange={(event) =>
          onChange(event.currentTarget.value || null)
        }
      >
        {includeUnassigned && <option value="">Unassigned</option>}
        {!includeUnassigned && value === null && (
          <option value="">Choose a profile</option>
        )}
        {profiles.map((profile) => (
          <option key={profile.profile_id} value={profile.profile_id}>
            {profile.display_name}
          </option>
        ))}
      </select>
    </label>
  );
}

export function AccountMenu({
  username,
  displayName,
  workspaceName,
  group,
  profiles,
  selectedProfileId,
  logoutPending,
  createPending,
  createError,
  onSelectProfile,
  onCreateProfile,
  onLogout,
}: {
  readonly username: string;
  readonly displayName: string;
  readonly workspaceName: string;
  readonly group: Group | undefined;
  readonly profiles: readonly Profile[];
  readonly selectedProfileId: string | null;
  readonly logoutPending: boolean;
  readonly createPending: boolean;
  readonly createError: string | null;
  readonly onSelectProfile: (profileId: string | null) => void;
  readonly onCreateProfile: (displayName: string) => void;
  readonly onLogout: () => void;
}) {
  const [open, setOpen] = useState(false);
  const [profileName, setProfileName] = useState("");
  const container = useRef<HTMLDivElement>(null);
  const canManage =
    group?.current_user_role === "owner" ||
    group?.current_user_role === "admin";
  const selectedName = profiles.find(
    (profile) => profile.profile_id === selectedProfileId,
  )?.display_name;

  useEffect(() => {
    if (!open) return;
    const close = (event: PointerEvent) => {
      if (
        event.target instanceof Node &&
        !container.current?.contains(event.target)
      ) {
        setOpen(false);
      }
    };
    window.addEventListener("pointerdown", close);
    return () => window.removeEventListener("pointerdown", close);
  }, [open]);

  const submit = (event: FormEvent) => {
    event.preventDefault();
    const name = profileName.trim();
    if (!name) return;
    onCreateProfile(name);
    setProfileName("");
  };

  return (
    <div className="account-menu" ref={container}>
      <button
        className="account-menu-trigger"
        type="button"
        aria-haspopup="dialog"
        aria-expanded={open}
        onClick={() => setOpen((value) => !value)}
      >
        <span aria-hidden="true">
          {displayName.trim().charAt(0).toUpperCase()}
        </span>
        <i>
          <strong>{selectedName ?? displayName}</strong>
          <small>{workspaceName}</small>
        </i>
        <b aria-hidden="true">⌄</b>
      </button>

      {open && (
        <section className="account-menu-popover" aria-label="Account and profiles">
          <header>
            <p>Signed in account</p>
            <strong>{displayName}</strong>
            <small>@{username}</small>
          </header>

          <PerformerSelect
            profiles={profiles}
            value={selectedProfileId}
            label="Default performer"
            onChange={onSelectProfile}
          />
          <p className="account-menu-help">
            This changes who new recordings are attributed to. It does not
            change the signed-in account or its permissions.
          </p>

          {canManage && (
            <form className="profile-create" onSubmit={submit}>
              <label>
                <span>Add a managed profile</span>
                <input
                  value={profileName}
                  maxLength={128}
                  placeholder="Daughter, nephew, student…"
                  disabled={createPending}
                  onChange={(event) =>
                    setProfileName(event.currentTarget.value)
                  }
                />
              </label>
              <button
                type="submit"
                disabled={createPending || !profileName.trim()}
              >
                {createPending ? "Adding…" : "Add profile"}
              </button>
            </form>
          )}
          {createError && (
            <p className="account-menu-error" role="alert">{createError}</p>
          )}

          <footer>
            <span>{group?.name ?? "Shared workspace"}</span>
            <button
              type="button"
              disabled={logoutPending}
              onClick={onLogout}
            >
              {logoutPending ? "Signing out…" : "Sign out"}
            </button>
          </footer>
        </section>
      )}
    </div>
  );
}
