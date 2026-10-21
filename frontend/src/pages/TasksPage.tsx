import { useEffect, useState, type FormEvent } from "react";

import {
  ApiError,
  assignTask,
  createTask,
  deleteTask,
  listTasks,
  transferTask,
  updateTask,
  type Task,
  type TaskStatus,
} from "../api/client";
import { Shell } from "../components/Shell";
import { useAppSelector } from "../store/hooks";

const statusLabels: Record<TaskStatus, string> = {
  todo: "To do",
  in_progress: "In progress",
  done: "Done",
};

export function TasksPage() {
  const user = useAppSelector((state) => state.auth.user);
  const [tasks, setTasks] = useState<Task[]>([]);
  const [title, setTitle] = useState("");
  const [description, setDescription] = useState("");
  const [emails, setEmails] = useState<Record<string, string>>({});
  const [owners, setOwners] = useState<Record<string, string>>({});
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);

  async function load() {
    try {
      setTasks(await listTasks());
    } catch (caught) {
      setError(caught instanceof ApiError ? caught.message : "Could not load tasks");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    void load();
  }, []);

  async function onCreate(event: FormEvent) {
    event.preventDefault();
    setError("");
    try {
      await createTask(title, description);
      setTitle("");
      setDescription("");
      await load();
    } catch (caught) {
      setError(caught instanceof ApiError ? caught.message : "Could not create the task");
    }
  }

  async function onStatus(task: Task, status: TaskStatus) {
    setError("");
    try {
      await updateTask(task.id, { status, version: task.version });
      await load();
    } catch (caught) {
      setError(caught instanceof ApiError ? caught.message : "Could not update the task");
      await load();
    }
  }

  async function onAssign(task: Task) {
    const email = (emails[task.id] ?? "").trim();
    if (!email) {
      return;
    }
    setError("");
    try {
      await assignTask(task.id, email, task.version);
      setEmails((current) => ({ ...current, [task.id]: "" }));
      await load();
    } catch (caught) {
      setError(caught instanceof ApiError ? caught.message : "Could not assign the task");
      await load();
    }
  }

  async function onTransfer(task: Task) {
    const email = (owners[task.id] ?? "").trim();
    if (!email) {
      return;
    }
    setError("");
    try {
      await transferTask(task.id, email, task.version);
      setOwners((current) => ({ ...current, [task.id]: "" }));
      await load();
    } catch (caught) {
      setError(caught instanceof ApiError ? caught.message : "Could not transfer the task");
      await load();
    }
  }

  async function onDelete(task: Task) {
    setError("");
    try {
      await deleteTask(task.id);
      await load();
    } catch (caught) {
      setError(caught instanceof ApiError ? caught.message : "Could not delete the task");
    }
  }

  return (
    <Shell>
      <form className="mb-8 space-y-3 rounded-lg border border-stone-200 bg-white p-4" onSubmit={onCreate}>
        <label className="block text-sm font-medium">
          Title
          <input className="mt-1 w-full rounded-md border border-stone-300 px-3 py-2" value={title} onChange={(event) => setTitle(event.target.value)} required maxLength={200} />
        </label>
        <label className="block text-sm font-medium">
          Description
          <textarea className="mt-1 w-full rounded-md border border-stone-300 px-3 py-2" rows={2} value={description} onChange={(event) => setDescription(event.target.value)} maxLength={5000} />
        </label>
        <button className="rounded-md bg-stone-900 px-4 py-2 text-sm text-white" type="submit">
          Add task
        </button>
      </form>
      {error ? <p className="mb-4 text-sm text-red-700">{error}</p> : null}
      {loading ? <p className="text-sm text-stone-600">Loading…</p> : null}
      <ul className="space-y-3">
        {tasks.map((task) => {
          const mine = user?.id === task.owner_id;
          return (
            <li key={task.id} className="rounded-lg border border-stone-200 bg-white p-4">
              <div className="flex items-start justify-between gap-3">
                <div>
                  <p className="font-medium">{task.title}</p>
                  {task.description ? <p className="mt-1 text-sm text-stone-600">{task.description}</p> : null}
                  <p className="mt-1 text-xs text-stone-500">
                    {mine ? "Owner" : "Assigned to you"}
                    {task.assignee_email ? ` · ${task.assignee_email}` : ""}
                  </p>
                </div>
                <select
                  className="rounded-md border border-stone-300 px-2 py-1 text-sm"
                  value={task.status}
                  onChange={(event) => void onStatus(task, event.target.value as TaskStatus)}
                >
                  {Object.entries(statusLabels).map(([value, label]) => (
                    <option key={value} value={value}>
                      {label}
                    </option>
                  ))}
                </select>
              </div>
              {mine ? (
                <div className="mt-3 space-y-2">
                  <p className="text-xs text-stone-500">
                    Assignment waits until that person's account has reached the task service. A brand new account can take a moment.
                  </p>
                  <div className="flex gap-2">
                    <input
                      className="flex-1 rounded-md border border-stone-300 px-3 py-2 text-sm"
                      placeholder="Assignee email"
                      value={emails[task.id] ?? ""}
                      onChange={(event) => setEmails((current) => ({ ...current, [task.id]: event.target.value }))}
                    />
                    <button className="rounded-md border border-stone-300 px-3 py-2 text-sm" type="button" onClick={() => void onAssign(task)}>
                      Assign
                    </button>
                    <button className="rounded-md border border-stone-300 px-3 py-2 text-sm" type="button" onClick={() => void onDelete(task)}>
                      Delete
                    </button>
                  </div>
                  <div className="flex gap-2">
                    <input
                      className="flex-1 rounded-md border border-stone-300 px-3 py-2 text-sm"
                      placeholder="New owner email"
                      value={owners[task.id] ?? ""}
                      onChange={(event) => setOwners((current) => ({ ...current, [task.id]: event.target.value }))}
                    />
                    <button className="rounded-md border border-stone-300 px-3 py-2 text-sm" type="button" onClick={() => void onTransfer(task)}>
                      Transfer
                    </button>
                  </div>
                </div>
              ) : null}
            </li>
          );
        })}
      </ul>
    </Shell>
  );
}
