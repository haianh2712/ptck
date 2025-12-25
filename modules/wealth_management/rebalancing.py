# File: modules/wealth_management/rebalancing.py
# Updated: Fix lỗi IntCastingNaNError (Xử lý NaN/Inf trước khi ép kiểu int)

import pandas as pd
import numpy as np # Import thêm numpy để xử lý số liệu an toàn

def calculate_rebalancing(engine, live_prices, targets):
    """
    engine: Engine tổng hợp (VCK + VPS)
    live_prices: Dict giá hiện tại
    targets: Dict { 'HPG': 20, 'FPT': 30 ... } (Đơn vị %)
    """
    # 1. Lấy dữ liệu hiện tại
    holdings = []
    
    # Lấy tiền mặt
    cash = engine.real_cash_balance
    if cash == 0: cash = engine.cash_balance # Fallback
    
    # Lấy cổ phiếu
    total_stock_val = 0
    if hasattr(engine, 'data'):
        for ticker, info in engine.data.items():
            qty = 0
            if 'inventory' in info:
                qty = sum(item['vol'] for item in info['inventory'])
            elif 'stats' in info:
                qty = info['stats'].get('curr_vol', 0)
            
            if qty > 0:
                # Lấy giá thị trường (nếu không có thì lấy giá vốn)
                clean_tik = str(ticker).replace('_WFT', '').strip().upper()
                price = live_prices.get(clean_tik, 0)
                if price == 0: 
                    price = info.get('avg_price', 0) # Fallback giá vốn
                
                val = qty * price
                total_stock_val += val
                
                holdings.append({
                    'ticker': clean_tik,
                    'qty_current': qty,
                    'price': price,
                    'val_current': val
                })
    
    # Tổng tài sản NAV
    total_nav = cash + total_stock_val
    if total_nav == 0: return None

    # 2. Tính toán Rebalance
    df = pd.DataFrame(holdings)
    
    # Gom nhóm các mã giống nhau (VCK + VPS có thể trùng mã)
    if not df.empty:
        df = df.groupby('ticker').agg({
            'qty_current': 'sum',
            'price': 'first', # Giá giống nhau
            'val_current': 'sum'
        }).reset_index()

    # Thêm dòng Tiền mặt vào DataFrame để dễ tính
    cash_row = {'ticker': 'CASH (Tiền)', 'qty_current': cash, 'price': 1, 'val_current': cash}
    df = pd.concat([df, pd.DataFrame([cash_row])], ignore_index=True)

    # Tính tỷ trọng hiện tại
    df['pct_current'] = (df['val_current'] / total_nav) * 100
    
    # Map tỷ trọng mục tiêu (Target)
    # Target trả về là % (VD: 20)
    df['pct_target'] = df['ticker'].map(targets).fillna(0)
    
    # Xử lý Tiền mặt: Target tiền = 100% - Tổng target cổ phiếu
    stock_target_sum = df[df['ticker'] != 'CASH (Tiền)']['pct_target'].sum()
    df.loc[df['ticker'] == 'CASH (Tiền)', 'pct_target'] = max(0, 100 - stock_target_sum)
    
    # Tính toán chênh lệch
    df['val_target'] = (df['pct_target'] / 100) * total_nav
    df['val_diff'] = df['val_target'] - df['val_current']
    
    # --- [FIX LỖI] TÍNH TOÁN SỐ LƯỢNG AN TOÀN ---
    df['action_qty'] = 0
    
    # Chỉ tính cho những dòng có giá > 0 (tránh chia cho 0)
    mask = df['price'] > 0
    
    # Bước 1: Chia lấy kết quả thô (Float)
    # Dùng .loc để đảm bảo alignment
    raw_qty = df.loc[mask, 'val_diff'] / df.loc[mask, 'price']
    
    # Bước 2: Xử lý NaN và Infinity (Vô cực) thành 0
    # Đây là bước quan trọng để tránh lỗi IntCastingNaNError
    raw_qty = raw_qty.replace([np.inf, -np.inf], 0).fillna(0)
    
    # Bước 3: Ép kiểu int sau khi đã sạch dữ liệu
    df.loc[mask, 'action_qty'] = raw_qty.astype(int)
    # ----------------------------------------------
    
    # Gợi ý hành động
    def get_action(row):
        if row['ticker'] == 'CASH (Tiền)':
            if row['val_diff'] > 100000: return "Nạp thêm / Bán bớt CP"
            elif row['val_diff'] < -100000: return "Rút bớt / Mua thêm CP"
            else: return "OK"
        
        if row['action_qty'] > 0: return f"MUA {row['action_qty']:,}"
        elif row['action_qty'] < 0: return f"BÁN {abs(row['action_qty']):,}"
        else: return "Giữ"

    df['recommendation'] = df.apply(get_action, axis=1)
    
    return {
        'df': df,
        'total_nav': total_nav,
        'stock_target_sum': stock_target_sum
    }