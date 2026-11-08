import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  ArrowLeft,
  CircleCheck,
  FileWarning,
  Link2,
  Loader2,
  MessageSquareReply,
  PhoneOff,
  Search,
  Send,
  ShieldAlert,
  UserCheck,
  UserRound,
  Users,
} from "lucide-react";
import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { Link, useParams, useSearchParams } from "react-router";
import {
  api,
  inboxApi,
  messagingApi,
  workApi,
  type IdentityCheck,
  type InboxItem,
  type InboxOutcome,
  type Person,
} from "../api/client";
import { Avatar } from "../components/Avatar";
import { ActionError, InlineForm } from "../components/care/shared";
import { MessageRow, PlaceholderLabel, useMessagingError } from "../components/messaging/shared";
import { errorStateKind, PageState } from "../components/PageState";
import { Button } from "../components/ui/button";
import { Card, CardHeader } from "../components/ui/card";
import { Field, Input, Select, Textarea } from "../components/ui/field";
import { Badge, CardSkeleton } from "../components/ui/kit";
import { Alert, StatusBadge } from "../components/ui/status";
import { formatDateTime } from "../lib/format";
import { canAt } from "../lib/roles";
import { useSession } from "../state/session";
import { DueBadge, KIND_ICON } from "./Inbox";

const CHECKS: IdentityCheck[] = ["CALLED_BACK", "ASKED_IDENTIFYING_DETAILS", "IN_PERSON"];
const OUTCOMES: InboxOutcome[] = ["RESPONDED", "CALLED", "NO_ACTION_NEEDED", "NOT_FOR_US", "OTHER"];

/** Shared by every action on one item: keep the item, the lists and the counts in step. */
function useItemAction(item: InboxItem) {
  const queryClient = useQueryClient();
  const errors = useMessagingError([["inboxItem", item.id], ["inbox"], ["inboxSummary"]]);
  return {
    errors,
    done: (updated: InboxItem) => {
      errors.clear();
      queryClient.setQueryData(["inboxItem", item.id], updated);
      void queryClient.invalidateQueries({ queryKey: ["inbox"] });
      void queryClient.invalidateQueries({ queryKey: ["inboxSummary"] });
    },
  };
}

/** The stored voice note or photo, fetched with the session and shown through an object URL. */
function Media({ item }: { item: InboxItem }) {
  const { t } = useTranslation();
  const media = useQuery({
    queryKey: ["inboxMedia", item.id],
    queryFn: () => inboxApi.media(item.id),
    enabled: item.media_state === "STORED",
    staleTime: Infinity,
    gcTime: 60_000,
  });
  const [url, setUrl] = useState<string | null>(null);
  useEffect(() => {
    if (!media.data) return;
    const next = URL.createObjectURL(media.data);
    setUrl(next);
    return () => URL.revokeObjectURL(next);
  }, [media.data]);

  if (item.media_state === "NONE") return null;
  if (item.media_state === "PENDING") {
    return (
      <p className="inline-flex items-center gap-2 text-sm text-muted">
        <Loader2 aria-hidden className="size-4 animate-spin" />
        {t("inbox.media.pending")}
      </p>
    );
  }
  if (item.media_state === "REJECTED" || item.media_state === "FAILED") {
    return (
      <Alert kind="pending" title={t(`inbox.media.${item.media_state}`)}>
        {item.media_note}
      </Alert>
    );
  }
  if (media.isError) return <Alert kind="problem">{t("inbox.media.loadFailed")}</Alert>;
  if (media.isPending || !url) return <p className="text-sm text-muted">{t("inbox.media.loading")}</p>;
  const type = media.data?.type || item.media_content_type || "";
  if (item.kind === "VOICE" || type.startsWith("audio/")) {
    return (
      <audio controls src={url} className="w-full">
        {t("inbox.media.noAudioSupport")}
      </audio>
    );
  }
  if (item.kind === "IMAGE" || type.startsWith("image/")) {
    return (
      <a href={url} target="_blank" rel="noopener noreferrer" className="block">
        <img src={url} alt={t("inbox.media.imageAlt")} className="max-h-[28rem] max-w-full rounded-lg border border-line object-contain" />
      </a>
    );
  }
  return (
    <a href={url} target="_blank" rel="noopener noreferrer" className="font-semibold text-brand">
      {t("inbox.media.open")}
    </a>
  );
}

