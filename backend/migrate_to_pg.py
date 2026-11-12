# -*- coding: utf-8 -*-
"""SQLite → PostgreSQL 一次性数据迁移（在容器内运行）。

用法：
    docker compose run --rm app python migrate_to_pg.py            # 非空表跳过（幂等）
    docker compose run --rm app python migrate_to_pg.py --force    # 清空目标表后重导
    docker compose run --rm app python migrate_to_pg.py --sqlite /app/backend/data/healing.db

行为：
1. 用应用的 DATABASE_URL（PostgreSQL）执行 create_all 建表；
2. 按外键依赖序（父→子）逐表搬运数据：
   - SQLite 的 0/1 布尔列转为真 bool（PG BOOLEAN 不接受整数）；
   - 显式保留源主键，迁移后对 PG 的 SERIAL 序列 setval 对齐，后续自增不冲突；
3. 无 --force 时目标已非空的表自动跳过，可安全重跑；
4. 时间列原样搬运（旧库为 UTC 字面量，列已改为 timestamptz）。
"""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

# 依赖序（父表在前）
TABLES = [
    "users",
    "chat_sessions",
    "messages",
    "emotion_records",
    "emotion_calibrations",
    "forum_posts",
    "forum_likes",
    "forum_comments",
    "points_ledger",
    "user_wiki_entries",
    "payment_orders",
    "knowledge_articles",
    "llm_models",
    "llm_usage_logs",
    "agent_trace_logs",
]

# SQLite 用 0/1 存布尔；PG BOOLEAN 列必须转 Python bool
BOOL_COLUMNS = {
    "users": {"is_active"},
    "user_wiki_entries": {"pinned"},
    "llm_models": {"enabled", "is_default"},
    "llm_usage_logs": {"success"},
}


def main() -> int:
    parser = argparse.ArgumentParser(description="SQLite → PostgreSQL 数据迁移")
    parser.add_argument("--sqlite", default=str(Path(__file__).parent / "data" / "healing.db"),
                        help="源 SQLite 文件路径")
    parser.add_argument("--force", action="store_true",
                        help="清空目标表后重新导入（TRUNCATE CASCADE）")
    args = parser.parse_args()

    from sqlalchemy import create_engine, inspect, text

    from app.database import DATABASE_URL, IS_POSTGRES, engine as pg_engine, init_db

    if not IS_POSTGRES:
        print("!! 当前 DATABASE_URL 未配置 PostgreSQL（可能仍是 SQLite 模式），中止。")
        print(f"   DATABASE_URL = {DATABASE_URL!r}")
        return 2
    src_path = Path(args.sqlite)
    if not src_path.exists():
        print(f"!! 源 SQLite 不存在：{src_path}")
        return 2

    print(f"目标：{DATABASE_URL.split('@')[-1]}")
    print(f"源  ：{src_path}")
    sqlite = create_engine(f"sqlite:///{src_path}")
    src = inspect(sqlite)

    # 1) 目标建表（幂等）
    init_db()
    print("目标表结构已就绪（create_all）")

    with sqlite.connect() as sc, pg_engine.begin() as pc:
        # --force：一次性清空全部目标表 + 重置序列
        if args.force:
            names = ", ".join(f'"{t}"' for t in reversed(TABLES))
            pc.execute(text(f"TRUNCATE {names} RESTART IDENTITY CASCADE"))
            print("已清空目标表（--force）")

        total = 0
        for table in TABLES:
            if not src.has_table(table):
                print(f"  {table:<22} 跳过（源无此表）")
                continue
            existing = pc.execute(text(f'SELECT COUNT(*) FROM "{table}"')).scalar()
            if existing > 0 and not args.force:
                print(f"  {table:<22} 跳过（目标已有 {existing} 行）")
                continue
            rows = [dict(r) for r in sc.execute(text(f'SELECT * FROM "{table}"')).mappings()]
            if not rows:
                print(f"  {table:<22} 0 行")
                continue
            bools = BOOL_COLUMNS.get(table, set())
            for r in rows:
                for col in bools:
                    if col in r and r[col] is not None:
                        r[col] = bool(r[col])
            cols = list(rows[0].keys())
            col_sql = ", ".join(f'"{c}"' for c in cols)
            param_sql = ", ".join(f":{c}" for c in cols)
            pc.execute(text(f'INSERT INTO "{table}" ({col_sql}) VALUES ({param_sql})'), rows)
            # 序列对齐（存在 id 主键的表）
            has_id = any(c == "id" for c in cols) and any(r.get("id") for r in rows)
            if has_id:
                seq = pc.execute(
                    text("SELECT pg_get_serial_sequence(:t, 'id')"), {"t": table}).scalar()
                if seq:
                    max_id = max(r["id"] for r in rows)
                    pc.execute(text(f"SELECT setval('{seq}', :v)"), {"v": max_id})
            print(f"  {table:<22} 迁移 {len(rows)} 行 ✓")
            total += len(rows)

    print(f"\n完成：共迁移 {total} 行。")

    # 2) 迁移后统计
    print("\n目标库行数：")
    with pg_engine.connect() as pc:
        for t in TABLES:
            n = pc.execute(text(f'SELECT COUNT(*) FROM "{t}"')).scalar()
            print(f"  {t:<22} {n}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())