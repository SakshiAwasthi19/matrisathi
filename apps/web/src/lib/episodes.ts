import type { PregnancyEpisode } from "../api/client";

export type EpisodeAction = { kind: "continue"; episodeId: string } | { kind: "start" };

/** D13: a mother has at most one ACTIVE episode. If she has one, staff
 * continue it; only otherwise do they start a new one. */
export function episodeAction(episodes: readonly PregnancyEpisode[]): EpisodeAction {
  const active = episodes.find((e) => e.status === "ACTIVE");
  return active ? { kind: "continue", episodeId: active.id } : { kind: "start" };
}
