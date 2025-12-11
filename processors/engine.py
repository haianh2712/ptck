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
                    'total_sold_vol': 0,
                    'total_trading_pl': 0,   
                    'total_dividend': 0,     
                    'total_invested_capital': 0, 
                    'total_sell_cost': 0,
                    'weighted_sold_days': 0      
                }
            }
        return self.data[symbol]

    def process_event(self, event):
        if event['type'] == 'CASH_SNAPSHOT':
            self.real_cash_balance = event.get('val', 0)
            return

        if event['type'] == 'DEPOSIT':
            self.total_deposit += event.get('val', 0)
            return

        symbol = event.get('sym')
        if not symbol: return 

        state = self.get_ticker_state(symbol)
        inv = state['inventory']
        stats = state['stats']
        date_obj = pd.Timestamp(event['date'])

        # --- PNL UPDATE ---
        if event['type'] == 'PNL_UPDATE':
            val = event.get('val', 0)
            stats['total_trading_pl'] += val 
            self.trade_log.append({'Ngày': date_obj, 'Mã': symbol, 'Loại': 'CHỐT LÃI (FILE)', 'SL': 0, 'Giá Bán': 0, 'Giá Vốn': 0, 'Lãi/Lỗ': val, 'Nguồn': 'Excel Lãi Lỗ'})
            if state['current_cycle']: state['current_cycle']['trading_pl'] += val
            return

        # --- BUY ---
        if event['type'] == 'BUY':
            cost_val = (event['price'] * event['vol']) + event.get('fee', 0)
            unit_cost = cost_val / event['vol'] if event['vol'] > 0 else 0
            
            if state['current_cycle'] is None:
                state['current_cycle'] = {
                    'start_date': date_obj, 'total_buy_val': 0, 'total_buy_vol': 0,
                    'total_sell_val': 0, 'total_sell_vol': 0, 'trading_pl': 0, 'dividend_pl': 0, 'status': 'Open'
                }
            
            cyc = state['current_cycle']
            cyc['total_buy_val'] += cost_val
            cyc['total_buy_vol'] += event['vol']
            stats['total_invested_capital'] += cost_val
            
            inv.append({'date': date_obj, 'vol': event['vol'], 'cost': unit_cost, 'adj_cost': unit_cost, 'org_vol': event['vol']})

        # --- SELL ---
        elif event['type'] == 'SELL':
            use_external_pnl = event.get('use_external_pnl', False)
            net_revenue = (event['price'] * event['vol']) - event.get('fee', 0)
            qty_needed = event['vol']
            cost_of_goods = 0 
            
            while qty_needed > 0 and inv:
                batch = inv[0]
                hold_days = (date_obj - batch['date']).days
                take = min(qty_needed, batch['vol'])
                cogs_part = take * batch['cost']
                cost_of_goods += cogs_part
                stats['weighted_sold_days'] += hold_days * take
                batch['vol'] -= take
                qty_needed -= take
                if batch['vol'] <= 0.0001: inv.popleft()

            trading_pl_deal = 0 if use_external_pnl else (net_revenue - cost_of_goods)
            if not use_external_pnl: stats['total_trading_pl'] += trading_pl_deal

            stats['total_sold_vol'] += event['vol']
            stats['total_sell_cost'] += cost_of_goods 

            self.trade_log.append({
                'Ngày': date_obj, 'Mã': symbol, 'Loại': 'BÁN',
                'SL': event['vol'], 'Giá Bán': event['price'], 'Giá Vốn': cost_of_goods/event['vol'] if event['vol']>0 else 0,
                'Lãi/Lỗ': trading_pl_deal, 'Nguồn': "VPS (File)" if use_external_pnl else "VCK (FIFO)"
            })

            if state['current_cycle']:
                cyc = state['current_cycle']
                cyc['total_sell_val'] += net_revenue
                cyc['total_sell_vol'] += event['vol']
                if not use_external_pnl: cyc['trading_pl'] += trading_pl_deal
                if sum(b['vol'] for b in inv) <= 0.001:
                    cyc['end_date'] = date_obj
                    cyc['status'] = 'Closed'
                    state['closed_cycles'].append(cyc)
                    state['current_cycle'] = None

        # --- DIVIDEND ---
        elif event['type'] == 'DIVIDEND':
            val = event.get('val', 0)
            stats['total_dividend'] += val
            if state['current_cycle']: state['current_cycle']['dividend_pl'] += val
            self.trade_log.append({'Ngày': date_obj, 'Mã': symbol, 'Loại': 'CỔ TỨC', 'SL': 0, 'Giá Bán': 0, 'Giá Vốn': 0, 'Lãi/Lỗ': val, 'Nguồn': 'Dòng Tiền'})
            curr_vol = sum(b['vol'] for b in inv)
            if curr_vol > 0:
                reduction = val / curr_vol
                for batch in inv: batch['adj_cost'] -= reduction

        # --- FEE ---
        elif event['type'] == 'FEE':
            val = event.get('val', 0)
            stats['total_trading_pl'] -= val
            if state['current_cycle']: state['current_cycle']['trading_pl'] -= val
            self.trade_log.append({'Ngày': date_obj, 'Mã': symbol, 'Loại': 'PHÍ/THUẾ', 'SL': 0, 'Giá Bán': 0, 'Giá Vốn': 0, 'Lãi/Lỗ': -val, 'Nguồn': 'Sheet Tiền'})

    def generate_reports(self):
        report_summary, report_cycles, report_inventory, report_warnings = [], [], [], []
        total_portfolio_value = 0
        temp_stats = {}

        # Tính tổng giá trị danh mục (bao gồm cả WFT để tính tỷ trọng đúng)
        for sym, state in self.data.items():
            inv = state['inventory']
            curr_val = sum(b['vol'] * b['cost'] for b in inv)
            total_portfolio_value += curr_val
            temp_stats[sym] = curr_val

        for sym, state in self.data.items():
            inv = state['inventory']
            stats = state['stats']
            curr_vol = sum(b['vol'] for b in inv)
            curr_val_org = temp_stats[sym]
            curr_val_adj = sum(b['vol'] * b['adj_cost'] for b in inv)
            
            # --- XỬ LÝ ẨN/HIỆN MÃ WFT ---
            # 1. Luôn thêm vào Báo Cáo Kho (Inventory) để theo dõi tài sản
            for b in inv:
                report_inventory.append({'Mã CK': sym, 'Ngày Mua': b['date'].strftime('%d/%m/%Y'), 'SL Tồn': b['vol'], 'Giá Vốn Gốc': b['cost'], 'Giá Vốn ĐC': b['adj_cost'], 'Ngày Giữ': (self.today - b['date']).days})

            # 2. Bỏ qua WFT ở các báo cáo Hiệu suất & Cycle
            if sym.endswith('_WFT'):
                continue 

            # Các chỉ số cho Báo cáo Hiệu suất
            alloc_pct = (curr_val_org / total_portfolio_value * 100) if total_portfolio_value > 0 else 0
            avg_hold_held = 0
            if curr_vol > 0: avg_hold_held = sum(((self.today - b['date']).days) * b['vol'] for b in inv) / curr_vol
            avg_hold_sold = 0
            if stats['total_sold_vol'] > 0: avg_hold_sold = stats['weighted_sold_days'] / stats['total_sold_vol']
            cost_basis_sold = stats['total_sell_cost']
            roi_trading = (stats['total_trading_pl'] / cost_basis_sold * 100) if cost_basis_sold > 0 else 0
            total_net_profit = stats['total_trading_pl'] + stats['total_dividend']

            report_summary.append({
                'Mã CK': sym, 'Tổng SL Đã Bán': stats['total_sold_vol'],
                'Lãi/Lỗ Giao Dịch': stats['total_trading_pl'],
                'Cổ Tức Đã Nhận': stats['total_dividend'],
                'Tổng Lãi Thực': total_net_profit,
                '% Hiệu Suất (Trade)': roi_trading,
                'SL Đang Giữ': curr_vol,
                'Vốn Gốc (Mua)': curr_val_org, 'Vốn Hợp Lý (Sau Cổ Tức)': curr_val_adj, 
                'Tổng Vốn Đã Rót': stats['total_invested_capital'],
                '% Tỷ Trọng Vốn': alloc_pct,
                'Ngày Giữ TB (Đã Bán)': avg_hold_sold, 'Tuổi Kho TB': avg_hold_held
            })

            # Báo cáo Cycle (Cũng ẩn WFT)
            all_cycles = state['closed_cycles'] + ([state['current_cycle']] if state['current_cycle'] else [])
            for cyc in all_cycles:
                end_d = cyc.get('end_date')
                duration = (end_d - cyc['start_date']).days if end_d else (self.today - cyc['start_date']).days
                status_str = 'Đã tất toán' if end_d else 'Đang nắm giữ'
                end_str = end_d.strftime('%d/%m/%Y') if end_d else ""
                total_cycle_pl = cyc['trading_pl'] + cyc['dividend_pl']
                roi_cyc = (total_cycle_pl / cyc['total_buy_val'] * 100) if cyc['total_buy_val'] > 0 else 0
                report_cycles.append({'Mã CK': sym, 'Ngày Bắt Đầu': cyc['start_date'].strftime('%d/%m/%Y'), 'Ngày Kết Thúc': end_str, 'Tuổi Vòng Đời (Ngày)': duration, 'Tổng Vốn Mua': cyc['total_buy_val'], 'Lãi Giao Dịch': cyc['trading_pl'], 'Cổ Tức': cyc['dividend_pl'], 'Tổng Lãi Cycle': total_cycle_pl, '% ROI Cycle': roi_cyc, 'Trạng Thái': status_str})

            if curr_vol > 0 and avg_hold_held > 90:
                report_warnings.append({'Mã CK': sym, 'Vốn Kẹp': curr_val_org, 'Tuổi Kho TB': avg_hold_held, 'Cảnh Báo': 'Kẹp hàng > 90 ngày'})

        return (pd.DataFrame(report_summary), pd.DataFrame(report_cycles), pd.DataFrame(report_inventory), pd.DataFrame(report_warnings))

    @property
    def total_profit(self):
        t_trade = sum(s['stats']['total_trading_pl'] for s in self.data.values())
        t_div = sum(s['stats']['total_dividend'] for s in self.data.values())
        return t_trade + t_div