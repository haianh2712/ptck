# File: modules/benchmarking/benchmark_view.py
# Purpose: Hiển thị Tab La Bàn với bộ lọc 3 chế độ (VPS | VCK | Tổng hợp)

import streamlit as st
import plotly.express as px
import pandas as pd
from modules.benchmarking.intelligence import MarketIntelligence
from modules.benchmarking.loader import create_compass_engine # Import Factory

def render_benchmark_tab(vck_data_tuple, vps_events, live_prices):
    """
    vck_data_tuple: (raw_events_vck, file_path_vck)
    vps_events: raw_events_vps
    """
    st.markdown("### 🧭 LA BÀN THỊ TRƯỜNG: Bạn vs. VN-Index")

    # 1. BỘ LỌC TÀI KHOẢN (UI)
    # Tách data VCK từ tuple
    raw_vck, path_vck = vck_data_tuple if vck_data_tuple else (None, None)
    
    # Tạo danh sách lựa chọn khả dụng
    options = ["Tổng hợp"]
    if raw_vck: options.append("Tài khoản VCK")
    if vps_events: options.append("Tài khoản VPS")
    
    # Hiển thị nút chọn nằm ngang
    view_mode = st.radio("🔍 Chọn góc nhìn:", options, horizontal=True)
    
    # 2. XỬ LÝ LOGIC TẠO ENGINE THEO LỰA CHỌN
    engine = None
    
    with st.spinner(f"Đang tính toán dữ liệu cho {view_mode}..."):
        if view_mode == "Tổng hợp":
            # Nạp cả hai
            engine = create_compass_engine(raw_vck, path_vck, vps_events)
        elif view_mode == "Tài khoản VCK":
            # Chỉ nạp VCK (VPS = None)
            engine = create_compass_engine(raw_vck, path_vck, None)
        elif view_mode == "Tài khoản VPS":
            # Chỉ nạp VPS (VCK = None)
            engine = create_compass_engine(None, None, vps_events)

    if not engine:
        st.warning("Chưa có dữ liệu để hiển thị.")
        return

    # 3. TÍNH TOÁN CHỈ SỐ (Dùng Engine vừa tạo)
    brain = MarketIntelligence()
    alpha_data = brain.calculate_alpha(engine, live_prices)
    
    if not alpha_data or alpha_data['net_deposit'] == 0:
        st.info(f"⚠️ {view_mode} chưa có dòng tiền thực tế.")
        return

    # 4. HIỂN THỊ KPI (Metrics) - [ĐÃ SỬA MÀU SẮC]
    st.markdown(f"#### 📈 Hiệu quả: {view_mode}")
    c1, c2, c3 = st.columns(3)
    
    roi = alpha_data['port_return']
    mkt = alpha_data['market_return']
    alpha = alpha_data['alpha']
    
    # 1. Hiệu quả Danh mục (ROI)
    # delta_color="normal": Dương -> Xanh, Âm -> Đỏ
    c1.metric(
        "Hiệu quả Danh mục (ROI)", 
        f"{roi:.2f}%", 
        delta=f"{roi:.2f}%",
        delta_color="normal" 
    )

    # 2. Hiệu quả VN-Index
    # Sửa từ "off" thành "normal" để hiện màu Xanh/Đỏ
    c2.metric(
        "Hiệu quả VN-Index (Cùng kỳ)", 
        f"{mkt:.2f}%", 
        delta=f"{mkt:.2f}%", 
        delta_color="normal"
    )

    # 3. Chỉ số Alpha
    # Ép cứng "normal" để Dương là Xanh (Thắng), Âm là Đỏ (Thua)
    c3.metric(
        "CHỈ SỐ ALPHA", 
        f"{alpha:.2f}%", 
        delta=f"{alpha:.2f}%", 
        delta_color="normal",
        help="Alpha > 0: Bạn thắng thị trường (Xanh). Alpha < 0: Bạn thua thị trường (Đỏ)."
    )

    if alpha < 0:
        st.error(f"📉 **Kết luận:** {view_mode} đang **THUA** thị trường {abs(alpha):.2f}%.")
    else:
        st.success(f"🎉 **Kết luận:** {view_mode} đang **THẮNG** thị trường {alpha:.2f}%.")

    st.divider()

    # 5. HIỂN THỊ PHÂN BỔ NGÀNH (Sector Allocation)
    st.markdown(f"#### 📊 Phân Bổ Ngành: {view_mode}")
    
    try:
        sectors = brain.calculate_sector_allocation(engine, live_prices)
        
        if sectors:
            df_sec = pd.DataFrame(sectors)
            c_chart, c_table = st.columns([1.5, 1])
            
            with c_chart:
                total_asset = df_sec['value'].sum()
                fig = px.pie(df_sec, values='value', names='sector', 
                             title=f"Tổng tài sản cổ phiếu: {total_asset:,.0f} VND",
                             hole=0.4)
                fig.update_traces(textposition='inside', textinfo='percent+label')
                st.plotly_chart(fig, use_container_width=True)
                
            with c_table:
                st.dataframe(
                    df_sec[['sector', 'percent', 'value']].style.format({
                        'percent': "{:.2f}%",
                        'value': "{:,.0f}"
                    }), 
                    use_container_width=True,
                    hide_index=True
                )
        else:
            st.info("Danh mục hiện tại đang giữ 100% Tiền mặt.")
            
    except Exception as e:
        st.error(f"Lỗi hiển thị biểu đồ ngành: {e}")