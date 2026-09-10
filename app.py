# virtual_mobility_testbed_streamlit_v3_fixed.py
# Streamlit 실행: streamlit run virtual_mobility_testbed_streamlit_v3_fixed.py

import json
import re
import math
import streamlit as st
import matplotlib.pyplot as plt
import matplotlib.patches as patches
from mpl_toolkits.mplot3d.art3d import Poly3DCollection

st.set_page_config(
    page_title="가상환경 모빌리티 테스트베드",
    layout="wide",
    initial_sidebar_state="expanded"
)

# -----------------------------
# 기본 상수/도움 함수
# -----------------------------
G = 9.81

ROAD_TABLE = {
    "실내 바닥": {"crr": 0.015, "mu": 0.75, "rough": 1.00, "desc": "마찰이 안정적이고 저항이 낮은 실내 바닥"},
    "아스팔트": {"crr": 0.020, "mu": 0.80, "rough": 1.02, "desc": "일반 도로 수준의 표준 노면"},
    "흙길": {"crr": 0.045, "mu": 0.55, "rough": 1.12, "desc": "구름저항과 진동이 증가하는 야외 노면"},
    "자갈길": {"crr": 0.065, "mu": 0.45, "rough": 1.20, "desc": "토크 요구량과 슬립 가능성이 커지는 노면"},
    "험지": {"crr": 0.095, "mu": 0.38, "rough": 1.35, "desc": "등판·장애물·슬립 위험이 모두 큰 환경"},
}

CONTROL_TABLE = {
    "일반 제어": {"eff_delta": 0.00, "heat_delta": 1.00, "speed_limit": 1.00, "desc": "기본 모터 드라이버 제어"},
    "효율 우선 전력 제어": {"eff_delta": 0.04, "heat_delta": 0.92, "speed_limit": 0.96, "desc": "배터리 소모를 줄이는 대신 최고 성능을 약간 제한"},
    "발열 억제 전력 제어": {"eff_delta": 0.02, "heat_delta": 0.78, "speed_limit": 0.88, "desc": "고부하 상황에서 출력을 제한해 열 위험을 낮춤"},
    "토크 우선 가변 제어": {"eff_delta": 0.01, "heat_delta": 0.95, "speed_limit": 0.93, "desc": "경사·험지에서 토크를 우선 확보하는 제어"},
}

PURPOSE_PRESETS = {
    "일반 플랫폼형": {"mass": 35.0, "target_speed": 1.5, "wheels": 4, "wheel_radius": 0.10, "motor_rpm": 3000, "motor_torque": 0.50, "gear_ratio": 18.0, "battery_wh": 480},
    "전동 킥보드형": {"mass": 75.0, "target_speed": 5.0, "wheels": 2, "wheel_radius": 0.13, "motor_rpm": 3000, "motor_torque": 1.30, "gear_ratio": 6.0, "battery_wh": 500},
    "스위피형 실내 청소로봇": {"mass": 75.0, "target_speed": 1.2, "wheels": 2, "wheel_radius": 0.10, "motor_rpm": 3000, "motor_torque": 0.70, "gear_ratio": 22.0, "battery_wh": 900},
    "카고형 고하중 물류로봇": {"mass": 365.0, "target_speed": 1.2, "wheels": 4, "wheel_radius": 0.12, "motor_rpm": 4000, "motor_torque": 1.40, "gear_ratio": 35.0, "battery_wh": 2400},
    "초소형 전기차형": {"mass": 562.0, "target_speed": 22.2, "wheels": 4, "wheel_radius": 0.25, "motor_rpm": 3000, "motor_torque": 8.00, "gear_ratio": 5.0, "battery_wh": 8000},
    "FRC/대회용 로봇": {"mass": 55.0, "target_speed": 2.0, "wheels": 4, "wheel_radius": 0.10, "motor_rpm": 3000, "motor_torque": 0.50, "gear_ratio": 18.0, "battery_wh": 432},
    "궤도형 험지 탐사 로봇": {"mass": 80.0, "target_speed": 0.7, "wheels": 4, "wheel_radius": 0.12, "motor_rpm": 4000, "motor_torque": 1.40, "gear_ratio": 42.0, "battery_wh": 1200},
}

SCALE_MAP = {
    "학생용": "student", "연구용": "research", "산업용": "industry",
    "student": "student", "research": "research", "industry": "industry"
}

ENV_MAP = {
    "단순 이동 / 평지 중심": "실내 바닥",
    "실내": "실내 바닥",
    "실내 바닥": "실내 바닥",
    "평지": "아스팔트",
    "일반": "아스팔트",
    "normal": "아스팔트",
    "indoor": "실내 바닥",
    "obstacle": "자갈길",
    "extreme": "험지",
    "장애물": "자갈길",
    "험지": "험지",
    "흙길": "흙길",
    "자갈길": "자갈길",
    "아스팔트": "아스팔트",
}


def clamp(x, lo, hi):
    return max(lo, min(hi, x))


def to_float(text, default=None):
    if text is None:
        return default
    s = str(text).replace(",", "")
    m = re.search(r"[-+]?\d+(?:\.\d+)?", s)
    if not m:
        return default
    try:
        return float(m.group(0))
    except Exception:
        return default


def normalize_key(s):
    return re.sub(r"\s+", "", str(s).strip())


def line_value(text, labels):
    """한국어 요약문에서 '라벨: 값' 형태 추출. 라벨 변형을 폭넓게 허용."""
    if not text:
        return None
    for raw_line in text.splitlines():
        line = raw_line.strip().lstrip("-•·*").strip()
        if not line or ":" not in line:
            continue
        left, right = line.split(":", 1)
        left_n = normalize_key(left)
        for label in labels:
            if normalize_key(label) == left_n or normalize_key(label) in left_n:
                return right.strip()
    return None


