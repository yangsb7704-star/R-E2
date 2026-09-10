import json
import math
import streamlit as st
import matplotlib.pyplot as plt
import matplotlib.patches as patches

# =========================================================
# 가상환경 모빌리티 테스트베드 프로그램
# - Thonny에서 편집 가능
# - Streamlit Cloud / 로컬 Streamlit 실행 가능
# 실행 예시: streamlit run virtual_mobility_testbed_streamlit.py
# =========================================================

st.set_page_config(
    page_title="가상환경 모빌리티 테스트베드",
    page_icon="🧪",
    layout="wide"
)

# -----------------------------
# 기본 상수 및 프리셋
# -----------------------------
G = 9.81
DEFAULT_EFF = 0.85

ROAD_DB = {
    "실내 매끄러운 바닥": {"crr": 0.012, "mu": 0.75, "rough": 0.00, "desc": "실내 안내로봇, 청소로봇에 가까운 조건"},
    "일반 아스팔트": {"crr": 0.018, "mu": 0.70, "rough": 0.02, "desc": "킥보드, 소형 이동체의 일반 도로 조건"},
    "콘크리트/창고 바닥": {"crr": 0.016, "mu": 0.72, "rough": 0.01, "desc": "물류창고, 실험실, 공장 바닥 조건"},
    "흙길": {"crr": 0.045, "mu": 0.55, "rough": 0.10, "desc": "농업로봇, 야외 저속 주행 조건"},
    "자갈길/요철 노면": {"crr": 0.070, "mu": 0.45, "rough": 0.18, "desc": "진동과 토크 요구가 큰 장애물 노면"},
    "험지/산악 지형": {"crr": 0.100, "mu": 0.38, "rough": 0.28, "desc": "산악 구조 로봇, 탐사 로봇에 가까운 고난도 조건"},
}

SCENARIOS = {
    "실내 평지 검증": {"road": "실내 매끄러운 바닥", "grade": 2.0, "course": 30.0, "time": 40.0, "obstacle": 0.0},
    "실내 문턱/완만한 경사": {"road": "실내 매끄러운 바닥", "grade": 8.0, "course": 25.0, "time": 45.0, "obstacle": 0.15},
    "물류창고 고하중 주행": {"road": "콘크리트/창고 바닥", "grade": 5.0, "course": 60.0, "time": 80.0, "obstacle": 0.10},
    "대회장 급가속 주행": {"road": "실내 매끄러운 바닥", "grade": 3.0, "course": 20.0, "time": 25.0, "obstacle": 0.05},
    "야외 흙길 주행": {"road": "흙길", "grade": 10.0, "course": 50.0, "time": 80.0, "obstacle": 0.25},
    "험지 등판 주행": {"road": "험지/산악 지형", "grade": 25.0, "course": 35.0, "time": 90.0, "obstacle": 0.40},
    "도로형 고속 주행": {"road": "일반 아스팔트", "grade": 3.0, "course": 120.0, "time": 90.0, "obstacle": 0.02},
}

DIRECT_PRESETS = {
    "직접 입력": {},
    "전동 킥보드형": {"purpose": "전동 킥보드형 퍼스널 모빌리티", "mass": 85.0, "target_speed": 4.2, "wheels": 2, "wheel_radius": 0.10, "motor_rpm": 3000, "motor_torque": 0.8, "gear_ratio": 8.0, "battery_wh": 360.0},
    "스위피형 실내 청소로봇": {"purpose": "스위피형 실내 청소로봇", "mass": 75.0, "target_speed": 1.2, "wheels": 2, "wheel_radius": 0.10, "motor_rpm": 3000, "motor_torque": 0.5, "gear_ratio": 22.0, "battery_wh": 480.0},
    "카고형 고하중 물류로봇": {"purpose": "카고형 고하중 물류로봇", "mass": 365.0, "target_speed": 1.2, "wheels": 4, "wheel_radius": 0.12, "motor_rpm": 4000, "motor_torque": 1.4, "gear_ratio": 30.0, "battery_wh": 1200.0},
    "초소형 전기차형": {"purpose": "초소형 전기차형 모빌리티", "mass": 562.0, "target_speed": 22.2, "wheels": 4, "wheel_radius": 0.25, "motor_rpm": 3000, "motor_torque": 8.0, "gear_ratio": 6.0, "battery_wh": 6000.0},
    "산악 구조 로봇": {"purpose": "산악 구조 보조 로봇", "mass": 50.0, "target_speed": 0.5, "wheels": 4, "wheel_radius": 0.12, "motor_rpm": 4000, "motor_torque": 1.4, "gear_ratio": 45.0, "battery_wh": 700.0},
    "농업 방제 로봇": {"purpose": "농업용 방제 로봇", "mass": 150.0, "target_speed": 1.0, "wheels": 4, "wheel_radius": 0.18, "motor_rpm": 3000, "motor_torque": 2.0, "gear_ratio": 35.0, "battery_wh": 1500.0},
    "FRC/대회용 로봇": {"purpose": "FRC/대회용 공 수집 및 발사 로봇", "mass": 55.0, "target_speed": 2.0, "wheels": 4, "wheel_radius": 0.10, "motor_rpm": 3000, "motor_torque": 0.5, "gear_ratio": 16.0, "battery_wh": 350.0},
    "궤도형 험지 탐사 로봇": {"purpose": "궤도형 험지 탐사 로봇", "mass": 80.0, "target_speed": 0.7, "wheels": 4, "wheel_radius": 0.12, "motor_rpm": 4000, "motor_torque": 1.4, "gear_ratio": 50.0, "battery_wh": 900.0},
}

# -----------------------------
# 유틸 함수
# -----------------------------
def clamp(x, lo, hi):
    return max(lo, min(hi, x))


def safe_float(v, default=0.0):
    try:
        if v is None or v == "":
            return default
        return float(v)
    except Exception:
        return default


