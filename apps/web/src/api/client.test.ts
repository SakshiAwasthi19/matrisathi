import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

type ClientModule = typeof import("./client");

const PERSON_INPUT = { full_name: "Synthetic Mother A", facility_id: "f1", phone: "1000000000" };

let fetchMock: ReturnType<typeof vi.fn>;
let client: ClientModule;

function jsonResponse(status: number, body: unknown = {}): Response {
  return new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } });
}

function pathOf(url: unknown): string {
  return String(url).replace(/^.*\/api\/v1/, "");
}

function calls(): { path: string; key: string | undefined }[] {
  return fetchMock.mock.calls.map(([url, init]) => ({
    path: pathOf(url),
    key: ((init as RequestInit).headers as Record<string, string>)["Idempotency-Key"],
  }));
}

beforeEach(async () => {
  // Fresh module per test: the client keeps refresh/handler state at module level.
  vi.resetModules();
  fetchMock = vi.fn();
  vi.stubGlobal("fetch", fetchMock);
  client = await import("./client");
});

afterEach(() => {
  vi.useRealTimers();
  vi.unstubAllGlobals();
});

describe("idempotent creates", () => {
  it("sends the Idempotency-Key header on keyed creates", async () => {
    fetchMock.mockResolvedValueOnce(jsonResponse(201, { id: "p1" }));
    await client.api.createPerson(PERSON_INPUT, "key-1");
    fetchMock.mockResolvedValueOnce(jsonResponse(201, { id: "e1" }));
    await client.api.createPregnancyEpisode("p1", "key-2");
    expect(calls()).toEqual([
      { path: "/people", key: "key-1" },
      { path: "/pregnancy-episodes", key: "key-2" },
    ]);
  });

  it("retries a network failure with the same key", async () => {
    vi.useFakeTimers();
    fetchMock
      .mockRejectedValueOnce(new TypeError("Failed to fetch"))
      .mockRejectedValueOnce(new TypeError("Failed to fetch"))
      .mockResolvedValueOnce(jsonResponse(201, { id: "p1" }));

    const pending = client.api.createPerson(PERSON_INPUT, "key-1");
    await vi.advanceTimersByTimeAsync(1000);
    await vi.advanceTimersByTimeAsync(3000);

    await expect(pending).resolves.toEqual({ id: "p1" });
    expect(calls().map((c) => c.key)).toEqual(["key-1", "key-1", "key-1"]);
  });

  it("gives up after three attempts", async () => {
    vi.useFakeTimers();
    fetchMock.mockRejectedValue(new TypeError("Failed to fetch"));

    const assertion = expect(client.api.createPerson(PERSON_INPUT, "key-1")).rejects.toThrow("Failed to fetch");
    await vi.advanceTimersByTimeAsync(4000);
    await assertion;
    expect(fetchMock).toHaveBeenCalledTimes(3);
  });

  it("does not retry an HTTP error response", async () => {
    fetchMock.mockResolvedValueOnce(jsonResponse(500, { detail: "boom" }));
    await expect(client.api.createPerson(PERSON_INPUT, "key-1")).rejects.toMatchObject({ status: 500 });
    expect(fetchMock).toHaveBeenCalledTimes(1);
  });

  it("does not retry requests without a key", async () => {
    fetchMock.mockRejectedValueOnce(new TypeError("Failed to fetch"));
    await expect(client.api.verifyContact("p1")).rejects.toThrow("Failed to fetch");
    expect(fetchMock).toHaveBeenCalledTimes(1);
  });
});

