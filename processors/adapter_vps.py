# File: processors/adapter_vps.py
# Version: V15 OFFICIAL - THREE PATHS LOGIC (UPDATED FROM V8.1)
import pandas as pd
import re
from datetime import datetime, timedelta
from collections import defaultdict

class VPSAdapter:
    def __init__(self):
        # [NEW] Két sắt LUỒNG 2: Mua Quyền (Lưu chi tiết để khớp số lượng)
        self.rights_vault = defaultdict(list) 
        # [NEW] Két sắt LUỒNG 3: IPO (Chỉ cộng dồn tiền)
        self.ipo_accumulator = defaultdict(float)
        
        self.buy_aggregator = defaultdict(lambda: {'cost': 0.0, 'qty': 0.0})
        # Cache giá WFT cho chuyển đổi
        self.wft_price_cache = {}

    # --- 1. HELPERS (GIỮ NGUYÊN V8.1) ---
    def clean_num(self, val):
        if pd.isna(val): return 0.0
        s = str(val).strip()
        s = re.sub(r'[^\d.,-]', '', s)
        try: return float(s.replace(',', ''))
        except: pass
        try: return float(s.replace('.', '').replace(',', '.'))
        except: pass
        return 0.0
    
    def extract_date(self, val):
        if isinstance(val, datetime): return val
        if isinstance(val, pd.Timestamp): return val.to_pydatetime()
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
        return s.lower()

    def parse(self, file_path):
        events = []
        # Reset các két tiền
        self.rights_vault.clear()
        self.ipo_accumulator.clear()
        self.buy_aggregator.clear()
        self.wft_price_cache.clear()

        try:
            xls = pd.ExcelFile(file_path)
            sheet_map = {s.lower(): s for s in xls.sheet_names}

            # =================================================================
            # BƯỚC 1: QUÉT SHEET TIỀN (PHÂN LOẠI VÀO 2 KÉT)
            # =================================================================
            sh_tien = next((sheet_map[s] for s in sheet_map if 'tiền' in s or 'cash' in s), None)
            if sh_tien:
                df_t = pd.read_excel(xls, sheet_name=sh_tien).iloc[::-1]
                df_t.columns = [str(c).strip().lower() for c in df_t.columns]
                
                c_desc = next((c for c in df_t.columns if 'mô tả' in c or 'nội dung' in c), None)
                c_out = next((c for c in df_t.columns if 'giảm' in c or 'debit' in c), None)
                c_in = next((c for c in df_t.columns if 'tăng' in c or 'credit' in c), None)
                c_date = next((c for c in df_t.columns if 'ngày' in c), None)
                c_bal = next((c for c in df_t.columns if 'số dư' in c or 'balance' in c), None)

                if c_desc:
                    for _, row in df_t.iterrows():
                        try:
                            d_obj = self.extract_date(row.get(c_date))
                            if not d_obj: continue
                            
                            # --- [FIX QUAN TRỌNG] ĐỌC SỐ DƯ TRƯỚC (Để không bị lệnh continue bỏ qua) ---
                            if c_bal:
                                val_bal = self.clean_num(row.get(c_bal, 0))
                                # Thêm index phụ để đảm bảo sort đúng thứ tự nếu trùng ngày
                                events.append({'date': d_obj, 'type': 'CASH_SNAPSHOT', 'value': val_bal})
                            # --------------------------------------------------------------------------

                            desc = str(row.get(c_desc, '')).strip()
                            desc_lower = self.remove_accents(desc).lower() 
                            desc_raw_lower = desc.lower()
                            
                            val_out = self.clean_num(row.get(c_out, 0))
                            val_in = self.clean_num(row.get(c_in, 0))
                            d_str = d_obj.strftime('%Y-%m-%d')

                            # --- [UPDATE] LOGIC PHÂN LOẠI TIỀN ---
                            if val_out > 0:
                                # A. Nhận diện Mua Quyền (Rights) -> Có "issued more" + Số lượng
                                m_issued = re.search(r"issued more.*?([0-9]+)\s+([a-zA-Z0-9]{3})\b", desc, re.IGNORECASE)
                                if m_issued:
                                    qty = float(m_issued.group(1))
                                    ticker = m_issued.group(2).upper().replace('_WFT', '')
                                    # Lưu vào Két 2 (Rights)
                                    self.rights_vault[ticker].append({'date': d_obj, 'amount': val_out, 'expected_qty': qty})
                                    events.append({'date': d_obj, 'type': 'IPO_PAYMENT', 'value': val_out, 'ticker': ticker, 'desc': desc})
                                    continue

                                # B. Nhận diện Nộp tiền chung (IPO candidate) -> "nop tien"
                                # (Chỉ gom nếu không phải là dòng issued more để tránh trùng)
                                m_ipo = re.search(r"(?:nop tien|mua).*?([0-9]+)\s*(?:cp|co phieu)?\s*([a-zA-Z0-9]{3})\b", desc_lower, re.IGNORECASE)
                                if m_ipo and 'nop tien' in desc_lower:
                                    ticker = m_ipo.group(2).upper().replace('_WFT', '')
                                    # Lưu vào Két 3 (IPO Accumulator)
                                    self.ipo_accumulator[ticker] += val_out
                                    events.append({'date': d_obj, 'type': 'IPO_PAYMENT', 'value': val_out, 'ticker': ticker, 'desc': desc})
                                    continue

                                # C. Các loại phí/rút tiền (Giữ nguyên V8.1)
                                refund_out_keys = ['hoan tra uttb', 'thu no', 'tra no', 'uttb', 'hoan ung']
                                if any(k in desc_lower for k in refund_out_keys): continue 
                                fee_keywords = ['phi ', 'thue ', 'transaction fee', 'tax ', 'tra phi', 'phi luu ky'] 
                                if any(k in desc_lower for k in fee_keywords):
                                    events.append({'date': d_obj, 'type': 'FEE', 'value': val_out, 'desc': desc})
                                    continue 
                                withdraw_keys = ['rut tien', 'chuyen tien ra', 'chuyen khoan ra']
                                if any(k in desc_lower for k in withdraw_keys):
                                    events.append({'date': d_obj, 'type': 'WITHDRAW', 'value': val_out})
                                elif "mua" in desc_lower: 
                                    blacklist = ['phí', 'thuế', 'fee', 'tax', 'phi ', 'thue '] 
                                    if any(b in desc_raw_lower for b in blacklist) or any(b in desc_lower for b in blacklist): pass 
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

            # =================================================================
            # BƯỚC 2: KHỚP HÀNG (3 LUỒNG ƯU TIÊN)
            # =================================================================
            sh_cp = next((sheet_map[s] for s in sheet_map if 'cp' in s or 'ck' in s or 'kho' in s), None)
            if sh_cp:
                df_cp = pd.read_excel(xls, sheet_name=sh_cp).iloc[::-1]
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
                            desc = str(row.get(c_desc, '')).strip()
                            desc_norm = self.remove_accents(desc).lower()
                            d_obj = self.extract_date(row.get(c_date))
                            if not d_obj: continue

                            # --- [UPDATE] LOGIC 3 LUỒNG ---
                            if val_in > 0:
                                base_sym = sym.replace('_WFT', '')
                                
                                # LUỒNG 1: CỔ TỨC/THƯỞNG (PRIORITY CAO NHẤT)
                                bonus_keywords = ['co tuc', 'thuong', 'dividend', 'share', 'bonus', 'tra lai']
                                is_pure_bonus = any(k in desc_norm for k in bonus_keywords)
                                if is_pure_bonus:
                                    events.append({'date': d_obj, 'ticker': sym, 'type': 'BUY', 'qty': val_in, 'price': 0, 'value': 0, 'source': 'VPS_BONUS', 'desc': desc})
                                    continue 

                                # LUỒNG 2: MUA QUYỀN (KHỚP SỐ LƯỢNG)
                                rights_keywords = ['phat hanh them', 'quyen mua', 'phan bo', 'issued more']
                                is_rights_candidate = any(k in desc_norm for k in rights_keywords) or ('_WFT' in sym)

                                found_rights = False
                                if is_rights_candidate and base_sym in self.rights_vault:
                                    for i, pack in enumerate(self.rights_vault[base_sym]):
                                        # Khớp số lượng chính xác (sai số < 1)
                                        if abs(val_in - pack['expected_qty']) < 1.0:
                                            price = pack['amount'] / val_in
                                            events.append({
                                                'date': d_obj, 'ticker': sym, 'type': 'BUY', 'qty': val_in, 
                                                'price': price, 'value': pack['amount'], 
                                                'source': 'VPS_RIGHTS_MATCHED', 'desc': desc
                                            })
                                            self.wft_price_cache[base_sym] = price # Lưu cache
                                            self.rights_vault[base_sym].pop(i) # Xóa gói tiền
                                            found_rights = True
                                            break
                                if found_rights: continue

                                # LUỒNG 3: MUA IPO (GOM TIỀN)
                                # Điều kiện: (Là _WFT hoặc có từ khóa 'luu ky') VÀ Có tiền trong Két IPO
                                if (is_rights_candidate or 'luu ky' in desc_norm or 'nhap kho' in desc_norm) and self.ipo_accumulator[base_sym] > 0:
                                    total_money = self.ipo_accumulator[base_sym]
                                    price = total_money / val_in
                                    events.append({
                                        'date': d_obj, 'ticker': sym, 'type': 'BUY', 'qty': val_in, 
                                        'price': price, 'value': total_money, 
                                        'source': 'VPS_RIGHTS_MATCHED', 'desc': desc
                                    })
                                    self.wft_price_cache[base_sym] = price
                                    self.ipo_accumulator[base_sym] = 0 # Xóa hết tiền
                                    continue

                                # XỬ LÝ CHUYỂN ĐỔI (DÙNG CACHE)
                                is_conversion = 'chuyen chung khoan' in desc_norm or 'chuyen doi' in desc_norm
                                if is_conversion and base_sym in self.wft_price_cache:
                                    cached_price = self.wft_price_cache[base_sym]
                                    events.append({
                                        'date': d_obj, 'ticker': sym, 'type': 'BUY', 'qty': val_in,
                                        'price': cached_price, 'value': val_in * cached_price, 
                                        'source': 'VPS_RIGHTS_MATCHED',
                                        'desc': desc
                                    })
                                    continue

                                # LUỒNG 4: MUA THƯỜNG (FALLBACK - GIỮ NGUYÊN V8.1)
                                price = 0
                                src_type = 'VPS_MATCH_BUY'
                                sym_lookup = sym.replace('_WFT', '')
                                search_order = sorted(range(-10, 11), key=abs) 
                                for delta in search_order:
                                    chk_d = d_obj + timedelta(days=delta)
                                    k = (sym_lookup, chk_d.strftime('%Y-%m-%d'))
                                    if k in price_map_normal: price = price_map_normal[k]; break
                                
                                events.append({'date': d_obj, 'ticker': sym, 'type': 'BUY', 'qty': val_in, 'price': price, 'value': val_in * price, 'source': src_type, 'desc': desc})

                            if val_out > 0:
                                events.append({'date': d_obj, 'ticker': sym, 'type': 'SELL', 'qty': val_out, 'price': 0, 'value': 0, 'use_external_pnl': True})

                        except Exception: continue

            # PHẦN 3: LÃI LỖ (GIỮ NGUYÊN V8.1)
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