import { useState } from "react";

import {
  applyColorTheme,
  persistColorTheme,
  storedColorTheme,
  type ColorTheme,
} from "../lib/color-theme.js";

export function ThemeToggle({
  compact = false,
}: {
  readonly compact?: boolean;
}) {
  const [theme, setTheme] = useState<ColorTheme>(() => {
    const initialTheme = storedColorTheme();
    applyColorTheme(initialTheme);
    return initialTheme;
  });
  const nextTheme = theme === "light" ? "dark" : "light";

  return (
    <button
      className={`theme-toggle${compact ? " compact" : ""}`}
      type="button"
      aria-label={`Switch to ${nextTheme} theme`}
      title={`Switch to ${nextTheme} theme`}
      onClick={() => {
        persistColorTheme(nextTheme);
        setTheme(nextTheme);
      }}
    >
      <span aria-hidden="true">{theme === "light" ? "☀" : "☾"}</span>
      {!compact && <strong>{theme === "light" ? "Light" : "Dark"}</strong>}
    </button>
  );
}