def safe_int(v, default=1):
    try:
        return int(round(float(v)))
    except Exception:
        return default


def first_existing(d, keys, default=None):
    for k in keys:
        if isinstance(d, dict) and k in d and d[k] not in [None, ""]:
            return d[k]
    return default


def get_nested(d, paths, default=None):
    for path in paths:
        cur = d
        ok = True
        for key in path:
            if isinstance(cur, dict) and key in cur:
                cur = cur[key]
            else:
                ok = False
                break
        if ok and cur not in [None, ""]:
            return cur
    return default


def status_label(value, warning=False, fail=False):
    if fail:
        return "FAIL"
    if warning:
        return "WARNING"
    return "PASS"

# -----------------------------
# 초기 설계 도움 시스템 JSON 해석
# -----------------------------
def normalize_design_json(payload):
    """
    초기 설계 도움 시스템에서 복사한 JSON 구조가 조금 달라도 최대한 해석한다.
    지원 예시:
    1) {input:{...}, result:{...}, parts:{...}, best_ratio:...}
    2) {data:{...}, calc:{...}, part:{...}, rows:[...]}
    3) {scale, purpose, mass, speed, unit, wheels, env, extra, ...}
    """
    if not isinstance(payload, dict):
        raise ValueError("JSON 최상위 구조가 객체(dict)가 아닙니다.")

    input_obj = payload.get("input", payload.get("data", payload))
    result_obj = payload.get("result", payload.get("calc", payload))
    part_obj = payload.get("parts", payload.get("part", payload))

    # 기어비 후보 추출
    rows = payload.get("gear_candidates", payload.get("rows", []))
    best_ratio = get_nested(payload, [["best_ratio"], ["result", "recommendedGearRatio"], ["result", "recommended_gear_ratio"], ["best", "ratio"], ["best", "r"]], None)
    if best_ratio is None and isinstance(rows, list) and rows:
        first = rows[0]
        if isinstance(first, dict):
            best_ratio = first.get("ratio", first.get("r", None))

    # 속도 해석
    speed = first_existing(input_obj, ["targetSpeedMps", "target_speed_mps", "speed_mps"], None)
    if speed is None:
        raw_speed = first_existing(input_obj, ["speed", "target_speed"], 1.5)
        unit = first_existing(input_obj, ["unit", "speedUnit", "speed_unit"], "mps")
        speed = safe_float(raw_speed, 1.5) / 3.6 if unit == "kmh" else safe_float(raw_speed, 1.5)

    model = {
        "purpose": str(first_existing(input_obj, ["purpose", "name", "mobility_name"], "붙여넣은 설계 기반 모빌리티")),
        "mass": safe_float(first_existing(input_obj, ["mass", "total_mass", "mass_kg"], 35.0), 35.0),
        "target_speed": safe_float(speed, 1.5),
        "wheels": safe_int(first_existing(input_obj, ["wheels", "drive_wheels", "wheel_count"], 4), 4),
        "wheel_radius": safe_float(first_existing(part_obj, ["wheel_r", "wheelRadiusM", "wheel_radius", "wheel_radius_m"], 0.10), 0.10),
        "motor_rpm": safe_float(first_existing(part_obj, ["motor_rpm", "motorRpm"], 3000.0), 3000.0),
        "motor_torque": safe_float(first_existing(result_obj, ["motor_nm", "motorTorqueNm"], first_existing(part_obj, ["motor_nm", "motorTorqueNm"], 0.5)), 0.5),
        "gear_ratio": safe_float(best_ratio, 15.0),
        "efficiency": safe_float(first_existing(result_obj, ["driveEfficiency", "efficiency"], DEFAULT_EFF), DEFAULT_EFF),
        "battery_wh": safe_float(first_existing(part_obj, ["battery_wh", "batteryWh"], 500.0), 500.0),
        "extra": str(first_existing(input_obj, ["extra", "requirements", "etc"], "")),
        "source_note": "초기 설계 도움 시스템 JSON에서 불러온 값",
        "req_power_from_design": safe_float(first_existing(result_obj, ["required_power_w", "requiredPowerW", "req_power"], 0.0), 0.0),
        "req_torque_from_design": safe_float(first_existing(result_obj, ["required_wheel_torque_nm", "requiredWheelTorqueNm", "req_tq"], 0.0), 0.0),
        "req_rpm_from_design": safe_float(first_existing(result_obj, ["required_wheel_rpm", "requiredWheelRpm", "req_rpm"], 0.0), 0.0),
        "raw_payload": payload,
    }
    return model

