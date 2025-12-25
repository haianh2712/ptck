# File: modules/wealth_management/wealth_view.py
# Version: FINAL FIX - DUPLICATE KEY (Sửa lỗi trùng mã WFT)

import streamlit as st
import pandas as pd
import altair as alt
import copy
import re
from datetime import datetime
from modules.wealth_management.rebalancing import calculate_rebalancing

# ==============================================================================
# 1. HELPER FUNCTIONS
# ==============================================================================
def normalize_text(text):
    if not text: return ""
    return str(text).upper().strip()

def force_float(val):
    try:
        if isinstance(val, (int, float)): return float(val)
        if pd.isna(val): return 0.0
        s = str(val).strip()
        if not s or s == '-': return 0.0
        s_clean = re.sub(r'[^\d.,-]', '', s)
        if ',' in s_clean and '.' in s_clean: return float(s_clean.replace(',', ''))
        if ',' in s_clean: return float(s_clean.replace(',', ''))
        return float(s_clean)
    except: return 0.0

# ==============================================================================
# 2. LOGIC VPS (GIỮ NGUYÊN)
# ==============================================================================
def find_money_vps(data_dict):
    priority_keys = ['Lãi/Lỗ', 'value', 'amount', 'net_val', 'cash_change', 'Tăng']
    for pk in priority_keys:
        for k, v in data_dict.items():
            if pk.lower() == str(k).lower():
                val = force_float(v)
                if val > 0: return val
    return 0.0

def run_vps_logic(engine):
    results = []
    if not engine or not hasattr(engine, 'trade_log'): return []

    all_logs = []
    if hasattr(engine, 'trade_log'): all_logs.extend(engine.trade_log)
    if hasattr(engine, 'dividends'): all_logs.extend(engine.dividends)
    if hasattr(engine, 'cash_logs'): all_logs.extend(engine.cash_logs)

    for log in all_logs:
        log_str = " | ".join([f"{k}:{v}" for k, v in log.items()]).upper()
        desc = normalize_text(log.get('description') or log.get('desc') or log.get('Nội dung') or log.get('Loại') or '')
        ticker_raw = normalize_text(log.get('ticker') or log.get('Mã') or log.get('Mã CK') or '')
        evt_type = normalize_text(log.get('type', ''))
        
        amt = find_money_vps(log)
        d_val = log.get('date') or log.get('Date') or log.get('time') or log.get('Ngày')

        is_income = False
        inc_type = ""
        
        if 'CỔ TỨC' in desc or 'DIVIDEND' in desc or 'CỔ TỨC' in log_str:
            is_income = True; inc_type = "Cổ Tức Tiền Mặt"
        elif 'DIVIDEND' in evt_type:
            is_income = True; inc_type = "Cổ Tức Tiền Mặt"
        elif ('LÃI' in desc and ('GỬI' in desc or 'NGÂN HÀNG' in desc or 'TIỀN' in desc or 'TK' in desc)) \
             or 'INTEREST' in desc or 'TIỀN GỬI' in desc:
            is_income = True; inc_type = "Lãi Tiền Gửi"
        elif 'INTEREST' in evt_type or 'CASH_INCOME' in evt_type:
             is_income = True; inc_type = "Lãi Tiền Gửi"

        if not is_income:
            for kw in ['CHỐT LÃI', 'PROFIT', 'PNL', 'BÁN', 'SELL', 'TRADING', 'EXCEL PNL']:
                if kw in desc or kw in log_str:
                    is_income = False; break
        
        if is_income and amt > 0:
            tik = "TIEN_GUI"
            if inc_type == "Cổ Tức Tiền Mặt":
                if ticker_raw and ticker_raw not in ['CASH', 'NONE', 'NAN']: tik = ticker_raw
                else:
                    m = re.search(r'\b[A-Z]{3}\b', desc)
                    if m: tik = m.group(0)
                    else: tik = "KHÁC"

            results.append({
                'Ngày': d_val,
                'Mã CK': tik.replace('_WFT', ''),
                'Loại': inc_type,
                'Số Tiền': amt,
                'Nguồn': 'VPS',
                'Mô tả': desc
            })
    return results

