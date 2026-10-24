import { NextRequest } from "next/server";
import { afterEach, expect, it, vi } from "vitest";
import { proxy } from "@/proxy";

afterEach(() => {
  vi.unstubAllEnvs();
  vi.resetModules();
});

it.each([
  ["development", "http://localhost:8000", true],
  ["production", "http://localhost:8000", false],
  ["development", "same-origin", false],
])(
  "preserves absolute redirect hosts only for the local API (%s, %s)",
  async (environment, apiOrigin, expected) => {
    vi.stubEnv("NODE_ENV", environment);
    vi.stubEnv("NEXT_PUBLIC_API_BASE_URL", apiOrigin);
    const { default: config } = await import("../../next.config");
    expect(config.skipProxyUrlNormalize).toBe(expected);
  },
);

it("opens the local app on the origin trusted by its API", () => {
  vi.stubEnv("NODE_ENV", "development");
  vi.stubEnv("NEXT_PUBLIC_API_BASE_URL", "http://localhost:8000");
  const response = proxy(
    new NextRequest("http://127.0.0.1:3000/workspaces?offset=20", {
      headers: { host: "127.0.0.1:3000" },
    }),
  );
  expect(response.status).toBe(307);
  expect(response.headers.get("location")).toBe(
    "http://localhost:3000/workspaces?offset=20",
  );
});

it.each([
  ["production", "http://localhost:8000"],
  ["development", "same-origin"],
  ["development", "http://127.0.0.1:8000"],
])("preserves the %s deployment origin for %s", (environment, apiOrigin) => {
  vi.stubEnv("NODE_ENV", environment);
  vi.stubEnv("NEXT_PUBLIC_API_BASE_URL", apiOrigin);
  expect(
    proxy(
      new NextRequest("http://127.0.0.1:3000/login", {
        headers: { host: "127.0.0.1:3000" },
      }),
    ).headers.get("location"),
  ).toBeNull();
});

it("does not redirect form submissions or another development port", () => {
  vi.stubEnv("NODE_ENV", "development");
  vi.stubEnv("NEXT_PUBLIC_API_BASE_URL", "http://localhost:8000");
  expect(
    proxy(
      new NextRequest("http://127.0.0.1:3000/login", {
        method: "POST",
        headers: { host: "127.0.0.1:3000" },
      }),
    ).headers.get("location"),
  ).toBeNull();
  expect(
    proxy(
      new NextRequest("http://127.0.0.1:3001/login", {
        headers: { host: "127.0.0.1:3001" },
      }),
    ).headers.get("location"),
  ).toBeNull();
});
