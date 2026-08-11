import { format, formatDistanceStrict, parseISO } from "date-fns";

export function formatUtc(iso: string, pattern = "yyyy-MM-dd HH:mm:ss") {
  try {
    return `${format(parseISO(iso), pattern)} UTC`;
  } catch {
    return iso;
  }
}

export function formatUtcShort(iso: string) {
  return formatUtc(iso, "HH:mm:ss");
}

export function formatUtcDate(iso: string) {
  return formatUtc(iso, "yyyy-MM-dd");
}

function reportReferenceDate(referenceIso?: string): Date {
  if (referenceIso) {
    try {
      return parseISO(referenceIso);
    } catch {
      // fall through to now
    }
  }
  return new Date();
}

/** How long before `referenceIso` the report occurred (defaults to wall-clock now). */
export function formatReportAge(iso: string, referenceIso?: string): string {
  try {
    const reportDate = parseISO(iso);
    const refDate = reportReferenceDate(referenceIso);
    if (reportDate.getTime() > refDate.getTime()) return "just now";
    return `${formatDistanceStrict(reportDate, refDate, { roundingMethod: "floor" })} ago`;
  } catch {
    return "—";
  }
}

/** Detail panel: full timestamp plus age. */
export function formatLastReportLong(iso: string, referenceIso?: string): string {
  try {
    return `${formatUtc(iso)} · ${formatReportAge(iso, referenceIso)}`;
  } catch {
    return iso;
  }
}

export function toMs(iso: string) {
  return new Date(iso).getTime();
}

export function fromMs(ms: number) {
  return new Date(ms).toISOString();
}
