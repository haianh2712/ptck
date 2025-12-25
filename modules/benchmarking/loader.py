# File: modules/benchmarking/loader.py
# Version: FIXED - SNAPSHOT COMPATIBLE (Gom sự kiện để chạy hàm run)

from processors.vck_patch import VCKPatch
from processors.engine import PortfolioEngine
import pandas as pd # Cần import pandas để sort nếu muốn chắc chắn

def create_compass_engine(raw_events_vck, file_path_vck, raw_events_vps=None):
    """
    Factory tạo PortfolioEngine riêng biệt cho La Bàn.
    - VCK: Áp dụng Patch T+15.
    - VPS: Áp dụng bộ lọc trùng lặp (Dedup).
    """
    # 1. Khởi tạo Engine độc lập
    compass_engine = PortfolioEngine("COMPASS_ENGINE")
    
    # [MỚI] Tạo danh sách chứa tất cả sự kiện để chạy 1 lần
    all_events = []
    
    # ==========================================================
    # 2. XỬ LÝ VCK
    # ==========================================================
    if raw_events_vck:
        events_for_compass_vck = [e.copy() for e in raw_events_vck]
        if file_path_vck:
            patcher = VCKPatch()
            events_for_compass_vck = patcher.apply_patch(events_for_compass_vck, file_path_vck)
        
        # [SỬA] Không chạy process_event ngay, mà gom vào list
        all_events.extend(events_for_compass_vck)
            
    # ==========================================================
    # 3. XỬ LÝ VPS (LỌC TRÙNG)
    # ==========================================================
    if raw_events_vps:
        print(f"   -> [Loader] Đang xử lý {len(raw_events_vps)} sự kiện VPS...")
        unique_vps_events = []
        seen_signatures = set()
        
        duplicate_count = 0
        
        for e in raw_events_vps:
            if e.get('type') in ['BUY', 'SELL', 'MUA', 'BAN']:
                d = e.get('date')
                t = e.get('ticker')
                q = int(e.get('qty', 0))
                p = int(e.get('price', 0))
                
                signature = f"{d}_{t}_{q}_{p}_{e.get('type')}"
                
                if signature in seen_signatures:
                    duplicate_count += 1
                    continue 
                
                seen_signatures.add(signature)
            
            unique_vps_events.append(e)
            
        print(f"   -> [Loader] Đã lọc bỏ {duplicate_count} lệnh VPS trùng lặp.")
        
        # [SỬA] Gom vào list chung
        all_events.extend(unique_vps_events)
    
    # ==========================================================
    # 4. CHẠY ENGINE (QUAN TRỌNG NHẤT)
    # ==========================================================
    if all_events:
        # Sắp xếp lại theo thời gian để đảm bảo logic dòng tiền chuẩn xác
        # (VCK và VPS có thể bị lộn xộn thời gian khi gộp)
        try:
            all_events.sort(key=lambda x: x.get('date', pd.Timestamp.min))
        except: pass
        
        # Gọi hàm run() để kích hoạt tính năng Snapshot Authority
        # Engine sẽ tự quét ngày chốt số dư từ VPS và áp dụng cho cả VCK nếu cần
        compass_engine.run(all_events)
    
    return compass_engine