# -*- coding: utf-8 -*-
"""测测专区路由：每日运势 / 八字（含大运流年+日期交互）/ 紫微斗数。"""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from ..database import get_db
from ..deps import get_current_user
from ..fortune import bazi_analyze, daily_fortune, ziwei_analyze
from ..fortune.bazi import compute_dayun_for_date
from ..models import User

router = APIRouter(prefix="/api/fortune", tags=["fortune"])


@router.get("/daily")
def daily(day_master_gan: str = "", day_master_wuxing: str = "",
          shengxiao: str = "",
          db: Session = Depends(get_db),
          user: User = Depends(get_current_user)):
    """今日运势。提供日主信息时走五行生克算法，否则按生肖+日支规则。"""
    sx = (shengxiao or "").strip()
    valid_sx = ["鼠", "牛", "虎", "兔", "龙", "蛇", "马", "羊", "猴", "鸡", "狗", "猪"]
    if sx not in valid_sx:
        sx = ""
    dm_g = (day_master_gan or "").strip()
    dm_w = (day_master_wuxing or "").strip()
    if dm_g not in list("甲乙丙丁戊己庚辛壬癸"):
        dm_g = ""
    return daily_fortune(user_key=str(user.id), shengxiao=sx,
                         day_master_gan=dm_g, day_master_wuxing=dm_w)


class BirthIn(BaseModel):
    birth_date: str = Field(..., pattern=r"^\d{4}-\d{2}-\d{2}$", examples=["2000-01-01"])
    birth_hour: int | None = Field(None, ge=0, le=23, description="0-23，未知可不传")
    birth_minute: int = Field(0, ge=0, le=59)
    gender: str = "女"
    liunian_gong_zhi: str | None = Field(None, description="流年命宫地支（点击宫位触发流年盘重排）")
    liunian_year: int | None = Field(None, ge=1850, le=2100, description="流年年份，默认当前年")


@router.post("/bazi")
def bazi(data: BirthIn, user: User = Depends(get_current_user)):
    """八字排盘：四柱、五行、日主、大运流年流月流日（含交互分析）。"""
    try:
        result = bazi_analyze(data.birth_date, data.birth_hour,
                              data.birth_minute, data.gender)
        # 大运+流年+交互（默认当天）
        result["dayun"] = compute_dayun_for_date(
            data.birth_date, data.birth_hour, data.gender)
        return result
    except ValueError:
        raise HTTPException(400, "出生日期格式有误，应为 YYYY-MM-DD")


class DayunQueryIn(BaseModel):
    birth_date: str = Field(..., pattern=r"^\d{4}-\d{2}-\d{2}$")
    birth_hour: int | None = None
    gender: str = "女"
    query_date: str | None = Field(None, pattern=r"^\d{4}-\d{2}-\d{2}$",
                                  description="要查询的日期，缺省为今天")


@router.post("/dayun")
def dayun(data: DayunQueryIn, user: User = Depends(get_current_user)):
    """查询任意日期的大运流年流月流日 + 命局交互分析。"""
    try:
        return compute_dayun_for_date(data.birth_date, data.birth_hour,
                                      data.gender, data.query_date)
    except ValueError:
        raise HTTPException(400, "日期格式有误，应为 YYYY-MM-DD")


@router.post("/ziwei")
def ziwei(data: BirthIn, user: User = Depends(get_current_user)):
    """紫微斗数：命宫、五行局、十二宫、生年四化；传入宫位与年份时附流年盘。"""
    try:
        return ziwei_analyze(data.birth_date, data.birth_hour, data.gender,
                             liunian_gong_zhi=data.liunian_gong_zhi,
                             liunian_year=data.liunian_year)
    except ValueError:
        raise HTTPException(400, "出生日期格式有误，应为 YYYY-MM-DD")
