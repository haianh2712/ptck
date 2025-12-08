import streamlit as st
import pandas as pd
import numpy as np
from collections import deque, defaultdict
import datetime
import re
import io
import traceback

# ==============================================================================
# 1. CẤU HÌNH TRANG
# ==============================================================================
st.set_page_config(page_title="Investment V64 (Final Fix)", layout="wide")

if 'data_raw' not in st.session_state:
    st.session_state.data_raw = None
if 'has_run' not in st.session_state:
    st.session_state.has_run = False

st.title("📊 DASHBOARD PHÂN TÍCH HIỆU QUẢ")
st.markdown("---")

# ==============================================================================
# 2. SIDEBAR
# ==============================================================================
with st.sidebar:
    st.header("1. Dữ liệu")
    uploaded_file = st.file_uploader("Upload 'history3.xlsx':", type=['xlsx'])
    
    user_pl_col = None
    if uploaded_file is not None:
        try:
            uploaded_file.seek(0)
            df_preview = pd.read_excel(uploaded_file, sheet_name='Lãi lỗ')
            df_preview.columns = [str(c).strip() for c in df_preview.columns]
            all_cols = list(df_preview.columns)
            default_ix = 0
            for i, col in enumerate(all_cols):
                if 'lãi' in str(col).lower() and '%' not in str(col):
                    default_ix = i; break
            st.caption("Cột tiền Lãi/Lỗ:")
            user_pl_col = st.selectbox("", all_cols, index=default_ix)
        except: pass

    st.markdown("---")
    st.header("2. Bộ Lọc")
    filter_type = st.radio("Thời gian:", ["Toàn thời gian", "Tùy chỉnh ngày"])
    start_date = datetime.date(2020, 1, 1)
    end_date = datetime.date.today()
    if filter_type == "Tùy chỉnh ngày":
        c1, c2 = st.columns(2)
        with c1: start_date = st.date_input("Từ:", datetime.date.today().replace(day=1))
        with c2: end_date = st.date_input("Đến:", datetime.date.today())

    st.header("3. Rủi ro")
    LIMIT_DAYS = st.number_input("Ngày giữ >", value=90)
    LIMIT_ALLOC = st.slider("Tỷ trọng > %", 0.0, 1.0, 0.20)
    LIMIT_CAP = st.number_input("Vốn > VNĐ", value=100000000)

# ==============================================================================
# 3. HÀM HỖ TRỢ (HELPER FUNCTIONS)
# ==============================================================================
def safe_date(obj):
    if pd.isna(obj): return None
    if isinstance(obj, str):
        try: return pd.to_datetime(obj, dayfirst=True).date()
        except: pass
    if isinstance(obj, pd.Timestamp): return obj.date()
    if isinstance(obj, datetime.datetime): return obj.date()
    return obj

def extract_date(text):
    if not isinstance(text, str): return None
    match = re.search(r"(\d{1,2})[\/\-](\d{1,2})[\/\-](\d{2,4})", text)
    if match:
        d, m, y = match.groups()
        if len(y) == 2: y = "20" + y
        try: return datetime.date(int(y), int(m), int(d))
        except: return None
    return None

def parse_desc(mo_ta):
    if not isinstance(mo_ta, str): return None
    p = r"(Trả tiền mua|Trả phí mua|Trả phí lệnh bán|Thuế TNCN bán|Thuế bán)\s*.*?(\d+)\s*([A-Za-z0-9_]+)"
    match = re.search(p, mo_ta, re.IGNORECASE)
    if match:
        act = match.group(1).lower()
        sl = int(match.group(2))
        mack = match.group(3).upper()
        d_tx = extract_date(mo_ta)
        type_tx = None
        if "trả tiền mua" in act: type_tx = 'BUY_COST'
        elif "trả phí mua" in act: type_tx = 'BUY_FEE'
        elif "trả phí lệnh bán" in act: type_tx = 'SELL_FEE'
        elif "thuế" in act: type_tx = 'SELL_TAX'
        return type_tx, sl, mack, d_tx
    return None

def check_0_dong(desc, ticker):
    desc = str(desc).lower()
    ticker = str(ticker).upper()
    if ticker.endswith('_WFT'): return True
    keys = ['thưởng', 'cổ tức', 'chuyển đổi', 'nhận', 'phát hành thêm', 'quyền mua']
    for k in keys:
        if k in desc and not desc.strip().startswith('mua '): return True
    return False

