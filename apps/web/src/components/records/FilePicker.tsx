import { useState } from "react";
import { useTranslation } from "react-i18next";
import { ACCEPT_ATTRIBUTE, uploadProblem } from "../../lib/records";
import { Field } from "../ui/field";
import { Alert } from "../ui/status";

/** File input that applies the server's rules before anything is sent. */
export function FilePicker({ id, onChange }: { id: string; onChange: (file: File | null) => void }) {
  const { t } = useTranslation();
  const [problem, setProblem] = useState<string | null>(null);
  return (
    <Field label={t("records.file.choose")} htmlFor={id}>
      <input
        id={id}
        type="file"
        accept={ACCEPT_ATTRIBUTE}
        className="block w-full text-base file:mr-3 file:min-h-12 file:rounded-md file:border file:border-line file:bg-surface file:px-4 file:font-semibold md:file:min-h-10"
        onChange={(e) => {
          const file = e.target.files?.[0] ?? null;
          const issue = file ? uploadProblem(file) : null;
          setProblem(issue);
          onChange(issue ? null : file);
        }}
      />
      {problem && <Alert kind="problem">{t(problem)}</Alert>}
    </Field>
  );
}
