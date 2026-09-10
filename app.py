# -*- coding: utf-8 -*-
"""
가상환경 모빌리티 테스트베드 프로그램 v4
- Streamlit 실행용
- 초기 설계 도움 시스템에서 복사한 JSON 또는 일반 요약문 붙여넣기 지원
- 붙여넣기란 비우기 정상 동작
- Matplotlib 그래프/3D 이미지 내부 텍스트는 영어만 사용하여 한글 깨짐 방지

실행:
streamlit run virtual_mobility_testbed_streamlit_v4_no_korean_break.py
"""

import json
import math
import re
from typing import Dict, Any, Tuple, List

import streamlit as st
import matplotlib.pyplot as plt
from mpl_toolkits.mplot3d.art3d import Poly3DCollection

# -----------------------------------------------------------------------------
# 기본 설정
# -----------------------------------------------------------------------------
st.set_page_config(
    page_title="가상환경 모빌리티 테스트베드",
    page_icon="🧪",
    layout="wide",
)

# Matplotlib 내부에는 한글을 쓰지 않는다. 영어만 사용하면 폰트 깨짐이 발생하지 않는다.
plt.rcParams["font.family"] = "DejaVu Sans"
plt.rcParams["axes.unicode_minus"] = False

G = 9.81

ROAD_PRESETS = {
    "실내 바닥": {"crr": 0.015, "mu": 0.75, "roughness": 0.05},
    "아스팔트": {"crr": 0.020, "mu": 0.80, "roughness": 0.10},
    "흙길": {"crr": 0.050, "mu": 0.55, "roughness": 0.30},
    "자갈길": {"crr": 0.070, "mu": 0.45, "roughness": 0.45},
    "험지": {"crr": 0.110, "mu": 0.35, "roughness": 0.70},
}

DIRECT_PRESETS = {
    "직접 입력": {},
    "전동 킥보드형": dict(purpose="전동 킥보드형 퍼스널 모빌리티", mass=20.0, target_speed=4.2, wheels=2, wheel_radius=0.10, motor_rpm=3000, motor_torque=0.8, gear_ratio=12.0, efficiency=0.85, battery_wh=360.0),
    "스위피형 실내 청소로봇": dict(purpose="스위피형 실내 청소로봇", mass=75.0, target_speed=1.2, wheels=2, wheel_radius=0.10, motor_rpm=3000, motor_torque=0.5, gear_ratio=25.0, efficiency=0.85, battery_wh=720.0),
    "카고형 고하중 물류로봇": dict(purpose="카고형 고하중 물류로봇", mass=365.0, target_speed=1.2, wheels=4, wheel_radius=0.12, motor_rpm=3000, motor_torque=1.4, gear_ratio=35.0, efficiency=0.82, battery_wh=1500.0),
    "초소형 전기차형": dict(purpose="초소형 전기차형 모빌리티", mass=562.0, target_speed=22.2, wheels=4, wheel_radius=0.25, motor_rpm=3000, motor_torque=8.0, gear_ratio=7.0, efficiency=0.88, battery_wh=8000.0),
    "FRC/대회용 로봇": dict(purpose="FRC/대회용 공 수집 및 발사 로봇", mass=55.0, target_speed=2.0, wheels=4, wheel_radius=0.10, motor_rpm=3000, motor_torque=0.5, gear_ratio=18.0, efficiency=0.85, battery_wh=450.0),
    "궤도형 험지 탐사 로봇": dict(purpose="궤도형 험지 탐사 로봇", mass=80.0, target_speed=0.7, wheels=4, wheel_radius=0.12, motor_rpm=3000, motor_torque=1.4, gear_ratio=45.0, efficiency=0.80, battery_wh=1000.0),
}

DEFAULT_SPEC = dict(
    source="manual_or_paste",
    purpose="가상 모빌리티",
    scale="직접 입력",
    mass=50.0,
    target_speed=1.5,
    wheels=4,
    wheel_radius=0.10,
    motor_rpm=3000.0,
    motor_torque=0.5,
    gear_ratio=18.0,
    efficiency=0.85,
    battery_wh=600.0,
    environment="실내 바닥",
    extra="",
    required_power_w=None,
    required_wheel_torque_nm=None,
    required_wheel_rpm=None,
)

# -----------------------------------------------------------------------------
# 유틸리티
# -----------------------------------------------------------------------------
def safe_float(value: Any, default: float = 0.0) -> float:
    """문자열에 kg, m/s, W, Nm, rpm, 개, :1 등이 섞여 있어도 첫 번째 숫자를 추출한다."""
    if value is None:
        return default
    if isinstance(value, (int, float)):
        return float(value)
    text = str(value).replace(",", "")
    m = re.search(r"[-+]?\d+(?:\.\d+)?", text)
    if not m:
        return default
    try:
        return float(m.group(0))
    except Exception:
        return default


def normalize_speed(value: Any, default_mps: float = 1.5) -> float:
    text = str(value).lower()
    num = safe_float(value, default_mps)
    if "km/h" in text or "kmh" in text or "킬로" in text:
        return num / 3.6
    return num


def normalize_env(text: str) -> str:
    t = str(text).lower()
    if any(k in t for k in ["험지", "극한", "산악", "궤도", "extreme"]):
        return "험지"
    if any(k in t for k in ["자갈", "요철", "장애", "obstacle"]):
        return "자갈길"
    if any(k in t for k in ["흙", "농업", "밭", "field", "dirt"]):
        return "흙길"
    if any(k in t for k in ["도로", "아스팔트", "normal", "road"]):
        return "아스팔트"
    return "실내 바닥"


def pick_default_by_purpose(purpose: str) -> Dict[str, Any]:
    p = str(purpose).lower()
    if any(k in p for k in ["킥보드", "스쿠터", "scooter"]):
        return DIRECT_PRESETS["전동 킥보드형"].copy()
    if any(k in p for k in ["청소", "스위피", "clean"]):
        return DIRECT_PRESETS["스위피형 실내 청소로봇"].copy()
    if any(k in p for k in ["물류", "카고", "cargo"]):
        return DIRECT_PRESETS["카고형 고하중 물류로봇"].copy()
    if any(k in p for k in ["전기차", "자동차", "ev", "car"]):
        return DIRECT_PRESETS["초소형 전기차형"].copy()
    if any(k in p for k in ["frc", "대회", "공 수집", "발사"]):
        return DIRECT_PRESETS["FRC/대회용 로봇"].copy()
    if any(k in p for k in ["궤도", "탐사", "험지", "구조"]):
        return DIRECT_PRESETS["궤도형 험지 탐사 로봇"].copy()
    return DEFAULT_SPEC.copy()


