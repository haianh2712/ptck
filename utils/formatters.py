# File: utils/formatters.py
import pandas as pd

def fmt_vnd(x):
    """Định dạng tiền tệ: 1.000.000"""
    if pd.isna(x): return "0"
    return "{:,.0f}".format(x).replace(",", ".")

def fmt_num(x):
    """Định dạng số lượng: 1.000"""
    if pd.isna(x): return "0"
    return "{:,.0f}".format(x).replace(",", ".")

def fmt_float(x):
    """Định dạng số thập phân: 1,5"""
    if pd.isna(x): return "0"
    return "{:,.2f}".format(x).replace(".", ",")

def fmt_pct(x):
    """Định dạng phần trăm: 10,50%"""
    if pd.isna(x): return "0%"
    return "{:,.2f}%".format(x).replace(".", ",")