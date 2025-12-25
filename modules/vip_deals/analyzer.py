import pandas as pd

def analyze_cost_advantage(engine):
    """
    Hàm lõi: Phân tách giá vốn thành 2 nguồn: VIP Deal vs Trading
    """
    # 1. Kiểm tra đầu vào
    if not engine or not hasattr(engine, 'trade_log') or not engine.trade_log:
        return pd.DataFrame()

    df = pd.DataFrame(engine.trade_log)
    df.columns = [str(c).lower().strip() for c in df.columns]

    # Map cột
    col_map = {
        'mã': 'ticker', 'loại': 'type', 'nguồn': 'source',
        'sl': 'qty', 'giá vốn': 'price_unit'
    }
    df = df.rename(columns=col_map)

    if 'value' not in df.columns and 'qty' in df.columns and 'price_unit' in df.columns:
        df['value'] = df['qty'] * df['price_unit']

    if 'type' not in df.columns: return pd.DataFrame()
    
    # 2. Lọc lệnh MUA
    df_buy = df[df['type'].str.upper().isin(['BUY', 'MUA', 'NHẬP'])].copy()
    if df_buy.empty: return pd.DataFrame()

    # 3. [FIX MỚI] LÀM SẠCH TÊN MÃ (GỘP WFT VÀO GỐC)
    # Loại bỏ đuôi _WFT, _PENDING để POW và POW_WFT được coi là 1 mã
    if 'ticker' in df_buy.columns:
        df_buy['ticker_clean'] = df_buy['ticker'].astype(str).str.replace('_WFT', '', regex=False).str.replace('_PENDING', '', regex=False).str.strip()
    else:
        return pd.DataFrame()

    # 4. Phân loại nguồn gốc
    def classify_source(src):
        src = str(src).upper()
        if any(k in src for k in ['IPO', 'DEAL', 'CHUYỂN ĐỔI', 'QUYỀN', 'CONVERT', 'WFT']):
            return 'VIP Deal'
        return 'Trading'

    if 'source' in df_buy.columns:
        df_buy['Category'] = df_buy['source'].apply(classify_source)
    else:
        df_buy['Category'] = 'Trading'

    # 5. Tính toán (Group theo TICKER_CLEAN)
    # Thay vì group theo 'ticker', ta group theo 'ticker_clean'
    df_stats = df_buy.groupby(['ticker_clean', 'Category']).apply(
        lambda x: pd.Series({
            'Total_Value': x['value'].sum(),
            'Total_Qty': x['qty'].sum()
        })
    ).reset_index()
    
    df_stats['Avg_Price'] = df_stats['Total_Value'] / df_stats['Total_Qty']
    
    # 6. Pivot
    # Index bây giờ là mã sạch (POW) -> Sẽ có cả 2 cột
    df_pivot = df_stats.pivot(index='ticker_clean', columns='Category', values='Avg_Price')
    return df_pivot.fillna(0)

def analyze_cashflow_sankey(engine):
    # (Giữ nguyên hàm này không đổi)
    if not engine: return {}
    total_dep = getattr(engine, 'total_deposit', 0)
    cash_balance = getattr(engine, 'real_cash_balance', 0)
    
    if not engine.trade_log: return {}
    df = pd.DataFrame(engine.trade_log)
    df.columns = [str(c).lower().strip() for c in df.columns]
    
    col_map = {'loại': 'type', 'nguồn': 'source', 'sl': 'qty', 'giá vốn': 'price_unit'}
    df = df.rename(columns=col_map)
    
    if 'value' not in df.columns: df['value'] = df['qty'] * df['price_unit']
    
    deal_mask = df['source'].str.upper().str.contains('IPO|DEAL|CHUYỂN|QUYỀN|WFT', na=False)
    trading_mask = ~deal_mask
    
    deal_value = df[(df['type'].str.upper().isin(['BUY','MUA'])) & deal_mask]['value'].sum()
    trading_value = df[(df['type'].str.upper().isin(['BUY','MUA'])) & trading_mask]['value'].sum()
    
    data = {'source': [], 'target': [], 'value': [], 'label': []}
    
    if deal_value > 0:
        data['source'].append(0); data['target'].append(1); data['value'].append(deal_value)
        data['label'].append(f"Vốn Săn Deal: {deal_value:,.0f}")
        
    if trading_value > 0:
        data['source'].append(0); data['target'].append(2); data['value'].append(trading_value)
        data['label'].append(f"Vốn Lướt Sóng: {trading_value:,.0f}")
        
    if cash_balance > 0:
        data['source'].append(0); data['target'].append(3); data['value'].append(cash_balance)
        data['label'].append(f"Tiền Nhàn Rỗi: {cash_balance:,.0f}")
        
    return data