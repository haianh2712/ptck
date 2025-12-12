# File: components/psychology_charts.py
import plotly.express as px
import plotly.graph_objects as go
import pandas as pd
import streamlit as st
from plotly.subplots import make_subplots

# --- 1. BIỂU ĐỒ NHỊP TIM ---
def draw_trading_timeline(trade_log):
    if not trade_log: return None
    try:
        df = pd.DataFrame(trade_log)
        col_map = {'type': 'Loại', 'date': 'Ngày', 'sym': 'Mã'}
        for old, new in col_map.items():
            if old in df.columns and new not in df.columns: df[new] = df[old]

        req = ['Loại', 'Ngày', 'Mã']
        if not all(c in df.columns for c in req): return None

        df = df[df['Loại'].isin(['MUA', 'BÁN', 'BUY', 'SELL'])]
        if df.empty: return None

        color_map = {'MUA': '#00CC96', 'BUY': '#00CC96', 'BÁN': '#FF2B2B', 'SELL': '#FF2B2B'}
        symbol_map = {'MUA': 'triangle-up', 'BUY': 'triangle-up', 'BÁN': 'triangle-down', 'SELL': 'triangle-down'}

        fig = px.scatter(
            df, x='Ngày', y='Mã', color='Loại', symbol='Loại',
            color_discrete_map=color_map, symbol_map=symbol_map,
            hover_data={'Ngày': True, 'Mã': True, 'Loại': False},
            title="Nhịp Tim Giao Dịch", height=500
        )
        fig.update_traces(marker=dict(size=14, line=dict(width=1, color='DarkSlateGrey')))
        fig.update_layout(xaxis_title="Thời Gian", yaxis_title="Mã CP")
        return fig
    except: return None

# --- 2. MA TRẬN KỶ LUẬT ---
def draw_discipline_matrix(closed_cycles):
    if not closed_cycles: return None
    try:
        df = pd.DataFrame(closed_cycles)
        
        # Data Healing
        if 'Tuổi Vòng Đời' not in df.columns: df['Tuổi Vòng Đời'] = 0
        if 'Lãi/Lỗ' not in df.columns: df['Lãi/Lỗ'] = 0
        if 'Tổng Vốn Mua' not in df.columns: df['Tổng Vốn Mua'] = 1000000
        if 'Mã CK' not in df.columns: df['Mã CK'] = 'UNKNOWN'

        # Ép kiểu
        df['Days'] = pd.to_numeric(df['Tuổi Vòng Đời'], errors='coerce').fillna(0)
        df['PnL'] = pd.to_numeric(df['Lãi/Lỗ'], errors='coerce').fillna(0)
        df['Capital'] = pd.to_numeric(df['Tổng Vốn Mua'], errors='coerce').fillna(0).abs()
        
        df['Vốn_Fmt'] = df['Capital'].apply(lambda x: f"{x:,.0f}")
        df['LaiLo_Fmt'] = df['PnL'].apply(lambda x: f"{x:,.0f}")

        # Size Scaling
        max_cap = df['Capital'].max()
        if max_cap == 0: max_cap = 1
        df['Size_Scaled'] = 10 + (df['Capital'] / max_cap * 35)

        fig = px.scatter(
            df, x='Days', y='PnL', color='PnL',
            size='Size_Scaled', size_max=45,
            hover_name='Mã CK',
            hover_data={'Days': True, 'PnL': False, 'Size_Scaled': False, 'Vốn_Fmt': True, 'LaiLo_Fmt': True, 'Capital': False},
            color_continuous_scale=['#FF2B2B', '#F3F4F6', '#00CC96'],
            title="Ma Trận Kỷ Luật: Thời Gian vs Hiệu Quả"
        )

        fig.add_hline(y=0, line_dash="solid", line_color="black", opacity=0.3)
        avg_days = df['Days'].mean()
        if pd.notna(avg_days):
            fig.add_vline(x=avg_days, line_dash="dash", line_color="gray", annotation_text=f"TB: {avg_days:.1f} ngày")

        max_x, max_y, min_y = df['Days'].max(), df['PnL'].max(), df['PnL'].min()
        if max_x > 0:
            if max_y > 0: fig.add_annotation(x=max_x, y=max_y, text="💎 BẢN LĨNH", font=dict(color="green"), showarrow=False)
            if min_y < 0: fig.add_annotation(x=max_x, y=min_y, text="💀 CỐ CHẤP", font=dict(color="red"), showarrow=False)

        fig.update_traces(
            textposition='top center',
            hovertemplate="<b>%{hovertext}</b><br>⏱️ Giữ: %{x:.0f} ngày<br>💰 Lãi/Lỗ: %{customdata[4]} đ<br>💵 Vốn: %{customdata[3]} đ"
        )
        fig.update_layout(xaxis_title="Thời Gian Giữ (Ngày)", yaxis_title="Lãi/Lỗ (VND)", height=600, coloraxis_showscale=False)
        return fig
    except Exception as e:
        st.error(f"Lỗi vẽ biểu đồ: {e}")
        return None

