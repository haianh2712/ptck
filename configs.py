# File: configs.py
import streamlit as st

# ==============================================================================
# 1. TỪ ĐIỂN Ý NGHĨA BIỂU ĐỒ (PSYCHOLOGY INSIGHTS)
# Chứa các phân tích chuyên sâu, cảnh báo tâm lý cho từng loại biểu đồ.
# ==============================================================================

CHART_INSIGHTS = {
    # --- NHÓM TÂM LÝ (PSYCHOLOGY) ---
    "chart_1_timeline": {
        "title": "Biểu đồ: Nhịp Tim Giao Dịch (Trading Heartbeat)",
        "meaning": """
        **🔍 GÓC NHÌN CHUYÊN GIA:**
        - Biểu đồ này là **"Điện tâm đồ"** cảm xúc của bạn.
        - **Mật độ dày đặc:** Cảnh báo bạn đang bị cuốn vào vòng xoáy **Giao dịch quá mức (Over-trading)**. Khi thị trường rung lắc, bạn có xu hướng mua/bán hoảng loạn thay vì tuân thủ kế hoạch.
        - **Kích thước điểm:** Các chấm to xuất hiện ở vùng giá cao thường là dấu hiệu của sự hưng phấn (FOMO) sai lầm.
        """,
        "warning": "⚠️ Cảnh báo: Nếu thấy các lệnh Mua/Bán xuất hiện dồn dập trong < 3 ngày, hãy dừng lại và tắt App ngay."
    },

    "chart_2_matrix": {
        "title": "Biểu đồ: Ma Trận Kỷ Luật (History Matrix)",
        "meaning": """
        **🔍 GÓC NHÌN CHUYÊN GIA:**
        - Đây là tấm gương soi chiếu **Kỷ luật Cắt lỗ & Gồng lãi**.
        - **Góc Tử Thần (Dưới-Phải):** Các chấm đỏ nằm xa trục tung -> Bạn đang mắc lỗi "Gồng lỗ" (Loss Aversion). Bạn giữ mã lỗ quá lâu với hy vọng nó hồi phục.
        - **Góc Lãng Phí (Trên-Trái):** Các chấm xanh nằm sát trục tung -> Bạn đang "Chốt non", không để lãi chạy (Let profits run).
        """,
        "warning": "🎯 Mục tiêu tối thượng: Xóa sạch các chấm đỏ nằm bên phải (Lỗ sâu + Giữ lâu)."
    },

    "chart_3_radar": {
        "title": "Biểu đồ: Ra-đa Rủi Ro (Portfolio Risk Radar)",
        "meaning": """
        **🔍 GÓC NHÌN CHUYÊN GIA:**
        - Quét toàn bộ danh mục hiện tại để tìm **"Chi phí cơ hội"**.
        - Trục ngang là **Thời gian kẹp hàng** (tính từ lô mua đầu tiên). Trục dọc là **Mức độ sát thương**.
        - Những mã nằm trong vùng đỏ (Góc dưới bên phải) được gọi là **"Vốn Chết"**. Chúng không chỉ làm giảm NAV mà còn bào mòn tâm lý của bạn mỗi ngày.
        """,
        "warning": "🚨 BÁO ĐỘNG ĐỎ: Bất kỳ mã nào lỗ > 7% và đã giữ > 60 ngày cần được xử lý (Cắt bỏ) ngay lập tức!"
    },

    "chart_4_efficiency": {
        "title": "Biểu đồ: Hiệu Quả vs Cường Độ (ROI vs Effort)",
        "meaning": """
        **🔍 GÓC NHÌN CHUYÊN GIA:**
        - Trả lời câu hỏi: **"Bạn đang đầu tư hay đang cúng phí cho sàn?"**
        - **Cột xám cao (Trade nhiều) + Đường xanh đi xuống:** Bạn đang làm việc vất vả nhưng không hiệu quả (Busy Fool).
        - **Cột xám thấp + Đường xanh đi lên:** Đây là trạng thái của một **Sniper** (Xạ thủ) - Bắn ít, trúng nhiều, tâm lý nhàn hạ.
        """,
        "warning": "⚠️ Nếu đường Lãi Tích Lũy đi ngang hoặc cắm đầu trong khi Số Lệnh tăng cao -> Nghỉ giao dịch 1 tuần để Reset."
    },

    "chart_5_streak": {
        "title": "Biểu đồ: Phong Độ & Chất Lượng Lệnh (Streak & ROI)",
        "meaning": """
        **🔍 GÓC NHÌN CHUYÊN GIA:**
        - Kiểm tra **Tính ổn định** và **Chất lượng** (ROI) của từng cú click chuột.
        - **Chuỗi Đỏ liên tiếp:** Dấu hiệu của sự "Cay cú" (Tilt). Thường sau 3 lệnh thua liên tiếp, IQ tài chính của bạn sẽ giảm 30%.
        - **ROI thấp:** Nếu bạn thấy nhiều cột xanh nhưng rất thấp, nghĩa là bạn đang bỏ vốn lớn để nhặt tiền lẻ (Rủi ro cao, lợi nhuận thấp).
        """,
        "warning": "🛑 Quy tắc vàng: Sau chuỗi 3 lệnh thua liên tiếp, bắt buộc ngừng giao dịch trong 48 giờ."
    },

    # --- NHÓM RỦI RO (RISK MANAGEMENT) - MỚI CẬP NHẬT ---
    "risk_heatmap": {
        "title": "Biểu đồ: Bản Đồ Nhiệt (Trading Heatmap)",
        "meaning": """
        **🔍 GÓC NHÌN CHUYÊN GIA:**
        - **Tính nhất quán (Consistency):** Trader chuyên nghiệp không cần thắng lớn, họ cần thắng đều. Một bảng màu xanh nhạt phủ kín tốt hơn là vài ô xanh đậm xen kẽ nhiều ô đỏ lòm.
        - **Ngày thảm họa:** Chú ý các ô đỏ đậm. Đó thường là ngày bạn phá vỡ kỷ luật (Revenge Trading). Hãy nhớ lại xem ngày đó chuyện gì đã xảy ra?
        """,
        "warning": "🛡️ Chiến lược: Cố gắng giữ cho bản đồ không xuất hiện các 'Hố Đen' (Mức lỗ > 2% NAV/ngày)."
    },

    "risk_drawdown": {
        "title": "Biểu đồ: Sụt Giảm Tài Sản (Drawdown)",
        "meaning": """
        **🔍 GÓC NHÌN CHUYÊN GIA:**
        - Đây là thước đo **"Khả năng sống sót"**.
        - **Toán học tàn nhẫn:** Nếu bạn để tài khoản sụt giảm 50% (Drawdown), bạn cần lãi 100% chỉ để về bờ.
        - **Vùng đau đớn:** Khi đường biểu đồ đi xuống càng sâu, tâm lý muốn "gỡ nhanh" càng lớn -> Dẫn đến cháy tài khoản.
        """,
        "warning": "☠️ QUY TẮC SỐNG CÒN: Đừng bao giờ để Drawdown vượt quá 15%. Nếu chạm mức này, hãy cắt toàn bộ danh mục và nghỉ ngơi."
    }
}

