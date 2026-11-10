# -*- coding: utf-8 -*-
"""积分充值：套餐管理 + 订单创建 + 支付确认（微信/支付宝）。

Demo 模式（默认）：POST /confirm 直接标记支付成功并到账，无需真实网关。
生产模式：设置 PAYMENT_DEMO=false 后需对接微信/支付宝真实 API（见文档注释）。

微信支付接入要点（生产）：
  1. 注册微信商户号 → 获取 mch_id + API 密钥
  2. 调用「统一下单」API 获取 prepay_id
  3. 生成带签名的支付二维码返回给前端
  4. 设置支付回调 URL 接收异步通知
  5. 验签通过后更新订单状态并到账积分

支付宝接入要点（生产）：
  1. 注册支付宝开放平台 → 获取 app_id + 商户私钥
  2. 调用「预创建交易」API 获取二维码链接
  3. 设置异步通知 URL
  4. 验签通过后更新订单状态并到账积分
"""
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from ..database import get_db
from ..deps import get_current_user
from ..models import PaymentOrder, User
from .points import add_points, DAILY_CLAIM

router = APIRouter(prefix="/api/payments", tags=["payments"])

# ============================================================
# 充值套餐
# ============================================================
PLANS = [
    {"id": "p100",   "amount_yuan": 1,  "amount_cents": 100,
     "points": 100,   "bonus": 0,   "label": "体验装"},
    {"id": "p500",   "amount_yuan": 5,  "amount_cents": 500,
     "points": 550,   "bonus": 10,  "label": "常用装"},
    {"id": "p1000",  "amount_yuan": 10, "amount_cents": 1000,
     "points": 1200,  "bonus": 20,  "label": "超值装"},
    {"id": "p5000",  "amount_yuan": 50, "amount_cents": 5000,
     "points": 6500,  "bonus": 30,  "label": "尊享装"},
]


@router.get("/plans")
def get_plans(user: User = Depends(get_current_user)):
    """可用的充值套餐列表。"""
    return {"plans": PLANS, "demo_mode": True,
            "note": "当前为演示模式，点击「模拟支付」即可到账（无需真实付款）"}


# ============================================================
# 订单管理
# ============================================================
class CreateOrderIn(BaseModel):
    plan_id: str = Field(..., description="套餐 ID")
    method: str = Field("wechat", description="wechat / alipay")


@router.post("/create")
def create_order(data: CreateOrderIn, db: Session = Depends(get_db),
                 user: User = Depends(get_current_user)):
    """创建充值订单。返回订单号 + 支付方式。"""
    plan = next((p for p in PLANS if p["id"] == data.plan_id), None)
    if not plan:
        raise HTTPException(400, "套餐不存在")
    if data.method not in ("wechat", "alipay"):
        raise HTTPException(400, "支付方式仅支持 wechat / alipay")

    order = PaymentOrder(
        user_id=user.id,
        amount_cents=plan["amount_cents"],
        points=plan["points"],
        method=data.method,
        plan_id=plan["id"],
        status="pending",
    )
    db.add(order)
    db.commit()
    db.refresh(order)

    # 生成支付链接（Demo 模式下是模拟链接）
    pay_url = f"/payments/confirm/{order.id}"
    qr_text = f"healing://pay?order={order.id}&amount={plan['amount_cents'] / 100}"

    return {
        "order_id": order.id,
        "plan": plan,
        "method": data.method,
        "amount_yuan": plan["amount_cents"] / 100,
        "points": plan["points"],
        "status": "pending",
        "pay_url": pay_url,
        "qr_text": qr_text,
        "demo_mode": True,
    }


class ConfirmIn(BaseModel):
    trade_no: str = ""


@router.post("/{order_id}/confirm")
def confirm_payment(order_id: int, data: ConfirmIn | None = None,
                    db: Session = Depends(get_db),
                    user: User = Depends(get_current_user)):
    """确认支付（Demo 模式直接到账；生产模式需先回调验签再调用此接口）。

    幂等设计：重复确认同一订单不会重复到账。body 可省略。
    """
    order = (db.query(PaymentOrder)
             .filter(PaymentOrder.id == order_id,
                     PaymentOrder.user_id == user.id)
             .first())
    if not order:
        raise HTTPException(404, "订单不存在")
    if order.status == "paid":
        # 幂等：已支付的订单直接返回成功
        return {"ok": True, "status": "paid", "points": order.points,
                "balance": user.points, "message": "订单已支付（幂等）"}

    if order.status == "cancelled":
        raise HTTPException(400, "订单已取消")

    # 生产模式：此处应验签 + 金额校验后再执行
    # Demo 模式：直接标记支付成功
    order.status = "paid"
    order.trade_no = (data.trade_no if data and data.trade_no else
                      f"demo_{order.id}_{int(datetime.now(timezone.utc).timestamp())}")
    order.paid_at = datetime.now(timezone.utc)

    # 到账积分
    balance = add_points(db, user, order.points, "recharge",
                         note=f"充值 ¥{order.amount_cents / 100:.2f}")

    return {
        "ok": True,
        "status": "paid",
        "order_id": order.id,
        "points": order.points,
        "balance": balance,
        "message": f"支付成功！{order.points} 积分已到账",
    }


@router.post("/{order_id}/cancel")
def cancel_order(order_id: int, db: Session = Depends(get_db),
                 user: User = Depends(get_current_user)):
    """取消未支付的订单。"""
    order = (db.query(PaymentOrder)
             .filter(PaymentOrder.id == order_id,
                     PaymentOrder.user_id == user.id)
             .first())
    if not order:
        raise HTTPException(404, "订单不存在")
    if order.status != "pending":
        raise HTTPException(400, f"订单状态为 {order.status}，无法取消")
    order.status = "cancelled"
    db.commit()
    return {"ok": True, "status": "cancelled"}


@router.get("/orders")
def my_orders(db: Session = Depends(get_db),
              user: User = Depends(get_current_user)):
    """我的充值订单列表。"""
    orders = (db.query(PaymentOrder)
              .filter(PaymentOrder.user_id == user.id)
              .order_by(PaymentOrder.created_at.desc())
              .limit(20).all())
    return {
        "orders": [
            {
                "id": o.id,
                "amount_yuan": o.amount_cents / 100,
                "points": o.points,
                "method": o.method,
                "method_label": "微信支付" if o.method == "wechat" else "支付宝",
                "status": o.status,
                "trade_no": o.trade_no,
                "created_at": o.created_at.isoformat() if o.created_at else None,
                "paid_at": o.paid_at.isoformat() if o.paid_at else None,
            }
            for o in orders
        ],
    }
