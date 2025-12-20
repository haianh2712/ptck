# File: processors/live_price.py
# Version: ULTIMATE HYBRID (Yahoo + Cophieu68 Parsing)
# Logic: Yahoo (Nhanh, cho HOSE) + Cophieu68 (Chính xác, cho UPCOM/Mã thiếu)

import yfinance as yf
import requests
import re
import pandas as pd
import threading

def get_current_price_dict(ticker_list):
    """
    Hệ thống lấy giá đa luồng:
    1. Yahoo Finance: Tốc độ cao, ưu tiên hàng đầu.
    2. Cophieu68.vn: Nguồn backup tin cậy cho mã UPCOM hoặc khi Yahoo thiếu.
    """
    if not ticker_list: return {}

    # 1. Lọc và chuẩn hóa
    clean_tickers = []
    wft_tickers = []
    for t in ticker_list:
        t_str = str(t).strip().upper()
        if t_str.endswith('_WFT'):
            wft_tickers.append(t_str)
        elif len(t_str) >= 3:
            clean_tickers.append(t_str)
    
    clean_tickers = list(set(clean_tickers))
    final_prices = {t: 0 for t in wft_tickers}
    
    if not clean_tickers: return final_prices

    # =========================================================================
    # PHASE 1: YAHOO FINANCE (NGUỒN CHÍNH)
    # =========================================================================
    yahoo_map = {f"{t}.VN": t for t in clean_tickers}
    yahoo_symbols = list(yahoo_map.keys())
    found_tickers = []
    
    try:
        data = yf.download(yahoo_symbols, period="1d", group_by='ticker', threads=True, progress=False)
        
        def get_p(df_sym):
            if df_sym.empty: return 0
            # Ưu tiên Close, fallback Open
            p = df_sym.iloc[-1].get('Close', 0)
            if pd.isna(p) or p == 0: p = df_sym.iloc[-1].get('Open', 0)
            return p

        if len(yahoo_symbols) == 1:
            sym_y = yahoo_symbols[0]
            price = get_p(data)
            if price > 0:
                final_prices[yahoo_map[sym_y]] = _normalize_price(price)
                found_tickers.append(yahoo_map[sym_y])
        else:
            for sym_y in yahoo_symbols:
                try:
                    if sym_y in data.columns.levels[0]:
                        price = get_p(data[sym_y])
                        if price > 0:
                            final_prices[yahoo_map[sym_y]] = _normalize_price(price)
                            found_tickers.append(yahoo_map[sym_y])
                except: pass
    except: pass

    # =========================================================================
    # PHASE 2: COPHIEU68 SCRAPING (VÉT CÁC MÃ THIẾU)
    # =========================================================================
    missing = [t for t in clean_tickers if t not in found_tickers]
    
    if missing:
        # print(f"🛡️ Đang gọi Cophieu68 cho {len(missing)} mã thiếu...")
        
        def scrape_cp68(sym):
            try:
                url = f"https://www.cophieu68.vn/quote/summary.php?id={sym}"
                headers = {'User-Agent': 'Mozilla/5.0'}
                resp = requests.get(url, headers=headers, timeout=8)
                
                if resp.status_code == 200:
                    html = resp.text
                    price = 0
                    
                    # --- CHIẾN THUẬT REGEX CHÍNH XÁC ---
                    # Tìm thẻ <strong id="stockname_close">26.5</strong>
                    # Đây là thẻ chứa giá khớp lệnh chuẩn của Cophieu68
                    match = re.search(r'id="stockname_close"[^>]*?>\s*([\d\.,]+)\s*<', html)
                    
                    if match:
                        p_str = match.group(1).replace(',', '')
                        price = float(p_str)
                    else:
                        # Backup: Tìm trong thẻ strong có style color (thường là giá biến động)
                        # <strong style="color:#00cc00;">26.5</strong>
                        # Chỉ lấy nếu giá trị hợp lý (< 200) để tránh bắt nhầm Volume
                        matches = re.findall(r'<strong[^>]*>\s*([\d\.,]+)\s*</strong>', html)
                        for m in matches:
                            try:
                                val = float(m.replace(',', ''))
                                if 0.1 < val < 200: # Giá CP thường nằm trong khoảng này (nghìn đồng)
                                    price = val
                                    break
                            except: continue

                    if price > 0:
                        final_prices[sym] = _normalize_price(price)
                        
            except: pass

        # Chạy đa luồng để không bị chậm
        threads = []
        for sym in missing:
            t = threading.Thread(target=scrape_cp68, args=(sym,))
            threads.append(t)
            t.start()
        for t in threads: t.join()

    return final_prices

def _normalize_price(price):
    """Chuẩn hóa giá về VND (26500)"""
    try:
        p = float(price)
        # Yahoo trả về 26500 hoặc 26.5 tùy mã
        # Cophieu68 trả về 26.5 (nghìn đồng)
        
        # Logic an toàn: Nếu < 5000 (tức là đang ở dạng nghìn đồng 26.5) -> Nhân 1000
        # Trừ trường hợp cổ phiếu rác giá < 500 đồng thật (hiếm), nhưng an toàn cho đa số
        if 0 < p < 5000:
            p *= 1000
            
        return int(p)
    except:
        return 0

# Test nhanh
if __name__ == "__main__":
    test_list = ['HPG', 'SSI', 'BSR', 'VGI', 'ABC'] 
    print("🚀 Đang chạy Hybrid (Yahoo + Cophieu68)...")
    res = get_current_price_dict(test_list)
    print("Kết quả:", res)