function LinkForm({ item, onDone }: { item: InboxItem; onDone: () => void }) {
  const { t } = useTranslation();
  const { errors, done } = useItemAction(item);
  const [query, setQuery] = useState("");
  const [results, setResults] = useState<Person[] | null>(null);
  const [person, setPerson] = useState<Person | null>(null);
  const [check, setCheck] = useState<IdentityCheck | null>(null);
  const search = useMutation({
    mutationFn: () => {
      const q = query.trim();
      return api.searchPeople(/^[+\d\s-]+$/.test(q) ? { phone: q } : { full_name: q });
    },
    meta: { silent: true },
    onSuccess: setResults,
    onError: errors.onError,
  });
  const link = useMutation({
    mutationFn: () => inboxApi.link(item.id, { expected_version: item.version, person_id: person!.id, identity_check: check! }),
    meta: { toast: t("inbox.linkedToast", { name: person?.full_name ?? "" }) },
    onSuccess: (updated) => {
      done(updated);
      onDone();
    },
    onError: errors.onError,
  });

  return (
    <div className="space-y-4 rounded-xl border border-brand-soft bg-brand-tint/40 p-4">
      {!person ? (
        <>
          <form
            className="flex flex-col gap-2 sm:flex-row sm:items-end"
            onSubmit={(e) => {
              e.preventDefault();
              if (query.trim()) search.mutate();
            }}
          >
            <div className="flex-1">
              <Field label={t("inbox.link.findLabel")} htmlFor="link-search" hint={t("inbox.link.findHint")}>
                <Input id="link-search" value={query} onChange={(e) => setQuery(e.target.value)} />
              </Field>
            </div>
            <Button type="submit" disabled={search.isPending || !query.trim()}>
              <Search aria-hidden className="size-4" />
              {t("find.submit")}
            </Button>
          </form>
          {results && results.length === 0 && <Alert kind="info">{t("inbox.link.noMatch")}</Alert>}
          {results && results.length > 0 && (
            <ul className="divide-y divide-line rounded-lg border border-line bg-surface">
              {results.map((p) => (
                <li key={p.id} className="flex items-center gap-3 px-3 py-2.5">
                  <Avatar name={p.full_name} size="sm" />
                  <span className="min-w-0 flex-1">
                    <span className="block truncate font-medium">{p.full_name}</span>
                    <span className="block text-sm text-muted tabular">{p.phone}</span>
                  </span>
                  <Button size="sm" variant="soft" onClick={() => setPerson(p)}>
                    {t("family.choose")}
                  </Button>
                </li>
              ))}
            </ul>
          )}
          <div className="flex justify-end">
            <Button variant="ghost" size="sm" onClick={onDone}>
              {t("care.cancel")}
            </Button>
          </div>
        </>
      ) : (
        <InlineForm
          onSubmit={() => check && link.mutate()}
          onCancel={onDone}
          submitLabel={t("inbox.link.confirm", { name: person.full_name })}
          busy={link.isPending || !check}
        >
          <div className="flex items-center gap-3">
            <Avatar name={person.full_name} size="sm" />
            <p className="font-semibold">{person.full_name}</p>
            <button type="button" className="text-sm font-semibold text-brand" onClick={() => setPerson(null)}>
              {t("family.change")}
            </button>
          </div>
          <fieldset className="space-y-2">
            <legend className="mb-1 text-sm font-semibold">{t("inbox.link.checkLabel")}</legend>
            {CHECKS.map((c) => (
              <label key={c} className="flex min-h-12 items-start gap-3 rounded-lg border border-line bg-surface p-3">
                <input type="radio" name="identity-check" className="mt-1 size-5 accent-[var(--color-brand)]" checked={check === c} onChange={() => setCheck(c)} />
                <span>{t(`inbox.check.${c}`)}</span>
              </label>
            ))}
          </fieldset>
          <p className="text-sm text-muted">{t("inbox.link.audited")}</p>
        </InlineForm>
      )}
      <ActionError message={errors.message} />
    </div>
  );
}

