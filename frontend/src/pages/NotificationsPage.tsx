import { useEffect, useState } from "react";

import { ApiError, listNotifications, markNotificationRead, type NotificationItem } from "../api/client";
import { Shell } from "../components/Shell";

export function NotificationsPage() {
  const [items, setItems] = useState<NotificationItem[]>([]);
  const [error, setError] = useState("");

  async function load() {
    try {
      setItems(await listNotifications());
      setError("");
    } catch (caught) {
      setError(caught instanceof ApiError ? caught.message : "Could not load notifications");
    }
  }

  useEffect(() => {
    void load();
  }, []);

  async function onRead(item: NotificationItem) {
    try {
      await markNotificationRead(item.id);
      await load();
    } catch (caught) {
      setError(caught instanceof ApiError ? caught.message : "Could not update the notification");
    }
  }

  return (
    <Shell>
      <p className="mb-4 text-sm text-stone-600">
        A notification appears after the task service has published the event and this service has stored it. A new assignment can lag behind the task save.
      </p>
      {error ? <p className="mb-4 text-sm text-red-700">{error}</p> : null}
      {items.length === 0 ? <p className="text-sm text-stone-600">No notifications yet.</p> : null}
      <ul className="space-y-3">
        {items.map((item) => (
          <li key={item.id} className="rounded-lg border border-stone-200 bg-white p-4 text-sm">
            <p className="font-medium">{item.type}</p>
            <p className="text-stone-600">{item.payload.title ?? "Task"}</p>
            {item.read_at ? (
              <p className="mt-2 text-xs text-stone-500">Read</p>
            ) : (
              <button className="mt-2 underline" type="button" onClick={() => void onRead(item)}>
                Mark read
              </button>
            )}
          </li>
        ))}
      </ul>
    </Shell>
  );
}
