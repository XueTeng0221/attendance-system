import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import type { CSSProperties, FormEvent } from "react";

import { checkAttendance, detectAttendanceFace, importStudentsFromDirectory, listStudents, registerStudent } from "../api/client";
import type { AttendanceResponse, CurrentUser, FaceBox, Student, StudentBatchImportResponse } from "../types";

type CaptureMode = "manual" | "auto";

type Phase =
  | "idle"
  | "capturing"
  | "uploading"
  | "success"
  | "liveness-failed"
  | "match-failed"
  | "auto-stopped"
  | "error";

const AUTO_INTERVAL_MS = 1500;
const FRAME_COUNT = 3;
const FRAME_INTERVAL_MS = 200;
const MAX_AUTO_FAILURES = 8;
const FACE_DETECT_INTERVAL_MS = 1200;
const IMPORT_BATCH_SIZE = 10;

interface FaceOverlayBox {
  leftPct: number;
  topPct: number;
  widthPct: number;
  heightPct: number;
  confidence: number;
}

function chunkArray<T>(items: T[], size: number): T[][] {
  if (size <= 0) return [items];
  const chunks: T[][] = [];
  for (let i = 0; i < items.length; i += size) {
    chunks.push(items.slice(i, i + size));
  }
  return chunks;
}

function toReadableScore(score: number): string {
  return `${(score * 100).toFixed(2)}%`;
}

function phaseText(phase: Phase): string {
  switch (phase) {
    case "idle":
      return "等待采集";
    case "capturing":
      return "采集中";
    case "uploading":
      return "识别中";
    case "success":
      return "考勤成功";
    case "liveness-failed":
      return "活体未通过，请正对镜头";
    case "match-failed":
      return "未匹配到本人";
    case "auto-stopped":
      return "自动模式已停止";
    case "error":
      return "采集异常";
    default:
      return "";
  }
}

function phaseTone(phase: Phase): string {
  if (phase === "success") return "tone-success";
  if (phase === "liveness-failed" || phase === "match-failed" || phase === "error") return "tone-warn";
  if (phase === "uploading" || phase === "capturing") return "tone-active";
  return "";
}

interface AttendancePageProps {
  user: CurrentUser;
}

