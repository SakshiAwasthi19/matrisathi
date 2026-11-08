from datetime import date, datetime

from pydantic import BaseModel, model_validator

from app.models.identity import AgePrecision


class PersonCreate(BaseModel):
    full_name: str
    age_precision: AgePrecision = AgePrecision.UNKNOWN
    date_of_birth: date | None = None
    birth_year: int | None = None
    reported_age_years: int | None = None
    preferred_language: str | None = None
    reported_medical_history: str | None = None
    known_allergies_medicines: str | None = None
    facility_id: str
    phone: str

    @model_validator(mode="after")
    def _exactly_one_age_field_matches_precision(self) -> "PersonCreate":
        # Never let a day-of-month, a year, or an age number sit alongside a
        # precision that doesn't claim to know it — that's exactly the kind
        # of invented/mismatched information F002 and T003 rule out.
        expected = {
            AgePrecision.EXACT_DOB: "date_of_birth",
            AgePrecision.YEAR_ONLY: "birth_year",
            AgePrecision.APPROXIMATE_AGE: "reported_age_years",
            AgePrecision.UNKNOWN: None,
        }[self.age_precision]
        for field in ("date_of_birth", "birth_year", "reported_age_years"):
            value = getattr(self, field)
            if field == expected and value is None:
                raise ValueError(f"age_precision={self.age_precision} requires {field}")
            if field != expected and value is not None:
                raise ValueError(f"{field} must not be set when age_precision={self.age_precision}")
        return self


class PersonOut(BaseModel):
    id: str
    full_name: str
    age_precision: AgePrecision
    date_of_birth: date | None
    birth_year: int | None
    reported_age_years: int | None
    preferred_language: str | None
    reported_medical_history: str | None
    known_allergies_medicines: str | None
    # True when the caller's role may not see reported history/allergies, so
    # screens say "hidden for your role" rather than "not recorded".
    reported_history_withheld: bool = False
    registering_facility_id: str
    phone: str
    contact_verified_at: datetime | None
    contact_verified_by_name: str | None
