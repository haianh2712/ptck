# File: components/psychology_charts.py
# Updated: Chart 4 (Sync Date) & Chart 5 (Add ROI, Tooltip, Binary Color)

import plotly.express as px
import plotly.graph_objects as go
import pandas as pd
import streamlit as st
from datetime import datetime

# ==============================================================================
# PHẦN 0: HÀM TIỆN ÍCH (UTILITIES)
# ==============================================================================

def smart_get(data_dict, potential_keys, default_val=None):
    """Tìm giá trị trong dict với danh sách key ưu tiên."""
    for key in potential_keys:
        if key in data_dict:
            val = data_dict[key]
            return val if pd.notnull(val) else default_val
    return default_val

def find_col(df, candidates):
    """Tìm tên cột thực tế tồn tại trong DataFrame."""
    for col in candidates:
        if col in df.columns: return col
    return None

# ==============================================================================
# 1. BIỂU ĐỒ NHỊP TIM (TRADING TIMELINE)
# ==============================================================================
def draw_trading_timeline(trade_log):
    if not trade_log: return None
    try:
        df = pd.DataFrame(trade_log)
        
        # 1. Tìm cột Ngày
        date_col = find_col(df, ['Ngày', 'date', 'Date', 'time'])
        if not date_col: return None
        
        # Chuẩn hóa ngày
        df['date_norm'] = pd.to_datetime(df[date_col], dayfirst=True, errors='coerce')
        df = df.dropna(subset=['date_norm'])
        if df.empty: return None

        # 2. Tìm các cột dữ liệu khác
        code_col = find_col(df, ['Mã', 'Mã CK', 'symbol', 'ticker', 'code']) or 'Mã'
        type_col = find_col(df, ['Loại', 'type', 'side', 'action']) or 'Loại'
        sl_col = find_col(df, ['SL', 'vol', 'volume', 'qty'])
        
        # 3. Xử lý kích thước điểm
        if sl_col:
            df['Size'] = df[sl_col].apply(lambda x: max(float(x), 100) if pd.notnull(x) else 100)
        else:
            df['Size'] = 100

        # 4. Cấu hình màu sắc
        color_map = {
            'MUA': '#00CC96', 'Buy': '#00CC96',
            'BAN': '#EF553B', 'BÁN': '#EF553B', 'Sell': '#EF553B',
            'CO_TUC': '#636EFA', 'CỔ TỨC': '#636EFA',
            'PHÍ/THUẾ': '#FFA15A'
        }
        
        fig = px.scatter(
            df, x='date_norm', y=code_col, color=type_col,
            size="Size", size_max=20,
            color_discrete_map=color_map,
            title="Nhịp Tim Giao Dịch (Lịch Sử Mua/Bán)",
            hover_data={code_col: True, 'date_norm': True}
        )
        fig.update_layout(height=400, xaxis_title="Thời Gian", yaxis_title="Mã CP")
        return fig
    except Exception: return None

