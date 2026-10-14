import type { Reminder } from "./types";

// BigInt evita perda de centavos acima do limite de Number.
export function money(cents: string): string {
  const value = BigInt(cents);
  const absolute = value < 0n ? -value : value;
  return `${value < 0n ? "−" : ""}R$ ${(absolute / 100n).toLocaleString("pt-BR")},${(absolute % 100n).toString().padStart(2, "0")}`;
}
// Aceita decimal brasileiro sem separadores de milhar; toda a conta é inteira.
export function parseBrl(value: string): string {
  const match = /^(\d+)(?:,(\d{1,2}))?$/.exec(value.trim());
  if (!match)
    throw new Error(
      "Use reais com vírgula e até duas casas, sem pontos. Ex.: 10,50.",
    );
  const cents =
    BigInt(match[1]) * 100n + BigInt((match[2] ?? "").padEnd(2, "0") || "0");
  if (cents <= 0n) throw new Error("Informe um valor maior que zero.");
  if (cents > 9223372036854775807n)
    throw new Error("O valor excede o limite permitido.");
  return cents.toString();
}
export function brlInput(cents: string): string {
  const value = BigInt(cents);
  return `${value / 100n},${(value % 100n).toString().padStart(2, "0")}`;
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

export const bucketOptions = [
  { key: "current", label: "Em dia (inclui hoje)" },
  { key: "1_30", label: "1–30 dias" },
  { key: "31_60", label: "31–60 dias" },
  { key: "61_90", label: "61–90 dias" },
  { key: "over_90", label: "Acima de 90 dias" },
];
export function bucketLabel(key: string): string {
  return (
    bucketOptions.find((option) => option.key === key)?.label ??
    "Todas as faixas"
  );
}
export function titleCount(count: number): string {
  return `${count} ${count === 1 ? "título" : "títulos"}`;
}
