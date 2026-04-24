import { useState } from "react";

import AttendancePage from "./pages/AttendancePage";
import EmotionDashboardPage from "./pages/EmotionDashboardPage";
import GroupPhotoPage from "./pages/GroupPhotoPage";

type TabKey = "attendance" | "group-photo" | "dashboard";

const TAB_ITEMS: Array<{ key: TabKey; label: string }> = [
  { key: "attendance", label: "基础考勤" },
  { key: "group-photo", label: "合照识别" },
  { key: "dashboard", label: "情绪与报表" }
];

export default function App() {
  const [activeTab, setActiveTab] = useState<TabKey>("attendance");

  return (
    <div className="app-shell">
      <header className="hero">
        <p className="hero-eyebrow">Torch + YOLOv11 + FastAPI + React</p>
        <h1>内容安全班级考勤系统</h1>
        <p>
          集成活体检测、人脸识别、合照识别与情绪分析，支持教学场景下的自动化考勤与活动参与统计。
        </p>
      </header>

      <nav className="tabs">
        {TAB_ITEMS.map((tab) => (
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
        {activeTab === "attendance" ? <AttendancePage /> : null}
        {activeTab === "group-photo" ? <GroupPhotoPage /> : null}
        {activeTab === "dashboard" ? <EmotionDashboardPage /> : null}
      </main>
    </div>
  );
}
