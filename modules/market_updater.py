# File: modules/market_updater.py
# Purpose: Module tự động kiểm tra và cập nhật dữ liệu VN-Index

import requests
import pandas as pd
import os
import time
from datetime import datetime

def check_and_update_market_data():
    """
    Hàm này sẽ kiểm tra file dữ liệu.
    - Nếu file chưa có -> Tải mới.
    - Nếu file cũ (không phải dữ liệu hôm nay) -> Tải mới.
    - Nếu file đã mới -> Bỏ qua (để App chạy nhanh).
    """
    file_path = os.path.join('data_market', 'vnindex_history.csv')
    
    # 1. Kiểm tra xem có cần cập nhật không
    should_update = False
    
    if not os.path.exists(file_path):
        should_update = True
        print("Creating market data file...")
    else:
        # Lấy thời gian sửa đổi cuối cùng của file
        mod_time = os.path.getmtime(file_path)
        file_date = datetime.fromtimestamp(mod_time).date()
        today = datetime.now().date()
        
        # Nếu file không phải của ngày hôm nay -> Cập nhật
        if file_date < today:
            should_update = True
            print(f"Data is old ({file_date}). Updating to {today}...")
    
    # 2. Thực hiện cập nhật nếu cần
    if should_update:
        try:
            # Logic gọi API VNDirect (Code chuẩn bạn đã test)
            start_ts = int(datetime.strptime("2023-01-01", "%Y-%m-%d").timestamp())
            end_ts = int(time.time())
            url = f"https://dchart-api.vndirect.com.vn/dchart/history?resolution=D&symbol=VNINDEX&from={start_ts}&to={end_ts}"
            
            headers = {'User-Agent': 'Mozilla/5.0'}
            response = requests.get(url, headers=headers, timeout=5)
            
            if response.status_code == 200:
                data = response.json()
                if 't' in data and 'c' in data:
                    df = pd.DataFrame({'timestamp': data['t'], 'Close': data['c']})
                    df['Date'] = pd.to_datetime(df['timestamp'], unit='s').dt.strftime('%Y-%m-%d')
                    df_final = df[['Date', 'Close']].sort_values('Date')
                    
                    if not os.path.exists('data_market'): os.makedirs('data_market')
                    df_final.to_csv(file_path, index=False)
                    print("✅ Market Data Updated Successfully!")
        except Exception as e:
            print(f"⚠️ Auto-update failed: {e}. Using old data.")