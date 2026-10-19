import "@testing-library/jest-dom/vitest";
import { cleanup } from "@testing-library/react";
import { afterEach, beforeEach, vi } from "vitest";
import { clearResources } from "@/hooks/use-resource";
class Channel {
  onmessage: ((event: MessageEvent) => void) | null = null;
  postMessage = vi.fn();
  close = vi.fn();
}
vi.stubGlobal("BroadcastChannel", Channel);
HTMLDialogElement.prototype.showModal = function () {
  this.open = true;
};
HTMLDialogElement.prototype.close = function () {
  this.open = false;
};
beforeEach(() => {
  clearResources();
  localStorage.clear();
  Object.defineProperty(document, "visibilityState", {
    value: "visible",
    configurable: true,
  });
});
afterEach(() => {
  cleanup();
  clearResources();
  vi.unstubAllGlobals();
  vi.stubGlobal("BroadcastChannel", Channel);
});
