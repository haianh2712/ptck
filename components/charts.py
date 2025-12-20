# File: components/charts.py
import plotly.express as px
import plotly.graph_objects as go
import pandas as pd

# [CẬP NHẬT] Hàm bổ trợ: Tìm cột Lãi/Lỗ thông minh (Thêm nhiều biến thể tên cột hơn)
def get_pnl_column(df):
    # Danh sách các tên cột có thể xuất hiện (Ưu tiên từ trái qua phải)
    candidates = [
        'Lãi/Lỗ', 'Lãi/Lỗ Thực', 'Tổng Lãi Cycle', 'Tổng Lãi/Lỗ', 
        'Lãi Giao Dịch', 'Profit', 'PnL', 'Lợi Nhuận', 'Realized PnL'
    ]
    for col in candidates:
        if col in df.columns:
            return col
    return None

# --- BIỂU ĐỒ 1: WIN RATE ---
def draw_win_rate_pie(kpi_data):
    if not kpi_data: return None
    total = kpi_data.get('total_trades', 0)
    rate = kpi_data.get('win_rate', 0)
    
    wins = int(total * rate / 100)
    losses = total - wins
    
    fig = px.pie(
        names=['Thắng', 'Thua'], values=[wins, losses],
        color=['Thắng', 'Thua'],
        color_discrete_map={'Thắng': '#00CC96', 'Thua': '#EF553B'},
        hole=0.6, title=f"Tỷ Lệ Thắng: {rate}%"
    )
    fig.update_layout(height=300, margin=dict(l=20, r=20, t=40, b=20))
    return fig

# --- BIỂU ĐỒ 2: RISK/REWARD ---
def draw_risk_reward_bar(kpi_data):
    if not kpi_data: return None
    avg_win = kpi_data.get('avg_win', 0)
    avg_loss = abs(kpi_data.get('avg_loss', 0))
    ratio = kpi_data.get('payoff_ratio', 0)
    
    fig = go.Figure(data=[
        go.Bar(name='Lãi TB', x=['Lãi'], y=[avg_win], marker_color='#00CC96', text=[f"{avg_win:,.0f}"], textposition='auto'),
        go.Bar(name='Lỗ TB', x=['Lỗ'], y=[avg_loss], marker_color='#EF553B', text=[f"{avg_loss:,.0f}"], textposition='auto')
    ])
    fig.add_annotation(x=0.5, y=max(avg_win, avg_loss), xref="paper", yref="y", text=f"R/R: {ratio} lần", showarrow=False, yshift=20)
    fig.update_layout(title="Tỷ Lệ Reward / Risk", yaxis_title="VND", height=300, showlegend=False, margin=dict(l=20, r=20, t=40, b=20))
    return fig

# --- BIỂU ĐỒ 3: PHÂN BỔ PNL ---
def draw_pnl_distribution(cycles_df):
    if cycles_df.empty: return None
    
    # Tự động tìm tên cột
    pnl_col = get_pnl_column(cycles_df)
    if not pnl_col: return None # Trả về None nếu không tìm thấy cột

    df_grp = cycles_df.groupby('Mã CK')[pnl_col].sum().reset_index()
    df_grp = df_grp.sort_values(by=pnl_col, ascending=False)
    colors = ['#00CC96' if x >= 0 else '#EF553B' for x in df_grp[pnl_col]]
    
    fig = px.bar(
        df_grp, x='Mã CK', y=pnl_col, text_auto='.2s',
        title="Phân Bổ Lãi/Lỗ Thực Tế Theo Mã"
    )
    fig.update_traces(marker_color=colors)
    fig.update_layout(xaxis_title=None, yaxis_title="VND")
    return fig

# --- BIỂU ĐỒ 4: MA TRẬN HIỆU QUẢ ---
def draw_efficiency_scatter(cycles_df):
    if cycles_df.empty: return None
    if 'Tổng Vốn Mua' not in cycles_df.columns: return None
    
    pnl_col = get_pnl_column(cycles_df)
    if not pnl_col: return None

    stats = cycles_df.groupby('Mã CK').agg({
        'Tổng Vốn Mua': 'sum',
        pnl_col: 'sum',
        '% ROI Cycle': 'mean'
    }).reset_index()
    
    fig = px.scatter(
        stats,
        x='Tổng Vốn Mua', y=pnl_col,
        size=stats['% ROI Cycle'].abs() + 1,
        color=pnl_col,
        hover_name='Mã CK', text='Mã CK',
        color_continuous_scale=['#EF553B', '#F3F4F6', '#00CC96'],
        title="Ma Trận Hiệu Quả Đầu Tư (Rủi Ro vs Lợi Nhuận)"
    )
    fig.add_hline(y=0, line_dash="dash", line_color="gray")
    fig.update_traces(textposition='top center')
    fig.update_layout(xaxis_title="Tổng Vốn Xoay Vòng", yaxis_title="Tổng Lãi/Lỗ", height=500)
    return fig