# --- 3. CƯỜNG ĐỘ GIAO DỊCH vs HIỆU QUẢ ---
def draw_efficiency_vs_intensity(trade_log, closed_cycles=None):
    if not trade_log: return None
    try:
        df = pd.DataFrame(trade_log)
        if 'Ngày' not in df.columns and 'date' in df.columns: df['Ngày'] = df['date']
        df['Tháng'] = pd.to_datetime(df['Ngày']).dt.to_period('M').astype(str)
        
        df_buy = df[df['Loại'].isin(['MUA', 'BUY'])]
        intensity_buy = df_buy.groupby('Tháng').size().reset_index(name='Lệnh_Mua')
        
        df_sell = df[df['Loại'].isin(['BÁN', 'SELL'])]
        intensity_sell = df_sell.groupby('Tháng').size().reset_index(name='Lệnh_Bán')
        
        df['Lãi/Lỗ'] = pd.to_numeric(df['Lãi/Lỗ'], errors='coerce').fillna(0)
        efficiency = df.groupby('Tháng')['Lãi/Lỗ'].sum().reset_index(name='Lãi_Lỗ_Thực')

        df_merge = pd.merge(intensity_buy, intensity_sell, on='Tháng', how='outer')
        df_merge = pd.merge(df_merge, efficiency, on='Tháng', how='outer').fillna(0)
        df_merge = df_merge.sort_values('Tháng')
        df_merge = df_merge[(df_merge['Lệnh_Mua'] > 0) | (df_merge['Lệnh_Bán'] > 0) | (df_merge['Lãi_Lỗ_Thực'] != 0)]

        if df_merge.empty: return None

        fig = make_subplots(specs=[[{"secondary_y": True}]])

        fig.add_trace(go.Bar(x=df_merge['Tháng'], y=df_merge['Lệnh_Mua'], name="Lệnh Mua", marker_color='rgba(0, 204, 150, 0.4)'), secondary_y=False)
        fig.add_trace(go.Bar(x=df_merge['Tháng'], y=df_merge['Lệnh_Bán'], name="Lệnh Bán", marker_color='rgba(255, 43, 43, 0.4)'), secondary_y=False)
        
        line_colors = ['#00CC96' if x >= 0 else '#EF553B' for x in df_merge['Lãi_Lỗ_Thực']]
        fig.add_trace(go.Scatter(x=df_merge['Tháng'], y=df_merge['Lãi_Lỗ_Thực'], name="Lãi/Lỗ Thực Nhận", mode='lines+markers', line=dict(color='#3B82F6', width=2.5), marker=dict(size=8, color=line_colors)), secondary_y=True)

        suspicious = df_merge[(df_merge['Lệnh_Bán'] > 0) & (df_merge['Lãi_Lỗ_Thực'].abs() < 1000)]
        if not suspicious.empty:
            sus_months = ", ".join(suspicious['Tháng'].tolist())
            st.warning(f"⚠️ CẢNH BÁO DỮ LIỆU: Các tháng **{sus_months}** có lệnh BÁN nhưng Lãi/Lỗ ≈ 0.")

        fig.update_layout(title="Cường Độ vs Hiệu Quả (Realized PnL)", height=500, hovermode="x unified", legend=dict(orientation="h", y=-0.1), barmode='group')
        fig.update_yaxes(title_text="Số Lệnh", secondary_y=False, showgrid=False)
        fig.update_yaxes(title_text="Lãi/Lỗ (VND)", secondary_y=True, showgrid=True)
        return fig
    except Exception as e:
        st.error(f"Lỗi vẽ biểu đồ Cường độ: {e}")
        return None

