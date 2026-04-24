import { useEffect, useState } from "react";

import { getEmotionReport, getParticipationReport } from "../api/client";
import type { EmotionReport, ParticipationRow } from "../types";

export default function EmotionDashboardPage() {
  const [emotionReport, setEmotionReport] = useState<EmotionReport | null>(null);
  const [participationRows, setParticipationRows] = useState<ParticipationRow[]>([]);
  const [loading, setLoading] = useState(false);
  const [errorText, setErrorText] = useState("");

  const loadReport = async () => {
    setLoading(true);
    setErrorText("");
    try {
      const [emotionData, participationData] = await Promise.all([
        getEmotionReport(),
        getParticipationReport()
      ]);
      setEmotionReport(emotionData);
      setParticipationRows(participationData);
    } catch {
      setErrorText("统计数据加载失败，请检查后端服务状态");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    void loadReport();
  }, []);

  const maxEmotion = Math.max(1, ...(emotionReport?.summary.map((item) => item.count) ?? [1]));

  return (
    <div className="page-grid">
      <section className="panel panel-glow">
        <h2>情绪统计</h2>
        <p className="panel-subtitle">展示考勤与合照识别中的面部情绪分类结果。</p>

        <button className="btn" type="button" onClick={loadReport} disabled={loading}>
          {loading ? "刷新中..." : "刷新统计"}
        </button>

        {errorText ? <p className="error-text">{errorText}</p> : null}

        <div className="bar-list">
          {(emotionReport?.summary ?? []).map((item) => (
            <div key={item.emotion} className="bar-row">
              <span>{item.emotion}</span>
              <div className="bar-track">
                <div
                  className="bar-fill"
                  style={{ width: `${Math.round((item.count / maxEmotion) * 100)}%` }}
                />
              </div>
              <strong>{item.count}</strong>
            </div>
          ))}
        </div>

        <h3>最近情绪事件</h3>
        <div className="table-shell">
          <table>
            <thead>
              <tr>
                <th>时间</th>
                <th>来源</th>
                <th>情绪</th>
              </tr>
            </thead>
            <tbody>
              {(emotionReport?.timeline ?? []).map((item, index) => (
                <tr key={`${item.timestamp}-${index}`}>
                  <td>{new Date(item.timestamp).toLocaleString()}</td>
                  <td>{item.source}</td>
                  <td>{item.emotion}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>

      <section className="panel">
        <h2>活动参与频次</h2>
        <p className="panel-subtitle">按学生维度统计参与班级活动次数。</p>
        <div className="table-shell">
          <table>
            <thead>
              <tr>
                <th>学号</th>
                <th>姓名</th>
                <th>班级</th>
                <th>参与次数</th>
              </tr>
            </thead>
            <tbody>
              {participationRows.map((row) => (
                <tr key={row.student_id}>
                  <td>{row.student_no}</td>
                  <td>{row.name}</td>
                  <td>{row.class_name}</td>
                  <td>{row.events_count}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>
    </div>
  );
}