def flatten_json(obj: Any, prefix: str = "") -> Dict[str, Any]:
    out = {}
    if isinstance(obj, dict):
        for k, v in obj.items():
            key = f"{prefix}.{k}" if prefix else str(k)
            out.update(flatten_json(v, key))
    else:
        out[prefix] = obj
    return out


def find_first(flat: Dict[str, Any], keys: List[str], default=None):
    lowered = {k.lower(): v for k, v in flat.items()}
    for wanted in keys:
        w = wanted.lower()
        for k, v in lowered.items():
            if k.endswith(w) or w in k:
                return v
    return default

# -----------------------------------------------------------------------------
# 붙여넣기 파서
# -----------------------------------------------------------------------------
def parse_json_text(text: str) -> Dict[str, Any]:
    obj = json.loads(text)
    flat = flatten_json(obj)

    purpose = find_first(flat, ["purpose", "용도", "mobility_purpose"], DEFAULT_SPEC["purpose"])
    spec = pick_default_by_purpose(str(purpose))
    spec.update(DEFAULT_SPEC)
    spec["purpose"] = str(purpose)
    spec["source"] = "json"

    spec["scale"] = str(find_first(flat, ["scale", "스케일"], spec.get("scale", "")))
    spec["mass"] = safe_float(find_first(flat, ["mass", "질량", "weight"], spec["mass"]), spec["mass"])

    speed_val = find_first(flat, ["target_speed", "targetSpeedMps", "speed_mps", "speed", "목표 속도", "속도"], spec["target_speed"])
    unit_val = str(find_first(flat, ["unit", "speed_unit", "단위"], "mps"))
    if unit_val.lower() in ["kmh", "km/h", "킬로미터"]:
        spec["target_speed"] = safe_float(speed_val, spec["target_speed"]) / 3.6
    else:
        spec["target_speed"] = normalize_speed(speed_val, spec["target_speed"])

    spec["wheels"] = int(max(1, safe_float(find_first(flat, ["wheels", "구동 바퀴 수", "바퀴 수"], spec["wheels"]), spec["wheels"])))
    spec["wheel_radius"] = safe_float(find_first(flat, ["wheel_r", "wheelRadiusM", "wheel_radius", "바퀴 반지름"], spec["wheel_radius"]), spec["wheel_radius"])
    spec["motor_rpm"] = safe_float(find_first(flat, ["motor_rpm", "motorRpm", "모터 rpm"], spec["motor_rpm"]), spec["motor_rpm"])
    spec["motor_torque"] = safe_float(find_first(flat, ["motor_nm", "motorTorqueNm", "motor_torque", "모터 토크"], spec["motor_torque"]), spec["motor_torque"])
    spec["gear_ratio"] = safe_float(find_first(flat, ["best_ratio", "recommendedGearRatio", "recommended_ratio", "추천 감속비", "기어비"], spec["gear_ratio"]), spec["gear_ratio"])
    spec["efficiency"] = safe_float(find_first(flat, ["efficiency", "driveEfficiency", "구동계 효율"], spec["efficiency"]), spec["efficiency"])
    spec["battery_wh"] = safe_float(find_first(flat, ["battery_wh", "batteryWh", "배터리 용량"], spec["battery_wh"]), spec["battery_wh"])
    spec["environment"] = normalize_env(str(find_first(flat, ["environment", "env", "운행 환경", "환경"], spec["environment"])))
    spec["extra"] = str(find_first(flat, ["extra", "기타 요구사항", "requirements"], spec["extra"]))

    spec["required_power_w"] = find_first(flat, ["required_power_w", "requiredPowerW", "요구 동력"], None)
    spec["required_wheel_torque_nm"] = find_first(flat, ["required_wheel_torque_nm", "requiredWheelTorqueNm", "바퀴당 요구 토크"], None)
    spec["required_wheel_rpm"] = find_first(flat, ["required_wheel_rpm", "requiredWheelRpm", "필요 휠 RPM"], None)
    if spec["required_power_w"] is not None:
        spec["required_power_w"] = safe_float(spec["required_power_w"], 0.0)
    if spec["required_wheel_torque_nm"] is not None:
        spec["required_wheel_torque_nm"] = safe_float(spec["required_wheel_torque_nm"], 0.0)
    if spec["required_wheel_rpm"] is not None:
        spec["required_wheel_rpm"] = safe_float(spec["required_wheel_rpm"], 0.0)
    return spec


def parse_summary_text(text: str) -> Dict[str, Any]:
    """
    초기 설계 도움 시스템에서 복사한 일반 요약문 파싱.
    예:
    [모빌리티 구동계 초기 설계 요약]
    용도: FRC/대회용 공 수집 및 발사 로봇
    질량: 15.0kg
    목표 속도: 5.0 m/s
    구동 바퀴 수: 4개
    ...
    """
    lines = [line.strip() for line in text.replace("\r", "\n").split("\n") if line.strip()]
    kv = {}
    for line in lines:
        # 마크다운 기호 제거
        clean = line.strip(" -*•\t")
        if ":" in clean:
            k, v = clean.split(":", 1)
        elif "：" in clean:
            k, v = clean.split("：", 1)
        else:
            continue
        key = k.strip().replace("**", "").replace("[", "").replace("]", "")
        val = v.strip().replace("**", "")
        if key:
            kv[key] = val

    purpose = kv.get("용도") or kv.get("목적") or kv.get("모빌리티 용도") or DEFAULT_SPEC["purpose"]
    spec = pick_default_by_purpose(purpose)
    base = DEFAULT_SPEC.copy()
    base.update(spec)
    spec = base
    spec["source"] = "summary_text"
    spec["purpose"] = purpose

    if "스케일" in kv:
        spec["scale"] = kv["스케일"]
    if "질량" in kv:
        spec["mass"] = safe_float(kv["질량"], spec["mass"])
    if "목표 속도" in kv:
        spec["target_speed"] = normalize_speed(kv["목표 속도"], spec["target_speed"])
    elif "속도" in kv:
        spec["target_speed"] = normalize_speed(kv["속도"], spec["target_speed"])
    if "구동 바퀴 수" in kv:
        spec["wheels"] = int(max(1, safe_float(kv["구동 바퀴 수"], spec["wheels"])))
    elif "바퀴 수" in kv:
        spec["wheels"] = int(max(1, safe_float(kv["바퀴 수"], spec["wheels"])))
    if "운행 환경" in kv:
        spec["environment"] = normalize_env(kv["운행 환경"])
    elif "환경" in kv:
        spec["environment"] = normalize_env(kv["환경"])
    if "기타 요구사항" in kv:
        spec["extra"] = kv["기타 요구사항"]

    # 물리 모델 결과
    for name, key in [
        ("요구 동력", "required_power_w"),
        ("바퀴당 요구 토크", "required_wheel_torque_nm"),
        ("필요 휠 RPM", "required_wheel_rpm"),
        ("추천 감속비", "gear_ratio"),
        ("추천 기어비", "gear_ratio"),
        ("모터 RPM", "motor_rpm"),
        ("모터 토크", "motor_torque"),
        ("바퀴 반지름", "wheel_radius"),
        ("구동계 효율", "efficiency"),
        ("배터리 용량", "battery_wh"),
    ]:
        if name in kv:
            spec[key] = safe_float(kv[name], spec.get(key, 0.0) or 0.0)

    # 본문 전체에서 보조적으로 숫자 추출: "추천 감속비: 18:1" 등
    if spec.get("gear_ratio", 0) <= 0:
        m = re.search(r"(?:추천\s*(?:감속비|기어비)|기어비)\s*[:：]\s*(\d+(?:\.\d+)?)", text)
        if m:
            spec["gear_ratio"] = float(m.group(1))

    return spec


