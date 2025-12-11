# File: processors/adapter_vps.py
import pandas as pd
import re
from datetime import datetime, timedelta
from collections import defaultdict

class VPSAdapter:
    def parse(self, file_path):
        events = []
        buy_aggregator = defaultdict(lambda: {'cost': 0.0, 'qty': 0.0})
        balance_history = [] # Lưu lịch sử số dư
        
        try:
            xls = pd.ExcelFile(file_path)
            sheet_map = {s.lower(): s for s in xls.sheet_names}

            # =================================================================
            # 1. QUÉT SHEET TIỀN
            # =================================================================
            sh_tien = next((sheet_map[s] for s in sheet_map if 'tiền' in s or 'cash' in s), None)
            if sh_tien:
                df_t = pd.read_excel(xls, sheet_name=sh_tien)
                df_t.columns = [str(c).strip().lower() for c in df_t.columns]
                
                c_desc = next((c for c in df_t.columns if 'mô tả' in c or 'nội dung' in c), None)
                c_out = next((c for c in df_t.columns if 'giảm' in c), None) 
                c_in = next((c for c in df_t.columns if 'tăng' in c), None)  
                c_date = next((c for c in df_t.columns if 'ngày' in c), None)
                
                # CỘT SỐ DƯ (QUAN TRỌNG)
                c_bal = next((c for c in df_t.columns if 'số dư' in c or 'balance' in c), None)

                if c_desc:
                    for _, row in df_t.iterrows():
                        try:
                            desc = str(row.get(c_desc, '')).strip()
                            desc_lower = desc.lower()
                            val_out = self.clean_num(row.get(c_out, 0))
                            val_in = self.clean_num(row.get(c_in, 0))
                            d_obj = self.extract_date(row.get(c_date))
                            if not d_obj: continue
                            
                            d_str = d_obj.strftime('%Y-%m-%d')

                            # --- LẤY SỐ DƯ (SNAPSHOT) ---
                            if c_bal:
                                val_bal = self.clean_num(row.get(c_bal, 0))
                                balance_history.append({'date': d_obj, 'val': val_bal})

                            # --- A. MUA & RÚT TIỀN ---
                            if val_out > 0:
                                # 1. GOM GIÁ VỐN MUA
                                if "mua" in desc_lower:
                                    m_buy = re.search(r"mua\s.*?(\d+)\s*([A-Za-z0-9_]+)", desc, re.IGNORECASE)
                                    if m_buy:
                                        qty = float(m_buy.group(1))
                                        sym = m_buy.group(2).upper()
                                        if "trả tiền mua" in desc_lower or desc_lower.startswith("mua "):
                                            buy_aggregator[(sym, d_str)]['qty'] += qty
                                            buy_aggregator[(sym, d_str)]['cost'] += val_out
                                        elif "trả phí mua" in desc_lower or "phi mua" in desc_lower:
                                            buy_aggregator[(sym, d_str)]['cost'] += val_out
                                
                                # 2. RÚT TIỀN (Chỉ để trừ Tổng Nạp, không ảnh hưởng Tiền Mặt vì đã có Snapshot)
                                is_withdraw = False
                                if any(k in desc_lower for k in ['rút tiền', 'rut tien', 'chuyen tien ra', 'chuyển tiền ra']): is_withdraw = True
                                if 'chuyen tien' in desc_lower and 'mua' not in desc_lower and 'phi' not in desc_lower: is_withdraw = True
                                if is_withdraw:
                                    events.append({'date': d_obj, 'type': 'DEPOSIT', 'val': -val_out, 'source': 'VPS'})

                            # --- B. NẠP TIỀN & CỔ TỨC ---
                            if val_in > 0:
                                # 1. NẠP TIỀN
                                if any(k in desc_lower for k in ['cashin', 'nộp tiền', 'nop tien', 'chuyen tien vao']):
                                    if 'nhận tiền bán' not in desc_lower and 'hoàn' not in desc_lower:
                                        events.append({'date': d_obj, 'type': 'DEPOSIT', 'val': val_in, 'source': 'VPS'})

                                # 2. CỔ TỨC
                                if any(k in desc_lower for k in ['cổ tức', 'co tuc', 'div', 'lãi', 'quyền']):
                                    if any(x in desc_lower for x in ['tiền gửi', 'không kỳ hạn', 'số dư', 'kỳ hạn']): continue 
                                    m_sym = re.search(r"\b([A-Z0-9]{3})\b", desc.upper())
                                    sym = m_sym.group(1) if m_sym else "UNKNOWN"
                                    if sym != "UNKNOWN":
                                        events.append({'date': d_obj, 'sym': sym, 'type': 'DIVIDEND', 'val': val_in, 'source': 'VPS'})

                        except: continue

            # TÍNH GIÁ VỐN
            price_map = {} 
            for (sym, d_str), data in buy_aggregator.items():
                if data['qty'] > 0: price_map[(sym, d_str)] = data['cost'] / data['qty']

            # =================================================================
            # 2. QUÉT SHEET CP
            # =================================================================
            sh_cp = next((sheet_map[s] for s in sheet_map if 'cp' in s or 'ck' in s), None)
            if sh_cp:
                df_cp = pd.read_excel(xls, sheet_name=sh_cp)
                df_cp.columns = [str(c).strip().lower() for c in df_cp.columns]
                c_date = next((c for c in df_cp.columns if 'ngày' in c), None)
                c_sym = next((c for c in df_cp.columns if 'mã' in c), None)
                c_desc = next((c for c in df_cp.columns if 'mô tả' in c or 'nội dung' in c), None)
                c_in = next((c for c in df_cp.columns if 'tăng' in c), None)
                c_out = next((c for c in df_cp.columns if 'giảm' in c), None)

                if c_sym:
                    for _, row in df_cp.iterrows():
                        try:
                            sym = str(row.get(c_sym, '')).strip().upper()
                            val_in = self.clean_num(row.get(c_in, 0))
                            val_out = self.clean_num(row.get(c_out, 0))
                            desc = str(row.get(c_desc, '')).lower()
                            d_obj = self.extract_date(row.get(c_date))
                            if not d_obj: continue

                            if val_in > 0:
                                price = 0
                                is_zero = False
                                zero_keys = ['thưởng', 'cổ tức', 'chuyển đổi', 'nhận', 'phát hành thêm', 'quyền mua', 'bonus']
                                if sym.endswith('_WFT') or any(k in desc for k in zero_keys): is_zero = True
                                if not is_zero:
                                    for delta in range(-5, 6):
                                        chk_d = d_obj + timedelta(days=delta)
                                        k = (sym, chk_d.strftime('%Y-%m-%d'))
                                        if k in price_map: price = price_map[k]; break
                                events.append({'date': d_obj, 'sym': sym, 'type': 'BUY', 'vol': val_in, 'price': price, 'fee': 0, 'source': 'VPS_CP'})

                            if val_out > 0:
                                events.append({'date': d_obj, 'sym': sym, 'type': 'SELL', 'vol': val_out, 'price': 0, 'fee': 0, 'source': 'VPS_CP', 'use_external_pnl': True})
                        except: continue

            # =================================================================
            # 3. QUÉT SHEET LÃI LỖ
            # =================================================================
            sh_ll = next((sheet_map[s] for s in sheet_map if 'lãi' in s and 'lỗ' in s), None)
            if sh_ll:
                df_ll = pd.read_excel(xls, sheet_name=sh_ll)
                df_ll.columns = [str(c).strip().lower() for c in df_ll.columns]
                c_date = next((c for c in df_ll.columns if 'ngày' in c), None)
                c_sym = next((c for c in df_ll.columns if 'mã' in c), None)
                c_pl = next((c for c in df_ll.columns if 'lãi' in c and 'lỗ' in c and '%' not in c), None)

                if c_sym and c_pl:
                    for _, row in df_ll.iterrows():
                        try:
                            val_pl = self.clean_num(row.get(c_pl, 0))
                            if val_pl == 0: continue
                            sym = str(row[c_sym]).strip().upper()
                            d_obj = self.extract_date(row.get(c_date))
                            if not d_obj: d_obj = datetime.now()
                            events.append({'date': d_obj, 'sym': sym, 'type': 'PNL_UPDATE', 'val': val_pl, 'source': 'VPS_PROFIT'})
                        except: continue

        except Exception as e: print(f"❌ Lỗi đọc file VPS: {e}")
            
        # 4. CHỐT SỐ DƯ CUỐI CÙNG
        cash_event = []
        if balance_history:
            # Sort ngày giảm dần để lấy số mới nhất
            balance_history.sort(key=lambda x: x['date'], reverse=True)
            latest_balance = balance_history[0]['val']
            cash_event.append({
                'date': datetime.now(),
                'type': 'CASH_SNAPSHOT',
                'val': latest_balance,
                'source': 'VPS_LEDGER'
            })

        # SẮP XẾP SỰ KIỆN
        if not events: return []
        df_ev = pd.DataFrame(events)
        type_prio = {'DEPOSIT': 1, 'BUY': 2, 'SELL': 3, 'PNL_UPDATE': 4, 'DIVIDEND': 5}
        df_ev['prio'] = df_ev['type'].map(type_prio).fillna(99)
        # return events + snapshot
        return df_ev.sort_values(by=['date', 'prio']).to_dict('records') + cash_event

    # --- HÀM HỖ TRỢ ---
    def clean_num(self, val):
        if pd.isna(val) or str(val).strip() == '': return 0.0
        try: return float(str(val).replace(',', '').replace(' ', ''))
        except: return 0.0
    
    def extract_date(self, val):
        if isinstance(val, datetime): return val
        if isinstance(val, str):
            val = val.strip()
            for fmt in ['%d/%m/%Y', '%Y-%m-%d', '%d-%m-%Y']:
                try: return datetime.strptime(val.split(' ')[0], fmt)
                except: pass
        return None