# ==============================================================================
# 3. LOGIC VCK (GIỮ NGUYÊN)
# ==============================================================================
def run_vck_logic(raw_list):
    results = []
    if not raw_list: return []

    for log in raw_list:
        if not isinstance(log, dict): continue

        evt_type = str(log.get('type', '')).upper()
        source = str(log.get('source', '')).upper()
        val = force_float(log.get('val', 0))
        sym = str(log.get('sym', '')).upper()
        d_val = log.get('date')
        original_desc = str(log.get('desc', '')).strip()

        is_income = False
        inc_type = ""
        ticker = "TIEN_GUI"
        desc = ""

        if evt_type == 'CO_TUC_TIEN' or evt_type == 'LAI_TIEN_GUI' or source == 'VCK_DIV':
            if evt_type == 'LAI_TIEN_GUI' or (sym == 'TIEN_GUI'):
                is_income = True; inc_type = "Lãi Tiền Gửi"; ticker = "TIEN_GUI"; desc = "Lãi tiền gửi"
            else:
                is_income = True; inc_type = "Cổ Tức Tiền Mặt"
                ticker = sym if sym and sym != 'UNKNOWN' else "KHÁC"
                desc = original_desc if original_desc else f"Cổ tức mã {ticker}"

        if is_income and val > 0:
            results.append({
                'Ngày': d_val, 'Mã CK': ticker.replace('_WFT', ''),
                'Loại': inc_type, 'Số Tiền': val, 'Nguồn': 'VCK', 'Mô tả': desc
            })
    return results

# ==============================================================================
# 3. LOGIC QUẢN LÝ TÀI SẢN (NAV & STRESS TEST)
# ==============================================================================
def create_merged_engine(engine_vck, engine_vps):
    class CombinedEngine:
        def __init__(self): self.data = {}; self.real_cash_balance = 0; self.total_deposit = 0
    merged = CombinedEngine()
    cash_vck = getattr(engine_vck, 'real_cash_balance', 0) if engine_vck else 0
    cash_vps = getattr(engine_vps, 'real_cash_balance', 0) if engine_vps else 0
    merged.real_cash_balance = cash_vck + cash_vps
    
    def merge_data(src):
        if not src or not hasattr(src, 'data'): return
        for k, v in src.data.items():
            tik = str(k).strip().upper()
            if tik not in merged.data: merged.data[tik] = copy.deepcopy(v)
            else:
                if 'inventory' in v:
                    if 'inventory' not in merged.data[tik]: merged.data[tik]['inventory'] = []
                    merged.data[tik]['inventory'].extend(copy.deepcopy(v['inventory']))
                qty = 0; s = v.get('stats', {})
                if s: qty = s.get('curr_vol', 0)
                if 'stats' not in merged.data[tik]: merged.data[tik]['stats'] = {'curr_vol': 0}
                merged.data[tik]['stats']['curr_vol'] = merged.data[tik]['stats'].get('curr_vol', 0) + qty
    merge_data(engine_vck); merge_data(engine_vps)
    return merged

def get_portfolio_snapshot(engine, live_prices):
    """Tính toán NAV hiện tại"""
    if not engine: return 0, 0, []
    
    cash = engine.real_cash_balance
    stock_val = 0
    holdings = []
    
    if hasattr(engine, 'data'):
        for k, v in engine.data.items():
            qty = 0
            if 'inventory' in v: qty = sum(i['vol'] for i in v['inventory'])
            elif 'stats' in v: qty = v['stats'].get('curr_vol', 0)
            
            if qty > 0:
                tik = str(k).replace('_WFT', '').strip().upper()
                price = live_prices.get(tik, 0)
                if price == 0: price = 10000 
                
                val = qty * price
                stock_val += val
                holdings.append({'Ticker': tik, 'Qty': qty, 'Price': price, 'Value': val})
    
    return cash, stock_val, holdings

