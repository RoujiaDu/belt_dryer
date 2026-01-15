#!/usr/bin/env python
# belt_dryer_app.py - 带式干燥机计算系统
# 兼容 Streamlit >= 1.52.2 和 Altair >= 5.5.0
# 已移除所有旧版 Altair (v4) 语法

import os
import sys
import math


# --- 前置库检查和兼容性处理 ---
def check_and_import():
    """检查并导入库，处理兼容性问题"""
    import_error_messages = []

    # 1. 检查并导入 streamlit
    try:
        import streamlit as st
        st_version = st.__version__
        print(f"[INFO] Streamlit 版本: {st_version}")
    except ImportError as e:
        import_error_messages.append(f"Streamlit 导入失败: {e}")

        # 创建伪对象避免后续错误
        class FakeSt:
            __version__ = "0.0.0"

            def __getattr__(self, name):
                return lambda *args, **kwargs: None

        st = FakeSt()

    # 2. 检查并导入 pandas
    try:
        import pandas as pd
        print(f"[INFO] Pandas 已成功导入")
    except ImportError as e:
        import_error_messages.append(f"Pandas 导入失败: {e}")
        pd = None

    # 3. 检查并导入 altair (但本应用当前版本未直接使用其可视化功能)
    # 此行仅为确保环境中有altair，但应用逻辑不依赖它绘图
    try:
        import altair as alt
        alt_version = alt.__version__
        print(f"[INFO] Altair 版本: {alt_version}")

        # 关键：验证是否为新版API，避免使用 v4 旧语法
        if hasattr(alt, 'Chart'):
            print(f"[INFO] Altair API 检查通过 (使用新版语法)")
        else:
            print(f"[WARN] Altair API 可能与预期不符")

    except ImportError as e:
        # 如果应用不绘图，缺少altair可能不是致命错误
        print(f"[INFO] Altair 未安装或导入失败: {e}")
        print(f"[INFO] 本应用核心计算功能不受影响，但高级图表功能将不可用。")
        alt = None

    # 如果有致命导入错误，显示并退出
    if import_error_messages and 'FakeSt' not in str(type(st)):
        st.error("## ⚠️ 库导入错误")
        for msg in import_error_messages:
            st.error(msg)
        st.stop()

    return st, pd


# 执行导入检查
st, pd = check_and_import()

# --- Streamlit 页面配置 ---
# 注意：此部分必须在所有st命令之前
if not hasattr(st, '__version__'):
    # 如果st是伪对象，直接退出
    print("错误: Streamlit 未正确安装。请使用 'pip install streamlit==1.52.2' 安装。")
    sys.exit(1)

st.set_page_config(
    page_title="带式干燥机计算系统",
    page_icon="🌡️",
    layout="wide",
    initial_sidebar_state="expanded"
)


# --- 计算函数定义 (与原算法一致) ---
def calculate_humidity_parameters_high_temp(T_db, RH, P=101325):
    """计算湿空气的含湿量和焓值（适用于20-80°C高温范围）"""
    if T_db < 20 or T_db > 80:
        st.warning(f"警告：温度{T_db}°C超出推荐范围(20-80°C)，计算结果可能不准确")

    T_k = T_db + 273.15
    C1 = -5800.2206
    C2 = 1.3914993
    C3 = -0.048640239
    C4 = 0.41764768e-4
    C5 = -0.14452093e-7
    C6 = 6.5459673

    ln_P_sat = C1 / T_k + C2 + C3 * T_k + C4 * T_k ** 2 + C5 * T_k ** 3 + C6 * math.log(T_k)
    P_sat = math.exp(ln_P_sat)
    P_w = (RH / 100.0) * P_sat

    if P <= P_w:
        st.error("错误：水蒸气分压不能大于或等于总压")
        return None

    W = 0.621945 * P_w / (P - P_w)

    Cp_air = 1.006 + 0.00005 * (T_db - 20)
    Cp_vapor = 1.86 + 0.0004 * (T_db - 20)
    h_fg = 2501 - 2.42 * T_db
    h = Cp_air * T_db + W * (h_fg + Cp_vapor * T_db)

    R_air = 287.058
    R_vapor = 461.495
    v_mix = (R_air + W * R_vapor) * T_k / (P * (1 + W))

    results = {
        '含湿量 (g/kg干空气)': round(W * 1000, 2),
        '焓值 (kJ/kg干空气)': round(h, 2),
        '湿空气比容 (m³/kg)': round(v_mix, 4)
    }

    return results


