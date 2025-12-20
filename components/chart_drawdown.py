# File: components/chart_drawdown.py
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import pandas as pd
import numpy as np

# --- HÀM HỖ TRỢ NỘI BỘ ---
def _find_col(df, candidates):
    """Tìm tên cột bất kể hoa thường."""
    if df is None or df.empty: return None
    cols = df.columns.tolist()
    cols_lower = [c.lower() for c in cols]
    for cand in candidates:
        cand_lower = cand.lower()
        if cand_lower in cols_lower:
            return cols[cols_lower.index(cand_lower)]
    # Tìm gần đúng
    for cand in candidates:
        cand_lower = cand.lower()
        for i, col_lower in enumerate(cols_lower):
            if cand_lower in col_lower:
                return cols[i]
    return None

def plot(df_history):
    """
    Vẽ biểu đồ kết hợp: Tăng trưởng NAV (Trên) & Sụt giảm (Dưới).
    Input: DataFrame lịch sử từ TimeMachine.
    Output: Figure, MaxDrawdown, CurrentDrawdown.
    """
    if df_history is None or df_history.empty:
        return None, 0, 0
    
    try:
        # 1. TÌM CỘT DỮ LIỆU
        # Tìm cột Ngày
        date_col = _find_col(df_history, ['Ngày', 'date', 'time'])
        # Tìm cột NAV (Thử nhiều tên để bắt dính)
        nav_col = _find_col(df_history, ['Tổng Tài Sản (NAV)', 'Tổng Tài Sản', 'nav', 'total_nav', 'equity'])
        
        if not date_col or not nav_col:
            return None, 0, 0
        
        # 2. CHUẨN HÓA DỮ LIỆU
        df = df_history.copy()
        df[date_col] = pd.to_datetime(df[date_col], errors='coerce')
        df = df.dropna(subset=[date_col]).sort_values(date_col)
        df[nav_col] = pd.to_numeric(df[nav_col], errors='coerce').fillna(0)
        
        if df.empty: return None, 0, 0
        
        # 3. TÍNH TOÁN CÁC CHỈ SỐ
        # Đỉnh cao nhất tính đến hiện tại (High Water Mark)
        df['Peak'] = df[nav_col].cummax()
        # Tránh lỗi chia cho 0
        df['Peak'] = df['Peak'].replace(0, 1) 
        
        # % Sụt giảm từ đỉnh
        df['DrawdownPct'] = ((df[nav_col] - df['Peak']) / df['Peak']) * 100
        
        # Lấy chỉ số báo cáo
        current_dd = df['DrawdownPct'].iloc[-1]
        max_dd = df['DrawdownPct'].min() # Số âm (ví dụ -15%)

        # 4. VẼ BIỂU ĐỒ (2 TẦNG)
        fig = make_subplots(
            rows=2, cols=1, 
            shared_xaxes=True,      # Chung trục thời gian
            vertical_spacing=0.05,  # Khoảng cách giữa 2 biểu đồ
            row_heights=[0.7, 0.3], # Tỷ lệ: NAV 70% - Drawdown 30%
            subplot_titles=("📈 Tăng Trưởng Tài Sản (NAV)", "📉 Mức Sụt Giảm (Drawdown)")
        )

        # --- TẦNG 1: NAV (EQUITY CURVE) ---
        fig.add_trace(go.Scatter(
            x=df[date_col], y=df[nav_col],
            mode='lines',
            name='Tài Sản (NAV)',
            line=dict(color='#00CC96', width=2),
            hovertemplate="<b>📅 %{x|%d/%m/%Y}</b><br>💰 NAV: <b>%{y:,.0f} đ</b><extra></extra>"
        ), row=1, col=1)

        # Vẽ đường đỉnh (High Water Mark) mờ mờ để tham chiếu
        fig.add_trace(go.Scatter(
            x=df[date_col], y=df['Peak'],
            mode='lines',
            name='Đỉnh Cũ',
            line=dict(color='gray', width=1, dash='dot'),
            hoverinfo='skip' # Không hiện tooltip cho đường này đỡ rối
        ), row=1, col=1)

        # --- TẦNG 2: DRAWDOWN (UNDERWATER) ---
        fig.add_trace(go.Scatter(
            x=df[date_col], y=df['DrawdownPct'],
            mode='lines',
            fill='tozeroy', # Tô màu vùng dưới
            name='Sụt Giảm',
            line=dict(color='#EF553B', width=1),
            fillcolor='rgba(239, 85, 59, 0.2)', # Màu đỏ nhạt
            hovertemplate="<b>📅 %{x|%d/%m/%Y}</b><br>📉 Âm: <b>%{y:.2f}%</b> từ đỉnh<extra></extra>"
        ), row=2, col=1)

        # Đánh dấu Đáy Sâu Nhất (Max Drawdown)
        min_idx = df['DrawdownPct'].idxmin()
        if pd.notnull(min_idx):
            min_date = df.loc[min_idx, date_col]
            fig.add_annotation(
                x=min_date, y=max_dd,
                text=f"Đáy: {max_dd:.1f}%",
                showarrow=True, arrowhead=1, ax=0, ay=30,
                font=dict(color="#EF553B", weight="bold"),
                row=2, col=1
            )

        # 5. TINH CHỈNH GIAO DIỆN
        fig.update_layout(
            height=550, # Chiều cao tổng thể
            showlegend=False,
            margin=dict(t=30, b=20, l=10, r=10),
            hovermode="x unified" # Hiển thị đường gióng dọc để so sánh trên/dưới
        )
        
        # Định dạng trục Y
        fig.update_yaxes(title_text="VND", tickformat=".2s", row=1, col=1)
        fig.update_yaxes(title_text="%", row=2, col=1)

        return fig, abs(max_dd), abs(current_dd)

    except Exception as e:
        # print(f"Lỗi vẽ Drawdown: {e}")
        return None, 0, 0