import pandas as pd
import re
import unicodedata
from datetime import datetime
from collections import defaultdict

class VCKAdapter:
    def __init__(self):
        # 1. Bộ nhớ tiền IPO (Gom từ Sheet Tiền)
        self.ipo_accumulator = defaultdict(float)
        
        # 2. "Két sắt" Giá vốn (Cache)
        self.unit_cost_cache = defaultdict(float)

    # --- HELPERS ---
    def normalize_str(self, s):
        if not isinstance(s, str): return str(s)
        s = re.sub(r'[đĐ]', 'd', s)
        s = unicodedata.normalize('NFD', s)
        s = s.encode('ascii', 'ignore').decode('utf-8')
        return s.lower().strip()

    def clean_num(self, val):
        if pd.isna(val) or str(val).strip() == '' or str(val).strip() == '-': return 0.0
        try:
            s = str(val)
            if isinstance(val, (int, float)): return float(val)
            s_clean = s.replace('.', '').replace(',', '').replace(' ', '')
            return float(s_clean)
        except: return 0.0

    def parse(self, file_path):
        trades = [] 
        deposits = []
        dividends = []
        fee_pool = [] 
        balance_history = [] 
        
        # Reset bộ nhớ
        self.ipo_accumulator = defaultdict(float)
        self.unit_cost_cache = defaultdict(float)

        try:
            if str(file_path).endswith('.csv'):
                try: df_raw_all = pd.read_csv(file_path); xls = None
                except: return []
            else:
                xls = pd.ExcelFile(file_path)

            if xls:
                sheet_map = {s.lower(): s for s in xls.sheet_names}
                sh_ck = next((sheet_map[s] for s in sheet_map if ('ck' in s or 'khớp' in s or 'lệnh' in s) and 'tiền' not in s), None)
                sh_tien = next((sheet_map[s] for s in sheet_map if ('tiền' in s or 'cash' in s)), None)
            else:
                sh_tien = 'sheet1'; sh_ck = None

            # =================================================================
            # VÒNG 1: LEARNING PHASE (HỌC DỮ LIỆU)
            # =================================================================
            
            # 1.1 Quét Sheet Tiền -> Gom tiền vào accumulator
            if sh_tien:
                df_t = self._read_sheet(xls, file_path, sh_tien)
                if df_t is not None:
                    c_nd, c_giam, _, _, _ = self._map_columns_tien(df_t)
                    if c_nd:
                        for _, row in df_t.iterrows():
                            val_giam = self.clean_num(row.get(c_giam, 0))
                            if val_giam > 0:
                                content_norm = self.normalize_str(str(row.get(c_nd, '')))
                                # Mở rộng từ khóa nhận diện
                                keywords = ['thanh toan', 'ipo', 'dat coc', 'phat hanh', 'quyen mua', 'nop tien']
                                if any(k in content_norm for k in keywords):
                                    # Sử dụng hàm Extract mới (đã thêm Regex Quyền Mua)
                                    ticker = self._extract_ticker_regex(content_norm)
                                    if ticker:
                                        self.ipo_accumulator[ticker] += val_giam

            # 1.2 Quét Sheet CK -> Tính Unit Cost của WFT
            if sh_ck:
                df_ck = self._read_sheet(xls, file_path, sh_ck)
                if df_ck is not None:
                    c_ma, c_status, _, c_tang, _, _, _ = self._map_columns_ck(df_ck)
                    if c_ma:
                        for _, row in df_ck.iterrows():
                            tik = str(row.get(c_ma, '')).strip().upper()
                            status = self.normalize_str(str(row.get(c_status, '') if c_status else ""))
                            vol_in = self.clean_num(row.get(c_tang, 0))

                            # Nếu là hàng WFT về kho
                            if 'cho giao dich' in status and vol_in > 0:
                                total_money = self.ipo_accumulator.get(tik, 0)
                                if total_money > 0:
                                    self.unit_cost_cache[tik] = total_money / vol_in
                                    # Reset tiền để không dùng lại cho lần sau (ví dụ cổ tức thưởng)
                                    self.ipo_accumulator[tik] = 0

            # =================================================================
            # VÒNG 2: ACTION PHASE (GHI SỔ & KHỚP LỆNH)
            # =================================================================
            
            # 2.1 Xử lý Sheet Tiền
            if sh_tien:
                df_t = self._read_sheet(xls, file_path, sh_tien)
                if df_t is not None:
                    c_nd, c_giam, c_tang, c_date, c_bal = self._map_columns_tien(df_t)
                    if c_nd:
                        for _, row in df_t.iterrows():
                            content_raw = str(row.get(c_nd, ''))
                            content_norm = self.normalize_str(content_raw)
                            val_giam = self.clean_num(row.get(c_giam, 0))
                            val_tang = self.clean_num(row.get(c_tang, 0))
                            d_obj = self.extract_date(str(row.get(c_date, '')))
                            if not d_obj: d_obj = self.extract_date_from_text(content_raw)
                            if not d_obj: continue
                            
                            if c_bal: balance_history.append({'date': d_obj, 'val': self.clean_num(row.get(c_bal, 0))})

                            if val_giam > 0:
                                keywords = ['thanh toan', 'ipo', 'dat coc', 'phat hanh', 'quyen mua', 'nop tien']
                                if any(k in content_norm for k in keywords):
                                    ticker = self._extract_ticker_regex(content_norm)
                                    if ticker:
                                        trades.append({'date': d_obj, 'type': 'IPO_DEPOSIT', 'ticker': ticker + "_PENDING", 'qty': 0, 'price': 0, 'value': val_giam, 'source': 'VCK_IPO_CASH'})
                                    # Nếu có từ khóa 'nop tien' mà không có mã, coi như rút tiền/chuyển tiền thường
                                    elif 'nop tien' not in content_norm: 
                                         pass # Bỏ qua nếu ko bắt đc mã, để dưới check tiếp

                                # Check các loại khác nếu chưa bắt được IPO
                                if not any(t['value'] == val_giam and t['date'] == d_obj for t in trades):
                                    if any(k in content_norm for k in ['phi', 'thue', 'tax', 'fee']):
                                        fee_pool.append({'date': d_obj, 'type': 'PHI_THUE', 'value': val_giam, 'source': 'VCK_FEE'})
                                    elif any(k in content_norm for k in ['rut', 'chuyen']) and not ('mua' in content_norm):
                                        deposits.append({'date': d_obj, 'type': 'RUT_TIEN', 'val': val_giam, 'source': 'VCK_WITHDRAW'})
                            
                            if val_tang > 0:
                                if any(k in content_norm for k in ['nop tien', 'cashin']):
                                    deposits.append({'date': d_obj, 'type': 'NAP_TIEN', 'val': val_tang, 'source': 'VCK_DEP'})
                                elif any(k in content_norm for k in ['co tuc', 'lai']):
                                    m = re.search(r"\b([a-zA-Z0-9]{3})\b", content_norm)
                                    sym = m.group(1).upper() if m else "UNKNOWN"
                                    dividends.append({'date': d_obj, 'sym': sym, 'type': 'CO_TUC_TIEN', 'val': val_tang, 'source': 'VCK_DIV'})
                                elif any(k in content_norm for k in ['ban ', 'ung truoc']):
                                    deposits.append({'date': d_obj, 'type': 'BAN_TIEN_VE', 'val': val_tang, 'source': 'VCK_SELL'})

            # 2.2 Xử lý Sheet CK
            if sh_ck:
                df_ck = self._read_sheet(xls, file_path, sh_ck)
                if df_ck is not None:
                    c_ma, c_status, c_nd, c_tang, c_giam, c_date, _ = self._map_columns_ck(df_ck)
                    if c_ma:
                        for _, row in df_ck.iterrows():
                            tik = str(row.get(c_ma, '')).strip().upper()
                            if not tik or tik == 'NAN': continue

                            content_raw = str(row.get(c_nd, '') if c_nd else "")
                            status_norm = self.normalize_str(str(row.get(c_status, '') if c_status else ""))
                            d_obj = self.extract_date_from_text(content_raw)
                            if not d_obj: d_obj = self.extract_date(str(row.get(c_date, '')))
                            if not d_obj: continue

                            vol_in = self.clean_num(row.get(c_tang, 0))
                            vol_out = self.clean_num(row.get(c_giam, 0))
                            m_price = re.search(r"gia[:\s]+([0-9,]+)", content_raw, re.IGNORECASE)
                            price = float(m_price.group(1).replace(',', '')) if m_price else 0

                            # LOGIC KHỚP LỆNH
                            if 'cho giao dich' in status_norm:
                                tik_wft = tik + "_WFT"
                                if vol_in > 0:
                                    unit_cost = self.unit_cost_cache.get(tik, 0)
                                    total_val = unit_cost * vol_in
                                    trades.append({'date': d_obj, 'type': 'BUY', 'ticker': tik_wft, 'qty': vol_in, 'price': 0, 'value': total_val, 'source': 'VCK_IPO_MATCH'})
                                elif vol_out > 0:
                                    # TRUNG HÒA P&L: Bán với giá = Giá vốn
                                    unit_cost = self.unit_cost_cache.get(tik, 0)
                                    total_val = unit_cost * vol_out
                                    trades.append({'date': d_obj, 'type': 'SELL', 'ticker': tik_wft, 'qty': vol_out, 'price': unit_cost, 'value': total_val, 'source': 'VCK_CONVERT_OUT'})

                            elif 'cho luu ky' in status_norm:
                                continue

                            else:
                                if vol_in > 0:
                                    cached_cost = self.unit_cost_cache.get(tik, 0)
                                    if price == 0 and cached_cost > 0:
                                        trades.append({'date': d_obj, 'type': 'BUY', 'ticker': tik, 'qty': vol_in, 'price': cached_cost, 'value': vol_in * cached_cost, 'source': 'VCK_CONVERT_IN'})
                                    else:
                                        trades.append({'date': d_obj, 'type': 'BUY', 'ticker': tik, 'qty': vol_in, 'price': price, 'value': vol_in*price, 'source': 'VCK_MATCH_BUY'})
                                
                                elif vol_out > 0:
                                    trades.append({'date': d_obj, 'type': 'SELL', 'ticker': tik, 'qty': vol_out, 'price': price, 'value': vol_out*price, 'source': 'VCK_MATCH_SELL'})

        except Exception as e:
            print(f"❌ Lỗi VCK: {e}")

        # Snapshot
        cash_event = []
        if balance_history:
            balance_history.sort(key=lambda x: x['date'], reverse=True)
            cash_event = [{'date': datetime.now(), 'type': 'CASH_SNAPSHOT', 'val': balance_history[0]['val'], 'source': 'VCK_LEDGER'}]

        all_events = trades + deposits + dividends + cash_event + fee_pool
        df_events = pd.DataFrame(all_events)
        if not df_events.empty:
            type_prio = {'NAP_TIEN': 1, 'DEPOSIT': 1, 'IPO_DEPOSIT': 1, 'BUY': 2, 'MUA': 2, 'SELL': 3, 'PHI_THUE': 4, 'CASH_SNAPSHOT': 99}
            df_events['prio'] = df_events['type'].map(type_prio).fillna(50)
            return df_events.sort_values(by=['date', 'prio']).to_dict('records')
        return []

    # --- HELPERS ---
    def _read_sheet(self, xls, file_path, sheet_name):
        try:
            if xls: df = pd.read_excel(xls, sheet_name=sheet_name, header=0)
            else: df = pd.read_csv(file_path, header=0)
            df.columns = [self.normalize_str(c) for c in df.columns]
            return df
        except: return None

    def _map_columns_tien(self, df):
        c_nd = next((c for c in df.columns if 'noi dung' in c or 'dien giai' in c), None)
        c_giam = next((c for c in df.columns if 'giam' in c or 'debit' in c), None)
        c_tang = next((c for c in df.columns if 'tang' in c or 'credit' in c), None)
        c_date = next((c for c in df.columns if 'ngay' in c or 'date' in c), None)
        c_bal = next((c for c in df.columns if 'so du' in c or 'balance' in c), None)
        return c_nd, c_giam, c_tang, c_date, c_bal

    def _map_columns_ck(self, df):
        c_ma = next((c for c in df.columns if 'ma' in c or 'ck' in c), None)
        c_status = next((c for c in df.columns if 'trang thai' in c or 'status' in c), None)
        c_nd = next((c for c in df.columns if 'noi dung' in c), None)
        c_tang = next((c for c in df.columns if 'tang' in c), None)
        c_giam = next((c for c in df.columns if 'giam' in c), None)
        c_date = next((c for c in df.columns if 'ngay' in c), None)
        return c_ma, c_status, c_nd, c_tang, c_giam, c_date, None

    def _extract_ticker_regex(self, content):
        # 1. Định dạng VPS_MÃ_
        m_vps = re.search(r"vps_([a-zA-Z0-9]{3})_", content, re.IGNORECASE)
        # 2. Định dạng Số lượng (Mua 100 VCK)
        m_qty = re.search(r"(?:mua|toan|ipo)\s+([0-9]+)\s*([a-zA-Z0-9]{3})", content, re.IGNORECASE)
        # 3. [FIX MỚI] Định dạng Quyền Mua (Quyen mua: VCK, khoi luong:...)
        m_rights = re.search(r"quyen mua[:\s]*([a-zA-Z0-9]{3})\b", content, re.IGNORECASE)

        if m_vps: return m_vps.group(1).upper()
        if m_qty: return m_qty.group(2).upper()
        if m_rights: return m_rights.group(1).upper()
        return None

    def extract_date(self, val):
        if isinstance(val, datetime): return val
        if isinstance(val, str):
            try: return datetime.strptime(val.split(' ')[0], '%d/%m/%Y')
            except: 
                try: return datetime.strptime(val.split(' ')[0], '%Y-%m-%d')
                except: pass
        return None

    def extract_date_from_text(self, text):
        m = re.search(r"(\d{2}/\d{2}/\d{4})", text)
        if m: return datetime.strptime(m.group(1), '%d/%m/%Y')
        return None