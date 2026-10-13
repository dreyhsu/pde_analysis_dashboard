import uuid
from datetime import datetime, timedelta
import random
import pandas as pd
import numpy as np # 用於常態分佈
import os # 用於路徑操作

# --- SQLAlchemy 設定 ---
from sqlalchemy import create_engine, Column, String, DateTime, Float, Integer, ForeignKey
from sqlalchemy.orm import sessionmaker, relationship
from sqlalchemy.ext.declarative import declarative_base

# --- 資料庫設定 ---
# 資料庫檔案將在專案資料夾中創建
DATABASE_FILE = "yolov11.db"
DATABASE_URL = f"sqlite:///{os.path.join(os.getcwd(), DATABASE_FILE)}" # 將資料庫儲存在目前工作目錄

engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False}) # 建立資料庫引擎
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine) # 建立資料庫會話工廠
Base = declarative_base() # 宣告性的基底類別

# --- SQLAlchemy 模型定義 ---

# 事件基礎資料表模型
class EventBase(Base):
    __tablename__ = "event_base" # 資料表名稱
    event_id = Column(String, primary_key=True, index=True) # 事件 ID (主鍵)
    start_time = Column(DateTime) # 事件開始時間
    end_time = Column(DateTime) # 事件結束時間
    station_id = Column(String, index=True) # 工作站 ID
    operator_id = Column(String, ForeignKey("member.job_number")) # 操作員 ID (外鍵關聯到 Member 表的 job_number)
    product_sn = Column(String, unique=True) # 產品序號
    batch_id = Column(String) # 批次 ID
    shift_code = Column(String) # 班別代碼
    model_version = Column(String) # 模型版本
    camera_id = Column(String) # 相機 ID
    result = Column(String) # 事件結果 (Pass/Fail)
    anomaly_score = Column(Float) # 異常分數
    video_path = Column(String) # 影片路徑
    insert_time = Column(DateTime, default=datetime.now) # 資料插入時間

    details = relationship("Detail", back_populates="event") # 定義與 Detail 表的關聯
    operator = relationship("Member") # 定義與 Member 表的關聯

# 事件詳細資料表模型
class Detail(Base):
    __tablename__ = "details" # 資料表名稱
    id = Column(String, primary_key=True, index=True) # 詳細記錄 ID (主鍵)
    event_id = Column(String, ForeignKey("event_base.event_id"), index=True) # 事件 ID (外鍵)
    detect_item = Column(String) # 偵測項目 (組件名稱)
    result = Column(String) # 此組件結果 (Pass/Fail)
    anomaly_description = Column(String, nullable=True) # 異常描述
    start_time = Column(DateTime) # 組件開始處理時間
    end_time = Column(DateTime) # 組件結束處理時間
    duration_seconds = Column(Float) # 組件處理持續時間 (秒)
    ai_confidence_score = Column(Float) # AI 信賴度分數
    insert_time = Column(DateTime, default=datetime.now) # 資料插入時間

    event = relationship("EventBase", back_populates="details") # 定義與 EventBase 表的關聯

# 成員資料表模型
class Member(Base):
    __tablename__ = "member" # 資料表名稱
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4())) # 成員記錄 ID (主鍵)
    job_number = Column(String, unique=True, index=True) # 工號 (唯一值)
    role = Column(String) # 角色

# --- 常數定義 ---
SOP_COMPONENTS = ["Comp 1", "Comp 2", "Comp 3", "Comp 4", "Comp 5"] # 標準作業流程組件
STATIONS = ["STA001", "STA002", "STA003"] # 工作站
OPERATORS = ["OP001", "OP002", "OP003", "OP004", "OP005"] # 操作員 ID (將用於 Member 表)
SUPERVISORS = ["SPV001", "SPV002"] # 主管 ID