# --- BIỂU ĐỒ 5: TĂNG TRƯỞNG NAV ---
def draw_nav_growth_chart(history_df, current_real_nav=None):
    if history_df.empty: return None
    
    fig = go.Figure()
    
    # 1. Đường Vốn Gốc
    if 'Vốn Nạp Ròng' in history_df.columns:
        fig.add_trace(go.Scatter(
            x=history_df['Ngày'], y=history_df['Vốn Nạp Ròng'], 
            mode='lines', name='Vốn Gốc Đã Nạp', 
            line=dict(color='gray', dash='dash', width=2)
        ))
    
    # 2. Đường NAV Sổ Sách
    if 'Tổng Tài Sản (NAV)' in history_df.columns:
        fig.add_trace(go.Scatter(
            x=history_df['Ngày'], y=history_df['Tổng Tài Sản (NAV)'], 
            mode='lines', name='NAV Sổ Sách', 
            line=dict(color='#00CC96', width=3), 
            fill='tonexty'
        ))

        # 3. Điểm NAV Thực Tế
        if current_real_nav is not None and current_real_nav > 0:
            last_date = history_df['Ngày'].iloc[-1]
            last_book_nav = history_df['Tổng Tài Sản (NAV)'].iloc[-1]
            current_date = pd.Timestamp.now()
            
            diff = current_real_nav - last_book_nav
            is_profit = diff >= 0
            color = '#00CC96' if is_profit else '#EF553B' 
            
            fig.add_trace(go.Scatter(
                x=[last_date, current_date], y=[last_book_nav, current_real_nav],
                mode='lines', name='Chênh lệch TT', line=dict(color=color, width=2, dash='dash'), showlegend=False
            ))

            fig.add_trace(go.Scatter(
                x=[current_date], y=[current_real_nav],
                mode='markers+text', name='NAV Thực Tế (Live)',
                marker=dict(color=color, size=10, symbol='diamond'),
                text=[f"{current_real_nav:,.0f}"], textposition="top center",
                hoverinfo='text+name'
            ))

    fig.update_layout(
        title="📈 Tăng Trưởng Tài Sản (NAV Sổ Sách vs Thực Tế)",
        xaxis_title="", yaxis_title="VND", hovermode="x unified", height=450,
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
    )
    return fig

# --- BIỂU ĐỒ 6: HIỆU QUẢ STACKED BAR ---
def draw_profit_stacked_bar(df_sum, df_inv):
    try:
        # 1. Lãi Đã Chốt
        d1 = pd.DataFrame(columns=['Mã CK', 'Đã Chốt'])
        if not df_sum.empty:
            realized_col = get_pnl_column(df_sum) # Tìm cột linh hoạt
            if not realized_col:
                # Fallback tìm các tên khác nếu hàm get_pnl_column chưa đủ
                if 'Lãi/Lỗ Giao Dịch' in df_sum.columns: realized_col = 'Lãi/Lỗ Giao Dịch'
                elif 'Tổng Lãi Thực' in df_sum.columns: realized_col = 'Tổng Lãi Thực'
            
            if realized_col:
                d1 = df_sum[['Mã CK', realized_col]].rename(columns={realized_col: 'Đã Chốt'})

        # 2. Lãi Tạm Tính
        d2 = pd.DataFrame(columns=['Mã CK', 'Tạm Tính'])
        if not df_inv.empty:
            unrealized_col = None
            for col in ['Chênh Lệch (Live)', 'Lãi/Lỗ Tạm Tính', 'Unrealized PnL']:
                if col in df_inv.columns:
                    unrealized_col = col
                    break
            
            if unrealized_col:
                d2 = df_inv.groupby('Mã CK')[unrealized_col].sum().reset_index().rename(columns={unrealized_col: 'Tạm Tính'})

        if d1.empty and d2.empty: return None
        
        df_merge = pd.merge(d1, d2, on='Mã CK', how='outer').fillna(0)
        df_merge['Total'] = df_merge['Đã Chốt'] + df_merge['Tạm Tính']
        df_merge = df_merge.sort_values(by='Total', ascending=False).head(15) 

        df_long = df_merge.melt(id_vars='Mã CK', value_vars=['Đã Chốt', 'Tạm Tính'], 
                                var_name='Loại', value_name='Số Tiền')
        df_long = df_long[df_long['Số Tiền'] != 0]

        fig = px.bar(
            df_long, x='Mã CK', y='Số Tiền', color='Loại',
            title='Hiệu Quả: Đã Chốt vs Tạm Tính',
            color_discrete_map={'Đã Chốt': '#00CC96', 'Tạm Tính': '#636EFA'},
            text_auto='.2s'
        )
        
        fig.update_layout(barmode='relative', xaxis_title="", yaxis_title="Lợi Nhuận (VND)", legend_title="", height=350, margin=dict(t=30, b=0, l=0, r=0))
        return fig

    except Exception as e:
        print(f"Lỗi vẽ Stacked Bar: {e}")
        return None