def parse_pasted_design(text):
    """JSON 또는 초기 설계 도움 시스템의 일반 요약문을 테스트베드 입력값으로 변환."""
    if not text or not text.strip():
        raise ValueError("붙여넣기 내용이 비어 있습니다.")

    raw = text.strip()
    data = {}

    # 1) JSON 우선 처리
    if raw.startswith("{") or raw.startswith("["):
        try:
            obj = json.loads(raw)
            # 여러 버전의 키 구조를 최대한 수용
            src_input = obj.get("input", obj.get("user_input", obj.get("design", obj))) if isinstance(obj, dict) else {}
            src_result = obj.get("result", obj.get("calc", obj.get("calculation", {}))) if isinstance(obj, dict) else {}
            src_parts = obj.get("parts", obj.get("part", obj.get("recommended_parts", {}))) if isinstance(obj, dict) else {}
            src_gear = obj.get("gear", obj.get("gear_recommendation", obj.get("recommendation", {}))) if isinstance(obj, dict) else {}

            data["purpose"] = src_input.get("purpose") or obj.get("purpose") or "붙여넣은 모빌리티"
            data["scale"] = src_input.get("scale") or obj.get("scale") or "student"
            data["mass"] = float(src_input.get("mass", obj.get("mass", 35.0)))
            speed = src_input.get("targetSpeedMps", src_input.get("speed_mps", src_input.get("speed", obj.get("speed", 1.5))))
            unit = src_input.get("unit", obj.get("unit", "mps"))
            speed = float(speed)
            if unit in ["kmh", "km/h", "㎞/h"]:
                speed = speed / 3.6
            data["target_speed"] = speed
            data["wheels"] = int(float(src_input.get("wheels", obj.get("wheels", 4))))
            env_raw = src_input.get("env", src_input.get("environment", obj.get("env", obj.get("environment", "실내 바닥"))))
            data["road"] = ENV_MAP.get(str(env_raw).strip(), str(env_raw).strip() or "실내 바닥")
            data["extra"] = src_input.get("extra", obj.get("extra", ""))

            data["required_power"] = float(src_result.get("requiredPowerW", src_result.get("req_power", src_result.get("required_power_w", 0.0))) or 0.0)
            data["required_torque"] = float(src_result.get("requiredWheelTorqueNm", src_result.get("req_tq", src_result.get("required_wheel_torque_nm", 0.0))) or 0.0)
            data["required_rpm"] = float(src_result.get("requiredWheelRpm", src_result.get("req_rpm", src_result.get("required_wheel_rpm", 0.0))) or 0.0)
            data["gear_ratio"] = float(src_result.get("recommendedGearRatio", src_gear.get("best_ratio", obj.get("gear_ratio", 18.0))) or 18.0)
            data["motor_rpm"] = float(src_parts.get("motor_rpm", src_result.get("motorRpm", obj.get("motor_rpm", 3000))) or 3000)
            data["motor_torque"] = float(src_parts.get("motor_nm", src_result.get("motorTorqueNm", obj.get("motor_torque", 0.5))) or 0.5)
            data["wheel_radius"] = float(src_parts.get("wheel_r", src_result.get("wheelRadiusM", obj.get("wheel_radius", 0.10))) or 0.10)
            data["efficiency"] = float(src_result.get("driveEfficiency", obj.get("efficiency", 0.85)) or 0.85)
            data["source_type"] = "JSON"
            return fill_missing_by_purpose(data)
        except Exception:
            # JSON처럼 보였지만 실패하면 일반 요약문으로 재시도
            pass

    # 2) 일반 요약문 처리
    purpose = line_value(raw, ["용도", "목적", "모빌리티 용도", "목표 모빌리티 용도"])
    scale = line_value(raw, ["스케일", "제작 스케일"])
    mass = line_value(raw, ["질량", "총 질량", "예상 총 질량"])
    speed = line_value(raw, ["목표 속도", "속도", "주행 속도"])
    wheels = line_value(raw, ["구동 바퀴 수", "바퀴 수", "구동바퀴수"])
    env = line_value(raw, ["운행 환경", "환경", "주행 환경"])
    extra = line_value(raw, ["기타 요구사항", "요구사항", "기타"])

    # 물리/추천 결과 라벨도 있으면 추출
    req_power = line_value(raw, ["요구 동력", "필요 동력", "required power"])
    req_torque = line_value(raw, ["바퀴당 요구 토크", "요구 토크", "required torque"])
    req_rpm = line_value(raw, ["필요 휠 RPM", "휠 RPM", "required wheel rpm"])
    gear_ratio = line_value(raw, ["추천 감속비", "추천 기어비", "감속비", "기어비"])
    motor_rpm = line_value(raw, ["모터 RPM", "추천 모터 RPM"])
    motor_torque = line_value(raw, ["모터 토크", "기준 토크", "연속토크"])
    wheel_radius = line_value(raw, ["바퀴 반지름", "휠 반지름", "wheel radius"])

    if not any([purpose, mass, speed, wheels, env, extra, req_power, req_torque, req_rpm]):
        raise ValueError("요약문에서 인식 가능한 항목을 찾지 못했습니다. '용도:', '질량:', '목표 속도:', '구동 바퀴 수:' 같은 라벨이 필요합니다.")

    data["purpose"] = purpose or "붙여넣은 모빌리티"
    data["scale"] = SCALE_MAP.get(str(scale).strip(), str(scale or "student"))
    data["mass"] = to_float(mass, 35.0)

    speed_value = to_float(speed, 1.5)
    speed_text = str(speed or "")
    if re.search(r"km\s*/?\s*h|㎞|kmh", speed_text, re.I):
        speed_value = speed_value / 3.6
    data["target_speed"] = speed_value
    data["wheels"] = int(to_float(wheels, 4))
    data["road"] = ENV_MAP.get(str(env).strip(), "실내 바닥")
    data["extra"] = extra or ""
    data["required_power"] = to_float(req_power, 0.0) or 0.0
    data["required_torque"] = to_float(req_torque, 0.0) or 0.0
    data["required_rpm"] = to_float(req_rpm, 0.0) or 0.0
    data["gear_ratio"] = to_float(gear_ratio, None)
    data["motor_rpm"] = to_float(motor_rpm, None)
    data["motor_torque"] = to_float(motor_torque, None)
    data["wheel_radius"] = to_float(wheel_radius, None)
    data["efficiency"] = 0.85
    data["source_type"] = "요약문"
    return fill_missing_by_purpose(data)


