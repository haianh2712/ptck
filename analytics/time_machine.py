# File: analytics/time_machine.py
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
        self.current_deposit = 0.0 # Vốn gốc đã nạp ròng
        self.inventory = {} # {symbol: {'vol': 0, 'cost': 0}}
        self.portfolio_value = 0.0 # Giá trị kho (theo giá vốn)

    def run(self):
        if not self.events: return pd.DataFrame()

        # Tạo khung thời gian từ ngày đầu tiên đến hôm nay
        start_date = self.events[0]['date']
        end_date = pd.Timestamp.now()
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
            self.history.append({
                'Ngày': day,
                'Tiền Mặt': self.current_cash,
                'Giá Trị Kho': self.portfolio_value,
                'Tổng Tài Sản (NAV)': self.current_cash + self.portfolio_value,
                'Vốn Nạp Ròng': self.current_deposit
            })

        return pd.DataFrame(self.history)

    def _process_single_event(self, e):
        evt_type = e['type']
        val = e.get('val', 0)
        sym = e.get('sym')

        # 1. ƯU TIÊN SỐ 1: SNAPSHOT TIỀN (Chính xác tuyệt đối)
        if evt_type == 'CASH_SNAPSHOT':
            self.current_cash = val
            return

        # 2. DÒNG TIỀN VÀO/RA
        if evt_type == 'DEPOSIT':
            # current_cash += val # Snapshot sẽ ghi đè, nhưng cộng để track nếu thiếu snapshot
            # Logic: Nếu có snapshot rồi thì deposit chỉ để tính Vốn Nạp Ròng
            self.current_deposit += val
            # Tạm thời vẫn cộng vào cash để support những ngày chưa có snapshot
            self.current_cash += val
        
        elif evt_type == 'PNL_UPDATE': # Lãi đã chốt -> Cộng vào tiền (nếu chưa có snapshot)
            self.current_cash += val
            
        elif evt_type == 'DIVIDEND': # Cổ tức -> Cộng tiền
            self.current_cash += val
            # Trừ giá vốn điều chỉnh
            if sym and sym in self.inventory:
                stock = self.inventory[sym]
                if stock['vol'] > 0:
                    reduction = val / stock['vol']
                    stock['cost'] -= reduction

        elif evt_type == 'FEE':
            self.current_cash -= val

        # 3. MUA BÁN KHO (Inventory)
        elif evt_type == 'BUY':
            cost = e.get('price', 0)
            vol = e.get('vol', 0)
            # Trừ tiền (nếu ko phải hàng 0 đồng)
            total_cost = cost * vol + e.get('fee', 0)
            self.current_cash -= total_cost
            
            # Nhập kho
            if sym not in self.inventory: self.inventory[sym] = {'vol': 0, 'cost': 0}
            stock = self.inventory[sym]
            
            # Tính lại giá vốn bình quân (Weighted Avg Price)
            new_vol = stock['vol'] + vol
            if new_vol > 0:
                stock['cost'] = ((stock['cost'] * stock['vol']) + total_cost) / new_vol
            stock['vol'] = new_vol

        elif evt_type == 'SELL':
            price = e.get('price', 0) # Giá bán
            vol = e.get('vol', 0)
            fee = e.get('fee', 0)
            revenue = (price * vol) - fee
            
            # Nếu có cờ use_external_pnl (VPS), doanh thu đã được tính qua PNL_UPDATE hoặc Snapshot rồi
            # Nên ở đây ta KHÔNG cộng tiền nữa để tránh tính kép, chỉ trừ kho thôi.
            if not e.get('use_external_pnl', False):
                self.current_cash += revenue
            
            # Xuất kho
            if sym in self.inventory:
                stock = self.inventory[sym]
                stock['vol'] = max(0, stock['vol'] - vol)
                # Giá vốn đơn vị giữ nguyên khi bán, chỉ giảm số lượng

    def _update_portfolio_value(self):
        """Tính tổng giá trị các mã đang giữ theo giá vốn điều chỉnh"""
        total = 0
        for sym, stock in self.inventory.items():
            # Không tính giá trị cho mã WFT để biểu đồ NAV sát thực tế hơn
            if not sym.endswith('_WFT'):
                total += stock['vol'] * stock['cost']
        self.portfolio_value = total