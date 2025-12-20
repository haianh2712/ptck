# File: app1.py
# Updated: FIX LỖI TÍNH TRÙNG CỔ TỨC (DÙNG CÔNG THỨC NAV CHUẨN)

import streamlit as st
import pandas as pd
import configs # File cấu hình

# --- IMPORT MODULES ---
try:
    from processors.adapter_vck import VCKAdapter
    from processors.adapter_vps import VPSAdapter
    from processors.engine import PortfolioEngine
    from processors.live_price import get_current_price_dict
    from utils.formatters import fmt_vnd, fmt_num, fmt_pct, fmt_float
    from analytics.performance import calculate_kpi
    from processors.ipo_merger import merge_ipo_events
    
    # Import Module Vá Lỗi Cổ Tức
    import patch_dividend_fix 
    
    # Import Views
    from views import dashboard_asset
    from views import dashboard_account_single
    
    # Components
    from components.psychology_charts import (
        draw_trading_timeline, 
        draw_history_matrix,
        draw_holding_risk_radar,
        draw_efficiency_vs_intensity, 
        draw_streak_analysis
    )
    from components import chart_drawdown
    from components import chart_heatmap

except ImportError as e:
    st.error(f"⚠️ Lỗi cấu trúc hệ thống: {e}")
    st.stop()

# ==============================================================================
# CONFIG & STATE
# ==============================================================================
st.set_page_config(page_title="Dashboard Quản Lý Đầu Tư", page_icon="📈", layout="wide")
st.title("📊 Dashboard Phân Tích Hiệu Quả Đầu Tư")

# Khởi tạo Session State
if 'data_processed' not in st.session_state:
    st.session_state.data_processed = False
    st.session_state.engine_vck = None
    st.session_state.engine_vps = None
    st.session_state.events_vck = []      
    st.session_state.events_vps = []      
    st.session_state.timeline_events = [] 

@st.cache_data(ttl=60, show_spinner=False)
def fetch_live_prices_cached(ticker_list):
    return get_current_price_dict(ticker_list)

# ==============================================================================
# SIDEBAR
# ==============================================================================
with st.sidebar:
    st.header("📂 Nguồn Dữ Liệu")
    file_vck = st.file_uploader("Upload File VCK", type=['xlsx'])
    file_vps = st.file_uploader("Upload File VPS", type=['xlsx'])
    st.divider()
    btn_run = st.button("🚀 CHẠY PHÂN TÍCH", type="primary", use_container_width=True)
    if st.session_state.data_processed:
        if st.button("🔄 Cập Nhật Giá Thị Trường"):
            fetch_live_prices_cached.clear()
            st.rerun()

if btn_run:
    if not file_vck and not file_vps:
        st.warning("Vui lòng upload ít nhất 1 file dữ liệu.")
    else:
        # Reset engines
        engine_vck = PortfolioEngine("VCK")
        engine_vps = PortfolioEngine("VPS")
        
        list_vck = []
        list_vps = []
        all_events = []

        # Xử lý VCK
        if file_vck:
            try:
                # 1. Parse dữ liệu (Adapter trả về thô)
                raw_events = VCKAdapter().parse(file_vck)
                
                # 2. [MỚI] Chạy qua bộ xử lý IPO
                events = merge_ipo_events(raw_events)
                
                # 3. Chạy Engine (như cũ)
                for e in events: engine_vck.process_event(e)
                
                # 4. Patch cổ tức
                patch_dividend_fix.apply_dividend_patch(engine_vck, file_vck)
                
                list_vck = events 
                all_events.extend(events) 
            except Exception as e: st.error(f"Lỗi đọc file VCK: {e}")
            
        # Xử lý VPS
        if file_vps:
            try:
                # 1. Parse dữ liệu (Adapter mới tự lo mọi thứ, trả về list events chuẩn)
                events = VPSAdapter().parse(file_vps)
                
                # 2. Chạy Engine
                for e in events: engine_vps.process_event(e)
                
                # 3. Patch cổ tức
                patch_dividend_fix.apply_dividend_patch(engine_vps, file_vps)
                
                list_vps = events 
                all_events.extend(events) 
            except Exception as e: st.error(f"Lỗi đọc file VPS: {e}")

        st.session_state.engine_vck = engine_vck
        st.session_state.engine_vps = engine_vps
        st.session_state.events_vck = list_vck
        st.session_state.events_vps = list_vps
        st.session_state.timeline_events = all_events
        st.session_state.data_processed = True
        st.rerun()

