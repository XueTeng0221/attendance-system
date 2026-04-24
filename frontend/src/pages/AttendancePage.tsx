import { useEffect, useMemo, useRef, useState } from "react";
import type { FormEvent } from "react";

import { checkAttendance, listStudents, registerStudent } from "../api/client";
import type { AttendanceResponse, Student } from "../types";

function toReadableScore(score: number): string {
  return `${(score * 100).toFixed(2)}%`;
}

export default function AttendancePage() {
  const videoRef = useRef<HTMLVideoElement | null>(null);
  const [stream, setStream] = useState<MediaStream | null>(null);
  const [cameraError, setCameraError] = useState<string>("");
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<AttendanceResponse | null>(null);

  const [students, setStudents] = useState<Student[]>([]);
  const [registerError, setRegisterError] = useState<string>("");
  const [registerSuccess, setRegisterSuccess] = useState<string>("");
  const [registering, setRegistering] = useState(false);

  const [studentNo, setStudentNo] = useState("");
  const [name, setName] = useState("");
  const [className, setClassName] = useState("");
  const [imageFile, setImageFile] = useState<File | null>(null);

  useEffect(() => {
    const load = async () => {
      try {
        const data = await listStudents();
        setStudents(data);
      } catch {
        setStudents([]);
      }
    };
    void load();
  }, []);

  useEffect(() => {
    return () => {
      if (stream) {
        stream.getTracks().forEach((track) => track.stop());
      }
    };
  }, [stream]);

  const statusText = useMemo(() => {
    if (!result) {
      return "等待考勤";
    }
    return result.status === "success" ? "考勤成功" : "考勤失败";
  }, [result]);

  const startCamera = async () => {
    setCameraError("");
    try {
      const mediaStream = await navigator.mediaDevices.getUserMedia({ video: true, audio: false });
      if (videoRef.current) {
        videoRef.current.srcObject = mediaStream;
      }
      setStream(mediaStream);
    } catch {
      setCameraError("摄像头调用失败，请检查浏览器权限与设备状态");
    }
  };

  const captureFrame = async (): Promise<Blob> => {
    const video = videoRef.current;
    if (!video) {
      throw new Error("视频组件未初始化");
    }

    const canvas = document.createElement("canvas");
    canvas.width = video.videoWidth;
    canvas.height = video.videoHeight;

    const ctx = canvas.getContext("2d");
    if (!ctx) {
      throw new Error("Canvas 初始化失败");
    }

    ctx.drawImage(video, 0, 0, canvas.width, canvas.height);

    const blob = await new Promise<Blob | null>((resolve) => {
      canvas.toBlob((value) => resolve(value), "image/jpeg", 0.92);
    });

    if (!blob) {
      throw new Error("图像抓拍失败");
    }

    return blob;
  };

  const handleAttendance = async () => {
    setLoading(true);
    setResult(null);

    try {
      const blob = await captureFrame();
      const data = await checkAttendance(blob);
      setResult(data);
    } catch (error) {
      const message = error instanceof Error ? error.message : "识别请求失败，请稍后重试";
      setCameraError(message);
    } finally {
      setLoading(false);
    }
  };

  const handleRegister = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setRegisterError("");
    setRegisterSuccess("");

    if (!imageFile) {
      setRegisterError("请上传学生正面照后再注册");
      return;
    }

    setRegistering(true);
    try {
      const newStudent = await registerStudent({
        studentNo,
        name,
        className,
        imageFile
      });
      setStudents((prev) => [newStudent, ...prev]);
      setRegisterSuccess(`已成功注册：${newStudent.name}`);
      setStudentNo("");
      setName("");
      setClassName("");
      setImageFile(null);
    } catch (error) {
      const message = error instanceof Error ? error.message : "学生注册失败";
      setRegisterError(message);
    } finally {
      setRegistering(false);
    }
  };

  return (
    <div className="page-grid">
      <section className="panel panel-glow">
        <h2>实时考勤</h2>
        <p className="panel-subtitle">浏览器摄像头采集学生人脸，后端完成活体检测与库比对。</p>

        <div className="video-shell">
          <video ref={videoRef} autoPlay playsInline muted />
        </div>

        <div className="action-row">
          <button className="btn" onClick={startCamera} type="button">
            开启摄像头
          </button>
          <button className="btn btn-accent" onClick={handleAttendance} type="button" disabled={loading}>
            {loading ? "识别中..." : "抓拍并考勤"}
          </button>
        </div>

        <p className="status-chip">状态：{statusText}</p>
        {cameraError ? <p className="error-text">{cameraError}</p> : null}

        {result ? (
          <div className="result-card">
            <p>活体分数：{toReadableScore(result.liveness_score)}</p>
            <p>匹配置信度：{toReadableScore(result.confidence)}</p>
            <p>
              情绪：{result.emotion.emotion} ({toReadableScore(result.emotion.score)})
            </p>
            <p>时间：{new Date(result.attendance_time).toLocaleString()}</p>
            <p>
              学生：
              {result.student
                ? `${result.student.name} (${result.student.student_no}) - ${result.student.class_name}`
                : "未匹配"}
            </p>
            {result.reason ? <p>原因：{result.reason}</p> : null}
          </div>
        ) : null}
      </section>

      <section className="panel">
        <h2>学生人脸入库</h2>
        <p className="panel-subtitle">录入学生学号、班级及标准人脸照片，形成比对库。</p>
        <form className="form-grid" onSubmit={handleRegister}>
          <label>
            学号
            <input value={studentNo} onChange={(e) => setStudentNo(e.target.value)} required />
          </label>
          <label>
            姓名
            <input value={name} onChange={(e) => setName(e.target.value)} required />
          </label>
          <label>
            班级
            <input value={className} onChange={(e) => setClassName(e.target.value)} required />
          </label>
          <label>
            学生正面照
            <input
              type="file"
              accept="image/*"
              onChange={(e) => setImageFile(e.target.files?.[0] ?? null)}
              required
            />
          </label>
          <button className="btn btn-accent" type="submit" disabled={registering}>
            {registering ? "提交中..." : "注册学生"}
          </button>
        </form>
        {registerError ? <p className="error-text">{registerError}</p> : null}
        {registerSuccess ? <p className="success-text">{registerSuccess}</p> : null}

        <h3>人脸库学生列表</h3>
        <div className="table-shell">
          <table>
            <thead>
              <tr>
                <th>学号</th>
                <th>姓名</th>
                <th>班级</th>
              </tr>
            </thead>
            <tbody>
              {students.map((student) => (
                <tr key={student.id}>
                  <td>{student.student_no}</td>
                  <td>{student.name}</td>
                  <td>{student.class_name}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>
    </div>
  );
}
