# File: processors/live_price.py
import pandas as pd
try:
    from vnstock import price_board
except ImportError:
    price_board = None

def get_current_price_dict(ticker_list):
    """
    Lấy giá thị trường. Phiên bản "Hard-binding" cột Mã CP và Giá.
    """
    if not ticker_list:
        return {}
    
    # 1. Làm sạch danh sách đầu vào
    clean_tickers = list(set([str(t).strip().upper() for t in ticker_list if t]))
    
    if not clean_tickers or price_board is None:
        return {}

    try:
        # 2. Gọi API
        symbols_str = ",".join(clean_tickers)
        df = price_board(symbols_str)
        
        if df.empty:
            print("⚠️ API trả về bảng rỗng.")
            return {}
            
        # 3. Tự động tìm tên cột (Tránh lỗi do đổi tên)
        # Tìm cột chứa chữ "Mã" hoặc "Symbol"
        col_sym = next((c for c in df.columns if "Mã" in c or "Symbol" in c), None)
        # Tìm cột chứa chữ "Giá" hoặc "Price" (Ưu tiên 'Giá', bỏ qua 'Giá trần/sàn' nếu có)
        col_price = next((c for c in df.columns if c in ['Giá', 'Price', 'Khớp lệnh', 'Last']), None)

        if not col_sym or not col_price:
            print(f"❌ Không tìm thấy cột Mã/Giá. Các cột hiện có: {df.columns.tolist()}")
            return {}

        # 4. Tạo Dictionary
        price_dict = {}
        for _, row in df.iterrows():
            try:
                sym = str(row[col_sym]).strip().upper()
                price = row[col_price]
                
                # Chuyển đổi sang float an toàn
                price = float(price)
                
                # Logic sửa lỗi đơn vị (Nếu giá < 500 đồng -> nhân 1000)
                # Ví dụ: HPG = 26.55 -> 26550
                if price < 500 and price > 0:
                    price = price * 1000
                    
                price_dict[sym] = price
            except Exception as ex:
                continue # Bỏ qua dòng lỗi
                
        print(f"✅ Đã khớp giá cho {len(price_dict)}/{len(clean_tickers)} mã.")
        return price_dict

    except Exception as e:
        print(f"❌ Lỗi Fatal Live Price: {e}")
        return {}