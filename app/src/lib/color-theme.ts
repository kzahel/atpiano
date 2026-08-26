import { invoke } from "@tauri-apps/api/core";

export const COLOR_THEME_STORAGE_KEY = "atpiano:color-theme";

export type ColorTheme = "light" | "dark";

async function applyNativeColorTheme(theme: ColorTheme): Promise<void> {
  if (!("__TAURI_INTERNALS__" in window)) return;
  try {
    const internals = Reflect.get(window, "__TAURI_INTERNALS__") as {
      readonly metadata?: {
        readonly currentWindow?: { readonly label?: string };
      };
    };
    await invoke("plugin:window|set_theme", {
      label: internals.metadata?.currentWindow?.label ?? "main",
      value: theme,
    });
  } catch {
    // Web content still has the requested theme if native chrome is unavailable.
  }
}

export function storedColorTheme(
  storage?: Pick<Storage, "getItem">,
): ColorTheme {
  try {
    const value = (storage ?? window.localStorage).getItem(
      COLOR_THEME_STORAGE_KEY,
    );
    return value === "dark" ? "dark" : "light";
  } catch {
    return "light";
  }
}

export function applyColorTheme(theme: ColorTheme): void {
  document.documentElement.dataset.theme = theme;
  document.documentElement.style.colorScheme = theme;
  void applyNativeColorTheme(theme);
}

export function persistColorTheme(
  theme: ColorTheme,
  storage?: Pick<Storage, "setItem">,
): void {
  try {
    (storage ?? window.localStorage).setItem(COLOR_THEME_STORAGE_KEY, theme);
  } catch {
    // Applying the choice still works for the current app session.
  }
  applyColorTheme(theme);
}
