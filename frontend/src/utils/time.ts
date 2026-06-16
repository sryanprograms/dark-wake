import { format, parseISO } from "date-fns";

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

export function toMs(iso: string) {
  return new Date(iso).getTime();
}

export function fromMs(ms: number) {
  return new Date(ms).toISOString();
}