def parse_pasted_design(text: str) -> Tuple[Dict[str, Any], str]:
    raw = (text or "").strip()
    if not raw:
        raise ValueError("붙여넣은 내용이 비어 있습니다.")

    # 중요: '['로 시작하는 요약문도 있으므로 JSON 실패 시 반드시 일반 요약문 파싱으로 넘어간다.
    json_error = None
    if raw.startswith("{") or raw.startswith("["):
        try:
            spec = parse_json_text(raw)
            return spec, "JSON 형식으로 해석했습니다."
        except Exception as e:
            json_error = str(e)

    spec = parse_summary_text(raw)

    # 최소 필수값 검증
    if spec.get("mass", 0) <= 0:
        raise ValueError("질량 값을 찾지 못했습니다. 예: 질량: 55kg")
    if spec.get("target_speed", 0) <= 0:
        raise ValueError("목표 속도 값을 찾지 못했습니다. 예: 목표 속도: 2.0 m/s")
    if spec.get("wheels", 0) <= 0:
        raise ValueError("구동 바퀴 수를 찾지 못했습니다. 예: 구동 바퀴 수: 4개")

    msg = "일반 요약문 형식으로 해석했습니다."
    if json_error:
        msg += f" JSON 해석은 실패했지만 요약문 파싱으로 처리했습니다."
    return spec, msg

# -----------------------------------------------------------------------------
# 물리 시뮬레이션
# -----------------------------------------------------------------------------
def infer_body_type(purpose: str, extra: str = "") -> str:
    t = f"{purpose} {extra}".lower()
    if any(k in t for k in ["킥보드", "스쿠터", "scooter"]):
        return "scooter"
    if any(k in t for k in ["전기차", "자동차", "ev", "car"]):
        return "car"
    if any(k in t for k in ["궤도", "트랙", "track", "험지", "탐사"]):
        return "tracked"
    if any(k in t for k in ["청소", "스위피", "clean"]):
        return "cleaner"
    if any(k in t for k in ["frc", "대회", "공 수집", "발사", "intake", "shooter"]):
        return "competition"
    return "platform"


