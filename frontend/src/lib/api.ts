import type { Session } from "./types";

type Access = { epoch: number; session: Session | null; ready: boolean };
const serverAccess: Access = { epoch: 0, session: null, ready: false };
let browserAccess = serverAccess;
const accessListeners = new Set<() => void>();
const LOCAL_LOGOUT = "gr.local-logout.v1";
let loggedOutLocally = false;
let sessionRefresh: { epoch: number; promise: Promise<void> } | undefined;

export function getAccessSnapshot(): Access {
  return typeof window === "undefined" ? serverAccess : browserAccess;
}

export function getServerAccessSnapshot(): Access {
  return serverAccess;
}

export function subscribeAccess(listener: () => void): () => void {
  accessListeners.add(listener);
  return () => accessListeners.delete(listener);
}

export function isLocallyLoggedOut(): boolean {
  if (typeof window === "undefined") return false;
  try {
    return loggedOutLocally || sessionStorage.getItem(LOCAL_LOGOUT) === "1";
  } catch {
    return loggedOutLocally;
  }
}

function publishAccess(session: Session | null, changed: boolean) {
  if (typeof window === "undefined") return;
  browserAccess = {
    epoch: browserAccess.epoch + (changed ? 1 : 0),
    session,
    ready: true,
  };
  accessListeners.forEach((listener) => listener());
}

export function finishSessionCheck() {
  publishAccess(getAccessSnapshot().session, false);
}

export function acceptSession(session: Session, explicitLogin = false) {
  if (typeof window === "undefined") return;
  if (explicitLogin) {
    loggedOutLocally = false;
    try {
      sessionStorage.removeItem(LOCAL_LOGOUT);
    } catch {
      // The memory guard still protects this page when storage is unavailable.
    }
  } else if (isLocallyLoggedOut()) return;
  const previous = browserAccess.session;
  publishAccess(
    session,
    explicitLogin ||
      previous?.user.id !== session.user.id ||
      previous?.user.role !== session.user.role ||
      previous?.csrf_token !== session.csrf_token,
  );
}

export function clearClientAccess(localLogout = false) {
  if (typeof window === "undefined") return;
  if (localLogout) {
    loggedOutLocally = true;
    try {
      sessionStorage.setItem(LOCAL_LOGOUT, "1");
    } catch {
      // Logout must remain possible even if browser storage is unavailable.
    }
  }
  publishAccess(null, true);
}

function staleAccess(epoch: number) {
  return typeof window !== "undefined" && epoch !== browserAccess.epoch;
}

function accessChanged() {
  return new ApiError(
    0,
    "access_changed",
    "O acesso foi atualizado. Confira a sessão e tente novamente.",
  );
}

export function refreshClientSession(): Promise<void> {
  const access = getAccessSnapshot();
  if (!access.session || isLocallyLoggedOut()) return Promise.resolve();
  if (sessionRefresh?.epoch === access.epoch) return sessionRefresh.promise;
  const promise = api<Session>("/auth/session")
    .then((session) => {
      if (!staleAccess(access.epoch)) acceptSession(session);
    })
    .catch(() => {
      // A 401 clears access in api(); network failures cannot confirm revocation.
    })
    .finally(() => {
      if (sessionRefresh?.promise === promise) sessionRefresh = undefined;
    });
  sessionRefresh = { epoch: access.epoch, promise };
  return promise;
}

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
  const epoch = getAccessSnapshot().epoch;
  const timeout = AbortSignal.timeout(30_000);
  const signal = options.signal
    ? AbortSignal.any([options.signal, timeout])
    : timeout;
  function connectionFailure() {
    if (staleAccess(epoch)) return accessChanged();
    return timeout.aborted || signal.reason?.name === "TimeoutError"
      ? new ApiError(
          0,
          "timeout",
          "Não recebemos a resposta a tempo. Tente novamente.",
        )
      : new ApiError(0, "network", "Falha na conexão. Tente novamente.");
  }
  const headers = new Headers(options.headers);
  if (options.body && !(options.body instanceof FormData))
    headers.set("Content-Type", "application/json");
  if (csrf) headers.set("X-CSRF-Token", csrf);
  let response: Response;
  try {
    const readV2 =
      (!options.method || options.method === "GET") &&
      /^\/(?:receivables(?:\/\d+)?|reports\/aging|customers\/\d+\/statement)(?:\?|$)/.test(
        path,
      );
    response = await fetch(`/api/${readV2 ? "v2" : "v1"}${path}`, {
      ...options,
      headers,
      credentials: "same-origin",
      cache: "no-store",
      signal,
    });
  } catch {
    throw connectionFailure();
  }
  if (staleAccess(epoch)) throw accessChanged();
  if (
    response.status === 401 &&
    path !== "/auth/login" &&
    path !== "/auth/logout" &&
    getAccessSnapshot().session
  ) {
    clearClientAccess();
    window.dispatchEvent(new Event("cf-session-expired"));
  }
  let body;
  if (response.status !== 204) {
    try {
      body = await response.json();
    } catch (failure) {
      if (signal.aborted) throw connectionFailure();
      if (staleAccess(epoch)) throw accessChanged();
      if (response.ok)
        throw failure instanceof SyntaxError
          ? new ApiError(
              response.status,
              "invalid_response",
              "Recebemos uma resposta inválida. Tente novamente.",
            )
          : connectionFailure();
    }
  }
  // Session expiry above belongs to this request; other late replies are discarded.
  if (staleAccess(epoch) && response.status !== 401) throw accessChanged();
  if (!response.ok) {
    if (response.status === 403 && !path.startsWith("/auth/"))
      await refreshClientSession();
    if (staleAccess(epoch) && response.status !== 401) throw accessChanged();
    throw new ApiError(
      response.status,
      body?.code ?? "request_failed",
      body?.message ?? "Falha na operação. Tente novamente.",
    );
  }
  return body as T;
}

export function query(
  params: Record<string, string | number | undefined>,
): string {
  const values = new URLSearchParams();
  for (const [key, value] of Object.entries(params))
    if (value !== "" && value !== undefined) values.set(key, String(value));
  return values.toString();
}

export function errorMessage(error: unknown): string {
  return error instanceof Error
    ? error.message
    : "Erro inesperado. Tente novamente.";
}
