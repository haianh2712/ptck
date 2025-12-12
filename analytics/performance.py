# File: analytics/performance.py
import pandas as pd
import numpy as np

def calculate_kpi(closed_cycles_list):
    """
    Tính toán các chỉ số KPI chuyên sâu từ danh sách các lệnh đã tất toán (Closed Cycles).
    Input: List of dicts (output từ Engine)
    """
    if not closed_cycles_list:
        return None

    # Chuyển sang DataFrame để dễ tính toán
    df = pd.DataFrame(closed_cycles_list)
    
    # 1. LỌC NHIỄU: Loại bỏ các mã WFT hoặc mã rác nếu còn sót
    if 'Mã CK' in df.columns:
        df = df[~df['Mã CK'].str.endswith('_WFT', na=False)]
        
    if df.empty: return None

    # 2. PHÂN LOẠI THẮNG / THUA
    # Lãi/Lỗ > 0 là Thắng, <= 0 là Thua (Hòa coi như thua để khắt khe)
    wins = df[df['Lãi/Lỗ'] > 0]
    losses = df[df['Lãi/Lỗ'] <= 0]

    # 3. TÍNH TOÁN CÁC CHỈ SỐ CỐT LÕI
    total_trades = len(df)
    num_wins = len(wins)
    num_losses = len(losses)
    
    # A. Tỷ lệ thắng (Win Rate)
    win_rate = (num_wins / total_trades * 100) if total_trades > 0 else 0
    
    # B. Profit Factor (Tổng Lãi / Tổng Lỗ Tuyệt Đối)
    gross_profit = wins['Lãi/Lỗ'].sum()
    gross_loss = abs(losses['Lãi/Lỗ'].sum())
    profit_factor = (gross_profit / gross_loss) if gross_loss > 0 else float('inf') 
    
    # C. Trung bình Lãi vs Lỗ (Avg Win / Avg Loss)
    avg_win = wins['Lãi/Lỗ'].mean() if num_wins > 0 else 0
    avg_loss = losses['Lãi/Lỗ'].mean() if num_losses > 0 else 0
    payoff_ratio = (avg_win / abs(avg_loss)) if avg_loss != 0 else 0
    
    # D. Thời gian nắm giữ (Holding Time)
    avg_hold_win = wins['Tuổi Vòng Đời'].mean() if num_wins > 0 else 0
    avg_hold_loss = losses['Tuổi Vòng Đời'].mean() if num_losses > 0 else 0

    return {
        'total_trades': total_trades,
        'win_rate': round(win_rate, 2),
        'profit_factor': round(profit_factor, 2),
        'avg_win': round(avg_win, 0),
        'avg_loss': round(avg_loss, 0),
        'payoff_ratio': round(payoff_ratio, 2),
        'avg_hold_win': round(avg_hold_win, 1),
        'avg_hold_loss': round(avg_hold_loss, 1),
        'net_pnl': gross_profit - gross_loss,
        'largest_win': wins['Lãi/Lỗ'].max() if num_wins > 0 else 0,
        'largest_loss': losses['Lãi/Lỗ'].min() if num_losses > 0 else 0
    }