# ==============================================================================
# 2. ĐỊNH NGHĨA KPI (KPI TOOLTIPS)
# ==============================================================================
KPI_TOOLTIPS = {
    "DEPOSIT": "💰 Tổng Tiền Đã Nạp:\nLà tổng số tiền mặt thực tế bạn đã nạp vào tài khoản trừ đi số tiền đã rút ra.\nĐây là dòng vốn thực nạp (Net Deposit).",
    
    "CASH": "💵 Tiền Mặt Khả Dụng:\nSố dư tiền mặt hiện tại có trong tài khoản (Sức mua).\nChưa bao gồm tiền bán chờ về.",
    
    "ADJ_COST": "🛡️ Vốn Hợp Lý (Kho):\nTổng vốn gốc thực tế (sau khi trừ cổ tức tiền mặt) của các mã ĐANG nắm giữ.\nĐây là số tiền rủi ro thực sự bạn đang để trong thị trường.",
    
    "MKT_VAL": "📦 Giá Trị Thị Trường (Live):\nTổng giá trị hiện tại của cổ phiếu trong kho.\nDelta hiển thị bên dưới là Chênh lệch giữa (Giá trị TT - Vốn Hợp Lý).",
    
    "NAV": "💎 Tài Sản Ròng (NAV):\nTổng tài sản = Tiền Mặt + Giá Trị Cổ Phiếu (Live).\nCon số quyết định bạn đang giàu lên hay nghèo đi.",
    
    "REALIZED": "💰 Lãi Đã Chốt:\nTổng lợi nhuận đã hiện thực hóa vào túi (Gồm: Lãi bán chốt lời + Cổ tức tiền mặt).",
    
    "PROFIT": "🚀 Tổng Lợi Nhuận (All-in):\nTổng lãi/lỗ tính gộp tất cả: (1) Lãi đã chốt + (2) Cổ tức + (3) Lãi tạm tính đang có.\nCon số cuối cùng đánh giá hiệu quả đầu tư."
}