# ==============================================================================
# 2. REVIEW LỊCH SỬ (HISTORY MATRIX - CLOSED CYCLES)
# ==============================================================================
def draw_history_matrix(closed_cycles):
    if not closed_cycles: return None
    data_list = []
    
    keys_ticker = ['Mã CK', 'ticker', 'symbol', 'code']
    keys_days = ['Tuổi Vòng Đời', 'days_held', 'duration']
    keys_pnl = ['Lãi/Lỗ', 'pnl_value', 'profit', 'total_pnl']
    keys_invest = ['Tổng Vốn Mua', 'total_invest', 'cost', 'total_buy_val']

    for c in closed_cycles:
        try:
            ticker = str(smart_get(c, keys_ticker, 'Unknown'))
            days = int(smart_get(c, keys_days, 0))
            pnl = float(smart_get(c, keys_pnl, 0))
            invest = float(smart_get(c, keys_invest, 0))
            
            display_size = max(invest, 5_000_000)

            if invest > 0 or pnl != 0:
                data_list.append({
                    'Mã': ticker,
                    'Days': days,
                    'PnL': pnl,
                    'Vốn': display_size,
                    'Vốn Thực': invest,
                    'Màu': 'Lãi' if pnl > 0 else 'Lỗ'
                })
        except: continue
            
    if not data_list: return None
    df = pd.DataFrame(data_list)
    
    try:
        fig = px.scatter(
            df, x="Days", y="PnL", size="Vốn", color="Màu",
            text="Mã",
            color_discrete_map={'Lãi': '#00CC96', 'Lỗ': '#EF553B'},
            hover_name="Mã",
            hover_data={'Mã': False, 'Days': True, 'PnL': ':,.0f', 'Vốn Thực': ':,.0f', 'Vốn': False, 'Màu': False},
            title="1. Review Lịch Sử: Ma Trận Kỷ Luật",
            size_max=40
        )
        fig.update_traces(textposition='top center')
        fig.add_hline(y=0, line_color="gray", opacity=0.5)
        fig.add_vline(x=90, line_dash="dot", line_color="orange", annotation_text="3 Tháng")
        fig.update_layout(height=450, xaxis_title="Thời Gian Giữ (Ngày)", yaxis_title="Lãi/Lỗ Thực (VND)")
        return fig
    except: return None

# ==============================================================================
# 3. RA-ĐA RỦI RO (HOLDINGS - GOM NHÓM THEO MÃ)
# ==============================================================================
def draw_holding_risk_radar(df_inv):
    if df_inv is None or df_inv.empty: return None
    
    grouped_data = {}
    today = datetime.now()
    
    c_ticker = find_col(df_inv, ['Mã CK', 'symbol', 'ticker'])
    c_qty = find_col(df_inv, ['SL Tồn', 'vol', 'quantity'])
    c_pnl = find_col(df_inv, ['Lãi/Lỗ Tạm Tính', 'unrealized_pnl', 'pnl'])
    c_cost = find_col(df_inv, ['Giá Vốn ĐC', 'adj_cost', 'price'])
    c_date = find_col(df_inv, ['Ngày Mua', 'date', 'buy_date'])
    
    if not c_ticker or not c_qty: return None 

    for _, row in df_inv.iterrows():
        try:
            qty = float(row[c_qty]) if pd.notnull(row[c_qty]) else 0
            if qty <= 0: continue
            
            ticker = str(row[c_ticker])
            pnl = float(row[c_pnl]) if c_pnl and pd.notnull(row[c_pnl]) else 0
            cost = float(row[c_cost]) if c_cost and pd.notnull(row[c_cost]) else 0
            invest = cost * qty
            
            buy_date = None
            if c_date and pd.notnull(row[c_date]):
                buy_date = pd.to_datetime(row[c_date], dayfirst=True, errors='coerce')

            if ticker not in grouped_data:
                grouped_data[ticker] = {
                    'total_pnl': 0.0,
                    'total_invest': 0.0,
                    'oldest_date': buy_date
                }
            
            grouped_data[ticker]['total_pnl'] += pnl
            grouped_data[ticker]['total_invest'] += invest
            
            curr_oldest = grouped_data[ticker]['oldest_date']
            if buy_date:
                if curr_oldest is None or buy_date < curr_oldest:
                    grouped_data[ticker]['oldest_date'] = buy_date

        except: continue

    data_list = []
    for ticker, vals in grouped_data.items():
        days_held = 0
        if vals['oldest_date']:
            days_held = (today - vals['oldest_date']).days
        
        pnl = vals['total_pnl']
        invest = vals['total_invest']
        
        data_list.append({
            'Mã': ticker,
            'Days': max(days_held, 0),
            'PnL': pnl,
            'Vốn': max(invest, 5_000_000),
            'Vốn Thực': invest,
            'Trạng Thái': 'Đang Lãi' if pnl > 0 else 'Đang Lỗ'
        })

    if not data_list: return None
    df = pd.DataFrame(data_list)
    
    try:
        fig = px.scatter(
            df, x="Days", y="PnL", size="Vốn", color="Trạng Thái",
            text="Mã",
            color_discrete_map={'Đang Lãi': '#00CC96', 'Đang Lỗ': '#AB63FA'},
            hover_name="Mã",
            hover_data={'Mã': False, 'Days': True, 'PnL': ':,.0f', 'Vốn Thực': ':,.0f', 'Vốn': False, 'Trạng Thái': False},
            title="2. Ra-đa Rủi Ro: Tổng Hợp Theo Mã",
            size_max=60
        )
        fig.update_traces(textposition='top center')
        
        if not df.empty:
            max_days = df['Days'].max() + 30
            min_pnl = df['PnL'].min()
            if min_pnl < 0:
                bottom_y = min_pnl * 1.2 
                fig.add_shape(type="rect", x0=60, y0=0, x1=max(max_days, 90), y1=bottom_y, 
                              fillcolor="red", opacity=0.1, line_width=0)
                fig.add_annotation(x=max_days-10, y=bottom_y/2, text="CẮT NGAY!", 
                                   showarrow=False, font=dict(color="red", size=14, weight='bold'))

        fig.add_hline(y=0, line_color="gray")
        fig.update_layout(height=450, xaxis_title="Số Ngày Giữ (Lô Cũ Nhất)", yaxis_title="Tổng Lãi/Lỗ (VND)")
        return fig
    except: return None

