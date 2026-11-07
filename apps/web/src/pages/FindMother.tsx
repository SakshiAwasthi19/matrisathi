import { useMutation, useQueries, useQueryClient } from "@tanstack/react-query";
import { ArrowRight, Building2, HeartPulse, Phone, Plus, Search } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { useLocation, useNavigate } from "react-router";
import { useTranslation } from "react-i18next";
import { api, ApiError, existingEpisodeId, type Person } from "../api/client";
import { Avatar } from "../components/Avatar";
import { PageState } from "../components/PageState";
import { Button } from "../components/ui/button";
import { Card } from "../components/ui/card";
import { Field, Input } from "../components/ui/field";
import { Alert, StatusBadge } from "../components/ui/status";
import { formatAge } from "../lib/age";
import { attemptKey, clearAttempt, createAttemptStore } from "../lib/attempts";
import { episodeAction, type EpisodeAction } from "../lib/episodes";
import { parseQuickFind } from "../lib/worklist";
import { useSession } from "../state/session";

export function FindMother({ onEpisodeCreated }: { onEpisodeCreated: (episodeId: string) => void }) {
  const { t } = useTranslation();
  const { staff } = useSession();
  const queryClient = useQueryClient();
  const [phone, setPhone] = useState("");
  const [fullName, setFullName] = useState("");
  const [formError, setFormError] = useState<string | null>(null);
  const [results, setResults] = useState<Person[] | null>(null);
  const [rowError, setRowError] = useState<Record<string, string>>({});
  const attempts = useRef(createAttemptStore());

  const facilityName = (id: string) =>
    staff?.memberships.find((m) => m.facility_id === id)?.facility_name ?? id;
  const message = (err: unknown, fallback: string) => (err instanceof ApiError ? err.message : fallback);

  const search = useMutation({
    mutationFn: (params: { phone?: string; full_name?: string }) => api.searchPeople(params),
    meta: { silent: true },
    onSuccess: (found) => setResults(found),
  });

  // Each match's episodes, so staff continue her active one (D13) instead of
  // opening another. Results are capped server-side, so this stays small.
  const episodeQueries = useQueries({
    queries: (results ?? []).map((p) => ({
      queryKey: ["episodes", p.id],
      queryFn: () => api.listEpisodes(p.id),
    })),
  });

  const openEpisode = useMutation({
    mutationFn: async ({ person, action }: { person: Person; action: EpisodeAction | null }) => {
      if (action?.kind === "continue") return action.episodeId;
      const scope = `episode:${person.id}`;
      try {
        const episode = await api.createPregnancyEpisode(
          person.id,
          attemptKey(attempts.current, scope, { person_id: person.id }),
        );
        clearAttempt(attempts.current, scope);
        return episode.id;
      } catch (err) {
        // Someone opened her episode meanwhile: go to it, never make a second.
        const existing = existingEpisodeId(err);
        if (existing) {
          clearAttempt(attempts.current, scope);
          return existing;
        }
        throw err;
      }
    },
    meta: { silent: true },
    onMutate: ({ person }) => setRowError((prev) => ({ ...prev, [person.id]: "" })),
    onSuccess: (episodeId, { person }) => {
      void queryClient.invalidateQueries({ queryKey: ["episodes", person.id] });
      onEpisodeCreated(episodeId);
    },
    onError: (err, { person }) =>
      setRowError((prev) => ({ ...prev, [person.id]: message(err, t("find.openFailed")) })),
  });

  const verify = useMutation({
    mutationFn: (person: Person) => api.verifyContact(person.id),
    onMutate: (person) => setRowError((prev) => ({ ...prev, [person.id]: "" })),
    onSuccess: (updated) => {
      setResults((prev) => prev?.map((p) => (p.id === updated.id ? updated : p)) ?? null);
      queryClient.setQueryData(["person", updated.id], updated);
    },
    onError: (err, person) =>
      setRowError((prev) => ({ ...prev, [person.id]: message(err, t("find.confirmFailed")) })),
  });

  const busyId =
    (openEpisode.isPending && openEpisode.variables?.person.id) ||
    (verify.isPending && verify.variables?.id) ||
    null;

  // Text typed in the top-bar search arrives in router state: fill the form,
  // run the search, then clear the state so a reload doesn't repeat it.
  const location = useLocation();
  const navigate = useNavigate();
  const quickFind = (location.state as { quickFind?: string } | null)?.quickFind;
  useEffect(() => {
    if (!quickFind) return;
    const params = parseQuickFind(quickFind);
    navigate(".", { replace: true, state: null });
    if (!params) return;
    setPhone(params.phone ?? "");
    setFullName(params.full_name ?? "");
    setFormError(null);
    search.mutate(params);
    // eslint-disable-next-line react-hooks/exhaustive-deps -- run once per hand-off
  }, [quickFind]);

  function handleSearch(e: React.FormEvent) {
    e.preventDefault();
    if (!phone.trim() && !fullName.trim()) {
      setFormError(t("find.needOneField"));
      return;
    }
    setFormError(null);
    search.mutate({ phone: phone.trim() || undefined, full_name: fullName.trim() || undefined });
  }

  return (
    <div className="space-y-4">
      <Card>
        <h2 className="text-lg font-semibold">{t("find.title")}</h2>
        <p className="mt-1 text-base text-muted">{t("find.intro")}</p>
        <form onSubmit={handleSearch} className="mt-4 grid gap-4 md:grid-cols-[1fr_1fr_auto] md:items-end">
          <Field label={t("find.phone")} htmlFor="search_phone">
            <Input
              id="search_phone"
              inputMode="tel"
              autoComplete="off"
              value={phone}
              onChange={(e) => setPhone(e.target.value)}
            />
          </Field>
          <Field label={t("find.name")} htmlFor="search_name">
            <Input id="search_name" autoComplete="off" value={fullName} onChange={(e) => setFullName(e.target.value)} />
          </Field>
          <Button type="submit" disabled={search.isPending}>
            <Search aria-hidden className="size-4" />
            {search.isPending ? t("find.submitting") : t("find.submit")}
          </Button>
        </form>
        {formError && (
          <Alert kind="problem" className="mt-4">
            {formError}
          </Alert>
        )}
      </Card>

      {results === null && !search.isPending && !search.isError && (
        <PageState kind="start" title={t("find.startTitle")} body={t("find.startBody")} />
      )}
      {search.isPending && <PageState kind="loading" />}
      {search.isError && (
        <PageState kind="error" body={message(search.error, t("find.failed"))} />
      )}
      {!search.isPending && !search.isError && results?.length === 0 && (
        <PageState kind="empty" title={t("find.emptyTitle")} body={t("find.emptyBody")} />
      )}

      {!search.isPending && results && results.length > 0 && (
        <section aria-label={t("find.resultsCount", { count: results.length })} className="space-y-3">
          <div className="flex flex-wrap items-baseline justify-between gap-2">
            <p className="text-sm font-semibold text-muted">{t("find.resultsCount", { count: results.length })}</p>
            {results.length > 1 && <p className="text-sm text-muted">{t("find.matchHint")}</p>}
          </div>
          <ul className="space-y-3">
            {results.map((person, index) => {
              const episodesQuery = episodeQueries[index];
              const action = episodesQuery?.data ? episodeAction(episodesQuery.data) : null;
              const opening = openEpisode.isPending && openEpisode.variables?.person.id === person.id;
              return (
              <li key={person.id}>
                <Card className="space-y-4 transition-shadow hover:shadow-raised">
                  <div className="flex flex-wrap items-center gap-3">
                    <Avatar name={person.full_name} />
                    <div className="min-w-0 flex-1">
                      <p className="text-lg font-semibold">{person.full_name}</p>
                      <p className="text-base text-muted">{formatAge(person, t)}</p>
                    </div>
                    {action?.kind === "continue" && (
                      <span className="inline-flex items-center gap-1.5 rounded-full bg-brand-soft px-3 py-1 text-sm font-semibold text-brand">
                        <HeartPulse aria-hidden className="size-4" />
                        {t("find.activeEpisode")}
                      </span>
                    )}
                  </div>
                  <dl className="grid gap-2 text-base sm:grid-cols-2">
                    <div className="flex items-center gap-2">
                      <Phone aria-hidden className="size-4 text-muted" />
                      <dt className="sr-only">{t("find.phoneLabel")}</dt>
                      <dd>{person.phone}</dd>
                    </div>
                    <div className="flex items-center gap-2">
                      <Building2 aria-hidden className="size-4 text-muted" />
                      <dt className="sr-only">{t("find.facilityLabel")}</dt>
                      <dd>{facilityName(person.registering_facility_id)}</dd>
                    </div>
                    <div className="sm:col-span-2">
                      <dt className="sr-only">{t("find.contactLabel")}</dt>
                      <dd>
                        {person.contact_verified_at ? (
                          <StatusBadge kind="confirmed">
                            {t("find.contactConfirmedBy", {
                              name: person.contact_verified_by_name ?? t("find.aStaffMember"),
                              date: new Date(person.contact_verified_at).toLocaleDateString(),
                            })}
                          </StatusBadge>
                        ) : (
                          <StatusBadge kind="pending">{t("status.notConfirmed")}</StatusBadge>
                        )}
                      </dd>
                    </div>
                  </dl>
                  {rowError[person.id] && <Alert kind="problem">{rowError[person.id]}</Alert>}
                  <div className="flex flex-col gap-2 sm:flex-row">
                    <Button
                      disabled={busyId === person.id || episodesQuery?.isPending}
                      onClick={() => openEpisode.mutate({ person, action })}
                    >
                      {action?.kind === "continue" ? (
                        <ArrowRight aria-hidden className="size-4" />
                      ) : (
                        <Plus aria-hidden className="size-4" />
                      )}
                      {opening
                        ? t("find.selecting")
                        : episodesQuery?.isPending
                          ? t("find.checkingEpisodes")
                          : action?.kind === "continue"
                            ? t("find.continueEpisode")
                            : t("find.startEpisode")}
                    </Button>
                    {!person.contact_verified_at && (
                      <Button
                        variant="secondary"
                        disabled={busyId === person.id}
                        onClick={() => verify.mutate(person)}
                      >
                        {t("find.confirmNumber")}
                      </Button>
                    )}
                  </div>
                </Card>
              </li>
              );
            })}
          </ul>
        </section>
      )}
    </div>
  );
}
