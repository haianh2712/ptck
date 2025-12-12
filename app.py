# File: app.py
import streamlit as st
import pandas as pd
import plotly.express as px

# --- IMPORT MODULES ---
try:
    from processors.adapter_vck import VCKAdapter
    from processors.adapter_vps import VPSAdapter
    from processors.engine import PortfolioEngine
    from processors.live_price import get_current_price_dict
    from utils.formatters import fmt_vnd, fmt_num, fmt_pct, fmt_float
    from analytics.performance import calculate_kpi
    from analytics.time_machine import TimeMachine
    from components.charts import (
        draw_win_rate_pie, draw_pnl_distribution, 
        draw_efficiency_scatter, draw_nav_growth_chart, draw_risk_reward_bar
    )
    from components.psychology_charts import (
        draw_trading_timeline, 
        draw_discipline_matrix,
        draw_efficiency_vs_intensity,
        draw_streak_analysis
    )
    from components.advanced_charts import (
        draw_realized_drawdown,
        draw_pnl_heatmap
    )
except ImportError as e:
    st.error(f"⚠️ Lỗi cấu trúc: {e}")
    st.stop()

# ==============================================================================
# 1. CẤU HÌNH TỪ ĐIỂN TRI THỨC (KNOWLEDGE BASE)
# ==============================================================================
def get_app_definitions():
    """
    KHO CHỨA TOÀN BỘ CHÚ THÍCH & HƯỚNG DẪN SỬ DỤNG.
    Sửa nội dung văn bản tại đây mà không ảnh hưởng logic code.
    """
    return {
        # --- A. KPI TỔNG QUAN ---
        "KPI": {
            "DEPOSIT": "💰 Tổng Vốn Gốc (Net Deposit):\nLà tổng số tiền mặt thực tế bạn đã nạp vào tài khoản trừ đi số tiền đã rút ra.\nĐây là số tiền 'xương máu' ban đầu.",
            "CASH": "💵 Tiền Mặt Khả Dụng (Buying Power):\nSố dư tiền mặt hiện tại có trong tài khoản có thể dùng để mua chứng khoán.\nChưa bao gồm tiền bán chờ về.",
            "MKT_VAL": "📦 Giá Trị Thị Trường (Market Value):\nTổng giá trị của tất cả cổ phiếu đang nắm giữ tính theo giá khớp lệnh hiện tại (Real-time).\nDelta thể hiện Lãi/Lỗ tạm tính (Unrealized PnL).",
            "NAV": "💎 Tài Sản Ròng (Net Asset Value):\nTổng giá trị tài sản thực tế = Tiền Mặt + Giá Trị Thị Trường Cổ Phiếu.\nCon số này cho biết bạn đang thực sự giàu lên hay nghèo đi.",
            "PROFIT": "🚀 Tổng Lợi Nhuận (Total PnL):\nTổng lãi/lỗ 'All-in' bao gồm: (1) Lãi đã chốt + (2) Cổ tức tiền mặt + (3) Lãi tạm tính chưa chốt.\nĐây là con số cuối cùng đánh giá hiệu quả đầu tư.",
            "HOLDING": "📊 Số Mã Đang Giữ:\nSố lượng mã cổ phiếu có số lượng > 0 trong danh mục."
        },
        
        # --- B. CHÚ THÍCH CÁC TAB PHÂN TÍCH ---
        "ANALYSIS": {
            # Tab Chuyên Sâu
            "WIN_RATE": "🎯 Tỷ Lệ Thắng (Win Rate):\nSố lệnh có lãi / Tổng số lệnh đã chốt.\n• Dưới 40%: Cần xem lại phương pháp chọn cổ phiếu.\n• Trên 60%: Rất tốt.",
            "PROFIT_FACTOR": "⚖️ Profit Factor (PF):\nTổng Tiền Lãi / Tổng Tiền Lỗ.\n• PF < 1: Hệ thống đang thua lỗ.\n• PF > 1.5: Hệ thống ổn định.\n• PF > 3: Hệ thống xuất sắc.",
            "AVG_WIN": "Tiền lãi trung bình kiếm được trong một lệnh thắng.",
            "AVG_LOSS": "Tiền lỗ trung bình phải chịu trong một lệnh thua.",
            
            # Tab Tâm Lý
            "PSY_TIMELINE": """
            **Ý nghĩa:** Biểu đồ này giúp bạn phát hiện **Over-trading** (Giao dịch quá mức).
            - Nếu thấy các điểm Mua/Bán dày đặc chi chít trong một khoảng thời gian ngắn -> Bạn đang bị tâm lý, giao dịch theo cảm xúc.
            - Nếu các điểm rải đều và thưa -> Bạn giao dịch có kế hoạch.
            """,
            "PSY_MATRIX": """
            **Cách đọc Ma Trận:**
            - **Trục Ngang:** Thời gian nắm giữ (Ngày). Bên phải là giữ lâu, bên trái là lướt sóng.
            - **Trục Dọc:** Lợi nhuận. Bên trên là Lãi, bên dưới là Lỗ.
            - **Bong bóng:** Kích thước thể hiện số vốn bỏ ra.
            👉 **Cảnh báo:** Hãy tìm những bong bóng **ĐỎ TO** nằm ở góc **DƯỚI BÊN PHẢI**. Đó là những khoản lỗ lớn mà bạn đã "gồng" quá lâu (Cố chấp).
            """,
            "PSY_INTENSITY": """
            **Ý nghĩa:** So sánh giữa "Sức lực bỏ ra" (Số lệnh) và "Kết quả thu về" (Tiền lãi).
            - **Tốt:** Cột thấp (ít lệnh) nhưng Đường xanh đi lên (Lãi tăng) -> Hiệu quả cao.
            - **Xấu:** Cột cao vút (Mua bán liên tục) nhưng Đường xanh đi ngang hoặc cắm đầu -> Tốn phí thuế, không hiệu quả ("Quay phí").
            """,
            "PSY_STREAK": """
            **Ý nghĩa:** Soi diễn biến tâm lý qua chuỗi Thắng/Thua.
            - Sau một chuỗi thắng dài, bạn có xu hướng chủ quan và đi lệnh lớn (dễ mất hết lãi)?
            - Sau một chuỗi thua, bạn có dừng lại nghỉ ngơi hay cố gỡ ngay lập tức?
            """,

            # Tab Rủi Ro
            "RISK_HEATMAP": """
            **Ý nghĩa:** Nhìn lại lịch sử để tìm ra "Chu kỳ sinh học" trong giao dịch.
            - Bạn thường lãi đậm vào tháng mấy?
            - Bạn hay bị "cắt tiết" vào giai đoạn nào?
            👉 Giúp bạn biết khi nào nên "nghỉ chơi" đi du lịch.
            """,
            "RISK_DRAWDOWN": """
            **Ý nghĩa:** Thước đo "Độ đau đớn" của tài khoản.
            - Biểu đồ thể hiện mức sụt giảm của Tài sản ròng (NAV) so với **đỉnh cao nhất** từng thiết lập trước đó.
            - **Max Drawdown:** Là điểm trũng sâu nhất. Nếu > 20%, hệ thống của bạn rủi ro cao, cần giảm quy mô vốn.
            """
        },

        # --- C. CHÚ THÍCH CỘT DỮ LIỆU ---
        "COLS": {
            "Mã CK": st.column_config.TextColumn("Mã CK", width="small", help="Mã chứng khoán niêm yết."),
            "Xu Hướng": st.column_config.TextColumn("Xu Hướng", width="small", help="Trạng thái lãi/lỗ hiện tại."),
            "Vốn Gốc (Mua)": st.column_config.NumberColumn("Vốn Gốc", help="Tổng số tiền đã chi ra để mua số lượng cổ phiếu đang nắm giữ (Giá khớp * SL)."),
            "Vốn Hợp Lý (Sau Cổ Tức)": st.column_config.NumberColumn("Vốn Hợp Lý", help="Vốn Gốc được điều chỉnh giảm đi tương ứng với số tiền cổ tức đã nhận.\nĐây là giá vốn thực tế để tính hòa vốn (Break-even)."),
            "Tổng Vốn Mua": st.column_config.NumberColumn("Tổng Vốn Mua", help="Tổng quy mô vốn giải ngân cho một chu kỳ giao dịch (Deal)."),
            "Tổng Vốn Đã Rót": st.column_config.NumberColumn("Tổng Vốn Đã Rót", help="Tổng tiền tích lũy đã từng mua mã này từ quá khứ đến nay."),
            "🔄 Doanh Số Mua": st.column_config.NumberColumn("Doanh Số Mua", help="Tổng giá trị giao dịch chiều Mua (Vòng quay vốn)."),
            "Tổng Lãi Thực": st.column_config.NumberColumn("Tổng Lãi Thực", help="Lợi nhuận đã hiện thực hóa (Realized): Lãi bán chốt lời + Cổ tức tiền mặt."),
            "Lãi/Lỗ Giao Dịch": st.column_config.NumberColumn("Lãi/Lỗ GD", help="Chênh lệch giá (Capital Gain) từ các lệnh đã bán. Chưa tính cổ tức."),
            "Cổ Tức Đã Nhận": st.column_config.NumberColumn("Cổ Tức", help="Tổng tiền mặt nhận được từ cổ tức."),
            "Lãi/Lỗ": st.column_config.NumberColumn("Lãi/Lỗ", help="PnL ròng của chu kỳ/giao dịch."),
            "Giá TT": st.column_config.NumberColumn("Giá TT", help="Giá khớp lệnh gần nhất trên thị trường (Cập nhật 60s/lần)."),
            "Giá Trị TT": st.column_config.NumberColumn("Giá Trị TT", help="Thành tiền theo thị trường: SL Tồn * Giá TT."),
            "Giá Trị TT (Live)": st.column_config.NumberColumn("Giá Trị TT (Live)", help="Tổng giá trị thị trường của mã này (Bao gồm tất cả các lô đang giữ)."),
            "Lãi/Lỗ Tạm Tính": st.column_config.NumberColumn("Lãi/Lỗ Tạm", help="Lãi/Lỗ chưa chốt (Unrealized PnL): Giá Trị TT - Vốn Hợp Lý."),
            "Chênh Lệch (Live)": st.column_config.NumberColumn("Chênh Lệch (Live)", help="So sánh Giá trị thị trường với Vốn Hợp Lý. Dương là Lãi thực tế."),
            "% Hiệu Suất (Trade)": st.column_config.NumberColumn("% Hiệu Suất", format="%.2f %%", help="Tỷ suất lợi nhuận trên vốn đã bán."),
            "% Lãi/Lỗ": st.column_config.NumberColumn("% Lãi/Lỗ", format="%.2f %%", help="Tỷ suất lợi nhuận tạm tính theo giá thị trường."),
            "% ROI Cycle": st.column_config.NumberColumn("% ROI Cycle", format="%.2f %%", help="Tỷ suất sinh lời của chu kỳ đầu tư."),
            "SL Đang Giữ": st.column_config.NumberColumn("SL Đang Giữ", format="%d", help="Khối lượng cổ phiếu khả dụng."),
            "SL": st.column_config.NumberColumn("SL", format="%d", help="Khối lượng giao dịch."),
            "Ngày Giữ TB (Đã Bán)": st.column_config.NumberColumn("Ngày Giữ TB", format="%.1f ngày", help="Thời gian nắm giữ trung bình của các lệnh đã bán."),
            "Tuổi Kho TB": st.column_config.NumberColumn("Tuổi Kho TB", format="%.1f ngày", help="Thời gian nắm giữ trung bình của cổ phiếu trong kho."),
            "Tuổi Vòng Đời": st.column_config.NumberColumn("Tuổi Vòng Đời", format="%d ngày", help="Số ngày từ lúc mở vị thế đến lúc đóng vị thế."),
            "Vốn Kẹp": st.column_config.NumberColumn("Vốn Kẹp", help="Giá trị vốn đang bị kẹt trong cổ phiếu lỗ hoặc giữ quá lâu."),
        }
    }

