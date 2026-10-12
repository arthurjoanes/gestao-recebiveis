export const PAYMENT_INTENT_PREFIX = "gr.payment-intent.v1:";
const ACTIVE_ACCOUNT = "gr.payment-account.v1";
export const PAYMENT_INTENT_TTL_MS = 24 * 60 * 60 * 1000;
export interface PaymentIntent {
  version: 1;
  user_id: number;
  receivable_id: number;
  created_at: number;
  payload: { idempotency_key: string; note: string; amount_cents?: string };
}
function key(userId: number, titleId: number): string {
  return `${PAYMENT_INTENT_PREFIX}${userId}:${titleId}`;
}
export function readPaymentIntent(
  userId: number,
  titleId: number,
): PaymentIntent | null {
  if (typeof window === "undefined") return null;
  try {
    const raw = sessionStorage.getItem(key(userId, titleId));
    if (!raw) return null;
    const value = JSON.parse(raw) as PaymentIntent;
    if (
      value.version !== 1 ||
      value.user_id !== userId ||
      value.receivable_id !== titleId ||
      !Number.isFinite(value.created_at) ||
      typeof value.payload?.idempotency_key !== "string" ||
      value.payload.idempotency_key.length === 0 ||
      typeof value.payload.note !== "string" ||
      (value.payload.amount_cents !== undefined &&
        (typeof value.payload.amount_cents !== "string" ||
          !/^[1-9][0-9]*$/.test(value.payload.amount_cents) ||
          BigInt(value.payload.amount_cents) > 9223372036854775807n))
    )
      throw new Error("Formato local inválido.");
    return value;
  } catch {
    // Registro ilegível também é ambíguo: não o substitua silenciosamente.
    throw new Error(
      "Não foi possível ler a intenção local. Confira o histórico antes de registrar outro pagamento; encerre a sessão para limpar os dados locais.",
    );
  }
}
export function savePaymentIntent(intent: PaymentIntent): void {
  // A gravação ocorre antes do envio. Se o navegador a bloquear, não envie.
  sessionStorage.setItem(
    key(intent.user_id, intent.receivable_id),
    JSON.stringify(intent),
  );
}
export function clearPaymentIntent(userId: number, titleId: number): void {
  sessionStorage.removeItem(key(userId, titleId));
}
export function clearAccountIntents(userId: number): void {
  try {
    for (const item of Object.keys(sessionStorage)) {
      if (item.startsWith(`${PAYMENT_INTENT_PREFIX}${userId}:`))
        sessionStorage.removeItem(item);
    }
    if (sessionStorage.getItem(ACTIVE_ACCOUNT) === String(userId))
      sessionStorage.removeItem(ACTIVE_ACCOUNT);
  } catch {
    // Logout continua disponível quando o navegador bloqueia armazenamento.
  }
}
export function activatePaymentAccount(userId: number): void {
  try {
    const previous = sessionStorage.getItem(ACTIVE_ACCOUNT);
    if (previous !== null && previous !== String(userId)) {
      for (const item of Object.keys(sessionStorage)) {
        if (item.startsWith(PAYMENT_INTENT_PREFIX))
          sessionStorage.removeItem(item);
      }
    }
    sessionStorage.setItem(ACTIVE_ACCOUNT, String(userId));
  } catch {
    // Consultas permanecem acessíveis; read/save bloqueiam pagamentos locais.
  }
}
