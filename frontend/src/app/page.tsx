"use client";
import { useEffect, useState } from "react";
import { api, ApiError, errorMessage } from "@/lib/api";
import type { Session } from "@/lib/types";
import { Loading } from "@/components/ui";
import { Brand } from "@/components/brand";
import { Login } from "@/features/login";
import { Workspace } from "@/features/workspace";

export default function Home() {
  const [session, setSession] = useState<Session | null>(null);
  const [loading, setLoading] = useState(true);
  const [notice, setNotice] = useState("");
  useEffect(() => {
    api<Session>("/auth/session")
      .then(setSession)
      .catch((failure) => {
        if (!(failure instanceof ApiError && failure.status === 401))
          setNotice(errorMessage(failure));
      })
      .finally(() => setLoading(false));
    function expired() {
      setSession(null);
      setNotice("Sessão expirada. Entre novamente.");
    }
    window.addEventListener("cf-session-expired", expired);
    return () => window.removeEventListener("cf-session-expired", expired);
  }, []);
  if (loading)
    return (
      <div className="initial-loading">
        <Brand />
        <Loading />
      </div>
    );
  if (!session)
    return (
      <Login
        notice={notice}
        onLogin={(value) => {
          setNotice("");
          setSession(value);
        }}
      />
    );
  return (
    <Workspace
      session={session}
      onLogout={() => {
        setSession(null);
        setNotice("");
      }}
    />
  );
}