def belt_dryer_design(temp1, humidity1, temp2, humidity2, temp3, humidity3,
                      temp4, humidity4, temp5, humidity5, temp6, humidity6,
                      temp7, humidity7, temp8, humidity8, water_volume,
                      dry_sludge_volume, inlet_sludge_temp, outlet_sludge_temp,
                      bypass_ratio, air_density, water_evaporation_heat,
                      water_condensation_heat, sludge_dry_c, water_c):
    # 风量计算
    WC5 = calculate_humidity_parameters_high_temp(temp5, humidity5)['含湿量 (g/kg干空气)']
    WC4 = calculate_humidity_parameters_high_temp(temp4, humidity4)['含湿量 (g/kg干空气)']
    air_volume2 = water_volume * 1000 / (WC4 - WC5) / air_density if (WC4 - WC5) != 0 else 0
    air_volume1 = air_volume2 / (1 - bypass_ratio) - air_volume2 if bypass_ratio != 1 else 0

    # 污泥干化需热量
    heat_requirement = (water_volume / 3600 * water_evaporation_heat +
                        water_volume / 3600 * water_c * (outlet_sludge_temp - inlet_sludge_temp) +
                        dry_sludge_volume / 24 / 3600 * 1000 * sludge_dry_c * (outlet_sludge_temp - inlet_sludge_temp))

    # 除湿需冷量
    cooling_capacity = (water_volume / 3600 * water_condensation_heat +
                        (temp6 - temp5) * water_c * water_volume / 3600)

    # 理论制热量
    H1 = calculate_humidity_parameters_high_temp(temp1, humidity1)['焓值 (kJ/kg干空气)']
    H8 = calculate_humidity_parameters_high_temp(temp8, humidity8)['焓值 (kJ/kg干空气)']
    heat1 = (H1 - H8) * air_volume1 * air_density / 3600 if air_volume1 > 0 else 0

    H7 = calculate_humidity_parameters_high_temp(temp7, humidity7)['焓值 (kJ/kg干空气)']
    H6 = calculate_humidity_parameters_high_temp(temp6, humidity6)['焓值 (kJ/kg干空气)']
    heat2 = (H7 - H6) * air_volume2 * air_density / 3600 if air_volume2 > 0 else 0

    heat = heat1 + heat2

    # 理论制冷量
    H4 = calculate_humidity_parameters_high_temp(temp4, humidity4)['焓值 (kJ/kg干空气)']
    H5 = calculate_humidity_parameters_high_temp(temp5, humidity5)['焓值 (kJ/kg干空气)']
    cooling = (H4 - H5) * air_volume2 * air_density / 3600 if air_volume2 > 0 else 0

    # 表冷器制冷量
    H2 = calculate_humidity_parameters_high_temp(temp2, humidity2)['焓值 (kJ/kg干空气)']
    H3 = calculate_humidity_parameters_high_temp(temp3, humidity3)['焓值 (kJ/kg干空气)']
    out_cooling = (H2 - H3) * air_volume2 * air_density / 3600 if air_volume2 > 0 else 0

    result = {
        '加热风量 (m³/h)': round(air_volume1, 2),
        '除湿风量 (m³/h)': round(air_volume2, 2),
        '总风量 (m³/h)': round(air_volume1 + air_volume2, 2),
        '污泥干化需热量 (kW)': round(heat_requirement, 2),
        '除湿需冷量 (kW)': round(cooling_capacity, 2),
        '理论制热量 (kW)': round(heat, 2),
        '上冷凝器制热量 (kW)': round(heat1, 2),
        '下冷凝器制热量 (kW)': round(heat2, 2),
        '理论制冷量 (kW)': round(cooling, 2),
        '表冷器制冷量 (kW)': round(out_cooling, 2)
    }

    return result


# --- 主应用界面 ---
st.title("🌡️ 低温带式干化机热力计算系统")
st.markdown("---")

# 侧边栏输入
st.sidebar.header("📊 输入参数")

# 分组输入参数
st.sidebar.subheader("1. 基本参数")
water_volume = st.sidebar.number_input("去水量 (kg/h)", value=250.0, min_value=0.0, step=1.0)
dry_sludge_volume = st.sidebar.number_input("绝干污泥量 (t/d)", value=1.8, min_value=0.0, step=0.1)
inlet_sludge_temp = st.sidebar.number_input("入口污泥温度 (°C)", value=15.0, min_value=0.0, step=1.0)
outlet_sludge_temp = st.sidebar.number_input("出口污泥温度 (°C)", value=50.0, min_value=0.0, step=1.0)

