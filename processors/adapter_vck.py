# File: processors/adapter_vck.py
import pandas as pd
import re
from datetime import datetime

class VCKAdapter:
    def parse(self, file_path):
        trades = [] 
        deposits = []
        dividends = []
        fee_pool = [] 
        
        # Danh sách lưu lịch sử số dư để tìm số dư cuối kỳ
        balance_history = [] 
        
        try:
            xls = pd.ExcelFile(file_path)
            # Map tên sheet
            sheet_map = {s.lower(): s for s in xls.sheet_names}

            sh_ck = next((sheet_map[s] for s in sheet_map if ('ck' in s or 'khớp' in s or 'lệnh' in s) and 'tiền' not in s), None)
            sh_tien = next((sheet_map[s] for s in sheet_map if ('tiền' in s or 'cash' in s)), None)

            # --- 2. ĐỌC SHEET TIỀN (QUAN TRỌNG: LẤY SỐ DƯ CUỐI KỲ) ---
            if sh_tien:
                # Đọc header row 0 (giả định chuẩn)
                df_t = pd.read_excel(xls, sheet_name=sh_tien, header=0)
                df_t.columns = [str(c).strip().lower() for c in df_t.columns]

                c_nd = next((c for c in df_t.columns if 'nội dung' in c), None)
                c_giam = next((c for c in df_t.columns if 'giảm' in c), None)
                c_tang = next((c for c in df_t.columns if 'tăng' in c), None)
                c_date = next((c for c in df_t.columns if 'ngày' in c), None)
                
                # CỘT SỐ DƯ (MỚI)
                c_bal = next((c for c in df_t.columns if 'số dư' in c or 'balance' in c or 'lũy kế' in c), None)

                if c_nd:
                    for _, row in df_t.iterrows():
                        content = str(row.get(c_nd, ''))
                        val_giam = self.clean_num(row.get(c_giam, 0))
                        val_tang = self.clean_num(row.get(c_tang, 0))
                        
                        # Lấy ngày
                        d_obj = self.extract_date(str(row.get(c_date, '')))
                        if not d_obj: d_obj = self.extract_date_from_text(content)
                        if not d_obj: continue

                        # --- LẤY SỐ DƯ (SNAPSHOT) ---
                        if c_bal:
                            val_bal = self.clean_num(row.get(c_bal, 0))
                            # Lưu lại cặp (Ngày, Số dư)
                            balance_history.append({'date': d_obj, 'val': val_bal})

                        # A. Nạp tiền (Trừ các dòng nội bộ)
                        # Lưu ý: Nếu rút tiền, VCK thường ghi ở cột GIẢM. Cần check kỹ nội dung.
                        # Tạm thời chỉ lấy Nạp (Tăng)
                        if val_tang > 0 and any(k in content.lower() for k in ['nop tien', 'nộp tiền', 'cashin', 'chuyen tien']):
                            if 'cổ tức' not in content.lower():
                                deposits.append({'date': d_obj, 'type': 'DEPOSIT', 'val': val_tang, 'source': 'VCK'})

                        # B. Cổ tức
                        if val_tang > 0 and any(k in content.lower() for k in ['co tuc', 'cổ tức', 'lãi trái phiếu']):
                            m_sym = re.search(r"(?:ma|mã|ck)\s*[:\s]*([a-z0-9]+)", content, re.IGNORECASE)
                            if not m_sym: m_sym = re.search(r"\b([a-zA-Z0-9]{3})\b", content)
                            sym = m_sym.group(1).upper() if m_sym else "UNKNOWN"
                            dividends.append({'date': d_obj, 'sym': sym, 'type': 'DIVIDEND', 'val': val_tang, 'source': 'VCK'})

                        # C. Phí Giao Dịch (Bóc tách để khớp lệnh)
                        if val_giam > 0 and any(k in content.lower() for k in ['phi', 'phí', 'thue', 'thuế']):
                            m_detail = re.search(r"KL:\s*([0-9,.]+)\s+Gia:\s*([0-9,.]+)", content, re.IGNORECASE)
                            m_sym = re.search(r"(?:mua|ban)\s+([a-z0-9]+)", content, re.IGNORECASE)
                            
                            if m_sym:
                                f_sym = m_sym.group(1).upper()
                                f_vol = float(m_detail.group(1).replace(',', '')) if m_detail else None
                                f_price = float(m_detail.group(2).replace(',', '')) if m_detail else None
                                
                                fee_pool.append({
                                    'date': d_obj.date(), 'sym': f_sym, 
                                    'vol': f_vol, 'price': f_price,
                                    'fee_val': val_giam, 'matched': False
                                })

            # --- 3. ĐỌC SHEET LỆNH (VÀ KHỚP PHÍ) ---
            if sh_ck:
                df_ck = pd.read_excel(xls, sheet_name=sh_ck, header=0)
                df_ck.columns = [str(c).strip().lower() for c in df_ck.columns]

                c_ma = next((c for c in df_ck.columns if 'mã ck' in c), None)
                c_nd = next((c for c in df_ck.columns if 'nội dung' in c), None)
                c_tang = next((c for c in df_ck.columns if 'phát sinh tăng' in c), None)
                c_giam = next((c for c in df_ck.columns if 'phát sinh giảm' in c), None)
                c_date = next((c for c in df_ck.columns if 'ngày' in c), None)

                if c_ma and c_nd:
                    for _, row in df_ck.iterrows():
                        content = str(row.get(c_nd, ''))
                        tik = str(row.get(c_ma, '')).strip().upper()
                        if not tik or tik == 'NAN': continue

                        date_obj = self.extract_date(str(row.get(c_date, '')))
                        if not date_obj: date_obj = self.extract_date_from_text(content)
                        if not date_obj: continue

                        m_price = re.search(r"Gia:\s*([0-9,]+)", content, re.IGNORECASE)
                        if not m_price: continue 
                        price = float(m_price.group(1).replace(',', ''))
                        
                        vol_in = self.clean_num(row.get(c_tang, 0)) if c_tang else 0
                        vol_out = self.clean_num(row.get(c_giam, 0)) if c_giam else 0
                        
                        vol = 0; side = ''
                        if vol_in > 0: side = 'BUY'; vol = vol_in
                        elif vol_out > 0: side = 'SELL'; vol = vol_out
                        
                        if vol > 0:
                            matched_fee = 0
                            for i, f in enumerate(fee_pool):
                                if not f['matched'] and f['sym'] == tik and f['date'] == date_obj.date():
                                    is_exact_match = False
                                    if f['vol'] is not None and f['price'] is not None:
                                        if f['vol'] == vol and abs(f['price'] - price) < 10: is_exact_match = True
                                    else: pass 
                                    if is_exact_match:
                                        matched_fee = f['fee_val']
                                        fee_pool[i]['matched'] = True
                                        break
                            
                            if matched_fee == 0:
                                for i, f in enumerate(fee_pool):
                                    if not f['matched'] and f['sym'] == tik and f['date'] == date_obj.date() and f['price'] is None:
                                        matched_fee = f['fee_val']
                                        fee_pool[i]['matched'] = True
                                        break

                            trades.append({
                                'date': date_obj, 'sym': tik, 'type': side,
                                'vol': vol, 'price': price, 'fee': matched_fee, 
                                'source': 'VCK'
                            })

        except Exception as e:
            print(f"❌ Lỗi đọc file VCK: {e}")
            
        # 4. TÌM SỐ DƯ TIỀN MỚI NHẤT (SNAPSHOT)
        cash_event = []
        if balance_history:
            # Sắp xếp theo ngày giảm dần (Mới nhất lên đầu)
            balance_history.sort(key=lambda x: x['date'], reverse=True)
            latest_balance = balance_history[0]['val']
            
            cash_event.append({
                'date': datetime.now(),
                'type': 'CASH_SNAPSHOT',
                'val': latest_balance,
                'source': 'VCK_LEDGER'
            })

        # 5. TRẢ VỀ KẾT QUẢ
        if not trades: return deposits + dividends + cash_event
        
        df_events = pd.DataFrame(trades)
        type_prio = {'BUY': 1, 'DEPOSIT': 2, 'SELL': 3} 
        df_events['prio'] = df_events['type'].map(type_prio).fillna(99)
        df_events = df_events.sort_values(by=['date', 'prio'])
        
        return df_events.to_dict('records') + deposits + dividends + cash_event

    # --- HÀM PHỤ TRỢ ---
    def clean_num(self, val):
        if pd.isna(val) or str(val).strip() == '' or str(val).strip() == '-': return 0.0
        try: return float(str(val).replace(',', '').replace(' ', ''))
        except: return 0.0
    
    def extract_date(self, val):
        if isinstance(val, datetime): return val
        if isinstance(val, str):
            try: return datetime.strptime(val.split(' ')[0], '%d/%m/%Y')
            except: pass
        return None

    def extract_date_from_text(self, text):
        m = re.search(r"(\d{2}/\d{2}/\d{4})", text)
        if m: return datetime.strptime(m.group(1), '%d/%m/%Y')
        return None