# File: modules/vip_deals/view.py
# Version: FINAL (Charts + Performance Table)

import streamlit as st
import plotly.graph_objects as go
import pandas as pd
from modules.vip_deals.analyzer import analyze_cost_advantage, analyze_cashflow_sankey

# --- Thay thế hàm này trong modules/vip_deals/view.py ---

def render_performance_attribution(engine, live_prices):
    """
    Tính năng 3: Bảng Phong Thần (Hunter vs. Trader)
    Phân tách hiệu quả đầu tư thành 2 nguồn: Săn Deal (VIP) và Lướt Sóng (Trading)
    """
    st.markdown("---")
    st.subheader("3. Bảng Phong Thần: Hunter vs. Trader")
    
    # 1. Xử lý dữ liệu
    hunter_data = [] 
    trader_data = [] 
    
    total_hunter_profit = 0
    total_hunter_cost = 0
    total_trader_profit = 0
    total_trader_cost = 0

    # Lấy dữ liệu từ Engine
    for ticker, holding in engine.data.items():
        # Lấy giá thị trường (đã bỏ đuôi WFT)
        clean_ticker = ticker.replace('_WFT', '')
        current_price = live_prices.get(clean_ticker, 0)
        
        # Lấy danh sách các lô lẻ (FIFO queues)
        if hasattr(engine, 'fifo_queues') and ticker in engine.fifo_queues:
            batches = engine.fifo_queues[ticker]
            
            for batch in batches:
                # [SỬA LỖI QUAN TRỌNG TẠI ĐÂY]
                # Engine lưu là 'vol' và 'cost', không phải 'qty' và 'price'
                qty = batch.get('vol', 0)     # <--- Sửa qty -> vol
                cost_price = batch.get('cost', 0) # <--- Sửa price -> cost
                
                src = batch.get('source', 'UNKNOWN')
                date_in = batch.get('date', 'N/A')
                
                if qty <= 0: continue
                
                market_val = qty * current_price
                cost_val = qty * cost_price
                pnl = market_val - cost_val
                pnl_pct = (pnl / cost_val * 100) if cost_val > 0 else 0
                
                # Phân loại Hunter vs Trader (Dựa trên Source đã lưu chuẩn từ Engine)
                is_hunter = False
                src_upper = str(src).upper()
                
                # Logic nhận diện: Nếu nguồn chứa từ khóa Deal/IPO/Bonus/Rights
                hunter_keywords = ['IPO', 'DEAL', 'BONUS', 'RIGHTS', 'WFT', 'CỔ TỨC', 'THƯỞNG', 'QUYỀN', 'CHUYỂN ĐỔI']
                if any(k in src_upper for k in hunter_keywords):
                    is_hunter = True
                
                # Logic phụ trợ: Nếu là mã WFT thì chắc chắn là Hunter
                if '_WFT' in ticker:
                    is_hunter = True

                item = {
                    'Mã': clean_ticker,
                    'Loại': '🎁 Săn Deal' if is_hunter else '🌊 Trading',
                    'Nguồn': src,
                    'Ngày về': date_in.strftime('%d/%m/%Y') if hasattr(date_in, 'strftime') else str(date_in),
                    'KL': qty,
                    'Giá Vốn': cost_price,
                    'Thị Trường': current_price,
                    'Lãi/Lỗ (VND)': pnl,
                    '% ROI': pnl_pct
                }
                
                if is_hunter:
                    hunter_data.append(item)
                    total_hunter_cost += cost_val
                    total_hunter_profit += pnl
                else:
                    trader_data.append(item)
                    total_trader_cost += cost_val
                    total_trader_profit += pnl

    # 2. HIỂN THỊ METRIC CARDS
    c1, c2 = st.columns(2)
    
    roi_hunter = (total_hunter_profit / total_hunter_cost * 100) if total_hunter_cost > 0 else 0
    roi_trader = (total_trader_profit / total_trader_cost * 100) if total_trader_cost > 0 else 0
    
    with c1:
        st.markdown(f"""
        <div style="background-color: #2ecc71; padding: 20px; border-radius: 10px; color: white;">
            <h3 style="margin:0; color:white;">🏹 TEAM HUNTER</h3>
            <p style="margin:0;">(Deal, IPO, Cổ tức)</p>
            <h2 style="margin:10px 0; color:white;">+{total_hunter_profit:,.0f} đ</h2>
            <h4 style="margin:0; color:white;">ROI: {roi_hunter:,.2f}%</h4>
        </div>
        """, unsafe_allow_html=True)
        
    with c2:
        color_trader = "#e67e22" if total_trader_profit >= 0 else "#e74c3c"
        sign = "+" if total_trader_profit >= 0 else ""
        st.markdown(f"""
        <div style="background-color: {color_trader}; padding: 20px; border-radius: 10px; color: white;">
            <h3 style="margin:0; color:white;">🌊 TEAM TRADER</h3>
            <p style="margin:0;">(Mua khớp lệnh)</p>
            <h2 style="margin:10px 0; color:white;">{sign}{total_trader_profit:,.0f} đ</h2>
            <h4 style="margin:0; color:white;">ROI: {roi_trader:,.2f}%</h4>
        </div>
        """, unsafe_allow_html=True)

    # 3. HIỂN THỊ BẢNG CHI TIẾT
    st.write("")
    st.markdown("#### 📖 Sổ Tay Chi Tiết (Từng Lô Hàng)")
    
    full_df = pd.DataFrame(hunter_data + trader_data)
    
    if not full_df.empty:
        full_df.sort_values(by=['Loại', 'Mã'], ascending=[True, True], inplace=True)
        
        st.dataframe(
            full_df.style.format({
                'KL': "{:,.0f}",
                'Giá Vốn': "{:,.0f}",
                'Thị Trường': "{:,.0f}",
                'Lãi/Lỗ (VND)': "{:+,.0f}",
                '% ROI': "{:+.2f}%"
            }).applymap(lambda x: 'color: #2ecc71' if x > 0 else 'color: #e74c3c', subset=['Lãi/Lỗ (VND)', '% ROI']),
            use_container_width=True,
            height=500
        )
    else:
        st.info("Chưa có dữ liệu chi tiết để hiển thị.")


