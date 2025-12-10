import streamlit as st
import pandas as pd
import re
from collections import deque
import io
from datetime import datetime
import plotly.express as px
import plotly.graph_objects as go

# --- CẤU HÌNH TRANG WEB ---
st.set_page_config(
    page_title="Dashboard Đầu Tư VPS Pro",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded"
)

# --- 1. CORE LOGIC (GIỮ NGUYÊN) ---

def clean_number(val):
    if pd.isna(val) or val == '': return 0.0
    try:
        return float(str(val).replace(',', '').replace(' ', '').strip())
    except ValueError: return 0.0

def find_header_index(df, keywords):
    for idx, row in df.iterrows():
        row_str = " ".join(row.astype(str).str.lower().fillna('').values)
        if sum(1 for k in keywords if k in row_str) >= 2: return idx
    return 0

# --- HÀM ĐỊNH DẠNG CHUẨN VIỆT NAM ---
def fmt_vnd(x):
    """Định dạng tiền tệ: 1.000.000"""
    if pd.isna(x): return ""
    return "{:,.0f}".format(x).replace(",", ".")

def fmt_num(x):
    """Định dạng số lượng: 1.000"""
    if pd.isna(x): return ""
    return "{:,.0f}".format(x).replace(",", ".")

def fmt_float(x):
    """Định dạng số thập phân: 1,5"""
    if pd.isna(x): return ""
    return "{:,.2f}".format(x).replace(".", ",")

def fmt_pct(x):
    """Định dạng phần trăm: 10,50%"""
    if pd.isna(x): return ""
    return "{:,.2f}%".format(x).replace(".", ",")

