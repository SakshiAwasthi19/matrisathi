import { useMutation, useQuery } from "@tanstack/react-query";
import { ClipboardCheck } from "lucide-react";
import { useState } from "react";
import { useTranslation } from "react-i18next";
import { careApi, type CarePlanTemplate } from "../../api/client";
import { formatDate, formatDateTime } from "../../lib/format";
import { errorStateKind, PageState } from "../PageState";
import { Button } from "../ui/button";
import { Card, Section } from "../ui/card";
import { Field, Select } from "../ui/field";
import { Alert } from "../ui/status";
import { ActionError, useActionError } from "./shared";

function TemplateItems({ template }: { template: CarePlanTemplate }) {
  return (
    <ol className="list-decimal space-y-1 pl-6 text-base">
      {template.items.map((i) => (
        <li key={i.id}>{i.name}</li>
      ))}
    </ol>
  );
}

export function CarePlanPanel({ episodeId, isClinician }: { episodeId: string; isClinician: boolean }) {
  const { t } = useTranslation();
  const key = ["carePlan", episodeId];
  const errors = useActionError([key, ["appointments", episodeId], ["episodeTasks", episodeId], ["tasks"]]);
  const plan = useQuery({ queryKey: key, queryFn: () => careApi.getCarePlan(episodeId) });
  const templates = useQuery({ queryKey: ["templates"], queryFn: careApi.listTemplates, enabled: isClinician });
  const [choosing, setChoosing] = useState(false);
  const [templateId, setTemplateId] = useState("");

  const publish = useMutation({
    mutationFn: (id: string) => careApi.publishPlan(episodeId, id),
    onSuccess: () => {
      setChoosing(false);
      setTemplateId("");
      errors.clear();
      errors.reload();
    },
    onError: errors.onError,
  });

  const options = (templates.data ?? []).filter((tpl) => tpl.id !== plan.data?.template.id);
  const chooser = (
    <div className="space-y-3">
      {plan.data && <Alert kind="info">{t("care.plan.replaceNote")}</Alert>}
      {templates.isPending ? (
        <PageState kind="loading" />
      ) : options.length === 0 ? (
        <p className="text-base text-muted">{t("care.plan.noTemplates")}</p>
      ) : (
        <>
          <Field label={t("care.plan.template")} htmlFor="plan_template">
            <Select id="plan_template" value={templateId} onChange={(e) => setTemplateId(e.target.value)}>
              <option value="" disabled>
                {t("care.plan.chooseTemplate")}
              </option>
              {options.map((tpl) => (
                <option key={tpl.id} value={tpl.id}>
                  {tpl.name} ({tpl.version_label})
                </option>
              ))}
            </Select>
          </Field>
          {templateId && options.find((o) => o.id === templateId)?.is_placeholder && (
            <Alert kind="pending">{t("care.plan.placeholderWarning")}</Alert>
          )}
          <div className="flex flex-col gap-2 sm:flex-row">
            <Button disabled={!templateId || publish.isPending} onClick={() => publish.mutate(templateId)}>
              {publish.isPending ? t("care.plan.publishing") : t("care.plan.publish")}
            </Button>
            {plan.data && (
              <Button variant="secondary" onClick={() => setChoosing(false)}>
                {t("care.cancel")}
              </Button>
            )}
          </div>
        </>
      )}
    </div>
  );

  return (
    <Card>
      <Section icon={ClipboardCheck} title={t("care.plan.title")}>
        {plan.isPending && <PageState kind="loading" />}
        {plan.isError && <PageState kind={errorStateKind(plan.error)} />}
        {plan.isSuccess && plan.data === null && (
          <div className="space-y-3">
            <p className="text-base text-muted">{isClinician ? t("care.plan.none") : t("care.plan.noneNonClinician")}</p>
            {isClinician && chooser}
          </div>
        )}
        {plan.data && (
          <div className="space-y-3">
            {plan.data.template.is_placeholder && <Alert kind="pending">{t("care.plan.placeholderWarning")}</Alert>}
            <p className="text-lg font-semibold">
              {plan.data.template.name} <span className="text-base font-normal text-muted">({plan.data.template.version_label})</span>
            </p>
            <p className="text-sm text-muted">
              {t("care.plan.publishedBy", { name: plan.data.published_by_name ?? "", date: formatDateTime(plan.data.published_at) })}
              {plan.data.template.approved_on && ` · ${formatDate(plan.data.template.approved_on)}`}
            </p>
            <TemplateItems template={plan.data.template} />
            {plan.data.unscheduled_item_names.length > 0 && (
              <Alert kind="pending">{t("care.plan.unscheduled", { names: plan.data.unscheduled_item_names.join(", ") })}</Alert>
            )}
            {isClinician && !choosing && (
              <Button variant="secondary" onClick={() => setChoosing(true)}>
                {t("care.plan.replace")}
              </Button>
            )}
            {isClinician && choosing && chooser}
          </div>
        )}
        <ActionError message={errors.message} />
      </Section>
    </Card>
  );
}