st.sidebar.subheader("2. 物性参数")
sludge_dry_c = st.sidebar.number_input("污泥干基比热容 (kJ/(kg·℃))", value=1.94, min_value=0.0, step=0.01)
water_c = st.sidebar.number_input("水比热容 (kJ/(kg·℃))", value=4.18, min_value=0.0, step=0.01)
water_evaporation_heat = st.sidebar.number_input("50℃水汽化潜热 (kJ/kg)", value=2382.0, min_value=0.0, step=1.0)
water_condensation_heat = st.sidebar.number_input("33℃水冷凝潜热 (kJ/kg)", value=2420.0, min_value=0.0, step=1.0)
air_density = st.sidebar.number_input("空气密度 (kg/m³)", value=1.06, min_value=0.0, step=0.01)

st.sidebar.subheader("3. 风量参数")
bypass_ratio = st.sidebar.slider("风量旁通比", value=0.6, min_value=0.0, max_value=1.0, step=0.01)

st.sidebar.subheader("4. 各工况点温湿度")
col_temp, col_hum = st.sidebar.columns(2)

with col_temp:
    st.markdown("**温度 (°C)**")
    temp1 = st.number_input("上出风温度", value=73.6, min_value=0.0, step=0.1, key="temp1")
    temp8 = st.number_input("上回风温度", value=58.6, min_value=0.0, step=0.1, key="temp8")
    temp7 = st.number_input("下出风温度", value=71.1, min_value=0.0, step=0.1, key="temp7")
    temp2 = st.number_input("表冷器进风温度", value=54.7, min_value=0.0, step=0.1, key="temp2")
    temp3 = st.number_input("表冷器出风温度", value=50.4, min_value=0.0, step=0.1, key="temp3")
    temp4 = st.number_input("蒸发器进风温度", value=45.8, min_value=0.0, step=0.1, key="temp4")
    temp5 = st.number_input("蒸发器出风温度", value=36.5, min_value=0.0, step=0.1, key="temp5")
    temp6 = st.number_input("下冷凝器进风温度", value=44.9, min_value=0.0, step=0.1, key="temp6")

with col_hum:
    st.markdown("**相对湿度 (%)**")
    humidity1 = st.number_input("上出风湿度", value=33.0, min_value=0.0, max_value=100.0, step=0.1, key="hum1")
    humidity8 = st.number_input("上回风湿度", value=63.0, min_value=0.0, max_value=100.0, step=0.1, key="hum8")
    humidity7 = st.number_input("下出风湿度", value=23.0, min_value=0.0, max_value=100.0, step=0.1, key="hum7")
    humidity2 = st.number_input("表冷器进风湿度", value=63.0, min_value=0.0, max_value=100.0, step=0.1, key="hum2")
    humidity3 = st.number_input("表冷器出风湿度", value=73.0, min_value=0.0, max_value=100.0, step=0.1, key="hum3")
    humidity4 = st.number_input("蒸发器进风湿度", value=83.7, min_value=0.0, max_value=100.0, step=0.1, key="hum4")
    humidity5 = st.number_input("蒸发器出风湿度", value=83.7, min_value=0.0, max_value=100.0, step=0.1, key="hum5")
    humidity6 = st.number_input("下冷凝器进风湿度", value=76.0, min_value=0.0, max_value=100.0, step=0.1, key="hum6")

