import { useState, type FormEvent } from "react";
import { Link, useNavigate } from "react-router-dom";

import { ApiError, login } from "../api/client";

export function LoginPage() {
  const navigate = useNavigate();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");

  async function onSubmit(event: FormEvent) {
    event.preventDefault();
    setError("");
    try {
      await login(email, password);
      navigate("/");
    } catch (caught) {
      setError(caught instanceof ApiError ? caught.message : "Could not log in");
    }
  }

  return (
    <form className="mx-auto mt-16 max-w-sm space-y-3 rounded-lg border border-stone-200 bg-white p-6" onSubmit={onSubmit}>
      <h1 className="text-xl font-semibold">Log in</h1>
      <label className="block text-sm">
        Email
        <input className="mt-1 w-full rounded-md border border-stone-300 px-3 py-2" type="email" value={email} onChange={(event) => setEmail(event.target.value)} required />
      </label>
      <label className="block text-sm">
        Password
        <input className="mt-1 w-full rounded-md border border-stone-300 px-3 py-2" type="password" value={password} onChange={(event) => setPassword(event.target.value)} required />
      </label>
      {error ? <p className="text-sm text-red-700">{error}</p> : null}
      <button className="rounded-md bg-stone-900 px-4 py-2 text-sm text-white" type="submit">
        Log in
      </button>
      <p className="text-sm">
        <Link className="underline" to="/register">
          Create an account
        </Link>
      </p>
    </form>
  );
}