# -----------------------------
# 물리 시뮬레이션 엔진
# -----------------------------
def run_simulation(model, env):
    mass = max(0.1, safe_float(model["mass"], 35.0) + safe_float(env.get("payload_mass", 0.0), 0.0))
    target_v = max(0.01, safe_float(model["target_speed"], 1.5))
    wheels = max(1, safe_int(model["wheels"], 4))
    r = max(0.02, safe_float(model["wheel_radius"], 0.10))
    motor_rpm = max(1.0, safe_float(model["motor_rpm"], 3000.0))
    motor_torque = max(0.01, safe_float(model["motor_torque"], 0.5))
    gear_ratio = max(0.1, safe_float(model["gear_ratio"], 15.0))
    eff = clamp(safe_float(model.get("efficiency", DEFAULT_EFF), DEFAULT_EFF), 0.2, 1.0)
    battery_wh = max(1.0, safe_float(model.get("battery_wh", 500.0), 500.0))

    road = ROAD_DB[env["road"]]
    crr = road["crr"]
    mu = road["mu"]
    rough = road["rough"]
    grade_deg = safe_float(env["grade"], 0.0)
    grade_rad = math.radians(grade_deg)
    course_m = max(1.0, safe_float(env["course"], 30.0))
    target_time = max(1.0, safe_float(env["time"], 40.0))
    obstacle_level = clamp(safe_float(env["obstacle"], 0.0), 0.0, 1.0)
    air_on = bool(env.get("air_on", True))
    cd_a = safe_float(env.get("cd_a", 0.35), 0.35)
    rho = 1.225
    brake_decel = max(0.2, safe_float(env.get("brake_decel", 1.5), 1.5))

    # 제어 방식 보정
    control_mode = env.get("control_mode", "일반 제어")
    thermal_factor = 1.0
    eff_bonus = 0.0
    torque_factor = 1.0
    speed_limit_factor = 1.0
    if control_mode == "효율 우선 전력 제어":
        eff_bonus = 0.04
        speed_limit_factor = 0.92
    elif control_mode == "발열 억제 전력 제어":
        thermal_factor = 0.82
        speed_limit_factor = 0.85
    elif control_mode == "가변 기어비 보조 제어":
        torque_factor = 1.15 if grade_deg >= 8 or obstacle_level >= 0.2 else 1.0
        speed_limit_factor = 1.03 if grade_deg < 5 else 0.95
    eff = clamp(eff + eff_bonus, 0.2, 0.95)

    # 구동 가능 토크/힘
    wheel_torque_total = motor_torque * gear_ratio * eff * wheels * torque_factor
    traction_force_motor = wheel_torque_total / r
    traction_limit = mu * mass * G * math.cos(grade_rad)
    usable_force = min(traction_force_motor, traction_limit)
    slip_risk = traction_force_motor > traction_limit * 1.05

    # 최고속도: 모터 rpm과 기어비 기반
    wheel_rpm_max = motor_rpm / gear_ratio
    max_speed_by_rpm = (2 * math.pi * r) * (wheel_rpm_max / 60.0) * speed_limit_factor

    # 시간 적분
    dt = 0.1
    max_steps = int(min(600.0, max(target_time * 2.0, 30.0)) / dt)
    t = 0.0
    v = 0.0
    x = 0.0
    energy_wh = 0.0
    peak_power = 0.0
    peak_torque_use = 0.0
    time_to_target = None
    logs = []
    times, speeds, distances, batteries, torque_uses, powers = [], [], [], [], [], []

    logs.append("[00.0s] 가상환경 시뮬레이션 시작")
    for step in range(max_steps):
        roll = crr * mass * G * math.cos(grade_rad)
        slope = mass * G * math.sin(grade_rad)
        air = 0.5 * rho * cd_a * v * v if air_on else 0.0
        obstacle_res = obstacle_level * (0.15 + rough) * mass * G
        resist = roll + slope + air + obstacle_res

        # 속도가 최고 rpm 한계에 가까우면 견인력을 서서히 줄임
        rpm_limit_factor = clamp(1.0 - (v / max(max_speed_by_rpm, 0.01)) ** 2, 0.0, 1.0)
        drive_force = usable_force * rpm_limit_factor
        net = drive_force - resist
        a = net / mass

        # 역주행 방지 및 최고속도 제한
        v = max(0.0, v + a * dt)
        v = min(v, max_speed_by_rpm)
        x += v * dt

        mech_power = max(resist * max(v, 0.05), 0.0)
        electric_power = mech_power / max(eff, 0.1)
        # 가속 중 부하 반영
        electric_power += max(mass * max(a, 0) * max(v, 0.05), 0.0) / max(eff, 0.1)
        energy_wh += electric_power * dt / 3600.0
        peak_power = max(peak_power, electric_power)

        # 요구 토크 사용률: 현재 저항을 이기기 위해 필요한 토크 / 사용 가능 토크
        required_wheel_torque_total = resist * r
        torque_use = required_wheel_torque_total / max(wheel_torque_total, 0.001)
        peak_torque_use = max(peak_torque_use, torque_use)

        battery_pct = clamp(100.0 * (1.0 - energy_wh / battery_wh), 0.0, 100.0)
        times.append(t)
        speeds.append(v)
        distances.append(x)
        batteries.append(battery_pct)
        torque_uses.append(torque_use * 100.0)
        powers.append(electric_power)

        if time_to_target is None and v >= target_v * 0.95:
            time_to_target = t
            logs.append(f"[{t:04.1f}s] 목표 속도의 95% 도달")

        if x >= course_m:
            logs.append(f"[{t:04.1f}s] 설정 코스 {course_m:.1f}m 완주")
            break
        if battery_pct <= 1.0:
            logs.append(f"[{t:04.1f}s] 배터리 잔량 부족으로 시뮬레이션 중단")
            break
        if step == max_steps - 1:
            logs.append(f"[{t:04.1f}s] 제한 시간 도달")
        t += dt

    final_time = times[-1] if times else 0.0
    final_speed = speeds[-1] if speeds else 0.0
    final_distance = distances[-1] if distances else 0.0
    used_wh = energy_wh
    avg_power = used_wh / max(final_time / 3600.0, 1e-6)
    est_runtime_h = battery_wh / max(avg_power, 1.0)
    est_range_m = est_runtime_h * 3600.0 * max(sum(speeds) / max(len(speeds), 1), 0.01)
    brake_distance = (target_v ** 2) / (2 * brake_decel)

    # 등판 한계 근사
    max_climb_rad = 0.0
    for deg in [i * 0.5 for i in range(0, 91)]:
        rad = math.radians(deg)
        res = crr * mass * G * math.cos(rad) + mass * G * math.sin(rad) + obstacle_level * (0.15 + rough) * mass * G
        if usable_force >= res:
            max_climb_rad = rad
        else:
            break
    max_climb_deg = math.degrees(max_climb_rad)

    # 판정
    speed_ratio = max_speed_by_rpm / target_v
    torque_margin = (usable_force - (crr * mass * G * math.cos(grade_rad) + mass * G * math.sin(grade_rad))) / max((crr * mass * G * math.cos(grade_rad) + mass * G * math.sin(grade_rad)), 1e-6) * 100
    course_pass = final_distance >= course_m * 0.98
    speed_pass = speed_ratio >= 0.95
    speed_warn = 0.75 <= speed_ratio < 0.95
    torque_fail = torque_margin < 0
    torque_warn = 0 <= torque_margin < 30
    climb_pass = max_climb_deg >= grade_deg
    climb_warn = max_climb_deg >= grade_deg * 0.85 and not climb_pass

    load_ratio = peak_torque_use / 100.0
    if load_ratio < 0.60:
        thermal = "낮음"
        thermal_score = 100
    elif load_ratio < 0.85:
        thermal = "보통"
        thermal_score = 78
    elif load_ratio < 1.10:
        thermal = "높음"
        thermal_score = 52
    else:
        thermal = "위험"
        thermal_score = 25
        logs.append(f"[{final_time:04.1f}s] 토크 사용률이 높아 발열 위험이 큼")

    if slip_risk:
        logs.append("[주의] 모터 토크가 노면 접지 한계를 초과할 수 있어 슬립 가능성이 있습니다.")

    score = 0
    score += clamp(speed_ratio * 25, 0, 25)
    score += 25 if not torque_fail else 5
    if torque_warn:
        score -= 7
    score += 20 if climb_pass else (10 if climb_warn else 3)
    score += 15 if course_pass else 6
    score += thermal_score * 0.10
    score += 5 if not slip_risk else 0
    score = int(clamp(score, 0, 100))

    if score >= 80 and not torque_fail and climb_pass:
        overall = "PASS"
    elif score >= 55 and not torque_fail:
        overall = "WARNING"
    else:
        overall = "FAIL"

    result = {
        "mass_total": mass,
        "wheel_torque_total": wheel_torque_total,
        "traction_force_motor": traction_force_motor,
        "traction_limit": traction_limit,
        "usable_force": usable_force,
        "max_speed_by_rpm": max_speed_by_rpm,
        "target_speed": target_v,
        "speed_ratio": speed_ratio,
        "time_to_target": time_to_target,
        "final_time": final_time,
        "final_speed": final_speed,
        "final_distance": final_distance,
        "course_pass": course_pass,
        "torque_margin": torque_margin,
        "max_climb_deg": max_climb_deg,
        "climb_pass": climb_pass,
        "used_wh": used_wh,
        "avg_power": avg_power,
        "peak_power": peak_power,
        "battery_wh": battery_wh,
        "est_runtime_h": est_runtime_h,
        "est_range_m": est_range_m,
        "thermal": thermal,
        "peak_torque_use": peak_torque_use * 100,
        "brake_distance": brake_distance,
        "slip_risk": slip_risk,
        "score": score,
        "overall": overall,
        "logs": logs,
        "series": {
            "time": times,
            "speed": speeds,
            "distance": distances,
            "battery": batteries,
            "torque_use": torque_uses,
            "power": powers,
        }
    }
    return result

