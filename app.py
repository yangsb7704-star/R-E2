
import json
import math
import re
import streamlit as st
import matplotlib.pyplot as plt
import matplotlib.patches as patches

st.set_page_config(page_title="가상환경 모빌리티 테스트베드", layout="wide")

# -----------------------------
# 기본 유틸
# -----------------------------

def to_float(x, default=0.0):
    try:
        if x is None:
            return default
        s = str(x).strip().replace(",", "")
        m = re.search(r"-?\d+(?:\.\d+)?", s)
        return float(m.group()) if m else default
    except Exception:
        return default


def normalize_env(text):
    t = str(text or "").lower()
    if any(k in t for k in ["indoor", "실내", "단순", "평지"]):
        return "실내/평지"
    if any(k in t for k in ["normal", "아스팔트", "일반"]):
        return "일반 도로"
    if any(k in t for k in ["obstacle", "요철", "장애물"]):
        return "요철/장애물"
    if any(k in t for k in ["extreme", "험지", "산악", "흙길", "자갈"]):
        return "험지/흙길"
    return "실내/평지"


def env_to_coeff(env):
    table = {
        "실내/평지": dict(crr=0.018, mu=0.75, rough=1.00),
        "일반 도로": dict(crr=0.025, mu=0.70, rough=1.05),
        "요철/장애물": dict(crr=0.045, mu=0.55, rough=1.22),
        "험지/흙길": dict(crr=0.080, mu=0.42, rough=1.45),
    }
    return table.get(env, table["실내/평지"])


def speed_to_mps(speed_value, unit_text="m/s"):
    unit = str(unit_text).lower()
    v = to_float(speed_value, 0.0)
    if "km" in unit or "kmh" in unit:
        return v / 3.6
    return v


def default_design():
    return {
        "source_mode": "직접 입력",
        "purpose": "",
        "scale": "",
        "mass": 30.0,
        "target_speed_mps": 1.5,
        "wheels": 4,
        "env": "실내/평지",
        "extra": "",
        "wheel_radius_m": 0.10,
        "motor_rpm": 3000.0,
        "motor_torque_nm": 0.50,
        "gear_ratio": 18.0,
        "efficiency": 0.85,
        "required_power_w": 0.0,
        "required_wheel_torque_nm": 0.0,
        "required_wheel_rpm": 0.0,
    }

# -----------------------------
# 붙여넣기 데이터 파서
# JSON + 일반 요약문 모두 대응
# -----------------------------

def parse_design_text(raw):
    raw = (raw or "").strip()
    if not raw:
        raise ValueError("붙여넣은 내용이 비어 있습니다.")

    # 1) 우선 JSON 시도
    if raw.startswith("{") or raw.startswith("["):
        obj = json.loads(raw)
        return parse_json_design(obj)

    # 2) 일반 요약문 파싱
    d = default_design()
    d["source_mode"] = "일반 요약문 붙여넣기"

    lines = [line.strip() for line in raw.splitlines() if line.strip()]
    for line in lines:
        compact = line.replace(" ", "")
        if line.startswith("용도:") or compact.startswith("용도:"):
            d["purpose"] = line.split(":", 1)[1].strip()
        elif line.startswith("스케일:") or compact.startswith("스케일:"):
            d["scale"] = line.split(":", 1)[1].strip()
        elif line.startswith("질량:") or compact.startswith("질량:"):
            d["mass"] = to_float(line, d["mass"])
        elif line.startswith("목표 속도:") or compact.startswith("목표속도:"):
            # 예: 목표 속도: 6.0 m/s 또는 15 km/h
            val = to_float(line, d["target_speed_mps"])
            unit = "km/h" if "km" in line.lower() else "m/s"
            d["target_speed_mps"] = speed_to_mps(val, unit)
        elif line.startswith("구동 바퀴 수:") or compact.startswith("구동바퀴수:"):
            d["wheels"] = max(1, int(to_float(line, d["wheels"])))
        elif line.startswith("운행 환경:") or compact.startswith("운행환경:"):
            d["env"] = normalize_env(line.split(":", 1)[1].strip())
        elif line.startswith("기타 요구사항:") or compact.startswith("기타요구사항:"):
            d["extra"] = line.split(":", 1)[1].strip()
        elif "요구 동력" in line:
            d["required_power_w"] = to_float(line, 0.0)
        elif "바퀴당" in line and "토크" in line:
            d["required_wheel_torque_nm"] = to_float(line, 0.0)
        elif "휠" in line and "RPM" in line.upper():
            d["required_wheel_rpm"] = to_float(line, 0.0)
        elif "기어비" in line:
            d["gear_ratio"] = max(1.0, to_float(line, d["gear_ratio"]))
        elif "모터" in line and "rpm" in line.lower():
            d["motor_rpm"] = to_float(line, d["motor_rpm"])
        elif "모터" in line and ("토크" in line or "nm" in line.lower()):
            d["motor_torque_nm"] = to_float(line, d["motor_torque_nm"])

    # 목적이 비면 첫 줄에서 유추하지 않고 빈값 유지
    # 초기 설계 요약문에는 바퀴 반지름/모터 토크/기어비가 없을 수 있으므로 합리 기본값 유지
    return d