# --- 4. [MỚI] PHÂN TÍCH CHUỖI THẮNG/THUA (STREAK ANALYZER) ---
def draw_streak_analysis(closed_cycles):
    """
    Vẽ biểu đồ diễn biến Lãi/Lỗ theo trình tự thời gian (Sequence)
    để soi Chuỗi Thắng/Thua liên tiếp.
    """
    if not closed_cycles: return None
    
    try:
        # 1. Sắp xếp dữ liệu theo ngày chốt lệnh
        df = pd.DataFrame(closed_cycles)
        # Khôi phục ngày kết thúc
        if 'Ngày Kết Thúc' not in df.columns:
            if 'end_date' in df.columns: df['Ngày Kết Thúc'] = df['end_date']
            else: df['Ngày Kết Thúc'] = pd.Timestamp.now()
            
        df['Date_Sort'] = pd.to_datetime(df['Ngày Kết Thúc'])
        df = df.sort_values('Date_Sort').reset_index(drop=True)
        
        # 2. Tính Lãi/Lỗ
        df['PnL'] = df.get('trading_pl', 0) + df.get('dividend_pl', 0)
        df['PnL'] = pd.to_numeric(df['PnL'], errors='coerce').fillna(0)
        
        # 3. Tính toán Chuỗi (Streak)
        streaks = []
        current_streak = 0
        
        for pnl in df['PnL']:
            if pnl > 0:
                current_streak = current_streak + 1 if current_streak > 0 else 1
            elif pnl < 0:
                current_streak = current_streak - 1 if current_streak < 0 else -1
            else:
                current_streak = 0 # Hòa vốn ngắt chuỗi
            streaks.append(current_streak)
            
        df['Streak_Count'] = streaks
        max_win_streak = df['Streak_Count'].max()
        max_loss_streak = df['Streak_Count'].min()

        # 4. Vẽ biểu đồ Sequence (Cột PnL theo thứ tự)
        colors = ['#00CC96' if x >= 0 else '#EF553B' for x in df['PnL']]
        
        fig = go.Figure()
        
        # Thêm đường nối mờ để thấy xu hướng
        fig.add_trace(go.Scatter(
            x=df.index, y=df['PnL'],
            mode='lines',
            line=dict(color='gray', width=1, dash='dot'),
            hoverinfo='skip'
        ))
        
        # Thêm cột PnL
        fig.add_trace(go.Bar(
            x=df.index, y=df['PnL'],
            marker_color=colors,
            text=df['Mã CK'],
            hovertemplate="<b>%{text}</b><br>Lần thứ: %{x}<br>Lãi/Lỗ: %{y:,.0f} đ<extra></extra>"
        ))

        # Hiển thị thông tin Streak
        st.info(f"""
        🔥 **Phân Tích Chuỗi Tâm Lý:**
        - Chuỗi Thắng dài nhất: **{max_win_streak}** lệnh liên tiếp.
        - Chuỗi Thua dài nhất: **{abs(max_loss_streak)}** lệnh liên tiếp.
        - *Lời khuyên:* Hãy kiểm tra xem sau chuỗi thắng/thua này, lệnh tiếp theo của bạn có bị "phá kỷ luật" (Volume to bất thường) không?
        """)

        fig.update_layout(
            title="Diễn Biến Kết Quả Giao Dịch (Theo Trình Tự)",
            xaxis_title="Thứ Tự Lệnh Bán (1 -> N)",
            yaxis_title="Lãi/Lỗ Thực Tế (VND)",
            height=500
        )
        
        return fig

    except Exception as e:
        st.error(f"Lỗi vẽ biểu đồ Chuỗi: {e}")
        return None