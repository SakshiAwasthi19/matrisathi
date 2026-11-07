import { useMutation, useQuery } from "@tanstack/react-query";
import { MapPin, Phone } from "lucide-react";
import { useState } from "react";
import { useTranslation } from "react-i18next";
import { recordsApi, type LocalContact, type ServiceType } from "../api/client";
import { ActionError, InlineForm, useActionError } from "../components/care/shared";
import { PageHeader } from "../components/PageHeader";
import { errorStateKind, PageState } from "../components/PageState";
import { Button } from "../components/ui/button";
import { Card } from "../components/ui/card";
import { CardSkeleton } from "../components/ui/kit";
import { Field, Input, Select } from "../components/ui/field";
import { Alert, StatusBadge } from "../components/ui/status";
import { formatDate } from "../lib/format";
import { useSession } from "../state/session";

const TYPES: ServiceType[] = ["PHC", "REFERRAL_HOSPITAL", "TRANSPORT", "NUTRITION", "BENEFITS", "OTHER"];

function ContactRow({ c, facilityId }: { c: LocalContact; facilityId: string }) {
  const { t } = useTranslation();
  const errors = useActionError([["contacts", facilityId]]);
  const verify = useMutation({
    mutationFn: () => recordsApi.verifyContact(c.id, c.version),
    onSuccess: () => {
      errors.clear();
      errors.reload();
    },
    onError: errors.onError,
  });
  return (
    <li>
      <Card className="space-y-2">
        <div className="flex flex-wrap items-start justify-between gap-2">
          <div>
            <p className="text-sm font-semibold text-muted">{t(`records.contacts.type${c.service_type}`)}</p>
            <p className="text-lg font-semibold">{c.name}</p>
          </div>
          {c.stale ? (
            <StatusBadge kind="pending">{t("records.contacts.stale")}</StatusBadge>
          ) : (
            <StatusBadge kind="confirmed">{t("status.confirmed")}</StatusBadge>
          )}
        </div>
        <div className="flex flex-wrap gap-x-6 gap-y-1">
          <a href={`tel:${c.phone}`} className="inline-flex min-h-12 items-center gap-2 font-semibold text-brand md:min-h-10">
            <Phone aria-hidden className="size-4" />
            {c.phone}
          </a>
          {c.alternate_phone && (
            <a href={`tel:${c.alternate_phone}`} className="inline-flex min-h-12 items-center gap-2 font-semibold text-brand md:min-h-10">
              <Phone aria-hidden className="size-4" />
              {c.alternate_phone}
            </a>
          )}
        </div>
        {c.landmarks && (
          <p className="inline-flex items-center gap-2 text-base text-muted">
            <MapPin aria-hidden className="size-4" />
            {c.landmarks}
          </p>
        )}
        {c.availability_note && <p className="text-base text-muted">{c.availability_note}</p>}
        <p className="text-sm text-muted">{t("records.contacts.verifiedBy", { name: c.verified_by_name ?? "", date: formatDate(c.verified_on) })}</p>
        <ActionError message={errors.message} />
        <Button variant="secondary" disabled={verify.isPending} onClick={() => verify.mutate()}>
          {t("records.contacts.verifyNow")}
        </Button>
      </Card>
    </li>
  );
}