def read_ex(file, sheet):
    try: return pd.read_excel(file, sheet_name=sheet)
    except: return None

def fmt_vn(val, decimals=0):
    if pd.isna(val) or val == "": return "-"
    try:
        if decimals == 0: s = "{:,.0f}".format(val)
        else: s = "{:,.2f}".format(val)
        return s.replace(",", "X").replace(".", ",").replace("X", ".")
    except: return val

# --- [FIXED] ĐÃ BỔ SUNG LẠI HÀM NÀY ---
def format_date_vn(df, col_name):
    """Hàm định dạng ngày tháng cho cột cụ thể"""
    if col_name in df.columns:
        df[col_name] = pd.to_datetime(df[col_name], errors='coerce')
        df[col_name] = df[col_name].dt.strftime('%d/%m/%Y').fillna('')
    return df

def apply_format_df(df):
    df_show = df.copy()
    for col in df_show.columns:
        c_lower = str(col).lower()
        if any(x in c_lower for x in ['vốn', 'lãi', 'giá', 'tiền', 'amount', 'price', 'cost', 'sl', 'qty', 'kl']):
            if 'ngày' not in c_lower:
                df_show[col] = df_show[col].apply(lambda x: fmt_vn(x, 0))
        elif '%' in str(col) or 'roi' in c_lower or 'suất' in c_lower:
            df_show[col] = df_show[col].apply(lambda x: fmt_vn(x, 2) + '%' if isinstance(x, (int, float)) else x)
        elif pd.api.types.is_datetime64_any_dtype(df_show[col]):
            df_show[col] = df_show[col].dt.strftime('%d/%m/%Y').fillna('')
        
        if 'tuổi' in c_lower or 'giữ tb' in c_lower:
             df_show[col] = df_show[col].apply(lambda x: fmt_vn(x, 1) if isinstance(x, (int, float)) and x > 0 else ("-" if x==0 else x))
    return df_show