def simulate(spec: Dict[str, Any], env: Dict[str, Any]) -> Dict[str, Any]:
    mass = max(1.0, float(spec["mass"]) + float(env.get("payload", 0.0)))
    target_speed = max(0.05, float(spec["target_speed"]))
    wheels = max(1, int(spec["wheels"]))
    r = max(0.03, float(spec["wheel_radius"]))
    motor_rpm = max(1.0, float(spec["motor_rpm"]))
    motor_torque = max(0.01, float(spec["motor_torque"]))
    gear_ratio = max(1.0, float(spec["gear_ratio"]))
    eff = min(0.98, max(0.30, float(spec["efficiency"])))
    battery_wh = max(1.0, float(spec["battery_wh"]))

    road = ROAD_PRESETS[env["road"]]
    crr = road["crr"]
    mu = road["mu"]
    roughness = road["roughness"]
    grade_deg = float(env["grade_deg"])
    course_m = max(1.0, float(env["course_m"]))
    target_time_s = max(1.0, float(env["target_time_s"]))
    obstacle_level = env["obstacle_level"]
    control_mode = env["control_mode"]

    obstacle_factor = {"없음": 1.00, "낮음": 1.08, "중간": 1.18, "높음": 1.32}.get(obstacle_level, 1.0)
    if control_mode == "효율 우선 제어":
        eff *= 1.04
        torque_limit_factor = 0.92
    elif control_mode == "발열 억제 제어":
        eff *= 1.02
        torque_limit_factor = 0.85
    elif control_mode == "토크 우선 제어":
        torque_limit_factor = 1.08
    else:
        torque_limit_factor = 1.00
    eff = min(eff, 0.98)

    wheel_torque_total = motor_torque * gear_ratio * eff * wheels * torque_limit_factor
    drive_force = wheel_torque_total / r
    traction_limit = mu * mass * G * math.cos(math.radians(grade_deg))
    usable_force = min(drive_force, traction_limit)

    rolling = crr * mass * G * math.cos(math.radians(grade_deg)) * obstacle_factor
    grade_force = mass * G * math.sin(math.radians(grade_deg))
    aero = 0.5 * 1.225 * 0.8 * 0.7 * target_speed * target_speed if target_speed > 4 else 0.0
    resist = rolling + grade_force + aero
    net_force = usable_force - resist
    accel = max(0.0, net_force / mass)

    wheel_rpm = motor_rpm / gear_ratio
    max_speed_by_rpm = (2 * math.pi * r) * (wheel_rpm / 60.0)
    reachable_speed = min(max_speed_by_rpm, max(0.0, math.sqrt(max(0.0, (usable_force - rolling - grade_force) / max(0.0001, 0.5 * 1.225 * 0.8 * 0.7))) if target_speed > 4 else max_speed_by_rpm))

    if accel <= 0.001:
        accel_time = float("inf")
    else:
        accel_time = target_speed / accel

    achieved_speed = min(target_speed, max_speed_by_rpm) if net_force > 0 else 0.0
    speed_ratio = achieved_speed / target_speed
    required_wheel_torque_total = resist * r
    torque_margin = (wheel_torque_total - required_wheel_torque_total) / max(required_wheel_torque_total, 0.001) * 100
    torque_usage = required_wheel_torque_total / max(wheel_torque_total, 0.001) * 100

    mech_power = max(resist * max(achieved_speed, 0.1), 0.0)
    elec_power = mech_power / max(eff, 0.1) + 15.0
    battery_time_h = battery_wh / max(elec_power, 1.0)
    battery_range_m = battery_time_h * 3600.0 * achieved_speed
    energy_course_wh = elec_power * (course_m / max(achieved_speed, 0.1)) / 3600.0

    # 발열 위험도: 부하율 기반. 모터 정격 출력 추정 = torque * rpm 기반에 여유 반영
    motor_mech_w = motor_torque * (motor_rpm * 2 * math.pi / 60.0) * wheels
    load_ratio = elec_power / max(motor_mech_w, 1.0)

    if load_ratio < 0.60:
        heat = "낮음"
    elif load_ratio < 0.85:
        heat = "주의"
    elif load_ratio < 1.10:
        heat = "높음"
    else:
        heat = "위험"

    # 제동 거리
    braking_mu = max(0.20, mu - roughness * 0.12)
    decel = braking_mu * G * 0.65
    braking_distance = target_speed * target_speed / max(2 * decel, 0.001)

    # 시간 기반 간단 프로파일
    dt = 0.5
    total_s = min(max(target_time_s, course_m / max(achieved_speed, 0.1) + 5), 180)
    times, speeds, distances, batteries, torques = [], [], [], [], []
    x = 0.0
    v = 0.0
    battery_used = 0.0
    t = 0.0
    while t <= total_s:
        if net_force <= 0:
            v = 0.0
        else:
            v = min(target_speed, max_speed_by_rpm, v + accel * dt)
        x += v * dt
        battery_used += elec_power * dt / 3600.0
        times.append(t)
        speeds.append(v)
        distances.append(min(x, course_m))
        batteries.append(max(0.0, 100.0 * (1 - battery_used / battery_wh)))
        torques.append(min(200.0, torque_usage))
        if x >= course_m:
            break
        t += dt

    # 판정
    def judge_speed():
        if speed_ratio >= 0.95:
            return "PASS"
        if speed_ratio >= 0.75:
            return "WARNING"
        return "FAIL"

    def judge_torque():
        if torque_margin >= 30:
            return "PASS"
        if torque_margin >= 0:
            return "WARNING"
        return "FAIL"

    def judge_grade():
        if net_force > 0 and torque_margin >= 15:
            return "PASS"
        if net_force > 0:
            return "WARNING"
        return "FAIL"

    def judge_battery():
        if battery_time_h * 3600 >= target_time_s:
            return "PASS"
        if battery_time_h * 3600 >= target_time_s * 0.7:
            return "WARNING"
        return "FAIL"

    def judge_heat():
        if heat in ["낮음"]:
            return "PASS"
        if heat in ["주의", "높음"]:
            return "WARNING"
        return "FAIL"

    def judge_brake():
        limit = max(1.0, target_speed * 1.2)
        if braking_distance <= limit:
            return "PASS"
        if braking_distance <= limit * 1.8:
            return "WARNING"
        return "FAIL"

    judgments = {
        "목표 속도": {
            "status": judge_speed(),
            "value": f"달성률 {speed_ratio*100:.1f}% / 예상 {achieved_speed:.2f} m/s",
            "criterion": "PASS ≥ 95%, WARNING 75~95%, FAIL < 75%",
            "basis": "기어비에 따른 휠 RPM 한계와 저항력을 반영한 예상 속도를 목표 속도와 비교했습니다.",
        },
        "토크 여유": {
            "status": judge_torque(),
            "value": f"여유율 {torque_margin:.1f}% / 사용률 {torque_usage:.1f}%",
            "criterion": "PASS ≥ 30%, WARNING 0~30%, FAIL < 0%",
            "basis": "모터 토크 × 기어비 × 효율로 계산한 바퀴 토크와 주행 저항 토크를 비교했습니다.",
        },
        "등판/노면 통과": {
            "status": judge_grade(),
            "value": f"경사 {grade_deg:.1f}° / 순가용 힘 {net_force:.1f} N",
            "criterion": "PASS: 힘 여유와 토크 여유 존재, WARNING: 통과 가능하나 여유 부족, FAIL: 순가용 힘 부족",
            "basis": "구름저항, 경사저항, 장애물 보정, 접지 한계를 함께 고려했습니다.",
        },
        "배터리 지속성": {
            "status": judge_battery(),
            "value": f"예상 {battery_time_h*60:.1f}분 / 목표 {target_time_s/60:.1f}분",
            "criterion": "PASS ≥ 목표 시간, WARNING ≥ 목표의 70%, FAIL < 목표의 70%",
            "basis": "평균 소비전력과 배터리 Wh를 이용해 예상 운용 시간을 계산했습니다.",
        },
        "발열 위험": {
            "status": judge_heat(),
            "value": f"위험도 {heat} / 부하율 {load_ratio*100:.1f}%",
            "criterion": "PASS: 낮음, WARNING: 주의·높음, FAIL: 위험",
            "basis": "예상 전력 요구량을 모터 회전수·토크 기반의 출력 추정값과 비교했습니다.",
        },
        "제동 안정성": {
            "status": judge_brake(),
            "value": f"예상 제동거리 {braking_distance:.2f} m",
            "criterion": "PASS: 기준거리 이하, WARNING: 기준의 1.8배 이하, FAIL: 그 이상",
            "basis": "노면 마찰계수와 목표 속도를 이용해 정지거리를 추정했습니다.",
        },
    }

    score_map = {"PASS": 100, "WARNING": 65, "FAIL": 25}
    score = sum(score_map[j["status"]] for j in judgments.values()) / len(judgments)

    return {
        "mass": mass,
        "achieved_speed": achieved_speed,
        "target_speed": target_speed,
        "max_speed_by_rpm": max_speed_by_rpm,
        "accel": accel,
        "accel_time": accel_time,
        "wheel_torque_total": wheel_torque_total,
        "required_wheel_torque_total": required_wheel_torque_total,
        "torque_margin": torque_margin,
        "torque_usage": torque_usage,
        "net_force": net_force,
        "elec_power": elec_power,
        "battery_time_h": battery_time_h,
        "battery_range_m": battery_range_m,
        "energy_course_wh": energy_course_wh,
        "heat": heat,
        "load_ratio": load_ratio,
        "braking_distance": braking_distance,
        "times": times,
        "speeds": speeds,
        "distances": distances,
        "batteries": batteries,
        "torques": torques,
        "judgments": judgments,
        "score": score,
        "body_type": infer_body_type(spec.get("purpose", ""), spec.get("extra", "")),
        "env": env,
    }

