"use client";
import { useEffect } from "react";
export function ThemeInit() {
  useEffect(() => {
    const sync = () => {
      try {
        const theme = localStorage.getItem("evidenceai:theme");
        document.documentElement.dataset.theme = ["light", "dark"].includes(
          theme || "",
        )
          ? theme!
          : "system";
      } catch {
        /* System preference remains available. */
      }
    };
    sync();
    window.addEventListener("storage", sync);
    return () => window.removeEventListener("storage", sync);
  }, []);
  return null;
}