def fill_missing_by_purpose(data):
    """붙여넣기에서 빠진 모터/바퀴/기어 값을 용도 기반 기본값으로 보완."""
    purpose = str(data.get("purpose", ""))
    preset_name = "일반 플랫폼형"
    for key in PURPOSE_PRESETS:
        if key != "일반 플랫폼형" and (key in purpose or purpose in key):
            preset_name = key
            break
    if "킥보드" in purpose or "스쿠터" in purpose:
        preset_name = "전동 킥보드형"
    elif "청소" in purpose or "스위피" in purpose:
        preset_name = "스위피형 실내 청소로봇"
    elif "물류" in purpose or "카고" in purpose:
        preset_name = "카고형 고하중 물류로봇"
    elif "전기차" in purpose or "자동차" in purpose or "EV" in purpose.upper():
        preset_name = "초소형 전기차형"
    elif "FRC" in purpose.upper() or "대회" in purpose:
        preset_name = "FRC/대회용 로봇"
    elif "궤도" in purpose or "탐사" in purpose or "험지" in purpose:
        preset_name = "궤도형 험지 탐사 로봇"

    p = PURPOSE_PRESETS[preset_name]
    for k, v in p.items():
        if data.get(k) is None or data.get(k) == "":
            data[k] = v
    # 이상치 보정
    data["mass"] = max(float(data.get("mass", p["mass"])), 0.1)
    data["target_speed"] = max(float(data.get("target_speed", p["target_speed"])), 0.01)
    data["wheels"] = max(int(float(data.get("wheels", p["wheels"]))), 1)
    data["wheel_radius"] = max(float(data.get("wheel_radius", p["wheel_radius"])), 0.02)
    data["motor_rpm"] = max(float(data.get("motor_rpm", p["motor_rpm"])), 100.0)
    data["motor_torque"] = max(float(data.get("motor_torque", p["motor_torque"])), 0.01)
    data["gear_ratio"] = max(float(data.get("gear_ratio", p["gear_ratio"])), 1.0)
    data["battery_wh"] = max(float(data.get("battery_wh", p.get("battery_wh", 500))), 10.0)
    data["efficiency"] = clamp(float(data.get("efficiency", 0.85)), 0.3, 0.98)
    data["preset_hint"] = preset_name
    if data.get("road") not in ROAD_TABLE:
        data["road"] = ENV_MAP.get(str(data.get("road", "")).strip(), "실내 바닥")
    return data


def clear_paste_text():
    st.session_state["paste_text"] = ""
    st.session_state.pop("parsed_data", None)
    st.session_state.pop("parse_message", None)


def apply_parsed_to_session(d):
    keys = ["purpose", "mass", "target_speed", "wheels", "wheel_radius", "motor_rpm", "motor_torque", "gear_ratio", "battery_wh", "efficiency", "road", "extra"]
    for k in keys:
        st.session_state[f"mob_{k}"] = d.get(k)
    st.session_state["parsed_data"] = d
    st.session_state["parse_message"] = f"{d.get('source_type', '데이터')} 형식으로 설계 데이터를 적용했습니다. 부족한 값은 '{d.get('preset_hint', '일반 플랫폼형')}' 기본값으로 보완했습니다."


# -----------------------------
# 시뮬레이션 계산
# -----------------------------
def simulate(spec, env):
    mass = spec["mass"] + env["payload"]
    v_target = spec["target_speed"]
    wheel_r = spec["wheel_radius"]
    wheels = max(int(spec["wheels"]), 1)
    motor_rpm = spec["motor_rpm"]
    motor_torque = spec["motor_torque"]
    ratio = spec["gear_ratio"]
    eff = spec["efficiency"] + CONTROL_TABLE[env["control"]]["eff_delta"]
    eff = clamp(eff, 0.3, 0.96)
    battery_wh = spec["battery_wh"]
    road = ROAD_TABLE[env["road"]]
    control = CONTROL_TABLE[env["control"]]
    angle = math.radians(env["slope_deg"])

    crr = road["crr"] * road["rough"]
    mu = road["mu"]
    obstacle_factor = {"없음": 1.0, "낮음": 1.08, "중간": 1.18, "높음": 1.35}[env["obstacle"]]

    wheel_torque_total = motor_torque * ratio * eff * wheels
    traction_force = wheel_torque_total / max(wheel_r, 0.001)
    traction_limit = mu * mass * G * math.cos(angle)
    usable_force = min(traction_force, traction_limit)

    rolling_force = crr * mass * G * math.cos(angle) * obstacle_factor
    grade_force = mass * G * math.sin(angle)
    aero_force_at_target = 0.5 * 1.225 * 0.75 * 0.8 * (v_target ** 2) if env["air_drag"] else 0.0
    required_force = rolling_force + grade_force + aero_force_at_target
    required_wheel_torque_total = required_force * wheel_r
    required_torque_per_wheel = required_wheel_torque_total / wheels

    net_force = usable_force - required_force
    acceleration = net_force / mass

    wheel_rpm_max = motor_rpm / ratio
    max_speed_by_rpm = (2 * math.pi * wheel_r) * wheel_rpm_max / 60.0 * control["speed_limit"]

    # 실제 최고속도는 RPM 한계와 힘 균형을 모두 고려하되 단순 모델로 제한
    if net_force <= 0:
        predicted_max_speed = max(0.0, min(max_speed_by_rpm, v_target * max(0.05, usable_force / max(required_force, 1e-6))))
        accel_time = float("inf")
    else:
        predicted_max_speed = max_speed_by_rpm
        accel_time = v_target / max(acceleration, 0.05)

    speed_achievement = predicted_max_speed / max(v_target, 0.01) * 100
    torque_margin = (wheel_torque_total - required_wheel_torque_total) / max(required_wheel_torque_total, 1e-6) * 100
    traction_margin = (traction_limit - traction_force) / max(traction_force, 1e-6) * 100

    mech_power = required_force * min(v_target, predicted_max_speed)
    electric_power = mech_power / max(eff, 0.1)
    # 가속/장애물 보정
    avg_power = electric_power * (1.15 + (obstacle_factor - 1) * 0.5)
    runtime_h = battery_wh / max(avg_power, 1.0)
    range_km = runtime_h * min(v_target, predicted_max_speed) * 3.6
    course_time_s = env["course_m"] / max(min(v_target, predicted_max_speed), 0.05)
    course_energy_wh = avg_power * (course_time_s / 3600.0)
    battery_after = clamp(100 - course_energy_wh / battery_wh * 100, 0, 100)

    # 열 위험: 모터 가용 출력 추정 = 토크*각속도*wheels
    motor_total_power = motor_torque * (motor_rpm * 2 * math.pi / 60) * wheels
    load_ratio = avg_power / max(motor_total_power, 1.0)
    heat_index = load_ratio * 100 * control["heat_delta"]

    # 제동 거리
    decel = clamp(mu * G * 0.65, 0.8, 7.0)
    braking_distance = (min(v_target, predicted_max_speed) ** 2) / (2 * decel)

    # 최대 등판각 근사
    available_for_grade = max(usable_force - crr * mass * G, 0.0)
    max_slope_rad = math.asin(clamp(available_for_grade / max(mass * G, 1e-6), 0, 0.95))
    max_slope_deg = math.degrees(max_slope_rad)

    # 시간 데이터
    total_time = min(max(course_time_s + 6, 20), 120)
    steps = 80
    t_list, v_list, x_list, b_list, torque_use_list = [], [], [], [], []
    x = 0.0
    for i in range(steps + 1):
        t = total_time * i / steps
        if math.isfinite(accel_time) and accel_time > 0:
            v = min(predicted_max_speed, v_target, (v_target / accel_time) * t)
        else:
            v = min(predicted_max_speed, v_target) * (1 - math.exp(-t / 8))
        if i > 0:
            dt = total_time / steps
            x += v * dt
        energy_wh = avg_power * (t / 3600.0)
        batt = clamp(100 - energy_wh / battery_wh * 100, 0, 100)
        torque_use = clamp(required_wheel_torque_total / max(wheel_torque_total, 1e-6) * 100, 0, 180)
        t_list.append(t); v_list.append(v); x_list.append(x); b_list.append(batt); torque_use_list.append(torque_use)

    result = {
        "mass_total": mass,
        "wheel_torque_total": wheel_torque_total,
        "required_wheel_torque_total": required_wheel_torque_total,
        "required_torque_per_wheel": required_torque_per_wheel,
        "traction_force": traction_force,
        "traction_limit": traction_limit,
        "usable_force": usable_force,
        "required_force": required_force,
        "rolling_force": rolling_force,
        "grade_force": grade_force,
        "aero_force": aero_force_at_target,
        "net_force": net_force,
        "acceleration": acceleration,
        "predicted_max_speed": predicted_max_speed,
        "speed_achievement": speed_achievement,
        "accel_time": accel_time,
        "torque_margin": torque_margin,
        "traction_margin": traction_margin,
        "avg_power": avg_power,
        "runtime_h": runtime_h,
        "range_km": range_km,
        "course_time_s": course_time_s,
        "course_energy_wh": course_energy_wh,
        "battery_after": battery_after,
        "heat_index": heat_index,
        "braking_distance": braking_distance,
        "max_slope_deg": max_slope_deg,
        "time": t_list,
        "speed_series": v_list,
        "distance_series": x_list,
        "battery_series": b_list,
        "torque_use_series": torque_use_list,
    }
    result["judgements"] = make_judgements(result, spec, env)
    result["score"] = calc_score(result["judgements"])
    return result


