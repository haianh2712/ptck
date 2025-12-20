# File: components/chart_heatmap.py
import plotly.graph_objects as go
import pandas as pd
import numpy as np

def _find_col(df, candidates):
    """Tìm tên cột bất kể hoa thường (Copy local để file độc lập)."""
    if df is None or df.empty: return None
    cols = df.columns.tolist()
    cols_lower = [c.lower() for c in cols]
    for cand in candidates:
        cand_lower = cand.lower()
        if cand_lower in cols_lower:
            return cols[cols_lower.index(cand_lower)]
    return None

def plot(trade_log):
    """
    Vẽ Heatmap Lãi/Lỗ theo Tháng & Năm.
    Input: Trade Log (Danh sách giao dịch).
    """
    if not trade_log: return None
    try:
        df = pd.DataFrame(trade_log)
        
        # 1. Tìm cột
        date_col = _find_col(df, ['Ngày', 'date', 'time'])
        pnl_col = _find_col(df, ['Lãi/Lỗ', 'pnl', 'profit', 'amount'])
        
        if not date_col or not pnl_col: return None
        
        # 2. Xử lý dữ liệu
        df['date_norm'] = pd.to_datetime(df[date_col], dayfirst=True, errors='coerce')
        df = df.dropna(subset=['date_norm'])
        
        # Chỉ lấy các dòng có PnL (Bán, Cổ tức, Phí)
        df = df[df[pnl_col] != 0]
        
        if df.empty: return None

        # 3. Pivot Table
        df['Year'] = df['date_norm'].dt.year
        df['Month'] = df['date_norm'].dt.month
        pivot = df.groupby(['Year', 'Month'])[pnl_col].sum().unstack(fill_value=0)
        
        # Fill đủ 12 tháng
        for m in range(1, 13):
            if m not in pivot.columns: pivot[m] = 0
        pivot = pivot[sorted(pivot.columns)]
        pivot = pivot.sort_index(ascending=False) # Năm mới nhất lên đầu

        # 4. Chuẩn bị vẽ
        z = pivot.values
        x = [f"T{m}" for m in pivot.columns]
        y = pivot.index.astype(str)
        
        # Hàm format số
        def format_val(v):
            if v == 0: return ""
            if abs(v) >= 1e9: return f"{v/1e9:.1f}B"
            if abs(v) >= 1e6: return f"{v/1e6:.1f}M"
            return f"{v/1e3:.0f}k"
            
        def format_full(v): return f"{v:,.0f} đ"

        text_display = [[format_val(v) for v in row] for row in z]
        text_hover = [[format_full(v) for v in row] for row in z]

        # 5. Vẽ Heatmap
        fig = go.Figure(data=go.Heatmap(
            z=z, x=x, y=y,
            text=text_display,
            customdata=text_hover,
            texttemplate="%{text}",
            # Tooltip tiếng Việt
            hovertemplate="<b>📅 %{x}/%{y}</b><br>💰 KQ: %{customdata}<extra></extra>",
            colorscale='RdYlGn', 
            zmid=0, 
            showscale=True,
            colorbar=dict(title="Lãi/Lỗ")
        ))
        
        fig.update_layout(
            title="Bản Đồ Hiệu Quả (Seasonality)",
            height=300 + (len(y) * 40),
            margin=dict(t=40, b=20, l=0, r=0),
            xaxis_title="", yaxis_title=""
        )
        return fig

    except Exception:
        return None