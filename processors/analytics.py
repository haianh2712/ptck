# File: processors/analytics.py
# Module: NAV Analytics (Chuẩn hóa định dạng TimeMachine cũ)
import pandas as pd

class NAVAnalytics:
    def process_chart_data(self, events):
        """
        Input: Danh sách sự kiện (List of dicts)
        Output: DataFrame chuẩn format cũ (Tiếng Việt) để vẽ biểu đồ 2 đường.
        """
        # 1. Sắp xếp sự kiện theo thời gian
        # Thêm prio để đảm bảo thứ tự: Nạp tiền -> Mua -> Bán -> Chốt lãi
        sorted_events = sorted(events, key=lambda x: (x['date'], x.get('prio', 50)))
        
        # 2. Các biến trạng thái (State)
        current_cash = 0.0
        current_deposit = 0.0 # [QUAN TRỌNG] Theo dõi vốn nạp ròng để vẽ đường Vốn
        current_stock_value = 0.0
        
        # Theo dõi giá vốn từng mã để trừ kho chính xác
        portfolio_state = {} # {Ticker: {vol, cost}}
        
        history = []
        
        for ev in sorted_events:
            etype = ev.get('type', '')
            
            # Logic lấy giá trị: PNL_UPDATE lấy cả số âm, còn lại lấy số dương
            if etype == 'PNL_UPDATE':
                val = ev.get('value', 0)
            else:
                val = ev.get('value', 0) if ev.get('value', 0) > 0 else ev.get('val', 0)
            
            # --- A. XỬ LÝ DÒNG TIỀN (CASH & DEPOSIT) ---
            if etype in ['NAP_TIEN', 'DEPOSIT']:
                current_cash += val
                current_deposit += val # Tăng vốn nạp
            
            elif etype in ['RUT_TIEN', 'WITHDRAW']:
                current_cash -= val
                current_deposit -= val # Giảm vốn nạp
            
            elif etype in ['PHI_THUE']:
                current_cash -= val
                # Phí thuế làm giảm tiền nhưng KHÔNG giảm Vốn Nạp (nó là chi phí)
            
            elif etype in ['CO_TUC_TIEN', 'DIVIDEND', 'BAN_TIEN_VE', 'UNG_TRUOC']:
                current_cash += val
            
            elif etype == 'HOAN_UNG':
                current_cash -= val
            
            elif etype == 'CASH_SNAPSHOT':
                if val > 0: current_cash = val

            # --- B. XỬ LÝ MUA/BÁN & KHO ---
            elif etype in ['MUA', 'BUY']:
                vol = ev.get('qty', 0)
                price = ev.get('price', 0)
                cost = val if val > 0 else (vol * price)
                
                # Mua: Trừ tiền, Cộng giá trị cổ phiếu
                current_cash -= cost
                current_stock_value += cost
                
                # Lưu state
                sym = ev.get('ticker')
                if sym:
                    if sym not in portfolio_state: portfolio_state[sym] = {'vol': 0, 'cost': 0}
                    portfolio_state[sym]['vol'] += vol
                    portfolio_state[sym]['cost'] += cost

            elif etype in ['BAN', 'SELL']:
                vol = ev.get('qty', 0)
                use_ext = ev.get('use_external_pnl', False)
                sym = ev.get('ticker')
                
                # Tính giá vốn hàng bán để trừ kho
                cost_of_goods = 0
                if sym and sym in portfolio_state:
                    p = portfolio_state[sym]
                    if p['vol'] > 0:
                        avg_price = p['cost'] / p['vol']
                        cost_of_goods = vol * avg_price
                        
                        # Trừ kho
                        p['vol'] -= vol
                        p['cost'] -= cost_of_goods
                        current_stock_value -= cost_of_goods
                
                # Xử lý Tiền về
                if use_ext:
                    # [VPS FIX]: Bán xong -> Hoàn GIÁ VỐN vào tiền mặt ngay
                    # Để NAV không bị tụt. Lãi/Lỗ tính sau.
                    current_cash += cost_of_goods
                else:
                    # [VCK]: Bán xong -> Cộng Doanh thu (Vốn + Lãi)
                    price = ev.get('price', 0)
                    fee = ev.get('fee', 0)
                    revenue = (price * vol) - fee
                    current_cash += revenue

            elif etype == 'PNL_UPDATE':
                # [VPS]: Cộng phần Lãi (hoặc trừ Lỗ) thực tế vào tiền mặt
                current_cash += val

            # --- C. SNAPSHOT CUỐI NGÀY ---
            d_date = ev['date'].date()
            nav = current_cash + current_stock_value
            
            # Logic ghi nhận dữ liệu cuối ngày
            # Dùng tên cột Tiếng Việt y hệt TimeMachine cũ để Chart cũ hiểu
            snapshot = {
                'Ngày': pd.Timestamp(d_date),
                'Tổng Tài Sản (NAV)': nav,
                'Vốn Nạp Ròng': current_deposit, # Cột quan trọng để vẽ đường thứ 2
                'Tiền Mặt': current_cash,
                'Giá Trị Cổ Phiếu': current_stock_value
            }
            
            if not history or history[-1]['Ngày'].date() != d_date:
                history.append(snapshot)
            else:
                history[-1].update(snapshot)

        # Chuyển thành DataFrame
        df = pd.DataFrame(history)
        if not df.empty:
            df = df.set_index('Ngày').sort_index().reset_index()
            
        return df