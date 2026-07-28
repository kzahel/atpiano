import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { AccountMenu } from "../../src/components/profile-controls.js";
import type {
  Group,
  Profile,
} from "../../src/runtime/atpiano-runtime.js";

const group: Group = {
  schema_version: "atpiano.contract.v1",
  group_id: "group:home",
  name: "Graehl Family",
  kind: "household",
  default_space_audience: "group",
  default_space_role: "editor",
  created_at: "2026-07-28T12:00:00Z",
  current_user_role: "owner",
};

const profiles: Profile[] = [
  {
    schema_version: "atpiano.contract.v1",
    profile_id: "profile:kyle",
    display_name: "Kyle",
    disabled: false,
    created_at: "2026-07-28T12:00:00Z",
    controller_role: "owner",
  },
  {
    schema_version: "atpiano.contract.v1",
    profile_id: "profile:daughter",
    display_name: "Daughter",
    disabled: false,
    created_at: "2026-07-28T12:00:00Z",
    controller_role: "owner",
  },
];

describe("account and profile menu", () => {
  it("keeps account identity separate from the default performer", () => {
    const onSelectProfile = vi.fn();
    const onCreateProfile = vi.fn();
    render(
      <AccountMenu
        username="kyle"
        displayName="Kyle"
        workspaceName="Family recordings"
        group={group}
        profiles={profiles}
        selectedProfileId="profile:kyle"
        logoutPending={false}
        createPending={false}
        createError={null}
        onSelectProfile={onSelectProfile}
        onCreateProfile={onCreateProfile}
        onLogout={vi.fn()}
      />,
    );

    fireEvent.click(screen.getByRole("button", {
      name: /Kyle.*Family recordings/,
    }));
    expect(screen.getByText("Signed in account")).toBeTruthy();
    expect(screen.getByText("@kyle")).toBeTruthy();

    fireEvent.change(screen.getByLabelText("Default performer"), {
      target: { value: "profile:daughter" },
    });
    expect(onSelectProfile).toHaveBeenCalledWith("profile:daughter");

    fireEvent.change(screen.getByPlaceholderText(
      "Daughter, nephew, student…",
    ), {
      target: { value: "Nephew" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Add profile" }));
    expect(onCreateProfile).toHaveBeenCalledWith("Nephew");
  });

  it("does not offer profile management to ordinary group members", () => {
    render(
      <AccountMenu
        username="brother"
        displayName="Brother"
        workspaceName="Family recordings"
        group={{ ...group, current_user_role: "member" }}
        profiles={profiles}
        selectedProfileId="profile:daughter"
        logoutPending={false}
        createPending={false}
        createError={null}
        onSelectProfile={vi.fn()}
        onCreateProfile={vi.fn()}
        onLogout={vi.fn()}
      />,
    );

    fireEvent.click(screen.getByRole("button", {
      name: /Daughter.*Family recordings/,
    }));
    expect(screen.queryByText("Add a managed profile")).toBeNull();
  });
});