def judge_status(value, pass_cond, warn_cond):
    if pass_cond(value):
        return "PASS"
    if warn_cond(value):
        return "WARNING"
    return "FAIL"


def make_judgements(r, spec, env):
    j = []
    # 목표 속도
    status = judge_status(r["speed_achievement"], lambda x: x >= 95, lambda x: x >= 75)
    j.append({
        "항목": "목표 속도",
        "판정": status,
        "결과값": f"{r['speed_achievement']:.1f}% 달성 / 최고 {r['predicted_max_speed']:.2f} m/s",
        "판정 기준": "PASS ≥ 95%, WARNING 75~95%, FAIL < 75%",
        "근거": "모터 RPM, 기어비, 바퀴 반지름으로 계산한 최고속도를 목표 속도와 비교",
        "주 원인": "기어비가 너무 크거나 모터 RPM/출력이 부족해 바퀴 회전수가 목표 속도에 미치지 못함",
        "해결방안": "감속비를 낮추거나 모터 RPM을 높이고, 목표 속도에 맞는 바퀴 반지름을 재검토"
    })
    # 토크
    status = judge_status(r["torque_margin"], lambda x: x >= 30, lambda x: x >= 0)
    j.append({
        "항목": "구동 토크",
        "판정": status,
        "결과값": f"토크 여유율 {r['torque_margin']:.1f}%",
        "판정 기준": "PASS ≥ 30%, WARNING 0~30%, FAIL < 0%",
        "근거": "모터 토크×감속비×효율×구동 바퀴 수와 노면/경사에서 필요한 바퀴 토크 비교",
        "주 원인": "질량, 경사각, 노면저항, 장애물 수준에 비해 모터 토크 또는 감속비가 부족함",
        "해결방안": "감속비 증가, 고토크 모터 적용, 질량 감소, 바퀴 반지름 축소, 구동 바퀴 수 증가 검토"
    })
    # 등판
    slope_margin = r["max_slope_deg"] - env["slope_deg"]
    status = judge_status(slope_margin, lambda x: x >= 5, lambda x: x >= 0)
    j.append({
        "항목": "등판 성능",
        "판정": status,
        "결과값": f"최대 등판각 {r['max_slope_deg']:.1f}° / 설정 {env['slope_deg']:.1f}°",
        "판정 기준": "PASS: 설정 경사보다 5° 이상 여유, WARNING: 통과 가능하지만 여유 부족, FAIL: 통과 불가",
        "근거": "사용 가능한 견인력에서 구름저항을 제외한 힘으로 극복 가능한 경사각 추정",
        "주 원인": "경사로 인한 중력 저항이 증가해 가용 견인력이 부족함",
        "해결방안": "경사 주행용 토크 우선 기어비 적용, 감속비 증가, 접지력 높은 바퀴/트랙 사용"
    })
    # 배터리
    target_min = env["target_runtime_min"]
    runtime_min = r["runtime_h"] * 60
    ratio = runtime_min / max(target_min, 0.1) * 100
    status = judge_status(ratio, lambda x: x >= 100, lambda x: x >= 70)
    j.append({
        "항목": "배터리 지속성",
        "판정": status,
        "결과값": f"예상 {runtime_min:.1f}분 / 목표 {target_min:.1f}분",
        "판정 기준": "PASS ≥ 목표시간 100%, WARNING 70~100%, FAIL < 70%",
        "근거": "평균 소비전력과 배터리 Wh를 이용해 연속 주행 가능 시간 계산",
        "주 원인": "배터리 용량 대비 평균 소비전력이 큼",
        "해결방안": "배터리 Wh 증가, 질량 감소, 효율 높은 모터/감속기 사용, 속도 또는 코스 난이도 조정"
    })
    # 발열
    heat = r["heat_index"]
    status = "PASS" if heat < 60 else ("WARNING" if heat < 100 else "FAIL")
    j.append({
        "항목": "발열 위험",
        "판정": status,
        "결과값": f"발열 지수 {heat:.1f}",
        "판정 기준": "PASS < 60, WARNING 60~100, FAIL ≥ 100",
        "근거": "평균 소비전력을 모터 추정 가용출력과 비교하고 제어 방식의 발열 억제 효과 반영",
        "주 원인": "모터 정격에 비해 요구 출력이 높거나 고부하 주행 시간이 길음",
        "해결방안": "상위 출력 모터/드라이버 사용, 방열 구조 추가, 발열 억제 제어 선택, 감속비 재조정"
    })
    # 제동
    safe_dist = max(1.0, spec["target_speed"] * 0.9)
    bd = r["braking_distance"]
    status = "PASS" if bd <= safe_dist else ("WARNING" if bd <= safe_dist * 1.8 else "FAIL")
    j.append({
        "항목": "제동 안정성",
        "판정": status,
        "결과값": f"제동거리 {bd:.2f} m / 기준 {safe_dist:.2f} m",
        "판정 기준": "PASS: 기준거리 이하, WARNING: 기준의 1.8배 이하, FAIL: 기준의 1.8배 초과",
        "근거": "노면 마찰계수와 목표 속도 기반의 단순 제동거리 계산",
        "주 원인": "속도 또는 질량이 높고 노면 마찰이 낮아 정지 거리가 길어짐",
        "해결방안": "전자식 브레이크/기계식 브레이크 보강, 최고속도 제한, 접지력 높은 타이어 사용"
    })
    return j