def parse_json_design(obj):
    d = default_design()
    d["source_mode"] = "JSON 붙여넣기"

    # 여러 형태의 JSON 키를 폭넓게 지원
    src_input = obj.get("input", {}) if isinstance(obj, dict) else {}
    src_result = obj.get("result", {}) if isinstance(obj, dict) else {}
    src_parts = obj.get("parts", {}) if isinstance(obj, dict) else {}
    src_calc = obj.get("calc", {}) if isinstance(obj, dict) else {}
    src_part = obj.get("part", {}) if isinstance(obj, dict) else {}

    def pick(*keys, default=None):
        for area in [obj, src_input, src_result, src_parts, src_calc, src_part]:
            if isinstance(area, dict):
                for k in keys:
                    if k in area and area[k] not in [None, ""]:
                        return area[k]
        return default

    d["purpose"] = str(pick("purpose", "용도", default=""))
    d["scale"] = str(pick("scale", "스케일", default=""))
    d["mass"] = to_float(pick("mass", "질량", default=d["mass"]), d["mass"])

    if pick("targetSpeedMps", "target_speed_mps", "speed_mps", default=None) is not None:
        d["target_speed_mps"] = to_float(pick("targetSpeedMps", "target_speed_mps", "speed_mps"), d["target_speed_mps"])
    else:
        speed = pick("speed", "목표속도", default=d["target_speed_mps"])
        unit = pick("unit", "단위", default="mps")
        d["target_speed_mps"] = speed_to_mps(speed, unit)

    d["wheels"] = max(1, int(to_float(pick("wheels", "구동바퀴수", default=d["wheels"]), d["wheels"])))
    d["env"] = normalize_env(pick("env", "environment", "운행환경", default=d["env"]))
    d["extra"] = str(pick("extra", "기타요구사항", default=""))

    d["wheel_radius_m"] = to_float(pick("wheel_r", "wheelRadiusM", "wheel_radius_m", default=d["wheel_radius_m"]), d["wheel_radius_m"])
    d["motor_rpm"] = to_float(pick("motor_rpm", "motorRpm", default=d["motor_rpm"]), d["motor_rpm"])
    d["motor_torque_nm"] = to_float(pick("motor_nm", "motorTorqueNm", "motor_torque_nm", default=d["motor_torque_nm"]), d["motor_torque_nm"])
    d["gear_ratio"] = max(1.0, to_float(pick("recommendedGearRatio", "best_ratio", "gear_ratio", "ratio", default=d["gear_ratio"]), d["gear_ratio"]))
    d["efficiency"] = min(0.98, max(0.30, to_float(pick("driveEfficiency", "efficiency", default=d["efficiency"]), d["efficiency"])))

    d["required_power_w"] = to_float(pick("requiredPowerW", "required_power_w", "req_power", default=0.0), 0.0)
    d["required_wheel_torque_nm"] = to_float(pick("requiredWheelTorqueNm", "required_wheel_torque_nm", "req_tq", default=0.0), 0.0)
    d["required_wheel_rpm"] = to_float(pick("requiredWheelRpm", "required_wheel_rpm", "req_rpm", default=0.0), 0.0)
    return d

# -----------------------------
# 시뮬레이션 엔진
# -----------------------------

