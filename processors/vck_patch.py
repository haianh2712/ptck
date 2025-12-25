# File: processors/vck_patch.py
# Version: FINAL PRODUCTION (Logic: Robust Column Search + Anti-Noise Fee + T+15 Tolerance)

import pandas as pd
import re
from datetime import datetime

class VCKPatch:
    def __init__(self):
        # Regex tìm lệnh mua
        self.regex_missing_buy = r"mua\s+([a-zA-Z0-9]+).*?kl:\s*([\d,]+).*?gia:\s*([\d,]+)"

    def clean_num(self, val):
        if pd.isna(val): return 0.0
        if isinstance(val, (int, float)): return float(val)
        try:
            return float(str(val).replace(',', '').replace(' ', ''))
        except: return 0.0

    def apply_patch(self, original_events, file_path_or_df):
        # 1. Đọc dữ liệu linh hoạt (Hỗ trợ cả DataFrame và Path)
        df = None
        if isinstance(file_path_or_df, pd.DataFrame):
            df = file_path_or_df
        else:
            try:
                try: df = pd.read_excel(file_path_or_df, engine='openpyxl')
                except: df = pd.read_excel(file_path_or_df)
            except: 
                try: df = pd.read_csv(file_path_or_df)
                except: return original_events

        # 2. Tìm cột thông minh (Robust Column Search)
        cols_lower = [str(c).lower().strip() for c in df.columns]
        def get_col(keywords):
            for i, c in enumerate(cols_lower):
                if any(k in c for k in keywords): return df.columns[i]
            return None

        desc_col = get_col(['diễn giải', 'nội dung', 'mo ta', 'description'])
        date_col = get_col(['ngày', 'date', 'thời gian'])
        val_col  = get_col(['ghi nợ', 'debit', 'ps giảm', 'chi', 'giảm'])

        if not (desc_col and val_col and date_col):
            return original_events

        # 3. Quét Regex tìm lệnh mua tiềm năng
        missing_buys = []
        for _, row in df.iterrows():
            val = self.clean_num(row[val_col])
            
            if val > 0: # Chỉ xử lý dòng tiền ra
                desc = str(row[desc_col])
                match = re.search(self.regex_missing_buy, desc.lower())
                if match:
                    qty = float(match.group(2).replace(',', ''))
                    price_raw = float(match.group(3).replace(',', ''))
                    
                    # --- BỘ LỌC PHÍ (ANTI-NOISE FEE FILTER) ---
                    theoretical_val = qty * price_raw
                    # Nếu giá trị thực tế < 10% giá trị lý thuyết -> Là Phí -> Bỏ qua
                    if theoretical_val > 0 and (val / theoretical_val) < 0.1:
                        continue 
                    # ------------------------------------------

                    ticker = match.group(1).upper()
                    price = price_raw
                    if price == 0 and qty > 0: price = val / qty

                    d_obj = row[date_col]
                    if not isinstance(d_obj, datetime):
                        try: d_obj = pd.to_datetime(d_obj, dayfirst=True)
                        except: continue
                    
                    if d_obj:
                        missing_buys.append({
                            'date': d_obj, 'value': val, 'ticker': ticker,
                            'qty': qty, 'price': price
                        })

        # 4. HỢP NHẤT THÔNG MINH (SMART MERGE - T+15 TOLERANCE)
        new_events = original_events.copy()

        for buy_cmd in missing_buys:
            is_already_captured = False
            target_event_index = -1

            for i, ev in enumerate(new_events):
                # Tính độ lệch ngày tuyệt đối
                t_diff_seconds = abs((ev.get('date') - buy_cmd['date']).total_seconds()) if ev.get('date') else 9999999
                
                # [QUAN TRỌNG] Chấp nhận lệch tối đa 15 ngày (1,300,000 giây)
                if t_diff_seconds < 1300000: 
                    
                    # CASE A: Adapter đã bắt đúng (Trùng Ticker + Trùng Qty) -> BỎ QUA
                    if (ev.get('type') == 'BUY' and 
                        ev.get('ticker') == buy_cmd['ticker'] and 
                        abs(ev.get('qty', 0) - buy_cmd['qty']) < 1):
                        is_already_captured = True
                        break 
                    
                    # CASE B: Adapter bắt nhầm là RUT_TIEN (Trùng Value) -> ĐÁNH DẤU ĐỂ SỬA
                    val_diff = abs(ev.get('value', 0) - buy_cmd['value'])
                    if (ev.get('type') != 'BUY' and val_diff < 50):
                        target_event_index = i
                        break
            
            if is_already_captured:
                continue # Skip

            if target_event_index != -1:
                # Sửa từ RUT_TIEN thành BUY
                ev = new_events[target_event_index]
                ev.update({
                    'type': 'BUY',
                    'ticker': buy_cmd['ticker'],
                    'qty': buy_cmd['qty'],
                    'price': buy_cmd['price'],
                    'source': 'VCK_PATCHED'
                })
            else:
                # Thêm mới (khi chắc chắn ko trùng trong vòng 15 ngày)
                new_events.append({
                    'date': buy_cmd['date'],
                    'type': 'BUY',
                    'ticker': buy_cmd['ticker'],
                    'qty': buy_cmd['qty'],
                    'price': buy_cmd['price'],
                    'value': buy_cmd['value'],
                    'source': 'VCK_PATCH_NEW',
                    'prio': 2
                })

        return new_events