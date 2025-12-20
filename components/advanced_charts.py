# File: components/advanced_charts.py
import plotly.express as px
import plotly.graph_objects as go
import pandas as pd
import numpy as np
import streamlit as st

# --- HÀM TIỆN ÍCH TÌM CỘT THÔNG MINH ---
def find_col(df, candidates):
    """
    Tìm tên cột trong DataFrame (Không phân biệt hoa thường).
    Ưu tiên 1: Khớp chính xác.
    Ưu tiên 2: Chứa từ khóa.
    """
    if df is None or df.empty: return None
    
    cols = df.columns.tolist()
    cols_lower = [c.lower() for c in cols]
    
    # 1. Tìm khớp chính xác
    for cand in candidates:
        cand_lower = cand.lower()
        if cand_lower in cols_lower:
            return cols[cols_lower.index(cand_lower)]
    
    # 2. Tìm chứa từ khóa (Partial match)
    for cand in candidates:
        cand_lower = cand.lower()
        for i, col_lower in enumerate(cols_lower):
            if cand_lower in col_lower:
                return cols[i]
    return None

# ==============================================================================
# 1. BẢN ĐỒ NHIỆT HIỆU QUẢ (MONTHLY SEASONALITY)
# ==============================================================================
def draw_pnl_heatmap(trade_log):
    """
    Vẽ Heatmap Lãi/Lỗ theo Tháng/Năm.
    Ý nghĩa: Giúp nhận diện "Mùa gặt" (Tháng thường lãi) và "Mùa đói" (Tháng thường lỗ).
    """
    if not trade_log: return None
    try:
        df = pd.DataFrame(trade_log)
        
        # Tìm cột (Khớp với trade_log trong engine.py)
        date_col = find_col(df, ['Ngày', 'date', 'time'])
        pnl_col = find_col(df, ['Lãi/Lỗ', 'pnl', 'profit', 'amount'])
        
        if not date_col or not pnl_col: return None
        
        # Xử lý dữ liệu
        df['date_norm'] = pd.to_datetime(df[date_col], dayfirst=True, errors='coerce')
        df = df.dropna(subset=['date_norm'])
        
        # Chỉ lấy các dòng có phát sinh lãi/lỗ thực (loại bỏ các dòng chỉ có Mua)
        df = df[df[pnl_col] != 0]
        
        if df.empty: return None

        # Pivot Table: Năm (Hàng) x Tháng (Cột)
        df['Year'] = df['date_norm'].dt.year
        df['Month'] = df['date_norm'].dt.month
        pivot = df.groupby(['Year', 'Month'])[pnl_col].sum().unstack(fill_value=0)
        
        # Fill đủ 12 tháng để biểu đồ đẹp
        for m in range(1, 13):
            if m not in pivot.columns: pivot[m] = 0
        pivot = pivot[sorted(pivot.columns)]
        pivot = pivot.sort_index(ascending=False) # Năm mới nhất lên trên

        # Chuẩn bị dữ liệu vẽ
        z = pivot.values
        x = [f"Tháng {m}" for m in pivot.columns]
        y = pivot.index.astype(str)
        
        # Format hiển thị rút gọn (cho ô bé)
        def format_val(v):
            if v == 0: return "" # Ô trống cho gọn
            if abs(v) >= 1e9: return f"{v/1e9:.1f}B"
            if abs(v) >= 1e6: return f"{v/1e6:.1f}M"
            return f"{v/1e3:.0f}k"
            
        # Format hiển thị đầy đủ (cho Tooltip)
        def format_full(v): return f"{v:,.0f} đ"

        text_display = [[format_val(v) for v in row] for row in z]
        text_hover = [[format_full(v) for v in row] for row in z]

        # Vẽ biểu đồ
        fig = go.Figure(data=go.Heatmap(
            z=z, x=x, y=y,
            text=text_display,
            customdata=text_hover, # Dữ liệu ẩn dùng cho tooltip
            texttemplate="%{text}", # Hiển thị text rút gọn trên ô
            
            # [CHÚ THÍCH CHI TIẾT]
            hovertemplate=(
                "<b>📅 Thời gian: %{x}/%{y}</b><br>" +
                "💰 Lợi nhuận: <b>%{customdata}</b><br>" +
                "<i>(Xanh = Lãi, Đỏ = Lỗ)</i>" +
                "<extra></extra>"
            ),
            
            colorscale='RdYlGn', # Red-Yellow-Green
            zmid=0, # Căn giữa tại 0 để phân biệt rõ Lãi/Lỗ
            showscale=True,
            colorbar=dict(title="Lãi/Lỗ (VND)")
        ))
        
        fig.update_layout(
            title="Bản Đồ Hiệu Quả Theo Tháng (Seasonality)",
            height=300 + (len(y) * 40), # Chiều cao tự động
            margin=dict(t=40, b=20, l=0, r=0),
            xaxis_title="",
            yaxis_title=""
        )
        return fig
    except: return None