# ==============================================================================
# 4. CƯỜNG ĐỘ VS HIỆU QUẢ (EFFICIENCY VS INTENSITY)
# ==============================================================================
def draw_efficiency_vs_intensity(trade_log, closed_cycles):
    if not closed_cycles or not trade_log: return None
    try:
        # 1. Closed Cycles DF
        df_cyc = pd.DataFrame(closed_cycles)
        end_key = find_col(df_cyc, ['end_date', 'Ngày Kết Thúc'])
        pnl_key = find_col(df_cyc, ['pnl_value', 'Lãi/Lỗ', 'Tổng Lãi Cycle'])
        if not end_key or not pnl_key: return None
        
        df_cyc['end_date_norm'] = pd.to_datetime(df_cyc[end_key], dayfirst=True, errors='coerce')
        df_cyc = df_cyc.dropna(subset=['end_date_norm'])
        df_cyc['Month'] = df_cyc['end_date_norm'].dt.to_period('M').astype(str)
        
        monthly_pnl = df_cyc.groupby('Month')[pnl_key].sum().reset_index()
        monthly_pnl.rename(columns={pnl_key: 'Monthly_PnL'}, inplace=True)

        # 2. Trade Log DF
        df_log = pd.DataFrame(trade_log)
        date_key = find_col(df_log, ['date', 'Ngày'])
        if not date_key: return None
        
        df_log['date_norm'] = pd.to_datetime(df_log[date_key], dayfirst=True, errors='coerce')
        df_log = df_log.dropna(subset=['date_norm'])
        df_log['Month'] = df_log['date_norm'].dt.to_period('M').astype(str)
        
        freq = df_log.groupby('Month').size().reset_index(name='Trade_Count')

        # 3. Merge Data (Full Outer)
        df_final = pd.merge(freq, monthly_pnl, on='Month', how='outer')
        df_final = df_final.sort_values('Month')
        df_final['Trade_Count'] = df_final['Trade_Count'].fillna(0)
        df_final['Monthly_PnL'] = df_final['Monthly_PnL'].fillna(0)
        df_final['CumPnL'] = df_final['Monthly_PnL'].cumsum()

        # 4. Draw
        fig = go.Figure()
        fig.add_trace(go.Bar(
            x=df_final['Month'], y=df_final['Trade_Count'], 
            name='Số Lệnh (Cường Độ)', marker_color='#d3d3d3', opacity=0.5, yaxis='y'
        ))
        fig.add_trace(go.Scatter(
            x=df_final['Month'], y=df_final['CumPnL'], 
            name='Lãi Tích Lũy (Hiệu Quả)', mode='lines+markers', 
            line=dict(color='#636EFA', width=3), yaxis='y2'
        ))

        fig.update_layout(
            title="Tương Quan: Cường Độ Giao Dịch vs Hiệu Quả Đầu Tư",
            xaxis_title="Thời Gian",
            yaxis=dict(title="Số Lệnh/Tháng", side="left", showgrid=False),
            yaxis2=dict(title="Tổng Lãi Thực (VND)", side="right", overlaying="y", showgrid=True),
            height=450,
            legend=dict(x=0, y=1.1, orientation="h"),
            hovermode="x unified"
        )
        return fig
    except: return None

