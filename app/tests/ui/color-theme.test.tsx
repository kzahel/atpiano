import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { ThemeToggle } from "../../src/components/theme-toggle.js";
import {
  applyColorTheme,
  COLOR_THEME_STORAGE_KEY,
} from "../../src/lib/color-theme.js";

describe("color theme", () => {
  beforeEach(() => {
    window.localStorage.removeItem(COLOR_THEME_STORAGE_KEY);
    delete document.documentElement.dataset.theme;
    document.documentElement.style.removeProperty("color-scheme");
  });

  afterEach(() => {
    window.localStorage.removeItem(COLOR_THEME_STORAGE_KEY);
    delete document.documentElement.dataset.theme;
    document.documentElement.style.removeProperty("color-scheme");
    Reflect.deleteProperty(window, "__TAURI_INTERNALS__");
  });

  it("defaults to the website-like light theme and persists dark mode", async () => {
    const user = userEvent.setup();
    const firstRender = render(<ThemeToggle />);

    expect(document.documentElement.dataset.theme).toBe("light");
    expect(document.documentElement.style.colorScheme).toBe("light");
    await user.click(screen.getByRole("button", { name: "Switch to dark theme" }));

    expect(window.localStorage.getItem(COLOR_THEME_STORAGE_KEY)).toBe("dark");
    expect(document.documentElement.dataset.theme).toBe("dark");
    expect(document.documentElement.style.colorScheme).toBe("dark");

    firstRender.unmount();
    render(<ThemeToggle />);
    expect(screen.getByRole("button", { name: "Switch to light theme" }))
      .toBeTruthy();
  });

  it("also applies the choice to native desktop window chrome", async () => {
    const invoke = vi.fn().mockResolvedValue(undefined);
    Object.defineProperty(window, "__TAURI_INTERNALS__", {
      configurable: true,
      value: {
        invoke,
        metadata: { currentWindow: { label: "main" } },
      },
    });

    applyColorTheme("dark");

    await waitFor(() => expect(invoke).toHaveBeenCalledWith(
      "plugin:window|set_theme",
      { label: "main", value: "dark" },
      undefined,
    ));
  });
});
