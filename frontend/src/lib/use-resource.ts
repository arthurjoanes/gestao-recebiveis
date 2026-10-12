"use client";
import { useEffect, useState, useSyncExternalStore } from "react";
import {
  api,
  errorMessage,
  getAccessSnapshot,
  getServerAccessSnapshot,
  subscribeAccess,
} from "./api";

export function useResource<T>(path: string, revision = 0) {
  const access = useSyncExternalStore(
    subscribeAccess,
    getAccessSnapshot,
    getServerAccessSnapshot,
  );
  const [state, setState] = useState<{
    data?: T;
    error?: string;
    path: string;
    revision: number;
    epoch: number;
  }>({ path: "", revision: -1, epoch: -1 });
  useEffect(() => {
    if (!getAccessSnapshot().session) return;
    let alive = true;
    const controller = new AbortController();
    api<T>(path, { signal: controller.signal })
      .then((data) => {
        if (alive) setState({ data, path, revision, epoch: access.epoch });
      })
      .catch((error) => {
        if (alive)
          setState({
            error: errorMessage(error),
            path,
            revision,
            epoch: access.epoch,
          });
      });
    return () => {
      alive = false;
      controller.abort();
    };
  }, [path, revision, access.epoch]);
  const current = !!access.session && state.epoch === access.epoch;
  const loading =
    !current || state.path !== path || state.revision !== revision;
  return {
    data: current && state.path === path ? state.data : undefined,
    error: loading ? undefined : state.error,
    loading,
  };
}
