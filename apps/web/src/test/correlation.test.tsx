import { render, screen } from "@testing-library/react";
import { expect, it, vi } from "vitest";
import { ApiError, request } from "@/lib/api/client";
import { ErrorBox } from "@/components/ui";

it("sends a fresh request ID and presents only a validated support ID", async () => {
  const identifier = "af954a4a-6803-47d9-ad34-b36143df3b03";
  const fetcher = vi.spyOn(globalThis, "fetch").mockResolvedValue(
    new Response(JSON.stringify({ detail: "private failure" }), {
      status: 503,
      headers: { "X-Request-ID": identifier },
    }),
  );
  let failure: unknown;
  try {
    await request("/api/v1/auth/me");
  } catch (error) {
    failure = error;
  }
  const sent = fetcher.mock.calls[0][1]?.headers as Headers;
  expect(sent.get("X-Request-ID")).toMatch(/^[0-9a-f-]{36}$/);
  expect(failure).toBeInstanceOf(ApiError);
  render(<ErrorBox error={failure} />);
  expect(screen.getByText(identifier)).toBeInTheDocument();
  expect(screen.queryByText("private failure")).not.toBeInTheDocument();
  fetcher.mockResolvedValue(
    new Response("{}", {
      status: 500,
      headers: { "X-Request-ID": "arbitrary-private-string" },
    }),
  );
  await expect(request("/api/v1/auth/me")).rejects.toMatchObject({
    requestId: undefined,
  });
  fetcher.mockRestore();
});
