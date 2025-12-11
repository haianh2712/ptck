# File: app.py
import streamlit as st
import pandas as pd
import plotly.express as px

from processors.adapter_vck import VCKAdapter
from processors.adapter_vps import VPSAdapter
from processors.engine import PortfolioEngine
from utils.formatters import fmt_vnd, fmt_num, fmt_pct, fmt_float

st.set_page_config(page_title="Dashboard Quản Lý Đầu Tư", page_icon="📈", layout="wide", initial_sidebar_state="expanded")
st.title("📊 Dashboard Phân Tích Hiệu Quả Đầu Tư")
st.markdown("---")

with st.sidebar:
    st.header("📂 Nguồn Dữ Liệu")
    file_vck = st.file_uploader("Upload File VCK (history_VCK.xlsx)", type=['xlsx'])
    file_vps = st.file_uploader("Upload File VPS (history3.xlsx)", type=['xlsx'])
    st.divider()
    btn_run = st.button("🚀 CHẠY PHÂN TÍCH", type="primary", use_container_width=True)
    st.info("💡 Mẹo: Hệ thống tự động lọc 'Lãi tiền gửi' và tính Tiền Mặt thực tế.")

if btn_run:
    if not file_vck and not file_vps:
        st.warning("⚠️ Vui lòng upload ít nhất 1 file dữ liệu.")
        st.stop()

    engine_vck = PortfolioEngine("VCK")
    engine_vps = PortfolioEngine("VPS")
    has_vck = False
    has_vps = False

    if file_vck:
        with st.spinner("Đang xử lý dữ liệu VCK..."):
            try:
                events_vck = VCKAdapter().parse(file_vck)
                if events_vck:
                    for e in events_vck: engine_vck.process_event(e)
                    has_vck = True
            except Exception as e: st.error(f"Lỗi xử lý file VCK: {e}")

    if file_vps:
        with st.spinner("Đang xử lý dữ liệu VPS..."):
            try:
                events_vps = VPSAdapter().parse(file_vps)
                if events_vps:
                    for e in events_vps: engine_vps.process_event(e)
                    has_vps = True
            except Exception as e: st.error(f"Lỗi xử lý file VPS: {e}")

    if not has_vck and not has_vps:
        st.error("❌ Không tìm thấy dữ liệu hợp lệ nào.")
        st.stop()

    # --- TÍNH TOÁN KPI CHÍNH ---
    total_deposit = engine_vck.total_deposit + engine_vps.total_deposit
    total_net_profit = engine_vck.total_profit + engine_vps.total_profit
    
    df_sum_vck, _, _, _ = engine_vck.generate_reports()
    df_sum_vps, _, _, _ = engine_vps.generate_reports()
    val_adj_vck = df_sum_vck['Vốn Hợp Lý (Sau Cổ Tức)'].sum() if not df_sum_vck.empty else 0
    val_adj_vps = df_sum_vps['Vốn Hợp Lý (Sau Cổ Tức)'].sum() if not df_sum_vps.empty else 0
    total_inventory_val = val_adj_vck + val_adj_vps

    count_vck = len(df_sum_vck[df_sum_vck['SL Đang Giữ'] > 0]) if not df_sum_vck.empty else 0
    count_vps = len(df_sum_vps[df_sum_vps['SL Đang Giữ'] > 0]) if not df_sum_vps.empty else 0
    total_active_tickers = count_vck + count_vps

    # [TIỀN MẶT]
    # VPS: Dùng số dư thực tế từ sổ cái (CASH_SNAPSHOT)
    cash_vps = engine_vps.real_cash_balance
    # VCK: [MỚI] Cũng dùng số dư thực tế từ cột "Số dư lũy kế"
    cash_vck = engine_vck.real_cash_balance
    
    total_cash_available = cash_vps + cash_vck

    # --- HIỂN THỊ KPI ---
    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("💰 Tổng Tiền Đã Nạp", fmt_vnd(total_deposit), help="Tổng tiền mặt nạp vào tài khoản từ trước đến nay.")
    c2.metric("📈 Tổng Lãi Thực Nhận", fmt_vnd(total_net_profit), delta_color="normal", help="Tổng Lãi Giao Dịch + Cổ Tức Tiền Mặt.")
    c3.metric("💵 Tiền Mặt Đang Có", fmt_vnd(total_cash_available), help="Tổng tiền mặt từ tất cả các tài khoản.")
    c4.metric("📦 Giá Trị Kho", fmt_vnd(total_inventory_val), help="Tổng giá vốn của hàng đang giữ (Đã trừ đi tiền cổ tức nhận được để giảm giá vốn).")
    c5.metric("📊 Mã Đang Giữ", f"{total_active_tickers}", help="Số lượng mã cổ phiếu hiện đang có trong danh mục.")

    st.divider()

    def display_account_section(engine, title, df_sum, df_cyc, df_inv, df_warn):
        st.markdown(f"## 🏦 {title}")
        if df_sum.empty: st.info("Chưa có dữ liệu."); return

        c_chart1, c_chart2 = st.columns(2)
        with c_chart1:
            df_holding = df_sum[df_sum['Vốn Gốc (Mua)'] > 0]
            if not df_holding.empty:
                fig_pie = px.pie(df_holding, values='Vốn Gốc (Mua)', names='Mã CK', title='Phân Bổ Vốn Gốc (Exposure)', hole=0.4)
                st.plotly_chart(fig_pie, use_container_width=True)
            else: st.info("Full Cash.")

        with c_chart2:
            df_pl = df_sum.sort_values(by='Tổng Lãi Thực', ascending=False).head(10)
            if not df_pl.empty:
                colors = ['#00CC96' if x >= 0 else '#EF553B' for x in df_pl['Tổng Lãi Thực']]
                fig_bar = px.bar(df_pl, x='Mã CK', y='Tổng Lãi Thực', title='Top Hiệu Quả (Lãi + Cổ Tức)', text_auto='.2s')
                fig_bar.update_traces(marker_color=colors)
                st.plotly_chart(fig_bar, use_container_width=True)

        t1, t2, t3, t4, t5 = st.tabs(["📋 Hiệu Suất Tổng", "🔄 Lịch Sử Cycle", "📦 Chi Tiết Kho", "⚠️ Cảnh Báo", "🔍 Soi Lỗi"])
        with t1:
            df_display = df_sum.rename(columns={'Tổng Vốn Đã Rót': '🔄 Doanh Số Mua (Vốn Quay)'})
            st.dataframe(df_display.style.format({
                'Tổng SL Đã Bán': fmt_num, 'SL Đang Giữ': fmt_num,
                'Lãi/Lỗ Giao Dịch': fmt_vnd, 'Cổ Tức Đã Nhận': fmt_vnd, 'Tổng Lãi Thực': fmt_vnd,
                'Vốn Gốc (Mua)': fmt_vnd, 'Vốn Hợp Lý (Sau Cổ Tức)': fmt_vnd, '🔄 Doanh Số Mua (Vốn Quay)': fmt_vnd, 
                '% Hiệu Suất (Trade)': fmt_pct, '% Tỷ Trọng Vốn': fmt_pct,
                'Ngày Giữ TB (Đã Bán)': fmt_float, 'Tuổi Kho TB': fmt_float
            }).background_gradient(subset=['Tổng Lãi Thực'], cmap='RdYlGn'), use_container_width=True)
        with t2:
            st.dataframe(df_cyc.style.format({'Tổng Vốn Mua': fmt_vnd, 'Tổng Tiền Bán': fmt_vnd, 'Lãi Giao Dịch': fmt_vnd, 'Cổ Tức': fmt_vnd, 'Tổng Lãi Cycle': fmt_vnd, '% ROI Cycle': fmt_pct}), use_container_width=True)
        with t3:
            st.dataframe(df_inv.style.format({'Giá Vốn Gốc': fmt_vnd, 'Giá Vốn ĐC': fmt_vnd, 'SL Tồn': fmt_num}), use_container_width=True)
        with t4:
            if not df_warn.empty: st.dataframe(df_warn.style.format({'Vốn Kẹp': fmt_vnd, 'Tuổi Kho TB': fmt_float}), use_container_width=True)
            else: st.success("Danh mục an toàn.")
        with t5:
            if engine.trade_log:
                df_log = pd.DataFrame(engine.trade_log)
                if 'Ngày' in df_log.columns: df_log['Ngày'] = pd.to_datetime(df_log['Ngày']).dt.strftime('%d/%m/%Y')
                all_syms = sorted(df_log['Mã'].unique())
                sel = st.selectbox(f"Lọc theo Mã ({title}):", ['Tất cả'] + all_syms, key=f"s_{title}")
                if sel != 'Tất cả': df_log = df_log[df_log['Mã'] == sel]
                st.dataframe(df_log.style.format({'SL': fmt_num, 'Giá Bán': fmt_vnd, 'Giá Vốn': fmt_vnd, 'Lãi/Lỗ': fmt_vnd}), use_container_width=True)
        st.markdown("---")

    if has_vck:
        df_s, df_c, df_i, df_w = engine_vck.generate_reports()
        display_account_section(engine_vck, "Tài Khoản VCK", df_s, df_c, df_i, df_w)
    if has_vps:
        df_s, df_c, df_i, df_w = engine_vps.generate_reports()
        display_account_section(engine_vps, "Tài Khoản VPS", df_s, df_c, df_i, df_w)
else:
    st.info("👋 Chào mừng! Vui lòng upload file dữ liệu và nhấn nút 'CHẠY PHÂN TÍCH'.")