import type { AlertEvent } from "../ws/timeline";

export function alertKindLabel(kind: string): string {
  if (kind === "ais_gap_resume") return "Resumed reporting";
  if (kind === "ais_silent") return "Stopped reporting position";
  if (kind === "ais_gap") return "Position reporting gap";
  return kind.replace(/_/g, " ");
}

export function alertTierLabel(tier: string | undefined): string | null {
  if (!tier) return null;
  if (tier === "suspicious") return "High concern";
  if (tier === "watch") return "Worth monitoring";
  return tier.replace(/_/g, " ");
}

export function isAttentionAlert(alert: AlertEvent): boolean {
  return (
    alert.kind === "ais_silent" ||
    alert.kind === "ais_gap_resume" ||
    alert.kind === "ais_gap"
  );
}

export function countAttentionAlerts(alerts: AlertEvent[]): number {
  return alerts.filter(isAttentionAlert).length;
}
