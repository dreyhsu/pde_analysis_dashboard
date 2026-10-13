from fastapi import FastAPI, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from sqlalchemy import create_engine, Column, String, DateTime, Float, ForeignKey
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from pydantic import BaseModel
import pandas as pd
from datetime import datetime
# In main.py, add after the imports
from sqlalchemy.orm import Session


# 定義資料庫模型
Base = declarative_base()

class Member(Base):
    __tablename__ = "member"
    id = Column(String, primary_key=True)
    job_number = Column(String, unique=True)
    role = Column(String)

class EventBase(Base):
    __tablename__ = "event_base"
    event_id = Column(String, primary_key=True)
    start_time = Column(DateTime)
    end_time = Column(DateTime)
    station_id = Column(String)
    operator_id = Column(String)
    product_sn = Column(String)
    batch_id = Column(String)
    shift_code = Column(String)
    model_version = Column(String)
    camera_id = Column(String)
    result = Column(String)
    video_path = Column(String)
    insert_time = Column(DateTime)
    anomaly_score = Column(Float)  # 添加這個欄位

class Details(Base):
    __tablename__ = "details"
    id = Column(String, primary_key=True)
    event_id = Column(String, ForeignKey("event_base.event_id"))
    detect_item = Column(String)
    result = Column(String)
    anomaly_description = Column(String)
    start_time = Column(DateTime)
    end_time = Column(DateTime)
    duration_seconds = Column(Float)
    ai_confidence_score = Column(Float)
    insert_time = Column(DateTime)

# 資料庫連線
DATABASE_URL = "sqlite:///yolov11.db"
engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# FastAPI 應用
app = FastAPI()

# CORS 設定
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 依賴項：獲取資料庫會話
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# Pydantic 模型：篩選條件
class FilterRequest(BaseModel):
    station: str
    operator: str | None = None
    start_date: str | None = None
    end_date: str | None = None

# Add new endpoint for fetching job numbers
@app.get("/api/job-numbers")
async def get_job_numbers(db: Session = Depends(get_db)):
    """獲取所有工號列表供 autocomplete 使用"""
    job_numbers = db.query(Member.job_number).filter(Member.job_number.isnot(None)).all()
    return {"job_numbers": [jn[0] for jn in job_numbers if jn[0]]}

