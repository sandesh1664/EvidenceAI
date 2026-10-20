import { createServer } from "node:http";
import { expect, it, vi } from "vitest";

it("blocks an unmocked fetch before any local HTTP receiver sees it", async () => {
  let received = 0;
  const server = createServer((_request, response) => {
    received += 1;
    response.end("synthetic receiver");
  });
  await new Promise<void>((resolve) => server.listen(0, "127.0.0.1", resolve));
  try {
    const address = server.address();
    if (!address || typeof address === "string") throw new Error("No fixture port");
    await fetch(`http://127.0.0.1:${address.port}/fixture`).catch(() => undefined);
    expect(received).toBe(0);
  } finally {
    await new Promise<void>((resolve, reject) => server.close((error) => error ? reject(error) : resolve()));
  }
});

it("allows an explicitly mocked fetch response", async () => {
  vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response("fixture")));
  expect(await (await fetch("https://fixture.invalid/")).text()).toBe("fixture");
});
