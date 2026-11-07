import { useMutation } from "@tanstack/react-query";
import { CalendarDays, NotebookPen, UserRound } from "lucide-react";
import { useRef, useState } from "react";
import { useTranslation } from "react-i18next";
import { api, ApiError, type AgePrecision, type Person, type PersonCreateInput } from "../api/client";
import { PageState } from "../components/PageState";
import { Button } from "../components/ui/button";
import { Card, Section } from "../components/ui/card";
import { Field, Hint, Input, Select, Textarea } from "../components/ui/field";
import { Alert } from "../components/ui/status";
import { attemptKey, clearAttempt, createAttemptStore } from "../lib/attempts";
import { useSession } from "../state/session";

export function RegisterNewMother({ onEpisodeCreated }: { onEpisodeCreated: (episodeId: string) => void }) {
  const { t } = useTranslation();
  const { staff } = useSession();
  const memberships = staff?.memberships ?? [];
  const [facilityId, setFacilityId] = useState(memberships[0]?.facility_id ?? "");
  const [fullName, setFullName] = useState("");
  const [phone, setPhone] = useState("");
  const [agePrecision, setAgePrecision] = useState<AgePrecision>("UNKNOWN");
  const [dateOfBirth, setDateOfBirth] = useState("");
  const [birthYear, setBirthYear] = useState("");
  const [reportedAgeYears, setReportedAgeYears] = useState("");
  const [medicalHistory, setMedicalHistory] = useState("");
  const [allergies, setAllergies] = useState("");
  const attempts = useRef(createAttemptStore());
  // Set once the person exists but opening her episode hasn't succeeded yet.
  // A resubmit then retries only the episode, so a failure between the two
  // calls can never register the same mother twice.
  const [registeredPerson, setRegisteredPerson] = useState<Person | null>(null);

  const register = useMutation({
    mutationFn: async () => {
      let person = registeredPerson;
      if (!person) {
        const input: PersonCreateInput = {
          full_name: fullName,
          facility_id: facilityId,
          phone,
          age_precision: agePrecision,
          date_of_birth: agePrecision === "EXACT_DOB" ? dateOfBirth : null,
          birth_year: agePrecision === "YEAR_ONLY" ? Number(birthYear) : null,
          reported_age_years: agePrecision === "APPROXIMATE_AGE" ? Number(reportedAgeYears) : null,
          reported_medical_history: medicalHistory.trim() || null,
          known_allergies_medicines: allergies.trim() || null,
        };
        person = await api.createPerson(input, attemptKey(attempts.current, "person", input));
        setRegisteredPerson(person);
      }
      const episode = await api.createPregnancyEpisode(
        person.id,
        attemptKey(attempts.current, "episode", { person_id: person.id }),
      );
      clearAttempt(attempts.current, "person");
      clearAttempt(attempts.current, "episode");
      setRegisteredPerson(null);
      return episode;
    },
    onSuccess: (episode) => onEpisodeCreated(episode.id),
  });

  if (memberships.length === 0) {
    return <PageState kind="no-access" body={t("register.noFacilities")} />;
  }

  const ageOption = (value: AgePrecision, label: string, input?: React.ReactNode) => (
    <div className="flex flex-wrap items-center gap-x-3 gap-y-2">
      <label className="inline-flex min-h-12 cursor-pointer items-center gap-3 md:min-h-10">
        <input
          type="radio"
          name="age_precision"
          id={`age_precision_${value.toLowerCase()}`}
          checked={agePrecision === value}
          onChange={() => setAgePrecision(value)}
          className="size-5 accent-brand"
        />
        <span>{label}</span>
      </label>
      {input}
    </div>
  );

  const errorText = register.error
    ? register.error instanceof ApiError
      ? register.error.message
      : t("register.failed")
    : null;

  return (
    <Card>
      <h2 className="text-lg font-semibold">{t("register.title")}</h2>
      <form
        className="mt-4 space-y-5"
        onSubmit={(e) => {
          e.preventDefault();
          register.mutate();
        }}
      >
        <fieldset disabled={registeredPerson !== null} className="space-y-8">
          <Section icon={UserRound} title={t("register.sectionWho")}>
          <Field label={t("register.facility")} htmlFor="facility">
            <Select id="facility" value={facilityId} onChange={(e) => setFacilityId(e.target.value)} required>
              <option value="" disabled>
                {t("register.selectFacility")}
              </option>
              {memberships.map((m) => (
                <option key={m.facility_id} value={m.facility_id}>
                  {t("register.facilityOption", { facility: m.facility_name, role: m.role })}
                </option>
              ))}
            </Select>
          </Field>
          <div className="grid gap-5 md:grid-cols-2">
            <Field label={t("register.fullName")} htmlFor="full_name">
              <Input id="full_name" autoComplete="off" value={fullName} onChange={(e) => setFullName(e.target.value)} required />
            </Field>
            <Field label={t("register.phone")} htmlFor="phone" hint={t("register.phoneHint")}>
              <Input
                id="phone"
                inputMode="tel"
                autoComplete="off"
                value={phone}
                onChange={(e) => setPhone(e.target.value)}
                required
              />
            </Field>
          </div>
          </Section>

          <Section icon={CalendarDays} title={t("register.sectionAge")}>
          <fieldset className="space-y-1 rounded-lg border border-line bg-page/60 p-3 md:p-4">
            <legend className="sr-only">{t("register.ageLegend")}</legend>
            {ageOption("UNKNOWN", t("register.ageUnknown"))}
            {ageOption(
              "EXACT_DOB",
              t("register.ageExact"),
              <Input
                id="date_of_birth_input"
                type="date"
                aria-label={t("register.ageExact")}
                value={dateOfBirth}
                disabled={agePrecision !== "EXACT_DOB"}
                onChange={(e) => setDateOfBirth(e.target.value)}
                required={agePrecision === "EXACT_DOB"}
                className="w-48"
              />,
            )}
            {ageOption(
              "YEAR_ONLY",
              t("register.ageYearOnly"),
              <Input
                id="birth_year_input"
                type="number"
                inputMode="numeric"
                aria-label={t("register.ageYearOnly")}
                value={birthYear}
                disabled={agePrecision !== "YEAR_ONLY"}
                onChange={(e) => setBirthYear(e.target.value)}
                required={agePrecision === "YEAR_ONLY"}
                className="w-28"
              />,
            )}
            {ageOption(
              "APPROXIMATE_AGE",
              t("register.ageApprox"),
              <Input
                id="reported_age_years_input"
                type="number"
                inputMode="numeric"
                aria-label={t("register.ageApprox")}
                value={reportedAgeYears}
                disabled={agePrecision !== "APPROXIMATE_AGE"}
                onChange={(e) => setReportedAgeYears(e.target.value)}
                required={agePrecision === "APPROXIMATE_AGE"}
                className="w-28"
              />,
            )}
            <Hint>{t("register.ageHint")}</Hint>
          </fieldset>
          </Section>

          <Section icon={NotebookPen} title={t("register.sectionHistory")}>
          <Field label={t("register.history")} htmlFor="history">
            <Textarea id="history" value={medicalHistory} onChange={(e) => setMedicalHistory(e.target.value)} rows={2} />
          </Field>
          <Field label={t("register.allergies")} htmlFor="allergies">
            <Textarea id="allergies" value={allergies} onChange={(e) => setAllergies(e.target.value)} rows={2} />
          </Field>
          </Section>
        </fieldset>

        {registeredPerson && (
          <Alert kind="pending">{t("register.registeredPending", { name: registeredPerson.full_name })}</Alert>
        )}
        {errorText && <Alert kind="problem">{errorText}</Alert>}
        <Button type="submit" className="w-full md:w-auto" disabled={register.isPending || !facilityId}>
          {register.isPending
            ? t("register.submitting")
            : registeredPerson
              ? t("register.retryEpisode")
              : t("register.submit")}
        </Button>
      </form>
    </Card>
  );
}