# API 端點：獲取檢測資料
@app.post("/api/detection-data")
async def get_detection_data(filters: FilterRequest, db: Session = Depends(get_db)):
    if not filters.station:
        raise HTTPException(status_code=400, detail="站點為必填欄位")

    # 驗證日期範圍
    if filters.start_date and filters.end_date:
        try:
            start = datetime.fromisoformat(filters.start_date.replace('Z', '+00:00'))
            end = datetime.fromisoformat(filters.end_date.replace('Z', '+00:00'))
            if (end - start).days > 7:
                raise HTTPException(status_code=400, detail="日期範圍不得超過7天")
            if start > end:
                raise HTTPException(status_code=400, detail="結束日期不得早於開始日期")
        except ValueError:
            raise HTTPException(status_code=400, detail="無效的日期格式")

    # 查詢 event_base - 按 anomaly_score 排序並取前20筆
    query = db.query(EventBase)
    query = query.filter(EventBase.station_id == filters.station)
    if filters.operator:
        query = query.filter(EventBase.operator_id == filters.operator)
    if filters.start_date:
        query = query.filter(EventBase.start_time >= start)
    if filters.end_date:
        query = query.filter(EventBase.end_time <= end)
    
    # 按 anomaly_score 降序排列，取前20筆用於圖表顯示
    top20_events_query = query.order_by(EventBase.anomaly_score.desc()).limit(20)
    top20_events = top20_events_query.all()
    top20_event_ids = [event.event_id for event in top20_events]

    # 獲取所有符合條件的 event_base 資料（用於統計）
    all_events_df = pd.read_sql(query.statement, db.bind)
    event_base_data = all_events_df.to_dict(orient='records')

    # 計算事件數（基於所有符合條件的事件）
    total_events = len(all_events_df)
    success_events = len(all_events_df[all_events_df['result'] == 'Pass'])
    error_events = len(all_events_df[all_events_df['result'] == 'Fail'])

    # 查詢所有符合條件的 details 資料（用於計算平均值）
    all_details_query = (
        db.query(Details.detect_item, Details.duration_seconds, Details.event_id)
        .join(EventBase, Details.event_id == EventBase.event_id)
        .filter(EventBase.station_id == filters.station)
    )
    if filters.operator:
        all_details_query = all_details_query.filter(EventBase.operator_id == filters.operator)
    if filters.start_date:
        all_details_query = all_details_query.filter(EventBase.start_time >= start)
    if filters.end_date:
        all_details_query = all_details_query.filter(EventBase.end_time <= end)

    all_details_df = pd.read_sql(all_details_query.statement, db.bind)

    # 查詢前20筆事件的 details 資料（用於圖表顯示）
    top20_details_query = (
        db.query(Details.detect_item, Details.duration_seconds, Details.event_id)
        .filter(Details.event_id.in_(top20_event_ids))
    )
    
    top20_details_df = pd.read_sql(top20_details_query.statement, db.bind)

    # 獲取 details 完整資料（用於下載）
    full_details_query = (
        db.query(Details)
        .join(EventBase, Details.event_id == EventBase.event_id)
        .filter(EventBase.station_id == filters.station)
    )
    if filters.operator:
        full_details_query = full_details_query.filter(EventBase.operator_id == filters.operator)
    if filters.start_date:
        full_details_query = full_details_query.filter(EventBase.start_time >= start)
    if filters.end_date:
        full_details_query = full_details_query.filter(EventBase.end_time <= end)

    details_full_df = pd.read_sql(full_details_query.statement, db.bind)
    details_data = details_full_df.to_dict(orient='records')

    # 獲取唯一步驟（基於所有資料）
    steps = sorted(all_details_df["detect_item"].unique().tolist())

    # 按 anomaly_score 排序的事件順序來組織圖表資料
    items = []
    for event in top20_events:  # 使用已排序的前20筆事件
        event_id = event.event_id
        group = top20_details_df[top20_details_df["event_id"] == event_id]
        durations = []
        for step in steps:
            step_data = group[group["detect_item"] == step]
            if not step_data.empty:
                durations.append(step_data["duration_seconds"].iloc[0])
            else:
                durations.append(0)
        items.append(durations)

    # 計算每個步驟的平均時長（基於所有符合條件的事件）
    avg_data = []
    if len(all_details_df) > 0:
        pivot_df = all_details_df.pivot(index="event_id", columns="detect_item", values="duration_seconds")
        pivot_df = pivot_df.fillna(0)
        pivot_df = pivot_df.reindex(columns=steps, fill_value=0)
        avg_data = pivot_df.mean().tolist()
        avg_data = [float(x) for x in avg_data]
    else:
        avg_data = [0.0] * len(steps)

    # 準備返回給前端的 top20 事件資料（保持 anomaly_score 排序）
    top20_event_base_data = []
    for event in top20_events:
        event_dict = {
            'event_id': event.event_id,
            'start_time': event.start_time,
            'end_time': event.end_time,
            'station_id': event.station_id,
            'operator_id': event.operator_id,
            'product_sn': event.product_sn,
            'batch_id': event.batch_id,
            'shift_code': event.shift_code,
            'model_version': event.model_version,
            'camera_id': event.camera_id,
            'result': event.result,
            'video_path': event.video_path,
            'insert_time': event.insert_time,
            'anomaly_score': event.anomaly_score
        }
        top20_event_base_data.append(event_dict)

    return {
        "steps": steps,
        "items": items,
        "avg_data": avg_data,
        "total_events": total_events,
        "success_events": success_events,
        "error_events": error_events,
        "event_base_data": event_base_data,  # 所有符合條件的事件（用於下載）
        "top20_event_base_data": top20_event_base_data,  # 前20筆事件（用於圖表）
        "details_data": details_data
    }