def simulate(design, env_cfg):
    g = 9.81
    mass = max(0.1, design["mass"] + env_cfg["payload_kg"])
    v_target = max(0.01, design["target_speed_mps"])
    r = max(0.02, design["wheel_radius_m"])
    wheels = max(1, int(design["wheels"]))
    motor_rpm = max(1.0, design["motor_rpm"])
    motor_tq = max(0.01, design["motor_torque_nm"])
    gear = max(1.0, design["gear_ratio"])
    eff = min(0.98, max(0.30, design["efficiency"]))
    grade_deg = env_cfg["grade_deg"]
    coeff = env_to_coeff(env_cfg["road"])
    crr, mu, rough = coeff["crr"], coeff["mu"], coeff["rough"]

    # 전력/제어 모드 보정
    control = env_cfg["control_mode"]
    if control == "효율 우선 전력 제어":
        eff *= 1.04
        motor_tq *= 0.94
    elif control == "발열 억제 전력 제어":
        motor_tq *= 0.88
    elif control == "가변 기어비 보조 제어":
        if grade_deg >= 8 or env_cfg["road"] in ["요철/장애물", "험지/흙길"]:
            gear *= 1.20
        else:
            gear *= 0.92

    wheel_torque_total = motor_tq * gear * eff * wheels
    traction_force = wheel_torque_total / r
    normal_force = mass * g * math.cos(math.radians(grade_deg))
    traction_limit = max(0.0, mu * normal_force)
    usable_force = min(traction_force, traction_limit)

    rolling = crr * mass * g * math.cos(math.radians(grade_deg)) * rough
    grade_force = mass * g * math.sin(math.radians(grade_deg))
    aero = 0.5 * 1.225 * 0.8 * 0.7 * v_target**2
    resist_at_target = rolling + grade_force + aero
    net_force = usable_force - resist_at_target
    acceleration = max(0.0, net_force / mass)

    wheel_rpm = motor_rpm / gear
    vmax_by_rpm = (wheel_rpm / 60.0) * (2 * math.pi * r)
    vmax = max(0.0, min(vmax_by_rpm, v_target * 1.25 if acceleration > 0 else 0.0))

    if acceleration <= 0.001:
        accel_time = None
    else:
        accel_time = min(999.0, min(v_target, vmax_by_rpm) / acceleration)

    course_m = max(1.0, env_cfg["course_m"])
    sim_time = max(1.0, env_cfg["target_time_s"])
    dt = 0.2
    t, v, x = 0.0, 0.0, 0.0
    time_list, speed_list, dist_list, batt_list, torque_use_list = [], [], [], [], []
    battery_wh = max(1.0, env_cfg["battery_wh"])
    energy_wh = 0.0

    while t <= sim_time and x < course_m:
        current_resist = rolling + grade_force + 0.5 * 1.225 * 0.8 * 0.7 * v**2
        current_net = max(0.0, usable_force - current_resist)
        a = current_net / mass
        rpm_cap_v = vmax_by_rpm
        v = min(rpm_cap_v, v + a * dt)
        x += v * dt
        mech_power = max(0.0, current_resist * max(v, 0.1))
        electric_power = mech_power / max(0.2, eff) + 20.0
        if env_cfg["obstacle_level"] == "중간":
            electric_power *= 1.10
        elif env_cfg["obstacle_level"] == "높음":
            electric_power *= 1.25
        energy_wh += electric_power * dt / 3600.0
        batt_percent = max(0.0, 100.0 * (1.0 - energy_wh / battery_wh))
        required_torque_total = resist_at_target * r
        torque_use = 100.0 * required_torque_total / max(wheel_torque_total, 0.001)

        time_list.append(t)
        speed_list.append(v)
        dist_list.append(x)
        batt_list.append(batt_percent)
        torque_use_list.append(min(180.0, torque_use))
        t += dt

    required_wheel_torque_each = resist_at_target * r / wheels
    available_wheel_torque_each = wheel_torque_total / wheels
    torque_margin = (available_wheel_torque_each - required_wheel_torque_each) / max(required_wheel_torque_each, 0.001) * 100
    speed_ratio = vmax_by_rpm / v_target * 100

    brake_decel = max(0.5, min(5.5, mu * g * 0.65))
    braking_distance = v_target**2 / (2 * brake_decel)

    avg_power = (energy_wh / max(t, 0.1)) * 3600.0
    runtime_h = battery_wh / max(avg_power, 1.0)
    range_m = runtime_h * 3600.0 * min(v_target, vmax_by_rpm)

    load_ratio = resist_at_target / max(usable_force, 0.001)
    if load_ratio < 0.55:
        heat = "낮음"
    elif load_ratio < 0.78:
        heat = "보통"
    elif load_ratio < 1.0:
        heat = "높음"
    else:
        heat = "위험"

    pass_speed = "PASS" if speed_ratio >= 95 else ("WARNING" if speed_ratio >= 75 else "FAIL")
    pass_torque = "PASS" if torque_margin >= 30 else ("WARNING" if torque_margin >= 0 else "FAIL")
    pass_grade = "PASS" if net_force > 0 else "FAIL"
    pass_battery = "PASS" if runtime_h * 60 >= env_cfg["target_time_s"] / 60 else "WARNING"
    pass_heat = "PASS" if heat in ["낮음", "보통"] else ("WARNING" if heat == "높음" else "FAIL")
    pass_brake = "PASS" if braking_distance <= 3.0 else ("WARNING" if braking_distance <= 7.0 else "FAIL")

    score = 100
    for p in [pass_speed, pass_torque, pass_grade, pass_battery, pass_heat, pass_brake]:
        if p == "WARNING":
            score -= 10
        elif p == "FAIL":
            score -= 25
    score = max(0, min(100, score))

    return {
        "mass_total": mass,
        "wheel_torque_each": available_wheel_torque_each,
        "required_torque_each": required_wheel_torque_each,
        "torque_margin": torque_margin,
        "wheel_rpm": wheel_rpm,
        "vmax_by_rpm": vmax_by_rpm,
        "speed_ratio": speed_ratio,
        "acceleration": acceleration,
        "accel_time": accel_time,
        "usable_force": usable_force,
        "resist_at_target": resist_at_target,
        "runtime_min": runtime_h * 60,
        "range_m": range_m,
        "avg_power": avg_power,
        "energy_wh": energy_wh,
        "heat": heat,
        "braking_distance": braking_distance,
        "score": score,
        "judgement": {
            "목표 속도": pass_speed,
            "토크 여유": pass_torque,
            "등판/노면 통과": pass_grade,
            "배터리 지속성": pass_battery,
            "발열 위험": pass_heat,
            "제동 안정성": pass_brake,
        },
        "series": {
            "time": time_list,
            "speed": speed_list,
            "distance": dist_list,
            "battery": batt_list,
            "torque_use": torque_use_list,
        }
    }

