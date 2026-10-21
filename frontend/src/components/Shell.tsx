import type { ReactNode } from "react";
import { Link } from "react-router-dom";

import { logout } from "../api/client";
import { useAppSelector } from "../store/hooks";

export function Shell({ children }: { children: ReactNode }) {
  const user = useAppSelector((state) => state.auth.user);
  return (
    <div className="mx-auto min-h-screen max-w-3xl px-4 py-8">
      <header className="mb-8 flex items-start justify-between gap-4">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">Tasks</h1>
          <p className="mt-1 text-sm text-stone-600">{user?.name}</p>
          <nav className="mt-2 flex gap-4 text-sm">
            <Link className="underline" to="/">
              Tasks
            </Link>
            <Link className="underline" to="/notifications">
              Notifications
            </Link>
          </nav>
        </div>
        <button
          className="rounded-md border border-stone-300 bg-white px-3 py-2 text-sm"
          type="button"
          onClick={() => void logout()}
        >
          Log out
        </button>
      </header>
      {children}
    </div>
  );
}