# 计算按钮和结果显示
st.markdown("### 📈 计算分析")
if st.button("🚀 开始计算", type="primary", use_container_width=True):
    st.markdown("---")

    with st.spinner("正在计算中，请稍候..."):
        try:
            result = belt_dryer_design(
                temp1, humidity1, temp2, humidity2, temp3, humidity3,
                temp4, humidity4, temp5, humidity5, temp6, humidity6,
                temp7, humidity7, temp8, humidity8, water_volume,
                dry_sludge_volume, inlet_sludge_temp, outlet_sludge_temp,
                bypass_ratio, air_density, water_evaporation_heat,
                water_condensation_heat, sludge_dry_c, water_c
            )

            st.success("✅ 计算完成！")

            # 显示关键结果
            col1, col2 = st.columns(2)
            with col1:
                st.markdown("#### 🔥 热量参数")
                st.metric("污泥干化需热量", f"{result['污泥干化需热量 (kW)']} kW")
                st.metric("理论总制热量", f"{result['理论制热量 (kW)']} kW")
                st.metric("上冷凝器制热量", f"{result['上冷凝器制热量 (kW)']} kW")
                st.metric("下冷凝器制热量", f"{result['下冷凝器制热量 (kW)']} kW")

            with col2:
                st.markdown("#### ❄️ 冷量参数")
                st.metric("除湿需冷量", f"{result['除湿需冷量 (kW)']} kW")
                st.metric("理论制冷量", f"{result['理论制冷量 (kW)']} kW")
                st.metric("表冷器制冷量", f"{result['表冷器制冷量 (kW)']} kW")

            st.markdown("---")
            st.markdown("#### 🌬️ 风量参数")
            col3, col4, col5 = st.columns(3)
            with col3:
                st.metric("加热风量", f"{result['加热风量 (m³/h)']} m³/h")
            with col4:
                st.metric("除湿风量", f"{result['除湿风量 (m³/h)']} m³/h")
            with col5:
                st.metric("总风量", f"{result['总风量 (m³/h)']} m³/h")

            # 详细结果表格
            st.markdown("---")
            st.markdown("#### 📋 详细计算结果表")
            if pd is not None:
                result_df = pd.DataFrame(list(result.items()), columns=['参数', '数值'])
                st.dataframe(result_df, use_container_width=True, hide_index=True)
            else:
                for key, value in result.items():
                    st.text(f"{key}: {value}")

            # 性能分析
            st.markdown("---")
            st.markdown("#### 📊 系统性能分析")
            if result['污泥干化需热量 (kW)'] > 0:
                heat_efficiency = (result['理论制热量 (kW)'] / result['污泥干化需热量 (kW)']) * 100
                cooling_efficiency = (result['理论制冷量 (kW)'] / result['除湿需冷量 (kW)']) * 100 if result[
                                                                                                          '除湿需冷量 (kW)'] > 0 else 0

                eff_col1, eff_col2 = st.columns(2)
                with eff_col1:
                    st.metric("制热效率", f"{min(heat_efficiency, 100):.1f} %")
                with eff_col2:
                    st.metric("制冷效率", f"{min(cooling_efficiency, 100):.1f} %")

                if heat_efficiency < 80:
                    st.warning("⚠️ 制热效率较低，建议检查上/下冷凝器进出风温湿度参数。")
                if cooling_efficiency < 80:
                    st.warning("⚠️ 制冷效率较低，建议检查蒸发器及表冷器进出风温湿度参数。")
                if heat_efficiency >= 80 and cooling_efficiency >= 80:
                    st.success("🎉 系统设计合理，热力性能良好！")

        except Exception as e:
            st.error(f"计算过程中出现错误: {e}")
            st.info("请检查输入参数是否在合理范围内，并确保所有必需参数已填写。")

# 使用说明
st.markdown("---")
with st.expander("📖 使用说明与注意事项", expanded=False):
    st.markdown("""
    ### 系统功能
    本系统用于带式干燥机的热力计算与性能分析，主要功能包括：
    1.  **参数输入**：通过侧边栏输入干燥机各项运行参数。
    2.  **核心计算**：基于热力学原理计算风量、热量、冷量需求。
    3.  **结果展示**：以指标卡片和表格形式展示详细计算结果。
    4.  **性能评估**：自动计算并评估系统的制热与制冷效率。

    ### 输入参数说明
    - **基本参数**：去水量、污泥处理量、进出口温度等核心工艺参数。
    - **物性参数**：物料与空气的比热容、潜热等物理性质。
    - **风量参数**：系统内部风量旁通比。
    - **工况点温湿度**：系统各关键测量点的空气温度和相对湿度。

    ### 输出结果说明
    - **风量参数**：加热、除湿及总风量。
    - **热量参数**：干燥所需热量及各冷凝器制热量。
    - **冷量参数**：除湿所需冷量及各冷却设备制冷量。
    - **性能分析**：系统制热与制冷效率，并提供优化建议。

    ### 注意事项
    - 计算结果基于理论热力学模型，实际应用时需考虑设备效率及安全系数。
    - 输入温度超出20-80°C范围时，计算精度可能下降，系统会给出提示。
    - 确保所有输入参数为正值且符合物理逻辑（如湿度不超过100%）。
    """)

st.markdown("---")
st.caption(f"带式干燥机热力计算系统 | Streamlit {st.__version__} | 兼容 Altair 5.x")

# --- 运行检查 ---
if __name__ == "__main__":
    # 直接运行时，检查是否通过 streamlit run 启动
    if len(sys.argv) > 1 and sys.argv[1] == "--direct-check":
        print("[INFO] 库兼容性检查通过。")
        print(f"[INFO] 请使用 'streamlit run {os.path.basename(__file__)}' 启动应用。")