def calc_score(judgements):
    score = 0
    for x in judgements:
        score += {"PASS": 16.7, "WARNING": 9.0, "FAIL": 2.0}.get(x["판정"], 0)
    return round(min(score, 100), 1)


def status_color(status):
    return {"PASS": "#0aa66a", "WARNING": "#f0a202", "FAIL": "#e74c3c"}.get(status, "#888")


# -----------------------------
# 시각화
# -----------------------------
def detect_shape(purpose, extra=""):
    s = (str(purpose) + " " + str(extra)).lower()
    if "킥보드" in s or "스쿠터" in s:
        return "scooter"
    if "전기차" in s or "자동차" in s or "ev" in s:
        return "car"
    if "궤도" in s or "트랙" in s or "track" in s or "험지" in s:
        return "tracked"
    if "청소" in s or "스위피" in s:
        return "cleaner"
    if "frc" in s or "대회" in s or "shooter" in s or "intake" in s:
        return "competition"
    return "platform"


def cuboid_data(origin, size):
    ox, oy, oz = origin
    l, w, h = size
    x = [ox, ox+l]
    y = [oy, oy+w]
    z = [oz, oz+h]
    vertices = [
        [(x[0],y[0],z[0]), (x[1],y[0],z[0]), (x[1],y[1],z[0]), (x[0],y[1],z[0])],
        [(x[0],y[0],z[1]), (x[1],y[0],z[1]), (x[1],y[1],z[1]), (x[0],y[1],z[1])],
        [(x[0],y[0],z[0]), (x[1],y[0],z[0]), (x[1],y[0],z[1]), (x[0],y[0],z[1])],
        [(x[0],y[1],z[0]), (x[1],y[1],z[0]), (x[1],y[1],z[1]), (x[0],y[1],z[1])],
        [(x[0],y[0],z[0]), (x[0],y[1],z[0]), (x[0],y[1],z[1]), (x[0],y[0],z[1])],
        [(x[1],y[0],z[0]), (x[1],y[1],z[0]), (x[1],y[1],z[1]), (x[1],y[0],z[1])],
    ]
    return vertices


def add_box(ax, origin, size, color="#4682b4", alpha=0.65):
    pc = Poly3DCollection(cuboid_data(origin, size), facecolors=color, linewidths=0.8, edgecolors="#222", alpha=alpha)
    ax.add_collection3d(pc)


def add_wheel(ax, x, y, z, r=0.18, color="#222"):
    # 간단한 3D 바퀴 표현: 원형 단면 두 개와 축선
    theta = [2*math.pi*i/36 for i in range(37)]
    xs = [x for _ in theta]
    ys = [y + r*math.cos(t) for t in theta]
    zs = [z + r*math.sin(t) for t in theta]
    ax.plot(xs, ys, zs, color=color, linewidth=3)
    ax.plot([x-0.06, x+0.06], [y, y], [z, z], color=color, linewidth=5)


