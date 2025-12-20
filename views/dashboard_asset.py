# File: views/dashboard_asset.py
import streamlit as st
import pandas as pd
import plotly.express as px
from utils.formatters import fmt_vnd
# Import hàm vẽ biểu đồ mới
from components.charts import draw_nav_growth_chart, draw_profit_stacked_bar

def display(total_dep, total_cash, total_mkt_val, unrealized_pnl, real_nav, total_prof, df_history, df_sum, kpi_tips):
    """
    Hiển thị Góc nhìn Quản lý Tài sản (Asset View).
    """
    st.markdown("### 🏠 Tổng Quan Tài Sản (Asset Management)")
    
    # 1. KPI Cards
    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("💰 Tổng Tiền Đã Nạp", fmt_vnd(total_dep), help=kpi_tips["DEPOSIT"])
    c2.metric("💵 Tiền Mặt Đang Có", fmt_vnd(total_cash), help=kpi_tips["CASH"])
    c3.metric("📦 Giá Trị Kho (TT)", fmt_vnd(total_mkt_val), 
              delta=fmt_vnd(unrealized_pnl), delta_color="normal", 
              help=kpi_tips["MKT_VAL"])
    c4.metric("💎 NAV Thực Tế", fmt_vnd(real_nav), help=kpi_tips["NAV"])
    
    pct_profit = (total_prof / total_dep * 100) if total_dep != 0 else 0
    c5.metric("🚀 Tổng Lợi Nhuận", fmt_vnd(total_prof), 
              delta=f"{pct_profit:.1f}%", 
              help=kpi_tips["PROFIT"])

    st.divider()

    # 2. Biểu đồ Tăng trưởng NAV (Có điểm thực tế)
    if not df_history.empty:
        # [CẬP NHẬT] Truyền thêm real_nav vào đây
        st.plotly_chart(draw_nav_growth_chart(df_history, real_nav), use_container_width=True, key="nav_asset_view")
    else:
        st.info("Chưa có dữ liệu lịch sử để vẽ biểu đồ NAV.")

    st.divider()

    # 3. Phân bổ tài sản & Top Hiệu Quả
    c1, c2 = st.columns(2)
    
    # --- CỘT TRÁI: PIE CHART ---
    with c1:
        st.markdown("##### 🍰 Phân Bổ Tài Sản")
        view_mode = st.radio(
            "Tiêu chí phân bổ:", 
            ["Theo Vốn Gốc", "Theo Giá Thị Trường"], 
            horizontal=True,
            key="pie_mode_asset",
            label_visibility="collapsed"
        )
        
        if not df_sum.empty:
            if view_mode == "Theo Vốn Gốc":
                df_pie = df_sum[df_sum['Vốn Gốc (Mua)'] > 0].copy()
                val_col = 'Vốn Gốc (Mua)'
                title_chart = "Tỷ Trọng Theo Vốn Bỏ Ra"
            else:
                if 'Giá Trị TT (Live)' in df_sum.columns:
                    df_pie = df_sum[df_sum['Giá Trị TT (Live)'] > 0].copy()
                    val_col = 'Giá Trị TT (Live)'
                    title_chart = "Tỷ Trọng Theo Giá Thực Tế"
                else:
                    df_pie = pd.DataFrame()
            
            if not df_pie.empty:
                fig_pie = px.pie(df_pie, values=val_col, names='Mã CK', hole=0.4, title=f"({title_chart})")
                fig_pie.update_layout(margin=dict(t=30, b=0, l=0, r=0), height=320)
                st.plotly_chart(fig_pie, use_container_width=True, key="pie_asset_chart")
            else:
                st.caption("Không có cổ phiếu đang nắm giữ.")
        else:
            st.caption("Chưa có dữ liệu.")

    # --- CỘT PHẢI: STACKED BAR CHART ---
    with c2:
        st.markdown("##### 🏆 Hiệu Quả Đầu Tư (Realized + Unrealized)")
        st.write("") 
        st.write("") 
        
        if not df_sum.empty:
            # Tạo proxy cho df_inv từ df_sum (tận dụng dữ liệu đã có)
            # [LƯU Ý]: Đảm bảo df_sum có 'Chênh Lệch (Live)' nếu không sẽ dùng cột khác
            df_inv_proxy = pd.DataFrame()
            if 'Chênh Lệch (Live)' in df_sum.columns:
                df_inv_proxy = df_sum[['Mã CK', 'Chênh Lệch (Live)']].rename(columns={'Chênh Lệch (Live)': 'Lãi/Lỗ Tạm Tính'})
            
            fig_bar = draw_profit_stacked_bar(df_sum, df_inv_proxy)
            
            if fig_bar:
                st.plotly_chart(fig_bar, use_container_width=True, key="bar_asset_view")
            else:
                st.caption("Chưa có dữ liệu Lợi nhuận.")
        else:
            st.caption("Chưa có dữ liệu.")