# File: processors/engine.py
from collections import deque
import pandas as pd
from datetime import datetime

class PortfolioEngine:
    def __init__(self, source_name="Unknown"):
        self.source_name = source_name
        self.today = pd.Timestamp.now().normalize()
        self.total_deposit = 0.0 
        self.real_cash_balance = 0.0
        self.data = {}
        self.trade_log = []

    def get_ticker_state(self, symbol):
        if symbol not in self.data:
            self.data[symbol] = {
                'inventory': deque(),       
                'closed_cycles': [],        
                'current_cycle': None,      
                'stats': {
                    'total_sold_vol': 0, 'total_trading_pl': 0,   
                    'total_dividend': 0, 'total_invested_capital': 0, 
                    'total_sell_cost': 0, 'weighted_sold_days': 0      
                }
            }
        return self.data[symbol]

    def process_event(self, event):
        # 1. CASH SNAPSHOT
        if event['type'] == 'CASH_SNAPSHOT':
            self.real_cash_balance = event.get('val', 0)
            return

        # 2. DEPOSIT
        if event['type'] == 'DEPOSIT':
            self.total_deposit += event.get('val', 0)
            return

        symbol = event.get('sym')
        if not symbol: return 

        state = self.get_ticker_state(symbol)
        inv = state['inventory']
        stats = state['stats']
        date_obj = pd.Timestamp(event['date'])

        # 3. PNL UPDATE
        if event['type'] == 'PNL_UPDATE':
            val = event.get('val', 0)
            stats['total_trading_pl'] += val 
            self.trade_log.append({
                'Ngày': date_obj, 'Mã': symbol, 'Loại': 'CHỐT LÃI (FILE)',
                'SL': 0, 'Giá Bán': 0, 'Giá Vốn': 0, 'Lãi/Lỗ': val, 'Nguồn': 'Excel PnL'
            })
            if state['current_cycle']: state['current_cycle']['trading_pl'] += val
            return

        # 4. BUY
        if event['type'] == 'BUY':
            cost_val = (event['price'] * event['vol']) + event.get('fee', 0)
            unit_cost = cost_val / event['vol'] if event['vol'] > 0 else 0
            
            if state['current_cycle'] is None:
                state['current_cycle'] = {
                    'start_date': date_obj, 
                    'total_buy_val': 0, 'total_buy_vol': 0,
                    'total_sell_val': 0, 'total_sell_vol': 0, 
                    'trading_pl': 0, 'dividend_pl': 0, 'status': 'Open'
                }
            
            cyc = state['current_cycle']
            cyc['total_buy_val'] += cost_val
            cyc['total_buy_vol'] += event['vol']
            stats['total_invested_capital'] += cost_val
            
            inv.append({
                'date': date_obj, 'vol': event['vol'], 
                'cost': unit_cost, 'adj_cost': unit_cost, 'org_vol': event['vol']
            })
            
            # Ghi Log MUA
            self.trade_log.append({
                'Ngày': date_obj, 'Mã': symbol, 'Loại': 'MUA',
                'SL': event['vol'], 'Giá Bán': 0, 'Giá Vốn': unit_cost,
                'Lãi/Lỗ': 0, 'Nguồn': 'Giao Dịch Mua'
            })

        # 5. SELL
        elif event['type'] == 'SELL':
            use_ext_pnl = event.get('use_external_pnl', False)
            net_rev = (event['price'] * event['vol']) - event.get('fee', 0)
            qty_needed = event['vol']
            cost_goods = 0 
            
            while qty_needed > 0 and inv:
                batch = inv[0]
                take = min(qty_needed, batch['vol'])
                cost_goods += take * batch['cost']
                stats['weighted_sold_days'] += (date_obj - batch['date']).days * take
                batch['vol'] -= take
                qty_needed -= take
                if batch['vol'] <= 0.0001: inv.popleft()

            pl_deal = 0 if use_ext_pnl else (net_rev - cost_goods)
            if not use_ext_pnl: stats['total_trading_pl'] += pl_deal

            stats['total_sold_vol'] += event['vol']
            stats['total_sell_cost'] += cost_goods 

            self.trade_log.append({
                'Ngày': date_obj, 'Mã': symbol, 'Loại': 'BÁN',
                'SL': event['vol'], 'Giá Bán': event['price'], 
                'Giá Vốn': cost_goods/event['vol'] if event['vol']>0 else 0,
                'Lãi/Lỗ': pl_deal, 'Nguồn': 'Giao Dịch Bán'
            })

            if state['current_cycle']:
                cyc = state['current_cycle']
                cyc['total_sell_val'] += net_rev
                cyc['total_sell_vol'] += event['vol']
                if not use_ext_pnl: cyc['trading_pl'] += pl_deal
                
                if sum(b['vol'] for b in inv) <= 0.001:
                    cyc['end_date'] = date_obj
                    cyc['status'] = 'Closed'
                    state['closed_cycles'].append(cyc)
                    state['current_cycle'] = None

        # 6. DIVIDEND
        elif event['type'] == 'DIVIDEND':
            val = event.get('val', 0)
            stats['total_dividend'] += val
            if state['current_cycle']: state['current_cycle']['dividend_pl'] += val
            
            self.trade_log.append({
                'Ngày': date_obj, 'Mã': symbol, 'Loại': 'CỔ TỨC',
                'SL': 0, 'Giá Bán': 0, 'Giá Vốn': 0, 'Lãi/Lỗ': val, 'Nguồn': 'Nhận Cổ Tức'
            })
            
            curr_vol = sum(b['vol'] for b in inv)
            if curr_vol > 0:
                red = val / curr_vol
                for b in inv: b['adj_cost'] -= red

        # 7. FEE
        elif event['type'] == 'FEE':
            val = event.get('val', 0)
            stats['total_trading_pl'] -= val
            if state['current_cycle']: state['current_cycle']['trading_pl'] -= val
            self.trade_log.append({
                'Ngày': date_obj, 'Mã': symbol, 'Loại': 'PHÍ/THUẾ',
                'SL': 0, 'Giá Bán': 0, 'Giá Vốn': 0, 'Lãi/Lỗ': -val, 'Nguồn': 'Trừ Phí'
            })

    def generate_reports(self):
        rep_sum, rep_cyc, rep_inv, rep_warn = [], [], [], []
        total_val = sum(sum(b['vol']*b['cost'] for b in s['inventory']) for s in self.data.values())
        
        for sym, state in self.data.items():
            inv = state['inventory']
            stats = state['stats']
            curr_vol = sum(b['vol'] for b in inv)
            curr_val_org = sum(b['vol'] * b['cost'] for b in inv)
            curr_val_adj = sum(b['vol'] * b['adj_cost'] for b in inv)
            
            for b in inv:
                rep_inv.append({
                    'Mã CK': sym, 'Ngày Mua': b['date'].strftime('%d/%m/%Y'),
                    'SL Tồn': b['vol'], 'Giá Vốn Gốc': b['cost'], 'Giá Vốn ĐC': b['adj_cost'],       
                    'Ngày Giữ': (self.today - b['date']).days
                })

            if sym.endswith('_WFT'): continue

            avg_hold_held = sum(((self.today - b['date']).days) * b['vol'] for b in inv) / curr_vol if curr_vol > 0 else 0
            avg_hold_sold = stats['weighted_sold_days'] / stats['total_sold_vol'] if stats['total_sold_vol'] > 0 else 0
            
            rep_sum.append({
                'Mã CK': sym, 
                'Tổng SL Đã Bán': stats['total_sold_vol'],
                'Lãi/Lỗ Giao Dịch': stats['total_trading_pl'],
                'Cổ Tức Đã Nhận': stats['total_dividend'],
                'Tổng Lãi Thực': stats['total_trading_pl'] + stats['total_dividend'],
                '% Hiệu Suất (Trade)': (stats['total_trading_pl'] / stats['total_sell_cost'] * 100) if stats['total_sell_cost'] > 0 else 0,
                'SL Đang Giữ': curr_vol, 
                'Vốn Gốc (Mua)': curr_val_org, 
                'Vốn Hợp Lý (Sau Cổ Tức)': curr_val_adj, 
                'Tổng Vốn Đã Rót': stats['total_invested_capital'],
                '% Tỷ Trọng Vốn': (curr_val_org / total_val * 100) if total_val > 0 else 0,
                'Ngày Giữ TB (Đã Bán)': avg_hold_sold, 
                'Tuổi Kho TB': avg_hold_held
            })

            all_c = state['closed_cycles'] + ([state['current_cycle']] if state['current_cycle'] else [])
            for c in all_c:
                end_d = c.get('end_date')
                dur = (end_d - c['start_date']).days if end_d else (self.today - c['start_date']).days
                
                # Tính ROI cho Cycle
                cycle_pl = c['trading_pl'] + c['dividend_pl']
                roi = (cycle_pl / c['total_buy_val'] * 100) if c['total_buy_val'] > 0 else 0
                
                rep_cyc.append({
                    'Mã CK': sym, 
                    'Ngày Bắt Đầu': c['start_date'].strftime('%d/%m/%Y'),
                    'Ngày Kết Thúc': end_d.strftime('%d/%m/%Y') if end_d else "",
                    'Tuổi Vòng Đời': dur, 
                    'Tổng Vốn Mua': c['total_buy_val'], 
                    'Lãi Giao Dịch': c['trading_pl'], 
                    'Cổ Tức': c['dividend_pl'],
                    'Tổng Lãi Cycle': cycle_pl, 
                    '% ROI Cycle': roi, 
                    'Trạng Thái': 'Đã tất toán' if end_d else 'Đang nắm giữ'
                })

            if curr_vol > 0 and avg_hold_held > 90:
                rep_warn.append({'Mã CK': sym, 'Vốn Kẹp': curr_val_org, 'Tuổi Kho TB': avg_hold_held, 'Cảnh Báo': '> 90 ngày'})

        return (pd.DataFrame(rep_sum), pd.DataFrame(rep_cyc), pd.DataFrame(rep_inv), pd.DataFrame(rep_warn))

    # [FIX LỖI] ĐÃ THÊM LẠI CÔNG THỨC TÍNH ROI
    def get_all_closed_cycles(self):
        res = []
        for sym, state in self.data.items():
            if sym.endswith('_WFT'): continue
            for c in state['closed_cycles']:
                cc = c.copy()
                cc['Mã CK'] = sym
                cc['Lãi/Lỗ'] = cc.get('trading_pl', 0) + cc.get('dividend_pl', 0)
                cc['Tuổi Vòng Đời'] = (cc['end_date'] - cc['start_date']).days if cc.get('end_date') else 0
                
                cost = cc.get('total_buy_val', 0)
                cc['Tổng Vốn Mua'] = cost 
                
                # --- KHÔI PHỤC CÔNG THỨC ROI ---
                if cost > 0:
                    cc['% ROI Cycle'] = (cc['Lãi/Lỗ'] / cost) * 100
                else:
                    cc['% ROI Cycle'] = 0
                # -------------------------------
                
                res.append(cc)
        return res

    @property
    def total_profit(self):
        return sum(s['stats']['total_trading_pl'] + s['stats']['total_dividend'] for s in self.data.values())