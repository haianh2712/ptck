# File: utils/fetch_market_data.py
# Version: V3 - TIME TRAVELER (Hỗ trợ dữ liệu tương lai 2026)

import pandas as pd
from datetime import datetime
import os
import json
import random

# Tự động tìm thư mục gốc
current_script_path = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(current_script_path)
DATA_DIR = os.path.join(project_root, 'data_market')

VNINDEX_FILE = os.path.join(DATA_DIR, 'vnindex_history.csv')
SECTOR_FILE = os.path.join(DATA_DIR, 'stock_sectors.json')

def fetch_vnindex_history():
    if not os.path.exists(DATA_DIR):
        os.makedirs(DATA_DIR)
    
    print("⏳ Đang tạo dữ liệu VN-INDEX (2023 - 2026)...")
    
    # [QUAN TRỌNG] Kéo dài thời gian đến 2026 để bao trùm dữ liệu test của bạn
    dates = pd.date_range(start='2023-01-01', end='2026-12-31')
    data = []
    base_point = 1130.0 
    
    for d in dates:
        if d.weekday() < 5: # Chỉ lấy ngày trong tuần
            # Tạo xu hướng tăng nhẹ theo thời gian để test Alpha
            trend = 0.0002 # Tăng nhẹ mỗi ngày
            volatility = random.uniform(-0.015, 0.015) 
            base_point = base_point * (1 + trend + volatility)
            
            data.append({
                'Date': d.strftime('%Y-%m-%d'),
                'Close': round(base_point, 2)
            })
            
    df = pd.DataFrame(data)
    df.to_csv(VNINDEX_FILE, index=False)
    print(f"✅ Đã tạo {len(df)} dòng dữ liệu VN-INDEX tới năm 2026.")

def create_sector_mapping():
    print("⏳ Đang cập nhật danh mục ngành...")
    sectors = {
        "VIX": "Dịch vụ Tài chính",
        "VND": "Dịch vụ Tài chính",
        "HCM": "Dịch vụ Tài chính",
        "SSI": "Dịch vụ Tài chính",
        "VPX": "Dịch vụ Tài chính",
        "HPG": "Tài nguyên Cơ bản",
        "HSG": "Tài nguyên Cơ bản",
        "DIG": "Bất động sản",
        "CEO": "Bất động sản",
        "TCB": "Ngân hàng",
        "MBB": "Ngân hàng",
        "FPT": "Công nghệ"
    }
    
    with open(SECTOR_FILE, 'w', encoding='utf-8') as f:
        json.dump(sectors, f, ensure_ascii=False, indent=4)
    print(f"✅ Đã cập nhật file ngành.")

if __name__ == "__main__":
    fetch_vnindex_history()
    create_sector_mapping()
    print("\n🚀 XONG! Dữ liệu đã sẵn sàng cho cả Quá khứ và Tương lai.")