class PortfolioEngine:
    def __init__(self):
        self.data = {} 
        self.today = pd.Timestamp.now().normalize()

    def get_ticker_state(self, symbol):
        if symbol not in self.data:
            self.data[symbol] = {
                'inventory': deque(),       
                'closed_cycles': [],        
                'current_cycle': None,      
                'total_sold_vol': 0,
                'total_realized_pl': 0,
                'weighted_sold_days': 0,    
                'total_invested_capital': 0 
            }
        return self.data[symbol]

    def process_transaction(self, date_obj, date_str, symbol, action, volume, price, fee, dividend_val=0):
        state = self.get_ticker_state(symbol)
        inv = state['inventory']

        if action == 'BUY':
            cost_val = (price * volume) + fee
            unit_cost = cost_val / volume
            
            if state['current_cycle'] is None:
                state['current_cycle'] = {
                    'start_date': date_obj, 'total_buy_val': 0, 'total_buy_vol': 0,
                    'total_sell_val': 0, 'total_sell_vol': 0, 'realized_pl_cycle': 0, 'status': 'Open'
                }
            cyc = state['current_cycle']
            cyc['total_buy_val'] += cost_val
            cyc['total_buy_vol'] += volume
            state['total_invested_capital'] += cost_val
            inv.append({'date_obj': date_obj, 'date_str': date_str, 'vol': volume, 'cost': unit_cost})

        elif action == 'SELL':
            net_revenue = (price * volume) - fee
            qty_needed = volume
            cost_of_goods = 0
            
            while qty_needed > 0 and inv:
                batch = inv[0]
                hold_days = (date_obj - batch['date_obj']).days
                if batch['vol'] > qty_needed:
                    cogs_part = qty_needed * batch['cost']
                    cost_of_goods += cogs_part
                    state['weighted_sold_days'] += hold_days * qty_needed
                    batch['vol'] -= qty_needed
                    qty_needed = 0
                else:
                    cogs_part = batch['vol'] * batch['cost']
                    cost_of_goods += cogs_part
                    state['weighted_sold_days'] += hold_days * batch['vol']
                    qty_needed -= batch['vol']
                    inv.popleft()

            realized_pl = net_revenue - cost_of_goods
            state['total_sold_vol'] += volume
            state['total_realized_pl'] += realized_pl
            
            if state['current_cycle']:
                cyc = state['current_cycle']
                cyc['total_sell_val'] += net_revenue
                cyc['total_sell_vol'] += volume
                cyc['realized_pl_cycle'] += realized_pl
                if sum(b['vol'] for b in inv) <= 0.001:
                    cyc['end_date'] = date_obj
                    cyc['status'] = 'Closed'
                    state['closed_cycles'].append(cyc)
                    state['current_cycle'] = None

        elif action == 'DIVIDEND':
            curr_vol = sum(b['vol'] for b in inv)
            if curr_vol > 0:
                reduction = dividend_val / curr_vol
                for batch in inv: batch['cost'] -= reduction
            if state['current_cycle']:
                 state['current_cycle']['total_buy_val'] -= dividend_val

    def generate_reports(self):
        report_summary, report_inventory, report_cycles, report_warnings = [], [], [], []

        for sym, state in self.data.items():
            inv = state['inventory']
            current_vol = sum(b['vol'] for b in inv)
            current_val = sum(b['vol'] * b['cost'] for b in inv)
            
            avg_holding_days_held = 0
            if current_vol > 0:
                total_days_vol = sum(((self.today - b['date_obj']).days) * b['vol'] for b in inv)
                avg_holding_days_held = total_days_vol / current_vol

            avg_holding_days_sold = 0
            if state['total_sold_vol'] > 0:
                avg_holding_days_sold = state['weighted_sold_days'] / state['total_sold_vol']

            roi_pct = (state['total_realized_pl'] / state['total_invested_capital'] * 100) if state['total_invested_capital'] > 0 else 0

            report_summary.append({
                'Mã CK': sym, 'Tổng SL Đã Bán': state['total_sold_vol'], 'Lãi/Lỗ Đã Chốt': state['total_realized_pl'],
                '% Hiệu Suất Tổng': roi_pct, 'Ngày Giữ TB (Đã Bán)': avg_holding_days_sold,
                'SL Đang Giữ': current_vol, 'Vốn Đang Giữ': current_val,
                'Tuổi Kho TB (Đang Giữ)': avg_holding_days_held, 'Tổng Vốn Đã Rót': state['total_invested_capital']
            })

            for b in inv:
                report_inventory.append({
                    'Mã CK': sym, 'Ngày Mua': b['date_str'], 'SL Tồn': b['vol'],
                    'Giá Vốn': b['cost'], 'Ngày Giữ': (self.today - b['date_obj']).days
                })

            all_cycles = state['closed_cycles'] + ([state['current_cycle']] if state['current_cycle'] else [])
            for cyc in all_cycles:
                net_pl = cyc['realized_pl_cycle']
                invested = cyc['total_buy_val']
                roi_cyc = (net_pl / invested * 100) if invested > 0 else 0
                start_d = cyc['start_date'].strftime('%d/%m/%Y')
                end_d = cyc['end_date'].strftime('%d/%m/%Y') if 'end_date' in cyc else 'Đang nắm giữ'
                
                report_cycles.append({
                    'Mã CK': sym, 'Ngày Bắt Đầu': start_d, 'Ngày Kết Thúc': end_d,
                    'Tổng Vốn Mua': invested, 'Tổng Tiền Bán': cyc['total_sell_val'],
                    'Lãi/Lỗ Thực': net_pl, '% Hiệu Suất Cycle': roi_cyc, 'Trạng Thái': cyc['status']
                })
            
            if current_vol > 0 and avg_holding_days_held > 90:
                report_warnings.append({'Mã CK': sym, 'Vốn Kẹp': current_val, 'Tuổi Kho TB': avg_holding_days_held, 'Cảnh Báo': 'Kẹp hàng > 90 ngày'})

        return (pd.DataFrame(report_summary), pd.DataFrame(report_cycles), 
                pd.DataFrame(report_inventory), pd.DataFrame(report_warnings))

# --- 2. XỬ LÝ FILE ---

