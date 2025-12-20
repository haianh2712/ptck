# File: processors/engine.py
# Version: RESTORED PROFIT LOGIC + CHART SUPPORT
from collections import deque
import pandas as pd
from datetime import datetime
from processors.analytics import NAVAnalytics # Module vẽ biểu đồ

class PortfolioEngine:
    def __init__(self, source_name="Unknown"):
        self.source_name = source_name
        self.today = pd.Timestamp.now().normalize()
        
        self.total_deposit = 0.0       
        self.real_cash_balance = 0.0   
        self.total_profit = 0.0  # [LOGIC CŨ] Biến này sẽ cộng dồn trực tiếp
        
        self.data = {}
        self.trade_log = []
        self.all_raw_events = [] # Kho lưu sự kiện để vẽ chart

    def clean_symbol(self, sym):
        if pd.isna(sym) or sym is None: return None
        s = str(sym).strip().upper()
        if s == 'NAN' or s == '': return None
        return s

    def get_ticker_state(self, symbol):
        clean_sym = self.clean_symbol(symbol)
        if not clean_sym: return None
        if clean_sym not in self.data:
            self.data[clean_sym] = {
                'inventory': deque(), 'closed_cycles': [], 'current_cycle': None,      
                'stats': {
                    'total_sold_vol': 0, 'total_trading_pl': 0, 'total_dividend': 0, 
                    'total_invested_capital': 0, 'total_sell_cost': 0, 'weighted_sold_days': 0,
                    'has_external_pnl': False
                }
            }
        return self.data[clean_sym]

    def process_event(self, event):
        # 1. Lưu sự kiện để vẽ chart
        self.all_raw_events.append(event)
        
        try: date_obj = pd.Timestamp(event['date'])
        except: return

        etype = event.get('type', '')
        # Logic lấy giá trị: VPS PNL lấy cả âm, VCK chỉ lấy dương
        if etype == 'PNL_UPDATE':
            val = event.get('value', 0)
        else:
            val = event.get('value', 0) if event.get('value', 0) > 0 else event.get('val', 0)

        # --- XỬ LÝ DÒNG TIỀN ---
        if etype == 'PHI_THUE':
            self.real_cash_balance -= val
            self.total_profit -= val # [LOGIC CŨ] Trừ thẳng vào tổng
            self.trade_log.append({'Ngày': date_obj, 'Mã': 'PHÍ', 'Loại': 'PHÍ/THUẾ', 'SL': 0, 'Giá Bán': 0, 'Giá Vốn': 0, 'Lãi/Lỗ': -val, 'Nguồn': event.get('desc', 'Chi phí')})
            return

        if etype in ['NAP_TIEN', 'DEPOSIT']:
            self.total_deposit += val
            self.real_cash_balance += val
            return

        if etype in ['RUT_TIEN', 'WITHDRAW']:
            self.total_deposit -= val
            self.real_cash_balance -= val
            return

        if etype in ['BAN_TIEN_VE', 'UNG_TRUOC', 'CASH_SNAPSHOT']:
            if val > 0: 
                if etype == 'CASH_SNAPSHOT': self.real_cash_balance = val
                else: self.real_cash_balance += val
            return
        
        if etype == 'HOAN_UNG':
            self.real_cash_balance -= val
            return

        # --- KHỚP LỆNH ---
        raw_sym = event.get('ticker') or event.get('sym')
        symbol = self.clean_symbol(raw_sym)
        if not symbol: return 

        state = self.get_ticker_state(symbol)
        inv = state['inventory']
        stats = state['stats']

        if etype == 'PNL_UPDATE':
            stats['total_trading_pl'] += val
            stats['has_external_pnl'] = True
            
            self.total_profit += val # [LOGIC CŨ] Cộng thẳng vào tổng
            self.real_cash_balance += val 
            
            self.trade_log.append({'Ngày': date_obj, 'Mã': symbol, 'Loại': 'CHỐT LÃI (FILE)', 'SL': 0, 'Giá Bán': 0, 'Giá Vốn': 0, 'Lãi/Lỗ': val, 'Nguồn': 'Excel PnL'})
            if state['current_cycle']: state['current_cycle']['trading_pl'] += val

        elif etype in ['MUA', 'BUY']:
            vol = event.get('qty', 0) or event.get('vol', 0)
            price = event.get('price', 0)
            cost = val if val > 0 else (vol * price)
            self.real_cash_balance -= cost
            if vol > 0:
                unit_cost = cost / vol
                inv.append({'date': date_obj, 'vol': vol, 'cost': unit_cost, 'adj_cost': unit_cost})
                stats['total_invested_capital'] += cost
                if state['current_cycle'] is None: state['current_cycle'] = {'start_date': date_obj, 'total_buy_val': 0, 'total_buy_vol': 0, 'total_sell_val': 0, 'total_sell_vol': 0, 'trading_pl': 0, 'dividend_pl': 0, 'status': 'Open'}
                cyc = state['current_cycle']
                cyc['total_buy_val'] += cost
                cyc['total_buy_vol'] += vol
                self.trade_log.append({'Ngày': date_obj, 'Mã': symbol, 'Loại': 'MUA', 'SL': vol, 'Giá Vốn': unit_cost, 'Lãi/Lỗ': 0, 'Nguồn': 'Giao Dịch Mua'})

        elif etype in ['BAN', 'SELL']:
            vol = event.get('qty', 0) or event.get('vol', 0)
            price = event.get('price', 0)
            use_ext_pnl = event.get('use_external_pnl', False)
            net_rev = (price * vol) - event.get('fee', 0)
            
            qty_needed = vol; cost_goods = 0 
            while qty_needed > 0 and inv:
                batch = inv[0]
                take = min(qty_needed, batch['vol'])
                cost_goods += take * batch['cost']
                stats['weighted_sold_days'] += (date_obj - batch['date']).days * take
                batch['vol'] -= take; qty_needed -= take
                if batch['vol'] <= 0.0001: inv.popleft()

            pl_deal = 0 if use_ext_pnl else (net_rev - cost_goods)
            if not use_ext_pnl: 
                stats['total_trading_pl'] += pl_deal
                self.total_profit += pl_deal # [LOGIC CŨ] Chỉ cộng nếu là VCK (không dùng pnl ngoài)
                
            stats['total_sold_vol'] += vol
            stats['total_sell_cost'] += cost_goods 
            
            if use_ext_pnl:
                self.real_cash_balance += cost_goods 
            
            self.trade_log.append({'Ngày': date_obj, 'Mã': symbol, 'Loại': 'BÁN', 'SL': vol, 'Giá Bán': price, 'Giá Vốn': cost_goods/vol if vol>0 else 0, 'Lãi/Lỗ': pl_deal, 'Nguồn': 'Giao Dịch Bán'})
            if state['current_cycle']:
                cyc = state['current_cycle']
                cyc['total_sell_val'] += net_rev; cyc['total_sell_vol'] += vol
                if not use_ext_pnl: cyc['trading_pl'] += pl_deal
                if sum(b['vol'] for b in inv) <= 0.001:
                    cyc['end_date'] = date_obj; cyc['status'] = 'Closed'
                    state['closed_cycles'].append(cyc); state['current_cycle'] = None

        elif etype in ['CO_TUC_TIEN', 'DIVIDEND']:
            val = event.get('val', 0) or event.get('value', 0)
            self.real_cash_balance += val
            self.total_profit += val # [LOGIC CŨ] Cộng thẳng cổ tức
            
            stats['total_dividend'] += val
            if state['current_cycle']: state['current_cycle']['dividend_pl'] += val
            self.trade_log.append({'Ngày': date_obj, 'Mã': symbol, 'Loại': 'CỔ TỨC', 'SL': 0, 'Giá Bán': 0, 'Giá Vốn': 0, 'Lãi/Lỗ': val, 'Nguồn': 'Nhận Cổ Tức'})
            curr_vol = sum(b['vol'] for b in inv)
            if curr_vol > 0:
                red = val / curr_vol
                for b in inv: b['adj_cost'] -= red

        elif etype == 'FEE':
            val = event.get('val', 0)
            stats['total_trading_pl'] -= val
            self.total_profit -= val # [LOGIC CŨ] Trừ phí
            if state['current_cycle']: state['current_cycle']['trading_pl'] -= val
            self.trade_log.append({'Ngày': date_obj, 'Mã': symbol, 'Loại': 'PHÍ/THUẾ', 'SL': 0, 'Giá Bán': 0, 'Giá Vốn': 0, 'Lãi/Lỗ': -val, 'Nguồn': 'Trừ Phí'})

    # --- CÁC HÀM GETTER ---
    
    def generate_reports(self):
        # [GIỮ NGUYÊN CODE REPORT CŨ CỦA BẠN]
        rep_sum, rep_cyc, rep_inv, rep_warn = [], [], [], []
        
        total_val = 0
        for sym, s in self.data.items():
            if self.clean_symbol(sym): total_val += sum(b['vol']*b['cost'] for b in s['inventory'])

        for sym, state in self.data.items():
            if not self.clean_symbol(sym): continue 
            inv = state['inventory']; stats = state['stats']
            curr_vol = sum(b['vol'] for b in inv)
            curr_val_org = sum(b['vol'] * b['cost'] for b in inv)
            curr_val_adj = sum(b['vol'] * b['adj_cost'] for b in inv)
            
            for b in inv: rep_inv.append({'Mã CK': sym, 'Ngày Mua': b['date'].strftime('%d/%m/%Y'), 'SL Tồn': b['vol'], 'Giá Vốn Gốc': b['cost'], 'Giá Vốn ĐC': b['adj_cost'], 'Ngày Giữ': (self.today - b['date']).days, 'Vốn Gốc (Mua)': b['vol'] * b['cost']})
            if str(sym).endswith('_WFT'): continue

            raw_trading_pl = stats['total_trading_pl']; total_div = stats['total_dividend']
            if stats.get('has_external_pnl', False):
                display_trading_pl = raw_trading_pl - total_div; display_total_pl = raw_trading_pl
            else:
                display_trading_pl = raw_trading_pl; display_total_pl = raw_trading_pl + total_div

            avg_hold_held = sum(((self.today - b['date']).days) * b['vol'] for b in inv) / curr_vol if curr_vol > 0 else 0
            avg_hold_sold = stats['weighted_sold_days'] / stats['total_sold_vol'] if stats['total_sold_vol'] > 0 else 0
            
            rep_sum.append({'Mã CK': sym, 'Tổng SL Đã Bán': stats['total_sold_vol'], 'Lãi/Lỗ Giao Dịch': display_trading_pl, 'Cổ Tức Đã Nhận': total_div, 'Tổng Lãi Thực': display_total_pl, '% Hiệu Suất (Trade)': (display_trading_pl / stats['total_sell_cost'] * 100) if stats['total_sell_cost'] > 0 else 0, 'SL Đang Giữ': curr_vol, 'Vốn Gốc (Mua)': curr_val_org, 'Vốn Hợp Lý (Sau Cổ Tức)': curr_val_adj, 'Tổng Vốn Đã Rót': stats['total_invested_capital'], '% Tỷ Trọng Vốn': (curr_val_org / total_val * 100) if total_val > 0 else 0, 'Ngày Giữ TB (Đã Bán)': avg_hold_sold, 'Tuổi Kho TB': avg_hold_held})

            all_c = state['closed_cycles'] + ([state['current_cycle']] if state['current_cycle'] else [])
            for c in all_c:
                end_d = c.get('end_date')
                dur = (end_d - c['start_date']).days if end_d else (self.today - c['start_date']).days
                cycle_pl = c['trading_pl'] + c['dividend_pl']
                roi = (cycle_pl / c['total_buy_val'] * 100) if c['total_buy_val'] > 0 else 0
                rep_cyc.append({'Mã CK': sym, 'Ngày Bắt Đầu': c['start_date'].strftime('%d/%m/%Y'), 'Ngày Kết Thúc': end_d.strftime('%d/%m/%Y') if end_d else "", 'Tuổi Vòng Đời': dur, 'Tổng Vốn Mua': c['total_buy_val'], 'Lãi Giao Dịch': c['trading_pl'], 'Cổ Tức': c['dividend_pl'], 'Tổng Lãi Cycle': cycle_pl, '% ROI Cycle': roi, 'Trạng Thái': 'Đã tất toán' if end_d else 'Đang nắm giữ'})

            if curr_vol > 0 and avg_hold_held > 90: rep_warn.append({'Mã CK': sym, 'Vốn Kẹp': curr_val_org, 'Tuổi Kho TB': avg_hold_held, 'Cảnh Báo': '> 90 ngày'})

        return (pd.DataFrame(rep_sum), pd.DataFrame(rep_cyc), pd.DataFrame(rep_inv), pd.DataFrame(rep_warn))

    def get_all_closed_cycles(self):
        # [GIỮ NGUYÊN CODE CŨ]
        res = []
        for sym, state in self.data.items():
            if not self.clean_symbol(sym): continue 
            if str(sym).endswith('_WFT'): continue
            for c in state['closed_cycles']:
                cc = c.copy(); cc['Mã CK'] = sym
                if state['stats'].get('has_external_pnl', False): cc['Lãi/Lỗ'] = cc.get('trading_pl', 0)
                else: cc['Lãi/Lỗ'] = cc.get('trading_pl', 0) + cc.get('dividend_pl', 0)
                cc['Tuổi Vòng Đời'] = (cc['end_date'] - cc['start_date']).days if cc.get('end_date') else 0
                cost = cc.get('total_buy_val', 0); cc['Tổng Vốn Mua'] = cost; cc['pnl_value'] = cc['Lãi/Lỗ'] 
                if cost > 0: cc['% ROI Cycle'] = (cc['Lãi/Lỗ'] / cost) * 100
                else: cc['% ROI Cycle'] = 0
                res.append(cc)
        return res

    @property
    def total_profit_calc(self):
        # [QUAN TRỌNG] Trả về biến cộng dồn self.total_profit
        # Đây là cách chính xác nhất để khớp với số liệu Dashboard cũ
        return self.total_profit

    # --- HÀM LẤY DỮ LIỆU BIỂU ĐỒ (GỌI ANALYTICS) ---
    def get_nav_chart_data(self):
        """Chuyển events sang Analytics để vẽ biểu đồ"""
        analytics = NAVAnalytics()
        return analytics.process_chart_data(self.all_raw_events)