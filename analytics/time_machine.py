# File: analytics/time_machine.py
# Version: EXPERT FIX (Trade Date Basis - Remove Double Counting)
import pandas as pd
from datetime import timedelta

class TimeMachine:
    def __init__(self, events):
        """
        Khởi tạo với danh sách sự kiện từ Adapter.
        Events cần được sắp xếp theo thời gian trước khi đưa vào đây.
        """
        self.events = sorted(events, key=lambda x: x['date'])
        self.history = []
        
        # Trạng thái tài khoản (State)
        self.current_cash = 0.0
        self.current_deposit = 0.0 # Vốn nạp ròng (Net Deposit)
        self.inventory = {} # {symbol: {'vol': 0, 'cost': 0}}
        self.portfolio_value = 0.0 

    def run(self):
        if not self.events: return pd.DataFrame()

        # [UPDATE] Mở rộng khung thời gian để bao gồm dữ liệu tương lai (2025)
        start_date = self.events[0]['date']
        
        # Tìm ngày xa nhất: So sánh 'Hôm nay' và 'Ngày cuối trong file Excel'
        last_event_date = self.events[-1]['date']
        end_date = max(pd.Timestamp.now(), last_event_date)
        
        date_range = pd.date_range(start=start_date, end=end_date, freq='D')
        
        # Gom nhóm sự kiện theo ngày để xử lý
        events_by_date = {}
        for e in self.events:
            d_str = e['date'].strftime('%Y-%m-%d')
            if d_str not in events_by_date: events_by_date[d_str] = []
            events_by_date[d_str].append(e)

        # --- CHẠY VÒNG LẶP THỜI GIAN (REPLAY) ---
        for day in date_range:
            d_str = day.strftime('%Y-%m-%d')
            daily_events = events_by_date.get(d_str, [])
            
            # Xử lý các sự kiện trong ngày
            for e in daily_events:
                self._process_single_event(e)
            
            # Cập nhật lại giá trị kho cuối ngày
            self._update_portfolio_value()
            
            # Ghi lại trạng thái cuối ngày (Snapshot)
            # NAV = Tiền (Sức mua) + Giá trị cổ phiếu
            nav = self.current_cash + self.portfolio_value
            
            self.history.append({
                'Ngày': day,
                'Tiền Mặt': self.current_cash,
                'Giá Trị Cổ Phiếu': self.portfolio_value, 
                'Tổng Tài Sản (NAV)': nav, 
                'Vốn Nạp Ròng': self.current_deposit,
                'Lãi/Lỗ Tạm Tính': nav - self.current_deposit
            })

        return pd.DataFrame(self.history)

    def _process_single_event(self, e):
        evt_type = e['type']
        val = e.get('value', 0) if e.get('value', 0) > 0 else e.get('val', 0)
        
        # Chuẩn hóa mã CK
        raw_sym = e.get('ticker') or e.get('sym')
        sym = None
        if raw_sym and str(raw_sym).lower() != 'nan':
            sym = str(raw_sym).strip().upper()

        # =================================================================
        # 1. NHÓM SỰ KIỆN ƯU TIÊN (SNAPSHOT)
        # =================================================================
        if evt_type == 'CASH_SNAPSHOT':
            if val > 0: self.current_cash = val
            return

        # =================================================================
        # 2. NHÓM VỐN (NẠP / RÚT) - ẢNH HƯỞNG VỐN GỐC
        # =================================================================
        if evt_type in ['DEPOSIT', 'NAP_TIEN']:
            self.current_deposit += val
            self.current_cash += val
            return
        
        if evt_type in ['WITHDRAW', 'RUT_TIEN']:
            self.current_deposit -= val
            self.current_cash -= val
            return

        # =================================================================
        # 3. NHÓM GIAO DỊCH (MUA / BÁN) - ẢNH HƯỞNG NAV & TIỀN
        # =================================================================
        # MUA: Trừ tiền, Tăng kho
        if evt_type in ['BUY', 'MUA']:
            # Tính giá trị mua
            vol = e.get('qty', 0) if e.get('qty', 0) > 0 else e.get('vol', 0)
            price = e.get('price', 0)
            
            # Nếu có 'value' (từ sheet Tiền) thì dùng luôn, ko thì tính vol*price
            total_cost = val if val > 0 else (price * vol)
            
            self.current_cash -= total_cost
            
            # Nhập kho
            if vol > 0 and sym:
                if sym not in self.inventory: self.inventory[sym] = {'vol': 0, 'cost': 0}
                stock = self.inventory[sym]
                
                # Tính giá vốn bình quân (Weighted Avg)
                new_vol = stock['vol'] + vol
                if new_vol > 0:
                    current_val = stock['vol'] * stock['cost']
                    stock['cost'] = (current_val + total_cost) / new_vol
                stock['vol'] = new_vol
            return

        # BÁN: Cộng tiền (Doanh thu), Giảm kho
        if evt_type in ['SELL', 'BAN']:
            vol = e.get('qty', 0) if e.get('qty', 0) > 0 else e.get('vol', 0)
            price = e.get('price', 0)
            fee = e.get('fee', 0)
            
            # Doanh thu thực nhận (tính luôn vào tiền mặt tại ngày giao dịch)
            revenue = (price * vol) - fee
            
            # Nếu dùng external pnl (như VPS), tiền có thể đã được update qua snapshot
            # Nhưng với VCK, ta cộng doanh thu vào tiền ngay lập tức (Trade Date)
            if not e.get('use_external_pnl', False):
                self.current_cash += revenue
            
            # Xuất kho
            if sym and sym in self.inventory:
                stock = self.inventory[sym]
                stock['vol'] = max(0, stock['vol'] - vol)
            return

        # =================================================================
        # 4. NHÓM PHÍ & CỔ TỨC (ẢNH HƯỞNG LỢI NHUẬN)
        # =================================================================
        if evt_type in ['FEE', 'PHI_THUE']:
            self.current_cash -= val
            return
            
        if evt_type in ['DIVIDEND', 'CO_TUC_TIEN']:
            self.current_cash += val
            # Điều chỉnh giá vốn (nếu muốn NAV chuẩn hơn thì trừ giá vốn)
            if sym and sym in self.inventory:
                stock = self.inventory[sym]
                if stock['vol'] > 0:
                    reduction = val / stock['vol']
                    stock['cost'] -= reduction
            return

        # =================================================================
        # 5. NHÓM THANH TOÁN BÙ TRỪ (IGNORE ĐỂ TRÁNH TRÙNG LẶP)
        # =================================================================
        # Tại sao bỏ qua? 
        # Vì tiền bán (BAN_TIEN_VE) đã được cộng ở lệnh SELL phía trên.
        # Vì tiền ứng (UNG_TRUOC) cũng là một dạng tiền bán về sớm.
        # Vì hoàn ứng (HOAN_UNG) là trả nợ, không làm thay đổi NAV ròng.
        if evt_type in ['BAN_TIEN_VE', 'UNG_TRUOC', 'HOAN_UNG']:
            return 

        # Lãi/Lỗ đã chốt từ file (dành cho VPS)
        if evt_type == 'PNL_UPDATE':
            self.current_cash += val
            return

    def _update_portfolio_value(self):
        """Tính tổng giá trị các mã đang giữ theo giá vốn điều chỉnh"""
        total = 0
        for raw_sym, stock in self.inventory.items():
            if pd.isna(raw_sym): continue
            sym = str(raw_sym).strip().upper()
            
            # Không tính giá trị cho mã WFT để biểu đồ NAV sát thực tế hơn
            if not sym.endswith('_WFT'):
                total += stock['vol'] * stock['cost']
        self.portfolio_value = total