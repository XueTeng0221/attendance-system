# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project

Class attendance system (B/S) focused on content-safety scenarios: camera-based attendance with liveness, group-photo batch recognition, and emotion analytics. README.md is in Chinese and is the authoritative feature spec.

## Commands

Backend (Python 3.11, run from `backend/`):

```bash
python -m venv .venv && .venv\Scripts\activate   # Windows
pip install -r requirements.txt
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Frontend (run from `frontend/`):

```bash
npm install
npm run dev        # Vite dev server on :5173
npm run build      # tsc -b && vite build  — use this for type-check + production build
```

Full stack via Docker: `docker compose up --build` (backend :8000, frontend :5173).

There is no test suite, no linter config, and no pre-commit hook in the repo. Don't invent commands for them.

## Architecture

### Backend (FastAPI + SQLAlchemy + SQLite)

- Entry point `backend/app/main.py` mounts `api_router` under `settings.api_prefix` (`/api/v1`), registers CORS, and installs two global exception handlers: `RequestValidationError` → 422 with Chinese message, `Exception` → 500. Preserve this envelope shape (`{detail, message}`) when adding error paths.
- `app/core/config.py` — single `Settings` (pydantic-settings) reading `.env`. Key knobs: `face_detector_model`, `emotion_model`, `recognition_threshold`, `liveness_threshold`, `detection_confidence`, `request_timeout_sec`, `allow_heuristic_fallback`.
- `app/api/v1/routes/` — one file per resource: `students`, `attendance`, `group_photo`, `reports`. Wired together in `app/api/v1/api.py`.
- `app/services/` holds the recognition pipeline, and **all routes go through the single `recognition_service` singleton in `app/services/container.py`**. When adding new inference code, extend `RecognitionService` rather than instantiating engines in routes.
  - `face_engine.py` — `FaceDetector`: YOLOv11 (`ultralytics`) when the weights file at `settings.face_detector_model` exists, otherwise falls back to OpenCV Haar cascade with a fixed 0.4 confidence placeholder.
  - `torch_embedder.py` — face embedding for cosine similarity matching.
  - `liveness.py` — texture/sharpness/color-variance heuristic anti-spoof score.
  - `emotion.py` — torch emotion model if `emotion_model` weights exist, else heuristic fallback (gated by `allow_heuristic_fallback`).
  - `recognition.py` — orchestrates detect → liveness → embed → match → emotion and exposes the methods the routes call.
- DB bootstrap: `Base.metadata.create_all` runs in the `startup` event against `settings.database_url` (default `sqlite:///./attendance.db`). No Alembic — schema changes require editing `app/models/` and either deleting `attendance.db` or handling migration manually.
- Weights live in `backend/weights/` (`yolo11n-face.pt`, `enet_b0_8_best_afew.pt`). The fallback paths are intentional: the system must still boot and serve requests when weights are missing, so keep both branches working in any engine edits.

### Frontend (React 19 + Vite + TypeScript)

- Three pages under `src/pages/` (`AttendancePage`, `GroupPhotoPage`, `EmotionDashboardPage`) — all HTTP goes through `src/api/client.ts` (axios). Shared response/domain types in `src/types.ts`.
- Attendance page captures from `getUserMedia` and POSTs a frame as multipart `image`; camera failure handling is a first-class UX concern per the spec.

## Conventions worth knowing

- Code comments and user-facing error messages are written in Chinese; match that when editing existing files.
- API contract is multipart form fields (not JSON) for any endpoint that takes an image — see `students/register`, `attendance/check`, `group-photo/recognize`.
- Timeouts: long-running inference should respect `settings.request_timeout_sec` and return 504, not 500.

## 运行约束

在虚拟环境中运行。

## 目前待实现的评分点

### 后端

1. 考勤数据支持 Excel (xlsx/csv) 导出
2. 活体检测可抵御照片、视频欺骗攻击
3. bug fix：抓拍后活体检测分数在 0.5 左右导致检测不通过

### 前端

1. 支持自动/手动捕捉并实时显示采集状态

### 系统安全

1. 实现师生账号权限区分
