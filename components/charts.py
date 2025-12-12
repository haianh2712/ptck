# File: components/charts.py
import plotly.express as px
import plotly.graph_objects as go
import pandas as pd

# --- BIỂU ĐỒ 1: WIN RATE (TRÒN) ---
def draw_win_rate_pie(kpi_data):
    if not kpi_data: return None
    wins = int(kpi_data['total_trades'] * kpi_data['win_rate'] / 100)
    losses = kpi_data['total_trades'] - wins
    
    fig = px.pie(
        names=['Thắng', 'Thua'],
        values=[wins, losses],
        color=['Thắng', 'Thua'],
        color_discrete_map={'Thắng': '#00CC96', 'Thua': '#EF553B'},
        hole=0.6,
        title=f"Tỷ Lệ Thắng: {kpi_data['win_rate']}%"
    )
    fig.update_layout(height=300, margin=dict(l=20, r=20, t=40, b=20))
    return fig

# --- BIỂU ĐỒ 2: RISK/REWARD (CỘT) ---
def draw_risk_reward_bar(kpi_data):
    if not kpi_data: return None
    avg_win = kpi_data['avg_win']
    avg_loss = abs(kpi_data['avg_loss'])
    ratio = kpi_data['payoff_ratio']
    
    fig = go.Figure(data=[
        go.Bar(name='Lãi TB', x=['Lãi'], y=[avg_win], marker_color='#00CC96', text=[f"{avg_win:,.0f}"], textposition='auto'),
        go.Bar(name='Lỗ TB', x=['Lỗ'], y=[avg_loss], marker_color='#EF553B', text=[f"{avg_loss:,.0f}"], textposition='auto')
    ])
    fig.add_annotation(x=0.5, y=max(avg_win, avg_loss), xref="paper", yref="y", text=f"R/R: {ratio} lần", showarrow=False, yshift=20)
    fig.update_layout(title="Tỷ Lệ Reward / Risk", yaxis_title="VND", height=300, showlegend=False, margin=dict(l=20, r=20, t=40, b=20))
    return fig

# --- BIỂU ĐỒ 3: PHÂN BỐ LÃI/LỖ (CỘT) ---
def draw_pnl_distribution(cycles_df):
    if cycles_df.empty: return None
    df_grp = cycles_df.groupby('Mã CK')['Lãi/Lỗ'].sum().reset_index()
    df_grp = df_grp.sort_values(by='Lãi/Lỗ', ascending=False)
    colors = ['#00CC96' if x >= 0 else '#EF553B' for x in df_grp['Lãi/Lỗ']]
    
    fig = px.bar(
        df_grp, x='Mã CK', y='Lãi/Lỗ', text_auto='.2s',
        title="Phân Bổ Lãi/Lỗ Thực Tế Theo Mã"
    )
    fig.update_traces(marker_color=colors)
    fig.update_layout(xaxis_title=None, yaxis_title="VND")
    return fig

# --- BIỂU ĐỒ 4: MA TRẬN HIỆU QUẢ (SCATTER) ---
def draw_efficiency_scatter(cycles_df):
    if cycles_df.empty: return None
    
    # Lưu ý: Cột 'Tổng Vốn Mua' phải được map từ Engine
    if 'Tổng Vốn Mua' not in cycles_df.columns:
        return None

    stats = cycles_df.groupby('Mã CK').agg({
        'Tổng Vốn Mua': 'sum',
        'Lãi/Lỗ': 'sum',
        '% ROI Cycle': 'mean'
    }).reset_index()
    
    fig = px.scatter(
        stats,
        x='Tổng Vốn Mua', y='Lãi/Lỗ',
        size=stats['% ROI Cycle'].abs() + 1,
        color='Lãi/Lỗ',
        hover_name='Mã CK', text='Mã CK',
        color_continuous_scale=['#EF553B', '#F3F4F6', '#00CC96'],
        title="Ma Trận Hiệu Quả Đầu Tư (Rủi Ro vs Lợi Nhuận)"
    )
    fig.add_hline(y=0, line_dash="dash", line_color="gray")
    fig.update_traces(textposition='top center')
    fig.update_layout(xaxis_title="Tổng Vốn Xoay Vòng", yaxis_title="Tổng Lãi/Lỗ", height=500)
    return fig

# --- BIỂU ĐỒ 5: TĂNG TRƯỞNG TÀI SẢN (NAV) ---
def draw_nav_growth_chart(history_df):
    if history_df.empty: return None
    
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=history_df['Ngày'], y=history_df['Vốn Nạp Ròng'], mode='lines', name='Vốn Gốc Đã Nạp', line=dict(color='gray', dash='dash', width=2)))
    fig.add_trace(go.Scatter(x=history_df['Ngày'], y=history_df['Tổng Tài Sản (NAV)'], mode='lines', name='Tổng Tài Sản (NAV)', line=dict(color='#00CC96', width=3), fill='tonexty'))

    fig.update_layout(
        title="📈 Tăng Trưởng Tài Sản Theo Thời Gian (NAV vs Vốn Gốc)",
        xaxis_title="", yaxis_title="VND", hovermode="x unified", height=450,
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
    )
    return fig