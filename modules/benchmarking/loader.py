# File: modules/benchmarking/loader.py
# Version: UPDATED (Support VPS Deduplication)

from processors.vck_patch import VCKPatch
from processors.engine import PortfolioEngine

def create_compass_engine(raw_events_vck, file_path_vck, raw_events_vps=None):
    """
    Factory tạo PortfolioEngine riêng biệt cho La Bàn.
    - VCK: Áp dụng Patch T+15.
    - VPS: Áp dụng bộ lọc trùng lặp (Dedup).
    """
    # 1. Khởi tạo Engine độc lập
    compass_engine = PortfolioEngine("COMPASS_ENGINE")
    
    # ==========================================================
    # 2. XỬ LÝ VCK (GIỮ NGUYÊN LOGIC CŨ)
    # ==========================================================
    if raw_events_vck:
        events_for_compass_vck = [e.copy() for e in raw_events_vck]
        if file_path_vck:
            patcher = VCKPatch()
            events_for_compass_vck = patcher.apply_patch(events_for_compass_vck, file_path_vck)
        
        for e in events_for_compass_vck:
            compass_engine.process_event(e)
            
    # ==========================================================
    # 3. XỬ LÝ VPS (THÊM LOGIC LỌC TRÙNG)
    # ==========================================================
    if raw_events_vps:
        print(f"   -> [Loader] Đang xử lý {len(raw_events_vps)} sự kiện VPS...")
        unique_vps_events = []
        seen_signatures = set()
        
        duplicate_count = 0
        
        for e in raw_events_vps:
            # Chỉ lọc trùng đối với lệnh MUA/BÁN (tránh nhân đôi tài sản)
            if e.get('type') in ['BUY', 'SELL', 'MUA', 'BAN']:
                # Tạo chữ ký duy nhất cho lệnh: Ngày_Mã_KL_Giá
                # Lưu ý: Ép kiểu để tránh lỗi so sánh float (100.0 vs 100)
                d = e.get('date')
                t = e.get('ticker')
                q = int(e.get('qty', 0))
                p = int(e.get('price', 0))
                
                signature = f"{d}_{t}_{q}_{p}_{e.get('type')}"
                
                if signature in seen_signatures:
                    duplicate_count += 1
                    continue # Bỏ qua lệnh trùng
                
                seen_signatures.add(signature)
            
            unique_vps_events.append(e)
            
        print(f"   -> [Loader] Đã lọc bỏ {duplicate_count} lệnh VPS trùng lặp.")
        
        # Nạp vào Engine
        for e in unique_vps_events:
            compass_engine.process_event(e)
    
    return compass_engine