START_DATE = datetime(2026, 10, 1) # 資料生成開始日期
END_DATE = datetime(2026, 10, 28) # 資料生成結束日期
NUM_DAYS = (END_DATE - START_DATE).days + 1 # 生成資料的總天數
EVENTS_PER_DAY = 50 # 每天生成的事件數量 (減少數量以加快測試)
FAIL_PERCENTAGE_PER_DAY = 0.10 # 每天事件中失敗的百分比

# 組件持續時間參數
MEAN_DURATION = 1.75  # 秒，常態分佈的平均值
STD_DEV_DURATION = 0.3 # 秒，常態分佈的標準差
MIN_DURATION = 1.0    # 秒，理想持續時間的最小值
MAX_DURATION = 2.5    # 秒，理想持續時間的最大值

# 時間失敗偏差百分比 (應用於 ideal_duration)
TIME_FAIL_DEVIATION_MIN = 0.03 # 3%
TIME_FAIL_DEVIATION_MAX = 0.05 # 5%

# 時間偏差的異常分數縮放因子
# 平均 K% 的時間偏差會貢獻時間部分異常分數的滿分 50 分
TIME_DEVIATION_SCALE_FOR_SCORE = 0.25

def determine_shift(time_obj: datetime) -> str:
    """根據給定時間物件的小時判斷班別。"""
    hour = time_obj.hour
    if 7 <= hour < 15:
        return "MORNING" # 早班
    elif 15 <= hour < 23:
        return "AFTERNOON" # 中班
    else: # 23-7 (涵蓋 23, 0-6)
        return "NIGHT" # 夜班