# -----------------------------
# 시각화 함수
# -----------------------------
def plot_series(result):
    s = result["series"]
    fig, axes = plt.subplots(2, 2, figsize=(12, 7))
    fig.patch.set_facecolor("white")

    axes[0, 0].plot(s["time"], s["speed"], color="#2563eb", linewidth=2)
    axes[0, 0].axhline(result["target_speed"], color="#ef4444", linestyle="--", linewidth=1)
    axes[0, 0].set_title("시간-속도")
    axes[0, 0].set_xlabel("시간(s)")
    axes[0, 0].set_ylabel("속도(m/s)")
    axes[0, 0].grid(True, alpha=0.25)

    axes[0, 1].plot(s["time"], s["distance"], color="#059669", linewidth=2)
    axes[0, 1].set_title("시간-거리")
    axes[0, 1].set_xlabel("시간(s)")
    axes[0, 1].set_ylabel("거리(m)")
    axes[0, 1].grid(True, alpha=0.25)

    axes[1, 0].plot(s["time"], s["battery"], color="#f59e0b", linewidth=2)
    axes[1, 0].set_title("배터리 잔량")
    axes[1, 0].set_xlabel("시간(s)")
    axes[1, 0].set_ylabel("잔량(%)")
    axes[1, 0].set_ylim(0, 105)
    axes[1, 0].grid(True, alpha=0.25)

    axes[1, 1].plot(s["time"], s["torque_use"], color="#dc2626", linewidth=2)
    axes[1, 1].axhline(100, color="#111827", linestyle="--", linewidth=1)
    axes[1, 1].set_title("토크 사용률")
    axes[1, 1].set_xlabel("시간(s)")
    axes[1, 1].set_ylabel("사용률(%)")
    axes[1, 1].grid(True, alpha=0.25)

    plt.tight_layout()
    return fig