# -----------------------------------------------------------------------------
# 원인/해결방안
# -----------------------------------------------------------------------------
def make_failure_feedback(judgments: Dict[str, Dict[str, str]], spec: Dict[str, Any]) -> List[str]:
    feedback = []
    for item, j in judgments.items():
        if j["status"] == "PASS":
            continue
        if item == "목표 속도":
            feedback.append("**목표 속도 미달 원인:** 기어비가 너무 크거나 모터 RPM이 부족해 휠 회전수가 목표 속도에 못 미칠 수 있습니다. **해결:** 감속비를 낮추거나, 더 높은 RPM 모터·큰 바퀴를 검토하세요.")
        elif item == "토크 여유":
            feedback.append("**토크 여유 부족 원인:** 질량, 경사, 노면저항에 비해 모터 토크 또는 감속비가 부족합니다. **해결:** 감속비 증가, 모터 토크 증가, 구동 바퀴 수 증가, 질량 절감을 검토하세요.")
        elif item == "등판/노면 통과":
            feedback.append("**등판/노면 통과 위험 원인:** 경사저항·구름저항·장애물 보정값이 커져 순가용 힘이 부족합니다. **해결:** 토크형 기어비, 접지력 높은 바퀴/궤도, 저속 토크 우선 제어를 적용하세요.")
        elif item == "배터리 지속성":
            feedback.append("**배터리 지속성 부족 원인:** 평균 소비전력에 비해 배터리 Wh가 작습니다. **해결:** 배터리 용량 확대, 효율 우선 제어, 질량 절감, 목표 속도 하향을 검토하세요.")
        elif item == "발열 위험":
            feedback.append("**발열 위험 원인:** 요구 출력이 모터/드라이버가 지속적으로 감당하기 어려운 수준입니다. **해결:** 정격 출력이 큰 모터, 방열판·팬, 발열 억제 제어, 감속비 재조정을 검토하세요.")
        elif item == "제동 안정성":
            feedback.append("**제동 안정성 위험 원인:** 속도 또는 질량이 커서 정지거리가 길어졌습니다. **해결:** 전자식 브레이크, 회생제동, 마찰 브레이크, 저속 제한, 타이어 마찰 개선을 검토하세요.")
    if not feedback:
        feedback.append("모든 핵심 항목이 PASS입니다. 실제 제작 단계에서는 센서 오차, 배터리 전압 강하, 부품 공차를 추가로 검증하면 좋습니다.")
    return feedback

# -----------------------------------------------------------------------------
# 시각화: 그래프 내부 한글 금지
# -----------------------------------------------------------------------------
def plot_profiles(result: Dict[str, Any]):
    fig, axs = plt.subplots(2, 2, figsize=(11, 7))
    t = result["times"]
    axs[0, 0].plot(t, result["speeds"], color="#2563eb", linewidth=2)
    axs[0, 0].set_title("Speed Profile")
    axs[0, 0].set_xlabel("Time (s)")
    axs[0, 0].set_ylabel("Speed (m/s)")
    axs[0, 0].grid(True, alpha=0.3)

    axs[0, 1].plot(t, result["distances"], color="#16a34a", linewidth=2)
    axs[0, 1].set_title("Distance Profile")
    axs[0, 1].set_xlabel("Time (s)")
    axs[0, 1].set_ylabel("Distance (m)")
    axs[0, 1].grid(True, alpha=0.3)

    axs[1, 0].plot(t, result["batteries"], color="#f59e0b", linewidth=2)
    axs[1, 0].set_title("Battery State")
    axs[1, 0].set_xlabel("Time (s)")
    axs[1, 0].set_ylabel("Battery (%)")
    axs[1, 0].set_ylim(0, 105)
    axs[1, 0].grid(True, alpha=0.3)

    axs[1, 1].plot(t, result["torques"], color="#dc2626", linewidth=2)
    axs[1, 1].axhline(100, color="#111827", linestyle="--", linewidth=1)
    axs[1, 1].set_title("Torque Usage")
    axs[1, 1].set_xlabel("Time (s)")
    axs[1, 1].set_ylabel("Usage (%)")
    axs[1, 1].grid(True, alpha=0.3)

    fig.tight_layout()
    st.pyplot(fig)
    plt.close(fig)


def cuboid_data(origin, size):
    ox, oy, oz = origin
    l, w, h = size
    x = [ox, ox + l]
    y = [oy, oy + w]
    z = [oz, oz + h]
    return [
        [(x[0], y[0], z[0]), (x[1], y[0], z[0]), (x[1], y[1], z[0]), (x[0], y[1], z[0])],
        [(x[0], y[0], z[1]), (x[1], y[0], z[1]), (x[1], y[1], z[1]), (x[0], y[1], z[1])],
        [(x[0], y[0], z[0]), (x[1], y[0], z[0]), (x[1], y[0], z[1]), (x[0], y[0], z[1])],
        [(x[0], y[1], z[0]), (x[1], y[1], z[0]), (x[1], y[1], z[1]), (x[0], y[1], z[1])],
        [(x[0], y[0], z[0]), (x[0], y[1], z[0]), (x[0], y[1], z[1]), (x[0], y[0], z[1])],
        [(x[1], y[0], z[0]), (x[1], y[1], z[0]), (x[1], y[1], z[1]), (x[1], y[0], z[1])],
    ]


def add_box(ax, origin, size, color, alpha=0.65):
    faces = cuboid_data(origin, size)
    poly = Poly3DCollection(faces, facecolors=color, edgecolors="#111827", linewidths=0.8, alpha=alpha)
    ax.add_collection3d(poly)


def add_wheel(ax, x, y, z, radius=0.22, width=0.12, color="#111827"):
    # 단순 원통형 바퀴. 텍스트 없음.
    import numpy as np
    theta = np.linspace(0, 2 * np.pi, 32)
    yy = [y - width / 2, y + width / 2]
    for yyv in yy:
        xs = x + radius * np.cos(theta)
        zs = z + radius * np.sin(theta)
        ax.plot(xs, [yyv] * len(theta), zs, color=color, linewidth=2)
    for i in range(0, len(theta), 4):
        ax.plot([x + radius * math.cos(theta[i])] * 2, yy, [z + radius * math.sin(theta[i])] * 2, color=color, linewidth=1)


