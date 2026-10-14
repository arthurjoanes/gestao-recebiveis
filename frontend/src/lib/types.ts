export interface User {
  id: number;
  email: string;
  name: string;
  role: "operator" | "reader";
}
export interface Session {
  user: User;
  csrf_token: string;
}
export interface Page<T> {
  items: T[];
  total: number;
  page: number;
  page_size: number;
}
export interface Payment {
  id: number;
  amount_cents: string;
  paid_at: string;
  recorded_at: string;
  note: string;
}
export interface AuditEvent {
  id: number;
  type: string;
  message: string;
  occurred_at: string;
  business_at: string;
  details: Record<string, unknown>;
}
export interface Receivable {
  id: number;
  source_system: string;
  external_receivable_id: string;
  customer_id: number;
  customer_name: string;
  customer_email: string;
  description: string;
  amount_cents: string;
  paid_cents: string;
  remaining_cents: string;
  payment_state: "unpaid" | "partial" | "paid";
  due_date: string;
  status: string;
  overdue: boolean;
  scenario: string;
}
export interface ReceivableDetail extends Receivable {
  payments: Payment[];
  history: Record<
    "payments" | "events" | "reminders",
    { total: number; page: number; page_size: number }
  >;
  payment: Payment | null;
  reminders: Reminder[];
  events: AuditEvent[];
}
export interface Reminder {
  id: number;
  receivable_id: number;
  external_receivable_id: string;
  customer_name: string;
  amount_cents: string;
  paid_cents: string;
  remaining_cents: string;
  stage: number;
  status: string;
  attempts_count: number;
  next_attempt_at: string | null;
  last_error: string | null;
  lease_expires_at: string | null;
  idempotency_key: string;
  cancel_requested: boolean;
}
export interface ReminderDetail extends Reminder {
  attempts: {
    id: number;
    number: number;
    outcome: string;
    error: string | null;
    authorized_at: string;
    authorized_remaining_cents: string;
    finished_at: string | null;
  }[];
  delivery: { id: number; accepted_at: string; message: string } | null;
}
export interface ImportBatch {
  id: number;
  filename: string;
  status: string;
  created_at: string;
  report: {
    row_count: number;
    new_count: number;
    existing_count: number;
    duplicate_count: number;
    total_cents: string;
    errors: { line: number; code: string; message: string }[];
    rows: {
      line: number;
      external_receivable_id: string;
      customer_name: string;
      amount_cents: string;
      due_date: string;
      status: string;
      message?: string;
    }[];
  };
}
export type ImportBatchSummary = Pick<
  ImportBatch,
  "id" | "filename" | "status" | "created_at"
> & { row_count: number };
export interface Overview {
  generated_at: string;
  business_now: string;
  current_cents: string;
  current_count: number;
  open_cents: string;
  overdue_cents: string;
  received_cents: string;
  open_count: number;
  overdue_count: number;
  paid_count: number;
  canceled_count: number;
  business_date: string;
  received_from: string | null;
  received_to: string | null;
}
export interface Demo {
  enabled: boolean;
  business_now: string;
  business_date: string;
  worker_enabled: boolean;
  policy: string | string[];
}

export type AgingBucket = "current" | "1_30" | "31_60" | "61_90" | "over_90";
export interface Aging extends Page<
  Receivable & { aging_bucket: AgingBucket; days_overdue: number }
> {
  generated_at: string;
  business_now: string;
  business_date: string;
  open_cents: string;
  title_count: number;
  bucket: AgingBucket | null;
  buckets: {
    key: AgingBucket;
    label: string;
    title_count: number;
    remaining_cents: string;
  }[];
}
export interface CustomerStatement {
  customer: {
    id: number;
    source_system: string;
    external_customer_id: string;
    name: string;
    email: string;
  };
  generated_at: string;
  business_now: string;
  business_date: string;
  titles: Page<Receivable>;
  payments: Page<
    Payment & {
      receivable_id: number;
      source_system: string;
      external_receivable_id: string;
    }
  >;
  totals: {
    amount_cents: string;
    paid_cents: string;
    remaining_cents: string;
    open_cents: string;
    canceled_remaining_cents: string;
    title_count: number;
    received_cents: string;
    paid_count: number;
  };
  received_from: string | null;
  received_to: string | null;
}
