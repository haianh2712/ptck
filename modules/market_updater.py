# File: modules/market_updater.py
# Purpose: Tự động cập nhật VN-Index từ nguồn VNDirect (Lightweight)

import requests
import pandas as pd
import os
import time
from datetime import datetime

def check_and_update_market_data():
    """
    Hàm kiểm tra và cập nhật dữ liệu thị trường.
    - Nguồn: VNDirect API.
    - Lịch sử: Từ 2023 đến nay.
    """
    data_dir = 'data_market'
    file_path = os.path.join(data_dir, 'vnindex_history.csv')
    
    print("🔄 [UPDATER] Đang kiểm tra dữ liệu thị trường (Nguồn: VNDirect)...")
    
    # 1. Tạo thư mục nếu chưa có
    if not os.path.exists(data_dir):
        os.makedirs(data_dir)

    # 2. Kiểm tra trạng thái file
    should_update = False
    
    if not os.path.exists(file_path):
        should_update = True
        print("   -> 📁 Chưa có file dữ liệu. Sẽ tải mới.")
    else:
        # Lấy thời gian sửa đổi file
        mod_time = os.path.getmtime(file_path)
        file_date = datetime.fromtimestamp(mod_time).date()
        today = datetime.now().date()
        
        # Nếu file cũ (ngày sửa < hôm nay) -> Cập nhật
        if file_date < today:
            should_update = True
            print(f"   -> ⏰ Dữ liệu cũ ({file_date}). Đang cập nhật cho ngày {today}...")
        else:
            # [QUAN TRỌNG] In ra dòng này để bạn biết hệ thống ĐÃ CHẠY và ĐÃ ỔN
            print("   -> ✅ Dữ liệu VN-Index đã mới nhất. Bỏ qua cập nhật.")

    # 3. Thực hiện cập nhật nếu cần
    if should_update:
        try:
            # Cấu hình thời gian: Từ 01/01/2023 đến hiện tại
            start_date_str = "2023-01-01"
            start_ts = int(datetime.strptime(start_date_str, "%Y-%m-%d").timestamp())
            end_ts = int(time.time())
            
            # API VNDirect
            url = f"https://dchart-api.vndirect.com.vn/dchart/history?resolution=D&symbol=VNINDEX&from={start_ts}&to={end_ts}"
            headers = {'User-Agent': 'Mozilla/5.0'}
            
            # Gọi API
            print(f"   -> ⏳ Đang tải dữ liệu từ {start_date_str}...")
            response = requests.get(url, headers=headers, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                if 't' in data and 'c' in data:
                    # Tạo DataFrame
                    df = pd.DataFrame({
                        'timestamp': data['t'], 
                        'Close': data['c']
                    })
                    
                    # Chuyển đổi timestamp sang ngày tháng
                    df['Date'] = pd.to_datetime(df['timestamp'], unit='s').dt.strftime('%Y-%m-%d')
                    
                    # Sắp xếp và lưu file (Chỉ lấy Date và Close)
                    df_final = df[['Date', 'Close']].sort_values('Date')
                    df_final.to_csv(file_path, index=False)
                    
                    print(f"   -> ✅ Cập nhật thành công! (Đã lưu {len(df_final)} phiên giao dịch).")
                else:
                    print("   -> ❌ Lỗi: API trả về dữ liệu trống.")
            else:
                print(f"   -> ❌ Lỗi kết nối API: Status Code {response.status_code}")
                
        except Exception as e:
            print(f"   -> ⚠️ Lỗi ngoại lệ khi cập nhật: {e}")
            print("      (Hệ thống sẽ sử dụng dữ liệu cũ nếu có)")