@st.cache_data(show_spinner=False)
def process_uploaded_file(uploaded_file):
    engine = PortfolioEngine()
    total_deposit = 0.0 

    try:
        xls = pd.ExcelFile(uploaded_file)
        sheet_names = [s.lower() for s in xls.sheet_names]
        
        sh_ck_real = next((xls.sheet_names[i] for i, s in enumerate(sheet_names) if ('ck' in s or 'khớp' in s or 'lệnh' in s) and 'tiền' not in s), None)
        sh_tien_real = next((xls.sheet_names[i] for i, s in enumerate(sheet_names) if ('tiền' in s or 'cash' in s)), None)

        if not sh_ck_real or not sh_tien_real:
            if len(xls.sheet_names) >= 2: sh_tien_real, sh_ck_real = xls.sheet_names[0], xls.sheet_names[1]
            else: return None, None, "Không tìm thấy sheet Lệnh/Tiền hợp lệ."

        raw_ck = pd.read_excel(xls, sheet_name=sh_ck_real, header=None, nrows=20)
        idx_ck = find_header_index(raw_ck, ['mã ck', 'phát sinh', 'nội dung'])
        df_ck = pd.read_excel(xls, sheet_name=sh_ck_real, header=idx_ck)
        
        raw_tien = pd.read_excel(xls, sheet_name=sh_tien_real, header=None, nrows=20)
        idx_tien = find_header_index(raw_tien, ['ngày', 'số dư', 'phát sinh'])
        df_tien = pd.read_excel(xls, sheet_name=sh_tien_real, header=idx_tien)

        df_ck.columns = [str(c).strip().lower() for c in df_ck.columns]
        df_tien.columns = [str(c).strip().lower() for c in df_tien.columns]
        
        c_ma = next((c for c in df_ck.columns if 'mã' in c), '')
        c_nd = next((c for c in df_ck.columns if 'nội dung' in c), '')
        c_tang = next((c for c in df_ck.columns if 'tăng' in c), None)
        c_giam = next((c for c in df_ck.columns if 'giảm' in c), None)

        c_nd_tien = next((c for c in df_tien.columns if 'nội dung' in c), None)
        c_giam_tien = next((c for c in df_tien.columns if 'giảm' in c), None)
        c_tang_tien = next((c for c in df_tien.columns if 'tăng' in c), None)

        events = []
        if c_ma and c_nd:
            for _, row in df_ck.iterrows():
                content = str(row.get(c_nd, ''))
                m_date = re.search(r"Ngay:\s*(\d{2}/\d{2}/\d{4})", content)
                m_price = re.search(r"Gia:\s*([0-9,]+)", content)
                if m_date and m_price:
                    vol_in = clean_number(row.get(c_tang, 0)) if c_tang else 0
                    vol_out = clean_number(row.get(c_giam, 0)) if c_giam else 0
                    if vol_in > 0: type_ = 'BUY'; vol = vol_in
                    elif vol_out > 0: type_ = 'SELL'; vol = vol_out
                    else: continue
                    events.append({'date': m_date.group(1), 'sym': str(row.get(c_ma, '')).strip().upper(), 'type': type_, 'vol': vol, 'price': clean_number(m_price.group(1)), 'val': 0})
        
        if c_nd_tien:
            for _, row in df_tien.iterrows():
                content = str(row.get(c_nd_tien, '')).lower()
                val_out = clean_number(row.get(c_giam_tien, 0))
                val_in = clean_number(row.get(c_tang_tien, 0))
                
                m_date = re.search(r"(\d{2}/\d{2}/\d{4})", content)
                t_date = m_date.group(1) if m_date else None
                if not t_date: 
                    raw_d = row.iloc[0]; t_date = raw_d.strftime('%d/%m/%Y') if isinstance(raw_d, datetime) else str(raw_d)

                if val_out > 0 and any(k in content for k in ['phi', 'phí', 'thue', 'thuế']):
                    m_sym = re.search(r"(?:mua|ban)\s+([a-z0-9]+)", content)
                    if m_sym: events.append({'date': t_date, 'sym': m_sym.group(1).upper(), 'type': 'FEE', 'vol': 0, 'price': 0, 'val': val_out})
                
                if val_in > 0 and any(k in content for k in ['co tuc', 'cổ tức']):
                    m_sym = re.search(r"ma:\s*([a-z0-9]+)", content)
                    if m_sym: events.append({'date': t_date, 'sym': m_sym.group(1).upper(), 'type': 'DIVIDEND', 'vol': 0, 'price': 0, 'val': val_in})

                if val_in > 0 and 'nop tien' in content and 'vpbank' in content:
                    total_deposit += val_in

        df_events = pd.DataFrame(events)
        if df_events.empty: return None, None, "Không tìm thấy dữ liệu giao dịch."

        df_events['date_obj'] = pd.to_datetime(df_events['date'], format='%d/%m/%Y', errors='coerce')
        prio_map = {'BUY': 1, 'FEE': 2, 'SELL': 3, 'DIVIDEND': 4}
        df_events['prio'] = df_events['type'].map(prio_map)
        df_events = df_events.sort_values(by=['date_obj', 'prio'])

        trades = df_events[df_events['type'].isin(['BUY', 'SELL'])].copy()
        fees = df_events[df_events['type'] == 'FEE'].copy()
        divs = df_events[df_events['type'] == 'DIVIDEND'].copy()

        trade_grp = trades.groupby(['date_obj', 'date', 'sym', 'type']).agg({'vol': 'sum', 'price': 'first'}).reset_index()
        fee_grp = fees.groupby(['date_obj', 'sym'])['val'].sum().reset_index().rename(columns={'val': 'fee'})
        
        merged = pd.merge(trade_grp, fee_grp, on=['date_obj', 'sym'], how='left')
        merged['fee'] = merged['fee'].fillna(0)
        divs['vol']=0; divs['price']=0; divs['fee']=0; divs['dividend']=divs['val']
        merged['dividend'] = 0
        
        final_stream = pd.concat([merged, divs], ignore_index=True).sort_values(by=['date_obj'])

        for _, row in final_stream.iterrows():
            engine.process_transaction(row['date_obj'], row['date'], row['sym'], row['type'], row['vol'], row['price'], row['fee'], row.get('dividend', 0))

        return engine.generate_reports(), total_deposit, None

    except Exception as e:
        return None, None, f"Lỗi xử lý: {str(e)}"