export default function AttendancePage({ user }: AttendancePageProps) {
  const isTeacher = user.role === "teacher";

  const videoRef = useRef<HTMLVideoElement | null>(null);
  const streamRef = useRef<MediaStream | null>(null);
  const autoTimerRef = useRef<number | null>(null);
  const faceDetectTimerRef = useRef<number | null>(null);
  const autoBusyRef = useRef<boolean>(false);
  const faceDetectBusyRef = useRef<boolean>(false);
  const failureCountRef = useRef<number>(0);
  const modeRef = useRef<CaptureMode>("manual");
  const directoryInputRef = useRef<HTMLInputElement | null>(null);

  const [streamReady, setStreamReady] = useState(false);
  const [cameraError, setCameraError] = useState<string>("");
  const [phase, setPhase] = useState<Phase>("idle");
  const [result, setResult] = useState<AttendanceResponse | null>(null);
  const [faceOverlayBox, setFaceOverlayBox] = useState<FaceOverlayBox | null>(null);
  const [mode, setMode] = useState<CaptureMode>("manual");
  const [autoRunning, setAutoRunning] = useState(false);

  // 教师端：学生入库
  const [students, setStudents] = useState<Student[]>([]);
  const [registerError, setRegisterError] = useState<string>("");
  const [registerSuccess, setRegisterSuccess] = useState<string>("");
  const [registering, setRegistering] = useState(false);
  const [studentNo, setStudentNo] = useState("");
  const [name, setName] = useState("");
  const [className, setClassName] = useState("");
  const [studentPassword, setStudentPassword] = useState("");
  const [imageFile, setImageFile] = useState<File | null>(null);
  const [batchFiles, setBatchFiles] = useState<File[]>([]);
  const [batchImporting, setBatchImporting] = useState(false);
  const [batchImportError, setBatchImportError] = useState("");
  const [batchImportResult, setBatchImportResult] = useState<StudentBatchImportResponse | null>(null);
  const [batchProcessedCount, setBatchProcessedCount] = useState(0);

  useEffect(() => {
    modeRef.current = mode;
  }, [mode]);

  useEffect(() => {
    if (!isTeacher) return;
    let cancelled = false;
    (async () => {
      try {
        const data = await listStudents();
        if (!cancelled) setStudents(data);
      } catch {
        if (!cancelled) setStudents([]);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [isTeacher]);

  useEffect(() => {
    return () => {
      if (autoTimerRef.current !== null) {
        window.clearInterval(autoTimerRef.current);
        autoTimerRef.current = null;
      }
      if (faceDetectTimerRef.current !== null) {
        window.clearInterval(faceDetectTimerRef.current);
        faceDetectTimerRef.current = null;
      }
      if (streamRef.current) {
        streamRef.current.getTracks().forEach((track) => track.stop());
        streamRef.current = null;
      }
    };
  }, []);

  useEffect(() => {
    if (!directoryInputRef.current) return;
    directoryInputRef.current.setAttribute("webkitdirectory", "");
    directoryInputRef.current.setAttribute("directory", "");
  }, []);

  const startCamera = async () => {
    setCameraError("");
    setFaceOverlayBox(null);
    try {
      const mediaStream = await navigator.mediaDevices.getUserMedia({ video: true, audio: false });
      if (videoRef.current) {
        videoRef.current.srcObject = mediaStream;
      }
      streamRef.current = mediaStream;
      setStreamReady(true);
    } catch {
      setCameraError("摄像头调用失败，请检查浏览器权限与设备状态");
      setStreamReady(false);
    }
  };

  const captureSingleFrame = useCallback(async (): Promise<{ blob: Blob; width: number; height: number }> => {
    const video = videoRef.current;
    if (!video || video.videoWidth === 0) {
      throw new Error("视频组件未就绪");
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
      canvas.toBlob((value) => resolve(value), "image/jpeg", 0.9);
    });
    if (!blob) {
      throw new Error("图像抓拍失败");
    }
    return { blob, width: canvas.width, height: canvas.height };
  }, []);

  const captureFrames = useCallback(async (count = FRAME_COUNT, intervalMs = FRAME_INTERVAL_MS): Promise<Blob[]> => {
    const blobs: Blob[] = [];
    for (let i = 0; i < count; i += 1) {
      const captured = await captureSingleFrame();
      blobs.push(captured.blob);
      if (i < count - 1) {
        await new Promise<void>((resolve) => window.setTimeout(resolve, intervalMs));
      }
    }
    return blobs;
  }, [captureSingleFrame]);

  const toOverlayBox = useCallback((box: FaceBox, imageWidth: number, imageHeight: number): FaceOverlayBox | null => {
    if (imageWidth <= 0 || imageHeight <= 0) return null;
    const left = Math.max(0, Math.min(imageWidth, box.x1));
    const top = Math.max(0, Math.min(imageHeight, box.y1));
    const right = Math.max(left, Math.min(imageWidth, box.x2));
    const bottom = Math.max(top, Math.min(imageHeight, box.y2));
    const width = right - left;
    const height = bottom - top;
    if (width <= 1 || height <= 1) return null;
    return {
      leftPct: (left / imageWidth) * 100,
      topPct: (top / imageHeight) * 100,
      widthPct: (width / imageWidth) * 100,
      heightPct: (height / imageHeight) * 100,
      confidence: box.confidence
    };
  }, []);

  const runFaceDetectOnce = useCallback(async () => {
    if (!streamReady || phase === "capturing" || phase === "uploading") return;
    if (faceDetectBusyRef.current) return;
    faceDetectBusyRef.current = true;
    try {
      const captured = await captureSingleFrame();
      const data = await detectAttendanceFace(captured.blob);
      if (!data.found || !data.box) {
        setFaceOverlayBox(null);
        return;
      }
      const imageWidth = data.image_width > 0 ? data.image_width : captured.width;
      const imageHeight = data.image_height > 0 ? data.image_height : captured.height;
      setFaceOverlayBox(toOverlayBox(data.box, imageWidth, imageHeight));
    } catch {
      setFaceOverlayBox(null);
    } finally {
      faceDetectBusyRef.current = false;
    }
  }, [captureSingleFrame, phase, streamReady, toOverlayBox]);

  useEffect(() => {
    if (faceDetectTimerRef.current !== null) {
      window.clearInterval(faceDetectTimerRef.current);
      faceDetectTimerRef.current = null;
    }
    faceDetectBusyRef.current = false;
    if (!streamReady) {
      setFaceOverlayBox(null);
      return;
    }
    const tick = () => {
      void runFaceDetectOnce();
    };
    void tick();
    faceDetectTimerRef.current = window.setInterval(tick, FACE_DETECT_INTERVAL_MS);
    return () => {
      if (faceDetectTimerRef.current !== null) {
        window.clearInterval(faceDetectTimerRef.current);
        faceDetectTimerRef.current = null;
      }
      faceDetectBusyRef.current = false;
    };
  }, [runFaceDetectOnce, streamReady]);

  const runAttendanceOnce = useCallback(
    async (isAuto: boolean) => {
      try {
        setPhase("capturing");
        const blobs = await captureFrames();
        setPhase("uploading");
        const data = await checkAttendance(blobs);
        setResult(data);

        if (data.status === "success") {
          setPhase("success");
          return "success" as const;
        }

        if (data.reason && data.reason.includes("匹配")) {
          setPhase("match-failed");
        } else {
          setPhase("liveness-failed");
        }
        return "fail" as const;
      } catch (error) {
        const message = error instanceof Error ? error.message : "识别请求失败";
        if (!isAuto) {
          setCameraError(message);
        }
        setPhase("error");
        return "fail" as const;
      }
    },
    [captureFrames]
  );

  const stopAuto = useCallback((finalPhase: Phase | null = null) => {
    if (autoTimerRef.current !== null) {
      window.clearInterval(autoTimerRef.current);
      autoTimerRef.current = null;
    }
    autoBusyRef.current = false;
    failureCountRef.current = 0;
    setAutoRunning(false);
    setMode("manual");
    if (finalPhase) {
      setPhase(finalPhase);
    }
  }, []);

  const handleManualCapture = async () => {
    if (!streamReady) {
      setCameraError("请先开启摄像头");
      return;
    }
    setCameraError("");
    setResult(null);
    await runAttendanceOnce(false);
  };

  const handleToggleAuto = () => {
    if (autoRunning) {
      stopAuto("auto-stopped");
      return;
    }
    if (!streamReady) {
      setCameraError("请先开启摄像头");
      return;
    }
    setCameraError("");
    setResult(null);
    setMode("auto");
    setAutoRunning(true);
    failureCountRef.current = 0;
    autoBusyRef.current = false;

    const tick = async () => {
      if (autoBusyRef.current) return;
      autoBusyRef.current = true;
      try {
        const outcome = await runAttendanceOnce(true);
        if (outcome === "success") {
          stopAuto("success");
          return;
        }
        failureCountRef.current += 1;
        if (failureCountRef.current >= MAX_AUTO_FAILURES) {
          stopAuto("auto-stopped");
        }
      } finally {
        autoBusyRef.current = false;
      }
    };

    void tick();
    autoTimerRef.current = window.setInterval(tick, AUTO_INTERVAL_MS);
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
        password: studentPassword || undefined,
        imageFile
      });
      setStudents((prev) => [newStudent, ...prev]);
      setRegisterSuccess(
        `已注册：${newStudent.name}（学生登录账号 ${newStudent.student_no}，密码默认为${
          studentPassword ? "您填写的值" : "学号"
        }）`
      );
      setStudentNo("");
      setName("");
      setClassName("");
      setStudentPassword("");
      setImageFile(null);
    } catch (error) {
      const detail =
        typeof error === "object" && error && "response" in error
          ? // eslint-disable-next-line @typescript-eslint/no-explicit-any
            ((error as any).response?.data?.detail as string | undefined)
          : undefined;
      setRegisterError(detail || (error instanceof Error ? error.message : "学生注册失败"));
    } finally {
      setRegistering(false);
    }
  };

  const handleBatchImport = async () => {
    setBatchImportError("");
    setBatchImportResult(null);
    setBatchProcessedCount(0);

    if (batchFiles.length === 0) {
      setBatchImportError("请先选择包含人脸图片的目录");
      return;
    }

    setBatchImporting(true);
    const chunks = chunkArray(batchFiles, IMPORT_BATCH_SIZE);
    const aggregated: StudentBatchImportResponse = {
      total: batchFiles.length,
      success_count: 0,
      failed_count: 0,
      items: []
    };
    const createdStudents: Student[] = [];
    let processedCount = 0;

    try {
      for (const chunk of chunks) {
        const data = await importStudentsFromDirectory(chunk);
        aggregated.success_count += data.success_count;
        aggregated.failed_count += data.failed_count;
        aggregated.items.push(...data.items);
        setBatchImportResult({ ...aggregated });

        createdStudents.push(
          ...data.items.map((item) => item.student).filter((student): student is Student => student !== null)
        );
        processedCount += chunk.length;
        setBatchProcessedCount(processedCount);
      }

      setStudents((prev) => {
        const existingNos = new Set(prev.map((item) => item.student_no));
        const dedup = createdStudents.filter((student) => !existingNos.has(student.student_no));
        return [...dedup, ...prev];
      });
    } catch (error) {
      if (aggregated.items.length > 0) {
        setBatchImportResult({ ...aggregated });
      }
      const detail =
        typeof error === "object" && error && "response" in error
          ? // eslint-disable-next-line @typescript-eslint/no-explicit-any
            ((error as any).response?.data?.detail as string | undefined)
          : undefined;
      const errorMessage = detail || (error instanceof Error ? error.message : "批量导入失败");
      setBatchImportError(`${errorMessage}（已完成 ${processedCount}/${batchFiles.length}）`);
    } finally {
      setBatchImporting(false);
    }
  };

  const livenessLine = useMemo(() => {
    if (!result) return null;
    const breakdown = result.liveness_breakdown;
    if (!breakdown) {
      return <p>活体分数：{toReadableScore(result.liveness_score)}</p>;
    }
    const fragments: string[] = [`总分 ${toReadableScore(result.liveness_score)}`];
    if (typeof breakdown.motion_raw === "number") {
      fragments.push(`运动 ${breakdown.motion_raw.toFixed(4)}`);
    }
    if (typeof breakdown.brightness_var === "number") {
      fragments.push(`亮度方差 ${breakdown.brightness_var.toFixed(4)}`);
    }
    if (typeof breakdown.moire === "number") {
      fragments.push(`摩尔纹 ${breakdown.moire.toFixed(2)}`);
    }
    if (typeof breakdown.frames === "number") {
      fragments.push(`帧数 ${breakdown.frames}`);
    }
    return <p>活体：{fragments.join(" / ")}</p>;
  }, [result]);

  const faceBoxStyle = useMemo<CSSProperties | null>(() => {
    if (!faceOverlayBox) return null;
    return {
      left: `${faceOverlayBox.leftPct}%`,
      top: `${faceOverlayBox.topPct}%`,
      width: `${faceOverlayBox.widthPct}%`,
      height: `${faceOverlayBox.heightPct}%`
    };
  }, [faceOverlayBox]);

  return (
    <div className={isTeacher ? "page-grid" : "page-grid single-column"}>
      <section className="panel panel-glow">
        <h2>实时考勤</h2>
        <p className="panel-subtitle">
          浏览器摄像头采集学生人脸，后端完成多帧活体校验、库匹配与情绪分析。
        </p>

        <div className="video-shell">
          <video ref={videoRef} autoPlay playsInline muted />
          {faceBoxStyle && faceOverlayBox ? (
            <div className="face-box" style={faceBoxStyle}>
              <span className="face-box-label">人脸 {(faceOverlayBox.confidence * 100).toFixed(0)}%</span>
            </div>
          ) : null}
        </div>

        <div className="action-row">
          <button className="btn" onClick={startCamera} type="button">
            {streamReady ? "重新开启" : "开启摄像头"}
          </button>
          <button
            className="btn btn-accent"
            onClick={handleManualCapture}
            type="button"
            disabled={autoRunning || phase === "capturing" || phase === "uploading"}
          >
            {phase === "capturing" || phase === "uploading" ? "识别中..." : "抓拍并考勤"}
          </button>
          <button
            className={`btn ${autoRunning ? "btn-danger" : ""}`}
            onClick={handleToggleAuto}
            type="button"
          >
            {autoRunning ? "停止自动模式" : "开启自动模式"}
          </button>
        </div>

        <p className={`status-chip ${phaseTone(phase)}`}>
          状态：{phaseText(phase)}
          {mode === "auto" && autoRunning ? "（自动）" : ""}
        </p>
        {streamReady ? <p className="panel-subtitle">人脸检测：{faceBoxStyle ? "已识别并框选" : "未检测到人脸"}</p> : null}
        {cameraError ? <p className="error-text">{cameraError}</p> : null}

        {result ? (
          <div className="result-card">
            {livenessLine}
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

      {isTeacher ? (
        <section className="panel">
          <h2>学生人脸入库</h2>
          <p className="panel-subtitle">
            录入学生学号、班级及标准人脸照片，并自动开通学生登录账号（用户名 = 学号）。
          </p>
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
              学生登录密码（可选，留空默认为学号）
              <input
                value={studentPassword}
                onChange={(e) => setStudentPassword(e.target.value)}
                type="password"
              />
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

          <h3>从目录批量导入人脸</h3>
          <p className="panel-subtitle">文件名格式：学号-姓名-班级-性别.*</p>
          <div className="form-grid">
            <label>
              人脸目录
              <input
                ref={directoryInputRef}
                type="file"
                accept="image/*"
                multiple
                onChange={(e) => {
                  const files = e.target.files ? Array.from(e.target.files) : [];
                  setBatchFiles(files);
                  setBatchProcessedCount(0);
                  setBatchImportResult(null);
                  setBatchImportError("");
                }}
              />
            </label>
            <button
              className="btn btn-accent"
              type="button"
              onClick={handleBatchImport}
              disabled={batchImporting || batchFiles.length === 0}
            >
              {batchImporting ? `导入中（${batchProcessedCount}/${batchFiles.length}）...` : "开始批量导入"}
            </button>
          </div>
          {batchFiles.length > 0 ? <p>已选择图片：{batchFiles.length} 张</p> : null}
          {batchImporting ? <p>当前按每批 {IMPORT_BATCH_SIZE} 张自动分批导入</p> : null}
          {batchImportError ? <p className="error-text">{batchImportError}</p> : null}
          {batchImportResult ? (
            <div className="result-card">
              <p>
                导入结果：总计 {batchImportResult.total}，成功 {batchImportResult.success_count}，失败{" "}
                {batchImportResult.failed_count}
              </p>
              {batchImportResult.failed_count > 0 ? (
                <div className="table-shell">
                  <table>
                    <thead>
                      <tr>
                        <th>文件名</th>
                        <th>失败原因</th>
                      </tr>
                    </thead>
                    <tbody>
                      {batchImportResult.items
                        .filter((item) => !item.success)
                        .slice(0, 20)
                        .map((item, idx) => (
                          <tr key={`${item.filename}-${idx}`}>
                            <td>{item.filename}</td>
                            <td>{item.message}</td>
                          </tr>
                        ))}
                    </tbody>
                  </table>
                </div>
              ) : (
                <p className="success-text">全部导入成功</p>
              )}
            </div>
          ) : null}

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
      ) : null}
    </div>
  );
}