export function LocalContacts() {
  const { t } = useTranslation();
  const { staff } = useSession();
  const facilities = staff?.memberships ?? [];
  const [facilityId, setFacilityId] = useState(facilities[0]?.facility_id ?? "");
  const key = ["contacts", facilityId];
  const errors = useActionError([key]);
  const list = useQuery({ queryKey: key, queryFn: () => recordsApi.listContacts(facilityId), enabled: !!facilityId });
  const [adding, setAdding] = useState(false);
  const [form, setForm] = useState({ service_type: "PHC" as ServiceType, name: "", phone: "", alternate_phone: "", landmarks: "", availability_note: "" });
  const set = (k: keyof typeof form) => (e: { target: { value: string } }) => setForm((f) => ({ ...f, [k]: e.target.value }));
  const create = useMutation({
    mutationFn: () =>
      recordsApi.createContact({
        facility_id: facilityId,
        service_type: form.service_type,
        name: form.name.trim(),
        phone: form.phone.trim(),
        alternate_phone: form.alternate_phone.trim() || null,
        landmarks: form.landmarks.trim() || null,
        availability_note: form.availability_note.trim() || null,
      }),
    onSuccess: () => {
      setAdding(false);
      setForm({ service_type: "PHC", name: "", phone: "", alternate_phone: "", landmarks: "", availability_note: "" });
      errors.clear();
      errors.reload();
    },
    onError: errors.onError,
  });

  if (facilities.length === 0) return <PageState kind="no-access" />;

  return (
    <div className="space-y-6">
      <PageHeader title={t("records.contacts.title")} description={t("records.contacts.intro")} />
      {facilities.length > 1 && (
        <Field label={t("records.contacts.facility")} htmlFor="contacts_facility">
          <Select id="contacts_facility" value={facilityId} onChange={(e) => setFacilityId(e.target.value)} className="sm:w-80">
            {facilities.map((m) => (
              <option key={m.facility_id} value={m.facility_id}>
                {m.facility_name}
              </option>
            ))}
          </Select>
        </Field>
      )}
      {list.isPending && (
        <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
          <CardSkeleton lines={3} />
          <CardSkeleton lines={3} />
        </div>
      )}
      {list.isError && <PageState kind={errorStateKind(list.error)} />}
      {list.data?.length === 0 && <PageState kind="empty" title={t("records.contacts.empty")} />}
      {list.data && list.data.length > 0 && (
        <ul className="grid grid-cols-1 gap-4 md:grid-cols-2">
          {list.data.map((c) => (
            <ContactRow key={c.id} c={c} facilityId={facilityId} />
          ))}
        </ul>
      )}
      <ActionError message={errors.message} />
      {!adding ? (
        <Button onClick={() => setAdding(true)}>{t("records.contacts.add")}</Button>
      ) : (
        <Card>
          <InlineForm submitLabel={t("care.save")} busy={create.isPending} onCancel={() => setAdding(false)} onSubmit={() => create.mutate()}>
            <Alert kind="info">{t("records.contacts.addNote")}</Alert>
            <div className="grid gap-3 sm:grid-cols-2">
              <Field label={t("records.contacts.serviceType")} htmlFor="c_type">
                <Select id="c_type" value={form.service_type} onChange={set("service_type")}>
                  {TYPES.map((x) => (
                    <option key={x} value={x}>
                      {t(`records.contacts.type${x}`)}
                    </option>
                  ))}
                </Select>
              </Field>
              <Field label={t("records.contacts.name")} htmlFor="c_name">
                <Input id="c_name" required maxLength={200} value={form.name} onChange={set("name")} />
              </Field>
              <Field label={t("records.contacts.phone")} htmlFor="c_phone">
                <Input id="c_phone" required inputMode="tel" maxLength={32} value={form.phone} onChange={set("phone")} />
              </Field>
              <Field label={t("records.contacts.alternatePhone")} htmlFor="c_alt">
                <Input id="c_alt" inputMode="tel" maxLength={32} value={form.alternate_phone} onChange={set("alternate_phone")} />
              </Field>
              <Field label={t("records.contacts.landmarks")} htmlFor="c_land">
                <Input id="c_land" maxLength={300} value={form.landmarks} onChange={set("landmarks")} />
              </Field>
              <Field label={t("records.contacts.availability")} htmlFor="c_avail">
                <Input id="c_avail" maxLength={200} value={form.availability_note} onChange={set("availability_note")} />
              </Field>
            </div>
          </InlineForm>
        </Card>
      )}
    </div>
  );
}
