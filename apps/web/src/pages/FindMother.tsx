import { useRef, useState } from "react";
import { api, ApiError, type Person } from "../api/client";
import { formatAge } from "../lib/age";
import { attemptKey, clearAttempt, createAttemptStore } from "../lib/attempts";
import { useSession } from "../state/session";

type SearchState = "idle" | "loading" | "done" | "error";

export function FindMother({ onEpisodeCreated }: { onEpisodeCreated: (episodeId: string) => void }) {
  const { staff } = useSession();
  const [phone, setPhone] = useState("");
  const [fullName, setFullName] = useState("");
  const [state, setState] = useState<SearchState>("idle");
  const [error, setError] = useState<string | null>(null);
  const [results, setResults] = useState<Person[]>([]);
  const [busyPersonId, setBusyPersonId] = useState<string | null>(null);
  const [rowError, setRowError] = useState<Record<string, string>>({});
  const attempts = useRef(createAttemptStore());

  const facilityName = (id: string) => staff?.memberships.find((m) => m.facility_id === id)?.facility_name ?? id;

  async function handleSearch(e: React.FormEvent) {
    e.preventDefault();
    if (!phone.trim() && !fullName.trim()) {
      setError("Enter a phone number, a name, or both.");
      setState("error");
      return;
    }
    setState("loading");
    setError(null);
    try {
      const found = await api.searchPeople({
        phone: phone.trim() || undefined,
        full_name: fullName.trim() || undefined,
      });
      setResults(found);
      setState("done");
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Search failed");
      setState("error");
    }
  }

  async function handleSelect(person: Person) {
    setBusyPersonId(person.id);
    setRowError((prev) => ({ ...prev, [person.id]: "" }));
    try {
      const scope = `episode:${person.id}`;
      const episode = await api.createPregnancyEpisode(
        person.id,
        attemptKey(attempts.current, scope, { person_id: person.id }),
      );
      clearAttempt(attempts.current, scope);
      onEpisodeCreated(episode.id);
    } catch (err) {
      setRowError((prev) => ({
        ...prev,
        [person.id]: err instanceof ApiError ? err.message : "Could not open this record",
      }));
    } finally {
      setBusyPersonId(null);
    }
  }

  async function handleVerify(person: Person) {
    setBusyPersonId(person.id);
    try {
      const updated = await api.verifyContact(person.id);
      setResults((prev) => prev.map((p) => (p.id === updated.id ? updated : p)));
    } catch (err) {
      setRowError((prev) => ({
        ...prev,
        [person.id]: err instanceof ApiError ? err.message : "Could not verify contact",
      }));
    } finally {
      setBusyPersonId(null);
    }
  }

  return (
    <div style={{ maxWidth: 560, fontFamily: "sans-serif" }}>
      <h2>Find an existing mother</h2>
      <p style={{ color: "#555" }}>
        Search only finds records at facilities you're assigned to. A shared phone number never merges
        people — each match is listed separately.
      </p>
      <form onSubmit={handleSearch}>
        <div style={{ marginBottom: 12 }}>
          <label htmlFor="search_phone">Phone</label>
          <br />
          <input id="search_phone" value={phone} onChange={(e) => setPhone(e.target.value)} />
        </div>
        <div style={{ marginBottom: 12 }}>
          <label htmlFor="search_name">Name (partial matches)</label>
          <br />
          <input id="search_name" value={fullName} onChange={(e) => setFullName(e.target.value)} />
        </div>
        <button type="submit" disabled={state === "loading"}>
          {state === "loading" ? "Searching..." : "Search"}
        </button>
      </form>

      {state === "error" && <p style={{ color: "crimson" }}>{error}</p>}

      {state === "done" && results.length === 0 && (
        <p style={{ marginTop: 16 }}>
          No matching records found in your facilities. If this mother is new here, use "Register new
          mother" instead.
        </p>
      )}

      {results.length > 0 && (
        <ul style={{ listStyle: "none", padding: 0, marginTop: 16 }}>
          {results.map((person) => (
            <li
              key={person.id}
              style={{ border: "1px solid #ccc", borderRadius: 4, padding: 12, marginBottom: 12 }}
            >
              <strong>{person.full_name}</strong>
              <div style={{ fontSize: 14, color: "#333" }}>
                <div>{formatAge(person)}</div>
                <div>Phone: {person.phone}</div>
                <div>Facility: {facilityName(person.registering_facility_id)}</div>
                <div>
                  Contact:{" "}
                  {person.contact_verified_at ? (
                    <span>
                      confirmed by {person.contact_verified_by_name ?? "a staff member"} on{" "}
                      {new Date(person.contact_verified_at).toLocaleDateString()}
                    </span>
                  ) : (
                    <span>not yet confirmed with the family</span>
                  )}
                </div>
              </div>
              {rowError[person.id] && <p style={{ color: "crimson", fontSize: 13 }}>{rowError[person.id]}</p>}
              <div style={{ marginTop: 8 }}>
                <button disabled={busyPersonId === person.id} onClick={() => handleSelect(person)}>
                  {busyPersonId === person.id ? "Opening..." : "Select & create episode"}
                </button>{" "}
                {!person.contact_verified_at && (
                  <button disabled={busyPersonId === person.id} onClick={() => handleVerify(person)}>
                    Confirm this is their number
                  </button>
                )}
              </div>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