def plot_3d_mobility(spec: Dict[str, Any], result: Dict[str, Any]):
    fig = plt.figure(figsize=(9, 6))
    ax = fig.add_subplot(111, projection="3d")
    ax.set_title("Virtual Mobility Testbed")
    ax.set_xlabel("Course X")
    ax.set_ylabel("Course Y")
    ax.set_zlabel("Height")

    body_type = result["body_type"]
    grade = result["env"]["grade_deg"]
    road_color = "#9ca3af"
    if result["env"]["road"] in ["흙길", "자갈길", "험지"]:
        road_color = "#a16207"

    # 경사로/주행면
    slope_z = math.tan(math.radians(grade)) * 3.0
    road = [[(-1.5, -1.2, 0), (3.5, -1.2, slope_z), (3.5, 1.2, slope_z), (-1.5, 1.2, 0)]]
    ax.add_collection3d(Poly3DCollection(road, facecolors=road_color, edgecolors="#374151", alpha=0.35))

    status = "PASS" if result["score"] >= 80 else ("WARNING" if result["score"] >= 55 else "FAIL")
    color = {"PASS": "#22c55e", "WARNING": "#f59e0b", "FAIL": "#ef4444"}[status]

    # 차체 종류별 간단 3D 형상
    if body_type == "scooter":
        add_box(ax, (0.0, -0.18, 0.35), (1.8, 0.36, 0.10), color, 0.75)
        add_box(ax, (1.35, -0.05, 0.45), (0.08, 0.10, 1.0), "#64748b", 0.9)
        add_wheel(ax, 0.25, 0, 0.28, 0.24, 0.12)
        add_wheel(ax, 1.55, 0, 0.28, 0.24, 0.12)
    elif body_type == "car":
        add_box(ax, (0.0, -0.55, 0.38), (2.2, 1.1, 0.38), color, 0.70)
        add_box(ax, (0.55, -0.38, 0.76), (0.85, 0.76, 0.35), "#60a5fa", 0.45)
        for x in [0.35, 1.85]:
            add_wheel(ax, x, -0.62, 0.32, 0.24, 0.12)
            add_wheel(ax, x, 0.62, 0.32, 0.24, 0.12)
    elif body_type == "tracked":
        add_box(ax, (0.0, -0.45, 0.45), (1.9, 0.9, 0.42), color, 0.70)
        add_box(ax, (-0.1, -0.62, 0.20), (2.1, 0.18, 0.22), "#111827", 0.85)
        add_box(ax, (-0.1, 0.44, 0.20), (2.1, 0.18, 0.22), "#111827", 0.85)
        add_box(ax, (0.85, -0.15, 0.87), (0.18, 0.30, 0.55), "#64748b", 0.85)
    elif body_type == "cleaner":
        add_box(ax, (0.0, -0.55, 0.25), (1.55, 1.1, 0.35), color, 0.70)
        add_box(ax, (0.25, -0.35, 0.60), (0.60, 0.70, 0.22), "#38bdf8", 0.50)
        add_wheel(ax, 0.25, -0.60, 0.25, 0.18, 0.10)
        add_wheel(ax, 1.25, 0.60, 0.25, 0.18, 0.10)
    elif body_type == "competition":
        add_box(ax, (0.0, -0.55, 0.30), (1.8, 1.1, 0.42), color, 0.65)
        add_box(ax, (1.55, -0.35, 0.42), (0.45, 0.70, 0.25), "#f97316", 0.65)
        add_box(ax, (0.60, -0.20, 0.75), (0.55, 0.40, 0.40), "#8b5cf6", 0.65)
        for x in [0.25, 1.45]:
            add_wheel(ax, x, -0.62, 0.28, 0.20, 0.10)
            add_wheel(ax, x, 0.62, 0.28, 0.20, 0.10)
    else:
        add_box(ax, (0.0, -0.50, 0.35), (1.8, 1.0, 0.35), color, 0.70)
        for x in [0.30, 1.50]:
            add_wheel(ax, x, -0.58, 0.30, 0.21, 0.10)
            add_wheel(ax, x, 0.58, 0.30, 0.21, 0.10)

    # 진행 방향 화살표와 영어 상태 라벨
    ax.quiver(2.1, 0, 0.55, 0.75, 0, math.tan(math.radians(grade)) * 0.75, color="#2563eb", linewidth=3)
    ax.text(2.05, 0.10, 1.05, f"Status: {status}", color="#111827", fontsize=10)
    ax.text(2.05, 0.10, 0.88, f"Speed: {result['achieved_speed']:.2f} m/s", color="#111827", fontsize=9)
    ax.text(2.05, 0.10, 0.72, f"Grade: {grade:.1f} deg", color="#111827", fontsize=9)

    ax.set_xlim(-1.0, 3.2)
    ax.set_ylim(-1.4, 1.4)
    ax.set_zlim(0, 1.8)
    ax.view_init(elev=22, azim=-55)
    fig.tight_layout()
    st.pyplot(fig)
    plt.close(fig)

# -----------------------------------------------------------------------------
# 세션 상태
# -----------------------------------------------------------------------------
if "paste_text" not in st.session_state:
    st.session_state["paste_text"] = ""
if "parsed_spec" not in st.session_state:
    st.session_state["parsed_spec"] = None
if "parse_message" not in st.session_state:
    st.session_state["parse_message"] = ""

# -----------------------------------------------------------------------------
# 화면 시작
# -----------------------------------------------------------------------------
st.title("🧪 가상환경 모빌리티 테스트베드 프로그램")
st.caption("실제 제작이 어렵거나 미완성 상태인 모빌리티를 가상환경에서 먼저 구현하고, 주행 가능성·성능 한계·개선 방향을 예측합니다.")

with st.expander("사용 방법", expanded=False):
    st.markdown(
        """
1. **초기 설계 도움 시스템 연동**: 초기 설계 도움 시스템에서 복사한 JSON 또는 전체 요약문을 붙여넣고 적용합니다.  
2. **직접 스펙 입력**: 아직 설계 시스템을 쓰지 않았거나 직접 만든 모빌리티의 값을 입력합니다.  
3. 가상환경 조건을 설정한 뒤 시뮬레이션을 실행합니다.  
4. 그래프와 3D 이미지는 한글 깨짐을 막기 위해 내부 표기를 영어로 표시하고, 아래에 주요 용어를 한국어로 설명합니다.
        """
    )

input_mode = st.radio(
    "입력 방식을 선택하세요.",
    ["초기 설계 도움 시스템에서 복사한 텍스트 붙여넣기", "자신의 모빌리티 스펙 직접 입력"],
    horizontal=True,
)

spec = DEFAULT_SPEC.copy()

