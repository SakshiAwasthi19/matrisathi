import type { TFunction } from "i18next";
import type { AgePrecision } from "../api/client";

export function formatAge(
  person: {
    age_precision: AgePrecision;
    date_of_birth: string | null;
    birth_year: number | null;
    reported_age_years: number | null;
  },
  t: TFunction,
): string {
  switch (person.age_precision) {
    case "EXACT_DOB":
      return person.date_of_birth ? t("age.dob", { date: person.date_of_birth }) : t("age.dobUnknown");
    case "YEAR_ONLY":
      return person.birth_year ? t("age.yearOnly", { year: person.birth_year }) : t("age.yearUnknown");
    case "APPROXIMATE_AGE":
      return person.reported_age_years != null
        ? t("age.approx", { years: person.reported_age_years })
        : t("age.approxUnknown");
    case "UNKNOWN":
    default:
      return t("age.notRecorded");
  }
}
