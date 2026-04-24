import { useState } from "react";
import type { FormEvent } from "react";

import { recognizeGroupPhoto } from "../api/client";
import type { GroupPhotoResponse } from "../types";

function asPercent(score: number): string {
  return `${(score * 100).toFixed(2)}%`;
}

export default function GroupPhotoPage() {
  const [eventName, setEventName] = useState("");
  const [photo, setPhoto] = useState<File | null>(null);
  const [result, setResult] = useState<GroupPhotoResponse | null>(null);
  const [errorText, setErrorText] = useState("");
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setErrorText("");
    setResult(null);

    if (!photo) {
      setErrorText("请先上传合照");
      return;
    }

    setLoading(true);
    try {
      const response = await recognizeGroupPhoto({
        eventName: eventName || "未命名活动",
        imageFile: photo
      });
      setResult(response);
    } catch (error) {
      const message = error instanceof Error ? error.message : "合照识别失败，请稍后重试";
      setErrorText(message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="page-grid single-column">
      <section className="panel panel-glow">
        <h2>合照学生识别</h2>
        <p className="panel-subtitle">上传班级活动大合照，自动识别学生并生成参与频次数据。</p>

        <form className="form-grid" onSubmit={handleSubmit}>
          <label>
            活动名称
            <input
              placeholder="例如：春季运动会"
              value={eventName}
              onChange={(e) => setEventName(e.target.value)}
            />
          </label>

          <label>
            合照图片
            <input
              type="file"
              accept="image/*"
              required
              onChange={(e) => setPhoto(e.target.files?.[0] ?? null)}
            />
          </label>

          <button className="btn btn-accent" type="submit" disabled={loading}>
            {loading ? "识别中..." : "开始识别"}
          </button>
        </form>

        {errorText ? <p className="error-text">{errorText}</p> : null}

        {result ? (
          <div className="result-card">
            <p>活动：{result.event_name}</p>
            <p>检测到人脸：{result.detected_faces}</p>
            <p>匹配成功：{result.matched_students.length}</p>
            <p>未匹配：{result.unmatched_faces}</p>
            <p>处理耗时：{result.processing_time_ms} ms</p>

            <div className="table-shell">
              <table>
                <thead>
                  <tr>
                    <th>学号</th>
                    <th>姓名</th>
                    <th>班级</th>
                    <th>匹配置信度</th>
                    <th>情绪</th>
                  </tr>
                </thead>
                <tbody>
                  {result.matched_students.map((item) => (
                    <tr key={item.student_id}>
                      <td>{item.student_no}</td>
                      <td>{item.name}</td>
                      <td>{item.class_name}</td>
                      <td>{asPercent(item.confidence)}</td>
                      <td>
                        {item.emotion} ({asPercent(item.emotion_score)})
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        ) : null}
      </section>
    </div>
  );
}
