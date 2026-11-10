# -*- coding: utf-8 -*-
"""测测专区引擎：八字 / 紫微斗数 / 每日运势（仅娱乐向）。"""
from .bazi import analyze as bazi_analyze
from .daily import daily_fortune
from .ziwei import analyze as ziwei_analyze

__all__ = ["bazi_analyze", "ziwei_analyze", "daily_fortune"]

# 本命信息可回填给运势个性化（如登录用户填过八字）