# --- HÀM CHÍNH: HIỂN THỊ TAB VIP ---
def render_vip_deals_tab(engine, live_prices, account_name="Unknown"):
    """
    Hàm hiển thị giao diện Tab Kho Báu IPO & Deal
    """
    st.markdown(f"## 💎 Phân Tích Deal VIP: Tài khoản {account_name}")
    
    # 1. Chạy phân tích
    df_cost = analyze_cost_advantage(engine)
    
    # [LOGIC LỌC]
    if not df_cost.empty and 'VIP Deal' in df_cost.columns:
        df_vip_only = df_cost[df_cost['VIP Deal'] > 0].copy()
        if not df_vip_only.empty:
            df_cost = df_vip_only
        else:
            st.info(f"⚠️ Tài khoản {account_name} không có mã nào thuộc diện IPO/Quyền mua.")
            return
    else:
        st.info(f"⚠️ Tài khoản {account_name} chưa ghi nhận giao dịch IPO/Deal nào.")
        return

    col1, col2 = st.columns([1, 1])

    # --- BIỂU ĐỒ 1: LỢI THẾ GIÁ VỐN ---
    with col1:
        st.subheader("1. So Sánh Giá Vốn Thực Tế (Chỉ mã VIP)")
        
        current_prices = []
        tickers = df_cost.index.tolist()
        for t in tickers:
            key = str(t).strip().upper()
            p = live_prices.get(key, 0)
            current_prices.append(p)
        
        df_cost['Thị Trường'] = current_prices
        
        fig = go.Figure()
        
        # Cột Giá Deal
        fig.add_trace(go.Bar(
            x=df_cost.index, y=df_cost['VIP Deal'],
            name='Giá Vốn Deal VIP', marker_color='#2ecc71',
            text=df_cost['VIP Deal'].apply(lambda x: f"{x:,.0f}"), textposition='auto'
        ))
        
        # Cột Giá Trading
        if 'Trading' in df_cost.columns:
            fig.add_trace(go.Bar(
                x=df_cost.index, y=df_cost['Trading'],
                name='Giá Vốn Trading', marker_color='#3498db',
                text=df_cost['Trading'].apply(lambda x: f"{x:,.0f}" if x>0 else ""), textposition='auto'
            ))
            
        # Đường Giá Thị Trường
        fig.add_trace(go.Scatter(
            x=df_cost.index, y=df_cost['Thị Trường'],
            mode='lines+markers', name='Giá Thị Trường (Live)',
            line=dict(color='#e74c3c', width=3, dash='dot'), marker=dict(size=8)
        ))

        fig.update_layout(
            barmode='group', height=450,
            legend=dict(orientation="h", y=1.1),
            yaxis=dict(title='Giá (VND)'), xaxis=dict(title='Mã Cổ Phiếu')
        )
        st.plotly_chart(fig, use_container_width=True)
        
        # INSIGHTS
        st.markdown("#### 💡 Góc nhìn chuyên gia:")
        for t in tickers:
            p_deal = df_cost.loc[t].get('VIP Deal', 0)
            p_trade = df_cost.loc[t].get('Trading', 0)
            p_mkt = df_cost.loc[t].get('Thị Trường', 0)
            
            if p_deal > 0 and p_trade > 0 and p_deal < p_trade:
                diff = (1 - p_deal/p_trade) * 100
                st.write(f"- ✅ **{t}**: Giá Deal rẻ hơn Trading **{diff:.1f}%**.")
            
            if p_deal > 0 and p_mkt > p_deal:
                roi = (p_mkt/p_deal - 1) * 100
                st.write(f"- 🚀 **{t}**: Lô Deal đang lãi **+{roi:.1f}%** (so với thị giá).")

    # --- BIỂU ĐỒ 2: DÒNG CHẢY VỐN (Sankey) - CHỮ VÀNG + BÓNG ĐẸP ---
    with col2:
        st.subheader("2. Dòng Chảy Phân Bổ Vốn")
        sankey_data = analyze_cashflow_sankey(engine)
        
        if sankey_data and len(sankey_data['source']) > 0:
            node_colors = ["#95a5a6", "#2ecc71", "#e67e22", "#3498db"]
            
            fig_sk = go.Figure(data=[go.Sankey(
                # Font chữ Vàng Gold
                textfont = dict(size=14, color="#FFD700", family="Arial"),
                
                # Node form cũ (có viền đen tạo bóng)
                node = dict(
                  pad = 15, thickness = 20,
                  line = dict(color = "black", width = 0.5),
                  label = ["Nguồn Vốn", "Hệ thống Deal (IPO)", "Hệ thống Trading", "Két Tiền Mặt"],
                  color = node_colors
                ),
                
                link = dict(
                  source = sankey_data['source'], target = sankey_data['target'],
                  value = sankey_data['value'], label = sankey_data['label']
              ))])
            
            fig_sk.update_layout(
                height=500,
                title_text="Sơ đồ luân chuyển dòng tiền",
                title_font=dict(size=18, color="#2B00FF"), # Tiêu đề cũng màu vàng
                font=dict(size=14, color="#FFD700"),       # Font dự phòng
                margin=dict(l=10, r=10, t=40, b=10),
                paper_bgcolor='rgba(169,169,169,0.5)',
                plot_bgcolor='rgba(169,169,169,1)'
            )
            
            st.plotly_chart(fig_sk, use_container_width=True)
            
            st.info("""
            **Giải thích biểu đồ:**
            - **Nhánh Xanh Lá (Deal):** Dòng vốn đi vào các mã có lợi thế giá vốn (IPO, Quyền mua).
            - **Nhánh Cam (Trading):** Dòng vốn đi vào các mã mua khớp lệnh thông thường.
            - **Mục tiêu:** Nên gia tăng tỷ trọng nhánh Xanh Lá để danh mục bền vững hơn.
            """)
        else:
            st.info("Chưa có dữ liệu dòng tiền để vẽ biểu đồ.")

    # --- CUỐI CÙNG: GỌI HÀM BẢNG PHONG THẦN ---
    # (Nằm ngoài 2 cột để hiển thị full chiều ngang)
    render_performance_attribution(engine, live_prices)