def draw_virtual_scene(model, env, result):
    fig, ax = plt.subplots(figsize=(12, 4.8))
    ax.set_xlim(0, 100)
    ax.set_ylim(0, 45)
    ax.axis("off")
    ax.set_facecolor("#f8fafc")

    grade = safe_float(env["grade"], 0.0)
    obstacle = safe_float(env["obstacle"], 0.0)
    road_color = "#475569"
    body_color = "#2563eb" if result["overall"] == "PASS" else ("#f59e0b" if result["overall"] == "WARNING" else "#dc2626")

    # 지면/경사로
    if abs(grade) < 1:
        ax.plot([0, 100], [30, 30], color=road_color, linewidth=4)
    else:
        ax.plot([0, 30], [34, 34], color=road_color, linewidth=4)
        ax.plot([30, 75], [34, 20], color=road_color, linewidth=4)
        ax.plot([75, 100], [20, 20], color=road_color, linewidth=4)
        ax.text(45, 18, f"경사 {grade:.1f}°", fontsize=11, color="#334155", weight="bold")

    # 장애물
    if obstacle > 0.05:
        for x in [25, 55, 82]:
            h = 2 + obstacle * 8
            ax.add_patch(patches.Rectangle((x, 30 - h), 4, h, color="#a16207", alpha=0.75))
        ax.text(76, 36, "장애물/요철", fontsize=10, color="#92400e", weight="bold")

    # 모빌리티 위치
    progress = clamp(result["final_distance"] / max(safe_float(env["course"], 30.0), 1.0), 0.05, 0.95)
    car_x = 10 + 70 * progress
    car_y = 27 if grade < 1 else 29 - 10 * progress

    purpose = model.get("purpose", "모빌리티")
    extra = model.get("extra", "").lower()
    is_scooter = "킥보드" in purpose or "스쿠터" in purpose
    is_ev = "전기차" in purpose or "ev" in purpose.lower() or "자동차" in purpose
    is_track = "궤도" in extra or "트랙" in extra or "track" in extra

    if is_scooter:
        # 킥보드형 외형
        ax.add_patch(patches.Circle((car_x, car_y), 2.2, fill=False, edgecolor="#111827", linewidth=2.5))
        ax.add_patch(patches.Circle((car_x + 14, car_y), 2.2, fill=False, edgecolor="#111827", linewidth=2.5))
        ax.plot([car_x, car_x + 14], [car_y - 2, car_y - 2], color=body_color, linewidth=4)
        ax.plot([car_x + 12, car_x + 16], [car_y - 2, car_y - 14], color=body_color, linewidth=3)
        ax.plot([car_x + 14, car_x + 19], [car_y - 14, car_y - 14], color=body_color, linewidth=3)
        ax.text(car_x - 2, car_y - 17, "스쿠터/킥보드형", fontsize=10, color=body_color, weight="bold")
    elif is_ev:
        # 자동차형 외형
        ax.add_patch(patches.Rectangle((car_x, car_y - 8), 22, 7, fill=False, edgecolor=body_color, linewidth=3))
        ax.add_patch(patches.Polygon([[car_x + 5, car_y - 8], [car_x + 10, car_y - 14], [car_x + 17, car_y - 14], [car_x + 21, car_y - 8]], fill=False, edgecolor=body_color, linewidth=3))
        ax.add_patch(patches.Circle((car_x + 5, car_y), 2.7, fill=False, edgecolor="#111827", linewidth=2.5))
        ax.add_patch(patches.Circle((car_x + 18, car_y), 2.7, fill=False, edgecolor="#111827", linewidth=2.5))
        ax.text(car_x, car_y - 17, "자동차형 차체", fontsize=10, color=body_color, weight="bold")
    elif is_track:
        # 궤도형 외형
        ax.add_patch(patches.FancyBboxPatch((car_x, car_y - 7), 23, 8, boxstyle="round,pad=0.2,rounding_size=4", fill=False, edgecolor="#111827", linewidth=2.5))
        ax.add_patch(patches.Rectangle((car_x + 3, car_y - 15), 17, 8, fill=False, edgecolor=body_color, linewidth=3))
        ax.add_patch(patches.Circle((car_x + 5, car_y - 3), 1.7, fill=False, edgecolor="#111827", linewidth=1.8))
        ax.add_patch(patches.Circle((car_x + 18, car_y - 3), 1.7, fill=False, edgecolor="#111827", linewidth=1.8))
        ax.text(car_x, car_y - 18, "궤도형 플랫폼", fontsize=10, color=body_color, weight="bold")
    else:
        # 일반 로봇형 외형
        ax.add_patch(patches.Rectangle((car_x, car_y - 11), 22, 10, fill=False, edgecolor=body_color, linewidth=3))
        ax.add_patch(patches.Circle((car_x + 4, car_y), 2.6, fill=False, edgecolor="#111827", linewidth=2.5))
        ax.add_patch(patches.Circle((car_x + 18, car_y), 2.6, fill=False, edgecolor="#111827", linewidth=2.5))
        ax.add_patch(patches.Rectangle((car_x + 7, car_y - 17), 8, 6, fill=False, edgecolor="#174a8b", linewidth=2))
        ax.text(car_x, car_y - 20, "로봇형 플랫폼", fontsize=10, color=body_color, weight="bold")

    ax.annotate("진행 방향", xy=(car_x + 28, car_y - 8), xytext=(car_x + 12, car_y - 8), arrowprops=dict(arrowstyle="->", color="#2563eb", lw=2), color="#2563eb", fontsize=10, weight="bold")

    ax.text(2, 6, "가상환경 모빌리티 테스트베드", fontsize=15, weight="bold", color="#111827")
    ax.text(2, 11, f"노면: {env['road']} / 상태: {result['overall']} / 점수: {result['score']}점", fontsize=11, color="#334155")
    ax.text(2, 16, f"속도 {result['final_speed']:.2f}m/s · 거리 {result['final_distance']:.1f}m · 배터리 사용 {result['used_wh']:.2f}Wh", fontsize=10, color="#475569")
    return fig

