# File: processors/live_price.py
import yfinance as yf
import pandas as pd
import streamlit as st

def get_current_price_dict(ticker_list):
    """
    Lấy giá thị trường từ Yahoo Finance (Thông qua thư viện yfinance).
    Nguồn này KHÔNG CHẶN IP Cloud, hoạt động ổn định trên Streamlit Cloud.
    """
    if not ticker_list:
        return {}
    
    # 1. Chuẩn hóa mã (Yahoo yêu cầu đuôi .VN cho cổ phiếu Việt Nam)
    # Lưu ý: Sàn UPCOM đôi khi không có trên Yahoo hoặc mã khác, nhưng HOSE/HNX thì ổn.
    clean_tickers = [str(t).strip().upper() for t in ticker_list if t]
    clean_tickers = list(set(clean_tickers))
    
    if not clean_tickers:
        return {}

    # Map: 'HPG' -> 'HPG.VN' để gọi API, sau đó map ngược lại để trả kết quả
    yahoo_map = {t: f"{t}.VN" for t in clean_tickers}
    yahoo_symbols = list(yahoo_map.values())
    
    price_dict = {}
    
    try:
        # 2. Gọi API Yahoo (Tải hàng loạt để nhanh hơn)
        # period='1d' để lấy dữ liệu phiên mới nhất
        data = yf.download(yahoo_symbols, period="1d", progress=False)
        
        if data.empty:
            print("⚠️ Yahoo Finance không trả về dữ liệu.")
            return {}

        # 3. Trích xuất giá mới nhất
        # yfinance trả về DataFrame MultiIndex nếu nhiều mã
        # Chúng ta lấy cột 'Close' (Giá đóng cửa/giá hiện tại)
        
        # Lấy dòng cuối cùng (giá mới nhất)
        if 'Close' in data:
            last_rows = data['Close'].iloc[-1]
            
            # Duyệt qua từng mã gốc để lấy giá
            for sym_raw, sym_vn in yahoo_map.items():
                try:
                    # Trường hợp 1: Tải nhiều mã, last_rows là Series có index là mã .VN
                    if isinstance(last_rows, pd.Series):
                        if sym_vn in last_rows:
                            price = last_rows[sym_vn]
                            if pd.notna(price):
                                price_dict[sym_raw] = float(price)
                    
                    # Trường hợp 2: Tải 1 mã, last_rows có thể là số float
                    elif len(yahoo_symbols) == 1:
                        # Khi tải 1 mã, structure có thể khác, ta check trực tiếp
                        val = data['Close'].iloc[-1]
                        # Nếu nó là Series (thường gặp ở bản mới), lấy .item()
                        if isinstance(val, pd.Series):
                            val = val.item()
                        price_dict[sym_raw] = float(val)

                except Exception as ex:
                    print(f"Lỗi parse mã {sym_raw}: {ex}")
                    continue

        print(f"✅ [Yahoo] Đã lấy giá cho {len(price_dict)} mã.")
        
    except Exception as e:
        print(f"❌ Lỗi yfinance: {e}")
    
    return price_dict