# ==============================================================================
# 4. VIEW RENDER (3 TABS)
# ==============================================================================
def render_wealth_tab(session_state, live_prices):
    st.markdown("### 🏛️ QUẢN LÝ TÀI SẢN TOÀN DIỆN")
    
    engine_vck = session_state.get('engine_vck')
    engine_vps = session_state.get('engine_vps')
    
    options = {}
    if engine_vck or engine_vps: options["Tổng hợp (Tất cả)"] = "ALL"
    if engine_vck: options["Tài khoản VCK"] = "VCK"
    if engine_vps: options["Tài khoản VPS"] = "VPS"
    
    if not options: return

    c1, _ = st.columns([1,2])
    with c1:
        sel_label = st.radio("🎯 Chọn phạm vi:", list(options.keys()))
        mode = options[sel_label]

    curr_engine = None
    if mode == "VCK": curr_engine = engine_vck
    elif mode == "VPS": curr_engine = engine_vps
    else: curr_engine = create_merged_engine(engine_vck, engine_vps)

    # --- CHUẨN BỊ DỮ LIỆU ---
    # 1. Income Data
    final_data = []
    if engine_vps: final_data.extend(run_vps_logic(engine_vps))
    raw_vck = session_state.get('compass_raw_vck')
    if raw_vck: final_data.extend(run_vck_logic(raw_vck))
    elif engine_vck and hasattr(engine_vck, 'all_raw_events'): final_data.extend(run_vck_logic(engine_vck.all_raw_events))
    
    df_income = pd.DataFrame(final_data)
    if not df_income.empty and mode != "ALL": df_income = df_income[df_income['Nguồn'] == mode]

    # 2. Portfolio Data (NAV)
    cash, stock_val, holdings = get_portfolio_snapshot(curr_engine, live_prices)
    total_nav = cash + stock_val

    # --- TABS ---
    t1, t2, t3 = st.tabs(["⚖️ Tái Cân Bằng", "💰 Dòng Tiền Thụ Động", "📉 Giả lập (Stress Test)"])
    
    # TAB 1: REBALANCING
    with t1:
        if not curr_engine: st.error("No Data")
        else:
            st.metric("Tổng Tài Sản (NAV)", f"{total_nav:,.0f} VND", help="Tiền mặt + Giá trị cổ phiếu hiện tại")
            
            # Form nhập mục tiêu
            # FIX: Dùng set() để loại bỏ mã trùng (ví dụ POW và POW_WFT cùng ra POW)
            # Điều này sửa lỗi StreamlitDuplicateElementKey
            active_tickers = sorted(list(set([h['Ticker'] for h in holdings])))
            
            if not active_tickers and cash > 0:
                st.success(f"Tài khoản Full Cash: {cash:,.0f} VND")
            elif active_tickers:
                st.write("**Phân bổ tỷ trọng mục tiêu (%)**")
                cols = st.columns(4)
                targets = {}; total_inp = 0
                for i, tik in enumerate(active_tickers):
                    with cols[i%4]:
                        v = st.number_input(f"{tik}", 0.0, 100.0, 0.0, 5.0, key=f"tg_{mode}_{tik}")
                        if v > 0: targets[tik] = v; total_inp += v
                
                remain = max(0, 100-total_inp)
                st.caption(f"Đã phân bổ: {total_inp}% | Dư (Tiền mặt): {remain}%")
                
                if total_inp <= 100:
                    st.divider()
                    try:
                        res = calculate_rebalancing(curr_engine, live_prices, targets)
                        if res:
                            st.dataframe(res['df'][['ticker', 'pct_current', 'pct_target', 'val_diff', 'recommendation']], use_container_width=True)
                            
                            df_c = res['df'][res['df']['ticker']!='CASH (Tiền)'].copy()
                            if not df_c.empty:
                                c_data = pd.DataFrame({'Mã': df_c['ticker'].tolist()*2, 'Val': df_c['pct_current'].tolist()+df_c['pct_target'].tolist(), 'Type': ['Hiện tại']*len(df_c)+['Mục tiêu']*len(df_c)})
                                st.altair_chart(alt.Chart(c_data).mark_bar().encode(x='Mã', y='Val', color='Type', xOffset='Type'), use_container_width=True)
                    except: pass

    # TAB 2: INCOME
    with t2:
        if df_income.empty:
            st.info("📭 Chưa tìm thấy dòng tiền (Cổ tức/Lãi).")
        else:
            df_income['Ngày'] = pd.to_datetime(df_income['Ngày'], dayfirst=True, errors='coerce')
            df_income['Tháng'] = df_income['Ngày'].dt.strftime('%Y-%m')
            df_income['Ngày Hiển Thị'] = df_income['Ngày'].dt.strftime('%d/%m/%Y').fillna("--")
            
            total = df_income['Số Tiền'].sum()
            avg = total / (df_income['Tháng'].nunique() or 1)
            
            m1, m2, m3 = st.columns(3)
            m1.metric("Tổng Thu Nhập", f"{total:,.0f} VND")
            m2.metric("Trung Bình/Tháng", f"{avg:,.0f} VND")
            m3.metric("Số Giao Dịch", f"{len(df_income)}")
            
            st.divider()
            c1, c2 = st.columns([2,1])
            with c1:
                st.altair_chart(alt.Chart(df_income).mark_bar().encode(x='Tháng', y='sum(Số Tiền)', color='Loại', tooltip=['Tháng', 'sum(Số Tiền)']), use_container_width=True)
            with c2:
                st.altair_chart(alt.Chart(df_income).mark_arc().encode(theta='sum(Số Tiền)', color='Loại', tooltip=['Loại', 'sum(Số Tiền)']), use_container_width=True)
            
            df_income = df_income.sort_values('Ngày', ascending=False)
            st.dataframe(df_income[['Ngày Hiển Thị', 'Mã CK', 'Loại', 'Số Tiền', 'Mô tả']], column_config={"Số Tiền": st.column_config.NumberColumn(format="%d đ")}, use_container_width=True)

    # TAB 3: STRESS TEST
    with t3:
        st.subheader("📉 Giả lập Sức chịu đựng (Stress Test)")
        st.write("Kịch bản: Nếu thị trường sập, tài sản của bạn sẽ biến động ra sao?")
        
        if total_nav == 0:
            st.warning("Chưa có dữ liệu tài sản để giả lập.")
        else:
            col_drop, col_cash = st.columns(2)
            with col_drop:
                drop_pct = st.slider("Mức độ thị trường sụt giảm (%):", 0, 50, 10, step=5)
            with col_cash:
                st.metric("Tỷ lệ Tiền mặt thực tế", f"{(cash/total_nav)*100:.1f}%", f"{cash:,.0f} VND")

            st.divider()
            
            projected_stock_val = stock_val * (1 - drop_pct/100)
            projected_nav = cash + projected_stock_val
            loss = total_nav - projected_nav
            
            c1, c2, c3 = st.columns(3)
            c1.metric("NAV Sau sụt giảm", f"{projected_nav:,.0f} VND", delta=f"-{loss:,.0f} VND", delta_color="inverse")
            c2.metric("Giá trị Cổ phiếu còn lại", f"{projected_stock_val:,.0f} VND")
            
            new_cash_ratio = (cash / projected_nav) * 100 if projected_nav > 0 else 0
            c3.metric("Tỷ lệ Tiền mặt mới", f"{new_cash_ratio:.1f}%", delta=f"+{new_cash_ratio - (cash/total_nav)*100:.1f}%")

            st.info(f"💡 **Nhận định:** Nếu thị trường giảm **{drop_pct}%**, bạn sẽ bốc hơi **{loss:,.0f} VND**. "
                    f"Tuy nhiên, tỷ lệ tiền mặt của bạn sẽ tăng lên **{new_cash_ratio:.1f}%**, tạo cơ hội để bắt đáy (Rebalancing).")

            sim_data = pd.DataFrame({
                'Trạng thái': ['Hiện tại', 'Sau sụt giảm'],
                'Tiền': [cash, cash],
                'Cổ phiếu': [stock_val, projected_stock_val]
            })
            sim_melt = sim_data.melt('Trạng thái', var_name='Loại TS', value_name='Giá trị')
            
            st.altair_chart(
                alt.Chart(sim_melt).mark_bar().encode(
                    x='Trạng thái', 
                    y='Giá trị', 
                    color='Loại TS',
                    tooltip=['Trạng thái', 'Loại TS', alt.Tooltip('Giá trị', format=',.0f')]
                ).properties(height=300),
                use_container_width=True
            )