# ==============================================================================
# 4. LOGIC XỬ LÝ (CORE)
# ==============================================================================
def run_logic_v64(f_in, pl_col):
    # --- B1: MAP GIA ---
    price_map = {} 
    fee_map = {} 
    cap_map = defaultdict(float)
    
    df_money = None
    cols_safe = [0, 1, 3]
    for s in ['SK Tiền', 'CK Tiền', 'Sheet1']:
        f_in.seek(0)
        tmp = read_ex(f_in, s)
        if tmp is not None:
            if 'Ngày' not in tmp.columns:
                f_in.seek(0)
                tmp = pd.read_excel(f_in, sheet_name=s, header=None)
                tmp = tmp.iloc[:, cols_safe]
                tmp.columns = ['Ngay', 'MoTa', 'Tien']
            else:
                try:
                    tmp = tmp.iloc[:, cols_safe]
                    tmp.columns = ['Ngay', 'MoTa', 'Tien']
                except: pass
            df_money = tmp
            break
            
    if df_money is not None:
        s_val = pd.to_numeric(df_money['Tien'], errors='coerce')
        df_money['Tien'] = s_val.fillna(0)
        df_money = df_money[df_money['Tien'] > 0]
        
        tmp_buy = defaultdict(lambda: {'q':0, 'c':0})
        
        for _, r in df_money.iterrows():
            parsed = parse_desc(str(r['MoTa']))
            if parsed:
                typ, qty, tik, d_tx = parsed
                if not d_tx: d_tx = safe_date(r['Ngay'])
                
                if typ in ['BUY_COST', 'BUY_FEE']:
                    cap_map[tik] += r['Tien']
                
                if d_tx:
                    k = (tik, d_tx)
                    if typ == 'BUY_COST':
                        tmp_buy[k]['q'] += qty
                        tmp_buy[k]['c'] += r['Tien']
                    elif typ == 'BUY_FEE':
                        tmp_buy[k]['c'] += r['Tien']
                    elif typ in ['SELL_FEE', 'SELL_TAX']:
                        if k not in fee_map: fee_map[k] = {'f':0, 'q':0}
                        fee_map[k]['f'] += r['Tien']
                        fee_map[k]['q'] += qty
        
        for k, v in tmp_buy.items():
            if v['q'] > 0: price_map[k] = v['c'] / v['q']

    # --- B2: CP ---
    events = []
    f_in.seek(0)
    df_cp = read_ex(f_in, 'CP')
    if df_cp is not None:
        ren = {'Ngày': 'Date', 'Mã CK': 'Tik', 'Giảm': 'Out', 'Tăng': 'In', 'Mô tả': 'Desc'}
        df_cp = df_cp.rename(columns=ren)
        df_cp['Date'] = pd.to_datetime(df_cp['Date'], dayfirst=True, format='mixed', errors='coerce')
        df_cp.dropna(subset=['Date', 'Tik'], inplace=True)
        
        df_cp['Out'] = pd.to_numeric(df_cp['Out'], errors='coerce').fillna(0)
        df_cp['In'] = pd.to_numeric(df_cp['In'], errors='coerce').fillna(0)
        
        for _, r in df_cp.iterrows():
            tik = str(r['Tik']).strip().upper()
            desc = str(r['Desc'])
            d_row = safe_date(r['Date'])
            d_tx = extract_date(desc)
            if not d_tx: d_tx = d_row
            
            if r['In'] > 0:
                p = 0
                if not check_0_dong(desc, tik):
                    p = price_map.get((tik, d_tx), 0)
                    if p == 0:
                        for d in range(-5, 6):
                            chk = d_tx + datetime.timedelta(days=d)
                            if (tik, chk) in price_map: p = price_map[(tik, chk)]; break
                evt = {'date': d_row, 'd_tx': d_tx, 'type': 'BUY', 'tik': tik, 'qty': r['In'], 'price': p}
                events.append(evt)
            
            if r['Out'] > 0:
                evt = {'date': d_row, 'd_tx': d_tx, 'type': 'SELL', 'tik': tik, 'qty': r['Out'], 'price': 0}
                events.append(evt)

    events.sort(key=lambda x: x['date'])

    # --- B3: LAI LO ---
    raw_sales = [] 
    mkt_map = {}
    f_in.seek(0)
    df_ll = read_ex(f_in, 'Lãi lỗ')
    
    if df_ll is not None:
        df_ll.columns = [str(c).strip() for c in df_ll.columns]
        for _, r in df_ll.iterrows():
            tik = str(r.iloc[1]).strip().upper()
            d_sell = safe_date(r.iloc[0]) 
            qty = pd.to_numeric(r.iloc[2], errors='coerce') or 0
            
            pl = 0
            if pl_col in r:
                pl = pd.to_numeric(r[pl_col], errors='coerce') or 0
            
            cost = 0; match_p = 0
            for c in df_ll.columns:
                cs = str(c).lower()
                val = pd.to_numeric(r[c], errors='coerce') or 0
                if 'giá trị vốn' in cs: cost = val
                if 'khớp' in cs and 'giá' in cs: match_p = val
            
            if cost == 0:
                uc = 0
                for c in df_ll.columns:
                    if str(c).strip() == 'Giá vốn':
                        uc = pd.to_numeric(r[c], errors='coerce') or 0
                cost = uc * qty
                
            if d_sell and match_p > 0: mkt_map[(tik, d_sell)] = match_p
            
            raw_sales.append({
                'Mã CK': tik, 'Ngày Bán': d_sell, 'SL Bán': qty, 'Vốn Bán': cost, 'Lãi/Lỗ': pl
            })

    # --- B4: FIFO ---
    inv = {}; cycles_active = {}; cycles_closed = []
    today = datetime.date.today()
    days_sold_map = defaultdict(list) 
    
    for e in events:
        tik = e['tik']; d = e['date']; d_tx = e['d_tx']
        
        if e['type'] == 'BUY':
            if tik not in inv: inv[tik] = deque()
            inv[tik].append({'d': d, 'q': e['qty'], 'p': e['price']})
            
            if tik not in cycles_active:
                cycles_active[tik] = {'start': d, 'buy_q': 0, 'cur_q': 0, 'cost': 0, 'pl': 0}
            cycles_active[tik]['buy_q'] += e['qty']
            cycles_active[tik]['cur_q'] += e['qty']
            cycles_active[tik]['cost'] += (e['qty'] * e['price'])
            
        elif e['type'] == 'SELL':
            rem = e['qty']; sell_p = 0
            if "_WFT" not in tik:
                gp = mkt_map.get((tik, d_tx), 0)
                if gp == 0:
                    for i in range(-5, 6):
                        chk = d_tx + datetime.timedelta(days=i)
                        if (tik, chk) in mkt_map: gp = mkt_map[(tik, chk)]; break
                
                fee_val = 0
                f_inf = fee_map.get((tik, d_tx))
                if not f_inf:
                    for i in range(-3, 4):
                        chk = d_tx + datetime.timedelta(days=i)
                        if (tik, chk) in fee_map: f_inf = fee_map[(tik, chk)]; break
                if f_inf and f_inf['q'] > 0: fee_val = f_inf['f'] / f_inf['q']
                if gp > 0: sell_p = gp - fee_val
                
            deal_pl = 0
            if tik in inv:
                while rem > 0 and inv[tik]:
                    batch = inv[tik][0]
                    take = min(rem, batch['q'])
                    d_held = (d - batch['d']).days
                    if d_held < 0: d_held = 0
                    days_sold_map[tik].append((d, d_held, take))
                    
                    if sell_p > 0: deal_pl += (sell_p - batch['p']) * take
                    rem -= take
                    batch['q'] -= take
                    if batch['q'] <= 0: inv[tik].popleft()
                if not inv[tik]: del inv[tik]
                
            if tik in cycles_active:
                cycles_active[tik]['cur_q'] -= e['qty']
                cycles_active[tik]['pl'] += deal_pl
                if cycles_active[tik]['cur_q'] <= 0.1:
                    cyc = cycles_active.pop(tik)
                    dur = (d - cyc['start']).days
                    roi = 0
                    if cyc['cost'] > 0: roi = (cyc['pl'] / cyc['cost']) * 100
                    c_row = {'Mã CK': tik, 'Ngày Bắt Đầu': cyc['start'], 'Ngày Kết Thúc': d, 
                             'Tuổi Vòng Đời': max(1, dur), 'Tổng Vốn': cyc['cost'], 
                             'Lãi/Lỗ': cyc['pl'], '% ROI': roi, 'Status': 'Đã tất toán'}
                    cycles_closed.append(c_row)

    for tik, dat in cycles_active.items():
        dur = (today - dat['start']).days
        c_row = {'Mã CK': tik, 'Ngày Bắt Đầu': dat['start'], 'Ngày Kết Thúc': None, 
                 'Tuổi Vòng Đời': dur, 'Tổng Vốn': dat['cost'], 'Lãi/Lỗ': dat['pl'], 
                 'Status': 'Đang nắm giữ'}
        cycles_closed.append(c_row)

    return {
        'raw_sales': raw_sales,
        'cycles': cycles_closed,
        'inventory': inv,
        'capital_map': cap_map,
        'days_sold_map': days_sold_map
    }

