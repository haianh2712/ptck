# File: patch_dividend_fix.py
# Version: FINAL V2 - UPDATE INVENTORY COST
# Chức năng: 
# 1. Cộng tiền cổ tức vào Lãi/Lỗ Cycle (Trading PnL)
# 2. Hạ giá vốn (Adjusted Cost) trong Inventory để tính Vốn Hợp Lý chính xác

import pandas as pd
import re
from datetime import datetime

def extract_dividend_info(content):
    """
    Trích xuất ngày NDKCC và Tỷ lệ từ nội dung chuyển tiền.
    """
    if not isinstance(content, str):
        return None
    
    # Regex bắt ngày (dd/mm/yyyy hoặc dd-mm-yyyy)
    date_match = re.search(r'NDKCC:\s*(\d{2}[/-]\d{2}[/-]\d{4})', content, re.IGNORECASE)
    
    # Regex bắt tỷ lệ
    rate_match = re.search(r'ty le:\s*(\d+(\.\d+)?)%', content, re.IGNORECASE)
    
    if date_match and rate_match:
        try:
            date_str = date_match.group(1).replace('-', '/')
            ex_date = datetime.strptime(date_str, '%d/%m/%Y').date()
            rate_percent = float(rate_match.group(1))
            return {
                'ex_date': ex_date,
                'rate_val': rate_percent * 100, # Mệnh giá 10k
                'raw_text': content
            }
        except:
            return None
    return None

def apply_dividend_patch(portfolio_engine, file_object):
    print("\n" + "="*60)
    print("🛠️ BẮT ĐẦU QUY TRÌNH VÁ CỔ TỨC & ĐIỀU CHỈNH GIÁ VỐN")
    print("="*60)
    
    try:
        # 1. ĐỌC DỮ LIỆU
        file_object.seek(0)
        xls = pd.ExcelFile(file_object)
        sheet_map = {s.lower(): s for s in xls.sheet_names}
        sh_tien = next((sheet_map[s] for s in sheet_map if 'tiền' in s or 'cash' in s), None)
        
        if not sh_tien:
            print("⚠️ Không tìm thấy Sheet Tiền.")
            return

        df_cash = pd.read_excel(xls, sheet_name=sh_tien)
        
        # Tìm cột
        df_cash.columns = [str(c).lower().strip() for c in df_cash.columns]
        col_content = next((c for c in df_cash.columns if 'nội dung' in c or 'content' in c), None)
        col_symbol = next((c for c in df_cash.columns if 'mã' in c or 'symbol' in c), None)

        # 2. MAP SỰ KIỆN
        dividend_map = {} 
        for _, row in df_cash.iterrows():
            content = row[col_content]
            info = extract_dividend_info(content)
            
            if info:
                symbol = None
                if col_symbol and pd.notna(row[col_symbol]):
                    symbol = str(row[col_symbol]).upper().strip()
                else:
                    sym_match = re.search(r'(?:ma|ck):\s*([A-Z0-9]+)', str(content), re.IGNORECASE)
                    if sym_match:
                        symbol = sym_match.group(1).upper()
                
                if symbol:
                    if symbol not in dividend_map: dividend_map[symbol] = []
                    dividend_map[symbol].append(info)

        # 3. QUÉT VÀ VÁ LỖI
        count_patched = 0
        
        for symbol, data in portfolio_engine.data.items():
            if symbol not in dividend_map:
                continue
            
            # Gom Cycle
            all_cycles_to_check = []
            for c in data.get('closed_cycles', []):
                c['_is_active'] = False
                all_cycles_to_check.append(c)
                
            if data.get('current_cycle'):
                curr = data['current_cycle']
                curr['_is_active'] = True
                curr['temp_end_date'] = curr.get('end_date').date() if curr.get('end_date') else datetime.now().date()
                all_cycles_to_check.append(curr)

            # --- LOOP CÁC CYCLES ---
            for cycle in all_cycles_to_check:
                c_start = cycle['start_date'].date()
                c_end = cycle.get('end_date').date() if (cycle.get('end_date') and pd.notna(cycle.get('end_date'))) else datetime.now().date()
                
                is_cycle_patched = False

                for div_event in dividend_map[symbol]:
                    d_date = div_event['ex_date']
                    
                    # Điều kiện: Ngày GDKHQ nằm trong thời gian giữ lệnh
                    if c_start <= d_date <= c_end:
                        
                        # A. TÍNH TOÁN CỘNG TIỀN (PNL)
                        vol_calc = 0
                        if cycle.get('total_buy_vol', 0) > 0: vol_calc = cycle['total_buy_vol']
                        elif cycle.get('volume', 0) > 0: vol_calc = cycle['volume']
                        
                        amt = 0
                        if vol_calc > 0:
                            amt = vol_calc * div_event['rate_val']
                            old_div = cycle.get('dividend_pl', 0.0)
                            
                            # Update PnL nếu chưa đủ
                            if old_div < amt:
                                cycle['dividend_pl'] = amt
                                cycle['total_pl'] = cycle.get('trading_pl', 0.0) + amt
                                if cycle.get('_is_active'):
                                    data['stats']['total_dividend'] = max(data['stats']['total_dividend'], amt)
                                is_cycle_patched = True

                        # B. [MỚI] HẠ GIÁ VỐN TRONG KHO (INVENTORY) - QUAN TRỌNG CHO VỐN HỢP LÝ
                        # Chỉ áp dụng nếu đây là Cycle đang hoạt động (Active)
                        if cycle.get('_is_active'):
                            inventory = data.get('inventory', [])
                            for batch in inventory:
                                # Logic: Lô hàng này phải được mua TRƯỚC ngày GDKHQ mới được trừ giá vốn
                                if batch['date'].date() <= d_date:
                                    # Trừ giá vốn điều chỉnh (adj_cost)
                                    # Lưu ý: Mỗi lần chạy script là chạy mới từ đầu, nên trừ thẳng tay
                                    # Tuy nhiên để tránh trừ nhiều lần nếu có nhiều event trùng, ta cần cẩn thận.
                                    # Ở đây Engine reset mỗi lần chạy -> An toàn.
                                    
                                    # Debug
                                    # print(f"   📉 Giảm giá vốn {symbol}: {div_event['rate_val']}đ cho lô {batch['date'].date()}")
                                    batch['adj_cost'] -= div_event['rate_val']

                if is_cycle_patched:
                    status = "ĐANG GIỮ" if cycle.get('_is_active') else "ĐÃ CHỐT"
                    # print(f"✅ [PATCHED] {symbol} ({status}) | +{amt:,.0f}đ")
                    count_patched += 1

    except Exception as e:
        print(f"⚠️ Lỗi Patch: {e}")

    print(f"HOÀN TẤT. ĐÃ CẬP NHẬT {count_patched} LỆNH.")
    print(f"="*60 + "\n")