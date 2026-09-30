import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

describe("expiration de session", () => {
  it("renvoie vers la connexion quand l'API répond 401", async () => {
    vi.stubEnv("VITE_USE_MOCK", "false");
    vi.resetModules();
    const fetchMock = vi.fn()
      .mockResolvedValueOnce({
        ok: true,
        status: 200,
        json: async () => ({ access_token: "temporary-token", token_type: "bearer", expires_in: 1800, role: "employee" }),
      })
      .mockResolvedValueOnce({ ok: false, status: 401 });
    vi.stubGlobal("fetch", fetchMock);

    const { default: App } = await import("./App.jsx");
    const user = userEvent.setup();
    render(<App />);

    await user.type(screen.getByLabelText("Identifiant"), "demo-user");
    await user.type(screen.getByLabelText("Mot de passe"), "password-demo");
    await user.click(screen.getByRole("button", { name: /se connecter/i }));
    await screen.findByRole("heading", { name: "Quelle information cherchez-vous ?" });

    await user.type(screen.getByLabelText("Votre question"), "Quelle règle de préavis ?");
    await user.click(screen.getByRole("button", { name: "Rechercher" }));

    expect(await screen.findByRole("heading", { name: "Bienvenue" })).toBeInTheDocument();
    expect(fetchMock).toHaveBeenCalledTimes(2);
  });
});