# ==============================================================================
# 5. UI TRIGGER & DISPLAY
# ==============================================================================
st.write("")
btn_run = st.button("🚀 CHẠY PHÂN TÍCH NGAY", type="primary", use_container_width=True)

if btn_run:
    if uploaded_file is None:
        st.error("⚠️ Chưa có file!")
    elif user_pl_col is None:
        st.error("⚠️ Vui lòng chọn cột Lãi/Lỗ")
    else:
        with st.spinner("Đang tính toán (V64)..."):
            try:
                raw_data = run_logic_v64(uploaded_file, user_pl_col)
                st.session_state.data_raw = raw_data
                st.session_state.has_run = True
            except Exception as e:
                st.error(f"Lỗi: {e}")
                st.code(traceback.format_exc())

# --- HIỂN THỊ KẾT QUẢ ---
if st.session_state.has_run and st.session_state.data_raw:
    raw = st.session_state.data_raw
    st.success("✅ Đã xử lý xong!")
    
    # 1. TOTAL CAPITAL
    all_tk_global = set(list(raw['capital_map'].keys()) + list(raw['inventory'].keys()))
    GLOBAL_TOTAL_HOLD_VAL = 0
    hold_map_global = {}
    today = datetime.date.today()
    
    for tik in all_tk_global:
        val_h = 0
        if tik in raw['inventory']:
            for b in raw['inventory'][tik]: val_h += b['q'] * b['p']
        hold_map_global[tik] = val_h
        GLOBAL_TOTAL_HOLD_VAL += val_h

    # 2. FILTER
    with st.sidebar:
        st.write("---")
        st.header("4. Lọc Mã Cổ Phiếu")
        all_display_tk = sorted(list(all_tk_global))
        selected_tickers = st.multiselect("Chọn mã:", all_display_tk)
        
    df_sales = pd.DataFrame(raw['raw_sales'])
    if not df_sales.empty:
        df_sales['Ngày Bán'] = pd.to_datetime(df_sales['Ngày Bán']).dt.date
        if filter_type == "Tùy chỉnh ngày":
            df_sales = df_sales[(df_sales['Ngày Bán'] >= start_date) & (df_sales['Ngày Bán'] <= end_date)]
        if selected_tickers:
            df_sales = df_sales[df_sales['Mã CK'].isin(selected_tickers)]
            
    df_cycles = pd.DataFrame(raw['cycles'])
    if not df_cycles.empty:
        if selected_tickers:
            df_cycles = df_cycles[df_cycles['Mã CK'].isin(selected_tickers)]
        if filter_type == "Tùy chỉnh ngày":
            def f_cyc(row):
                if row['Status'] == 'Đã tất toán':
                    d_end = safe_date(row['Ngày Kết Thúc'])
                    if d_end: return start_date <= d_end <= end_date
                return True 
            df_cycles = df_cycles[df_cycles.apply(f_cyc, axis=1)]

    inv_rows = []
    for t, q in raw['inventory'].items():
        if selected_tickers and t not in selected_tickers: continue
        for b in q:
            inv_rows.append({'Mã CK': t, 'Ngày Mua': b['d'], 'SL Tồn': b['q'], 'Giá Vốn': b['p']})
    df_inv = pd.DataFrame(inv_rows)

    # 3. AGGREGATE
    agg_sales = {}
    if not df_sales.empty:
        agg_sales = df_sales.groupby('Mã CK').agg({'SL Bán':'sum','Vốn Bán':'sum','Lãi/Lỗ':'sum'}).to_dict('index')
    
    final_rows = []
    warn_rows = []
    display_tickers = selected_tickers if selected_tickers else all_tk_global
    
    for tik in display_tickers:
        q_hold = 0; d_sum = 0
        if tik in raw['inventory']:
            for b in raw['inventory'][tik]:
                q_hold += b['q']
                d_sum += (today - b['d']).days * b['q']
        
        avg_d_hold = d_sum/q_hold if q_hold > 0 else 0
        val_hold = hold_map_global.get(tik, 0)
        
        s_inf = agg_sales.get(tik, {'SL Bán':0, 'Vốn Bán':0, 'Lãi/Lỗ':0})
        
        sold_list = raw['days_sold_map'].get(tik, [])
        d_sold_s = 0; q_sold_s = 0
        for d_sell, days, q in sold_list:
            is_in_time = True
            if filter_type == "Tùy chỉnh ngày":
                d_sell_date = safe_date(d_sell)
                if d_sell_date and not (start_date <= d_sell_date <= end_date): is_in_time = False
            if is_in_time:
                d_sold_s += days * q
                q_sold_s += q
        
        avg_d_sold = 0
        if q_sold_s > 0:
            avg_d_sold = d_sold_s / q_sold_s
        
        pct_eff = (s_inf['Lãi/Lỗ']/s_inf['Vốn Bán']*100) if s_inf['Vốn Bán'] > 0 else 0
        
        final_rows.append({
            'Mã CK': tik, 
            'Lãi/Lỗ (Trong Kỳ)': s_inf['Lãi/Lỗ'], 
            '% Hiệu Suất (Trong Kỳ)': pct_eff,
            'SL Đang Giữ': q_hold, 
            'Vốn Đang Giữ': val_hold, 
            'Tuổi Kho TB': avg_d_hold, 
            'Ngày Giữ TB (Bán)': avg_d_sold
        })
        
        w = []
        alloc = 0
        if GLOBAL_TOTAL_HOLD_VAL > 0: alloc = val_hold / GLOBAL_TOTAL_HOLD_VAL
        if alloc > LIMIT_ALLOC: w.append(f"Tỷ trọng {round(alloc*100,1)}%")
        if val_hold > LIMIT_CAP: w.append("Vốn lớn")
        if avg_d_hold > LIMIT_DAYS: w.append(f"Kẹp > {LIMIT_DAYS} ngày")
        if w: warn_rows.append({'Mã CK': tik, 'Vốn': val_hold, 'Cảnh Báo': "; ".join(w)})

    df_final = pd.DataFrame(final_rows)
    if not df_final.empty: df_final = df_final.sort_values('Vốn Đang Giữ', ascending=False)
    df_warn = pd.DataFrame(warn_rows)

    # --- FORMAT DATE ---
    if not df_cycles.empty:
        df_cycles = format_date_vn(df_cycles, 'Ngày Bắt Đầu')
        df_cycles = format_date_vn(df_cycles, 'Ngày Kết Thúc')
    if not df_inv.empty:
        df_inv = format_date_vn(df_inv, 'Ngày Mua')

    # --- EXPORT ---
    bio = io.BytesIO()
    with pd.ExcelWriter(bio, engine='xlsxwriter') as wr:
        df_final.to_excel(wr, sheet_name='HIỆU SUẤT', index=False)
        if not df_inv.empty: df_inv.to_excel(wr, sheet_name='TỒN KHO', index=False)
        if not df_cycles.empty: df_cycles.to_excel(wr, sheet_name='LỊCH SỬ', index=False)
        if not df_warn.empty: df_warn.to_excel(wr, sheet_name='CẢNH BÁO', index=False)
    
    st.download_button("📥 Tải Excel (DD/MM/YYYY)", bio.getvalue(), "Bao_cao_V64.xlsx")
    
    # --- DISPLAY ---
    m1, m2 = st.columns(2)
    t_pl = df_final['Lãi/Lỗ (Trong Kỳ)'].sum()
    current_show_val = df_final['Vốn Đang Giữ'].sum()
    
    m1.metric(f"Lãi/Lỗ ({start_date.strftime('%d/%m')} - {end_date.strftime('%d/%m')})", fmt_vn(t_pl) + " VNĐ", delta_color="normal" if t_pl>=0 else "inverse")
    m2.metric(f"Vốn Đang Giữ (Hiển thị / Tổng)", f"{fmt_vn(current_show_val)} / {fmt_vn(GLOBAL_TOTAL_HOLD_VAL)} VNĐ")
    
    st.markdown("---")
    c_chart1, c_chart2 = st.columns(2)
    with c_chart1:
        st.subheader("💰 Phân Bổ Vốn")
        if not df_final.empty and current_show_val > 0:
            df_c1 = df_final[df_final['Vốn Đang Giữ'] > 0].set_index('Mã CK')
            st.bar_chart(df_c1['Vốn Đang Giữ'], color="#FF4B4B")
        else: st.info("Không có dữ liệu vốn.")
        
    with c_chart2:
        st.subheader("📈 Hiệu Quả (Trong Kỳ)")
        if not df_final.empty:
            df_c2 = df_final.set_index('Mã CK')
            st.bar_chart(df_c2['Lãi/Lỗ (Trong Kỳ)'])
    
    st.markdown("---")
    
    # APPLY FORMAT VN FOR DISPLAY
    df_final_show = apply_format_df(df_final)
    df_inv_show = apply_format_df(df_inv)
    df_cycles_show = apply_format_df(df_cycles)
    df_warn_show = apply_format_df(df_warn)
    
    t1, t2, t3, t4 = st.tabs(["📊 Hiệu Suất", "📦 Chi Tiết Tồn Kho", "🔄 Lịch Sử Vòng Đời", "⚠️ Cảnh Báo"])
    with t1: st.dataframe(df_final_show, use_container_width=True)
    with t2: 
        if not df_inv_show.empty: st.dataframe(df_inv_show, use_container_width=True)
        else: st.info("Không có hàng tồn kho cho các mã đã chọn.")
    with t3: st.dataframe(df_cycles_show, use_container_width=True)

    with t4: st.dataframe(df_warn_show, use_container_width=True)