def generate_dummy_data(db_session):
    """
    生成事件及其詳細資訊的虛擬資料，並將其插入資料庫。
    """
    print("開始生成虛擬資料並寫入資料庫...")
    overall_event_counter = 0
    current_time_for_insertion = datetime.now() # 為一批次資料使用一致的插入時間

    for day_offset in range(NUM_DAYS):
        current_date = START_DATE + timedelta(days=day_offset)
        print(f"正在為 {current_date.strftime('%Y-%m-%d')} 生成資料...")

        # 決定當天哪些事件索引將被標記為失敗
        num_failed_events_today = int(EVENTS_PER_DAY * FAIL_PERCENTAGE_PER_DAY)
        failed_event_indices_this_day = random.sample(range(EVENTS_PER_DAY), num_failed_events_today)

        # 生成當天事件開始時間的排序隨機秒數偏移量
        daily_event_second_offsets = sorted([random.randint(0, (24 * 60 * 60) - 1) for _ in range(EVENTS_PER_DAY)])
        
        day_start_datetime = datetime(current_date.year, current_date.month, current_date.day)

        for event_idx_in_day in range(EVENTS_PER_DAY):
            event_id_str = str(uuid.uuid4())
            event_start_time_dt = day_start_datetime + timedelta(seconds=daily_event_second_offsets[event_idx_in_day])
            
            is_targeted_for_failure = event_idx_in_day in failed_event_indices_this_day
            
            current_component_processing_time = event_start_time_dt # 追蹤前一個組件的結束時間
            event_details_to_add = []
            
            components_for_this_event = list(SOP_COMPONENTS) # 從完整的 SOP 開始
            num_missing_for_this_event = 0
            event_has_time_deviation_failure_flag = False
            overall_event_result_status = "Pass" # 初始化假設通過

            # 如果此事件被標記為失敗，則確定失敗類型
            if is_targeted_for_failure:
                failure_type = random.choice(["missing_component", "time_deviation"])
                if failure_type == "missing_component":
                    num_to_miss = random.randint(1, 2) # 操作員遺漏 1 或 2 個組件
                    components_to_skip_names = random.sample(SOP_COMPONENTS, num_to_miss)
                    components_for_this_event = [c for c in SOP_COMPONENTS if c not in components_to_skip_names]
                    num_missing_for_this_event = len(SOP_COMPONENTS) - len(components_for_this_event)
                    overall_event_result_status = "Fail" # 遺漏組件意味著事件失敗
                else: # 時間偏差失敗
                    event_has_time_deviation_failure_flag = True
                    # overall_event_result_status 可能會因為詳細資料失敗而變為 "Fail"
            
            # 如果是時間偏差失敗事件，選擇一個組件來表現偏差
            component_idx_with_time_failure = -1
            if event_has_time_deviation_failure_flag and components_for_this_event: # 確保有組件可以失敗
                component_idx_with_time_failure = random.choice(range(len(components_for_this_event)))

            sum_normalized_time_deviations_for_event = 0.0
            
            for comp_idx, component_name in enumerate(components_for_this_event):
                detail_id_str = str(uuid.uuid4())
                detail_start_time_dt = current_component_processing_time
                detail_result_status = "Pass" # 假設此詳細資訊通過
                anomaly_desc_detail_str = None

                # 為此組件生成理想持續時間 (常態分佈，有上下限)
                ideal_duration = np.random.normal(MEAN_DURATION, STD_DEV_DURATION)
                ideal_duration = max(MIN_DURATION, min(ideal_duration, MAX_DURATION))
                actual_duration = ideal_duration # 從理想值開始

                # 如果此組件是此事件中選定的失敗組件，則應用時間失敗
                if event_has_time_deviation_failure_flag and comp_idx == component_idx_with_time_failure:
                    deviation_percent = random.uniform(TIME_FAIL_DEVIATION_MIN, TIME_FAIL_DEVIATION_MAX) # 3% 到 5%
                    direction = random.choice([-1, 1]) # 更短或更長
                    if direction > 0: # 強制為最長理想時間以突顯過長
                        actual_duration_base = MAX_DURATION
                    else: # 強制為最短理想時間以突顯過短
                        actual_duration_base = MIN_DURATION
                    actual_duration = actual_duration_base * (1 + direction * deviation_percent)
                    actual_duration = max(0.1, actual_duration) # 確保持續時間為正且合理
                    
                    detail_result_status = "Fail"
                    anomaly_desc_detail_str = f"時間偏差: {'過短' if direction == -1 else '過長'} {deviation_percent*100:.1f}%"
                    overall_event_result_status = "Fail" # 失敗的詳細資訊使整個事件失敗

                detail_end_time_dt = detail_start_time_dt + timedelta(seconds=actual_duration)
                
                # 計算標準化偏差以用於異常分數
                normalized_deviation = abs(actual_duration - ideal_duration) / ideal_duration if ideal_duration > 0 else 0
                sum_normalized_time_deviations_for_event += normalized_deviation

                detail_obj = Detail(
                    id=detail_id_str,
                    event_id=event_id_str,
                    detect_item=component_name,
                    result=detail_result_status,
                    anomaly_description=anomaly_desc_detail_str,
                    start_time=detail_start_time_dt,
                    end_time=detail_end_time_dt,
                    duration_seconds=round(actual_duration, 3),
                    ai_confidence_score=round(random.uniform(0.85, 0.99) if detail_result_status == "Pass" else random.uniform(0.6, 0.85), 4),
                    insert_time=current_time_for_insertion
                )
                event_details_to_add.append(detail_obj)
                current_component_processing_time = detail_end_time_dt # 下一個組件在此組件結束後開始

            # --- 事件級別計算 ---
            event_end_time_dt = current_component_processing_time if event_details_to_add else event_start_time_dt
            num_installed_components = len(event_details_to_add)

            # 異常分數計算
            # 1. 遺漏組件分數 (最高 50 分)
            missing_score = (num_missing_for_this_event / len(SOP_COMPONENTS)) * 50 if len(SOP_COMPONENTS) > 0 else 0
            
            # 2. 時間偏差分數 (最高 50 分)
            time_dev_score = 0.0
            if num_installed_components > 0:
                avg_normalized_dev = sum_normalized_time_deviations_for_event / num_installed_components
                # 縮放: 如果 avg_normalized_dev 是 K (TIME_DEVIATION_SCALE_FOR_SCORE)，分數為 50
                time_dev_score = min(avg_normalized_dev / TIME_DEVIATION_SCALE_FOR_SCORE, 1.0) * 50
            
            final_anomaly_score = round(min(missing_score + time_dev_score, 100.0), 2)

            event_base_obj = EventBase(
                event_id=event_id_str,
                start_time=event_start_time_dt,
                end_time=event_end_time_dt,
                station_id=random.choice(STATIONS),
                operator_id=random.choice(OPERATORS), # 確保這些 OPERATORS 存在於 Member 表中
                product_sn=f"SN{10000 + overall_event_counter:05d}",
                batch_id=f"BATCH{1000 + (overall_event_counter // 50):04d}", # 每 50 個產品一個新批次
                shift_code=determine_shift(event_start_time_dt),
                model_version="v1.1", # 範例版本
                camera_id=f"CAM{random.randint(1, 3):03d}",
                result=overall_event_result_status,
                anomaly_score=final_anomaly_score,
                video_path=f"/videos/{event_id_str}.mp4", # 使用 event_id 命名影片路徑
                insert_time=current_time_for_insertion
            )
            db_session.add(event_base_obj)
            for detail_obj in event_details_to_add:
                db_session.add(detail_obj)
            
            overall_event_counter += 1
        
        db_session.commit() # 每天結束後提交一次，或根據需要更頻繁/更少頻繁地提交
        print(f"完成 {current_date.strftime('%Y-%m-%d')} 的資料生成。目前總共生成事件數: {overall_event_counter}")
    
    print(f"總共生成並嘗試寫入 {overall_event_counter} 個事件記錄。")


