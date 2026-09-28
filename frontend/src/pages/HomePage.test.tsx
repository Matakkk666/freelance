import { render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { HomePage } from "./HomePage.tsx";

function mockFetch(status: number, body: unknown) {
  vi.stubGlobal(
    "fetch",
    vi.fn(() => Promise.resolve(new Response(JSON.stringify(body), { status }))),
  );
}

describe("HomePage", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("shows that the server is up", async () => {
    mockFetch(200, { status: "ok", database: "ok" });
    render(<HomePage />);
    expect(await screen.findByText("Сервер работает")).toBeInTheDocument();
  });

  it("shows database outage from a 503 health response", async () => {
    mockFetch(503, { status: "error", database: "unavailable" });
    render(<HomePage />);
    expect(await screen.findByText("База данных недоступна")).toBeInTheDocument();
  });

  it("shows that the server is unreachable", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(() => Promise.reject(new TypeError("network"))),
    );
    vi.spyOn(console, "error").mockImplementation(() => undefined);
    render(<HomePage />);
    expect(await screen.findByText("Сервер недоступен")).toBeInTheDocument();
  });
});