# -----------------------------------------------------------------------------
# 입력 방식 1: 붙여넣기
# -----------------------------------------------------------------------------
if input_mode == "초기 설계 도움 시스템에서 복사한 텍스트 붙여넣기":
    st.header("1. 설계 데이터 붙여넣기")
    st.write("초기 설계 도움 시스템에서 복사한 테스트베드용 JSON 또는 전체 요약문을 아래에 붙여넣으세요.")

    c1, c2, c3 = st.columns([1, 1, 4])
    with c1:
        if st.button("🧹 붙여넣기란 비우기", use_container_width=True):
            st.session_state["paste_text"] = ""
            st.session_state["parsed_spec"] = None
            st.session_state["parse_message"] = ""
            st.rerun()
    with c2:
        if st.button("🧪 예시 넣기", use_container_width=True):
            st.session_state["paste_text"] = """[모빌리티 구동계 초기 설계 요약]
용도: FRC/대회용 공 수집 및 발사 로봇
스케일: 학생용
질량: 15.0kg
목표 속도: 5.0 m/s
구동 바퀴 수: 4개
운행 환경: 단순 이동 / 평지 중심
기타 요구사항: intake, feeder, shooter, waterwheel, 3D 프린팅 브라켓

[물리 모델 결과]
요구 동력: 104 W
바퀴당 요구 토크: 0.42 Nm
필요 휠 RPM: 477.5 RPM
추천 감속비: 6:1
모터 RPM: 3000 rpm
모터 토크: 0.50 Nm
바퀴 반지름: 0.10 m
구동계 효율: 0.85
배터리 용량: 450 Wh
"""
            st.rerun()

    st.text_area(
        "붙여넣기 영역",
        key="paste_text",
        height=260,
        placeholder="예: [모빌리티 구동계 초기 설계 요약]\n용도: ...\n질량: ...\n목표 속도: ...",
    )

    if st.button("📥 붙여넣은 설계 데이터 적용", use_container_width=True):
        try:
            parsed, msg = parse_pasted_design(st.session_state["paste_text"])
            st.session_state["parsed_spec"] = parsed
            st.session_state["parse_message"] = msg
            st.success(msg)
        except Exception as e:
            st.session_state["parsed_spec"] = None
            st.error(f"설계 데이터 해석에 실패했습니다: {e}")
            st.info("JSON이 아니어도 됩니다. 단, '용도:', '질량:', '목표 속도:', '구동 바퀴 수:'처럼 항목명과 콜론이 포함된 요약문이면 더 정확히 해석됩니다.")

    if st.session_state.get("parsed_spec"):
        spec = st.session_state["parsed_spec"].copy()
        st.success(st.session_state.get("parse_message", "설계 데이터를 적용했습니다."))
        with st.expander("적용된 설계 데이터 확인", expanded=True):
            st.json(spec, expanded=False)
    else:
        st.warning("아직 적용된 설계 데이터가 없습니다. 붙여넣기 후 '붙여넣은 설계 데이터 적용' 버튼을 눌러주세요.")

# -----------------------------------------------------------------------------
# 입력 방식 2: 직접 입력
# -----------------------------------------------------------------------------
else:
    st.header("1. 자신의 모빌리티 스펙 직접 입력")
    preset_name = st.selectbox("빠른 프리셋", list(DIRECT_PRESETS.keys()))
    p = DIRECT_PRESETS.get(preset_name, {}).copy()
    base = DEFAULT_SPEC.copy()
    base.update(p)
    spec = base
    spec["source"] = "manual"

    c1, c2, c3 = st.columns(3)
    with c1:
        spec["purpose"] = st.text_input("모빌리티 이름/용도", value="" if preset_name == "직접 입력" else spec["purpose"])
        spec["mass"] = st.number_input("총 질량 kg", min_value=0.1, value=float(spec["mass"]), step=1.0)
        spec["target_speed"] = st.number_input("목표 속도 m/s", min_value=0.01, value=float(spec["target_speed"]), step=0.1)
        spec["wheels"] = int(st.number_input("구동 바퀴 수", min_value=1, value=int(spec["wheels"]), step=1))
    with c2:
        spec["wheel_radius"] = st.number_input("바퀴 반지름 m", min_value=0.02, value=float(spec["wheel_radius"]), step=0.01)
        spec["motor_rpm"] = st.number_input("모터 RPM", min_value=1.0, value=float(spec["motor_rpm"]), step=100.0)
        spec["motor_torque"] = st.number_input("모터 1개당 연속 토크 Nm", min_value=0.01, value=float(spec["motor_torque"]), step=0.1)
        spec["gear_ratio"] = st.number_input("기어비", min_value=1.0, value=float(spec["gear_ratio"]), step=1.0)
    with c3:
        spec["efficiency"] = st.slider("구동계 효율", min_value=0.30, max_value=0.98, value=float(spec["efficiency"]), step=0.01)
        spec["battery_wh"] = st.number_input("배터리 용량 Wh", min_value=1.0, value=float(spec["battery_wh"]), step=50.0)
        spec["extra"] = st.text_area("기타 특징/요구사항", value="" if preset_name == "직접 입력" else spec.get("extra", ""), height=110)

# -----------------------------------------------------------------------------
# 가상환경 설정
# -----------------------------------------------------------------------------
st.header("2. 가상환경 조건 설정")
col_a, col_b, col_c, col_d, col_e = st.columns(5)
with col_a:
    road = st.selectbox("노면 종류", list(ROAD_PRESETS.keys()), index=list(ROAD_PRESETS.keys()).index(spec.get("environment", "실내 바닥")) if spec.get("environment", "실내 바닥") in ROAD_PRESETS else 0)
with col_b:
    grade_deg = st.slider("경사각 °", min_value=0.0, max_value=35.0, value=8.0, step=1.0)
with col_c:
    course_m = st.number_input("코스 길이 m", min_value=1.0, value=30.0, step=5.0)
with col_d:
    obstacle_level = st.selectbox("장애물 수준", ["없음", "낮음", "중간", "높음"])
with col_e:
    target_time_s = st.number_input("목표 운용 시간 s", min_value=1.0, value=60.0, step=10.0)

col_f, col_g = st.columns(2)
with col_f:
    payload = st.number_input("추가 적재 하중 kg", min_value=0.0, value=0.0, step=5.0)
with col_g:
    control_mode = st.selectbox("전력/제어 방식", ["일반 제어", "효율 우선 제어", "발열 억제 제어", "토크 우선 제어"])

env = dict(road=road, grade_deg=grade_deg, course_m=course_m, obstacle_level=obstacle_level, target_time_s=target_time_s, payload=payload, control_mode=control_mode)

# -----------------------------------------------------------------------------
# 시뮬레이션 실행
# -----------------------------------------------------------------------------
st.header("3. 시뮬레이션 실행 및 결과")
run = st.button("🚗 가상 주행 시뮬레이션 실행", type="primary", use_container_width=True)

