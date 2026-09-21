import type { Reminder } from "./types";

// BigInt evita perda de centavos acima do limite de Number.
export function money(cents: string): string {
  const value = BigInt(cents);
  const absolute = value < 0n ? -value : value;
  return `${value < 0n ? "−" : ""}R$ ${(absolute / 100n).toLocaleString("pt-BR")},${(absolute % 100n).toString().padStart(2, "0")}`;
}
export function date(value: string | null | undefined): string {
  if (!value) return "—";
  const [year, month, day] = value.slice(0, 10).split("-");
  return `${day}/${month}/${year}`;
}
export function instant(value: string | null | undefined): string {
  if (!value) return "—";
  return new Intl.DateTimeFormat("pt-BR", {
    dateStyle: "short",
    timeStyle: "short",
    timeZone: "America/Sao_Paulo",
  }).format(new Date(value));
}
export function reminderStage(stage: number): string {
  return stage > 0 ? `D+${stage}` : stage < 0 ? `D−${Math.abs(stage)}` : "D0";
}
export function nextAttempt(
  job: Pick<Reminder, "status" | "next_attempt_at">,
): string {
  // Jobs concluídos mantêm a data em que ficaram elegíveis.
  return ["pending", "retry_scheduled"].includes(job.status)
    ? instant(job.next_attempt_at)
    : "—";
}
