# File: views/dashboard_account_single.py
import streamlit as st
import pandas as pd
import plotly.express as px
from utils.formatters import fmt_vnd, fmt_num, fmt_pct, fmt_float
import configs
from analytics.time_machine import TimeMachine
from components.charts import (
    draw_profit_stacked_bar, 
    draw_nav_growth_chart, 
    draw_win_rate_pie, 
    draw_risk_reward_bar,
    draw_pnl_distribution,
    draw_efficiency_scatter,
    get_pnl_column
)

def display(engine, title, df_sum, df_cyc, df_inv, df_warn):
    st.markdown(f"## 📂 Quản Lý: {title}")
    
    tips = configs.KPI_TOOLTIPS if hasattr(configs, 'KPI_TOOLTIPS') else {}
    col_cfg = configs.get_column_config()

    # 1. TÍNH TOÁN CÁC CHỈ SỐ CƠ BẢN (KPI)
    # ----------------------------------------------------
    curr_cash = getattr(engine, 'real_cash_balance', 0)
    
    # Tính giá trị kho hiện tại
    curr_stock_val = 0
    if not df_inv.empty:
        if 'Giá Trị TT' in df_inv.columns:
            curr_stock_val = df_inv['Giá Trị TT'].sum()
        elif 'Giá Vốn ĐC' in df_inv.columns:
            curr_stock_val = (df_inv['SL Tồn'] * df_inv['Giá Vốn ĐC']).sum()
            
    # NAV Thực tế (Live)
    curr_nav = curr_cash + curr_stock_val
    
    # Tính Tổng Vốn Nạp Ròng (Để làm mốc so sánh)
    total_dep = 0
    try:
        # Cố gắng lấy tổng nạp từ engine (nếu có lưu)
        if hasattr(engine, 'total_deposit'):
            total_dep = engine.total_deposit
        elif hasattr(engine, 'initial_capital'):
            total_dep = engine.initial_capital
        
        # Nếu vẫn 0, thử cộng từ events
        if total_dep == 0 and hasattr(engine, 'events') and engine.events:
             total_dep = sum(e.get('cash', 0) for e in engine.events if e.get('type') in ['DEPOSIT', 'NẠP'])
    except: pass
    
    # Lãi đã chốt (Realized PnL)
    realized_pnl = 0
    try:
        if hasattr(engine, 'data'):
            t_pl = sum(item['stats'].get('total_trading_pl', 0) for item in engine.data.values())
            t_div = sum(item['stats'].get('total_dividend', 0) for item in engine.data.values())
            realized_pnl = t_pl + t_div
    except: pass
    
    # Lãi chưa chốt (Unrealized PnL)
    total_adjusted_cost = 0
    if not df_sum.empty and 'Vốn Hợp Lý (Sau Cổ Tức)' in df_sum.columns:
        active = df_sum[df_sum['SL Đang Giữ'] > 0]
        total_adjusted_cost = active['Vốn Hợp Lý (Sau Cổ Tức)'].sum()
    pnl_unrealized = curr_stock_val - total_adjusted_cost


    # 2. XỬ LÝ DỮ LIỆU LỊCH SỬ NAV (QUAN TRỌNG: CƠ CHẾ FALLBACK)
    # ----------------------------------------------------
    df_nav_history = pd.DataFrame()
    
    # Bước 1: Thử dùng TimeMachine (Cách chuẩn)
    try:
        # Ưu tiên dùng 'events' vì chứa cả Nạp/Rút
        source_data = getattr(engine, 'events', [])
        if not source_data: 
            source_data = getattr(engine, 'trade_log', []) # Fallback sang trade_log
            
        if source_data:
            tm = TimeMachine(source_data)
            df_nav_history = tm.run()
    except Exception:
        df_nav_history = pd.DataFrame() # Reset nếu lỗi

    # Bước 2: NẾU TimeMachine thất bại (df rỗng), TỰ TẠO DỮ LIỆU GIẢ LẬP
    # Mục đích: Để biểu đồ luôn hiện, không báo lỗi "Cần nạp Data"
    if df_nav_history.empty and total_dep > 0:
        # Tạo 2 điểm: [Ngày xưa, Vốn Gốc] -> [Hôm nay, NAV Sổ Sách]
        # NAV Sổ sách ước tính = Vốn gốc + Lãi đã chốt
        est_book_nav = total_dep + realized_pnl
        
        # Lấy ngày bắt đầu từ dữ liệu giao dịch hoặc mặc định 30 ngày trước
        start_date = pd.Timestamp.now() - pd.Timedelta(days=30)
        if hasattr(engine, 'trade_log') and engine.trade_log:
            try:
                # Tìm ngày giao dịch đầu tiên
                dates = [pd.to_datetime(x.get('date', x.get('Ngày'))) for x in engine.trade_log if x.get('date') or x.get('Ngày')]
                if dates: start_date = min(dates)
            except: pass
            
        # Tạo DataFrame thủ công
        df_nav_history = pd.DataFrame([
            {'Ngày': start_date, 'Tổng Tài Sản (NAV)': total_dep, 'Vốn Nạp Ròng': total_dep},
            {'Ngày': pd.Timestamp.now(), 'Tổng Tài Sản (NAV)': est_book_nav, 'Vốn Nạp Ròng': total_dep}
        ])

    # 3. HIỂN THỊ KPI METRICS
    # ----------------------------------------------------
    k1, k2, k3, k4, k5 = st.columns(5)
    k1.metric("💵 Tiền Mặt", fmt_vnd(curr_cash), help=tips.get("CASH", ""))
    k2.metric("🛡️ Vốn Hợp Lý (Kho)", fmt_vnd(total_adjusted_cost), help=tips.get("ADJ_COST", ""))
    k3.metric("📦 Cổ Phiếu (Live)", fmt_vnd(curr_stock_val), 
              delta=fmt_vnd(pnl_unrealized), delta_color="normal", help=tips.get("MKT_VAL", ""))
    k4.metric("💎 NAV Tài Khoản", fmt_vnd(curr_nav), help=tips.get("NAV", ""))
    k5.metric("💰 Lãi Đã Chốt", fmt_vnd(realized_pnl), help=tips.get("REALIZED", ""))
    
    st.divider()

    # 4. KHU VỰC BIỂU ĐỒ (CHARTS)
    # ----------------------------------------------------
    c_left, c_right = st.columns([2, 1])

    # --- Cột Trái: Biểu đồ NAV ---
    with c_left:
        st.markdown("##### 📈 Tăng Trưởng NAV")
        if not df_nav_history.empty:
            # Vẽ biểu đồ với dữ liệu (chuẩn hoặc giả lập)
            fig_nav = draw_nav_growth_chart(df_nav_history, curr_nav)
            if fig_nav:
                st.plotly_chart(fig_nav, use_container_width=True, key=f"nav_{title}")
            else:
                st.info("Lỗi hiển thị biểu đồ.")
        else:
            # Chỉ hiện khi KHÔNG có cả dữ liệu nạp tiền
            st.warning("Chưa xác định được Vốn Nạp. Vui lòng kiểm tra file đầu vào.")

    # --- Cột Phải: Biểu đồ Phân Bổ (Pie) ---
    with c_right:
        st.markdown("##### 🍰 Phân Bổ")
        if not df_sum.empty:
            view_mode = st.radio("Chế độ:", ["Theo Vốn Gốc", "Theo Giá TT"], horizontal=True, key=f"pm_{title}", label_visibility="collapsed")
            
            df_pie = pd.DataFrame()
            val = None
            if view_mode == "Theo Vốn Gốc":
                if 'Vốn Gốc (Mua)' in df_sum.columns:
                    df_pie = df_sum[df_sum['Vốn Gốc (Mua)'] > 0].copy()
                    val = 'Vốn Gốc (Mua)'
            else:
                mkt_col = 'Giá Trị TT (Live)' if 'Giá Trị TT (Live)' in df_sum.columns else 'Giá Trị TT'
                if mkt_col in df_sum.columns:
                    df_pie = df_sum[df_sum[mkt_col] > 0].copy()
                    val = mkt_col
            
            if not df_pie.empty and val:
                st.plotly_chart(px.pie(df_pie, values=val, names='Mã CK', hole=0.4), use_container_width=True, key=f"pie_{title}")
            else:
                st.caption("Danh mục trống.")
        else:
            st.caption("Chưa có danh mục.")
    
    # --- Hàng dưới: Biểu đồ Hiệu quả (Stacked Bar) ---
    if not df_sum.empty:
        st.markdown("##### 🏆 Hiệu Quả Đầu Tư (Realized + Unrealized)")
        fig_bar = draw_profit_stacked_bar(df_sum, df_inv)
        if fig_bar:
            st.plotly_chart(fig_bar, use_container_width=True, key=f"bar_{title}")
    
    st.divider()

    # 5. CÁC BẢNG DỮ LIỆU CHI TIẾT (TABS)
    # ----------------------------------------------------
    t1, t2, t3, t4, t5 = st.tabs(["📊 Hiệu Suất Tổng", "🔄 Lịch Sử Cycle", "📦 Chi Tiết Kho (Live)", "⚠️ Cảnh Báo", "🔍 Nhật Ký GD"])

    with t1: # Hiệu suất tổng
        if not df_sum.empty:
            df_display = df_sum.rename(columns={'Tổng Vốn Đã Rót': '🔄 Doanh Số Mua'})
            cols = list(df_display.columns)
            if 'Vốn Hợp Lý (Sau Cổ Tức)' in cols and 'Giá Trị TT (Live)' in cols:
                try:
                    idx = cols.index('Vốn Hợp Lý (Sau Cổ Tức)')
                    cols.insert(idx + 1, cols.pop(cols.index('Giá Trị TT (Live)')))
                    if 'Chênh Lệch (Live)' in cols:
                        cols.insert(idx + 2, cols.pop(cols.index('Chênh Lệch (Live)')))
                    df_display = df_display[cols]
                except ValueError: pass

            st.dataframe(df_display.style.format({
                'Tổng SL Đã Bán': fmt_num, 'Lãi/Lỗ Giao Dịch': fmt_vnd, 'Cổ Tức Đã Nhận': fmt_vnd, 'Tổng Lãi Thực': fmt_vnd,
                '% Hiệu Suất (Trade)': fmt_pct, 'SL Đang Giữ': fmt_num, 'Vốn Gốc (Mua)': fmt_vnd, 'Vốn Hợp Lý (Sau Cổ Tức)': fmt_vnd,
                '🔄 Doanh Số Mua': fmt_vnd, '% Tỷ Trọng Vốn': fmt_pct, 'Ngày Giữ TB (Đã Bán)': fmt_float, 'Tuổi Kho TB': fmt_float,
                'Giá Trị TT (Live)': fmt_vnd, 'Chênh Lệch (Live)': fmt_vnd
            }), use_container_width=True, column_config=col_cfg)
        else: st.info("Chưa có dữ liệu.")

    with t2: # Cycle History
        if not df_cyc.empty:
            pnl_col = get_pnl_column(df_cyc)
            c_dist, c_scat = st.columns(2)
            
            fig_dist = draw_pnl_distribution(df_cyc)
            if fig_dist:
                with c_dist: st.plotly_chart(fig_dist, use_container_width=True, key=f"dist_{title}")
            
            fig_scat = draw_efficiency_scatter(df_cyc)
            if fig_scat:
                with c_scat: st.plotly_chart(fig_scat, use_container_width=True, key=f"scat_{title}")

            fmt_dict = {
                'Tổng Vốn Mua': fmt_vnd, 'Lãi Giao Dịch': fmt_vnd, 'Cổ Tức': fmt_vnd, 
                'Tổng Lãi Cycle': fmt_vnd, '% ROI Cycle': fmt_pct, 'Tuổi Vòng Đời': fmt_num
            }
            if pnl_col: fmt_dict[pnl_col] = fmt_vnd
            st.dataframe(df_cyc.style.format(fmt_dict), use_container_width=True, column_config=col_cfg)
        else: st.info("Chưa có chu kỳ.")

    with t3: # Kho
        if not df_inv.empty:
            limit = 1000
            if 'Lãi/Lỗ Tạm Tính' in df_inv.columns:
                limit = max(df_inv['Lãi/Lỗ Tạm Tính'].abs().max(), 1000)
            cols = [c for c in df_inv.columns if c not in ['Key_Map', 'Giá Tính Toán', 'Xu Hướng']]
            st.dataframe(
                df_inv[cols].style.format({
                    'SL Tồn': fmt_num, 'Giá Vốn Gốc': fmt_vnd, 'Giá Vốn ĐC': fmt_vnd, 
                    'Giá TT': fmt_vnd, 'Giá Trị TT': fmt_vnd, 'Lãi/Lỗ Tạm Tính': fmt_vnd,
                    '% Lãi/Lỗ': fmt_pct
                }).background_gradient(subset=['Lãi/Lỗ Tạm Tính'], cmap='RdYlGn', vmin=-limit, vmax=limit),
                use_container_width=True, column_config=col_cfg)
        else: st.info("Kho trống.")

    with t4: # Cảnh báo
        if not df_warn.empty:
            st.dataframe(df_warn.style.format({'Vốn Kẹp': fmt_vnd, 'Tuổi Kho TB': fmt_float}), use_container_width=True, column_config=col_cfg)
        else: st.success("An toàn.")

    with t5: # Nhật ký
        log_data = getattr(engine, 'trade_log', []) or getattr(engine, 'events', [])
        if log_data:
            st.dataframe(pd.DataFrame(log_data).style.format({
                'SL': fmt_num, 'Giá Bán': fmt_vnd, 'Giá Vốn': fmt_vnd, 'Lãi/Lỗ': fmt_vnd
            }), use_container_width=True, column_config=col_cfg)
        else: st.info("Chưa có nhật ký.")