function WhoPanel({ item, canTriage }: { item: InboxItem; canTriage: boolean }) {
  const { t } = useTranslation();
  const [linking, setLinking] = useState(false);
  const episodes = useQuery({
    queryKey: ["episodes", item.person_id],
    queryFn: () => api.listEpisodes(item.person_id!),
    enabled: !!item.person_id,
  });
  const episode = episodes.data?.find((e) => e.status === "ACTIVE") ?? episodes.data?.[0];

  if (item.person_id) {
    return (
      <Card>
        <CardHeader icon={UserCheck} title={t("inbox.who.linkedTitle")} />
        <div className="space-y-2">
          <div className="flex flex-wrap items-center gap-3">
            <Avatar name={item.person_name ?? "?"} size="sm" />
            <p className="font-semibold">{item.person_name}</p>
            {episode && (
              <Link to={`/episodes/${episode.id}?tab=messages`} className="text-sm font-semibold text-brand">
                {t("inbox.who.openRecord")}
              </Link>
            )}
          </div>
          {item.linked_at && (
            <p className="text-sm text-muted">
              {t("inbox.who.linkedBy", {
                name: item.linked_by_name ?? t("find.aStaffMember"),
                time: formatDateTime(item.linked_at),
                check: item.identity_check ? t(`inbox.check.${item.identity_check}`) : "—",
              })}
            </p>
          )}
          <p className="text-sm text-muted">{t("inbox.who.fromNumber", { number: item.from_number })}</p>
        </div>
      </Card>
    );
  }

  return (
    <Card>
      <CardHeader
        icon={ShieldAlert}
        title={t("inbox.who.unlinkedTitle")}
        actions={
          canTriage && item.status === "OPEN" && !linking ? (
            <Button size="sm" onClick={() => setLinking(true)}>
              <Link2 aria-hidden className="size-4" />
              {t("inbox.link.button")}
            </Button>
          ) : undefined
        }
      />
      <div className="space-y-3">
        <Alert kind="pending" title={t("inbox.who.notIdentityTitle")}>
          {t("inbox.who.notIdentityBody")}
        </Alert>
        <p className="text-sm text-ink-2">{t("inbox.who.fromNumber", { number: item.from_number })}</p>
        {item.people_on_number > 1 && (
          <p className="inline-flex items-center gap-2 rounded-md border border-pending-line bg-pending-bg px-3 py-2 text-sm font-semibold text-pending">
            <Users aria-hidden className="size-4 shrink-0" />
            {t("inbox.who.peopleOnNumber", { count: item.people_on_number })}
          </p>
        )}
        {item.people_on_number === 0 && <p className="text-sm text-muted">{t("inbox.who.nobodyOnNumber")}</p>}
        {!canTriage && <p className="text-sm text-muted">{t("inbox.who.onlyCoordinator")}</p>}
        {linking && <LinkForm item={item} onDone={() => setLinking(false)} />}
      </div>
    </Card>
  );
}

