# File: processors/ipo_merger.py
# Module: Hợp nhất lệnh Đặt cọc IPO và Lệnh Mua chính thức

def merge_ipo_events(events):
    """
    Input: Danh sách sự kiện thô từ Adapter.
    Output: Danh sách sự kiện đã được xử lý (Gộp tiền cọc vào giá vốn).
    """
    # Sắp xếp theo ngày để đảm bảo Cọc xuất hiện trước Mua
    sorted_events = sorted(events, key=lambda x: (x['date'], x.get('prio', 50)))
    
    cleaned_events = []
    
    # Bộ nhớ tạm để lưu tiền cọc: { 'MÃ_CK': Số_Tiền_Cọc }
    pending_deposits = {}
    
    for ev in sorted_events:
        etype = ev.get('type', '')
        ticker = ev.get('ticker', '')
        val = ev.get('value', 0) 

        # TRƯỜNG HỢP 1: LỆNH ĐẶT CỌC (IPO_DEPOSIT)
        if etype == 'IPO_DEPOSIT' and ticker:
            # 1. Lưu tiền cọc vào bộ nhớ
            if ticker not in pending_deposits:
                pending_deposits[ticker] = 0.0
            pending_deposits[ticker] += val
            
            # 2. Biến sự kiện này thành sự kiện trừ tiền thuần túy (PHI_THUE)
            # Để Engine vẫn trừ tiền mặt, nhưng KHÔNG tạo ra kho cổ phiếu rác
            ev['type'] = 'PHI_THUE' 
            ev['desc'] = f"Đặt cọc IPO mã {ticker}"
            cleaned_events.append(ev)
            
        # TRƯỜNG HỢP 2: LỆNH MUA CHÍNH THỨC (CỦA MÃ ĐANG CÓ CỌC)
        elif etype in ['MUA', 'BUY'] and ticker in pending_deposits:
            deposit_amount = pending_deposits[ticker]
            
            # 1. Cộng tiền cọc vào giá trị mua (Value)
            # Lúc này: Value (Giá vốn tổng) = Tiền nộp nốt (val) + Tiền cọc (deposit)
            ev['value'] += deposit_amount
            
            # 2. Xóa tiền cọc khỏi bộ nhớ (đã dùng xong)
            del pending_deposits[ticker]
            
            # 3. Tạo sự kiện hoàn tiền ảo để cân bằng dòng tiền cho Engine
            # (Vì tiền mặt đã bị trừ 1 lần ở bước Cọc, giờ lệnh Mua lại trừ Full -> Phải bù lại 1 lần)
            refund_event = {
                'date': ev['date'],
                'type': 'BAN_TIEN_VE', # Dùng loại này để cộng tiền vào Cash
                'value': deposit_amount,
                'ticker': ticker,
                'desc': 'System: Merge IPO Deposit (Bù trừ dòng tiền)'
            }
            cleaned_events.append(refund_event)
            cleaned_events.append(ev)

        # TRƯỜNG HỢP 3: CÁC SỰ KIỆN KHÁC
        else:
            cleaned_events.append(ev)
            
    return cleaned_events