import type { Config } from "tailwindcss";

const config: Config = {
  content: [
    "./app/**/*.{ts,tsx}",
    "./components/**/*.{ts,tsx}",
    "./lib/**/*.{ts,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        ink: "#0a0e1a",
        panel: "#111827",
        panel2: "#0f1626",
        edge: "#1f2a3d",
        accent: "#38bdf8",
        good: "#34d399",
        warn: "#fbbf24",
        bad: "#f87171",
        veto: "#a78bfa",
      },
      fontFamily: {
        mono: ["ui-monospace", "SFMono-Regular", "Menlo", "monospace"],
      },
      keyframes: {
        pulseRow: {
          "0%": { backgroundColor: "rgba(56,189,248,0.18)" },
          "100%": { backgroundColor: "transparent" },
        },
      },
      animation: {
        pulseRow: "pulseRow 1.4s ease-out",
      },
    },
  },
  plugins: [],
};

export default config;
