"use client";
import { useEffect, useState, useSyncExternalStore } from "react";
import {
  acceptSession,
  api,
  ApiError,
  clearClientAccess,
  finishSessionCheck,
  getAccessSnapshot,
  getServerAccessSnapshot,
  isLocallyLoggedOut,
  refreshClientSession,
  subscribeAccess,
} from "@/lib/api";
import type { Session } from "@/lib/types";
import { clearAccountIntents } from "@/lib/payment-intent";
import { Loading } from "@/components/ui";
import { Brand } from "@/components/brand";
import { Login } from "@/features/login";
import { Workspace } from "@/features/workspace";

export default function Home() {
  const { session, ready } = useSyncExternalStore(
    subscribeAccess,
    getAccessSnapshot,
    getServerAccessSnapshot,
  );
  const [loggingOut, setLoggingOut] = useState(false);
  const [notice, setNotice] = useState("");
  useEffect(() => {
    let alive = true;
    const controller = new AbortController();
    const epoch = getAccessSnapshot().epoch;
    if (isLocallyLoggedOut()) finishSessionCheck();
    else
      api<Session>("/auth/session", { signal: controller.signal })
        .then((value) => {
          if (alive && getAccessSnapshot().epoch === epoch)
            acceptSession(value);
        })
        .catch((failure) => {
          if (
            alive &&
            getAccessSnapshot().epoch === epoch &&
            !(failure instanceof ApiError && failure.status === 401)
          )
            setNotice("Não foi possível consultar a sessão. Entre novamente.");
        })
        .finally(() => {
          if (alive) finishSessionCheck();
        });
    function expired() {
      setNotice("Sessão expirada. Entre novamente.");
    }
    function revalidate() {
      if (document.visibilityState === "visible") void refreshClientSession();
    }
    window.addEventListener("cf-session-expired", expired);
    window.addEventListener("focus", revalidate);
    document.addEventListener("visibilitychange", revalidate);
    return () => {
      alive = false;
      controller.abort();
      window.removeEventListener("cf-session-expired", expired);
      window.removeEventListener("focus", revalidate);
      document.removeEventListener("visibilitychange", revalidate);
    };
  }, []);
  async function logout() {
    if (!session || loggingOut) return;
    const csrf = session.csrf_token;
    clearClientAccess(true);
    clearAccountIntents(session.user.id);
    setNotice("");
    setLoggingOut(true);
    try {
      await api(
        "/auth/logout",
        { method: "POST", signal: AbortSignal.timeout(10_000) },
        csrf,
      );
    } catch (failure) {
      if (!(failure instanceof ApiError && failure.status === 401))
        setNotice(
          "O conteúdo local foi removido. Não foi possível confirmar o encerramento da sessão no servidor.",
        );
    } finally {
      setLoggingOut(false);
    }
  }
  if (!ready || loggingOut)
    return (
      <div className="initial-loading">
        <Brand />
        <Loading />
        {loggingOut && <p role="status">Encerrando o acesso…</p>}
      </div>
    );
  if (!session)
    return (
      <Login
        notice={notice}
        onLogin={(value) => {
          setNotice("");
          acceptSession(value, true);
        }}
      />
    );
  return (
    <Workspace
      key={`${session.user.id}:${session.user.role}`}
      session={session}
      onLogout={() => void logout()}
    />
  );
}
