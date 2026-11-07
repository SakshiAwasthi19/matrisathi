/** The public Urgent help address for a facility, as printed on the birth
 * plan. It opens without signing in and without location access. */
export function urgentHelpUrl(facilityId: string, origin: string = window.location.origin): string {
  return `${origin}/urgent-help/${facilityId}`;
}

/** "tel:" link with spaces and dashes removed (dialler-friendly). */
export function telHref(phone: string): string {
  return `tel:${phone.replace(/[\s-]/g, "")}`;
}
