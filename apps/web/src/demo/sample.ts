/*
 * SAMPLE DATA for screens whose backend does not exist yet (reporting,
 * messaging, child care). Everything here is invented and administrative
 * only: counts, dates and logistics. No clinical content, no real people.
 *
 * Every screen that shows it must display <SampleBadge />. When the real
 * APIs arrive, replace the import of this module with the API call; the
 * shapes below are what those endpoints are expected to return.
 */
import type { Point, StackRow } from "../components/charts";

export const registrationsByWeek: Point[] = [
  { label: "Sep 14", value: 6 },
  { label: "Sep 21", value: 9 },
  { label: "Sep 28", value: 7 },
  { label: "Oct 5", value: 11 },
  { label: "Oct 12", value: 10 },
  { label: "Oct 19", value: 14 },
  { label: "Oct 26", value: 12 },
  { label: "Nov 2", value: 16 },
];

/** Visits per week: [attended, missed]. Missed = administrative follow-up, never risk. */
export const visitsByWeek: StackRow[] = [
  { label: "Sep 28", values: [18, 3] },
  { label: "Oct 5", values: [22, 4] },
  { label: "Oct 12", values: [20, 2] },
  { label: "Oct 19", values: [25, 5] },
  { label: "Oct 26", values: [27, 3] },
  { label: "Nov 2", values: [24, 2] },
];

export const referralFunnel: Point[] = [
  { label: "Sent", value: 24 },
  { label: "Service contacted", value: 21 },
  { label: "Attended", value: 17 },
  { label: "Advice received", value: 14 },
  { label: "Follow-up completed", value: 11 },
];

export const insightTiles = {
  activePregnancies: 142,
  visitsThisMonth: 96,
  followUpsClosedOnTime: "88%",
  reportsAwaitingReview: 7,
};

export type ThreadStatus = "unlinked" | "open" | "closed";
export interface SampleThread {
  id: string;
  name: string;
  phoneTail: string;
  status: ThreadStatus;
  preview: string;
  time: string;
  unread: number;
  kind: "text" | "voice" | "photo";
  messages: { from: "family" | "staff" | "system"; text: string; time: string; kind?: "voice" | "photo" }[];
}

export const sampleThreads: SampleThread[] = [
  {
    id: "t1",
    name: "Sample Mother A",
    phoneTail: "•• 0123",
    status: "open",
    preview: "Can I come on Thursday instead?",
    time: "09:42",
    unread: 2,
    kind: "text",
    messages: [
      { from: "system", text: "Reminder sent: visit on Tuesday at the sub-centre (approved template).", time: "Mon 08:00" },
      { from: "family", text: "Namaste. Tuesday is difficult, my husband is away.", time: "09:40" },
      { from: "family", text: "Can I come on Thursday instead?", time: "09:42" },
    ],
  },
  {
    id: "t2",
    name: "Unlinked number",
    phoneTail: "•• 7781",
    status: "unlinked",
    preview: "Voice note (0:24)",
    time: "08:15",
    unread: 1,
    kind: "voice",
    messages: [{ from: "family", text: "Voice note (0:24)", time: "08:15", kind: "voice" }],
  },
  {
    id: "t3",
    name: "Sample Mother B",
    phoneTail: "•• 4410",
    status: "open",
    preview: "Photo of the outside report",
    time: "Yesterday",
    unread: 0,
    kind: "photo",
    messages: [
      { from: "family", text: "Photo of the outside report", time: "Yesterday 17:05", kind: "photo" },
      { from: "staff", text: "Thank you. A doctor will look at it; we will call you.", time: "Yesterday 17:20" },
    ],
  },
  {
    id: "t4",
    name: "Sample Mother C",
    phoneTail: "•• 9902",
    status: "closed",
    preview: "Thank you, we have the transport number.",
    time: "Tue",
    unread: 0,
    kind: "text",
    messages: [
      { from: "staff", text: "The transport number is on your printed plan.", time: "Tue 11:02" },
      { from: "family", text: "Thank you, we have the transport number.", time: "Tue 11:10" },
    ],
  },
];

export interface SampleChild {
  id: string;
  name: string;
  mother: string;
  ageLabel: string;
  nextStep: string;
  status: "due" | "given" | "unknown";
}

export const sampleChildren: SampleChild[] = [
  { id: "c1", name: "Sample Baby A", mother: "Sample Mother D", ageLabel: "6 weeks", nextStep: "Placeholder dose 2", status: "due" },
  { id: "c2", name: "Sample Baby B", mother: "Sample Mother E", ageLabel: "4 months", nextStep: "Placeholder dose 3", status: "given" },
  { id: "c3", name: "Sample Twin 1", mother: "Sample Mother F", ageLabel: "10 days", nextStep: "Placeholder contact", status: "unknown" },
  { id: "c4", name: "Sample Twin 2", mother: "Sample Mother F", ageLabel: "10 days", nextStep: "Placeholder contact", status: "due" },
];
