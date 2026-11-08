import { useQuery } from "@tanstack/react-query";
import {
  AlarmClock,
  ChevronRight,
  Image as ImageIcon,
  Inbox as InboxIcon,
  MessageSquareText,
  MessageSquareWarning,
  Mic,
  Paperclip,
  UserRound,
  UserRoundSearch,
  type LucideIcon,
} from "lucide-react";
import { useTranslation } from "react-i18next";
import { Link, useSearchParams } from "react-router";
import { inboxApi, type InboxItem, type InboxKind, type InboxView } from "../api/client";
import { MessageFailures } from "../components/messaging/MessageFailures";
import { PageHeader } from "../components/PageHeader";
import { errorStateKind, PageState } from "../components/PageState";
import { Card } from "../components/ui/card";
import { Select } from "../components/ui/field";
import { CardSkeleton, StatTile, Tabs, type TabItem } from "../components/ui/kit";
import { StatusBadge } from "../components/ui/status";
import { formatDateTime } from "../lib/format";
import { canAt } from "../lib/roles";
import { useSession } from "../state/session";

export const KIND_ICON: Record<InboxKind, LucideIcon> = {
  TEXT: MessageSquareText,
  VOICE: Mic,
  IMAGE: ImageIcon,
  OTHER: Paperclip,
};

const VIEWS: InboxView[] = ["open", "unlinked", "mine", "overdue", "closed"];

/** Administrative follow-up timing only; never a statement about her health. */
export function DueBadge({ item }: { item: InboxItem }) {
  const { t } = useTranslation();
  if (item.status === "CLOSED") {
    return <StatusBadge kind="neutral">{t("inbox.closedWith", { outcome: t(`inbox.outcome.${item.outcome ?? "OTHER"}`) })}</StatusBadge>;
  }
  return item.overdue ? (
    <StatusBadge kind="attention">{t("inbox.overdueSince", { time: formatDateTime(item.due_at) })}</StatusBadge>
  ) : (
    <StatusBadge kind="pending">{t("inbox.dueBy", { time: formatDateTime(item.due_at) })}</StatusBadge>
  );
}

function ItemRow({ item, facilityId }: { item: InboxItem; facilityId: string }) {
  const { t } = useTranslation();
  const Icon = KIND_ICON[item.kind];
  return (
    <li>
      <Link
        to={`/inbox/${item.id}?facility=${facilityId}`}
        className="flex items-start gap-3 px-4 py-3.5 transition-colors hover:bg-subtle/60 md:px-5"
      >
        <span className="mt-0.5 inline-flex size-10 shrink-0 items-center justify-center rounded-full bg-brand-tint text-brand" title={t(`inbox.kind.${item.kind}`)}>
          <Icon aria-hidden className="size-5" />
          <span className="sr-only">{t(`inbox.kind.${item.kind}`)}</span>
        </span>
        <div className="min-w-0 flex-1 space-y-1.5">
          <div className="flex flex-wrap items-center gap-2">
            {item.person_name ? (
              <span className="inline-flex items-center gap-1.5 font-semibold text-ink">
                <UserRound aria-hidden className="size-4 text-muted" />
                {item.person_name}
              </span>
            ) : (
              <StatusBadge kind="unknown">{t("inbox.unlinkedName")}</StatusBadge>
            )}
            <span className="text-sm text-muted">{t("inbox.receivedAt", { time: formatDateTime(item.received_at) })}</span>
          </div>
          {item.text_body && <p className="line-clamp-2 text-sm text-ink-2">{item.text_body}</p>}
          {!item.text_body && item.kind !== "TEXT" && <p className="text-sm text-muted">{t(`inbox.kind.${item.kind}`)}</p>}
          <div className="flex flex-wrap items-center gap-2 text-sm text-muted">
            <DueBadge item={item} />
            <span>{item.owner_name ? t("inbox.ownerIs", { name: item.owner_name }) : t("inbox.noOwner")}</span>
          </div>
        </div>
        <ChevronRight aria-hidden className="mt-2 size-5 shrink-0 text-faint" />
      </Link>
    </li>
  );
}

/** The team's shared inbox for WhatsApp messages, voice notes and photos (F018, F019).
 * Not watched for emergencies; "overdue" is an administrative follow-up target. */
