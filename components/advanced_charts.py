# File: components/advanced_charts.py
import plotly.graph_objects as go
import plotly.express as px
import pandas as pd
import streamlit as st

# --- 1. BIỂU ĐỒ SỤT GIẢM VỐN THỰC (REALIZED DRAWDOWN) ---
def draw_realized_drawdown(history_df):
    """
    Vẽ biểu đồ mức độ sụt giảm của Tài sản ròng (NAV) so với đỉnh cao nhất trong quá khứ.
    Lưu ý: Đây là sụt giảm THỰC TẾ (do cắt lỗ hoặc rút tiền), không phải sụt giảm tạm thời do thị trường.
    """
    if history_df is None or history_df.empty:
        return None
    
    try:
        df = history_df.copy()
        
        # Đảm bảo dữ liệu được sắp xếp theo thời gian
        df = df.sort_values('Ngày')
        
        # 1. Tính đỉnh cao nhất tích lũy (Cumulative Max)
        df['Peak'] = df['Tổng Tài Sản (NAV)'].cummax()
        
        # 2. Tính Drawdown (%)
        # Công thức: (NAV hiện tại - Đỉnh cao nhất) / Đỉnh cao nhất
        df['Drawdown'] = (df['Tổng Tài Sản (NAV)'] - df['Peak']) / df['Peak'] * 100
        
        # Tìm mức sụt giảm sâu nhất (Max Drawdown)
        max_dd = df['Drawdown'].min()
        current_dd = df['Drawdown'].iloc[-1]

        # 3. Vẽ biểu đồ vùng (Area Chart)
        fig = go.Figure()
        
        fig.add_trace(go.Scatter(
            x=df['Ngày'], 
            y=df['Drawdown'],
            mode='lines',
            fill='tozeroy', # Tô màu vùng từ đường biểu đồ tới trục 0
            name='Sụt Giảm (%)',
            line=dict(color='#EF553B', width=1.5), # Màu đỏ cam cảnh báo
            fillcolor='rgba(239, 85, 59, 0.2)',    # Màu nền đỏ nhạt
            hovertemplate="Ngày: %{x}<br>Sụt giảm: %{y:.2f}%<extra></extra>"
        ))

        fig.update_layout(
            title=f"📉 Sụt Giảm Vốn Thực (Max Drawdown: {max_dd:.2f}%)",
            xaxis_title="",
            yaxis_title="Mức Sụt Giảm Từ Đỉnh (%)",
            height=400,
            hovermode="x unified"
        )
        
        # Format trục Y thêm dấu %
        fig.update_yaxes(ticksuffix="%")
        
        return fig, max_dd, current_dd

    except Exception as e:
        st.error(f"Lỗi vẽ Drawdown: {e}")
        return None, 0, 0

# --- 2. BẢN ĐỒ NHIỆT HIỆU QUẢ (TRADING HEATMAP) ---
def draw_pnl_heatmap(trade_log):
    """
    Vẽ biểu đồ phân bố Lãi/Lỗ theo thời gian để soi thói quen/phong độ.
    Dạng: Scatter Plot theo dòng thời gian, màu sắc thể hiện Lãi/Lỗ.
    """
    if not trade_log: return None
    
    try:
        df = pd.DataFrame(trade_log)
        
        # 1. Chuẩn hóa dữ liệu
        col_map = {'date': 'Ngày', 'Lãi/Lỗ': 'PnL'}
        for k, v in col_map.items():
            if k in df.columns: df[v] = df[k]
            
        # Chỉ lấy các lệnh có phát sinh Lãi/Lỗ thực (Bán, Cổ tức)
        # Bỏ qua các dòng Lãi/Lỗ = 0 (Lệnh Mua)
        df = df[df['Lãi/Lỗ'] != 0].copy()
        
        if df.empty: return None
        
        df['Ngày'] = pd.to_datetime(df['Ngày'])
        df['Tháng'] = df['Ngày'].dt.strftime('%Y-%m')
        
        # 2. Vẽ biểu đồ
        # Xanh = Lãi, Đỏ = Lỗ
        # Kích thước chấm = Độ lớn của tiền (càng to càng rõ)
        
        fig = px.scatter(
            df,
            x="Ngày",
            y="Lãi/Lỗ",
            color="Lãi/Lỗ",
            size=df['Lãi/Lỗ'].abs(), # Kích thước theo giá trị tuyệt đối
            size_max=30,             # Giới hạn kích thước bong bóng
            hover_data={'Ngày': True, 'Lãi/Lỗ': True, 'Mã': True, 'Loại': True},
            color_continuous_scale=['#FF2B2B', '#F3F4F6', '#00CC96'], # Đỏ - Xám - Xanh
            title="📅 Bản Đồ Nhiệt: Lịch Sử Chốt Lời & Cắt Lỗ"
        )
        
        fig.update_layout(
            height=450,
            xaxis_title="Thời Gian",
            yaxis_title="Số Tiền (VND)",
            coloraxis_showscale=False # Ẩn thanh màu cho gọn
        )
        
        # Thêm đường tham chiếu 0
        fig.add_hline(y=0, line_dash="solid", line_color="gray", opacity=0.5)
        
        return fig

    except Exception as e:
        st.error(f"Lỗi vẽ Heatmap: {e}")
        return None