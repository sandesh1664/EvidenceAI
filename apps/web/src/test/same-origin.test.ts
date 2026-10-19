import { afterEach, expect, it, vi } from "vitest";

afterEach(() => {
  vi.restoreAllMocks();
  vi.unstubAllEnvs();
  vi.resetModules();
});

it("uses relative authenticated API requests for the same-origin deployment bundle", async () => {
  vi.stubEnv("NEXT_PUBLIC_API_BASE_URL", "same-origin");
  vi.resetModules();
  const fetcher = vi
    .spyOn(globalThis, "fetch")
    .mockResolvedValue(new Response("{}", { status: 200 }));
  const { API_ORIGIN, request } = await import("@/lib/api/client");
  expect(API_ORIGIN).toBe("");
  await request("/api/v1/auth/me");
  expect(fetcher).toHaveBeenCalledWith(
    "/api/v1/auth/me",
    expect.objectContaining({
      credentials: "include",
      cache: "no-store",
      redirect: "error",
    }),
  );
});