def draw_3d_scene(spec, env, result):
    shape = detect_shape(spec["purpose"], spec.get("extra", ""))
    fig = plt.figure(figsize=(9.5, 5.7))
    ax = fig.add_subplot(111, projection="3d")
    ax.set_facecolor("#f7f9fc")
    ax.view_init(elev=23, azim=-58)
    ax.set_xlim(0, 7); ax.set_ylim(-2.5, 2.5); ax.set_zlim(0, 2.5)
    ax.set_xlabel("X: Course")
    ax.set_ylabel("Y: Width")
    ax.set_zlabel("Z: Height")

    # 경사면/코스
    slope = math.radians(env["slope_deg"])
    xs = [0, 7, 7, 0]
    ys = [-2.2, -2.2, 2.2, 2.2]
    z0 = 0
    z1 = math.tan(slope) * 1.8
    zs = [z0, z1, z1, z0]
    ground = Poly3DCollection([list(zip(xs, ys, zs))], facecolors="#d8e8d2", alpha=0.65, edgecolors="#6b8e23")
    ax.add_collection3d(ground)

    # 장애물
    if env["obstacle"] != "없음":
        h = {"낮음": 0.12, "중간": 0.22, "높음": 0.35}[env["obstacle"]]
        add_box(ax, (4.6, -1.4, z1*0.65), (0.25, 2.8, h), "#9c6b30", 0.75)
        ax.text(4.55, 1.65, z1*0.65+h+0.05, "Obstacle", fontsize=9, color="#333")

    # 모빌리티 위치
    bx, by, bz = 2.4, -0.7, 0.35 + math.tan(slope)*0.65
    if shape == "scooter":
        add_box(ax, (bx, by, bz), (1.8, 0.35, 0.13), "#2e86de", 0.78)  # deck
        add_box(ax, (bx+1.45, by+0.13, bz+0.1), (0.08, 0.08, 1.05), "#555", 0.9)  # handle
        add_wheel(ax, bx+0.2, by+0.18, bz-0.05, 0.22)
        add_wheel(ax, bx+1.65, by+0.18, bz-0.05, 0.22)
        ax.text(bx+0.5, by-0.5, bz+0.55, "Simple 3D Scooter Mobility", fontsize=10)
    elif shape == "car":
        add_box(ax, (bx, by, bz), (2.1, 1.2, 0.45), "#e67e22", 0.72)
        add_box(ax, (bx+0.55, by+0.2, bz+0.42), (0.9, 0.8, 0.45), "#f6c85f", 0.55)
        for wx in [bx+0.25, bx+1.85]:
            add_wheel(ax, wx, by-0.05, bz-0.05, 0.20); add_wheel(ax, wx, by+1.25, bz-0.05, 0.20)
        ax.text(bx+0.35, by-0.7, bz+0.85, "Simple 3D Vehicle Mobility", fontsize=10)
    elif shape == "tracked":
        add_box(ax, (bx, by, bz), (1.9, 1.1, 0.45), "#607d3b", 0.78)
        add_box(ax, (bx-0.05, by-0.12, bz-0.1), (2.0, 0.22, 0.22), "#333", 0.9)
        add_box(ax, (bx-0.05, by+1.0, bz-0.1), (2.0, 0.22, 0.22), "#333", 0.9)
        add_box(ax, (bx+0.75, by+0.35, bz+0.45), (0.16, 0.16, 0.8), "#555", 0.8)
        ax.text(bx+0.2, by-0.7, bz+0.9, "Simple 3D Tracked Mobility", fontsize=10)
    elif shape == "cleaner":
        add_box(ax, (bx, by, bz), (1.6, 1.25, 0.32), "#7f8c8d", 0.75)
        add_box(ax, (bx+0.1, by+0.15, bz+0.32), (1.4, 0.95, 0.18), "#95a5a6", 0.7)
        add_wheel(ax, bx+0.25, by+0.05, bz-0.03, 0.18); add_wheel(ax, bx+1.35, by+1.20, bz-0.03, 0.18)
        ax.text(bx+0.1, by-0.7, bz+0.75, "Simple 3D Cleaning Robot", fontsize=10)
    elif shape == "competition":
        add_box(ax, (bx, by, bz), (1.8, 1.2, 0.50), "#c0392b", 0.68)
        add_box(ax, (bx+1.45, by+0.15, bz+0.25), (0.35, 0.9, 0.25), "#34495e", 0.65)  # intake
        add_box(ax, (bx+0.45, by+0.25, bz+0.55), (0.65, 0.7, 0.55), "#8e44ad", 0.55)  # shooter
        for wx in [bx+0.2, bx+1.55]:
            add_wheel(ax, wx, by-0.05, bz-0.05, 0.19); add_wheel(ax, wx, by+1.25, bz-0.05, 0.19)
        ax.text(bx+0.1, by-0.8, bz+1.15, "Simple 3D Competition Robot", fontsize=10)
    else:
        add_box(ax, (bx, by, bz), (1.8, 1.1, 0.42), "#3498db", 0.72)
        add_box(ax, (bx+0.45, by+0.25, bz+0.42), (0.8, 0.6, 0.25), "#85c1e9", 0.65)
        for wx in [bx+0.25, bx+1.55]:
            add_wheel(ax, wx, by-0.05, bz-0.05, 0.18); add_wheel(ax, wx, by+1.15, bz-0.05, 0.18)
        ax.text(bx+0.2, by-0.7, bz+0.85, "Simple 3D Mobility Platform", fontsize=10)

    ax.quiver(5.5, -1.7, 0.25+z1*0.8, 0.8, 0, 0.15, color="#e74c3c", linewidth=2)
    ax.text(5.45, -1.9, 0.55+z1*0.8, "Driving Direction", color="#e74c3c", fontsize=9)
    ax.text(0.15, -2.1, 1.85, f"Speed: {result['predicted_max_speed']:.2f} m/s", fontsize=9)
    ax.text(0.15, -2.1, 1.65, f"Slope: {env['slope_deg']:.1f} deg", fontsize=9)
    ax.text(0.15, -2.1, 1.45, f"Road: {env['road']}", fontsize=9)
    plt.tight_layout()
    return fig


def draw_graphs(result):
    fig, axes = plt.subplots(2, 2, figsize=(11, 6))
    axes[0,0].plot(result["time"], result["speed_series"], color="#1f77b4")
    axes[0,0].set_title("Speed-Time")
    axes[0,0].set_xlabel("Time (s)"); axes[0,0].set_ylabel("Speed (m/s)"); axes[0,0].grid(True, alpha=0.3)

    axes[0,1].plot(result["time"], result["distance_series"], color="#2ca02c")
    axes[0,1].set_title("Distance-Time")
    axes[0,1].set_xlabel("Time (s)"); axes[0,1].set_ylabel("Distance (m)"); axes[0,1].grid(True, alpha=0.3)

    axes[1,0].plot(result["time"], result["battery_series"], color="#ff7f0e")
    axes[1,0].set_title("Battery Remaining")
    axes[1,0].set_xlabel("Time (s)"); axes[1,0].set_ylabel("Battery (%)"); axes[1,0].grid(True, alpha=0.3)

    axes[1,1].plot(result["time"], result["torque_use_series"], color="#d62728")
    axes[1,1].axhline(100, color="#555", linestyle="--", linewidth=1)
    axes[1,1].set_title("Torque Usage")
    axes[1,1].set_xlabel("Time (s)"); axes[1,1].set_ylabel("Torque Usage (%)"); axes[1,1].grid(True, alpha=0.3)
    plt.tight_layout()
    return fig


def make_report(spec, env, result):
    not_pass = [x for x in result["judgements"] if x["판정"] != "PASS"]
    if not_pass:
        weak = ", ".join([x["항목"] for x in not_pass])
        improve = " / ".join([x["해결방안"] for x in not_pass[:3]])
    else:
        weak = "뚜렷한 취약 항목 없음"
        improve = "현재 조건에서는 목표 성능을 대체로 만족하므로 실제 제작 전 안전율과 부품 정격 검증을 추가하면 됩니다."

    return f"""
해당 모빌리티는 '{spec['purpose']}' 조건에서 총 질량 {result['mass_total']:.1f} kg, 목표 속도 {spec['target_speed']:.2f} m/s, 기어비 {spec['gear_ratio']:.1f}:1을 기준으로 가상 주행을 수행하였다. 
설정 환경은 {env['road']}, 경사각 {env['slope_deg']:.1f}°, 장애물 수준 '{env['obstacle']}'이며, 예측 최고 속도는 {result['predicted_max_speed']:.2f} m/s, 토크 여유율은 {result['torque_margin']:.1f}%, 예상 주행 가능 시간은 {result['runtime_h']*60:.1f}분으로 계산되었다. 
종합 점수는 {result['score']:.1f}/100점이며, PASS가 아닌 주요 항목은 {weak}이다. 개선 방향은 {improve}
""".strip()


# -----------------------------
# UI 시작
# -----------------------------
st.title("🌐 가상환경 모빌리티 테스트베드")
st.caption("초기 설계 도움 시스템에서 복사한 설계 요약문/JSON을 붙여넣거나, 직접 모빌리티 스펙을 입력해 가상환경에서 주행 성능을 예측합니다.")

if "paste_text" not in st.session_state:
    st.session_state["paste_text"] = ""

mode = st.radio(
    "입력 방식을 선택하세요.",
    ["초기 설계 도움 시스템에서 복사한 텍스트 붙여넣기", "자신의 모빌리티 스펙 직접 입력"],
    horizontal=True
)

parsed = st.session_state.get("parsed_data")

