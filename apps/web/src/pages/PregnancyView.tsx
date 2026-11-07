import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  ArrowLeft,
  CalendarCheck,
  ClipboardList,
  FileStack,
  Footprints,
  LayoutGrid,
  NotebookTabs,
  Phone,
  PhoneCall,
  UserRound,
} from "lucide-react";
import type * as React from "react";
import { useTranslation } from "react-i18next";
import { Link, useParams, useSearchParams } from "react-router";
import { api, ApiError, type PregnancyEpisode } from "../api/client";
import { Avatar } from "../components/Avatar";
import { AppointmentList } from "../components/care/AppointmentList";
import { BirthPlanPanel } from "../components/care/BirthPlanPanel";
import { CarePlanPanel } from "../components/care/CarePlanPanel";
import { DatingCard } from "../components/care/DatingCard";
import { EpisodeTasks } from "../components/care/EpisodeTasks";
import { errorStateKind, PageState } from "../components/PageState";
import { ObservationsPanel } from "../components/records/ObservationsPanel";
import { PrescriptionsPanel } from "../components/records/PrescriptionsPanel";
import { ReferralsPanel } from "../components/records/ReferralsPanel";
import { ReportsPanel } from "../components/records/ReportsPanel";
import { Button } from "../components/ui/button";
import { Card, Section } from "../components/ui/card";
import { CardSkeleton, Skeleton, Tabs, type TabItem } from "../components/ui/kit";
import { Alert, StatusBadge, type StatusKind } from "../components/ui/status";
import i18n from "../i18n";
import { formatAge } from "../lib/age";
import { isClinicianAt } from "../lib/roles";
import { useSession } from "../state/session";

const DATING_STATUS: Record<string, StatusKind> = {
  UNKNOWN: "unknown",
  SELF_REPORTED: "pending",
  CLINICIAN_CONFIRMED: "confirmed",
};

type RecordTab = "overview" | "care" | "records" | "birth";
const TABS: RecordTab[] = ["overview", "care", "records", "birth"];

function Row({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="grid gap-1 border-b border-line/70 py-3 last:border-b-0 sm:grid-cols-[12rem_1fr] sm:gap-4">
      <dt className="text-sm font-semibold text-muted">{label}</dt>
      <dd className="text-base">{children}</dd>
    </div>
  );
}

function Fact({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="min-w-0">
      <dt className="text-xs font-semibold tracking-wide text-faint uppercase">{label}</dt>
      <dd className="mt-1 truncate text-[0.95rem] text-ink">{children}</dd>
    </div>
  );
}

function RecordSkeleton() {
  return (
    <div className="space-y-6" aria-busy="true">
      <div className="rounded-[var(--radius-card)] border border-line bg-surface p-5">
        <div className="flex items-center gap-4">
          <Skeleton className="size-14 rounded-full" />
          <div className="flex-1 space-y-2">
            <Skeleton className="h-6 w-56" />
            <Skeleton className="h-4 w-32" />
          </div>
        </div>
      </div>
      <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
        <CardSkeleton lines={4} />
        <CardSkeleton lines={4} />
      </div>
    </div>
  );
}