def create_db_and_tables():
    """創建資料庫和所有定義的資料表。"""
    # Base.metadata.drop_all(bind=engine) # 如果需要，取消註解以在每次運行時刪除並重建資料表
    Base.metadata.create_all(bind=engine)
    print(f"資料表已在 {DATABASE_FILE} 中成功創建 (如果尚不存在)！")

def insert_member_data(db_session):
    """插入測試用的成員資料。"""
    print("正在插入成員資料...")
    members_to_add = []
    
    # 從 OPERATORS 常數添加操作員
    for op_id in OPERATORS:
        member = db_session.query(Member).filter_by(job_number=op_id).first()
        if not member: # 僅在成員不存在時添加
            members_to_add.append(Member(id=str(uuid.uuid4()), job_number=op_id, role="Operator")) # 操作員角色
    
    # 添加範例中的主管
    for sup_id in SUPERVISORS:
        member = db_session.query(Member).filter_by(job_number=sup_id).first()
        if not member:
            members_to_add.append(Member(id=str(uuid.uuid4()), job_number=sup_id, role="Supervisor")) # 主管角色

    if members_to_add:
        db_session.add_all(members_to_add)
        db_session.commit()
        print(f"已成功插入/更新 {len(members_to_add)} 筆成員資料。")
    else:
        print("成員資料已存在，無需插入。")


# --- 主要執行流程 ---
if __name__ == "__main__":
    print("開始資料庫設置與資料生成腳本...")

    # 1. 創建資料庫檔案和資料表 (如果它們不存在)
    create_db_and_tables()

    # 2. 創建資料庫會話
    db = SessionLocal()

    try:
        # 3. 插入成員資料
        insert_member_data(db)

        # 4. 生成並插入虛擬事件和詳細資料
        generate_dummy_data(db)

        # 驗證資料是否已插入 (可選)
        event_count = db.query(EventBase).count()
        detail_count = db.query(Detail).count()
        member_count = db.query(Member).count()
        print(f"\n資料庫中的記錄數量:")
        print(f"  - 事件 (EventBase): {event_count}")
        print(f"  - 詳細資訊 (Details): {detail_count}")
        print(f"  - 成員 (Member): {member_count}")

        print(f"\n資料已成功插入到 {DATABASE_FILE}")

    except Exception as e:
        print(f"\n處理過程中發生錯誤: {e}")
        db.rollback() # 如果發生錯誤，回滾事務
    finally:
        db.close() # 確保關閉資料庫會話

    print("資料生成與資料庫操作完成。 🎉")