# -----------------------------
# 보고서 문장 생성
# -----------------------------
def make_report(model, env, result):
    ttt = "목표 속도에 도달하지 못함" if result["time_to_target"] is None else f"약 {result['time_to_target']:.1f}초 만에 목표 속도의 95%에 도달"
    slip = " 또한 현재 조건에서는 접지 한계 초과에 따른 슬립 가능성이 있어 노면 마찰 또는 토크 제한 제어를 고려해야 한다." if result["slip_risk"] else ""
    if result["overall"] == "PASS":
        verdict = "전체적으로 설정한 가상환경에서 주행 가능성이 높은 것으로 예측되었다."
    elif result["overall"] == "WARNING":
        verdict = "일부 조건에서 한계에 근접하므로 실제 제작 전 기어비, 모터 출력, 배터리 용량 또는 제어 방식을 조정할 필요가 있다."
    else:
        verdict = "현재 설계값으로는 설정한 가상환경을 안정적으로 통과하기 어렵다고 예측되었다."
    return (
        f"해당 모빌리티는 '{model.get('purpose', '사용자 정의 모빌리티')}' 조건에서 총 질량 {result['mass_total']:.1f}kg, "
        f"목표 속도 {result['target_speed']:.2f}m/s, 기어비 {safe_float(model.get('gear_ratio'), 0):.1f}:1을 적용해 가상 주행을 수행하였다. "
        f"시뮬레이션 결과 최고 예상 속도는 약 {result['max_speed_by_rpm']:.2f}m/s이며, {ttt}한 것으로 나타났다. "
        f"설정 경사 {safe_float(env['grade']):.1f}°에 대해 최대 등판 가능 각도는 약 {result['max_climb_deg']:.1f}°로 계산되었고, "
        f"피크 토크 사용률은 {result['peak_torque_use']:.0f}%로 발열 위험도는 '{result['thermal']}' 수준이다. "
        f"예상 제동 거리는 약 {result['brake_distance']:.2f}m이며, 종합 점수는 {result['score']}/100점으로 판정은 {result['overall']}이다. "
        f"{verdict}{slip}"
    )

# -----------------------------
# 세션 상태 초기화
# -----------------------------
def init_state():
    if "model" not in st.session_state:
        st.session_state.model = {
            "purpose": "",
            "mass": 35.0,
            "target_speed": 1.5,
            "wheels": 4,
            "wheel_radius": 0.10,
            "motor_rpm": 3000.0,
            "motor_torque": 0.5,
            "gear_ratio": 15.0,
            "efficiency": DEFAULT_EFF,
            "battery_wh": 500.0,
            "extra": "",
            "source_note": "직접 입력",
        }
    if "json_text" not in st.session_state:
        st.session_state.json_text = ""
    if "result" not in st.session_state:
        st.session_state.result = None

init_state()

# -----------------------------
# 화면 상단
# -----------------------------
st.title("🧪 가상환경 모빌리티 테스트베드")
st.caption("초기 설계 도움 시스템에서 복사한 데이터를 붙여넣거나, 직접 조건을 입력해 미완성/가상 모빌리티의 성능을 예측하는 Streamlit 프로그램입니다.")

with st.expander("이 프로그램의 목적", expanded=True):
    st.markdown(
        """
        - 이 테스트베드는 **완성된 실물 없이도** 모빌리티의 주행 가능성, 등판 성능, 배터리 소모, 발열 위험, 제동 거리를 예측하기 위한 도구입니다.
        - 앞선 **모빌리티 구동계 초기 설계 도움 시스템**의 결과 JSON을 붙여넣으면 빠르게 시작할 수 있습니다.
        - JSON 없이도 사용자가 직접 질량, 바퀴, 모터, 기어비, 배터리, 노면 조건을 입력해 독립적으로 시뮬레이션할 수 있습니다.
        - 결과는 실제 실험값이 아니라 단순화된 물리 모델 기반의 **초기 예측값**입니다.
        """
    )

# -----------------------------
# 사이드바: 모드 및 환경 설정
# -----------------------------
st.sidebar.header("1. 사용 방식")
mode = st.sidebar.radio("입력 방식", ["설계 데이터 붙여넣기", "직접 입력/수정"], index=0)

st.sidebar.header("2. 가상환경 시나리오")
scenario_name = st.sidebar.selectbox("시나리오 프리셋", list(SCENARIOS.keys()))
scenario = SCENARIOS[scenario_name]

road = st.sidebar.selectbox("노면 종류", list(ROAD_DB.keys()), index=list(ROAD_DB.keys()).index(scenario["road"]))
grade = st.sidebar.slider("경사각(도)", 0.0, 35.0, float(scenario["grade"]), 0.5)
course = st.sidebar.number_input("코스 길이(m)", min_value=1.0, max_value=1000.0, value=float(scenario["course"]), step=5.0)
time_goal = st.sidebar.number_input("시뮬레이션 목표 시간(s)", min_value=5.0, max_value=600.0, value=float(scenario["time"]), step=5.0)
obstacle = st.sidebar.slider("장애물/요철 수준", 0.0, 1.0, float(scenario["obstacle"]), 0.05)
payload_mass = st.sidebar.number_input("추가 적재 하중(kg)", min_value=0.0, max_value=10000.0, value=0.0, step=1.0)
control_mode = st.sidebar.selectbox("전력/반도체 제어 방식", ["일반 제어", "효율 우선 전력 제어", "발열 억제 전력 제어", "가변 기어비 보조 제어"])
air_on = st.sidebar.checkbox("공기저항 반영", value=True)
cd_a = st.sidebar.number_input("CdA 공기저항 면적 계수", min_value=0.05, max_value=5.0, value=0.35, step=0.05)
brake_decel = st.sidebar.number_input("제동 감속도(m/s²)", min_value=0.2, max_value=10.0, value=1.5, step=0.1)

env = {
    "road": road,
    "grade": grade,
    "course": course,
    "time": time_goal,
    "obstacle": obstacle,
    "payload_mass": payload_mass,
    "control_mode": control_mode,
    "air_on": air_on,
    "cd_a": cd_a,
    "brake_decel": brake_decel,
}

# -----------------------------
# 본문: 입력부
# -----------------------------
left, right = st.columns([1.05, 1.0])