export function PregnancyView() {
  const { t } = useTranslation();
  const { episodeId = "" } = useParams();
  const { staff } = useSession();
  const queryClient = useQueryClient();
  const [params, setParams] = useSearchParams();
  const tabParam = params.get("tab") as RecordTab | null;
  const tab: RecordTab = tabParam && TABS.includes(tabParam) ? tabParam : "overview";
  const setTab = (next: RecordTab) =>
    setParams(
      (p) => {
        if (next === "overview") p.delete("tab");
        else p.set("tab", next);
        return p;
      },
      { replace: true },
    );

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
    onSuccess: (updated) => {
      queryClient.setQueryData(["person", updated.id], updated);
    },
    meta: { toast: i18n.t("toast.contactConfirmed") },
  });

  const backLink = (
    <Button asChild variant="ghost" size="sm" className="-ml-2 text-muted">
      <Link to="/mothers">
        <ArrowLeft aria-hidden className="size-4" />
        {t("common.backHome")}
      </Link>
    </Button>
  );

  if (episode.isPending) return <RecordSkeleton />;
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
              <Link to="/mothers">{t("common.backHome")}</Link>
            </Button>
          </div>
        }
      />
    );
  }

  const e: PregnancyEpisode = episode.data;
  const isClinician = isClinicianAt(staff?.memberships ?? [], e.facility_id);
  const datingKind = DATING_STATUS[e.dating_source] ?? "unknown";
  const datingLabel = t(`episode.dating${e.dating_source}`, { defaultValue: e.dating_source });
  const statusLabel = t(`episode.status${e.status}`, { defaultValue: e.status });

  const tabs: TabItem<RecordTab>[] = [
    { value: "overview", label: t("episode.tab.overview"), icon: LayoutGrid },
    { value: "care", label: t("episode.tab.care"), icon: CalendarCheck },
    { value: "records", label: t("episode.tab.records"), icon: FileStack },
    { value: "birth", label: t("episode.tab.birth"), icon: NotebookTabs },
  ];

  return (
    <div className="space-y-6">
      {backLink}

      {/* Summary header: who this record is for, at a glance. */}
      <Card className="animate-rise p-0 md:p-0">
        <div className="flex flex-col gap-4 p-4 sm:flex-row sm:items-center md:p-6">
          <Avatar name={e.mother_full_name} size="lg" />
          <div className="min-w-0 flex-1 space-y-1">
            <p className="text-xs font-semibold tracking-wide text-faint uppercase">{t("episode.title")}</p>
            <h1 className="truncate text-2xl font-semibold tracking-tight">{e.mother_full_name}</h1>
            <div className="flex flex-wrap items-center gap-2 pt-1">
              <span className="inline-flex items-center rounded-full border border-line bg-subtle px-2.5 py-0.5 text-sm font-semibold">
                {statusLabel}
              </span>
              <StatusBadge kind={datingKind}>{datingLabel}</StatusBadge>
            </div>
          </div>
          <div className="flex flex-col gap-2 sm:items-end">
            <Button asChild>
              <Link to={`/episodes/${e.id}/next-step`}>
                <Footprints aria-hidden className="size-4" />
                {t("next.open")}
              </Link>
            </Button>
            <Button asChild variant="secondary">
              <a href={`/urgent-help/${e.facility_id}`} target="_blank" rel="noopener noreferrer">
                <PhoneCall aria-hidden className="size-4" />
                {t("next.urgentLink")}
              </a>
            </Button>
          </div>
        </div>
        <dl className="grid grid-cols-2 gap-4 border-t border-line bg-page/60 px-4 py-4 sm:grid-cols-4 md:px-6">
          <Fact label={t("episode.age")}>
            {mother.data ? (
              mother.data.age_precision === "UNKNOWN" ? (
                <StatusBadge kind="unknown">{t("status.unknown")}</StatusBadge>
              ) : (
                formatAge(mother.data, t)
              )
            ) : (
              <Skeleton className="w-20" />
            )}
          </Fact>
          <Fact label={t("episode.contactLabel")}>
            {mother.data ? <span className="tabular">{mother.data.phone}</span> : <Skeleton className="w-24" />}
          </Fact>
          <Fact label={t("episode.created")}>{new Date(e.created_at).toLocaleDateString()}</Fact>
          <Fact label={t("episode.datingSource")}>{datingLabel}</Fact>
        </dl>
      </Card>

      <Tabs items={tabs} value={tab} onChange={setTab} label={t("episode.tab.label")} />

      <div key={tab} role="tabpanel" aria-label={tabs.find((x) => x.value === tab)?.label} className="animate-fade-in space-y-6">
        {tab === "overview" && (
          <>
            <div className="grid grid-cols-1 gap-6 lg:grid-cols-2 lg:items-start">
              <Card>
                <Section icon={UserRound} title={t("episode.motherRecord")}>
                  {mother.isPending && <CardSkeleton lines={3} />}
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
                                className="h-auto max-w-full py-2 whitespace-normal"
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
            </div>
            {/* Doctor-only controls are hidden from other roles; the server refuses them regardless. */}
            <div className="grid grid-cols-1 gap-6 lg:grid-cols-2 lg:items-start">
              <DatingCard episodeId={e.id} isClinician={isClinician} />
              <CarePlanPanel episodeId={e.id} isClinician={isClinician} />
            </div>
          </>
        )}

        {tab === "care" && (
          <div className="grid grid-cols-1 gap-6 lg:grid-cols-2 lg:items-start">
            <AppointmentList episodeId={e.id} />
            <EpisodeTasks episodeId={e.id} />
          </div>
        )}

        {tab === "records" && (
          <>
            <div className="grid grid-cols-1 gap-6 lg:grid-cols-2 lg:items-start">
              <ReportsPanel episodeId={e.id} personId={e.mother_person_id} isClinician={isClinician} />
              <PrescriptionsPanel episodeId={e.id} personId={e.mother_person_id} isClinician={isClinician} />
            </div>
            <div className="grid grid-cols-1 gap-6 lg:grid-cols-2 lg:items-start">
              <ObservationsPanel episodeId={e.id} isClinician={isClinician} />
              <ReferralsPanel
                episodeId={e.id}
                personId={e.mother_person_id}
                facilityId={e.facility_id}
                isClinician={isClinician}
              />
            </div>
          </>
        )}

        {tab === "birth" && <BirthPlanPanel episodeId={e.id} facilityId={e.facility_id} isClinician={isClinician} />}
      </div>

      <p className="text-sm text-muted">{t("episode.reloadNote")}</p>
    </div>
  );
}