# ==============================================================================
# 2. BIỂU ĐỒ SỤT GIẢM (UNDERWATER DRAWDOWN)
# ==============================================================================
def draw_realized_drawdown(df_history):
    """
    Vẽ biểu đồ vùng ngập nước (Underwater).
    Ý nghĩa: Đo lường rủi ro. Cho biết tài khoản đang 'bốc hơi' bao nhiêu % so với đỉnh cao nhất lịch sử.
    """
    if df_history is None or df_history.empty: return None, 0, 0
    
    try:
        # 1. Tìm cột (Khớp với TimeMachine: 'Ngày', 'Tổng Tài Sản (NAV)')
        date_col = find_col(df_history, ['Ngày', 'date', 'time'])
        nav_col = find_col(df_history, [
            'Tổng Tài Sản (NAV)', # Key chính xác từ TimeMachine
            'Tổng Tài Sản', 'nav', 'total_nav', 'equity'
        ])
        
        if not date_col or not nav_col: 
            return None, 0, 0
        
        # 2. Xử lý dữ liệu
        df = df_history.copy()
        df[date_col] = pd.to_datetime(df[date_col], errors='coerce')
        df = df.dropna(subset=[date_col]).sort_values(date_col)
        df[nav_col] = pd.to_numeric(df[nav_col], errors='coerce').fillna(0)
        
        if df.empty: return None, 0, 0
        
        # 3. Tính toán Drawdown
        # Peak: Đỉnh cao nhất tính đến thời điểm t
        df['Peak'] = df[nav_col].cummax()
        
        # Drawdown: Chênh lệch so với đỉnh
        # Xử lý chia cho 0: Nếu Peak=0 (tài khoản chưa nạp tiền), drawdown = 0
        df['DrawdownPct'] = np.where(
            df['Peak'] > 0, 
            ((df[nav_col] - df['Peak']) / df['Peak']) * 100, 
            0
        )
        
        # Chỉ số
        current_dd = df['DrawdownPct'].iloc[-1]
        max_dd = df['DrawdownPct'].min()

        # 4. Vẽ biểu đồ
        fig = go.Figure()
        
        # Vẽ vùng sụt giảm (Màu đỏ nhạt)
        fig.add_trace(go.Scatter(
            x=df[date_col], 
            y=df['DrawdownPct'],
            fill='tozeroy', # Tô màu từ đường biểu diễn đến trục 0
            mode='lines',
            line=dict(color='#EF553B', width=1.5),
            fillcolor='rgba(239, 85, 59, 0.2)',
            name='Sụt Giảm',
            
            # [CHÚ THÍCH CHI TIẾT]
            hovertemplate=(
                "<b>📅 Ngày: %{x|%d/%m/%Y}</b><br>" +
                "📉 Đang âm: <b>%{y:.2f}%</b> so với đỉnh<br>" +
                "<i>(Càng sâu càng nguy hiểm)</i>" +
                "<extra></extra>"
            )
        ))
        
        # Đánh dấu Đáy Lịch Sử
        min_idx = df['DrawdownPct'].idxmin()
        if pd.notnull(min_idx):
            min_date = df.loc[min_idx, date_col]
            
            fig.add_annotation(
                x=min_date, y=max_dd,
                text=f"Đáy Sâu Nhất: {max_dd:.1f}%",
                showarrow=True, arrowhead=1, ax=0, ay=40,
                arrowcolor="#EF553B",
                font=dict(color="#EF553B", weight="bold")
            )

        fig.update_layout(
            title="Biểu Đồ Sụt Giảm Vốn (Underwater)",
            xaxis_title="Thời Gian",
            yaxis_title="Sụt Giảm Từ Đỉnh (%)",
            height=350,
            showlegend=False,
            margin=dict(t=40, b=20, l=0, r=0),
            hovermode="x unified" # Hiển thị đường gióng dọc để dễ so sánh
        )
        
        # Trả về: Figure, MaxDD (dương), CurrentDD (dương) để hiển thị KPI
        return fig, abs(max_dd), abs(current_dd)

    except Exception as e:
        return None, 0, 0