function AssignPanel({ item, facilityId }: { item: InboxItem; facilityId: string }) {
  const { t } = useTranslation();
  const { errors, done } = useItemAction(item);
  const [editing, setEditing] = useState(false);
  const team = useQuery({ queryKey: ["workload", facilityId], queryFn: () => workApi.workload(facilityId), enabled: editing && !!facilityId });
  // Until it is linked, only a coordinator may own it (the server checks this too).
  const people = (team.data?.people ?? []).filter((p) => p.works_here && (item.person_id || p.role === "COORDINATOR"));
  const [owner, setOwner] = useState(item.owner_staff_user_id ?? "");
  const [backup, setBackup] = useState(item.backup_staff_user_id ?? "");
  const assign = useMutation({
    mutationFn: () => inboxApi.assign(item.id, { expected_version: item.version, owner_staff_user_id: owner, backup_staff_user_id: backup || null }),
    meta: { toast: t("inbox.assign.saved") },
    onSuccess: (updated) => {
      done(updated);
      setEditing(false);
    },
    onError: errors.onError,
  });

  return (
    <Card>
      <CardHeader
        icon={UserRound}
        title={t("inbox.assign.title")}
        actions={
          item.status === "OPEN" && !editing ? (
            <Button size="sm" variant="secondary" onClick={() => setEditing(true)}>
              {t("inbox.assign.change")}
            </Button>
          ) : undefined
        }
      />
      <dl className="grid gap-2 text-sm sm:grid-cols-2">
        <div>
          <dt className="font-semibold text-muted">{t("inbox.assign.owner")}</dt>
          <dd>{item.owner_name ?? t("inbox.noOwner")}</dd>
        </div>
        <div>
          <dt className="font-semibold text-muted">{t("inbox.assign.backup")}</dt>
          <dd>{item.backup_name ?? t("inbox.assign.noBackup")}</dd>
        </div>
      </dl>
      {editing && (
        <div className="mt-4">
          {team.isPending && <CardSkeleton lines={2} />}
          {team.isError && <Alert kind="problem">{t("states.errorBody")}</Alert>}
          {team.data && (
            <InlineForm onSubmit={() => owner && assign.mutate()} onCancel={() => setEditing(false)} submitLabel={t("inbox.assign.save")} busy={assign.isPending || !owner}>
              {!item.person_id && <p className="text-sm text-muted">{t("inbox.assign.coordinatorsOnly")}</p>}
              <div className="grid gap-3 sm:grid-cols-2">
                <Field label={t("inbox.assign.owner")} htmlFor={`owner-${item.id}`}>
                  <Select id={`owner-${item.id}`} value={owner} onChange={(e) => setOwner(e.target.value)}>
                    <option value="">{t("inbox.assign.choose")}</option>
                    {people.map((p) => (
                      <option key={p.staff_user_id} value={p.staff_user_id}>
                        {p.full_name} · {t(`nav.role.${p.role}`, { defaultValue: p.role ?? "" })}
                      </option>
                    ))}
                  </Select>
                </Field>
                <Field label={t("inbox.assign.backup")} htmlFor={`backup-${item.id}`}>
                  <Select id={`backup-${item.id}`} value={backup} onChange={(e) => setBackup(e.target.value)}>
                    <option value="">{t("inbox.assign.noBackup")}</option>
                    {people
                      .filter((p) => p.staff_user_id !== owner)
                      .map((p) => (
                        <option key={p.staff_user_id} value={p.staff_user_id}>
                          {p.full_name} · {t(`nav.role.${p.role}`, { defaultValue: p.role ?? "" })}
                        </option>
                      ))}
                  </Select>
                </Field>
              </div>
            </InlineForm>
          )}
        </div>
      )}
      <div className="mt-3">
        <ActionError message={errors.message} />
      </div>
    </Card>
  );
}

