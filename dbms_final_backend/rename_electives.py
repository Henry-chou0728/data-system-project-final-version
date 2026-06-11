"""
一次性更新 14 門「專業選修（數字）」placeholder 課程為政大資科系實際課名。

特性：
- 只更新 courses 資料表的課名（course_name），不會清空或變更任何修課紀錄。
- 可重複執行（idempotent）：已是新課名時不會重複更動。

執行方式（與 seed.py 相同，於 dbms_final_backend 目錄下）：
    python rename_electives.py
或在 docker 容器內：
    docker compose exec backend python rename_electives.py
"""

from app.database import SessionLocal
from app.models.course import Course


# (course_id, 新課名, 學分)
ELECTIVE_RENAMES = [
    ("002888001", "多媒體技術 (Multimedia Technology)", 2),
    ("703100001", "機器學習 (Machine Learning)", 3),
    ("703100002", "深度學習 (Deep Learning)", 3),
    ("703100003", "資料探勘 (Data Mining)", 3),
    ("703100004", "雲端運算 (Cloud Computing)", 3),
    ("703100005", "行動應用程式設計 (Mobile App Development)", 3),
    ("703100006", "網頁程式設計 (Web Programming)", 3),
    ("703100007", "自然語言處理 (Natural Language Processing)", 3),
    ("703100008", "計算機視覺 (Computer Vision)", 3),
    ("703100009", "區塊鏈技術 (Blockchain Technology)", 3),
    ("703100010", "物聯網概論 (Internet of Things)", 3),
    ("703100011", "平行程式設計 (Parallel Programming)", 3),
    ("703100012", "資訊科學專題討論 (CS Seminar)", 1),
    ("703100013", "數位影像處理 (Digital Image Processing)", 3),
    ("703100014", "推薦系統 (Recommender Systems)", 3),
]


def rename_electives():
    db = SessionLocal()
    updated = 0
    missing = 0
    try:
        for course_id, name, credits in ELECTIVE_RENAMES:
            course = (
                db.query(Course)
                .filter(Course.course_id == course_id)
                .first()
            )
            if course is None:
                print(f"  [skip] 找不到課程 {course_id}（資料庫尚未 seed 此課）")
                missing += 1
                continue

            if course.course_name != name or course.credits != credits:
                course.course_name = name
                course.credits = credits
                updated += 1
                print(f"  [update] {course_id} -> {name}")
            else:
                print(f"  [ok] {course_id} 已是最新課名，略過")

        db.commit()
        print(f"\n完成：更新 {updated} 門、略過/找不到 {missing} 門。")
    except Exception as e:
        db.rollback()
        print(f"更新失敗，已回滾：{e}")
        raise
    finally:
        db.close()


if __name__ == "__main__":
    rename_electives()