def convert_df_to_excel(df_sum, df_cycle, df_inv, df_warn, deposit_val):
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        info_df = pd.DataFrame({
            'Thông tin': ['Nguồn dữ liệu', 'Thời gian chạy', 'Tổng Tiền Đã Nạp'],
            'Giá trị': ['VPS Web Dashboard', datetime.now().strftime('%d/%m/%Y %H:%M'), f"{deposit_val:,.0f}"]
        })
        info_df.to_excel(writer, sheet_name='Thông Tin', index=False)
        if not df_warn.empty: df_warn.to_excel(writer, sheet_name='CẢNH BÁO RỦI RO', index=False)
        df_sum.to_excel(writer, sheet_name='HIỆU SUẤT TỔNG', index=False)
        df_cycle.to_excel(writer, sheet_name='LỊCH SỬ CÁC VÒNG ĐẦU TƯ', index=False)
        df_inv.to_excel(writer, sheet_name='CHI TIẾT TỒN KHO', index=False)
    return output.getvalue()

# --- 3. UI LAYOUT ---

with st.sidebar:
    st.header("1️⃣ Nguồn Dữ Liệu")
    uploaded_file = st.file_uploader("Upload 'history_VCK.xlsx'", type=["xlsx"])
    st.divider()
    st.header("2️⃣ Bộ Lọc (Filter)")
    filter_container = st.container()