if mode == "초기 설계 도움 시스템에서 복사한 텍스트 붙여넣기":
    st.header("1. 설계 데이터 붙여넣기")
    st.write("초기 설계 도움 시스템에서 복사한 **테스트베드용 JSON 또는 전체 요약문**을 아래에 붙여넣으세요.")
    c1, c2 = st.columns([1, 1])
    with c1:
        st.button("🧹 붙여넣기란 비우기", on_click=clear_paste_text, use_container_width=True)
    with c2:
        sample = """[모빌리티 구동계 초기 설계 요약]\n용도: FRC/대회용 공 수집 및 발사 로봇\n스케일: 학생용\n질량: 15.0kg\n목표 속도: 5.0 m/s\n구동 바퀴 수: 4개\n운행 환경: 단순 이동 / 평지 중심\n기타 요구사항: intake, feeder, shooter, waterwheel, 3D 프린팅 브라켓\n\n[물리 모델 결과]\n요구 동력: 104 W\n바퀴당 요구 토크: 0.80 Nm\n필요 휠 RPM: 477.5 RPM\n추천 감속비: 6:1"""
        if st.button("예시 요약문 넣기", use_container_width=True):
            st.session_state["paste_text"] = sample
            st.rerun()

    paste_text = st.text_area(
        "붙여넣기 영역",
        key="paste_text",
        height=260,
        placeholder="여기에 Ctrl+V로 붙여넣으세요. JSON이 아니어도 '용도:', '질량:', '목표 속도:' 같은 요약문이면 해석합니다."
    )

    if st.button("📥 붙여넣은 설계 데이터 적용", type="primary", use_container_width=True):
        try:
            d = parse_pasted_design(st.session_state.get("paste_text", ""))
            apply_parsed_to_session(d)
            st.success(st.session_state["parse_message"])
            st.rerun()
        except Exception as e:
            st.error(f"설계 데이터 해석에 실패했습니다: {e}")
            st.info("JSON이 아니어도 됩니다. 단, '용도:', '질량:', '목표 속도:', '구동 바퀴 수:'처럼 항목명과 콜론(:)이 포함된 요약문이면 더 정확히 해석됩니다.")

    if st.session_state.get("parse_message"):
        st.success(st.session_state["parse_message"])

    if parsed:
        with st.expander("적용된 설계 데이터 요약", expanded=True):
            st.json({k: v for k, v in parsed.items() if k not in ["source_text"]})
else:
    st.header("1. 직접 입력 모드")
    st.info("붙여넣기 없이 아직 제작 전이거나 미완성인 모빌리티의 스펙을 직접 입력해 가상환경에서 시험할 수 있습니다.")

# 입력 기본값 결정
base = st.session_state.get("parsed_data", PURPOSE_PRESETS["일반 플랫폼형"].copy())
if mode == "자신의 모빌리티 스펙 직접 입력" and "manual_initialized" not in st.session_state:
    st.session_state["manual_initialized"] = True
    for k, v in PURPOSE_PRESETS["일반 플랫폼형"].items():
        st.session_state.setdefault(f"mob_{k}", v)
    st.session_state.setdefault("mob_purpose", "직접 입력 모빌리티")
    st.session_state.setdefault("mob_extra", "")
    st.session_state.setdefault("mob_road", "실내 바닥")

# 세션 기본값 세팅
for k, v in {
    "purpose": base.get("purpose", "붙여넣은 모빌리티"),
    "mass": base.get("mass", 35.0),
    "target_speed": base.get("target_speed", 1.5),
    "wheels": base.get("wheels", 4),
    "wheel_radius": base.get("wheel_radius", 0.10),
    "motor_rpm": base.get("motor_rpm", 3000.0),
    "motor_torque": base.get("motor_torque", 0.50),
    "gear_ratio": base.get("gear_ratio", 18.0),
    "battery_wh": base.get("battery_wh", 500.0),
    "efficiency": base.get("efficiency", 0.85),
    "road": base.get("road", "실내 바닥"),
    "extra": base.get("extra", ""),
}.items():
    st.session_state.setdefault(f"mob_{k}", v)

st.header("2. 모빌리티 스펙 확인 및 수정")
left, right = st.columns(2)
with left:
    purpose = st.text_input("모빌리티 이름/용도", key="mob_purpose")
    mass = st.number_input("총 질량 kg", min_value=0.1, max_value=5000.0, step=1.0, key="mob_mass")
    target_speed = st.number_input("목표 속도 m/s", min_value=0.01, max_value=80.0, step=0.1, key="mob_target_speed")
    wheels = st.number_input("구동 바퀴 수", min_value=1, max_value=12, step=1, key="mob_wheels")
    wheel_radius = st.number_input("바퀴 반지름 m", min_value=0.02, max_value=1.5, step=0.01, key="mob_wheel_radius")
with right:
    motor_rpm = st.number_input("모터 RPM", min_value=100.0, max_value=30000.0, step=100.0, key="mob_motor_rpm")
    motor_torque = st.number_input("모터 1개당 연속 토크 Nm", min_value=0.01, max_value=500.0, step=0.05, key="mob_motor_torque")
    gear_ratio = st.number_input("감속비 / 기어비", min_value=1.0, max_value=300.0, step=0.5, key="mob_gear_ratio")
    battery_wh = st.number_input("배터리 용량 Wh", min_value=10.0, max_value=200000.0, step=10.0, key="mob_battery_wh")
    efficiency = st.slider("구동계 효율", min_value=0.30, max_value=0.98, step=0.01, key="mob_efficiency")
extra = st.text_area("기타 특징/장치", key="mob_extra", height=80, placeholder="예: intake, feeder, shooter, LiDAR, 궤도, 방수 구조 등")

st.header("3. 가상환경 조건 설정")
col_a, col_b, col_c = st.columns(3)
with col_a:
    road = st.selectbox("노면 종류", list(ROAD_TABLE.keys()), index=list(ROAD_TABLE.keys()).index(st.session_state.get("mob_road", "실내 바닥")) if st.session_state.get("mob_road", "실내 바닥") in ROAD_TABLE else 0)
    slope_deg = st.slider("경사각 deg", 0.0, 40.0, 5.0, 0.5)
with col_b:
    course_m = st.number_input("코스 길이 m", min_value=1.0, max_value=10000.0, value=50.0, step=5.0)
    obstacle = st.selectbox("장애물 수준", ["없음", "낮음", "중간", "높음"], index=0)
with col_c:
    payload = st.number_input("추가 적재 하중 kg", min_value=0.0, max_value=3000.0, value=0.0, step=1.0)
    target_runtime_min = st.number_input("목표 주행 시간 min", min_value=1.0, max_value=600.0, value=30.0, step=1.0)
