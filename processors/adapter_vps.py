# File: processors/adapter_vps.py
# Version: V6 FINAL - ROBUST NUMBER PARSER (FIX DOT/COMMA FORMATTING)
import pandas as pd
import re
from datetime import datetime, timedelta
from collections import defaultdict

class VPSAdapter:
    def __init__(self):
        self.ipo_pending_bucket = defaultdict(float)
        self.buy_aggregator = defaultdict(lambda: {'cost': 0.0, 'qty': 0.0})

    def parse(self, file_path):
        events = []
        self.ipo_pending_bucket.clear()
        self.buy_aggregator.clear()

        try:
            xls = pd.ExcelFile(file_path)
            sheet_map = {s.lower(): s for s in xls.sheet_names}

            # =================================================================
            # PHẦN 1: QUÉT SHEET TIỀN
            # =================================================================
            sh_tien = next((sheet_map[s] for s in sheet_map if 'tiền' in s or 'cash' in s), None)
            if sh_tien:
                df_t = pd.read_excel(xls, sheet_name=sh_tien)
                df_t = df_t.iloc[::-1] 
                df_t.columns = [str(c).strip().lower() for c in df_t.columns]
                
                c_desc = next((c for c in df_t.columns if 'mô tả' in c or 'nội dung' in c), None)
                c_out = next((c for c in df_t.columns if 'giảm' in c or 'debit' in c), None) 
                c_in = next((c for c in df_t.columns if 'tăng' in c or 'credit' in c), None)  
                c_date = next((c for c in df_t.columns if 'ngày' in c), None)
                c_bal = next((c for c in df_t.columns if 'số dư' in c or 'balance' in c), None)

                if c_desc:
                    for _, row in df_t.iterrows():
                        try:
                            desc = str(row.get(c_desc, '')).strip()
                            desc_raw_lower = desc.lower()
                            desc_lower = self.remove_accents(desc).lower()
                            
                            val_out = self.clean_num(row.get(c_out, 0))
                            val_in = self.clean_num(row.get(c_in, 0))
                            
                            d_obj = self.extract_date(row.get(c_date))
                            if not d_obj: continue
                            d_str = d_obj.strftime('%Y-%m-%d')

                            # --- [MODULE 1] INTERCEPTOR ---
                            
                            if val_out > 0:
                                # 1.1. IPO / Quyền mua
                                ipo_keywords = ['nop tien dang ky mua', 'dang ky mua phat hanh them', 'nop tien thuc hien quyen', 'nop tien dat coc', 'thuc hien quyen mua', 'register to buy']
                                if any(k in desc_lower for k in ipo_keywords):
                                    m_sym = re.search(r"(?:cp|mã|quyền|ck|stocks)\s*([a-zA-Z0-9]{3,})", desc_lower)
                                    if not m_sym: m_sym = re.search(r"\b([A-Z]{3})\b", desc)
                                    ticker_wft = "UNKNOWN_WFT"
                                    if m_sym:
                                        raw_ticker = m_sym.group(1).upper()
                                        ticker_wft = raw_ticker + '_WFT' if not raw_ticker.endswith('_WFT') else raw_ticker
                                    
                                    self.ipo_pending_bucket[ticker_wft] += val_out
                                    events.append({'date': d_obj, 'type': 'IPO_PAYMENT', 'value': val_out, 'ticker': ticker_wft, 'desc': desc})
                                    continue 

                                # 1.2. Hoàn Ứng / Trả nợ UTTB
                                refund_out_keys = ['hoan tra uttb', 'thu no', 'tra no', 'uttb', 'hoan ung', 'refund advanced']
                                if any(k in desc_lower for k in refund_out_keys): continue 

                                # 1.3. Phí & Thuế
                                fee_keywords = ['phi ', 'thue ', 'transaction fee', 'tax ', 'tra phi', 'phi luu ky'] 
                                if any(k in desc_lower for k in fee_keywords):
                                    events.append({'date': d_obj, 'type': 'FEE', 'value': val_out, 'desc': desc})
                                    continue 

                            if val_in > 0:
                                # 1.4. Nhận Ứng Trước / Hoàn Tiền
                                refund_in_keys = ['hoan tra', 'nhan lai tien', 'hoan tien', 'uttb', 'ung truoc']
                                if any(k in desc_lower for k in refund_in_keys): continue 

                            # --- [MODULE 2] LOGIC THƯỜNG ---
                            
                            if c_bal:
                                val_bal = self.clean_num(row.get(c_bal, 0))
                                events.append({'date': d_obj, 'type': 'CASH_SNAPSHOT', 'value': val_bal})

                            if val_out > 0:
                                withdraw_keys = ['rut tien', 'chuyen tien ra', 'chuyen khoan ra']
                                if any(k in desc_lower for k in withdraw_keys):
                                    events.append({'date': d_obj, 'type': 'WITHDRAW', 'value': val_out})
                                
                                elif "mua" in desc_lower: 
                                    # CHỐT CHẶN CỨNG: Loại bỏ dòng Phí/Thuế
                                    blacklist = ['phí', 'thuế', 'fee', 'tax', 'phi ', 'thue '] 
                                    if any(b in desc_raw_lower for b in blacklist) or any(b in desc_lower for b in blacklist):
                                        pass 
                                    else:
                                        m_buy = re.search(r"mua\s.*?([\d.,]+)\s*([A-Za-z0-9_]+)", desc, re.IGNORECASE)
                                        if m_buy:
                                            qty_str = m_buy.group(1).replace('.', '').replace(',', '')
                                            try:
                                                qty = float(qty_str)
                                                sym = m_buy.group(2).upper()
                                                if qty > 0:
                                                    self.buy_aggregator[(sym, d_str)]['qty'] += qty
                                                    self.buy_aggregator[(sym, d_str)]['cost'] += val_out
                                            except: pass

                            if val_in > 0:
                                deposit_keys = ['nop tien vao', 'chuyen tien vao', 'cashin', 'nop tien mat']
                                exclude_dep = ['nhan tien ban', 'tien ban ck', 'hoan tra', 'hoan tien', 'hoan ung', 'nop tien mua']
                                if any(k in desc_lower for k in deposit_keys):
                                    if not any(e in desc_lower for e in exclude_dep):
                                        events.append({'date': d_obj, 'type': 'DEPOSIT', 'value': val_in})
                                elif any(k in desc_lower for k in ['co tuc', 'div', 'lai', 'quyen']):
                                    if not any(x in desc_lower for x in ['tien gui', 'khong ky han', 'so du', 'ky han']): 
                                        m_sym = re.search(r"\b([A-Z0-9]{3})\b", desc.upper())
                                        sym = m_sym.group(1) if m_sym else "UNKNOWN"
                                        events.append({'date': d_obj, 'ticker': sym, 'type': 'DIVIDEND', 'value': val_in})

                        except Exception: continue

            price_map_normal = {} 
            for (sym, d_str), data in self.buy_aggregator.items():
                if data['qty'] > 0: price_map_normal[(sym, d_str)] = data['cost'] / data['qty']

            # PHẦN 2: QUÉT SHEET KHO
            sh_cp = next((sheet_map[s] for s in sheet_map if 'cp' in s or 'ck' in s or 'kho' in s), None)
            if sh_cp:
                df_cp = pd.read_excel(xls, sheet_name=sh_cp)
                df_cp = df_cp.iloc[::-1]
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

                            # IPO (Module 1)
                            if val_in > 0 and sym in self.ipo_pending_bucket:
                                pending_money = self.ipo_pending_bucket[sym]
                                if pending_money > 0:
                                    price_ipo = pending_money / val_in
                                    events.append({'date': d_obj, 'ticker': sym, 'type': 'BUY', 'qty': val_in, 'price': price_ipo, 'value': pending_money, 'source': 'IPO_MATCHED'})
                                    self.ipo_pending_bucket[sym] = 0 
                                    continue 

                            # Mua thường (Module 2)
                            if val_in > 0:
                                price = 0
                                is_zero_cost = False
                                zero_keys = ['thưởng', 'cổ tức', 'chuyển đổi', 'nhận', 'phát hành thêm', 'bonus']
                                if any(k in desc for k in zero_keys) and "quyen mua" not in desc: is_zero_cost = True
                                
                                if not is_zero_cost:
                                    sym_lookup = sym.replace('_WFT', '')
                                    search_order = sorted(range(-10, 11), key=abs) 
                                    for delta in search_order:
                                        chk_d = d_obj + timedelta(days=delta)
                                        k = (sym_lookup, chk_d.strftime('%Y-%m-%d'))
                                        if k in price_map_normal: 
                                            price = price_map_normal[k]; break
                                
                                total_val = val_in * price
                                events.append({'date': d_obj, 'ticker': sym, 'type': 'BUY', 'qty': val_in, 'price': price, 'value': total_val})

                            if val_out > 0:
                                events.append({'date': d_obj, 'ticker': sym, 'type': 'SELL', 'qty': val_out, 'price': 0, 'value': 0, 'use_external_pnl': True})
                        except: continue

            # PHẦN 3: QUÉT SHEET LÃI LỖ
            sh_ll = next((sheet_map[s] for s in sheet_map if 'lãi' in s and 'lỗ' in s), None)
            if sh_ll:
                df_ll = pd.read_excel(xls, sheet_name=sh_ll)
                df_ll.columns = [str(c).strip().lower() for c in df_ll.columns]
                c_date = next((c for c in df_ll.columns if 'ngày' in c), None)
                c_sym = next((c for c in df_ll.columns if 'mã' in c), None)
                c_pl = next((c for c in df_ll.columns if 'lãi' in c and 'lỗ' in c and '%' not in c), None)

                if c_sym and c_pl:
                    for _, row in df_ll.iterrows():
                        val_pl = self.clean_num(row.get(c_pl, 0))
                        sym = str(row.get(c_sym, '')).strip().upper()
                        if val_pl == 0: continue
                        d_obj = self.extract_date(row.get(c_date)) or datetime.now()
                        events.append({'date': d_obj, 'ticker': sym, 'type': 'PNL_UPDATE', 'value': val_pl})

        except Exception as e: return []
            
        if not events: return []
        df_ev = pd.DataFrame(events)
        type_prio = {'DEPOSIT': 1, 'IPO_PAYMENT': 2, 'WITHDRAW': 3, 'BUY': 4, 'SELL': 5, 'PNL_UPDATE': 6, 'DIVIDEND': 7, 'CASH_SNAPSHOT': 99}
        df_ev['prio'] = df_ev['type'].map(type_prio).fillna(50)
        return df_ev.sort_values(by=['date', 'prio']).to_dict('records')

    # --- [NEW] ROBUST NUMBER PARSER ---
    def clean_num(self, val):
        if pd.isna(val): return 0.0
        s = str(val).strip()
        if not s: return 0.0
        if s.startswith('(') and s.endswith(')'): s = '-' + s[1:-1]
        
        # Xóa các ký tự tiền tệ/chữ thừa, chỉ giữ lại số và dấu
        s = re.sub(r'[^\d.,-]', '', s)
        
        # Cách 1: Thử parse số chuẩn (VD: 1234 hoặc 1234.56)
        try: return float(s)
        except: pass
        
        # Cách 2: Thử parse kiểu Mỹ (có dấu phẩy 1,234.56) -> Xóa phẩy
        try: return float(s.replace(',', ''))
        except: pass
        
        # Cách 3: Thử parse kiểu VN (có dấu chấm 1.234.567) -> Xóa chấm, đổi phẩy thành chấm
        try: return float(s.replace('.', '').replace(',', '.'))
        except: pass
        
        return 0.0
    
    def extract_date(self, val):
        if isinstance(val, datetime): return val
        if isinstance(val, str):
            val = val.strip()
            for fmt in ['%d/%m/%Y', '%Y-%m-%d', '%d-%m-%Y', '%d-%b-%y']:
                try: return datetime.strptime(val.split(' ')[0], fmt)
                except: pass
        return None

    def remove_accents(self, input_str):
        if not input_str: return ""
        s1 = u'ÀÁÂÃÈÉÊÌÍÒÓÔÕÙÚÝàáâãèéêìíòóôõùúýĂăĐđĨĩŨũƠơƯưẠạẢảẤấẦầẨẩẪẫẬậẮắẰằẲẳẴẵẶặẸẹẺẻẼẽẾếỀềỂểỄễỆệỈỉỊịỌọỎỏỐốỒồỔổỖỗỘộỚớỜờỞởỠỡỢợỤụỦủỨứỪừỬửỮữỰựỲỳỴỵỶỷỸỹ'
        s0 = u'AAAAEEEIIOOOUUYaaaaeeeiiooouuyAaDdIiUuOoUuAaAaAaAaAaAaAaAaAaAaAaAaEeEeEeEeEeEeEeEeIiIiOoOoOoOoOoOoOoOoOoOoOoOoUuUuUuUuUuUuUuYyYyYyYy'
        s = ''
        input_str = str(input_str)
        for c in input_str:
            if c in s1: s += s0[s1.index(c)]
            else: s += c
        return s