# ==============================================================================
# 2. SETUP & STATE
# ==============================================================================
st.set_page_config(page_title="Dashboard Quản Lý Đầu Tư", page_icon="📈", layout="wide")
st.title("📊 Dashboard Phân Tích Hiệu Quả Đầu Tư")
st.markdown("---")

if 'data_processed' not in st.session_state:
    st.session_state.data_processed = False
    st.session_state.engine_vck = None
    st.session_state.engine_vps = None
    st.session_state.timeline_events = []

@st.cache_data(ttl=60, show_spinner=False)
def fetch_live_prices_cached(ticker_list):
    return get_current_price_dict(ticker_list)

# ==============================================================================
# 3. SIDEBAR & LOGIC
# ==============================================================================
with st.sidebar:
    st.header("📂 Nguồn Dữ Liệu")
    file_vck = st.file_uploader("Upload File VCK (history_VCK.xlsx)", type=['xlsx'])
    file_vps = st.file_uploader("Upload File VPS (history3.xlsx)", type=['xlsx'])
    st.divider()
    btn_run = st.button("🚀 CHẠY PHÂN TÍCH", type="primary", use_container_width=True)
    
    if st.session_state.data_processed:
        if st.button("🔄 Cập Nhật Giá Thị Trường"):
            fetch_live_prices_cached.clear()
            st.rerun()
        st.caption("Giá cập nhật mỗi 60s.")