# ==============================================================================
# MAIN DISPLAY
# ==============================================================================
if st.session_state.data_processed:
    
    KPI_TIPS = configs.KPI_TOOLTIPS
    COL_CFG = configs.get_column_config()
    INSIGHTS = configs.CHART_INSIGHTS 

    engine_vck = st.session_state.engine_vck
    engine_vps = st.session_state.engine_vps
    
    # 1. Reports
    df_s_vck, df_c_vck, df_i_vck, df_w_vck = engine_vck.generate_reports()
    df_s_vps, df_c_vps, df_i_vps, df_w_vps = engine_vps.generate_reports()

    # 2. Live Price
    tickers_vck = df_i_vck[df_i_vck['SL Tồn'] > 0]['Mã CK'].tolist() if not df_i_vck.empty else []
    tickers_vps = df_i_vps[df_i_vps['SL Tồn'] > 0]['Mã CK'].tolist() if not df_i_vps.empty else []
    all_tickers = list(set([str(t).strip().upper() for t in (tickers_vck + tickers_vps)]))
    
    live_prices = {}
    if all_tickers:
        with st.spinner("⏳ Đang kết nối thị trường..."):
            live_prices = fetch_live_prices_cached(all_tickers)

    with st.expander("🔍 Chẩn đoán kết nối dữ liệu (Debug)", expanded=False):
        if live_prices:
            st.success(f"✅ Đã lấy được giá của {len(live_prices)} mã.")
            st.json(live_prices)
        else: st.warning("⚠️ Chưa lấy được giá hoặc thị trường đang đóng cửa.")

    import re # Đảm bảo đã import re ở đầu file hoặc trong hàm

    # 3. Calculations (PHIÊN BẢN ỔN ĐỊNH - KHÔNG ĐỊNH DẠNG PHỨC TẠP)
    def calc_mkt(df_inv, prices):
        if df_inv.empty: return 0, df_inv
        
        # 1. Chuẩn hóa tên cột
        df_inv.columns = [str(c).strip() for c in df_inv.columns]

        # 2. Mapping giá thị trường
        df_inv['Key_Map'] = df_inv['Mã CK'].astype(str).str.strip().str.upper()
        df_inv['Giá TT'] = df_inv['Key_Map'].map(prices).fillna(0)
        
        # 3. Tính giá tính toán
        df_inv['Giá Tính Toán'] = df_inv.apply(lambda x: x['Giá TT'] if x['Giá TT'] > 0 else x['Giá Vốn ĐC'], axis=1)
        
        # 4. [CLEANUP] Xóa cột Vốn Gốc cũ (tránh trùng lặp)
        cols_to_drop = [c for c in df_inv.columns if 'vốn' in c.lower() and ('gốc' in c.lower() or 'tổng' in c.lower()) and 'giá vốn' not in c.lower()]
        if cols_to_drop: df_inv = df_inv.drop(columns=cols_to_drop)

        # 5. [TÍNH TOÁN]
        df_inv['Vốn Gốc'] = df_inv['SL Tồn'] * df_inv['Giá Vốn ĐC']
        df_inv['Giá Trị TT'] = df_inv['SL Tồn'] * df_inv['Giá Tính Toán']
        df_inv['Lãi/Lỗ Tạm Tính'] = df_inv['Giá Trị TT'] - df_inv['Vốn Gốc']
        
        # 6. [AN TOÀN] ÉP VỀ SỐ NGUYÊN (INT64)
        # Streamlit sẽ tự động hiển thị số này là 2,015,000 (dấu phẩy) -> Chấp nhận được.
        for col in df_inv.columns:
            if pd.api.types.is_numeric_dtype(df_inv[col]):
                col_lower = col.lower()
                keywords = ['giá', 'vốn', 'lãi', 'lỗ', 'trị', 'nav', 'tài sản']
                if any(k in col_lower for k in keywords):
                    try:
                        df_inv[col] = df_inv[col].fillna(0).round(0).astype('int64')
                    except: continue

        return df_inv['Giá Trị TT'].sum(), df_inv

    def enrich_summary(df_sum, df_inv):
        if df_sum.empty or df_inv.empty: return df_sum
        mkt_values = df_inv.groupby('Mã CK')['Giá Trị TT'].sum()
        df_sum['Giá Trị TT (Live)'] = df_sum['Mã CK'].map(mkt_values).fillna(0)
        df_sum['Chênh Lệch (Live)'] = df_sum.apply(lambda x: (x['Giá Trị TT (Live)'] - x['Vốn Hợp Lý (Sau Cổ Tức)']) if x['SL Đang Giữ'] > 0 else 0, axis=1)
        return df_sum

    val_mkt_vck, df_i_vck = calc_mkt(df_i_vck, live_prices)
    val_mkt_vps, df_i_vps = calc_mkt(df_i_vps, live_prices)
    df_s_vck = enrich_summary(df_s_vck, df_i_vck)
    df_s_vps = enrich_summary(df_s_vps, df_i_vps)

    # 4. Global KPI (FIX LỖI TÍNH TRÙNG CỔ TỨC)
    # ======================================================================
    # a. Tổng Vốn Nạp Ròng (Tiền vào - Tiền ra)
    total_dep = engine_vck.total_deposit + engine_vps.total_deposit
    
    # b. Tổng Tiền Mặt (Số dư khả dụng hiện tại)
    total_cash = engine_vps.real_cash_balance + engine_vck.real_cash_balance
    
    # c. Tổng Giá Trị Chứng Khoán (Theo thị giá)
    total_mkt = val_mkt_vck + val_mkt_vps
    
    # d. NAV Thực Tế (Tổng tài sản hiện có)
    real_nav = total_cash + total_mkt
    
    # e. Lãi Tạm Tính (Để hiển thị tham khảo)
    unrealized_pnl = (df_i_vck['Lãi/Lỗ Tạm Tính'].sum() if not df_i_vck.empty else 0) + \
                     (df_i_vps['Lãi/Lỗ Tạm Tính'].sum() if not df_i_vps.empty else 0)
    
    # [FIX] TỔNG LỢI NHUẬN THỰC TẾ = NAV - VỐN GỐC
    # Công thức này đúng tuyệt đối, không quan tâm giá vốn đã điều chỉnh hay chưa.
    total_all_in_profit = real_nav - total_dep
    # ======================================================================

    # 5. History Machine (ĐỒNG BỘ HÓA DỮ LIỆU)
    df_history_vck = engine_vck.get_nav_chart_data()
    df_history_vps = engine_vps.get_nav_chart_data()
    
    df_vck_ready = pd.DataFrame()
    if df_history_vck is not None and not df_history_vck.empty:
        df_vck_ready = df_history_vck.set_index('Ngày')

    df_vps_ready = pd.DataFrame()
    if df_history_vps is not None and not df_history_vps.empty:
        df_vps_ready = df_history_vps.set_index('Ngày')

    df_history_global = pd.DataFrame()

    if not df_vck_ready.empty and not df_vps_ready.empty:
        min_date = min(df_vck_ready.index.min(), df_vps_ready.index.min())
        max_date = max(df_vck_ready.index.max(), df_vps_ready.index.max())
        all_days = pd.date_range(min_date, max_date, freq='D')

        vck_filled = df_vck_ready.reindex(all_days).ffill().fillna(0)
        vps_filled = df_vps_ready.reindex(all_days).ffill().fillna(0)

        df_combined = vck_filled + vps_filled
        df_history_global = df_combined.reset_index().rename(columns={'index': 'Ngày'})

    elif not df_vck_ready.empty:
        df_history_global = df_history_vck
    elif not df_vps_ready.empty:
        df_history_global = df_history_vps

    # --- TAB LAYOUT ---
    tab_asset, tab_vck, tab_vps, tab_anal = st.tabs([
        "🏠 TỔNG QUAN TÀI SẢN", "📘 TÀI KHOẢN VCK", "📕 TÀI KHOẢN VPS", "⚡ PHÂN TÍCH NÂNG CAO"
    ])

    # Tab 1: Tổng Quan
    with tab_asset:
        df_sum_all = pd.concat([df_s_vck, df_s_vps]) if not df_s_vck.empty or not df_s_vps.empty else pd.DataFrame()
        # Truyền total_all_in_profit (đã fix) vào hàm hiển thị
        dashboard_asset.display(total_dep, total_cash, total_mkt, unrealized_pnl, real_nav, total_all_in_profit, df_history_global, df_sum_all, KPI_TIPS)
        st.success(f"🔎 **Chi tiết Vốn Nạp:** VCK = **{fmt_vnd(engine_vck.total_deposit)}** | VPS = **{fmt_vnd(engine_vps.total_deposit)}**")

    # Tab 2: VCK
    with tab_vck:
        st.success(f"💰 **Tổng Vốn Thực Nạp (VCK):** {fmt_vnd(engine_vck.total_deposit)}", icon="💵")
        st.divider()
        if not df_history_vck.empty:
            st.subheader("📈 Tăng trưởng NAV (VCK)")
            st.line_chart(df_history_vck.set_index('Ngày')['Tổng Tài Sản (NAV)'])
        dashboard_account_single.display(engine_vck, "VCK", df_s_vck, df_c_vck, df_i_vck, df_w_vck)

    # Tab 3: VPS
    with tab_vps:
        st.success(f"💰 **Tổng Vốn Thực Nạp (VPS):** {fmt_vnd(engine_vps.total_deposit)}", icon="💵")
        st.divider()
        if not df_history_vps.empty:
            st.subheader("📈 Tăng trưởng NAV (VPS)")
            st.line_chart(df_history_vps.set_index('Ngày')['Tổng Tài Sản (NAV)'])
        dashboard_account_single.display(engine_vps, "VPS", df_s_vps, df_c_vps, df_i_vps, df_w_vps)

    # Tab 4: Phân Tích
    with tab_anal:
        st.markdown("### ⚡ Phân Tích Tâm Lý & Hiệu Quả Đầu Tư")
        acc_opt = st.radio("Chọn tài khoản để phân tích:", ["VCK", "VPS"], horizontal=True)
        if acc_opt == "VCK":
            eng = engine_vck
            df_curr_inv = df_i_vck
            df_hist_selected = df_history_vck 
        else:
            eng = engine_vps
            df_curr_inv = df_i_vps
            df_hist_selected = df_history_vps
        
        def render_insight(key):
            if key in INSIGHTS:
                with st.expander("💡 PHÂN TÍCH CHUYÊN SÂU & CẢNH BÁO TÂM LÝ (Đọc trước khi xem)", expanded=True):
                    st.markdown(INSIGHTS[key]["meaning"])
                    st.warning(INSIGHTS[key]["warning"])

        t_psy, t_risk = st.tabs(["🧠 Tâm Lý Giao Dịch", "🛡️ Quản Trị Rủi Ro"])
        
        with t_psy:
            atype = st.selectbox("Chọn công cụ phân tích:", ["1. Ma Trận Kỷ Luật (Quan trọng)", "2. Nhịp Tim Giao Dịch", "3. Cường Độ vs Hiệu Quả", "4. Chuỗi Thắng Thua (Phong độ)"], key=f"psy_{acc_opt}")
            if "1. Ma Trận" in atype:
                sub_t1, sub_t2 = st.tabs(["📜 Lịch Sử (Đã Chốt)", "📡 Ra-đa Rủi Ro (Đang Giữ)"])
                with sub_t1:
                    render_insight("chart_2_matrix") 
                    fig_hist = draw_history_matrix(eng.get_all_closed_cycles())
                    if fig_hist: st.plotly_chart(fig_hist, use_container_width=True)
                    else: st.info("Chưa có lệnh chốt lời/lỗ nào.")
                with sub_t2:
                    render_insight("chart_3_radar") 
                    fig_hold = draw_holding_risk_radar(df_curr_inv)
                    if fig_hold: st.plotly_chart(fig_hold, use_container_width=True)
                    else: st.info("Hiện không nắm giữ cổ phiếu nào.")
            elif "2. Nhịp Tim" in atype:
                render_insight("chart_1_timeline") 
                fig = draw_trading_timeline(eng.trade_log)
                if fig: st.plotly_chart(fig, use_container_width=True)
                else: st.info("Chưa có dữ liệu giao dịch.")
            elif "3. Cường Độ" in atype:
                render_insight("chart_4_efficiency") 
                fig = draw_efficiency_vs_intensity(eng.trade_log, eng.get_all_closed_cycles())
                if fig: st.plotly_chart(fig, use_container_width=True)
                else: st.info("Chưa có dữ liệu.")
            elif "4. Chuỗi" in atype:
                render_insight("chart_5_streak") 
                fig = draw_streak_analysis(eng.get_all_closed_cycles())
                if fig: st.plotly_chart(fig, use_container_width=True)
                else: st.info("Chưa có dữ liệu.")

        with t_risk:
            st.markdown("#### 🔥 Bản Đồ Nhiệt (Heatmap)")
            render_insight("risk_heatmap") 
            fig_heat = chart_heatmap.plot(eng.trade_log)
            if fig_heat: st.plotly_chart(fig_heat, use_container_width=True)
            else: st.info("Chưa có dữ liệu giao dịch để vẽ Heatmap.")
        
            st.divider()
            st.markdown(f"#### 📉 Sụt Giảm Vốn Thực (Drawdown: {acc_opt})")
            render_insight("risk_drawdown") 
            if not df_hist_selected.empty:
                fig_dd, max_dd, curr_dd = chart_drawdown.plot(df_hist_selected)
                if fig_dd:
                    k1, k2 = st.columns(2)
                    k1.metric("Max Drawdown (Đáy lịch sử)", f"{max_dd:.2f}%", help="Mức sụt giảm lớn nhất từ đỉnh từng ghi nhận.")
                    k2.metric("Current Drawdown (Hiện tại)", f"{curr_dd:.2f}%", help="Bạn đang cách đỉnh tài sản bao nhiêu %.")
                    st.plotly_chart(fig_dd, use_container_width=True)
            else: st.info(f"Chưa đủ dữ liệu lịch sử NAV của {acc_opt} để vẽ Drawdown (Cần tối thiểu 2 ngày).")

else:
    st.info("👋 Chào mừng! Vui lòng upload file dữ liệu VCK hoặc VPS.")