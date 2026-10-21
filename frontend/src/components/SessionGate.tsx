import { useEffect, useState, type ReactNode } from "react";

import { restoreSession } from "../api/client";

export function SessionGate({ children }: { children: ReactNode }) {
  const [ready, setReady] = useState(false);

  useEffect(() => {
    void restoreSession().finally(() => setReady(true));
  }, []);

  if (!ready) {
    return <p className="p-8 text-sm text-stone-600">Checking session…</p>;
  }
  return children;
}