# -----------------------------
# 시각화
# -----------------------------

def draw_virtual_scene(design, env_cfg, result):
    fig, ax = plt.subplots(figsize=(10, 4.8))
    ax.set_xlim(0, 100)
    ax.set_ylim(0, 60)
    ax.axis("off")
    ax.set_facecolor("#f7f9fc")

    grade = env_cfg["grade_deg"]
    base_y = 18
    slope_h = min(25, grade * 0.6)
    ax.plot([0, 100], [base_y, base_y + slope_h], color="#555", linewidth=4)
    ax.text(3, base_y - 5, f"노면: {env_cfg['road']} / 경사 {grade:.1f}°", fontsize=11, color="#333")

    x0 = 42
    y0 = base_y + slope_h * (x0 / 100) + 7
    purpose = design.get("purpose", "")
    extra = design.get("extra", "")
    text = (purpose + " " + extra).lower()

    if any(k in text for k in ["킥보드", "스쿠터", "scooter"]):
        # 스쿠터형
        ax.plot([x0-8, x0+10], [y0, y0], color="#1f77b4", lw=4)
        ax.plot([x0+7, x0+12], [y0, y0-18], color="#1f77b4", lw=4)
        ax.plot([x0+12, x0+16], [y0-18, y0-17], color="#1f77b4", lw=3)
        ax.add_patch(patches.Circle((x0-8, y0+3), 3.8, fill=False, lw=3, edgecolor="#222"))
        ax.add_patch(patches.Circle((x0+10, y0+3), 3.8, fill=False, lw=3, edgecolor="#222"))
        ax.text(x0-7, y0-7, "배터리", fontsize=8)
    elif any(k in text for k in ["전기차", "자동차", "ev", "차형"]):
        # 자동차형
        ax.add_patch(patches.Rectangle((x0-16, y0-8), 32, 10, fill=False, lw=3, edgecolor="#1f77b4"))
        ax.add_patch(patches.Polygon([[x0-9,y0-8],[x0-3,y0-17],[x0+8,y0-17],[x0+15,y0-8]], fill=False, lw=3, edgecolor="#1f77b4"))
        ax.add_patch(patches.Circle((x0-9, y0+4), 4.5, fill=False, lw=3, edgecolor="#222"))
        ax.add_patch(patches.Circle((x0+11, y0+4), 4.5, fill=False, lw=3, edgecolor="#222"))
        ax.text(x0-13, y0-2, "모터/감속", fontsize=8)
    elif any(k in text for k in ["궤도", "트랙", "track"]):
        # 궤도형
        ax.add_patch(patches.FancyBboxPatch((x0-18, y0-2), 36, 10, boxstyle="round,pad=0.2,rounding_size=5", fill=False, lw=3, edgecolor="#222"))
        ax.add_patch(patches.Rectangle((x0-14, y0-15), 28, 13, fill=False, lw=3, edgecolor="#1f77b4"))
        ax.text(x0-11, y0-7, "센서/제어", fontsize=8)
    else:
        # 일반 로봇형
        ax.add_patch(patches.Rectangle((x0-16, y0-11), 32, 13, fill=False, lw=3, edgecolor="#1f77b4"))
        ax.add_patch(patches.Circle((x0-11, y0+4), 4.5, fill=False, lw=3, edgecolor="#222"))
        ax.add_patch(patches.Circle((x0+11, y0+4), 4.5, fill=False, lw=3, edgecolor="#222"))
        ax.add_patch(patches.Rectangle((x0-5, y0-8), 10, 6, fill=False, lw=2, edgecolor="#d62728"))
        ax.text(x0-14, y0-15, "가상 모빌리티", fontsize=9)

    ax.arrow(x0 + 20, y0 - 5, 16, 0, head_width=3, head_length=4, color="#2ca02c", linewidth=2)
    ax.text(x0 + 20, y0 - 11, f"예상 최고속도 {result['vmax_by_rpm']:.2f} m/s", fontsize=10, color="#2ca02c")
    ax.text(3, 55, f"배터리 예상 지속: {result['runtime_min']:.1f}분 / 종합 점수: {result['score']}/100", fontsize=12, weight="bold")
    st.pyplot(fig)


