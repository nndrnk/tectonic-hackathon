import { describe, expect, it, vi } from "vitest";

describe("gestion de session API", () => {
  it("ne persiste jamais le jeton dans localStorage", async () => {
    vi.stubEnv("VITE_USE_MOCK", "true");
    vi.resetModules();
    const storageSpy = vi.spyOn(Storage.prototype, "setItem");
    const api = await import("./api.js");

    await api.login({ username: "demo-user", password: "password-demo" });

    expect(storageSpy).not.toHaveBeenCalled();
    api.logout();
  });
});
