import { useRef, useState } from "react";
import { api, ApiError, type AgePrecision, type Person, type PersonCreateInput } from "../api/client";
import { attemptKey, clearAttempt, createAttemptStore } from "../lib/attempts";
import { useSession } from "../state/session";

export function RegisterNewMother({ onEpisodeCreated }: { onEpisodeCreated: (episodeId: string) => void }) {
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
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const attempts = useRef(createAttemptStore());
  // Set once the person exists but opening her episode hasn't succeeded yet.
  // A resubmit then retries only the episode, so a failure between the two
  // calls can never register the same mother twice.
  const [registeredPerson, setRegisteredPerson] = useState<Person | null>(null);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setSubmitting(true);
    try {
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
      onEpisodeCreated(episode.id);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Could not register mother");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div style={{ maxWidth: 520, fontFamily: "sans-serif" }}>
      <h2>Register a mother &amp; open a pregnancy episode</h2>
      <p style={{ color: "#555" }}>Synthetic data only — this is a demonstration flow.</p>
      <form onSubmit={handleSubmit}>
        <fieldset disabled={registeredPerson !== null} style={{ border: 0, padding: 0, margin: 0 }}>
          <div style={{ marginBottom: 12 }}>
            <label htmlFor="facility">Facility</label>
            <br />
            <select id="facility" value={facilityId} onChange={(e) => setFacilityId(e.target.value)} required>
              <option value="" disabled>
                Select a facility
              </option>
              {memberships.map((m) => (
                <option key={m.facility_id} value={m.facility_id}>
                  {m.facility_name} ({m.role})
                </option>
              ))}
            </select>
          </div>
          <div style={{ marginBottom: 12 }}>
            <label htmlFor="full_name">Mother's full name</label>
            <br />
            <input id="full_name" value={fullName} onChange={(e) => setFullName(e.target.value)} required />
          </div>
          <div style={{ marginBottom: 12 }}>
            <label htmlFor="phone">Contact phone</label>
            <br />
            <input id="phone" value={phone} onChange={(e) => setPhone(e.target.value)} required />
            <p style={{ fontSize: 12, color: "#777", margin: "4px 0 0" }}>
              A phone number may be shared by more than one household member — it is never used as
              anyone's identity.
            </p>
          </div>

          <fieldset style={{ marginBottom: 12 }}>
            <legend>Age / date of birth</legend>
            <label>
              <input
                id="age_precision_unknown"
                type="radio"
                name="age_precision"
                checked={agePrecision === "UNKNOWN"}
                onChange={() => setAgePrecision("UNKNOWN")}
              />{" "}
              Unknown
            </label>
            <br />
            <label>
              <input
                id="age_precision_exact_dob"
                type="radio"
                name="age_precision"
                checked={agePrecision === "EXACT_DOB"}
                onChange={() => setAgePrecision("EXACT_DOB")}
              />{" "}
              Exact date of birth:{" "}
              <input
                id="date_of_birth_input"
                type="date"
                value={dateOfBirth}
                disabled={agePrecision !== "EXACT_DOB"}
                onChange={(e) => setDateOfBirth(e.target.value)}
                required={agePrecision === "EXACT_DOB"}
              />
            </label>
            <br />
            <label>
              <input
                id="age_precision_year_only"
                type="radio"
                name="age_precision"
                checked={agePrecision === "YEAR_ONLY"}
                onChange={() => setAgePrecision("YEAR_ONLY")}
              />{" "}
              Year of birth only:{" "}
              <input
                id="birth_year_input"
                type="number"
                inputMode="numeric"
                value={birthYear}
                disabled={agePrecision !== "YEAR_ONLY"}
                onChange={(e) => setBirthYear(e.target.value)}
                required={agePrecision === "YEAR_ONLY"}
                style={{ width: 80 }}
              />
            </label>
            <br />
            <label>
              <input
                id="age_precision_approximate"
                type="radio"
                name="age_precision"
                checked={agePrecision === "APPROXIMATE_AGE"}
                onChange={() => setAgePrecision("APPROXIMATE_AGE")}
              />{" "}
              Approximate age (years):{" "}
              <input
                id="reported_age_years_input"
                type="number"
                inputMode="numeric"
                value={reportedAgeYears}
                disabled={agePrecision !== "APPROXIMATE_AGE"}
                onChange={(e) => setReportedAgeYears(e.target.value)}
                required={agePrecision === "APPROXIMATE_AGE"}
                style={{ width: 80 }}
              />
            </label>
            <p style={{ fontSize: 12, color: "#777", margin: "4px 0 0" }}>
              Never guessed — pick "Unknown" rather than inventing a date.
            </p>
          </fieldset>

          <div style={{ marginBottom: 12 }}>
            <label htmlFor="history">Reported medical history (as told by the family, optional)</label>
            <br />
            <textarea
              id="history"
              value={medicalHistory}
              onChange={(e) => setMedicalHistory(e.target.value)}
              rows={2}
              style={{ width: "100%" }}
            />
          </div>
          <div style={{ marginBottom: 12 }}>
            <label htmlFor="allergies">Known allergies / current medicines (optional)</label>
            <br />
            <textarea
              id="allergies"
              value={allergies}
              onChange={(e) => setAllergies(e.target.value)}
              rows={2}
              style={{ width: "100%" }}
            />
          </div>
        </fieldset>

        {registeredPerson && (
          <p>
            {registeredPerson.full_name} is registered. Opening the pregnancy episode didn't finish —
            try again.
          </p>
        )}
        {error && <p style={{ color: "crimson" }}>{error}</p>}
        <button type="submit" disabled={submitting || !facilityId}>
          {submitting
            ? "Creating..."
            : registeredPerson
              ? "Try opening the episode again"
              : "Register mother & create episode"}
        </button>
      </form>
    </div>
  );
}
