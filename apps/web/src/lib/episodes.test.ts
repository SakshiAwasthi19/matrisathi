import { describe, expect, it } from "vitest";
import { ApiError, existingEpisodeId, type PregnancyEpisode } from "../api/client";
import { episodeAction } from "./episodes";

const episode = (id: string, status: string): PregnancyEpisode => ({
  id,
  mother_person_id: "p1",
  mother_full_name: "Synthetic Mother",
  facility_id: "f1",
  dating_estimate: null,
  dating_source: "UNKNOWN",
  status,
  created_at: "2026-11-07T00:00:00Z",
});

describe("continue or start an episode", () => {
  it("starts one when the mother has no episodes", () => {
    expect(episodeAction([])).toEqual({ kind: "start" });
  });

  it("starts one when all her episodes are closed", () => {
    expect(episodeAction([episode("e1", "CLOSED")])).toEqual({ kind: "start" });
  });

  it("continues her active episode instead of starting another", () => {
    expect(episodeAction([episode("e2", "ACTIVE"), episode("e1", "CLOSED")])).toEqual({
      kind: "continue",
      episodeId: "e2",
    });
  });
});

describe("409 pointing at an existing episode", () => {
  it("reads the existing episode id from a structured 409", () => {
    const err = new ApiError(409, "already active", { message: "already active", existing_episode_id: "e9" });
    expect(existingEpisodeId(err)).toBe("e9");
  });

  it("ignores other errors", () => {
    expect(existingEpisodeId(new ApiError(409, "Idempotency key already used", "Idempotency key already used"))).toBeNull();
    expect(existingEpisodeId(new ApiError(404, "Not found", "Not found"))).toBeNull();
    expect(existingEpisodeId(new Error("network"))).toBeNull();
  });
});
