import { act, renderHook, waitFor } from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";
import { useResource } from "@/hooks/use-resource";
import { api } from "@/lib/api/client";
afterEach(() => vi.useRealTimers());
it("does not reuse private cached data across accounts", async () => {
  const fetcher = vi
    .fn()
    .mockResolvedValueOnce(
      new Response(JSON.stringify({ secret: "Account A" })),
    )
    .mockResolvedValueOnce(
      new Response(JSON.stringify({ secret: "Account B" })),
    );
  vi.stubGlobal("fetch", fetcher);
  const { result, rerender } = renderHook(
    ({ account }) =>
      useResource<{ secret: string }>("/api/v1/private", account),
    { initialProps: { account: "A" } },
  );
  await waitFor(() => expect(result.current.data?.secret).toBe("Account A"));
  rerender({ account: "B" });
  expect(result.current.data).toBeUndefined();
  await waitFor(() => expect(result.current.data?.secret).toBe("Account B"));
  expect(fetcher).toHaveBeenCalledTimes(2);
});
it("aborts obsolete reads and ignores late responses from another workspace", async () => {
  let resolveFirst: (value: Response) => void = () => {};
  const fetcher = vi
    .fn()
    .mockImplementationOnce(
      () =>
        new Promise((resolve) => {
          resolveFirst = resolve;
        }),
    )
    .mockResolvedValueOnce(
      new Response(JSON.stringify({ name: "Second workspace" })),
    );
  vi.stubGlobal("fetch", fetcher);
  const { result, rerender } = renderHook(
    ({ path }) => useResource<{ name: string }>(path, "A"),
    { initialProps: { path: "/api/v1/first" } },
  );
  const signal = fetcher.mock.calls[0][1].signal;
  rerender({ path: "/api/v1/second" });
  expect(signal.aborted).toBe(true);
  await waitFor(() =>
    expect(result.current.data?.name).toBe("Second workspace"),
  );
  await act(async () =>
    resolveFirst(
      new Response(JSON.stringify({ name: "First workspace PRIVATE" })),
    ),
  );
  expect(result.current.data?.name).toBe("Second workspace");
});
it("explicit refresh bypasses the short-lived cache", async () => {
  const fetcher = vi
    .fn()
    .mockResolvedValueOnce(new Response("[1]"))
    .mockResolvedValueOnce(new Response("[2]"));
  vi.stubGlobal("fetch", fetcher);
  const { result } = renderHook(() =>
    useResource<number[]>("/api/v1/private", "A"),
  );
  await waitFor(() => expect(result.current.data).toEqual([1]));
  act(() => result.current.refresh());
  await waitFor(() => expect(result.current.data).toEqual([2]));
});
it("successful mutations invalidate active authenticated reads", async () => {
  let changed = false;
  vi.stubGlobal(
    "fetch",
    vi.fn((_url: string, init: RequestInit) => {
      if (init.method === "POST") {
        changed = true;
        return Promise.resolve(new Response("{}"));
      }
      return Promise.resolve(new Response(JSON.stringify({ changed })));
    }),
  );
  const { result } = renderHook(() =>
    useResource<{ changed: boolean }>("/api/v1/private", "A"),
  );
  await waitFor(() => expect(result.current.data?.changed).toBe(false));
  await act(() => api.createWorkspace("New project", ""));
  await waitFor(() => expect(result.current.data?.changed).toBe(true));
});
it("polling stops while hidden and after unmount", async () => {
  vi.useFakeTimers();
  const fetcher = vi.fn(() => Promise.resolve(new Response("[]")));
  vi.stubGlobal("fetch", fetcher);
  const { unmount } = renderHook(() =>
    useResource<unknown[]>("/api/v1/private", "A", 100),
  );
  await act(async () => {
    await vi.advanceTimersByTimeAsync(10);
  });
  expect(fetcher).toHaveBeenCalledTimes(1);
  Object.defineProperty(document, "visibilityState", {
    value: "hidden",
    configurable: true,
  });
  await act(async () => {
    await vi.advanceTimersByTimeAsync(500);
  });
  expect(fetcher).toHaveBeenCalledTimes(1);
  Object.defineProperty(document, "visibilityState", {
    value: "visible",
    configurable: true,
  });
  await act(async () => {
    document.dispatchEvent(new Event("visibilitychange"));
    await vi.advanceTimersByTimeAsync(10);
  });
  expect(fetcher).toHaveBeenCalledTimes(2);
  unmount();
  await act(async () => {
    await vi.advanceTimersByTimeAsync(1000);
  });
  expect(fetcher).toHaveBeenCalledTimes(2);
});

it("honors an explicit refresh while background polling is paused", async () => {
  const fetcher = vi
    .fn()
    .mockResolvedValueOnce(new Response("[1]"))
    .mockResolvedValueOnce(new Response("[2]"));
  vi.stubGlobal("fetch", fetcher);
  const { result } = renderHook(() =>
    useResource<number[]>("/api/v1/private", "A"),
  );
  await waitFor(() => expect(result.current.data).toEqual([1]));
  Object.defineProperty(document, "visibilityState", {
    value: "hidden",
    configurable: true,
  });
  act(() => result.current.refresh());
  await waitFor(() => expect(result.current.data).toEqual([2]));
});