if uploaded_file:
    with st.spinner("🚀 Đang chạy thuật toán FIFO..."):
        results, deposit_val, error_msg = process_uploaded_file(uploaded_file)

    if error_msg:
        st.error(f"❌ {error_msg}")
    elif results:
        df_sum, df_cycle, df_inv, df_warn = results

        with filter_container:
            all_tickers = sorted(df_sum['Mã CK'].unique())
            selected_tickers = st.multiselect("Chọn Mã CK", options=all_tickers, default=all_tickers)
            if selected_tickers:
                df_sum_view = df_sum[df_sum['Mã CK'].isin(selected_tickers)]
                df_cycle_view = df_cycle[df_cycle['Mã CK'].isin(selected_tickers)]
                df_inv_view = df_inv[df_inv['Mã CK'].isin(selected_tickers)]
            else:
                df_sum_view = df_sum
                df_cycle_view = df_cycle
                df_inv_view = df_inv

        # --- DASHBOARD ---
        st.title("📊 Dashboard Phân Tích Đầu Tư")
        
        # KPI Cards (Định dạng chuẩn VN)
        total_profit = df_sum_view['Lãi/Lỗ Đã Chốt'].sum()
        total_holding_val = df_sum_view['Vốn Đang Giữ'].sum()
        total_invested = df_sum_view['Tổng Vốn Đã Rót'].sum()
        
        col1, col2, col3, col4, col5 = st.columns(5)
        col1.metric("💰 Lãi Đã Chốt", f"{fmt_vnd(total_profit)} đ", delta_color="normal")
        col2.metric("📦 Giá Trị Kho", f"{fmt_vnd(total_holding_val)} đ")
        col3.metric("💳 Nạp Tiền VPBank", f"{fmt_vnd(deposit_val)} đ")
        col4.metric("💸 Vốn Xoay Vòng", f"{fmt_vnd(total_invested)} đ")
        
        holding_count = len(df_sum_view[df_sum_view['SL Đang Giữ'] > 0])
        col5.metric("🔖 Mã Đang Giữ", f"{holding_count} mã")

        # --- CHARTS ---
        st.divider()
        st.subheader("📈 Phân Tích Trực Quan")
        chart_col1, chart_col2 = st.columns(2)
        
        with chart_col1:
            df_holding = df_sum_view[df_sum_view['Vốn Đang Giữ'] > 0]
            if not df_holding.empty:
                fig_pie = px.pie(df_holding, values='Vốn Đang Giữ', names='Mã CK', title='Phân Bổ Tỷ Trọng (Vốn Đang Giữ)', hole=0.4)
                st.plotly_chart(fig_pie, use_container_width=True)
            else: st.info("Hiện không nắm giữ mã nào.")

        with chart_col2:
            df_pl = df_sum_view.sort_values(by='Lãi/Lỗ Đã Chốt', ascending=False)
            if not df_pl.empty:
                df_pl['Màu'] = df_pl['Lãi/Lỗ Đã Chốt'].apply(lambda x: '#00CC96' if x >= 0 else '#EF553B')
                fig_bar = px.bar(df_pl, x='Mã CK', y='Lãi/Lỗ Đã Chốt', title='Top Lợi Nhuận Thực Hiện', text_auto='.2s')
                fig_bar.update_traces(marker_color=df_pl['Màu'])
                st.plotly_chart(fig_bar, use_container_width=True)

        st.subheader("🎯 Hiệu Quả Vị Thế (ROI vs Vốn)")
        if not df_sum_view.empty:
            fig_scat = px.scatter(
                df_sum_view, x='Tổng Vốn Đã Rót', y='Lãi/Lỗ Đã Chốt',
                size='Tổng Vốn Đã Rót', color='Lãi/Lỗ Đã Chốt', hover_name='Mã CK',
                size_max=60, color_continuous_scale=px.colors.diverging.Tealrose,
                title='Tương Quan: Quy Mô Vốn vs Lợi Nhuận'
            )
            fig_scat.add_hline(y=0, line_dash="dash", line_color="gray")
            st.plotly_chart(fig_scat, use_container_width=True)

        # --- TABLES (Áp dụng định dạng chuẩn VN) ---
        st.divider()
        tab1, tab2, tab3, tab4 = st.tabs(["📋 Hiệu Suất Tổng", "🔄 Lịch Sử Cycle", "📦 Kho Chi Tiết", "⚠️ Cảnh Báo"])

        # Format dict cho bảng Hiệu Suất Tổng
        fmt_sum = {
            'Tổng SL Đã Bán': fmt_num, 'Lãi/Lỗ Đã Chốt': fmt_vnd,
            '% Hiệu Suất Tổng': fmt_pct, 'Ngày Giữ TB (Đã Bán)': fmt_float,
            'SL Đang Giữ': fmt_num, 'Vốn Đang Giữ': fmt_vnd,
            'Tuổi Kho TB (Đang Giữ)': fmt_float, 'Tổng Vốn Đã Rót': fmt_vnd
        }

        # Format dict cho bảng Cycle
        fmt_cyc = {
            'Tổng Vốn Mua': fmt_vnd, 'Tổng Tiền Bán': fmt_vnd,
            'Lãi/Lỗ Thực': fmt_vnd, '% Hiệu Suất Cycle': fmt_pct
        }

        # Format dict cho bảng Tồn kho
        fmt_inv = {
            'SL Tồn': fmt_num, 'Giá Vốn': fmt_vnd, 'Ngày Giữ': fmt_num
        }

        # Format dict cho Cảnh báo
        fmt_warn = {
            'Vốn Kẹp': fmt_vnd, 'Tuổi Kho TB': fmt_float
        }

        with tab1: st.dataframe(df_sum_view.style.format(fmt_sum).background_gradient(subset=['Lãi/Lỗ Đã Chốt'], cmap='RdYlGn'), use_container_width=True)
        with tab2: st.dataframe(df_cycle_view.style.format(fmt_cyc), use_container_width=True)
        with tab3: st.dataframe(df_inv_view.style.format(fmt_inv), use_container_width=True)
        with tab4:
            if not df_warn.empty:
                warn_view = df_warn[df_warn['Mã CK'].isin(selected_tickers)]
                if not warn_view.empty:
                    st.error(f"Cảnh báo: Có {len(warn_view)} mã kẹp hàng > 90 ngày!")
                    st.dataframe(warn_view.style.format(fmt_warn), use_container_width=True)
                else: st.success("Không có cảnh báo cho mã đã chọn.")
            else: st.success("✅ Danh mục an toàn.")

        # --- DOWNLOAD ---
        st.sidebar.divider()
        st.sidebar.header("📥 Xuất Báo Cáo")
        excel_data = convert_df_to_excel(df_sum, df_cycle, df_inv, df_warn, deposit_val)
        st.sidebar.download_button(label="Tải File Excel", data=excel_data, file_name=f"Bao_cao_VPS_Pro_{datetime.now().strftime('%Y%m%d')}.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", type="primary")

else:
    st.info("👋 Vui lòng upload file 'history_VCK.xlsx' ở Sidebar bên trái.")