with left:
    st.subheader("1. 설계 데이터 붙여넣기")
    st.write("초기 설계 도움 시스템에서 복사한 테스트베드용 JSON을 아래에 붙여넣으세요. 붙여넣기 없이 직접 입력만 사용해도 됩니다.")
    json_text = st.text_area(
        "JSON 데이터 붙여넣기",
        value=st.session_state.json_text,
        height=210,
        placeholder="여기에 초기 설계 도움 시스템에서 복사한 JSON 데이터를 붙여넣으세요.",
        key="json_input_area"
    )
    col_a, col_b = st.columns(2)
    with col_a:
        apply_json = st.button("📥 붙여넣은 설계 데이터 적용", use_container_width=True)
    with col_b:
        clear_json = st.button("🧹 붙여넣기 내용 비우기", use_container_width=True)

    if clear_json:
        st.session_state.json_text = ""
        st.rerun()

    if apply_json:
        try:
            payload = json.loads(json_text)
            model = normalize_design_json(payload)
            st.session_state.model.update(model)
            st.session_state.json_text = json_text
            st.success("설계 데이터를 테스트베드 입력값으로 적용했습니다.")
        except Exception as e:
            st.error(f"JSON 해석에 실패했습니다: {e}")

with right:
    st.subheader("2. 직접 입력/수정")
    st.write("붙여넣은 값도 여기서 수정할 수 있습니다. 직접 입력 모드에서는 처음부터 사용자가 값을 구성하면 됩니다.")

    preset_name = st.selectbox("빠른 직접 입력 프리셋", list(DIRECT_PRESETS.keys()))
    if st.button("프리셋 적용", use_container_width=True):
        if preset_name == "직접 입력":
            st.session_state.model = {
                "purpose": "",
                "mass": 0.0,
                "target_speed": 0.0,
                "wheels": 0,
                "wheel_radius": 0.0,
                "motor_rpm": 0.0,
                "motor_torque": 0.0,
                "gear_ratio": 0.0,
                "efficiency": DEFAULT_EFF,
                "battery_wh": 0.0,
                "extra": "",
                "source_note": "직접 입력 - 빈 양식",
            }
        else:
            st.session_state.model.update(DIRECT_PRESETS[preset_name])
            st.session_state.model["efficiency"] = DEFAULT_EFF
            st.session_state.model["extra"] = st.session_state.model.get("extra", "")
            st.session_state.model["source_note"] = f"직접 입력 프리셋: {preset_name}"
        st.rerun()

    m = st.session_state.model
    purpose = st.text_input("모빌리티 이름/용도", value=m.get("purpose", ""), placeholder="예: 실내 물류 로봇, 전동 킥보드형 이동체")
    c1, c2 = st.columns(2)
    with c1:
        mass = st.number_input("총 질량(kg)", min_value=0.0, value=float(m.get("mass", 0.0)), step=1.0)
        wheels = st.number_input("구동 바퀴 수", min_value=0, value=int(m.get("wheels", 0)), step=1)
        motor_rpm = st.number_input("모터 기준 RPM", min_value=0.0, value=float(m.get("motor_rpm", 0.0)), step=100.0)
        gear_ratio = st.number_input("기어비", min_value=0.0, value=float(m.get("gear_ratio", 0.0)), step=1.0)
    with c2:
        target_speed = st.number_input("목표 속도(m/s)", min_value=0.0, value=float(m.get("target_speed", 0.0)), step=0.1)
        wheel_radius = st.number_input("바퀴 반지름(m)", min_value=0.0, value=float(m.get("wheel_radius", 0.0)), step=0.01)
        motor_torque = st.number_input("모터 1개 기준 토크(Nm)", min_value=0.0, value=float(m.get("motor_torque", 0.0)), step=0.1)
        battery_wh = st.number_input("배터리 용량(Wh)", min_value=0.0, value=float(m.get("battery_wh", 0.0)), step=50.0)

    efficiency = st.slider("구동계 효율", 0.20, 0.95, float(m.get("efficiency", DEFAULT_EFF)), 0.01)
    extra = st.text_area("기타 요구사항/장치 설명", value=m.get("extra", ""), height=90, placeholder="예: 인테이크, 슈터, 라이다, 궤도, 방수, 고하중 등")

    st.session_state.model.update({
        "purpose": purpose,
        "mass": mass,
        "target_speed": target_speed,
        "wheels": wheels,
        "wheel_radius": wheel_radius,
        "motor_rpm": motor_rpm,
        "motor_torque": motor_torque,
        "gear_ratio": gear_ratio,
        "efficiency": efficiency,
        "battery_wh": battery_wh,
        "extra": extra,
    })

# -----------------------------
# 적용 데이터 요약
# -----------------------------
st.subheader("3. 현재 테스트베드 입력 요약")
model = st.session_state.model
s1, s2, s3, s4 = st.columns(4)
s1.metric("총 질량", f"{safe_float(model.get('mass')):.1f} kg")
s2.metric("목표 속도", f"{safe_float(model.get('target_speed')):.2f} m/s")
s3.metric("기어비", f"{safe_float(model.get('gear_ratio')):.1f}:1")
s4.metric("배터리", f"{safe_float(model.get('battery_wh')):.0f} Wh")
st.caption(f"입력 출처: {model.get('source_note', '직접 입력')}")
st.info(f"노면 조건: {road} — {ROAD_DB[road]['desc']}")

# -----------------------------
# 시뮬레이션 실행
# -----------------------------
run_col1, run_col2, run_col3 = st.columns([1, 1, 2])
with run_col1:
    run_btn = st.button("▶ 가상 주행 시뮬레이션 실행", type="primary", use_container_width=True)
with run_col2:
    reset_btn = st.button("🔄 결과 초기화", use_container_width=True)

if reset_btn:
    st.session_state.result = None
    st.rerun()