control = st.selectbox("전력/반도체 제어 방식", list(CONTROL_TABLE.keys()), index=0)
air_drag = st.checkbox("공기저항 반영", value=True)

spec = {
    "purpose": purpose,
    "mass": float(mass),
    "target_speed": float(target_speed),
    "wheels": int(wheels),
    "wheel_radius": float(wheel_radius),
    "motor_rpm": float(motor_rpm),
    "motor_torque": float(motor_torque),
    "gear_ratio": float(gear_ratio),
    "battery_wh": float(battery_wh),
    "efficiency": float(efficiency),
    "extra": extra,
}
env = {
    "road": road,
    "slope_deg": float(slope_deg),
    "course_m": float(course_m),
    "obstacle": obstacle,
    "payload": float(payload),
    "target_runtime_min": float(target_runtime_min),
    "control": control,
    "air_drag": bool(air_drag),
}

st.header("4. 가상 주행 시뮬레이션 결과")
if st.button("🚗 가상 주행 시뮬레이션 실행", type="primary", use_container_width=True):
    st.session_state["last_result"] = simulate(spec, env)
    st.session_state["last_spec"] = spec
    st.session_state["last_env"] = env

if "last_result" not in st.session_state:
    st.info("입력 방식을 선택하고 설계 데이터를 적용한 뒤, 가상 주행 시뮬레이션을 실행하세요. 붙여넣기 없이 직접 입력만으로도 사용할 수 있습니다.")
    st.stop()

result = st.session_state["last_result"]
spec = st.session_state["last_spec"]
env = st.session_state["last_env"]

m1, m2, m3, m4 = st.columns(4)
m1.metric("종합 점수", f"{result['score']:.1f} / 100")
m2.metric("예상 최고 속도", f"{result['predicted_max_speed']:.2f} m/s")
m3.metric("토크 여유율", f"{result['torque_margin']:.1f}%")
m4.metric("예상 주행 가능 시간", f"{result['runtime_h']*60:.1f}분")

st.subheader("PASS / WARNING / FAIL 판정 기준 및 근거")
for item in result["judgements"]:
    color = status_color(item["판정"])
    st.markdown(
        f"""
<div style='border-left:8px solid {color}; padding:12px 16px; margin:10px 0; background:rgba(128,128,128,0.08); border-radius:8px;'>
<b>{item['항목']}</b> &nbsp; <span style='color:{color}; font-weight:800;'>{item['판정']}</span><br>
<b>결과값:</b> {item['결과값']}<br>
<b>판정 기준:</b> {item['판정 기준']}<br>
<b>근거:</b> {item['근거']}
</div>
""",
        unsafe_allow_html=True,
    )
    if item["판정"] != "PASS":
        st.warning(f"주 원인 분석: {item['주 원인']}")
        st.info(f"해결방안: {item['해결방안']}")

st.subheader("3D Virtual Driving Scene")
st.caption("English labels are used inside the image to avoid font rendering issues.")
st.pyplot(draw_3d_scene(spec, env, result))
with st.expander("이미지 주요 용어 한글 설명", expanded=True):
    st.markdown(
        """
- **Course**: 주행 코스 방향입니다.
- **Width**: 노면의 좌우 폭입니다.
- **Height**: 지면 또는 구조물의 높이입니다.
- **Driving Direction**: 모빌리티가 진행하는 방향입니다.
- **Obstacle**: 설정된 장애물 수준이 반영된 가상 장애물입니다.
- **Speed**: 현재 조건에서 계산된 예상 최고 속도입니다.
- **Slope**: 사용자가 설정한 경사각입니다.
- **Road**: 사용자가 선택한 노면 조건입니다.
"""
    )

st.subheader("성능 그래프")
st.pyplot(draw_graphs(result))

st.subheader("시뮬레이션 로그")
logs = [
    f"[00.0s] 가상 주행 시작: {spec['purpose']}",
    f"[환경] 노면={env['road']}, 경사={env['slope_deg']:.1f}°, 장애물={env['obstacle']}, 코스={env['course_m']:.1f}m",
    f"[구동계] 모터토크={spec['motor_torque']:.2f}Nm, 모터RPM={spec['motor_rpm']:.0f}, 기어비={spec['gear_ratio']:.1f}:1, 바퀴반지름={spec['wheel_radius']:.2f}m",
    f"[계산] 사용 가능 견인력={result['usable_force']:.1f}N, 필요 견인력={result['required_force']:.1f}N",
    f"[결과] 최고속도={result['predicted_max_speed']:.2f}m/s, 토크여유율={result['torque_margin']:.1f}%, 발열지수={result['heat_index']:.1f}",
]
for line in logs:
    st.text(line)

st.subheader("보고서용 해석문")
report = make_report(spec, env, result)
st.text_area("자동 생성 해석문", report, height=180)

st.subheader("발전 방향 및 피드백")
st.markdown(
    """
### 향후 발전 방향
1. 실제 모터의 토크-속도 곡선과 효율맵을 반영하면 최고속도와 발열 예측 정확도를 높일 수 있습니다.
2. 배터리 전압 강하, BMS 제한, 드라이버 전류 제한을 추가하면 고부하 상황을 더 현실적으로 분석할 수 있습니다.
3. 장애물 통과 모델, 서스펜션, 무게중심, 전복 위험도까지 포함하면 테스트베드의 검증 범위가 넓어집니다.
4. 초기 설계 도움 시스템에서 JSON을 표준 형식으로 내보내면 붙여넣기 정확도가 더 높아집니다.
"""
)
feedback = st.text_area("이 시뮬레이터에 추가적으로 원하는 기능이 있다면 개발자에게 알려주세요.", height=100, placeholder="예: 센서 시뮬레이션, 카메라/LiDAR 표시, 실제 부품 DB 연동, 코스 편집 기능 등")
if st.button("피드백 임시 저장"):
    st.success("피드백이 화면 세션에 임시 저장되었습니다. 실제 제출 기능은 추후 서버/DB 연동으로 확장할 수 있습니다.")

export = {
    "spec": spec,
    "environment": env,
    "result_summary": {k: v for k, v in result.items() if k not in ["time", "speed_series", "distance_series", "battery_series", "torque_use_series", "judgements"]},
    "judgements": result["judgements"],
    "report": report,
}
st.download_button(
    "⬇️ 테스트베드 결과 JSON 다운로드",
    data=json.dumps(export, ensure_ascii=False, indent=2),
    file_name="virtual_mobility_testbed_result.json",
    mime="application/json",
    use_container_width=True,
)