# ==============================================================================
# 5. CHUỖI THẮNG THUA (STREAK ANALYSIS) - ĐÃ NÂNG CẤP
# ==============================================================================
def draw_streak_analysis(closed_cycles):
    """
    Vẽ biểu đồ các lệnh chốt gần đây.
    Nâng cấp: Hiển thị ROI%, Màu xanh/đỏ rõ ràng, Tooltip chi tiết.
    """
    if not closed_cycles: return None
    data_list = []
    
    # Define keys
    keys_ticker = ['Mã CK', 'ticker', 'symbol', 'code']
    keys_end = ['end_date', 'Ngày Kết Thúc', 'date']
    keys_pnl = ['pnl_value', 'Lãi/Lỗ', 'Tổng Lãi Cycle']
    keys_invest = ['total_invest', 'Tổng Vốn Mua', 'cost']
    keys_days = ['days_held', 'Tuổi Vòng Đời', 'duration']

    # 1. Trích xuất dữ liệu chuẩn
    for c in closed_cycles:
        try:
            ticker = str(smart_get(c, keys_ticker, 'Unknown'))
            end_date = smart_get(c, keys_end)
            pnl = float(smart_get(c, keys_pnl, 0))
            invest = float(smart_get(c, keys_invest, 0))
            days = int(smart_get(c, keys_days, 0))
            
            # Tính ROI % (Tránh chia cho 0)
            roi = (pnl / invest * 100) if invest > 0 else 0
            
            # Phân loại trạng thái để tô màu nhị phân
            status = 'Thắng' if pnl > 0 else 'Thua'
            
            if end_date:
                data_list.append({
                    'Mã': ticker,
                    'Ngày Chốt': end_date,
                    'PnL': pnl,
                    'ROI (%)': roi,
                    'Số Ngày Giữ': days,
                    'Kết Quả': status
                })
        except: continue
            
    if not data_list: return None
    
    df = pd.DataFrame(data_list)
    # Convert ngày để sort
    df['date_norm'] = pd.to_datetime(df['Ngày Chốt'], dayfirst=True, errors='coerce')
    df = df.sort_values('date_norm')
    
    try:
        # 2. Vẽ biểu đồ Bar với màu sắc dứt khoát
        fig = px.bar(
            df, 
            x='date_norm', 
            y='PnL', 
            color='Kết Quả', # Dùng cột này để phân màu
            color_discrete_map={'Thắng': '#00CC96', 'Thua': '#EF553B'}, # Xanh / Đỏ
            title="Chuỗi Thắng/Thua & Chất Lượng Lệnh (ROI)",
            # Tùy biến Tooltip (Hover)
            hover_data={
                'date_norm': False, # Ẩn ngày định dạng gốc
                'Mã': True,
                'PnL': ':,.0f',     # Định dạng tiền
                'ROI (%)': ':.2f',  # Định dạng % (2 số lẻ)
                'Số Ngày Giữ': True,
                'Kết Quả': False
            }
        )
        
        fig.update_layout(
            height=350, 
            xaxis_title="Thời Gian Chốt Lệnh",
            yaxis_title="Lãi/Lỗ (VND)",
            hovermode="x unified" # Giúp so sánh dễ hơn
        )
        return fig
    except Exception as e: 
        return None