function ReplyPanel({ item, facilityId, canSend }: { item: InboxItem; facilityId: string; canSend: boolean }) {
  const { t } = useTranslation();
  const { errors, done } = useItemAction(item);
  const queryClient = useQueryClient();
  const [text, setText] = useState("");
  const canCompose = canSend && item.status === "OPEN" && !!item.person_id;
  const templates = useQuery({
    queryKey: ["messageTemplates", facilityId],
    queryFn: () => messagingApi.templates(facilityId),
    enabled: canCompose && !item.can_reply_free_text && !!facilityId,
  });
  const followUp = templates.data?.filter((tpl) => tpl.purpose === "FOLLOW_UP") ?? [];
  const reply = useMutation({
    mutationFn: (body: { text: string } | { template_purpose: "FOLLOW_UP" }) => inboxApi.reply(item.id, { expected_version: item.version, ...body }),
    meta: { toast: t("inbox.reply.queued") },
    onSuccess: (updated) => {
      setText("");
      done(updated);
      if (updated.person_id) void queryClient.invalidateQueries({ queryKey: ["personMessages", updated.person_id] });
    },
    onError: errors.onError,
  });

  return (
    <Card>
      <CardHeader icon={MessageSquareReply} title={t("inbox.reply.title")} />
      <div className="space-y-4">
        {item.replies.length === 0 && <p className="text-sm text-muted">{t("inbox.reply.none")}</p>}
        {item.replies.length > 0 && (
          <ul className="space-y-3">
            {item.replies.map((m) => (
              <li key={m.id} className="rounded-lg border border-line p-3">
                <MessageRow message={m} />
              </li>
            ))}
          </ul>
        )}

        {item.status === "OPEN" && !item.person_id && <Alert kind="info">{t("inbox.reply.linkFirst")}</Alert>}
        {item.status === "OPEN" && item.person_id && !canSend && <Alert kind="info">{t("inbox.reply.cannotSend")}</Alert>}

        {canCompose && item.can_reply_free_text && (
          <form
            className="space-y-2"
            onSubmit={(e) => {
              e.preventDefault();
              if (text.trim()) reply.mutate({ text: text.trim() });
            }}
          >
            <Field label={t("inbox.reply.textLabel")} htmlFor={`reply-${item.id}`} hint={t("inbox.reply.textHint")}>
              <Textarea id={`reply-${item.id}`} maxLength={1000} value={text} onChange={(e) => setText(e.target.value)} />
            </Field>
            <Button type="submit" disabled={reply.isPending || !text.trim()}>
              <Send aria-hidden className="size-4" />
              {t("inbox.reply.send")}
            </Button>
          </form>
        )}

        {canCompose && !item.can_reply_free_text && (
          <div className="space-y-3">
            <Alert kind="info" title={t("inbox.reply.windowTitle")}>
              {t("inbox.reply.windowBody")}
            </Alert>
            {templates.isPending && <CardSkeleton lines={1} />}
            {templates.data && followUp.length === 0 && <Alert kind="pending">{t("inbox.reply.noTemplate")}</Alert>}
            {followUp.map((tpl) => (
              <div key={tpl.id} className="space-y-2 rounded-lg border border-line bg-page/60 p-3">
                <div className="flex flex-wrap items-center gap-2 text-sm text-muted">
                  <span>{t("inbox.reply.templatePreview", { version: tpl.version_label, language: tpl.language })}</span>
                  {tpl.is_placeholder && <PlaceholderLabel />}
                </div>
                <p className="text-sm whitespace-pre-wrap">{tpl.body_text}</p>
              </div>
            ))}
            <Button variant="secondary" disabled={reply.isPending || (!!templates.data && followUp.length === 0)} onClick={() => reply.mutate({ template_purpose: "FOLLOW_UP" })}>
              <Send aria-hidden className="size-4" />
              {t("inbox.reply.sendTemplate")}
            </Button>
          </div>
        )}
        <ActionError message={errors.message} />
      </div>
    </Card>
  );
}

function ClosePanel({ item }: { item: InboxItem }) {
  const { t } = useTranslation();
  const { errors, done } = useItemAction(item);
  const [closing, setClosing] = useState(false);
  const [outcome, setOutcome] = useState<InboxOutcome>("RESPONDED");
  const [note, setNote] = useState("");
  const close = useMutation({
    mutationFn: () => inboxApi.close(item.id, { expected_version: item.version, outcome, note: note.trim() || null }),
    meta: { toast: t("inbox.close.closedToast") },
    onSuccess: (updated) => {
      done(updated);
      setClosing(false);
    },
    onError: errors.onError,
  });

  if (item.status === "CLOSED") {
    return (
      <Card>
        <CardHeader icon={CircleCheck} title={t("inbox.close.closedTitle")} />
        <div className="space-y-1 text-sm">
          <p>
            <StatusBadge kind="neutral">{t(`inbox.outcome.${item.outcome ?? "OTHER"}`)}</StatusBadge>
          </p>
          {item.closed_at && <p className="text-muted">{t("inbox.close.closedAt", { time: formatDateTime(item.closed_at) })}</p>}
          {item.closure_note && <p className="whitespace-pre-wrap">{item.closure_note}</p>}
        </div>
      </Card>
    );
  }
  return (
    <Card>
      <CardHeader
        icon={CircleCheck}
        title={t("inbox.close.title")}
        description={t("inbox.close.description")}
        actions={
          !closing ? (
            <Button size="sm" variant="secondary" onClick={() => setClosing(true)}>
              {t("inbox.close.button")}
            </Button>
          ) : undefined
        }
      />
      {closing && (
        <InlineForm onSubmit={() => close.mutate()} onCancel={() => setClosing(false)} submitLabel={t("inbox.close.confirm")} busy={close.isPending}>
          <Field label={t("inbox.close.outcomeLabel")} htmlFor={`outcome-${item.id}`}>
            <Select id={`outcome-${item.id}`} value={outcome} onChange={(e) => setOutcome(e.target.value as InboxOutcome)}>
              {OUTCOMES.map((o) => (
                <option key={o} value={o}>
                  {t(`inbox.outcome.${o}`)}
                </option>
              ))}
            </Select>
          </Field>
          <Field label={t("inbox.close.noteLabel")} htmlFor={`note-${item.id}`}>
            <Textarea id={`note-${item.id}`} maxLength={500} value={note} onChange={(e) => setNote(e.target.value)} />
          </Field>
        </InlineForm>
      )}
      <div className="mt-3">
        <ActionError message={errors.message} />
      </div>
    </Card>
  );
}

