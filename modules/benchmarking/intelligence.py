# File: modules/benchmarking/intelligence.py
# Version: ULTIMATE (Fix VN-Index 0% by reading Inventory Dates + Fix Sector Map)

import pandas as pd
import os
import json
from datetime import datetime

class MarketIntelligence:
    def __init__(self):
        # 1. Load VN-Index
        self.vnindex_df = pd.DataFrame()
        try:
            path = os.path.join('data_market', 'vnindex_history.csv')
            if os.path.exists(path):
                self.vnindex_df = pd.read_csv(path)
                if 'Date' in self.vnindex_df.columns:
                    self.vnindex_df['Date'] = pd.to_datetime(self.vnindex_df['Date'])
                    self.vnindex_df = self.vnindex_df.sort_values('Date')
        except: pass

        # 2. Load Sector Map
        self.sector_map = {}
        try:
            path_sec = os.path.join('data_market', 'stock_sectors.json')
            if os.path.exists(path_sec):
                with open(path_sec, 'r', encoding='utf-8') as f:
                    self.sector_map = json.load(f)
        except: pass

    def _extract_data_from_engine(self, engine_obj):
        """Trích xuất dữ liệu, hỗ trợ đọc ngày tháng từ Inventory (Fix lỗi Trade Log rỗng)"""
        holdings = []
        earliest_date = None # Biến lưu ngày đầu tư sớm nhất tìm được
        
        cash = getattr(engine_obj, 'real_cash_balance', 0)
        if cash == 0: cash = getattr(engine_obj, 'cash_balance', 0)
        net_deposit = getattr(engine_obj, 'total_deposit', 0)
        
        if hasattr(engine_obj, 'data'):
            for ticker, info in engine_obj.data.items():
                qty = 0
                total_cost_val = 0
                
                # --- QUÉT KHO HÀNG (INVENTORY) ---
                if 'inventory' in info and info['inventory']:
                    for item in info['inventory']:
                        if isinstance(item, dict): 
                            # Item mẫu: {'date': Timestamp(...), 'vol': 100, 'cost': 31000}
                            v = item.get('vol', 0)
                            c = item.get('cost', 0)
                            d = item.get('date') # Lấy ngày nhập kho
                            
                            qty += v
                            total_cost_val += (v * c)
                            
                            # Cập nhật ngày sớm nhất
                            if d:
                                try:
                                    d_obj = pd.to_datetime(d)
                                    if earliest_date is None or d_obj < earliest_date:
                                        earliest_date = d_obj
                                except: pass
                
                # Fallback stats (cho trường hợp không có inventory)
                if qty == 0 and 'stats' in info and isinstance(info['stats'], dict):
                    qty = info['stats'].get('curr_vol', 0)

                if qty > 0:
                    avg_price = total_cost_val / qty if qty > 0 else 0
                    holdings.append({
                        'ticker': ticker,
                        'qty': qty,
                        'avg_price': avg_price
                    })
        
        # Nếu vẫn không tìm thấy ngày trong inventory, thử tìm trong trade_log (fallback)
        if earliest_date is None:
            trade_log = getattr(engine_obj, 'trade_log', [])
            if trade_log:
                valid_dates = [e['date'] for e in trade_log if 'date' in e]
                if valid_dates:
                    earliest_date = pd.to_datetime(min(valid_dates))

        return {
            'cash': cash,
            'net_deposit': net_deposit,
            'holdings': holdings,
            'start_date': earliest_date # Ngày bắt đầu đầu tư thực tế
        }

    def _get_valuation_price(self, ticker, avg_price, live_prices):
        if not live_prices: return avg_price
        clean = str(ticker).replace('_WFT', '').strip().upper()
        price = live_prices.get(clean, 0)
        return price if price > 0 else avg_price

    def calculate_alpha(self, engine_obj, live_prices):
        data = self._extract_data_from_engine(engine_obj)
        net_deposit = data['net_deposit']
        
        if net_deposit == 0: 
            return {'nav': 0, 'net_deposit': 0, 'port_return': 0, 'market_return': 0, 'alpha': 0}

        # 1. Tính NAV
        stock_val = 0
        for item in data['holdings']:
            price = self._get_valuation_price(item['ticker'], item['avg_price'], live_prices)
            stock_val += item['qty'] * price
        
        current_nav = stock_val + data['cash']
        port_return = ((current_nav - net_deposit) / net_deposit) * 100
        
        # 2. Tính VN-Index Return (Dựa trên start_date từ Inventory)
        market_return = 0.0
        start_date = data.get('start_date') # Lấy ngày tìm được
        
        if not self.vnindex_df.empty and start_date:
            try:
                # Tìm dòng có ngày >= start_date (Search sorted để tối ưu)
                idx_start = self.vnindex_df['Date'].searchsorted(start_date)
                
                # Nếu tìm thấy hoặc xấp xỉ (Logic tự động lấy ngày gần nhất nếu rơi vào T7/CN)
                if idx_start < len(self.vnindex_df):
                    row_start = self.vnindex_df.iloc[idx_start]
                    
                    # Lấy giá đóng cửa
                    vni_start = row_start['Close']
                    vni_end = self.vnindex_df.iloc[-1]['Close']
                    
                    if vni_start > 0:
                        market_return = ((vni_end - vni_start) / vni_start) * 100
            except Exception as e:
                print(f"Lỗi tính Market Return: {e}")
            
        return {
            'port_return': port_return,
            'market_return': market_return,
            'alpha': port_return - market_return,
            'nav': current_nav,
            'net_deposit': net_deposit
        }

    def calculate_sector_allocation(self, engine_obj, live_prices):
        data = self._extract_data_from_engine(engine_obj)
        sector_values = {}
        total_val = 0.0
        
        for item in data['holdings']:
            price = self._get_valuation_price(item['ticker'], item['avg_price'], live_prices)
            val = item['qty'] * price
            total_val += val
            
            # Map ngành (Chuẩn hóa chữ hoa để khớp Key trong JSON)
            clean_tik = str(item['ticker']).strip().upper()
            sec = self.sector_map.get(clean_tik, "Khác")
            sector_values[sec] = sector_values.get(sec, 0) + val
            
        res = []
        if total_val > 0:
            for s, v in sector_values.items():
                res.append({'sector': s, 'value': v, 'percent': (v/total_val)*100})
        
        return sorted(res, key=lambda x: x['value'], reverse=True)