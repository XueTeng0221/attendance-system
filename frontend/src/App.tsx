import { useEffect, useMemo, useState } from "react";

import { fetchMe, registerUnauthorizedHandler } from "./api/client";
import { clearAuth, getCachedUser, getToken, setCachedUser } from "./auth";
import AttendancePage from "./pages/AttendancePage";
import EmotionDashboardPage from "./pages/EmotionDashboardPage";
import GroupPhotoPage from "./pages/GroupPhotoPage";
import LoginPage from "./pages/LoginPage";
import type { CurrentUser } from "./types";

type TabKey = "attendance" | "group-photo" | "dashboard";

const ALL_TABS: Array<{ key: TabKey; label: string }> = [
  { key: "attendance", label: "基础考勤" },
  { key: "group-photo", label: "合照识别" },
  { key: "dashboard", label: "情绪与报表" }
];

export default function App() {
  const [user, setUser] = useState<CurrentUser | null>(getCachedUser());
  const [bootstrapping, setBootstrapping] = useState<boolean>(Boolean(getToken()));
  const [activeTab, setActiveTab] = useState<TabKey>("attendance");

  const tabs = useMemo<Array<{ key: TabKey; label: string }>>(() => {
    if (!user) return ALL_TABS;
    if (user.role === "student") return [{ key: "attendance", label: "基础考勤" }];
    return ALL_TABS;
  }, [user]);

  useEffect(() => {
    registerUnauthorizedHandler(() => {
      setUser(null);
    });
  }, []);

  useEffect(() => {
    const token = getToken();
    if (!token) {
      setBootstrapping(false);
      return;
    }
    let cancelled = false;
    (async () => {
      try {
        const me = await fetchMe();
        if (!cancelled) {
          setUser(me);
          setCachedUser(me);
        }
      } catch {
        if (!cancelled) {
          clearAuth();
          setUser(null);
        }
      } finally {
        if (!cancelled) {
          setBootstrapping(false);
        }
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    if (user && !tabs.some((tab) => tab.key === activeTab)) {
      setActiveTab(tabs[0]?.key ?? "attendance");
    }
  }, [tabs, activeTab, user]);

  const handleLogout = () => {
    clearAuth();
    setUser(null);
    setActiveTab("attendance");
  };

  if (bootstrapping) {
    return (
      <div className="app-shell">
        <p className="status-chip">登录态校验中...</p>
      </div>
    );
  }

  if (!user) {
    return <LoginPage onLoggedIn={setUser} />;
  }

  return (
    <div className="app-shell">
      <header className="hero">
        <div className="hero-top">
          <div>
            <p className="hero-eyebrow">Torch + YOLOv11 + FastAPI + React</p>
            <h1>内容安全班级考勤系统</h1>
            <p>
              集成活体检测、人脸识别、合照识别与情绪分析，支持教学场景下的自动化考勤与活动参与统计。
            </p>
          </div>
          <div className="user-chip">
            <span className="user-chip-role">{user.role === "teacher" ? "教师" : "学生"}</span>
            <span className="user-chip-name">{user.username}</span>
            <button className="btn btn-ghost" type="button" onClick={handleLogout}>
              退出登录
            </button>
          </div>
        </div>
      </header>

      <nav className="tabs">
        {tabs.map((tab) => (
          <button
            key={tab.key}
            type="button"
            className={`tab-btn ${activeTab === tab.key ? "tab-btn-active" : ""}`}
            onClick={() => setActiveTab(tab.key)}
          >
            {tab.label}
          </button>
        ))}
      </nav>

      <main>
        {activeTab === "attendance" ? <AttendancePage user={user} /> : null}
        {activeTab === "group-photo" && user.role === "teacher" ? <GroupPhotoPage /> : null}
        {activeTab === "dashboard" && user.role === "teacher" ? <EmotionDashboardPage /> : null}
      </main>
    </div>
  );
}