def plot_series(result):
    s = result["series"]
    fig, axs = plt.subplots(2, 2, figsize=(11, 6))
    axs[0,0].plot(s["time"], s["speed"], color="#1f77b4")
    axs[0,0].set_title("시간-속도")
    axs[0,0].set_xlabel("시간(s)")
    axs[0,0].set_ylabel("속도(m/s)")
    axs[0,1].plot(s["time"], s["distance"], color="#2ca02c")
    axs[0,1].set_title("시간-거리")
    axs[0,1].set_xlabel("시간(s)")
    axs[0,1].set_ylabel("거리(m)")
    axs[1,0].plot(s["time"], s["battery"], color="#ff7f0e")
    axs[1,0].set_title("배터리 잔량")
    axs[1,0].set_xlabel("시간(s)")
    axs[1,0].set_ylabel("잔량(%)")
    axs[1,1].plot(s["time"], s["torque_use"], color="#d62728")
    axs[1,1].axhline(100, color="#555", ls="--", lw=1)
    axs[1,1].set_title("토크 사용률")
    axs[1,1].set_xlabel("시간(s)")
    axs[1,1].set_ylabel("사용률(%)")
    plt.tight_layout()
    st.pyplot(fig)

# -----------------------------
# 앱 UI
# -----------------------------

st.title("🧪 가상환경 모빌리티 테스트베드")
st.caption("초기 설계 도움 시스템에서 복사한 값 또는 직접 입력값을 바탕으로, 실제 제작 전 가상환경에서 주행 성능을 예측합니다.")

if "design" not in st.session_state:
    st.session_state.design = default_design()

left, right = st.columns([1.05, 1.15])

