"use client";

import { ThemeProvider as NextThemeProvider } from "next-themes";

// Wraps the app with next-themes so the `.dark` class is toggled on <html>.
// `attribute="class"` matches Tailwind's `darkMode: "class"` configuration.
export default function ThemeProvider({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <NextThemeProvider
      attribute="class"
      defaultTheme="dark"
      enableSystem
      disableTransitionOnChange
    >
      {children}
    </NextThemeProvider>
  );
}