if run_btn:
    errors = []
    if safe_float(model.get("mass"), 0) <= 0:
        errors.append("총 질량은 0보다 커야 합니다.")
    if safe_float(model.get("target_speed"), 0) <= 0:
        errors.append("목표 속도는 0보다 커야 합니다.")
    if safe_int(model.get("wheels"), 0) <= 0:
        errors.append("구동 바퀴 수는 1개 이상이어야 합니다.")
    if safe_float(model.get("wheel_radius"), 0) <= 0:
        errors.append("바퀴 반지름은 0보다 커야 합니다.")
    if safe_float(model.get("motor_rpm"), 0) <= 0:
        errors.append("모터 RPM은 0보다 커야 합니다.")
    if safe_float(model.get("motor_torque"), 0) <= 0:
        errors.append("모터 토크는 0보다 커야 합니다.")
    if safe_float(model.get("gear_ratio"), 0) <= 0:
        errors.append("기어비는 0보다 커야 합니다.")
    if safe_float(model.get("battery_wh"), 0) <= 0:
        errors.append("배터리 용량은 0보다 커야 합니다.")

    if errors:
        for e in errors:
            st.error(e)
    else:
        st.session_state.result = run_simulation(model, env)
        st.success("시뮬레이션이 완료되었습니다.")

# -----------------------------
# 결과 출력
# -----------------------------
result = st.session_state.result
if result:
    st.subheader("4. 성능 예측 결과")
    k1, k2, k3, k4 = st.columns(4)
    k1.metric("종합 판정", result["overall"], f"{result['score']} / 100점")
    k2.metric("예상 최고 속도", f"{result['max_speed_by_rpm']:.2f} m/s", f"목표 대비 {result['speed_ratio']*100:.0f}%")
    k3.metric("최대 등판 가능각", f"{result['max_climb_deg']:.1f}°", f"설정 {safe_float(env['grade']):.1f}°")
    k4.metric("발열 위험도", result["thermal"], f"피크 토크 {result['peak_torque_use']:.0f}%")

    r1, r2, r3, r4 = st.columns(4)
    ttt = "미도달" if result["time_to_target"] is None else f"{result['time_to_target']:.1f}s"
    r1.metric("목표 속도 도달", ttt)
    r2.metric("코스 주행 거리", f"{result['final_distance']:.1f} m")
    r3.metric("예상 주행 가능 시간", f"{result['est_runtime_h']*60:.1f} 분")
    r4.metric("예상 제동 거리", f"{result['brake_distance']:.2f} m")

    # 세부 판정표
    speed_state = status_label(result["speed_ratio"], warning=(0.75 <= result["speed_ratio"] < 0.95), fail=(result["speed_ratio"] < 0.75))
    torque_state = status_label(result["torque_margin"], warning=(0 <= result["torque_margin"] < 30), fail=(result["torque_margin"] < 0))
    climb_state = status_label(result["climb_pass"], warning=(not result["climb_pass"] and result["max_climb_deg"] >= safe_float(env['grade']) * 0.85), fail=(not result["climb_pass"] and result["max_climb_deg"] < safe_float(env['grade']) * 0.85))
    battery_state = status_label(result["est_runtime_h"] * 3600 >= safe_float(env["time"]), warning=(result["est_runtime_h"] * 3600 >= safe_float(env["time"]) * 0.7 and result["est_runtime_h"] * 3600 < safe_float(env["time"])), fail=(result["est_runtime_h"] * 3600 < safe_float(env["time"]) * 0.7))
    thermal_state = "PASS" if result["thermal"] in ["낮음", "보통"] else ("WARNING" if result["thermal"] == "높음" else "FAIL")
    slip_state = "WARNING" if result["slip_risk"] else "PASS"

    st.markdown("#### PASS / WARNING / FAIL 세부 판정")
    st.table([
        {"항목": "목표 속도", "판정": speed_state, "근거": f"목표 대비 {result['speed_ratio']*100:.0f}%"},
        {"항목": "토크 여유", "판정": torque_state, "근거": f"저항 대비 여유 {result['torque_margin']:.0f}%"},
        {"항목": "등판 성능", "판정": climb_state, "근거": f"최대 {result['max_climb_deg']:.1f}° / 설정 {safe_float(env['grade']):.1f}°"},
        {"항목": "배터리 지속성", "판정": battery_state, "근거": f"예상 {result['est_runtime_h']*60:.1f}분"},
        {"항목": "발열 위험", "판정": thermal_state, "근거": f"{result['thermal']} / 피크 토크 {result['peak_torque_use']:.0f}%"},
        {"항목": "접지 안정성", "판정": slip_state, "근거": "슬립 위험 있음" if result["slip_risk"] else "접지 한계 내"},
    ])

    st.subheader("5. 가상 주행 시각화")
    st.pyplot(draw_virtual_scene(model, env, result))
    st.pyplot(plot_series(result))

    st.subheader("6. 시뮬레이션 로그")
    st.code("\n".join(result["logs"]), language="text")

    st.subheader("7. 보고서용 해석문")
    report = make_report(model, env, result)
    st.write(report)

    export_obj = {
        "program": "가상환경 모빌리티 테스트베드",
        "model": {k: v for k, v in model.items() if k != "raw_payload"},
        "environment": env,
        "result_summary": {k: v for k, v in result.items() if k not in ["series", "logs"]},
        "logs": result["logs"],
        "report": report,
    }
    export_text = json.dumps(export_obj, ensure_ascii=False, indent=2)
    st.markdown("#### 결과 전체 복사용 데이터")
    st.text_area("아래 내용을 복사해 보고서, 기록, 다른 프로그램 입력에 사용할 수 있습니다.", value=export_text, height=260)
    st.download_button(
        "💾 테스트베드 결과 JSON 다운로드",
        data=export_text,
        file_name="virtual_mobility_testbed_result.json",
        mime="application/json",
        use_container_width=True
    )
else:
    st.warning("아직 시뮬레이션 결과가 없습니다. 입력값을 확인한 뒤 [가상 주행 시뮬레이션 실행] 버튼을 누르세요.")

st.markdown("---")
st.caption("본 프로그램은 단순화된 물리 모델을 사용한 초기 성능 예측 도구입니다. 실제 제작 전에는 구조 강도, 전류 제한, 발열, 제동, 배터리 안전성, 센서 오차를 별도로 검증해야 합니다.")

