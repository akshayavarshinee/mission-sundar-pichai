"use client";

import { useEffect, useState } from "react";
import { useTheme } from "next-themes";
import { Moon, Sun } from "lucide-react";

// A compact light/dark switch. Renders a stable placeholder until mounted to
// avoid a hydration mismatch (the resolved theme is only known on the client).
export default function ThemeToggle() {
  const { resolvedTheme, setTheme } = useTheme();
  const [mounted, setMounted] = useState(false);

  useEffect(() => setMounted(true), []);

  const isDark = resolvedTheme === "dark";

  return (
    <button
      type="button"
      aria-label="Toggle colour theme"
      title={mounted ? (isDark ? "Switch to light" : "Switch to dark") : undefined}
      onClick={() => setTheme(isDark ? "light" : "dark")}
      className="btn h-9 w-9 p-0"
    >
      {mounted ? (
        isDark ? (
          <Sun className="h-4 w-4" />
        ) : (
          <Moon className="h-4 w-4" />
        )
      ) : (
        <span className="h-4 w-4" />
      )}
    </button>
  );
}
