import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ArrowLeft, ClipboardList, Phone, UserRound } from "lucide-react";
import type * as React from "react";
import { useTranslation } from "react-i18next";
import { Link, useParams } from "react-router";
import { api, ApiError, type PregnancyEpisode } from "../api/client";
import { Avatar } from "../components/Avatar";
import { PageHeader } from "../components/PageHeader";
import { errorStateKind, PageState } from "../components/PageState";
import { Button } from "../components/ui/button";
import { Card, Section } from "../components/ui/card";
import { Alert, StatusBadge, type StatusKind } from "../components/ui/status";
import { formatAge } from "../lib/age";

const DATING_STATUS: Record<string, StatusKind> = {
  UNKNOWN: "unknown",
  SELF_REPORTED: "pending",
  CLINICIAN_CONFIRMED: "confirmed",
};

function Row({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="grid gap-1 border-b border-line/70 py-3 last:border-b-0 sm:grid-cols-[12rem_1fr] sm:gap-4">
      <dt className="text-sm font-semibold text-muted">{label}</dt>
      <dd className="text-base">{children}</dd>
    </div>
  );
}

export function PregnancyView() {
  const { t } = useTranslation();
  const { episodeId = "" } = useParams();
  const queryClient = useQueryClient();

  // Always fetched from the API by the id in the URL, so a reload shows what
  // is saved on the server, never a copy kept only in the browser.
  const episode = useQuery({
    queryKey: ["episode", episodeId],
    queryFn: () => api.getPregnancyEpisode(episodeId),
    enabled: episodeId !== "",
  });
  const motherId = episode.data?.mother_person_id;
  const mother = useQuery({
    queryKey: ["person", motherId],
    queryFn: () => api.getPerson(motherId as string),
    enabled: !!motherId,
  });
  const verify = useMutation({
    mutationFn: (personId: string) => api.verifyContact(personId),
    onSuccess: (updated) => queryClient.setQueryData(["person", updated.id], updated),
  });

  const backLink = (
    <Button asChild variant="ghost" className="-ml-2">
      <Link to="/">
        <ArrowLeft aria-hidden className="size-4" />
        {t("common.backHome")}
      </Link>
    </Button>
  );

  if (episode.isPending) return <PageState kind="loading" />;
  if (episode.isError) {
    const kind = errorStateKind(episode.error);
    return (
      <PageState
        kind={kind}
        action={
          <div className="flex flex-col gap-2 sm:flex-row">
            {kind === "error" && (
              <Button variant="secondary" onClick={() => episode.refetch()}>
                {t("common.retry")}
              </Button>
            )}
            <Button asChild variant="secondary">
              <Link to="/">{t("common.backHome")}</Link>
            </Button>
          </div>
        }
      />
    );
  }

  const e: PregnancyEpisode = episode.data;
  const datingKind = DATING_STATUS[e.dating_source] ?? "unknown";
  const datingLabel = t(`episode.dating${e.dating_source}`, { defaultValue: e.dating_source });
  const statusLabel = t(`episode.status${e.status}`, { defaultValue: e.status });

  return (
    <div className="space-y-6">
      {backLink}
      <PageHeader title={t("episode.title")} />

      {/* Summary: who this record is for, at a glance. */}
      <Card className="flex flex-col gap-4 sm:flex-row sm:items-center">
        <Avatar name={e.mother_full_name} size="lg" />
        <div className="min-w-0 flex-1">
          <p className="truncate text-xl font-semibold">{e.mother_full_name}</p>
          <p className="text-sm text-muted">
            {t("episode.openedOn", { date: new Date(e.created_at).toLocaleDateString() })}
          </p>
        </div>
        <div className="flex flex-wrap gap-2">
          <span className="inline-flex items-center rounded-full border border-line bg-subtle px-2.5 py-0.5 text-sm font-semibold">
            {statusLabel}
          </span>
          <StatusBadge kind={datingKind}>{datingLabel}</StatusBadge>
        </div>
      </Card>

      <div className="grid gap-6 lg:grid-cols-2 lg:items-start">
        <Card>
          <Section icon={ClipboardList} title={t("episode.summary")}>
            <dl>
              <Row label={t("episode.status")}>{statusLabel}</Row>
              <Row label={t("episode.datingSource")}>
                <StatusBadge kind={datingKind}>{datingLabel}</StatusBadge>
              </Row>
              <Row label={t("episode.created")}>{new Date(e.created_at).toLocaleString()}</Row>
              <Row label={t("episode.recordId")}>
                <span className="font-mono text-sm break-all">{e.id}</span>
              </Row>
            </dl>
          </Section>
        </Card>

        <Card>
          <Section icon={UserRound} title={t("episode.motherRecord")}>
            {mother.isPending && <PageState kind="loading" />}
            {mother.isError && (
              <Alert kind="problem">
                {mother.error instanceof ApiError ? mother.error.message : t("episode.motherLoadFailed")}
              </Alert>
            )}
            {mother.data && (
              <dl>
                <Row label={t("episode.age")}>
                  {mother.data.age_precision === "UNKNOWN" ? (
                    <StatusBadge kind="unknown">{t("status.unknown")}</StatusBadge>
                  ) : (
                    formatAge(mother.data, t)
                  )}
                </Row>
                <Row label={t("episode.history")}>
                  {mother.data.reported_medical_history || (
                    <StatusBadge kind="not-recorded">{t("status.notRecorded")}</StatusBadge>
                  )}
                </Row>
                <Row label={t("episode.allergies")}>
                  {mother.data.known_allergies_medicines || (
                    <StatusBadge kind="not-recorded">{t("status.notRecorded")}</StatusBadge>
                  )}
                </Row>
                <Row label={t("episode.contactLabel")}>
                  <div className="space-y-2">
                    <span className="inline-flex items-center gap-2">
                      <Phone aria-hidden className="size-4 text-muted" />
                      {mother.data.phone}
                    </span>
                    {mother.data.contact_verified_at ? (
                      <div>
                        <StatusBadge kind="confirmed">
                          {t("episode.contactConfirmedBy", {
                            name: mother.data.contact_verified_by_name ?? t("find.aStaffMember"),
                            date: new Date(mother.data.contact_verified_at).toLocaleString(),
                          })}
                        </StatusBadge>
                      </div>
                    ) : (
                      <div className="space-y-2">
                        <StatusBadge kind="pending">{t("status.notConfirmed")}</StatusBadge>
                        <p className="text-sm text-muted">{t("episode.contactNotConfirmed")}</p>
                        <Button
                          variant="secondary"
                          onClick={() => verify.mutate(mother.data.id)}
                          disabled={verify.isPending}
                        >
                          {verify.isPending ? t("episode.confirming") : t("episode.confirmNumber")}
                        </Button>
                        {verify.isError && (
                          <Alert kind="problem">
                            {verify.error instanceof ApiError ? verify.error.message : t("episode.confirmFailed")}
                          </Alert>
                        )}
                      </div>
                    )}
                  </div>
                </Row>
              </dl>
            )}
          </Section>
        </Card>
      </div>
      <p className="text-sm text-muted">{t("episode.reloadNote")}</p>
    </div>
  );
}