# ==============================================================================
# 3. ĐỊNH NGHĨA CỘT (COLUMN CONFIG)
# ==============================================================================
def get_column_config():
    """Trả về cấu hình cột chuẩn cho toàn bộ ứng dụng."""
    return {
        # --- CỘT ĐỊNH DANH ---
        "Mã CK": st.column_config.TextColumn("Mã CK", width="small", help="Mã chứng khoán niêm yết."),
        "Xu Hướng": st.column_config.TextColumn("Xu Hướng", width="small", help="Trạng thái giá hiện tại so với giá vốn."),
        "Trạng Thái": st.column_config.TextColumn("Trạng Thái", width="small"),

        # --- CỘT VỐN & GIÁ ---
        "Vốn Gốc (Mua)": st.column_config.NumberColumn("Vốn Gốc", help="Tổng tiền gốc ban đầu bỏ ra để mua số lượng đang giữ."),
        "Vốn Hợp Lý (Sau Cổ Tức)": st.column_config.NumberColumn("Vốn Hợp Lý", help="Vốn gốc đã trừ đi phần cổ tức tiền mặt nhận được. Dùng để tính giá hòa vốn thực tế."),
        "Giá Vốn": st.column_config.NumberColumn("Giá Vốn", help="Giá vốn bình quân."),
        "Giá Vốn Gốc": st.column_config.NumberColumn("Giá Khớp Lệnh", help="Giá mua bình quân ban đầu (Chưa trừ cổ tức)."),
        "Giá Vốn ĐC": st.column_config.NumberColumn("Giá Vốn ĐC", help="Giá vốn điều chỉnh (Giá hòa vốn sau khi nhận cổ tức)."),
        
        # --- CỘT THỊ TRƯỜNG (LIVE) ---
        "Giá TT": st.column_config.NumberColumn("Giá TT", help="Giá thị trường hiện tại (Cập nhật Real-time từ Yahoo)."),
        "Giá Trị TT": st.column_config.NumberColumn("Giá Trị TT", help="Thành tiền theo giá thị trường: SL Tồn * Giá TT."),
        "Giá Trị TT (Live)": st.column_config.NumberColumn("Giá Trị TT (Live)", help="Tổng giá trị thị trường của mã này (Gồm tất cả các lô đang giữ)."),
        "Lãi/Lỗ Tạm Tính": st.column_config.NumberColumn("Lãi/Lỗ Tạm", help="Lợi nhuận/Rủi ro chưa chốt (Unrealized PnL): Giá Trị TT - Vốn Hợp Lý."),
        "Chênh Lệch (Live)": st.column_config.NumberColumn("Chênh Lệch (Live)", help="Lãi/Lỗ tạm tính trên tổng vị thế. Dương là đang Lãi thực tế."),
        
        # --- CỘT HIỆU SUẤT ---
        "Tổng Lãi Thực": st.column_config.NumberColumn("Tổng Lãi Thực", help="Lợi nhuận đã chốt + Cổ tức tiền mặt."),
        "Lãi/Lỗ Giao Dịch": st.column_config.NumberColumn("Lãi/Lỗ GD", help="Chênh lệch giá Mua/Bán của các lệnh đã đóng (Trading PnL)."),
        "Cổ Tức Đã Nhận": st.column_config.NumberColumn("Cổ Tức", help="Tổng tiền mặt nhận được từ cổ tức."),
        "% Hiệu Suất (Trade)": st.column_config.NumberColumn("% Hiệu Suất", format="%.2f %%", help="Tỷ suất lợi nhuận trên vốn bán ra."),
        "% Lãi/Lỗ": st.column_config.NumberColumn("% Lãi/Lỗ", format="%.2f %%", help="Tỷ suất lợi nhuận tạm tính theo giá thị trường."),
        "% ROI Cycle": st.column_config.NumberColumn("% ROI Cycle", format="%.2f %%", help="Tỷ suất sinh lời toàn bộ chu kỳ (Lãi chốt + Cổ tức / Vốn bỏ ra)."),
        
        # --- CỘT THỜI GIAN & KHỐI LƯỢNG ---
        "SL Đang Giữ": st.column_config.NumberColumn("SL Đang Giữ", format="%d", help="Số lượng cổ phiếu hiện có trong kho."),
        "SL": st.column_config.NumberColumn("SL", format="%d"),
        "SL Tồn": st.column_config.NumberColumn("SL Tồn", format="%d"),
        "Ngày Giữ TB (Đã Bán)": st.column_config.NumberColumn("Ngày Giữ (Bán)", format="%.1f ngày", help="Thời gian nắm giữ trung bình của các lệnh đã bán."),
        "Tuổi Kho TB": st.column_config.NumberColumn("Tuổi Kho", format="%.1f ngày", help="Thời gian nắm giữ trung bình của cổ phiếu trong kho."),
        "Tuổi Vòng Đời": st.column_config.NumberColumn("Vòng Đời", format="%d ngày", help="Số ngày từ khi mở vị thế đến khi đóng hết."),
        "Ngày": st.column_config.DateColumn("Ngày", format="DD/MM/YYYY"),
        
        # --- CỘT KHÁC ---
        "Vốn Kẹp": st.column_config.NumberColumn("Vốn Kẹp", help="Giá trị vốn đang bị giữ trong các mã lỗ hoặc giữ quá lâu."),
        "Tổng Vốn Mua": st.column_config.NumberColumn("Tổng Vốn Mua", help="Tổng quy mô vốn giải ngân cho một chu kỳ."),
        "Tổng Vốn Đã Rót": st.column_config.NumberColumn("Tổng Vốn Đã Rót", help="Doanh số mua tích lũy."),
        "🔄 Doanh Số Mua": st.column_config.NumberColumn("Doanh Số Mua", help="Tổng tiền đã chi ra để mua mã này (Vòng quay vốn)."),
    }