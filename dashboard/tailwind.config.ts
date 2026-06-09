import type { Config } from "tailwindcss";

// Colours are driven by CSS variables (see app/globals.css) so the same class
// names resolve to the right value in both light and dark themes. Each token is
// stored as an `R G B` triplet and consumed via the `<alpha-value>` placeholder
// so Tailwind's `/<alpha>` opacity modifier works everywhere.
const rgb = (variable: string) => `rgb(var(${variable}) / <alpha-value>)`;

const config: Config = {
  darkMode: "class",
  content: [
    "./app/**/*.{ts,tsx}",
    "./components/**/*.{ts,tsx}",
    "./lib/**/*.{ts,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        // Surfaces
        bg: rgb("--c-bg"),
        panel: rgb("--c-panel"),
        panel2: rgb("--c-panel-2"),
        edge: rgb("--c-edge"),
        // Text
        ink: rgb("--c-ink"),
        body: rgb("--c-body"),
        muted: rgb("--c-muted"),
        faint: rgb("--c-faint"),
        // Semantic accents
        accent: rgb("--c-accent"),
        good: rgb("--c-good"),
        warn: rgb("--c-warn"),
        bad: rgb("--c-bad"),
        veto: rgb("--c-veto"),
      },
      fontFamily: {
        sans: ["var(--font-sans)", "ui-sans-serif", "system-ui", "sans-serif"],
        mono: ["var(--font-mono)", "ui-monospace", "SFMono-Regular", "monospace"],
      },
      boxShadow: {
        card: "0 1px 2px 0 rgb(0 0 0 / 0.04), 0 1px 3px 0 rgb(0 0 0 / 0.06)",
        "card-dark":
          "0 1px 0 0 rgb(255 255 255 / 0.02) inset, 0 8px 24px -12px rgb(0 0 0 / 0.6)",
      },
      keyframes: {
        pulseRow: {
          "0%": { backgroundColor: "rgb(var(--c-accent) / 0.16)" },
          "100%": { backgroundColor: "transparent" },
        },
        fadeIn: {
          "0%": { opacity: "0", transform: "translateY(4px)" },
          "100%": { opacity: "1", transform: "translateY(0)" },
        },
      },
      animation: {
        pulseRow: "pulseRow 1.4s ease-out",
        fadeIn: "fadeIn 0.25s ease-out",
      },
    },
  },
  plugins: [],
};

export default config;