/** One inbound message: what arrived, who (if confirmed) sent it, who owns it, replies and closing. */
export function InboxItemPage() {
  const { t } = useTranslation();
  const { itemId = "" } = useParams();
  const [params] = useSearchParams();
  const { staff } = useSession();
  const memberships = staff?.memberships ?? [];
  const item = useQuery({ queryKey: ["inboxItem", itemId], queryFn: () => inboxApi.get(itemId), enabled: !!itemId });
  const paramFacility = params.get("facility");
  const back = (
    <Button asChild variant="ghost" size="sm" className="-ml-2 text-muted">
      <Link to={paramFacility ? `/inbox?facility=${paramFacility}` : "/inbox"}>
        <ArrowLeft aria-hidden className="size-4" />
        {t("inbox.back")}
      </Link>
    </Button>
  );

  if (item.isPending) return <CardSkeleton lines={5} />;
  if (item.isError) {
    return (
      <div className="space-y-4">
        {back}
        <PageState kind={errorStateKind(item.error)} />
      </div>
    );
  }
  const it = item.data;
  const facilityId =
    it.facility_id ??
    (paramFacility && memberships.some((m) => m.facility_id === paramFacility) ? paramFacility : null) ??
    memberships.find((m) => m.capabilities?.includes("TRIAGE_UNLINKED_INBOX"))?.facility_id ??
    memberships[0]?.facility_id ??
    "";
  const canTriage = canAt(memberships, facilityId, "TRIAGE_UNLINKED_INBOX");
  const canSend = canAt(memberships, facilityId, "SEND_MESSAGES");
  const Icon = KIND_ICON[it.kind];

  return (
    <div className="space-y-6">
      {back}
      <Card>
        <div className="flex flex-wrap items-start gap-3">
          <span className="inline-flex size-11 shrink-0 items-center justify-center rounded-full bg-brand-tint text-brand">
            <Icon aria-hidden className="size-5" />
          </span>
          <div className="min-w-0 flex-1 space-y-1.5">
            <h1 className="text-xl font-semibold tracking-tight">{it.person_name ?? t("inbox.unlinkedName")}</h1>
            <div className="flex flex-wrap items-center gap-2 text-sm text-muted">
              <Badge>{t(`inbox.kind.${it.kind}`)}</Badge>
              <span>{t("inbox.receivedAt", { time: formatDateTime(it.received_at) })}</span>
              <DueBadge item={it} />
            </div>
          </div>
        </div>
        <div className="mt-4 space-y-3">
          {it.text_body ? (
            <p className="rounded-lg border border-line bg-page/60 p-3 text-base whitespace-pre-wrap">{it.text_body}</p>
          ) : (
            it.kind === "TEXT" && (
              <p className="inline-flex items-center gap-2 text-sm text-muted">
                <FileWarning aria-hidden className="size-4" />
                {t("inbox.noText")}
              </p>
            )
          )}
          <Media item={it} />
          <p className="inline-flex items-start gap-2 text-sm text-muted">
            <PhoneOff aria-hidden className="mt-0.5 size-4 shrink-0" />
            {t("inbox.notMonitored")}
          </p>
        </div>
      </Card>

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-2 lg:items-start">
        <WhoPanel item={it} canTriage={canTriage} />
        <AssignPanel item={it} facilityId={facilityId} />
      </div>
      <div className="grid grid-cols-1 gap-6 lg:grid-cols-2 lg:items-start">
        <ReplyPanel item={it} facilityId={facilityId} canSend={canSend} />
        <ClosePanel item={it} />
      </div>
    </div>
  );
}
