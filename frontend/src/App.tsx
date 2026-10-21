import { Navigate, Route, Routes } from "react-router-dom";

import { RequireAuth } from "./components/RequireAuth";
import { SessionGate } from "./components/SessionGate";
import { LoginPage } from "./pages/LoginPage";
import { NotificationsPage } from "./pages/NotificationsPage";
import { RegisterPage } from "./pages/RegisterPage";
import { TasksPage } from "./pages/TasksPage";

export default function App() {
  return (
    <SessionGate>
      <Routes>
        <Route path="/login" element={<LoginPage />} />
        <Route path="/register" element={<RegisterPage />} />
        <Route element={<RequireAuth />}>
          <Route path="/" element={<TasksPage />} />
          <Route path="/notifications" element={<NotificationsPage />} />
        </Route>
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </SessionGate>
  );
}