with left:
    st.header("1. 설계 데이터 붙여넣기")
    st.write("초기 설계 도움 시스템에서 복사한 **JSON 또는 요약문**을 아래에 붙여넣으세요. 붙여넣기 없이 직접 입력만 사용해도 됩니다.")
    raw = st.text_area("JSON/요약문 데이터 붙여넣기", height=230, placeholder="예시: { ... } 또는 [모빌리티 구동계 초기 설계 요약]으로 시작하는 요약문")
    c1, c2 = st.columns(2)
    with c1:
        if st.button("📥 붙여넣은 설계 데이터 적용", use_container_width=True):
            try:
                st.session_state.design = parse_design_text(raw)
                st.success("설계 데이터를 적용했습니다. 일반 요약문도 자동 해석했습니다.")
            except Exception as e:
                st.error(f"데이터 해석에 실패했습니다: {e}")
                st.info("현재 붙여넣은 내용이 JSON이 아니라면, 이 수정본에서는 일반 요약문도 처리합니다. 그래도 안 되면 요약문 전체를 그대로 붙여넣었는지 확인하세요.")
    with c2:
        if st.button("🧹 붙여넣기 내용 비우기", use_container_width=True):
            st.rerun()

    st.divider()
    st.header("2. 모빌리티 직접 설정")
    d = st.session_state.design
    d["purpose"] = st.text_input("모빌리티 용도/이름", value=d.get("purpose", ""))
    d["scale"] = st.text_input("스케일", value=d.get("scale", ""))
    d["mass"] = st.number_input("총 질량 kg", min_value=0.1, value=float(d.get("mass", 30.0)), step=1.0)
    d["target_speed_mps"] = st.number_input("목표 속도 m/s", min_value=0.01, value=float(d.get("target_speed_mps", 1.5)), step=0.1)
    d["wheels"] = st.number_input("구동 바퀴 수", min_value=1, max_value=12, value=int(d.get("wheels", 4)), step=1)
    d["wheel_radius_m"] = st.number_input("바퀴 반지름 m", min_value=0.02, max_value=1.0, value=float(d.get("wheel_radius_m", 0.10)), step=0.01)
    d["motor_rpm"] = st.number_input("모터 기준 RPM", min_value=1.0, value=float(d.get("motor_rpm", 3000.0)), step=100.0)
    d["motor_torque_nm"] = st.number_input("모터 1개 기준 토크 Nm", min_value=0.01, value=float(d.get("motor_torque_nm", 0.50)), step=0.05)
    d["gear_ratio"] = st.number_input("감속비", min_value=1.0, value=float(d.get("gear_ratio", 18.0)), step=1.0)
    d["efficiency"] = st.slider("구동계 효율", min_value=0.30, max_value=0.98, value=float(d.get("efficiency", 0.85)), step=0.01)
    d["extra"] = st.text_area("기타 요구사항", value=d.get("extra", ""), height=80)
    st.session_state.design = d

