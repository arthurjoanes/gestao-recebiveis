export function portfolioShare(cents: string, totalCents: string): number {
  const total = BigInt(totalCents);
  if (total <= 0n) return 0;
  return Number((BigInt(cents) * 10_000n + total / 2n) / total) / 100;
}
