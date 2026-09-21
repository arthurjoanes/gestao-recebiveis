export class ApiError extends Error {
  constructor(
    public status: number,
    public code: string,
    message: string,
  ) {
    super(message);
  }
}

export async function api<T>(
  path: string,
  options: RequestInit = {},
  csrf?: string,
): Promise<T> {
  const headers = new Headers(options.headers);
  if (options.body && !(options.body instanceof FormData))
    headers.set("Content-Type", "application/json");
  if (csrf) headers.set("X-CSRF-Token", csrf);
  let response: Response;
  try {
    response = await fetch(`/api/v1${path}`, {
      ...options,
      headers,
      credentials: "same-origin",
      cache: "no-store",
    });
  } catch {
    throw new ApiError(0, "network", "Falha na conexão. Tente novamente.");
  }
  const body = await response.json().catch(() => null);
  if (!response.ok) {
    if (
      response.status === 401 &&
      path !== "/auth/login" &&
      path !== "/auth/session"
    )
      window.dispatchEvent(new Event("cf-session-expired"));
    throw new ApiError(
      response.status,
      body?.code ?? "request_failed",
      body?.message ?? "Falha na operação. Tente novamente.",
    );
  }
  return body as T;
}

export function query(params: Record<string, string | number>): string {
  const values = new URLSearchParams();
  for (const [key, value] of Object.entries(params))
    if (value !== "") values.set(key, String(value));
  return values.toString();
}

export function errorMessage(error: unknown): string {
  return error instanceof Error
    ? error.message
    : "Erro inesperado. Tente novamente.";
}