with right:
    st.header("3. 가상환경 설정")
    road = st.selectbox("노면 종류", ["실내/평지", "일반 도로", "요철/장애물", "험지/흙길"], index=["실내/평지", "일반 도로", "요철/장애물", "험지/흙길"].index(st.session_state.design.get("env", "실내/평지")) if st.session_state.design.get("env", "실내/평지") in ["실내/평지", "일반 도로", "요철/장애물", "험지/흙길"] else 0)
    col_a, col_b = st.columns(2)
    with col_a:
        grade_deg = st.slider("경사각 °", min_value=0.0, max_value=35.0, value=8.0, step=0.5)
        course_m = st.number_input("코스 길이 m", min_value=1.0, value=30.0, step=5.0)
        battery_wh = st.number_input("배터리 용량 Wh", min_value=1.0, value=480.0, step=10.0)
    with col_b:
        obstacle_level = st.selectbox("장애물 수준", ["없음", "낮음", "중간", "높음"])
        payload_kg = st.number_input("추가 적재 하중 kg", min_value=0.0, value=0.0, step=1.0)
        target_time_s = st.number_input("목표 주행 시간 s", min_value=1.0, value=60.0, step=10.0)
    control_mode = st.selectbox("전력/반도체 제어 방식", ["일반 제어", "효율 우선 전력 제어", "발열 억제 전력 제어", "가변 기어비 보조 제어"])

    env_cfg = {
        "road": road,
        "grade_deg": grade_deg,
        "course_m": course_m,
        "battery_wh": battery_wh,
        "obstacle_level": obstacle_level,
        "payload_kg": payload_kg,
        "target_time_s": target_time_s,
        "control_mode": control_mode,
    }

    st.divider()
    st.header("4. 가상 주행 시뮬레이션")
    if st.button("🚗 가상 주행 시작", type="primary", use_container_width=True):
        st.session_state.result = simulate(st.session_state.design, env_cfg)
        st.session_state.env_cfg = env_cfg

    if "result" in st.session_state:
        result = st.session_state.result
        design = st.session_state.design
        st.subheader("성능 요약")
        m1, m2, m3, m4 = st.columns(4)
        m1.metric("예상 최고 속도", f"{result['vmax_by_rpm']:.2f} m/s")
        m2.metric("토크 여유율", f"{result['torque_margin']:.1f}%")
        m3.metric("예상 주행 시간", f"{result['runtime_min']:.1f}분")
        m4.metric("종합 점수", f"{result['score']} / 100")

        m5, m6, m7, m8 = st.columns(4)
        accel_text = "도달 불가" if result["accel_time"] is None else f"{result['accel_time']:.1f}s"
        m5.metric("0→목표속도", accel_text)
        m6.metric("발열 위험도", result["heat"])
        m7.metric("제동 거리", f"{result['braking_distance']:.2f} m")
        m8.metric("평균 소비전력", f"{result['avg_power']:.0f} W")

        st.subheader("PASS / WARNING / FAIL 판정")
        st.table([{"항목": k, "판정": v} for k, v in result["judgement"].items()])

        st.subheader("2D 가상 주행 화면")
        draw_virtual_scene(design, st.session_state.env_cfg, result)

        st.subheader("성능 변화 그래프")
        plot_series(result)

        st.subheader("시뮬레이션 로그")
        logs = []
        logs.append(f"[시작] 질량 {result['mass_total']:.1f}kg, 목표 속도 {design['target_speed_mps']:.2f}m/s 조건으로 가상 주행을 시작했습니다.")
        logs.append(f"[구동계] 감속비 {design['gear_ratio']:.1f}:1, 바퀴 반지름 {design['wheel_radius_m']:.2f}m, 바퀴당 가용 토크 {result['wheel_torque_each']:.2f}Nm로 계산되었습니다.")
        logs.append(f"[환경] {st.session_state.env_cfg['road']}, 경사 {st.session_state.env_cfg['grade_deg']:.1f}°, 장애물 {st.session_state.env_cfg['obstacle_level']} 조건을 적용했습니다.")
        logs.append(f"[판정] 종합 점수는 {result['score']}/100이며, 발열 위험도는 {result['heat']}입니다.")
        st.code("\n".join(logs), language="text")

        st.subheader("보고서용 해석문")
        analysis = f"해당 모빌리티는 '{design.get('purpose','미지정')}' 용도로 설정되었으며, 총 질량 {result['mass_total']:.1f}kg, 목표 속도 {design['target_speed_mps']:.2f}m/s 조건에서 가상환경 주행을 수행하였다. 감속비 {design['gear_ratio']:.1f}:1과 모터 토크 {design['motor_torque_nm']:.2f}Nm를 적용했을 때 예상 최고 속도는 {result['vmax_by_rpm']:.2f}m/s, 토크 여유율은 {result['torque_margin']:.1f}%로 계산되었다. {st.session_state.env_cfg['road']} 및 경사 {st.session_state.env_cfg['grade_deg']:.1f}° 조건에서의 종합 적합도는 {result['score']}/100점이며, 발열 위험도는 {result['heat']}으로 예측되었다. 따라서 실제 제작 전에는 토크 여유율, 배터리 지속성, 제동 거리 항목을 중심으로 설계를 보완하는 것이 필요하다."
        st.write(analysis)

        export_obj = {
            "testbed_result": result,
            "design": design,
            "environment": st.session_state.env_cfg,
            "report_text": analysis,
        }
        st.download_button("📄 테스트베드 결과 JSON 다운로드", data=json.dumps(export_obj, ensure_ascii=False, indent=2), file_name="virtual_mobility_testbed_result.json", mime="application/json")
    else:
        st.info("왼쪽에서 설계값을 붙여넣거나 직접 입력한 뒤, [가상 주행 시작] 버튼을 누르세요.")

st.divider()
st.caption("주의: 본 프로그램은 교육·탐구용 성능 예측 도구이며, 실제 제작 전에는 실측 데이터와 안전 검증이 필요합니다.")

