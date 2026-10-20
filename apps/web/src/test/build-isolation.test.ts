import { afterEach, expect, it, vi } from "vitest";

afterEach(() => {
  vi.unstubAllEnvs();
  vi.resetModules();
});

it("keeps the normal frontend build location", async () => {
  vi.stubEnv("EVIDENCEAI_E2E", "");
  vi.resetModules();
  const { default: config } = await import("../../next.config");
  expect(config.distDir).toBe(".next");
});

it("isolates acceptance artifacts from the operator's running dev server", async () => {
  vi.stubEnv("EVIDENCEAI_E2E", "1");
  vi.resetModules();
  const { default: config } = await import("../../next.config");
  expect(config.distDir).toBe(".next-e2e");
  expect(config.distDir).not.toBe(".next");
});