if run:
    if input_mode.startswith("초기") and not st.session_state.get("parsed_spec"):
        st.warning("먼저 붙여넣은 설계 데이터를 적용하세요. 또는 직접 입력 모드를 선택해 사용할 수 있습니다.")
        st.stop()
    if not spec.get("purpose"):
        spec["purpose"] = "이름 미입력 모빌리티"

    result = simulate(spec, env)

    # 요약 카드
    k1, k2, k3, k4, k5 = st.columns(5)
    k1.metric("종합 점수", f"{result['score']:.0f} / 100")
    k2.metric("예상 속도", f"{result['achieved_speed']:.2f} m/s")
    k3.metric("토크 여유", f"{result['torque_margin']:.1f}%")
    k4.metric("예상 운용 시간", f"{result['battery_time_h']*60:.1f}분")
    k5.metric("제동 거리", f"{result['braking_distance']:.2f} m")

    st.subheader("PASS / WARNING / FAIL 판정 기준과 근거")
    rows = []
    for item, j in result["judgments"].items():
        rows.append({
            "항목": item,
            "판정": j["status"],
            "결과값": j["value"],
            "판정 기준": j["criterion"],
            "근거": j["basis"],
        })
    st.dataframe(rows, use_container_width=True, hide_index=True)

    st.subheader("PASS가 아닌 항목의 주 원인 분석 및 해결방안")
    for fb in make_failure_feedback(result["judgments"], spec):
        st.markdown(f"- {fb}")

    st.subheader("3D Virtual Driving View")
    plot_3d_mobility(spec, result)
    st.markdown(
        """
**3D 이미지 주요 용어 설명**  
- **Virtual Mobility Testbed**: 가상환경 모빌리티 테스트베드  
- **Status**: 종합 주행 상태 판정  
- **Speed**: 가상환경에서 예측된 주행 속도  
- **Grade**: 주행로 경사각  
- **Course X / Course Y / Height**: 주행 방향, 좌우 방향, 높이 축  
- 초록색 차체는 상대적으로 안정, 노란색은 주의, 빨간색은 위험 가능성이 큼을 의미합니다.
        """
    )

    st.subheader("성능 변화 그래프")
    plot_profiles(result)
    st.markdown(
        """
**그래프 주요 용어 설명**  
- **Speed Profile**: 시간에 따른 속도 변화  
- **Distance Profile**: 시간에 따른 이동 거리  
- **Battery State**: 배터리 잔량 변화  
- **Torque Usage**: 필요한 토크가 사용 가능한 토크에서 차지하는 비율  
- 그래프 내부 표기는 한글 깨짐 방지를 위해 영어로 표시했습니다.
        """
    )

    st.subheader("시뮬레이션 로그")
    log_lines = [
        f"[00.0s] 시뮬레이션 시작: {spec.get('purpose', '모빌리티')}",
        f"[입력] 질량 {result['mass']:.1f} kg, 목표 속도 {result['target_speed']:.2f} m/s, 노면 {road}, 경사 {grade_deg:.1f}°",
        f"[구동계] 모터 RPM {spec['motor_rpm']:.0f}, 모터 토크 {spec['motor_torque']:.2f} Nm, 기어비 {spec['gear_ratio']:.1f}:1, 효율 {spec['efficiency']:.2f}",
        f"[결과] 예상 속도 {result['achieved_speed']:.2f} m/s, 토크 여유 {result['torque_margin']:.1f}%, 발열 위험 {result['heat']}",
        f"[제동] 예상 제동거리 {result['braking_distance']:.2f} m",
        f"[종합] 테스트베드 적합도 {result['score']:.0f}/100점",
    ]
    st.code("\n".join(log_lines), language="text")

    st.subheader("보고서용 해석문")
    non_pass = [k for k, v in result["judgments"].items() if v["status"] != "PASS"]
    if non_pass:
        weak = ", ".join(non_pass)
        report = (
            f"해당 모빌리티는 '{spec.get('purpose', '모빌리티')}' 조건에서 질량 {result['mass']:.1f} kg, "
            f"목표 속도 {result['target_speed']:.2f} m/s, 경사 {grade_deg:.1f}°의 가상환경을 기준으로 평가되었다. "
            f"시뮬레이션 결과 종합 점수는 {result['score']:.0f}/100점이며, 특히 {weak} 항목에서 개선이 필요하다. "
            f"따라서 실제 제작 전에는 모터 토크, 감속비, 배터리 용량, 바퀴 접지력 등을 조정하여 성능 여유를 확보하는 과정이 필요하다."
        )
    else:
        report = (
            f"해당 모빌리티는 '{spec.get('purpose', '모빌리티')}' 조건에서 가상환경 테스트베드 평가 결과 모든 핵심 항목이 PASS로 나타났다. "
            f"이는 설정된 노면, 경사, 속도, 배터리 조건에서 기본 주행 가능성이 비교적 높다는 것을 의미한다. "
            f"다만 실제 제작 시에는 센서 오차, 부품 공차, 배터리 전압 강하, 반복 주행에 따른 발열을 추가 검증해야 한다."
        )
    st.write(report)

    st.subheader("발전 방향 제시")
    st.markdown(
        """
- 실제 부품 데이터시트를 기반으로 모터 토크-속도 곡선과 효율맵을 추가하면 예측 정확도가 높아집니다.
- 장애물 높이, 문턱, 회전 반경, 차체 무게중심을 반영하면 가상환경이 더 실제에 가까워집니다.
- 배터리 전압 강하와 모터 온도 상승 모델을 넣으면 장시간 주행 예측이 강화됩니다.
- 여러 기어비 후보를 한 번에 비교하는 기능을 추가하면 설계 최적화 도구로도 확장할 수 있습니다.
        """
    )

    st.subheader("추가 기능 요청 / 개발자 피드백")
    feedback = st.text_area(
        "이 시뮬레이터에 추가적으로 원하는 기능이 있다면 개발자에게 알려주세요.",
        placeholder="예: 장애물 높이 입력 기능, 여러 설계안 비교, 결과 PDF 저장, 실제 부품 DB 연동 등",
        height=120,
    )
    if st.button("📨 피드백 임시 저장"):
        st.success("피드백이 화면 세션에 임시 저장되었습니다. 실제 전송 기능은 추후 서버 또는 데이터베이스 연동 시 추가할 수 있습니다.")
        st.session_state["developer_feedback"] = feedback

    result_export = {
        "spec": spec,
        "environment": env,
        "summary": {
            "score": result["score"],
            "achieved_speed_mps": result["achieved_speed"],
            "torque_margin_percent": result["torque_margin"],
            "battery_time_min": result["battery_time_h"] * 60,
            "braking_distance_m": result["braking_distance"],
            "heat_risk": result["heat"],
        },
        "judgments": result["judgments"],
        "report_text": report,
    }
    st.download_button(
        "💾 테스트베드 결과 JSON 다운로드",
        data=json.dumps(result_export, ensure_ascii=False, indent=2),
        file_name="virtual_mobility_testbed_result.json",
        mime="application/json",
        use_container_width=True,
    )

else:
    st.info("입력 방식을 선택하고 필요한 값을 적용한 뒤, '가상 주행 시뮬레이션 실행' 버튼을 누르세요.")

