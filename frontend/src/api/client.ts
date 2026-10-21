import { clearSession, setAccessToken, setUser, type AuthUser } from "../store/authSlice";
import { store } from "../store/store";

export type TaskStatus = "todo" | "in_progress" | "done";

export type Task = {
  id: string;
  owner_id: string;
  assignee_id: string | null;
  assignee_email: string | null;
  title: string;
  description: string | null;
  status: TaskStatus;
  version: number;
  created_at: string;
  updated_at: string;
};

export type NotificationItem = {
  id: string;
  user_id: string;
  task_id: string | null;
  type: string;
  payload: { title?: string; status?: string };
  read_at: string | null;
  created_at: string;
};

type TokenResponse = {
  access_token: string;
  expires_in: number;
};

type RequestOptions = {
  method?: string;
  body?: unknown;
  retry?: boolean;
  idempotencyKey?: string;
};

export class ApiError extends Error {
  status: number;

  constructor(message: string, status: number) {
    super(message);
    this.name = "ApiError";
    this.status = status;
  }
}

let refreshInFlight: Promise<boolean> | null = null;

async function readError(response: Response): Promise<string> {
  try {
    const body = (await response.json()) as { detail?: unknown };
    if (typeof body.detail === "string") {
      return body.detail;
    }
  } catch {
    // The body was not JSON.
  }
  return `Request failed (${response.status})`;
}

async function performRefresh(): Promise<boolean> {
  const response = await fetch("/api/auth/refresh", { method: "POST", credentials: "include" });
  if (!response.ok) {
    store.dispatch(clearSession());
    return false;
  }
  const body = (await response.json()) as TokenResponse;
  store.dispatch(setAccessToken(body.access_token));
  return true;
}

function refreshSession(): Promise<boolean> {
  if (!refreshInFlight) {
    refreshInFlight = performRefresh().finally(() => {
      refreshInFlight = null;
    });
  }
  return refreshInFlight;
}

async function request<T>(path: string, options: RequestOptions = {}): Promise<T> {
  const headers = new Headers();
  if (options.body !== undefined) {
    headers.set("Content-Type", "application/json");
  }
  if (options.idempotencyKey) {
    headers.set("Idempotency-Key", options.idempotencyKey);
  }
  const accessToken = store.getState().auth.accessToken;
  if (accessToken) {
    headers.set("Authorization", `Bearer ${accessToken}`);
  }
  const response = await fetch(path, {
    method: options.method ?? "GET",
    headers,
    credentials: "include",
    body: options.body !== undefined ? JSON.stringify(options.body) : undefined,
  });
  if (response.status === 401 && options.retry !== false && path !== "/api/auth/refresh") {
    const refreshed = await refreshSession();
    if (refreshed) {
      return request<T>(path, { ...options, retry: false });
    }
    throw new ApiError("Session expired", 401);
  }
  if (!response.ok) {
    throw new ApiError(await readError(response), response.status);
  }
  if (response.status === 204) {
    return undefined as T;
  }
  return (await response.json()) as T;
}

async function loadCurrentUser(): Promise<void> {
  const user = await request<AuthUser>("/api/auth/me");
  store.dispatch(setUser(user));
}

async function startSession(path: "/api/auth/login" | "/api/auth/register", body: unknown): Promise<void> {
  const tokens = await request<TokenResponse>(path, { method: "POST", body, retry: false });
  store.dispatch(setAccessToken(tokens.access_token));
  try {
    await loadCurrentUser();
  } catch (error) {
    store.dispatch(clearSession());
    throw error;
  }
}

export async function restoreSession(): Promise<boolean> {
  if (store.getState().auth.accessToken) {
    return true;
  }
  const refreshed = await refreshSession();
  if (!refreshed) {
    return false;
  }
  try {
    await loadCurrentUser();
  } catch {
    store.dispatch(clearSession());
    return false;
  }
  return true;
}

export function login(email: string, password: string): Promise<void> {
  return startSession("/api/auth/login", { email, password });
}

export function register(name: string, email: string, password: string): Promise<void> {
  return startSession("/api/auth/register", { name, email, password });
}

export async function logout(): Promise<void> {
  try {
    await fetch("/api/auth/logout", { method: "POST", credentials: "include" });
  } finally {
    store.dispatch(clearSession());
  }
}

export function lookupUser(email: string): Promise<AuthUser> {
  return request<AuthUser>(`/api/auth/users?email=${encodeURIComponent(email)}`);
}

export function listTasks(): Promise<Task[]> {
  return request<Task[]>("/api/tasks");
}

export function createTask(title: string, description: string): Promise<Task> {
  return request<Task>("/api/tasks", {
    method: "POST",
    body: { title, description: description || null },
    idempotencyKey: crypto.randomUUID(),
  });
}

export function updateTask(
  id: string,
  changes: { status?: TaskStatus; title?: string; version: number },
): Promise<Task> {
  return request<Task>(`/api/tasks/${id}`, { method: "PATCH", body: changes });
}

export function assignTask(id: string, assigneeEmail: string, version: number): Promise<Task> {
  return request<Task>(`/api/tasks/${id}/assign`, {
    method: "POST",
    body: { assignee_email: assigneeEmail, version },
    idempotencyKey: crypto.randomUUID(),
  });
}

export function transferTask(id: string, newOwnerEmail: string, version: number): Promise<Task> {
  return request<Task>(`/api/tasks/${id}/transfer`, {
    method: "POST",
    body: { new_owner_email: newOwnerEmail, version },
    idempotencyKey: crypto.randomUUID(),
  });
}

export function deleteTask(id: string): Promise<void> {
  return request<void>(`/api/tasks/${id}`, { method: "DELETE" });
}

export function listNotifications(): Promise<NotificationItem[]> {
  return request<NotificationItem[]>("/api/notifications");
}

export function markNotificationRead(id: string): Promise<NotificationItem> {
  return request<NotificationItem>(`/api/notifications/${id}/read`, { method: "POST" });
}
