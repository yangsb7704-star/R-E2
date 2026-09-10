import json
import math
import re
import textwrap
from datetime import datetime

import streamlit as st
import matplotlib.pyplot as plt
import matplotlib.patches as patches
from mpl_toolkits.mplot3d.art3d import Poly3DCollection

# =========================================================
# 가상환경 모빌리티 테스트베드 Streamlit App
# - 초기 설계 도움 시스템의 JSON/요약문 붙여넣기 지원
# - 직접 입력 모드 지원
# - PASS / WARNING / FAIL 기준 및 근거 표시
# - 3D 심플 가상 주행 이미지
# =========================================================

st.set_page_config(
    page_title="가상환경 모빌리티 테스트베드",
    page_icon="🧪",
    layout="wide",
)

# -----------------------------
# 기본 스타일
# -----------------------------
st.markdown(
    """
    <style>
    .main-title {
        font-size: 2.25rem;
        font-weight: 800;
        margin-bottom: 0.25rem;
    }
    .sub-desc {
        color: #6b7280;
        font-size: 1.02rem;
        margin-bottom: 1.2rem;
    }
    .small-note {
        color: #6b7280;
        font-size: 0.9rem;
    }
    .pass-box, .warn-box, .fail-box, .info-box {
        padding: 0.85rem 1rem;
        border-radius: 0.75rem;
        margin: 0.35rem 0;
        border: 1px solid rgba(255,255,255,0.15);
    }
    .pass-box { background: rgba(34, 197, 94, 0.13); border-left: 5px solid #22c55e; }
    .warn-box { background: rgba(245, 158, 11, 0.15); border-left: 5px solid #f59e0b; }
    .fail-box { background: rgba(239, 68, 68, 0.15); border-left: 5px solid #ef4444; }
    .info-box { background: rgba(59, 130, 246, 0.12); border-left: 5px solid #3b82f6; }
    .criterion {
        font-size: 0.92rem;
        color: #6b7280;
        margin-top: 0.25rem;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

# -----------------------------
# 상수 및 프리셋
# -----------------------------
ROAD_PROFILES = {
    "실내 평지": {"crr": 0.018, "mu": 0.75, "rough": 1.00, "desc": "마찰과 요철이 작아 안정적인 주행 환경"},
    "아스팔트": {"crr": 0.022, "mu": 0.85, "rough": 1.05, "desc": "일반 도로형 주행 환경"},
    "흙길": {"crr": 0.045, "mu": 0.60, "rough": 1.20, "desc": "구름저항이 증가하고 접지 안정성이 낮아지는 환경"},
    "자갈길": {"crr": 0.060, "mu": 0.52, "rough": 1.32, "desc": "요철과 진동 때문에 토크와 안정성이 더 필요한 환경"},
    "험지/경사 복합": {"crr": 0.085, "mu": 0.45, "rough": 1.55, "desc": "등판, 요철, 접지 한계가 동시에 문제가 되는 환경"},
}

OBSTACLE_LEVELS = {
    "없음": 1.00,
    "낮음": 1.10,
    "중간": 1.25,
    "높음": 1.45,
}

CONTROL_MODES = {
    "일반 제어": {"eff_bonus": 0.00, "heat_factor": 1.00, "traction_bonus": 0.00, "desc": "별도 보정 없이 기본 구동 상태로 주행"},
    "효율 우선 전력 제어": {"eff_bonus": 0.04, "heat_factor": 0.92, "traction_bonus": 0.00, "desc": "전력 손실을 줄여 배터리 지속성을 높이는 제어"},
    "발열 억제 제어": {"eff_bonus": 0.02, "heat_factor": 0.78, "traction_bonus": 0.00, "desc": "순간 성능보다 모터·드라이버 과열 억제를 우선"},
    "센서 기반 토크 보정": {"eff_bonus": 0.01, "heat_factor": 0.90, "traction_bonus": 0.08, "desc": "경사·험지에서 미끄러짐을 줄이도록 토크를 보정"},
}

DIRECT_PRESETS = {
    "직접 입력": {},
    "실내 청소로봇 가상 검증": {
        "mobility_name": "스위피형 실내 청소로봇",
        "purpose": "실내 바닥 청소 및 저속 자율 이동",
        "mass": 75.0,
        "target_speed": 1.2,
        "wheels": 2,
        "wheel_radius": 0.10,
        "motor_rpm": 3000.0,
        "motor_torque": 0.50,
        "gear_ratio": 22.0,
        "efficiency": 0.85,
        "battery_wh": 480.0,
    },
    "FRC/대회용 로봇 가상 검증": {
        "mobility_name": "FRC/대회용 로봇",
        "purpose": "공 수집, 이송, 발사 기능을 가진 경기장 주행 로봇",
        "mass": 55.0,
        "target_speed": 2.0,
        "wheels": 4,
        "wheel_radius": 0.10,
        "motor_rpm": 3000.0,
        "motor_torque": 0.50,
        "gear_ratio": 16.0,
        "efficiency": 0.85,
        "battery_wh": 430.0,
    },
    "전동 킥보드형 모빌리티": {
        "mobility_name": "전동 킥보드형 모빌리티",
        "purpose": "개인 이동용 저중량 고속 주행",
        "mass": 85.0,
        "target_speed": 4.2,
        "wheels": 2,
        "wheel_radius": 0.11,
        "motor_rpm": 3200.0,
        "motor_torque": 0.80,
        "gear_ratio": 12.0,
        "efficiency": 0.86,
        "battery_wh": 520.0,
    },
    "초소형 전기차형 모빌리티": {
        "mobility_name": "초소형 전기차형 모빌리티",
        "purpose": "도로형 고속 이동 및 탑승자 운송",
        "mass": 562.0,
        "target_speed": 13.9,
        "wheels": 4,
        "wheel_radius": 0.25,
        "motor_rpm": 3000.0,
        "motor_torque": 8.0,
        "gear_ratio": 9.0,
        "efficiency": 0.88,
        "battery_wh": 6000.0,
    },
    "궤도형 험지 탐사 로봇": {
        "mobility_name": "궤도형 험지 탐사 로봇",
        "purpose": "험지, 경사, 장애물 환경에서 저속 탐사",
        "mass": 80.0,
        "target_speed": 0.7,
        "wheels": 4,
        "wheel_radius": 0.12,
        "motor_rpm": 4000.0,
        "motor_torque": 1.4,
        "gear_ratio": 38.0,
        "efficiency": 0.82,
        "battery_wh": 800.0,
    },
}

# -----------------------------
# 유틸 함수
# -----------------------------
def safe_float(value, default=0.0):
    try:
        if value is None:
            return default
        if isinstance(value, (int, float)):
            return float(value)
        txt = str(value).replace(",", "")
        nums = re.findall(r"-?\d+(?:\.\d+)?", txt)
        return float(nums[0]) if nums else default
    except Exception:
        return default


def safe_int(value, default=0):
    try:
        return int(round(safe_float(value, default)))
    except Exception:
        return default


def line_value(text, keys):
    for line in text.splitlines():
        clean = line.strip()
        for key in keys:
            if clean.startswith(key):
                parts = re.split(r"[:：]", clean, maxsplit=1)
                if len(parts) == 2:
                    return parts[1].strip()
    return None


def infer_vehicle_type(name, purpose, extra=""):
    s = f"{name} {purpose} {extra}".lower()
    if any(k in s for k in ["킥보드", "scooter"]):
        return "scooter"
    if any(k in s for k in ["전기차", "자동차", "ev", "car", "초소형"]):
        return "car"
    if any(k in s for k in ["궤도", "트랙", "track", "험지", "탐사"]):
        return "tracked"
    if any(k in s for k in ["청소", "스위피", "clean"]):
        return "cleaner"
    if any(k in s for k in ["물류", "카고", "cargo"]):
        return "cargo"
    if any(k in s for k in ["frc", "대회", "shooter", "intake", "feeder"]):
        return "competition"
    return "generic"


def parse_design_text(raw_text):
    """JSON 또는 일반 요약문을 모두 해석한다."""
    raw = (raw_text or "").strip()
    if not raw:
        raise ValueError("붙여넣은 내용이 비어 있습니다.")

    # 1) JSON 우선 시도
    if raw.startswith("{") or raw.startswith("["):
        obj = json.loads(raw)
        if isinstance(obj, list):
            obj = obj[0]
        return normalize_design_data(obj)

    # 2) 일반 요약문 파싱
    purpose = line_value(raw, ["용도", "목적", "모빌리티 용도"])
    scale = line_value(raw, ["스케일", "규모"])
    mass = line_value(raw, ["질량", "총 질량", "예상 총 질량"])
    speed = line_value(raw, ["목표 속도", "속도"])
    wheels = line_value(raw, ["구동 바퀴 수", "바퀴 수", "구동바퀴수"])
    env = line_value(raw, ["운행 환경", "환경"])
    extra = line_value(raw, ["기타 요구사항", "요구사항", "추가 요구사항"])

    req_power = line_value(raw, ["요구 동력", "필요 동력"])
    req_tq = line_value(raw, ["바퀴당 요구 토크", "요구 토크"])
    req_rpm = line_value(raw, ["필요 휠 RPM", "휠 RPM", "필요 RPM"])
    gear = line_value(raw, ["추천 감속비", "추천 기어비", "감속비", "기어비"])
    motor_rpm = line_value(raw, ["모터 RPM", "모터 회전수"])
    motor_torque = line_value(raw, ["모터 토크", "모터 기준 토크", "기준 토크"])
    wheel_radius = line_value(raw, ["바퀴 반지름", "휠 반지름"])

    # 속도 단위 추론
    speed_num = safe_float(speed, 1.0)
    unit = "mps"
    if speed and ("km/h" in speed.lower() or "kmh" in speed.lower() or "킬로" in speed):
        unit = "kmh"
    target_speed = speed_num / 3.6 if unit == "kmh" else speed_num

    env_map = {
        "indoor": "실내 평지",
        "normal": "아스팔트",
        "obstacle": "자갈길",
        "extreme": "험지/경사 복합",
        "단순 이동": "실내 평지",
        "평지": "실내 평지",
        "실내": "실내 평지",
        "장애물": "자갈길",
        "험지": "험지/경사 복합",
    }
    road = "실내 평지"
    if env:
        for k, v in env_map.items():
            if k in env:
                road = v
                break

    design = {
        "mobility_name": purpose or "불러온 모빌리티",
        "purpose": purpose or "초기 설계 도움 시스템에서 불러온 모빌리티",
        "scale": scale or "문서에 명시되지 않음",
        "mass": safe_float(mass, 35.0),
        "target_speed": target_speed,
        "wheels": max(1, safe_int(wheels, 4)),
        "road": road,
        "extra": extra or "",
        "wheel_radius": safe_float(wheel_radius, 0.10),
        "motor_rpm": safe_float(motor_rpm, 3000.0),
        "motor_torque": safe_float(motor_torque, 0.50),
        "gear_ratio": safe_float(gear, 18.0),
        "efficiency": 0.85,
        "battery_wh": 500.0,
        "required_power_w_from_design": safe_float(req_power, 0.0),
        "required_wheel_torque_nm_from_design": safe_float(req_tq, 0.0),
        "required_wheel_rpm_from_design": safe_float(req_rpm, 0.0),
        "source_type": "text_summary",
    }
    design["vehicle_type"] = infer_vehicle_type(design["mobility_name"], design["purpose"], design["extra"])
    return design


def normalize_design_data(obj):
    """초기 설계 시스템 JSON 구조가 조금 달라도 테스트베드 공통 구조로 변환한다."""
    input_data = obj.get("input", obj.get("data", obj)) if isinstance(obj, dict) else {}
    result = obj.get("result", obj.get("calc", obj.get("analysis", {}))) if isinstance(obj, dict) else {}
    parts = obj.get("parts", obj.get("part", {})) if isinstance(obj, dict) else {}

    purpose = input_data.get("purpose") or obj.get("purpose") or "불러온 모빌리티"
    scale = input_data.get("scale") or obj.get("scale") or "문서에 명시되지 않음"

    speed = input_data.get("targetSpeedMps", input_data.get("speed_mps", input_data.get("speed", 1.0)))
    unit = input_data.get("unit", "mps")
    target_speed = safe_float(speed, 1.0)
    if unit in ["kmh", "km/h"]:
        target_speed = target_speed / 3.6

    env = input_data.get("env", input_data.get("environment", "indoor"))
    road = "실내 평지"
    if str(env).lower() in ["normal", "road", "asphalt"]:
        road = "아스팔트"
    elif str(env).lower() in ["obstacle"]:
        road = "자갈길"
    elif str(env).lower() in ["extreme"]:
        road = "험지/경사 복합"

    gear_ratio = (
        result.get("recommendedGearRatio")
        or result.get("best_ratio")
        or result.get("recommended_ratio")
        or result.get("gear_ratio")
        or obj.get("best_ratio")
        or 18.0
    )

    design = {
        "mobility_name": purpose,
        "purpose": purpose,
        "scale": scale,
        "mass": safe_float(input_data.get("mass", obj.get("mass", 35.0)), 35.0),
        "target_speed": target_speed,
        "wheels": max(1, safe_int(input_data.get("wheels", obj.get("wheels", 4)), 4)),
        "road": road,
        "extra": input_data.get("extra", obj.get("extra", "")),
        "wheel_radius": safe_float(parts.get("wheel_r", result.get("wheelRadiusM", result.get("wheel_radius", 0.10))), 0.10),
        "motor_rpm": safe_float(parts.get("motor_rpm", result.get("motorRpm", result.get("motor_rpm", 3000.0))), 3000.0),
        "motor_torque": safe_float(parts.get("motor_nm", result.get("motorTorqueNm", result.get("motor_nm", 0.50))), 0.50),
        "gear_ratio": safe_float(gear_ratio, 18.0),
        "efficiency": safe_float(result.get("driveEfficiency", result.get("efficiency", 0.85)), 0.85),
        "battery_wh": safe_float(result.get("batteryWh", result.get("battery_wh", 500.0)), 500.0),
        "required_power_w_from_design": safe_float(result.get("requiredPowerW", result.get("req_power", 0.0)), 0.0),
        "required_wheel_torque_nm_from_design": safe_float(result.get("requiredWheelTorqueNm", result.get("req_tq", 0.0)), 0.0),
        "required_wheel_rpm_from_design": safe_float(result.get("requiredWheelRpm", result.get("req_rpm", 0.0)), 0.0),
        "source_type": "json",
    }
    design["vehicle_type"] = infer_vehicle_type(design["mobility_name"], design["purpose"], design["extra"])
    return design


def evaluate_status(value, pass_cond, warn_cond):
    if pass_cond(value):
        return "PASS"
    if warn_cond(value):
        return "WARNING"
    return "FAIL"


def status_box(status, title, value_text, criterion, evidence):
    cls = "pass-box" if status == "PASS" else "warn-box" if status == "WARNING" else "fail-box"
    icon = "✅" if status == "PASS" else "⚠️" if status == "WARNING" else "❌"
    st.markdown(
        f"""
        <div class="{cls}">
            <b>{icon} {title}: {status}</b><br>
            <b>결과값:</b> {value_text}<br>
            <div class="criterion"><b>판정 기준:</b> {criterion}</div>
            <div class="criterion"><b>판정 근거:</b> {evidence}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def run_simulation(design, env):
    g = 9.81
    mass = max(0.1, design["mass"] + env["payload_kg"])
    target_speed = max(0.01, design["target_speed"])
    wheels = max(1, int(design["wheels"]))
    wheel_r = max(0.02, design["wheel_radius"])
    motor_rpm = max(1.0, design["motor_rpm"])
    motor_torque = max(0.001, design["motor_torque"])
    gear_ratio = max(1.0, design["gear_ratio"])

    road = ROAD_PROFILES[env["road"]]
    control = CONTROL_MODES[env["control_mode"]]
    efficiency = min(0.96, max(0.40, design["efficiency"] + control["eff_bonus"]))
    grade_deg = env["grade_deg"]
    obstacle_factor = OBSTACLE_LEVELS[env["obstacle"]]

    # 구동 가능 토크/힘
    wheel_torque_each = motor_torque * gear_ratio * efficiency
    total_traction_force = (wheel_torque_each / wheel_r) * wheels

    # 접지 한계
    traction_limit = road["mu"] * mass * g * math.cos(math.radians(grade_deg)) * (1 + control["traction_bonus"])
    usable_traction_force = min(total_traction_force, traction_limit)

    # 저항력
    rolling_force = road["crr"] * mass * g * math.cos(math.radians(grade_deg)) * road["rough"] * obstacle_factor
    grade_force = mass * g * math.sin(math.radians(grade_deg))
    aero_force = 0.5 * 1.225 * 0.8 * 0.7 * (target_speed ** 2) if env["use_air_drag"] else 0.0
    required_force = rolling_force + grade_force + aero_force

    # 속도 한계
    wheel_rpm = motor_rpm / gear_ratio
    vmax_mps = (2 * math.pi * wheel_r) * wheel_rpm / 60.0
    speed_achievement = min(vmax_mps / target_speed, 1.5) * 100

    # 가속
    net_force = usable_traction_force - required_force
    acceleration = max(0.0, net_force / mass)
    accel_time = target_speed / acceleration if acceleration > 0.02 else float("inf")

    # 등판 한계: traction >= rolling + m*g*sin(theta)
    max_grade_rad = 0.0
    available_for_grade = usable_traction_force - (road["crr"] * mass * g * road["rough"] * obstacle_factor) - aero_force
    if available_for_grade > 0:
        ratio = min(1.0, max(0.0, available_for_grade / (mass * g)))
        max_grade_rad = math.asin(ratio)
    max_grade_deg = math.degrees(max_grade_rad)

    # 토크 여유율
    required_wheel_torque_each = (required_force * wheel_r) / wheels
    torque_margin = ((wheel_torque_each - required_wheel_torque_each) / max(required_wheel_torque_each, 0.001)) * 100

    # 배터리/전력
    cruise_speed = min(target_speed, vmax_mps)
    mechanical_power = max(required_force * cruise_speed, 0.0)
    electrical_power = mechanical_power / max(efficiency, 0.1)
    # 가속/장애물 보정
    avg_power = electrical_power * (1.0 + min(max(env["obstacle_target_weight"], 0), 0.35)) + 15
    if design.get("required_power_w_from_design", 0) > 0:
        avg_power = max(avg_power, design["required_power_w_from_design"] * 0.75)
    battery_wh = max(1.0, design["battery_wh"])
    runtime_h = battery_wh / max(avg_power, 1.0)
    runtime_min = runtime_h * 60
    range_m = runtime_h * cruise_speed * 3600
    required_time_min = env["target_time_min"]

    # 발열: 모터의 기계적 정격 근사 = 토크 * 각속도
    motor_rated_power_each = motor_torque * (2 * math.pi * motor_rpm / 60.0)
    total_motor_rated_power = max(1.0, motor_rated_power_each * wheels)
    load_ratio = (avg_power / max(total_motor_rated_power, 1.0)) * 100 * control["heat_factor"]

    if load_ratio < 60:
        heat_level = "낮음"
    elif load_ratio < 85:
        heat_level = "주의"
    elif load_ratio < 110:
        heat_level = "높음"
    else:
        heat_level = "위험"

    # 제동 거리
    brake_mu = max(0.15, road["mu"] * 0.72)
    decel = brake_mu * g * math.cos(math.radians(grade_deg)) - g * math.sin(math.radians(grade_deg)) * 0.2
    decel = max(0.4, decel)
    braking_distance = (target_speed ** 2) / (2 * decel)
    safe_braking_limit = max(1.5, target_speed * 1.2)

    # 시간 기반 간이 프로파일
    duration = max(10, int(env["target_time_min"] * 60))
    samples = min(180, max(40, duration))
    t_values = [i * duration / (samples - 1) for i in range(samples)]
    speeds = []
    distances = []
    batteries = []
    torque_usages = []
    dist = 0.0
    battery_pct = 100.0
    dt = duration / (samples - 1)
    for t in t_values:
        if accel_time != float("inf") and t < accel_time:
            v = min(target_speed, acceleration * t)
        else:
            v = min(target_speed, vmax_mps)
        # 후반부 10% 제동 표현
        if t > duration * 0.9:
            ratio = max(0.0, 1 - (t - duration * 0.9) / (duration * 0.1))
            v *= ratio
        dist += v * dt
        consumed_wh = avg_power * (t / 3600.0)
        battery_pct = max(0.0, 100.0 * (1 - consumed_wh / battery_wh))
        torque_usage = min(160.0, 100.0 * required_wheel_torque_each / max(wheel_torque_each, 0.001))
        speeds.append(v)
        distances.append(dist)
        batteries.append(battery_pct)
        torque_usages.append(torque_usage)

    # 판정
    speed_status = evaluate_status(
        speed_achievement,
        lambda x: x >= 95,
        lambda x: x >= 75,
    )
    torque_status = evaluate_status(
        torque_margin,
        lambda x: x >= 30,
        lambda x: x >= 0,
    )
    grade_status = evaluate_status(
        max_grade_deg - grade_deg,
        lambda x: x >= 3,
        lambda x: x >= 0,
    )
    battery_status = evaluate_status(
        runtime_min / max(required_time_min, 0.1) * 100,
        lambda x: x >= 100,
        lambda x: x >= 70,
    )
    heat_status = "PASS" if heat_level in ["낮음", "주의"] else "WARNING" if heat_level == "높음" else "FAIL"
    brake_status = evaluate_status(
        safe_braking_limit - braking_distance,
        lambda x: x >= 0.5,
        lambda x: x >= 0,
    )

    statuses = {
        "속도": speed_status,
        "토크": torque_status,
        "등판": grade_status,
        "배터리": battery_status,
        "발열": heat_status,
        "제동": brake_status,
    }

    score_map = {"PASS": 100, "WARNING": 65, "FAIL": 25}
    weights = {"속도": 0.18, "토크": 0.24, "등판": 0.18, "배터리": 0.15, "발열": 0.13, "제동": 0.12}
    total_score = sum(score_map[statuses[k]] * weights[k] for k in statuses)

    return {
        "mass_total": mass,
        "wheel_torque_each": wheel_torque_each,
        "required_wheel_torque_each": required_wheel_torque_each,
        "torque_margin": torque_margin,
        "total_traction_force": total_traction_force,
        "usable_traction_force": usable_traction_force,
        "traction_limit": traction_limit,
        "required_force": required_force,
        "rolling_force": rolling_force,
        "grade_force": grade_force,
        "aero_force": aero_force,
        "vmax_mps": vmax_mps,
        "speed_achievement": speed_achievement,
        "acceleration": acceleration,
        "accel_time": accel_time,
        "max_grade_deg": max_grade_deg,
        "avg_power": avg_power,
        "runtime_min": runtime_min,
        "range_m": range_m,
        "load_ratio": load_ratio,
        "heat_level": heat_level,
        "braking_distance": braking_distance,
        "safe_braking_limit": safe_braking_limit,
        "statuses": statuses,
        "total_score": total_score,
        "t_values": t_values,
        "speeds": speeds,
        "distances": distances,
        "batteries": batteries,
        "torque_usages": torque_usages,
        "road_desc": road["desc"],
        "control_desc": control["desc"],
        "efficiency_used": efficiency,
    }

# -----------------------------
# 3D 시각화 함수
# -----------------------------
def cuboid_vertices(origin, size):
    x, y, z = origin
    dx, dy, dz = size
    return [
        [(x, y, z), (x+dx, y, z), (x+dx, y+dy, z), (x, y+dy, z)],
        [(x, y, z+dz), (x+dx, y, z+dz), (x+dx, y+dy, z+dz), (x, y+dy, z+dz)],
        [(x, y, z), (x+dx, y, z), (x+dx, y, z+dz), (x, y, z+dz)],
        [(x, y+dy, z), (x+dx, y+dy, z), (x+dx, y+dy, z+dz), (x, y+dy, z+dz)],
        [(x, y, z), (x, y+dy, z), (x, y+dy, z+dz), (x, y, z+dz)],
        [(x+dx, y, z), (x+dx, y+dy, z), (x+dx, y+dy, z+dz), (x+dx, y, z+dz)],
    ]


def add_box(ax, origin, size, color, alpha=0.75, edge="#111827"):
    verts = cuboid_vertices(origin, size)
    poly = Poly3DCollection(verts, facecolors=color, edgecolors=edge, linewidths=0.8, alpha=alpha)
    ax.add_collection3d(poly)


def add_wheel(ax, x, y, z, r=0.18, width=0.08, color="#111827"):
    # 간단한 원통형 바퀴: 두 원 + 연결선
    theta = [i * 2 * math.pi / 32 for i in range(33)]
    ys = [y - width/2, y + width/2]
    for yy in ys:
        xs = [x + r * math.cos(t) for t in theta]
        zs = [z + r * math.sin(t) for t in theta]
        ax.plot(xs, [yy]*len(xs), zs, color=color, linewidth=2.0)
    for t in theta[::4]:
        ax.plot([x + r*math.cos(t), x + r*math.cos(t)], [y-width/2, y+width/2], [z + r*math.sin(t), z + r*math.sin(t)], color=color, linewidth=1.0)


def draw_3d_scene(design, env, sim):
    vehicle_type = design.get("vehicle_type") or infer_vehicle_type(design.get("mobility_name", ""), design.get("purpose", ""), design.get("extra", ""))
    fig = plt.figure(figsize=(9.5, 6.2))
    ax = fig.add_subplot(111, projection="3d")
    ax.set_facecolor("#f8fafc")

    # Ground / slope
    grade = env["grade_deg"]
    slope_z = math.tan(math.radians(min(grade, 28))) * 3.0
    ground = [[(-2.2, -1.6, 0), (4.2, -1.6, slope_z), (4.2, 1.6, slope_z), (-2.2, 1.6, 0)]]
    ax.add_collection3d(Poly3DCollection(ground, facecolors="#d1fae5", edgecolors="#059669", alpha=0.58))

    # Obstacle blocks
    if env["obstacle"] != "없음":
        add_box(ax, (2.0, -0.75, slope_z*0.55), (0.22, 0.35, 0.16), "#9ca3af", 0.85)
        add_box(ax, (2.55, 0.45, slope_z*0.68), (0.28, 0.28, 0.22), "#9ca3af", 0.85)

    # Vehicle position responds to speed achievement and grade
    x0 = 0.0 + min(1.2, sim["speed_achievement"] / 100.0)
    z0 = 0.35 + math.tan(math.radians(min(grade, 28))) * (x0 + 0.8) * 0.15

    # Different simple 3D shapes by mobility type
    if vehicle_type == "scooter":
        # Deck + handlebar
        add_box(ax, (x0-0.6, -0.14, z0), (1.25, 0.28, 0.12), "#3b82f6", 0.85)
        add_box(ax, (x0+0.35, -0.035, z0+0.10), (0.07, 0.07, 0.95), "#111827", 0.92)
        add_box(ax, (x0+0.12, -0.38, z0+1.02), (0.55, 0.07, 0.06), "#111827", 0.92)
        add_wheel(ax, x0-0.52, -0.18, z0-0.05, 0.19, 0.09)
        add_wheel(ax, x0+0.57, -0.18, z0-0.05, 0.19, 0.09)
        label = "Scooter-type mobility running on virtual course"
    elif vehicle_type == "car":
        add_box(ax, (x0-0.8, -0.48, z0), (1.6, 0.96, 0.35), "#2563eb", 0.82)
        add_box(ax, (x0-0.35, -0.38, z0+0.32), (0.75, 0.76, 0.38), "#60a5fa", 0.62)
        for wx in [x0-0.55, x0+0.55]:
            add_wheel(ax, wx, -0.55, z0, 0.18, 0.10)
            add_wheel(ax, wx, 0.55, z0, 0.18, 0.10)
        label = "Car-type mobility climbing and cruising in virtual environment"
    elif vehicle_type == "tracked":
        add_box(ax, (x0-0.75, -0.42, z0+0.10), (1.5, 0.84, 0.42), "#f97316", 0.82)
        add_box(ax, (x0-0.20, -0.15, z0+0.52), (0.48, 0.30, 0.38), "#fdba74", 0.75)
        # track belts
        add_box(ax, (x0-0.88, -0.62, z0-0.02), (1.76, 0.18, 0.20), "#111827", 0.88)
        add_box(ax, (x0-0.88, 0.44, z0-0.02), (1.76, 0.18, 0.20), "#111827", 0.88)
        for wx in [x0-0.55, x0, x0+0.55]:
            add_wheel(ax, wx, -0.70, z0+0.08, 0.13, 0.05)
            add_wheel(ax, wx, 0.70, z0+0.08, 0.13, 0.05)
        label = "Tracked robot passing rough terrain with high torque mode"
    elif vehicle_type == "cleaner":
        add_box(ax, (x0-0.58, -0.46, z0+0.03), (1.16, 0.92, 0.28), "#14b8a6", 0.82)
        add_box(ax, (x0-0.38, -0.32, z0+0.31), (0.76, 0.64, 0.22), "#99f6e4", 0.70)
        add_box(ax, (x0+0.50, -0.38, z0-0.02), (0.13, 0.76, 0.10), "#0f766e", 0.88)
        add_wheel(ax, x0-0.42, -0.52, z0+0.02, 0.16, 0.08)
        add_wheel(ax, x0+0.42, -0.52, z0+0.02, 0.16, 0.08)
        label = "Indoor cleaning robot moving with stable low-speed traction"
    elif vehicle_type == "competition":
        add_box(ax, (x0-0.70, -0.50, z0+0.03), (1.4, 1.0, 0.28), "#ef4444", 0.78)
        add_box(ax, (x0+0.44, -0.32, z0+0.22), (0.38, 0.64, 0.32), "#fca5a5", 0.65)
        add_box(ax, (x0-0.55, -0.28, z0+0.33), (0.50, 0.56, 0.30), "#fb7185", 0.62)
        for wx in [x0-0.48, x0+0.48]:
            add_wheel(ax, wx, -0.58, z0+0.04, 0.17, 0.09)
            add_wheel(ax, wx, 0.58, z0+0.04, 0.17, 0.09)
        label = "Competition robot accelerating while operating intake and shooter modules"
    else:
        add_box(ax, (x0-0.65, -0.42, z0+0.05), (1.3, 0.84, 0.34), "#8b5cf6", 0.78)
        add_box(ax, (x0-0.25, -0.25, z0+0.38), (0.50, 0.50, 0.30), "#c4b5fd", 0.68)
        for wx in [x0-0.45, x0+0.45]:
            add_wheel(ax, wx, -0.50, z0+0.02, 0.16, 0.08)
            add_wheel(ax, wx, 0.50, z0+0.02, 0.16, 0.08)
        label = "Generic mobility platform running in virtual testbed"

    # Motion arrow and status text in English only to avoid font breakage
    ax.quiver(x0-0.9, 1.15, z0+0.35, 1.2, 0, 0.15, color="#dc2626", linewidth=2.2, arrow_length_ratio=0.12)
    ax.text(x0-0.9, 1.25, z0+0.62, "Motion Direction", color="#dc2626", fontsize=10)
    ax.text(-2.05, -1.45, 0.15, f"Road: {env['road']} / Grade: {grade:.1f} deg", color="#111827", fontsize=9)
    ax.text(-2.05, -1.45, 0.38, f"Speed achievement: {sim['speed_achievement']:.0f}%", color="#111827", fontsize=9)
    ax.set_title(label, fontsize=12, pad=12)

    ax.set_xlim(-2.2, 4.2)
    ax.set_ylim(-1.6, 1.6)
    ax.set_zlim(0, 2.0)
    ax.set_xlabel("X: Course Direction")
    ax.set_ylabel("Y: Vehicle Width")
    ax.set_zlabel("Z: Height")
    ax.view_init(elev=22, azim=-58)
    plt.tight_layout()
    st.pyplot(fig)


def draw_graphs(sim):
    fig, axes = plt.subplots(2, 2, figsize=(11, 6.2))
    t = sim["t_values"]

    axes[0, 0].plot(t, sim["speeds"], color="#2563eb", linewidth=2)
    axes[0, 0].set_title("Speed Profile")
    axes[0, 0].set_xlabel("Time (s)")
    axes[0, 0].set_ylabel("Speed (m/s)")
    axes[0, 0].grid(alpha=0.3)

    axes[0, 1].plot(t, sim["distances"], color="#16a34a", linewidth=2)
    axes[0, 1].set_title("Distance Profile")
    axes[0, 1].set_xlabel("Time (s)")
    axes[0, 1].set_ylabel("Distance (m)")
    axes[0, 1].grid(alpha=0.3)

    axes[1, 0].plot(t, sim["batteries"], color="#f59e0b", linewidth=2)
    axes[1, 0].set_title("Battery Remaining")
    axes[1, 0].set_xlabel("Time (s)")
    axes[1, 0].set_ylabel("Battery (%)")
    axes[1, 0].grid(alpha=0.3)

    axes[1, 1].plot(t, sim["torque_usages"], color="#dc2626", linewidth=2)
    axes[1, 1].axhline(100, color="#111827", linestyle="--", linewidth=1)
    axes[1, 1].set_title("Torque Usage")
    axes[1, 1].set_xlabel("Time (s)")
    axes[1, 1].set_ylabel("Torque Usage (%)")
    axes[1, 1].grid(alpha=0.3)

    plt.tight_layout()
    st.pyplot(fig)


def analyze_causes_and_solutions(design, env, sim):
    statuses = sim["statuses"]
    problems = []

    if statuses["속도"] != "PASS":
        problems.append({
            "항목": "목표 속도",
            "주 원인": f"모터 RPM과 기어비로 계산한 예상 최고속도({sim['vmax_mps']:.2f} m/s)가 목표속도({design['target_speed']:.2f} m/s)에 충분히 도달하지 못합니다.",
            "해결방안": "기어비를 낮춰 속도형으로 조정하거나, 모터 RPM이 더 높은 부품을 선택하고 바퀴 반지름을 재검토합니다. 단, 기어비를 낮추면 토크 여유가 감소할 수 있습니다.",
        })
    if statuses["토크"] != "PASS":
        problems.append({
            "항목": "토크 여유",
            "주 원인": f"바퀴당 사용 가능 토크({sim['wheel_torque_each']:.2f} Nm) 대비 요구 토크({sim['required_wheel_torque_each']:.2f} Nm)의 여유율이 {sim['torque_margin']:.1f}%입니다.",
            "해결방안": "기어비를 높여 토크형으로 바꾸거나, 모터 토크가 더 큰 구동계를 사용합니다. 질량과 적재 하중을 줄이는 것도 효과적입니다.",
        })
    if statuses["등판"] != "PASS":
        problems.append({
            "항목": "등판 성능",
            "주 원인": f"설정 경사각({env['grade_deg']:.1f}°)이 최대 등판 가능각({sim['max_grade_deg']:.1f}°)에 너무 근접하거나 초과합니다.",
            "해결방안": "경사 환경에서는 감속비를 높이고, 접지력이 큰 바퀴/궤도 구조를 적용하며, 무게중심을 낮춰 슬립 위험을 줄입니다.",
        })
    if statuses["배터리"] != "PASS":
        problems.append({
            "항목": "배터리 지속성",
            "주 원인": f"예상 주행 가능 시간({sim['runtime_min']:.1f}분)이 목표 주행 시간({env['target_time_min']:.1f}분)에 부족하거나 여유가 작습니다.",
            "해결방안": "배터리 용량(Wh)을 늘리거나 효율 우선 제어를 적용하고, 구름저항이 작은 바퀴와 경량 구조를 사용합니다.",
        })
    if statuses["발열"] != "PASS":
        problems.append({
            "항목": "발열 위험",
            "주 원인": f"부하율이 약 {sim['load_ratio']:.1f}%로 계산되어 모터/드라이버가 장시간 고부하 상태일 가능성이 있습니다.",
            "해결방안": "정격 출력이 더 큰 모터와 드라이버를 사용하거나, 발열 억제 제어·방열판·냉각팬을 적용합니다. 연속 운전 시간을 제한하는 것도 필요합니다.",
        })
    if statuses["제동"] != "PASS":
        problems.append({
            "항목": "제동 안정성",
            "주 원인": f"예상 제동 거리({sim['braking_distance']:.2f} m)가 안전 기준거리({sim['safe_braking_limit']:.2f} m)에 근접하거나 초과합니다.",
            "해결방안": "전자식 브레이크, 회생제동, 기계식 보조 브레이크를 추가하고 고속 주행 시 제한속도 로직을 적용합니다.",
        })

    return problems


def make_report_text(design, env, sim, problems):
    overall = "적합" if sim["total_score"] >= 80 else "조건부 적합" if sim["total_score"] >= 60 else "개선 필요"
    fail_items = [k for k, v in sim["statuses"].items() if v != "PASS"]
    fail_text = ", ".join(fail_items) if fail_items else "없음"

    base = f"""
    해당 모빌리티는 '{design['mobility_name']}' 용도로 설정되었으며, 총 시험 질량은 {sim['mass_total']:.1f} kg, 목표 속도는 {design['target_speed']:.2f} m/s이다.
    가상환경은 {env['road']} 노면, 경사각 {env['grade_deg']:.1f}°, 장애물 수준 {env['obstacle']} 조건으로 구성하였다.
    시뮬레이션 결과 예상 최고속도는 {sim['vmax_mps']:.2f} m/s, 토크 여유율은 {sim['torque_margin']:.1f}%, 예상 주행 가능 시간은 {sim['runtime_min']:.1f}분으로 계산되었다.
    종합 점수는 {sim['total_score']:.1f}/100점이며, 전체 판정은 '{overall}'으로 해석할 수 있다.
    PASS가 아닌 항목은 {fail_text}이다.
    """
    if problems:
        problem_text = "\n".join([f"- {p['항목']}: {p['주 원인']} 해결을 위해 {p['해결방안']}" for p in problems])
    else:
        problem_text = "- 모든 핵심 항목이 PASS로 판정되어 현재 조건에서는 큰 성능 병목이 발견되지 않았다. 다만 실제 제작 전에는 센서 오차, 부품 효율, 노면 변화에 대한 추가 검증이 필요하다."
    return textwrap.dedent(base).strip() + "\n\n주요 원인 및 개선 방향:\n" + problem_text

# -----------------------------
# 앱 본문
# -----------------------------
st.markdown('<div class="main-title">🧪 가상환경 모빌리티 테스트베드</div>', unsafe_allow_html=True)
st.markdown(
    '<div class="sub-desc">초기 설계 도움 시스템의 결과 또는 사용자가 직접 입력한 모빌리티 스펙을 바탕으로, 실제 제작 전 가상환경에서 주행 가능성·성능 한계·위험 요소를 예측합니다.</div>',
    unsafe_allow_html=True,
)

with st.expander("이 시뮬레이터의 역할", expanded=False):
    st.write(
        """
        이 프로그램은 단순 계산기가 아니라, 아직 실제 제작이 어렵거나 미완성 상태인 모빌리티를 가상환경에서 먼저 시험하기 위한 테스트베드입니다.
        초기 설계 도움 시스템에서 복사한 텍스트를 붙여넣어 빠르게 시작할 수 있고, 설계 시스템 없이도 직접 스펙을 입력해 독립적으로 사용할 수 있습니다.
        """
    )

# 세션 상태 초기화
if "design" not in st.session_state:
    st.session_state.design = None
if "last_raw_text" not in st.session_state:
    st.session_state.last_raw_text = ""

input_mode = st.radio(
    "입력 방식 선택",
    ["초기 설계 도움 시스템에서 복사한 텍스트 붙여넣기", "자신의 모빌리티 스펙 직접 입력"],
    horizontal=True,
)

st.divider()

# -----------------------------
# 입력 방식 1: 붙여넣기
# -----------------------------
if input_mode == "초기 설계 도움 시스템에서 복사한 텍스트 붙여넣기":
    st.subheader("1. 설계 데이터 붙여넣기")
    st.write("초기 설계 도움 시스템에서 복사한 테스트베드용 JSON 또는 전체 요약문을 아래에 붙여넣으세요.")
    raw_text = st.text_area(
        "붙여넣기 영역",
        value=st.session_state.last_raw_text,
        height=230,
        placeholder="예: [모빌리티 구동계 초기 설계 요약]\n용도: FRC/대회용 공 수집 및 발사 로봇\n질량: 55kg\n목표 속도: 2.0 m/s\n...",
    )
    c1, c2 = st.columns([1, 1])
    with c1:
        apply_btn = st.button("📥 붙여넣은 설계 데이터 적용", use_container_width=True)
    with c2:
        clear_btn = st.button("🧹 붙여넣기 내용 비우기", use_container_width=True)

    if clear_btn:
        st.session_state.last_raw_text = ""
        st.session_state.design = None
        st.rerun()

    if apply_btn:
        try:
            design = parse_design_text(raw_text)
            st.session_state.design = design
            st.session_state.last_raw_text = raw_text
            st.success("설계 데이터를 성공적으로 적용했습니다. 아래의 모빌리티 스펙과 가상환경 조건을 확인한 뒤 시뮬레이션을 실행하세요.")
        except Exception as e:
            st.error(f"설계 데이터 해석에 실패했습니다: {e}")
            st.info("JSON 형식이 아니어도 됩니다. 단, '용도:', '질량:', '목표 속도:', '구동 바퀴 수:'처럼 항목명과 콜론이 포함된 요약문이면 더 정확히 해석됩니다.")

# -----------------------------
# 입력 방식 2: 직접 입력
# -----------------------------
else:
    st.subheader("1. 자신의 모빌리티 스펙 직접 입력")
    preset_name = st.selectbox("빠른 예시 프리셋", list(DIRECT_PRESETS.keys()))
    preset = DIRECT_PRESETS[preset_name]

    if preset_name == "직접 입력":
        default = {
            "mobility_name": "",
            "purpose": "",
            "mass": 0.0,
            "target_speed": 0.0,
            "wheels": 4,
            "wheel_radius": 0.10,
            "motor_rpm": 3000.0,
            "motor_torque": 0.5,
            "gear_ratio": 18.0,
            "efficiency": 0.85,
            "battery_wh": 500.0,
        }
    else:
        default = preset

    c1, c2 = st.columns(2)
    with c1:
        mobility_name = st.text_input("모빌리티 이름", value=default.get("mobility_name", ""))
        purpose = st.text_area("용도/목표 기능", value=default.get("purpose", ""), height=90)
        mass = st.number_input("총 질량 kg", min_value=0.0, value=float(default.get("mass", 0.0)), step=1.0)
        target_speed = st.number_input("목표 속도 m/s", min_value=0.0, value=float(default.get("target_speed", 0.0)), step=0.1)
        wheels = st.number_input("구동 바퀴 수", min_value=1, max_value=12, value=int(default.get("wheels", 4)), step=1)
    with c2:
        wheel_radius = st.number_input("바퀴 반지름 m", min_value=0.02, value=float(default.get("wheel_radius", 0.10)), step=0.01)
        motor_rpm = st.number_input("모터 기준 RPM", min_value=1.0, value=float(default.get("motor_rpm", 3000.0)), step=100.0)
        motor_torque = st.number_input("모터 연속 토크 Nm", min_value=0.001, value=float(default.get("motor_torque", 0.50)), step=0.05)
        gear_ratio = st.number_input("기어비", min_value=1.0, value=float(default.get("gear_ratio", 18.0)), step=1.0)
        efficiency = st.slider("구동계 효율", 0.40, 0.96, float(default.get("efficiency", 0.85)), 0.01)
        battery_wh = st.number_input("배터리 용량 Wh", min_value=1.0, value=float(default.get("battery_wh", 500.0)), step=50.0)

    extra = st.text_input("기타 특징/장치", value="")
    if st.button("✅ 직접 입력값 적용", use_container_width=True):
        if not mobility_name.strip() or mass <= 0 or target_speed <= 0:
            st.warning("직접 입력 모드에서는 모빌리티 이름, 질량, 목표 속도를 입력해야 합니다.")
        else:
            design = {
                "mobility_name": mobility_name.strip(),
                "purpose": purpose.strip() or mobility_name.strip(),
                "scale": "직접 입력",
                "mass": mass,
                "target_speed": target_speed,
                "wheels": int(wheels),
                "wheel_radius": wheel_radius,
                "motor_rpm": motor_rpm,
                "motor_torque": motor_torque,
                "gear_ratio": gear_ratio,
                "efficiency": efficiency,
                "battery_wh": battery_wh,
                "extra": extra,
                "road": "실내 평지",
                "source_type": "manual",
                "required_power_w_from_design": 0.0,
                "required_wheel_torque_nm_from_design": 0.0,
                "required_wheel_rpm_from_design": 0.0,
            }
            design["vehicle_type"] = infer_vehicle_type(mobility_name, purpose, extra)
            st.session_state.design = design
            st.success("직접 입력한 모빌리티 스펙을 적용했습니다.")

# -----------------------------
# 설계 데이터 요약 및 수정 가능 입력
# -----------------------------
design = st.session_state.design
if design is None:
    st.info("먼저 입력 방식을 선택하고 설계 데이터를 적용하세요. 붙여넣기 없이 직접 입력만으로도 사용할 수 있습니다.")
    st.stop()

st.divider()
st.subheader("2. 적용된 모빌리티 스펙 확인/수정")

c1, c2, c3 = st.columns(3)
with c1:
    design["mobility_name"] = st.text_input("모빌리티 이름", value=design.get("mobility_name", ""))
    design["mass"] = st.number_input("총 질량 kg", min_value=0.1, value=float(design.get("mass", 35.0)), step=1.0, key="edit_mass")
    design["target_speed"] = st.number_input("목표 속도 m/s", min_value=0.01, value=float(design.get("target_speed", 1.0)), step=0.1, key="edit_speed")
with c2:
    design["wheels"] = st.number_input("구동 바퀴 수", min_value=1, max_value=12, value=int(design.get("wheels", 4)), step=1, key="edit_wheels")
    design["wheel_radius"] = st.number_input("바퀴 반지름 m", min_value=0.02, value=float(design.get("wheel_radius", 0.10)), step=0.01, key="edit_wheel_r")
    design["gear_ratio"] = st.number_input("기어비", min_value=1.0, value=float(design.get("gear_ratio", 18.0)), step=1.0, key="edit_gear")
with c3:
    design["motor_rpm"] = st.number_input("모터 기준 RPM", min_value=1.0, value=float(design.get("motor_rpm", 3000.0)), step=100.0, key="edit_rpm")
    design["motor_torque"] = st.number_input("모터 연속 토크 Nm", min_value=0.001, value=float(design.get("motor_torque", 0.5)), step=0.05, key="edit_torque")
    design["battery_wh"] = st.number_input("배터리 용량 Wh", min_value=1.0, value=float(design.get("battery_wh", 500.0)), step=50.0, key="edit_battery")

design["efficiency"] = st.slider("구동계 효율", 0.40, 0.96, float(design.get("efficiency", 0.85)), 0.01, key="edit_eff")
design["purpose"] = st.text_area("용도/설명", value=design.get("purpose", ""), height=80)
design["extra"] = st.text_input("기타 특징/장치", value=design.get("extra", ""))
design["vehicle_type"] = infer_vehicle_type(design.get("mobility_name", ""), design.get("purpose", ""), design.get("extra", ""))
st.session_state.design = design

# -----------------------------
# 가상환경 설정
# -----------------------------
st.divider()
st.subheader("3. 가상환경 조건 설정")

e1, e2, e3 = st.columns(3)
with e1:
    default_road = design.get("road", "실내 평지")
    if default_road not in ROAD_PROFILES:
        default_road = "실내 평지"
    road = st.selectbox("노면 종류", list(ROAD_PROFILES.keys()), index=list(ROAD_PROFILES.keys()).index(default_road))
    grade_deg = st.slider("경사각 °", 0.0, 35.0, 8.0 if road == "실내 평지" else 12.0, 0.5)
with e2:
    obstacle = st.selectbox("장애물 수준", list(OBSTACLE_LEVELS.keys()), index=1)
    payload_kg = st.number_input("추가 적재 하중 kg", min_value=0.0, value=0.0, step=5.0)
with e3:
    target_time_min = st.number_input("목표 주행 시간 min", min_value=0.1, value=10.0, step=1.0)
    control_mode = st.selectbox("전력/센서 제어 방식", list(CONTROL_MODES.keys()), index=0)
    use_air_drag = st.checkbox("공기저항 반영", value=False)

course_length_m = st.number_input("가상 코스 길이 m", min_value=1.0, value=50.0, step=5.0)

env = {
    "road": road,
    "grade_deg": grade_deg,
    "obstacle": obstacle,
    "payload_kg": payload_kg,
    "target_time_min": target_time_min,
    "course_length_m": course_length_m,
    "control_mode": control_mode,
    "use_air_drag": use_air_drag,
    "obstacle_target_weight": OBSTACLE_LEVELS[obstacle] - 1.0,
}

st.markdown(
    f"""
    <div class="info-box">
    <b>가상환경 설명</b><br>
    노면: {road} — {ROAD_PROFILES[road]['desc']}<br>
    제어 방식: {control_mode} — {CONTROL_MODES[control_mode]['desc']}
    </div>
    """,
    unsafe_allow_html=True,
)

# -----------------------------
# 시뮬레이션 실행
# -----------------------------
st.divider()
if st.button("🚀 가상 주행 시뮬레이션 실행", use_container_width=True):
    st.session_state.sim = run_simulation(design, env)
    st.session_state.env = env

if "sim" not in st.session_state:
    st.info("가상환경 조건을 설정한 뒤 [가상 주행 시뮬레이션 실행] 버튼을 누르세요.")
    st.stop()

sim = st.session_state.sim
env = st.session_state.env

# -----------------------------
# 결과 대시보드
# -----------------------------
st.divider()
st.subheader("4. 핵심 성능 예측 결과")

m1, m2, m3, m4 = st.columns(4)
m1.metric("종합 점수", f"{sim['total_score']:.1f} / 100")
m2.metric("예상 최고속도", f"{sim['vmax_mps']:.2f} m/s")
m3.metric("토크 여유율", f"{sim['torque_margin']:.1f} %")
m4.metric("예상 주행시간", f"{sim['runtime_min']:.1f} 분")

m5, m6, m7, m8 = st.columns(4)
m5.metric("최대 등판 가능각", f"{sim['max_grade_deg']:.1f} °")
m6.metric("가속 시간", "불가" if sim['accel_time'] == float('inf') else f"{sim['accel_time']:.1f} s")
m7.metric("발열 위험도", sim["heat_level"])
m8.metric("예상 제동거리", f"{sim['braking_distance']:.2f} m")

# -----------------------------
# PASS / WARNING / FAIL 판정 기준 및 근거
# -----------------------------
st.subheader("5. PASS / WARNING / FAIL 판정 및 근거")
st.caption("각 판정은 입력된 가상환경 조건에서의 상대적 예측입니다. 실제 제작 시 부품 효율, 노면 상태, 센서 오차 등에 따라 달라질 수 있습니다.")

status_box(
    sim["statuses"]["속도"],
    "목표 속도 달성",
    f"목표 대비 {sim['speed_achievement']:.1f}% 달성, 예상 최고속도 {sim['vmax_mps']:.2f} m/s",
    "PASS ≥ 목표속도의 95%, WARNING 75~95%, FAIL < 75%",
    f"모터 RPM {design['motor_rpm']:.0f}, 기어비 {design['gear_ratio']:.1f}:1, 바퀴 반지름 {design['wheel_radius']:.2f} m를 이용해 휠 회전 속도를 계산했습니다.",
)
status_box(
    sim["statuses"]["토크"],
    "토크 여유",
    f"토크 여유율 {sim['torque_margin']:.1f}%, 사용 가능 바퀴토크 {sim['wheel_torque_each']:.2f} Nm / 요구 {sim['required_wheel_torque_each']:.2f} Nm",
    "PASS ≥ 30% 여유, WARNING 0~30%, FAIL < 0%",
    f"경사, 노면 구름저항, 장애물 수준을 반영한 요구 견인력을 바퀴당 요구 토크로 환산했습니다.",
)
status_box(
    sim["statuses"]["등판"],
    "등판 성능",
    f"설정 경사 {env['grade_deg']:.1f}°, 최대 가능 {sim['max_grade_deg']:.1f}°",
    "PASS = 설정 경사보다 3° 이상 여유, WARNING = 통과 가능하지만 여유 3° 미만, FAIL = 설정 경사 초과",
    f"접지 한계와 사용 가능 견인력에서 구름저항을 제외한 값을 이용해 최대 등판각을 추정했습니다.",
)
status_box(
    sim["statuses"]["배터리"],
    "배터리 지속성",
    f"예상 {sim['runtime_min']:.1f}분 / 목표 {env['target_time_min']:.1f}분, 예상 주행거리 {sim['range_m']:.1f} m",
    "PASS ≥ 목표시간 100%, WARNING 70~100%, FAIL < 70%",
    f"평균 소비전력 {sim['avg_power']:.1f} W와 배터리 용량 {design['battery_wh']:.1f} Wh를 이용했습니다.",
)
status_box(
    sim["statuses"]["발열"],
    "발열 위험",
    f"부하율 {sim['load_ratio']:.1f}%, 위험도 {sim['heat_level']}",
    "PASS = 낮음/주의, WARNING = 높음, FAIL = 위험",
    f"모터 토크와 RPM으로 근사 정격출력을 계산하고 평균 소비전력과 비교했습니다.",
)
status_box(
    sim["statuses"]["제동"],
    "제동 안정성",
    f"제동거리 {sim['braking_distance']:.2f} m / 기준 {sim['safe_braking_limit']:.2f} m",
    "PASS = 기준보다 0.5 m 이상 짧음, WARNING = 기준 이내이나 여유 0.5 m 미만, FAIL = 기준 초과",
    f"노면 마찰계수와 목표 속도를 이용해 단순 제동거리를 추정했습니다.",
)

# -----------------------------
# 원인 분석 및 해결방안
# -----------------------------
problems = analyze_causes_and_solutions(design, env, sim)
st.subheader("6. PASS가 아닌 항목의 주 원인 분석 및 해결방안")
if problems:
    for p in problems:
        st.markdown(f"**{p['항목']}**")
        st.write(f"- 주 원인: {p['주 원인']}")
        st.write(f"- 해결방안: {p['해결방안']}")
else:
    st.success("현재 조건에서는 모든 핵심 판정이 PASS입니다. 실제 제작 전에는 부품 실제 효율, 배터리 전압 강하, 센서 지연 등을 추가 검증하는 것이 좋습니다.")

# -----------------------------
# 3D 가상 주행 이미지
# -----------------------------
st.subheader("7. 3D Virtual Driving Scene")
st.caption("이미지 제목과 축 설명은 글자 깨짐을 줄이기 위해 영어로 표시됩니다. 아래에 주요 용어를 한국어로 풀어 설명합니다.")
draw_3d_scene(design, env, sim)

with st.expander("3D 이미지 주요 용어 한국어 설명", expanded=True):
    st.write(
        """
        - **Motion Direction**: 모빌리티가 진행하는 방향입니다.
        - **Course Direction**: 가상 코스의 길이 방향입니다.
        - **Vehicle Width**: 모빌리티의 좌우 폭 방향입니다.
        - **Height**: 지면으로부터의 높이 방향입니다.
        - **Road**: 선택한 노면 조건입니다.
        - **Grade**: 경사각입니다. 값이 클수록 등판에 필요한 토크가 증가합니다.
        - **Speed achievement**: 목표 속도 대비 예상 최고속도의 달성률입니다.
        """
    )

# -----------------------------
# 그래프
# -----------------------------
st.subheader("8. 시간 기반 성능 그래프")
draw_graphs(sim)

with st.expander("그래프 용어 설명", expanded=False):
    st.write(
        """
        - **Speed Profile**: 시간에 따른 속도 변화입니다.
        - **Distance Profile**: 시간에 따른 누적 이동 거리입니다.
        - **Battery Remaining**: 시간에 따른 배터리 잔량 추정값입니다.
        - **Torque Usage**: 사용 가능 토크 대비 요구 토크의 비율입니다. 100%를 넘으면 토크 부족 위험이 커집니다.
        """
    )

# -----------------------------
# 보고서용 해석문
# -----------------------------
st.subheader("9. 보고서용 해석 문장")
report_text = make_report_text(design, env, sim, problems)
st.text_area("자동 생성 해석문", value=report_text, height=260)

# -----------------------------
# 결과 내보내기
# -----------------------------
st.subheader("10. 테스트베드 결과 저장/복사")
result_payload = {
    "program": "virtual_mobility_testbed",
    "created_at": datetime.now().isoformat(timespec="seconds"),
    "design": design,
    "environment": env,
    "simulation_summary": {
        "score": round(sim["total_score"], 2),
        "statuses": sim["statuses"],
        "vmax_mps": round(sim["vmax_mps"], 3),
        "torque_margin_percent": round(sim["torque_margin"], 2),
        "runtime_min": round(sim["runtime_min"], 2),
        "max_grade_deg": round(sim["max_grade_deg"], 2),
        "heat_level": sim["heat_level"],
        "braking_distance_m": round(sim["braking_distance"], 3),
    },
    "problems_and_solutions": problems,
    "report_text": report_text,
}
st.download_button(
    "💾 테스트베드 결과 JSON 다운로드",
    data=json.dumps(result_payload, ensure_ascii=False, indent=2),
    file_name="virtual_mobility_testbed_result.json",
    mime="application/json",
    use_container_width=True,
)

# -----------------------------
# 발전 방향 및 피드백
# -----------------------------
st.divider()
st.subheader("11. 발전 방향 및 피드백")

st.markdown(
    """
    **향후 발전 방향**
    1. 실제 모터의 토크-RPM 곡선과 배터리 전압 강하를 반영하면 예측 정확도를 높일 수 있습니다.
    2. 바퀴형, 궤도형, 스쿠터형, 자동차형 등 외형별 물리 모델을 더 세분화할 수 있습니다.
    3. 장애물 통과, 급정지, 코너링, 미끄러짐 같은 동작을 별도 시나리오로 추가할 수 있습니다.
    4. 초기 설계 도움 시스템과 동일한 데이터 포맷을 유지하면 두 프로그램을 하나의 설계-검증 흐름으로 연결할 수 있습니다.
    5. 실제 제작 후 측정값을 입력해 시뮬레이션 결과와 비교하면 보정 계수를 만들 수 있습니다.
    """
)

feedback = st.text_area(
    "이 시뮬레이터에 추가적으로 원하는 기능이 있다면 개발자에게 알려주세요.",
    placeholder="예: 코너링 안정성 추가, 실제 모터 DB 연동, 3D 이미지 더 구체화, 장애물 통과 애니메이션 등",
    height=120,
)
if st.button("📨 피드백 임시 저장", use_container_width=True):
    if feedback.strip():
        st.success("피드백이 입력되었습니다. Streamlit Cloud에서는 별도 DB가 없으면 서버에 영구 저장되지는 않으므로, 필요한 경우 내용을 복사해 개발자에게 전달하세요.")
    else:
        st.warning("피드백 내용을 입력한 뒤 버튼을 눌러주세요.")

st.caption("주의: 본 테스트베드는 교육·탐구 목적의 성능 예측 도구이며, 실제 제작 안전성 검증을 완전히 대체하지 않습니다.")

