"use client";
import { useEffect, useState } from "react";
import { api, errorMessage } from "./api";

export function useResource<T>(path: string, revision = 0) {
  const [state, setState] = useState<{
    data?: T;
    error?: string;
    path: string;
    revision: number;
  }>({ path: "", revision: -1 });
  useEffect(() => {
    let alive = true;
    api<T>(path)
      .then((data) => {
        if (alive) setState({ data, path, revision });
      })
      .catch((error) => {
        if (alive) setState({ error: errorMessage(error), path, revision });
      });
    return () => {
      alive = false;
    };
  }, [path, revision]);
  const loading = state.path !== path || state.revision !== revision;
  return {
    data: state.path === path ? state.data : undefined,
    error: loading ? undefined : state.error,
    loading,
  };
}