describe("session refresh", () => {
  it("refreshes once on 401 and replays the request", async () => {
    fetchMock
      .mockResolvedValueOnce(jsonResponse(401, { detail: "Not authenticated" }))
      .mockResolvedValueOnce(jsonResponse(200, {}))
      .mockResolvedValueOnce(jsonResponse(200, { id: "p1" }));

    await expect(client.api.getPerson("p1")).resolves.toEqual({ id: "p1" });
    expect(calls().map((c) => c.path)).toEqual(["/people/p1", "/auth/refresh", "/people/p1"]);
  });

  it("replays a keyed create with the same key after refreshing", async () => {
    fetchMock
      .mockResolvedValueOnce(jsonResponse(401, { detail: "Not authenticated" }))
      .mockResolvedValueOnce(jsonResponse(200, {}))
      .mockResolvedValueOnce(jsonResponse(201, { id: "p1" }));

    await client.api.createPerson(PERSON_INPUT, "key-1");
    expect(calls()).toEqual([
      { path: "/people", key: "key-1" },
      { path: "/auth/refresh", key: undefined },
      { path: "/people", key: "key-1" },
    ]);
  });

  it("shares one refresh between concurrent 401s", async () => {
    let releaseRefresh: () => void = () => {};
    const refreshGate = new Promise<void>((resolve) => {
      releaseRefresh = () => resolve();
    });
    let refreshed = false;

    fetchMock.mockImplementation(async (url: unknown) => {
      const path = pathOf(url);
      if (path === "/auth/refresh") {
        await refreshGate;
        refreshed = true;
        return jsonResponse(200, {});
      }
      return refreshed ? jsonResponse(200, { path }) : jsonResponse(401, { detail: "Not authenticated" });
    });

    const pending = Promise.all([
      client.api.getPerson("a"),
      client.api.getPerson("b"),
      client.api.getPregnancyEpisode("c"),
    ]);
    await new Promise((resolve) => setTimeout(resolve, 0));
    releaseRefresh();

    await expect(pending).resolves.toHaveLength(3);
    expect(calls().filter((c) => c.path === "/auth/refresh")).toHaveLength(1);
  });

  it("serializes refresh across tabs with the Web Locks API when available", async () => {
    const request = vi.fn((_name: string, fn: () => Promise<unknown>) => fn());
    vi.stubGlobal("navigator", { locks: { request } });
    fetchMock
      .mockResolvedValueOnce(jsonResponse(401, { detail: "Not authenticated" }))
      .mockResolvedValueOnce(jsonResponse(200, {}))
      .mockResolvedValueOnce(jsonResponse(200, { id: "p1" }));

    await client.api.getPerson("p1");
    expect(request).toHaveBeenCalledTimes(1);
    expect(request.mock.calls[0][0]).toBe("matrisathi-refresh");
  });

  it("reports an expired session when the refresh is refused", async () => {
    const onExpired = vi.fn();
    client.setSessionExpiredHandler(onExpired);
    fetchMock
      .mockResolvedValueOnce(jsonResponse(401, { detail: "Not authenticated" }))
      .mockResolvedValueOnce(jsonResponse(401, { detail: "Not authenticated" }));

    await expect(client.api.getPerson("p1")).rejects.toMatchObject({ status: 401 });
    expect(onExpired).toHaveBeenCalledTimes(1);
    expect(fetchMock).toHaveBeenCalledTimes(2);
  });

  it("does not end the session when the refresh fails on the network", async () => {
    const onExpired = vi.fn();
    client.setSessionExpiredHandler(onExpired);
    fetchMock
      .mockResolvedValueOnce(jsonResponse(401, { detail: "Not authenticated" }))
      .mockRejectedValueOnce(new TypeError("Failed to fetch"));

    await expect(client.api.getPerson("p1")).rejects.toThrow("Failed to fetch");
    expect(onExpired).not.toHaveBeenCalled();
  });

  it("does not refresh on a failed login", async () => {
    const onExpired = vi.fn();
    client.setSessionExpiredHandler(onExpired);
    fetchMock.mockResolvedValueOnce(jsonResponse(401, { detail: "Invalid username or password" }));

    await expect(client.api.login("coordinator1", "wrong")).rejects.toMatchObject({ status: 401 });
    expect(fetchMock).toHaveBeenCalledTimes(1);
    expect(onExpired).not.toHaveBeenCalled();
  });

  it("refreshes before logging out with an expired access token", async () => {
    fetchMock
      .mockResolvedValueOnce(jsonResponse(401, { detail: "Not authenticated" }))
      .mockResolvedValueOnce(jsonResponse(200, {}))
      .mockResolvedValueOnce(new Response(null, { status: 204 }));

    await client.api.logout();
    expect(calls().map((c) => c.path)).toEqual(["/auth/logout", "/auth/refresh", "/auth/logout"]);
  });
});
