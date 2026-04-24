# 班级考勤系统（内容安全方向）

基于 B/S 架构实现的班级考勤系统，聚焦于以下能力：

- 基础考勤：浏览器调用摄像头采集人脸，后端进行活体检测和人脸库匹配。
- 合照识别：上传班级活动合照，批量识别人脸并统计活动参与频次。
- 情绪分析：在考勤与合照识别过程中同步推断学生情绪并形成统计视图。

## 1. 技术栈

- 内核：`torch` + `ultralytics (YOLOv11)`
- 前端：`TypeScript` + `React` + `Vite`
- 后端：`FastAPI` + `SQLAlchemy` + `SQLite`

## 2. 项目结构

```text
attendance-system/
  backend/
    app/
      api/v1/routes/
      core/
      db/
      models/
      schemas/
      services/
      utils/
      main.py
    requirements.txt
    .env.example
  frontend/
    src/
      api/
      pages/
      App.tsx
      main.tsx
      styles.css
    package.json
  docker-compose.yml
  README.md
```

## 3. 后端能力说明

### 3.1 识别链路

1. 人脸检测：优先使用 YOLOv11 模型（`FACE_DETECTOR_MODEL` 指向权重）；若未配置则回退 OpenCV 检测。
2. 活体检测：使用纹理、清晰度、颜色方差融合评分，过滤照片/屏幕攻击的低质量输入。
3. 人脸比对：基于 torch 特征向量与余弦相似度匹配学生人脸库。
4. 情绪分析：优先加载 torch 情绪模型（`EMOTION_MODEL`）；若未配置，自动回退启发式分类。

### 3.2 核心接口

- `POST /api/v1/students/register`
  - 表单字段：`student_no`、`name`、`class_name`、`image`
  - 用途：学生入库
- `GET /api/v1/students`
  - 用途：查询人脸库
- `POST /api/v1/attendance/check`
  - 表单字段：`image`
  - 用途：考勤识别（状态、学生信息、时间、活体分、情绪）
- `POST /api/v1/group-photo/recognize`
  - 表单字段：`event_name`、`image`
  - 用途：合照批量识别（匹配名单、未匹配数、耗时）
- `GET /api/v1/reports/participation`
  - 用途：活动参与频次统计
- `GET /api/v1/reports/emotions`
  - 用途：情绪汇总与时间线

### 3.3 异常处理

已覆盖以下关键异常场景：

- 摄像头调用失败（前端检测与提示）
- 图片解码失败（后端 `400`）
- 识别超时（后端 `504`）
- 参数校验失败（后端 `422`）
- 服务内部异常（统一 `500` 返回）

## 4. 前端功能说明

- 基础考勤页：实时摄像头预览、抓拍考勤、结果渲染。
- 学生入库：学号/姓名/班级/人脸照片注册，形成人脸库。
- 合照识别页：上传活动合照并查看匹配名单、置信度与情绪。
- 情绪与报表页：查看情绪柱状统计、最近情绪时间线、活动参与排行。

## 5. 运行方式

### 5.1 本地运行（推荐开发）

后端：

```bash
cd backend
python -m venv .venv
# Windows
.venv\Scripts\activate
pip install -r requirements.txt
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

前端：

```bash
cd frontend
npm install
npm run dev
```

访问：`http://127.0.0.1:5173`

### 5.2 Docker Compose

```bash
docker compose up --build
```

## 6. 模型与精度优化建议

为进一步提高识别准确率、降低误识别率，建议在当前工程上继续增强：

- 替换基线特征提取器为训练好的 ArcFace/FaceNet（torch）模型。
- 使用专用活体检测模型（RGB + depth/IR 或视频时序模型）。
- 配置专用情绪识别模型（FER 数据集训练），减少启发式误判。
- 引入质量评估（遮挡、侧脸、模糊）后再进入比对。
- 针对班级场景进行阈值标定（ROC、FAR/FRR）。

## 7. 环境变量

参考 `backend/.env.example`：

- `FACE_DETECTOR_MODEL`：YOLOv11 人脸检测权重路径
- `EMOTION_MODEL`：torch 情绪模型权重路径
- `RECOGNITION_THRESHOLD`：人脸相似度阈值
- `LIVENESS_THRESHOLD`：活体评分阈值
- `REQUEST_TIMEOUT_SEC`：请求超时秒数

## 8. 注意事项

- 首次部署时，请先通过“学生人脸入库”建立至少一名学生样本。
- 若未放置模型权重，系统会自动使用回退策略，可用于联调，但建议生产环境配置专用模型。
- 默认数据库为 `SQLite`，可替换为 MySQL/PostgreSQL 以支持更高并发。