export function Inbox() {
  const { t } = useTranslation();
  const { staff } = useSession();
  const memberships = staff?.memberships ?? [];
  const facilities = [...new Map(memberships.map((m) => [m.facility_id, m])).values()];
  const [params, setParams] = useSearchParams();
  const paramFacility = params.get("facility");
  const facilityId = paramFacility && facilities.some((f) => f.facility_id === paramFacility) ? paramFacility : (facilities[0]?.facility_id ?? "");
  const canTriage = canAt(memberships, facilityId, "TRIAGE_UNLINKED_INBOX");
  const canSend = canAt(memberships, facilityId, "SEND_MESSAGES");
  const paramView = params.get("view") as InboxView | null;
  const view: InboxView = paramView && VIEWS.includes(paramView) && (paramView !== "unlinked" || canTriage) ? paramView : "open";
  const set = (key: string, value: string) =>
    setParams(
      (p) => {
        p.set(key, value);
        return p;
      },
      { replace: true },
    );

  const summary = useQuery({ queryKey: ["inboxSummary", facilityId], queryFn: () => inboxApi.summary(facilityId), enabled: !!facilityId });
  const list = useQuery({ queryKey: ["inbox", facilityId, view], queryFn: () => inboxApi.list(facilityId, view), enabled: !!facilityId });
  const s = summary.data;

  if (memberships.length === 0) return <PageState kind="no-access" />;

  const tabs: TabItem<InboxView>[] = [
    { value: "open", label: t("inbox.view.open"), count: s?.open },
    ...(canTriage ? [{ value: "unlinked" as const, label: t("inbox.view.unlinked"), count: s?.unlinked }] : []),
    { value: "mine", label: t("inbox.view.mine"), count: s?.mine },
    { value: "overdue", label: t("inbox.view.overdue"), count: s?.overdue },
    { value: "closed", label: t("inbox.view.closed") },
  ];

  return (
    <div className="space-y-6">
      <PageHeader
        title={t("inbox.title")}
        description={t("inbox.description")}
        actions={
          facilities.length > 1 ? (
            <Select aria-label={t("nav.facility")} value={facilityId} onChange={(e) => set("facility", e.target.value)} className="w-auto">
              {facilities.map((m) => (
                <option key={m.facility_id} value={m.facility_id}>
                  {m.facility_name}
                </option>
              ))}
            </Select>
          ) : undefined
        }
      />

      <p className="rounded-md border border-line bg-subtle p-3 text-sm text-ink-2">{t("inbox.notMonitored")}</p>

      <section className="grid grid-cols-2 gap-3 md:gap-4 xl:grid-cols-5">
        <StatTile label={t("inbox.tile.open")} value={s ? s.open : "—"} icon={InboxIcon} />
        {canTriage && <StatTile label={t("inbox.tile.unlinked")} value={s ? s.unlinked : "—"} icon={UserRoundSearch} tone={s?.unlinked ? "accent" : "brand"} />}
        <StatTile label={t("inbox.tile.mine")} value={s ? s.mine : "—"} icon={UserRound} />
        <StatTile label={t("inbox.tile.overdue")} value={s ? s.overdue : "—"} icon={AlarmClock} tone={s?.overdue ? "accent" : "brand"} hint={t("inbox.overdueHint")} />
        <StatTile label={t("inbox.tile.failed")} value={s ? s.failed_messages : "—"} icon={MessageSquareWarning} tone={s?.failed_messages ? "accent" : "brand"} />
      </section>

      <Card className="overflow-hidden p-0 md:p-0">
        <div className="px-4 pt-2 md:px-5">
          <Tabs items={tabs} value={view} onChange={(v) => set("view", v)} label={t("inbox.viewsLabel")} />
        </div>
        {list.isPending && (
          <div className="p-4 md:p-5">
            <CardSkeleton lines={3} />
          </div>
        )}
        {list.isError && (
          <div className="p-4 md:p-5">
            <PageState kind={errorStateKind(list.error)} />
          </div>
        )}
        {list.data && list.data.length === 0 && (
          <div className="p-4 md:p-5">
            <PageState kind="empty" title={t(`inbox.empty.${view}`)} />
          </div>
        )}
        {list.data && list.data.length > 0 && (
          <ul className="divide-y divide-line/70">
            {list.data.map((item) => (
              <ItemRow key={item.id} item={item} facilityId={facilityId} />
            ))}
          </ul>
        )}
      </Card>

      <MessageFailures facilityId={facilityId} canSend={canSend} />
    </div>
  );
}