if btn_run:
    if not file_vck and not file_vps:
        st.warning("⚠️ Vui lòng upload file dữ liệu.")
    else:
        engine_vck = PortfolioEngine("VCK")
        engine_vps = PortfolioEngine("VPS")
        all_events = []
        if file_vck:
            try:
                events = VCKAdapter().parse(file_vck)
                for e in events: engine_vck.process_event(e)
                all_events.extend(events)
            except Exception as e: st.error(f"Lỗi VCK: {e}")
        if file_vps:
            try:
                events = VPSAdapter().parse(file_vps)
                for e in events: engine_vps.process_event(e)
                all_events.extend(events)
            except Exception as e: st.error(f"Lỗi VPS: {e}")

        st.session_state.engine_vck = engine_vck
        st.session_state.engine_vps = engine_vps
        st.session_state.timeline_events = all_events
        st.session_state.data_processed = True
        st.rerun()

# ==============================================================================
# 4. MAIN DISPLAY
# ==============================================================================
if st.session_state.data_processed:
    # Load Definitions
    APP_DEFS = get_app_definitions()
    KPI_TEXT = APP_DEFS["KPI"]
    ANA_TEXT = APP_DEFS["ANALYSIS"]
    COL_CFG = APP_DEFS["COLS"]

    engine_vck = st.session_state.engine_vck
    engine_vps = st.session_state.engine_vps
    
    has_vck = (len(engine_vck.data) > 0 or len(engine_vck.trade_log) > 0)
    has_vps = (len(engine_vps.data) > 0 or len(engine_vps.trade_log) > 0)

    # --- REPORT GENERATION ---
    df_s_vck, df_c_vck, df_i_vck, df_w_vck = engine_vck.generate_reports()
    df_s_vps, df_c_vps, df_i_vps, df_w_vps = engine_vps.generate_reports()

    # --- LIVE PRICE ---
    tickers_vck = df_i_vck[df_i_vck['SL Tồn'] > 0]['Mã CK'].tolist() if not df_i_vck.empty else []
    tickers_vps = df_i_vps[df_i_vps['SL Tồn'] > 0]['Mã CK'].tolist() if not df_i_vps.empty else []
    all_tickers = list(set([str(t).strip().upper() for t in (tickers_vck + tickers_vps)]))
    
    live_prices = {}
    if all_tickers:
        with st.spinner("⏳ Đang cập nhật giá thị trường..."):
            live_prices = fetch_live_prices_cached(all_tickers)

    with st.expander("🔍 Chẩn đoán kết nối dữ liệu (Debug)", expanded=False):
        if live_prices:
            st.success(f"✅ Đã lấy được giá của {len(live_prices)} mã.")
            st.json(live_prices)
        else:
            st.warning("⚠️ Chưa lấy được giá. Kiểm tra lại kết nối mạng hoặc thư viện vnstock.")

    # --- CALCULATION LOGIC ---
    def calc_mkt(df_inv, prices):
        if df_inv.empty: return 0, df_inv
        df_inv['Key_Map'] = df_inv['Mã CK'].astype(str).str.strip().str.upper()
        df_inv['Giá TT'] = df_inv['Key_Map'].map(prices).fillna(0)
        df_inv['Giá Tính Toán'] = df_inv.apply(lambda x: x['Giá TT'] if x['Giá TT'] > 0 else x['Giá Vốn ĐC'], axis=1)
        df_inv['Giá Trị TT'] = df_inv['SL Tồn'] * df_inv['Giá Tính Toán']
        df_inv['Lãi/Lỗ Tạm Tính'] = df_inv['Giá Trị TT'] - (df_inv['SL Tồn'] * df_inv['Giá Vốn ĐC'])
        df_inv['% Lãi/Lỗ'] = df_inv.apply(lambda x: (x['Lãi/Lỗ Tạm Tính'] / (x['SL Tồn'] * x['Giá Vốn ĐC']) * 100) if (x['SL Tồn'] * x['Giá Vốn ĐC']) != 0 else 0, axis=1)
        return df_inv['Giá Trị TT'].sum(), df_inv

    def enrich_summary_with_mkt(df_sum, df_inv):
        if df_sum.empty or df_inv.empty: return df_sum
        mkt_values = df_inv.groupby('Mã CK')['Giá Trị TT'].sum()
        df_sum['Giá Trị TT (Live)'] = df_sum['Mã CK'].map(mkt_values).fillna(0)
        df_sum['Chênh Lệch (Live)'] = df_sum.apply(lambda x: (x['Giá Trị TT (Live)'] - x['Vốn Hợp Lý (Sau Cổ Tức)']) if x['SL Đang Giữ'] > 0 else 0, axis=1)
        return df_sum

    val_mkt_vck, df_i_vck = calc_mkt(df_i_vck, live_prices)
    val_mkt_vps, df_i_vps = calc_mkt(df_i_vps, live_prices)
    df_s_vck = enrich_summary_with_mkt(df_s_vck, df_i_vck)
    df_s_vps = enrich_summary_with_mkt(df_s_vps, df_i_vps)

    # --- KPI GLOBAL ---
    total_dep = engine_vck.total_deposit + engine_vps.total_deposit
    total_prof = engine_vck.total_profit + engine_vps.total_profit
    total_cash = engine_vps.real_cash_balance + engine_vck.real_cash_balance
    total_mkt_val = val_mkt_vck + val_mkt_vps
    unrealized_pnl = (df_i_vck['Lãi/Lỗ Tạm Tính'].sum() if not df_i_vck.empty else 0) + \
                     (df_i_vps['Lãi/Lỗ Tạm Tính'].sum() if not df_i_vps.empty else 0)
    real_nav = total_cash + total_mkt_val
    act_cnt = (len(df_s_vck[df_s_vck['SL Đang Giữ']>0]) if not df_s_vck.empty else 0) + \
              (len(df_s_vps[df_s_vps['SL Đang Giữ']>0]) if not df_s_vps.empty else 0)

    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("💰 Tổng Tiền Đã Nạp", fmt_vnd(total_dep), help=KPI_TEXT["DEPOSIT"])
    c2.metric("💵 Tiền Mặt Đang Có", fmt_vnd(total_cash), help=KPI_TEXT["CASH"])
    c3.metric("📦 Giá Trị Kho (TT)", fmt_vnd(total_mkt_val), delta=fmt_vnd(unrealized_pnl), delta_color="normal", help=KPI_TEXT["MKT_VAL"])
    c4.metric("💎 NAV Thực Tế", fmt_vnd(real_nav), help=KPI_TEXT["NAV"])
    total_all = total_prof + unrealized_pnl
    c5.metric("🚀 Tổng Hiệu Quả", fmt_vnd(total_all), delta=f"{(total_all/total_dep*100):.1f}%" if total_dep!=0 else "0%", help=KPI_TEXT["PROFIT"])

    st.divider()
    
    # --- NAV CHART ---
    df_history_global = pd.DataFrame() 
    if st.session_state.timeline_events:
        tm = TimeMachine(st.session_state.timeline_events)
        df_history_global = tm.run()
        if not df_history_global.empty:
            st.plotly_chart(draw_nav_growth_chart(df_history_global), use_container_width=True, key="nav_main")

    st.divider()

    # --- DISPLAY ACC FUNCTION ---
    def display_acc(engine, title, df_sum, df_cyc, df_inv, df_warn, df_hist):
        st.markdown(f"## 🏦 {title}")
        if df_sum.empty: return

        # Overview Charts
        c1, c2 = st.columns(2)
        with c1:
            df_h = df_sum[df_sum['Vốn Gốc (Mua)'] > 0]
            if not df_h.empty: st.plotly_chart(px.pie(df_h, values='Vốn Gốc (Mua)', names='Mã CK', title='Phân Bổ Vốn', hole=0.4), use_container_width=True, key=f"p1_{title}")
        with c2:
            df_p = df_sum.sort_values(by='Tổng Lãi Thực', ascending=False).head(10)
            if not df_p.empty:
                st.plotly_chart(px.bar(df_p, x='Mã CK', y='Tổng Lãi Thực', title='Top Hiệu Quả', text_auto='.2s', color_discrete_sequence=['#00CC96']), use_container_width=True, key=f"p2_{title}")

        # TABS
        t_adv, t_psy, t_risk, t1, t2, t3, t4, t5 = st.tabs(["🧠 PT Chuyên Sâu", "❤️ Tâm Lý", "🛡️ Quản Trị Rủi Ro", "📋 Hiệu Suất Tổng", "🔄 Lịch Sử Cycle", "📦 Chi Tiết Kho (Live)", "⚠️ Cảnh Báo", "🔍 Soi Lỗi"])
        
        # 1. PT Chuyên Sâu
        with t_adv:
            closed = engine.get_all_closed_cycles()
            if closed:
                kpi = calculate_kpi(closed)
                if kpi:
                    k1, k2, k3, k4 = st.columns(4)
                    k1.metric("Win Rate", f"{kpi['win_rate']}%", help=ANA_TEXT["WIN_RATE"])
                    k2.metric("Profit Factor", f"{kpi['profit_factor']}", help=ANA_TEXT["PROFIT_FACTOR"])
                    k3.metric("Avg Win", fmt_vnd(kpi['avg_win']), help=ANA_TEXT["AVG_WIN"])
                    k4.metric("Avg Loss", fmt_vnd(kpi['avg_loss']), help=ANA_TEXT["AVG_LOSS"])
                    st.divider()
                    cc1, cc2, cc3 = st.columns([1,1,2])
                    with cc1: st.plotly_chart(draw_win_rate_pie(kpi), use_container_width=True, key=f"w_{title}")
                    with cc2: st.plotly_chart(draw_risk_reward_bar(kpi), use_container_width=True, key=f"rr_{title}")
                    with cc3: st.plotly_chart(draw_pnl_distribution(pd.DataFrame(closed)), use_container_width=True, key=f"pnl_{title}")
                    st.plotly_chart(draw_efficiency_scatter(pd.DataFrame(closed)), use_container_width=True, key=f"eff_{title}")
            else: st.info("Chưa có lệnh tất toán.")

        # 2. Tâm Lý (Có giải thích)
        with t_psy:
            st.markdown("#### 🧘 Phân Tích Tâm Lý")
            atype = st.selectbox("Góc nhìn:", ["1. Nhịp Tim", "2. Ma Trận Kỷ Luật", "3. Cường Độ vs Hiệu Quả", "4. Chuỗi"], key=f"psy_{title}")
            
            if "1. Nhịp Tim" in atype:
                st.info(ANA_TEXT["PSY_TIMELINE"])
                if engine.trade_log:
                    fig = draw_trading_timeline(engine.trade_log)
                    if fig: st.plotly_chart(fig, use_container_width=True, key=f"tline_{title}")
            elif "2. Ma Trận" in atype:
                st.info(ANA_TEXT["PSY_MATRIX"])
                closed = engine.get_all_closed_cycles()
                if closed:
                    fig = draw_discipline_matrix(closed)
                    if fig: st.plotly_chart(fig, use_container_width=True, key=f"mat_{title}")
            elif "3. Cường Độ" in atype:
                st.info(ANA_TEXT["PSY_INTENSITY"])
                closed = engine.get_all_closed_cycles()
                if engine.trade_log:
                    fig = draw_efficiency_vs_intensity(engine.trade_log, closed)
                    if fig: st.plotly_chart(fig, use_container_width=True, key=f"int_{title}")
            elif "4. Chuỗi" in atype:
                st.info(ANA_TEXT["PSY_STREAK"])
                closed = engine.get_all_closed_cycles()
                if closed:
                    fig = draw_streak_analysis(closed)
                    if fig: st.plotly_chart(fig, use_container_width=True, key=f"str_{title}")

        # 3. Quản Trị Rủi Ro (Có giải thích)
        with t_risk:
            st.markdown("#### 🛡️ Quản Trị Rủi Ro")
            
            st.markdown("##### 1. Bản Đồ Nhiệt Hiệu Quả")
            with st.expander("ℹ️ Giải thích ý nghĩa"):
                st.markdown(ANA_TEXT["RISK_HEATMAP"])
            if engine.trade_log:
                fig_heat = draw_pnl_heatmap(engine.trade_log)
                if fig_heat: st.plotly_chart(fig_heat, use_container_width=True, key=f"heat_{title}")
            
            st.divider()
            
            st.markdown("##### 2. Sụt Giảm Vốn Thực (Realized Drawdown)")
            with st.expander("ℹ️ Giải thích ý nghĩa"):
                st.markdown(ANA_TEXT["RISK_DRAWDOWN"])
            if not df_hist.empty:
                fig_dd, max_dd, curr_dd = draw_realized_drawdown(df_hist)
                if fig_dd:
                    k1, k2 = st.columns(2)
                    k1.metric("Max Drawdown", f"{max_dd:.2f}%")
                    k2.metric("Current Drawdown", f"{curr_dd:.2f}%")
                    st.plotly_chart(fig_dd, use_container_width=True, key=f"dd_{title}")

        # --- TABLES ---
        with t1: 
            df_display = df_sum.rename(columns={'Tổng Vốn Đã Rót': '🔄 Doanh Số Mua'})
            cols = list(df_display.columns)
            if 'Vốn Hợp Lý (Sau Cổ Tức)' in cols and 'Giá Trị TT (Live)' in cols:
                idx = cols.index('Vốn Hợp Lý (Sau Cổ Tức)')
                cols.insert(idx + 1, cols.pop(cols.index('Giá Trị TT (Live)')))
                cols.insert(idx + 2, cols.pop(cols.index('Chênh Lệch (Live)')))
                df_display = df_display[cols]

            limit = 1000
            cols_to_color = ['Tổng Lãi Thực', 'Chênh Lệch (Live)']
            if not df_display.empty:
                max_val = 0
                for c in cols_to_color:
                    if c in df_display.columns:
                        m = df_display[c].abs().max()
                        if m > max_val: max_val = m
                if max_val > 0: limit = max_val

            st.dataframe(
                df_display.style.format({
                    'Tổng SL Đã Bán': fmt_num, 'Lãi/Lỗ Giao Dịch': fmt_vnd, 'Cổ Tức Đã Nhận': fmt_vnd, 'Tổng Lãi Thực': fmt_vnd,
                    '% Hiệu Suất (Trade)': fmt_pct, 'SL Đang Giữ': fmt_num, 'Vốn Gốc (Mua)': fmt_vnd, 'Vốn Hợp Lý (Sau Cổ Tức)': fmt_vnd,
                    '🔄 Doanh Số Mua': fmt_vnd, '% Tỷ Trọng Vốn': fmt_pct, 'Ngày Giữ TB (Đã Bán)': fmt_float, 'Tuổi Kho TB': fmt_float,
                    'Giá Trị TT (Live)': fmt_vnd, 'Chênh Lệch (Live)': fmt_vnd
                })
                .background_gradient(subset=[c for c in cols_to_color if c in df_display.columns], cmap='RdYlGn', vmin=-limit, vmax=limit), 
                use_container_width=True, column_config=COL_CFG
            )

        with t2: st.dataframe(df_cyc.style.format({
                'Tổng Vốn Mua': fmt_vnd, 'Lãi Giao Dịch': fmt_vnd, 'Cổ Tức': fmt_vnd, 
                'Tổng Lãi Cycle': fmt_vnd, '% ROI Cycle': fmt_pct, 'Tuổi Vòng Đời': fmt_num
            }), use_container_width=True, column_config=COL_CFG)
        
        with t3: 
            limit = 1000
            if not df_inv.empty and 'Lãi/Lỗ Tạm Tính' in df_inv.columns:
                max_abs = df_inv['Lãi/Lỗ Tạm Tính'].abs().max()
                if max_abs > 0: limit = max_abs
            
            cols = [c for c in df_inv.columns if c not in ['Key_Map', 'Giá Tính Toán', 'Xu Hướng']]
            
            st.dataframe(
                df_inv[cols].style.format({
                    'SL Tồn': fmt_num, 'Giá Vốn Gốc': fmt_vnd, 'Giá Vốn ĐC': fmt_vnd, 
                    'Giá TT': fmt_vnd, 'Giá Trị TT': fmt_vnd, 'Lãi/Lỗ Tạm Tính': fmt_vnd,
                    '% Lãi/Lỗ': fmt_pct
                }).background_gradient(subset=['Lãi/Lỗ Tạm Tính'], cmap='RdYlGn', vmin=-limit, vmax=limit),
                use_container_width=True, column_config=COL_CFG
            )
            
        with t4: 
            if not df_warn.empty: 
                st.dataframe(df_warn.style.format({'Vốn Kẹp': fmt_vnd, 'Tuổi Kho TB': fmt_float}), use_container_width=True, column_config=COL_CFG)
            else: st.success("An toàn.")
        with t5:
            if engine.trade_log: 
                st.dataframe(pd.DataFrame(engine.trade_log).style.format({
                    'SL': fmt_num, 'Giá Bán': fmt_vnd, 'Giá Vốn': fmt_vnd, 'Lãi/Lỗ': fmt_vnd
                }), use_container_width=True, column_config=COL_CFG)

    if has_vck: display_acc(engine_vck, "Tài Khoản VCK", df_s_vck, df_c_vck, df_i_vck, df_w_vck, df_history_global)
    if has_vps: display_acc(engine_vps, "Tài Khoản VPS", df_s_vps, df_c_vps, df_i_vps, df_w_vps, df_history_global)

else:
    st.info("👋 Chào mừng! Vui lòng upload file dữ liệu.")