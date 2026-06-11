from sqlalchemy.orm import Session
from sqlalchemy import select, func, Integer
from typing import List
from app.models.student import Student
from app.models.student_course_record import StudentCourseRecord
from app.models.course import Course
from app.models.course_category_mapping import CourseCategoryMapping
from app.models.required_course import RequiredCourse
from app.schemas.recommendation import RecommendedCourse
from app.repositories.credit_check_repository import CreditCheckRepository
from app.services.credit_check_service import CreditCheckService, CAT_ELECTIVE

class RecommendationService:
    def __init__(self, db: Session):
        self.db = db

    def get_recommendations(self, student_id: str) -> List[RecommendedCourse]:
        # 1. 取得學生入學年份
        student = self.db.scalars(
            select(Student).where(Student.student_id == student_id)
        ).first()
        if not student:
            return []

        already_passed_subquery = select(StudentCourseRecord.course_id).where(
            StudentCourseRecord.student_id == student_id,
            StudentCourseRecord.is_passed == True
        )

        missing_required_courses = self.db.execute(
            select(Course)
            .join(RequiredCourse, RequiredCourse.course_id == Course.course_id)
            .join(CourseCategoryMapping, CourseCategoryMapping.course_id == Course.course_id)
            .where(
                RequiredCourse.admission_year == student.admission_year,
                CourseCategoryMapping.category_id == 1,
                Course.course_id.not_in(already_passed_subquery)
            )
            .order_by(Course.course_id)
        ).scalars().all()

        # 缺修必修排在最前面（不再 early return），稍後與缺漏類別（含專業選修）推薦合併回傳
        required_recs = [
            RecommendedCourse(
                course_id=course.course_id,
                course_name=course.course_name,
                category_id=1,
                credits=course.credits,
                peer_pass_rate=self._get_course_pass_rate(course.course_id),
                recommendation_score=2.0
            )
            for course in missing_required_courses
        ]
        required_ids = {course.course_id for course in missing_required_courses}

        # 2~3. 以正式畢業檢核（CreditCheckService）判定哪些類別尚未達標。
        #       直接沿用畢業檢核邏輯，確保與「畢業規則檢核」「進度總覽」一致，
        #       例如專業選修會扣除被群修佔用的學分，避免原始類別加總高估而漏推薦。
        missing_categories = []
        try:
            credit_check = CreditCheckService(
                CreditCheckRepository(self.db)
            ).check_student_graduation(student_id)
        except Exception:
            credit_check = None

        if credit_check:
            for result in credit_check["results"]:
                cat_id = result["category_id"]
                # 0=總學分彙總、99=通識彙總，非實際可推薦課程的類別，略過
                if not result["is_passed"] and cat_id not in (0, 99):
                    missing_categories.append(cat_id)

            # 各類別皆達標、但總學分仍不足 128 時，以專業選修(5)作為補足來源
            total_rule = next(
                (r for r in credit_check["results"] if r["category_id"] == 0),
                None
            )
            if not missing_categories and total_rule and not total_rule["is_passed"]:
                missing_categories = [CAT_ELECTIVE]

        # 去除重複類別
        missing_categories = list(dict.fromkeys(missing_categories))

        if not missing_categories:
            return required_recs  # 已滿足所有類別與總學分門檻，僅回傳缺修必修（若有）

        # 4. 計算所有課程的同儕通過率 (通過人數 / 總修課人數)
        peer_stats = self.db.execute(
            select(
                StudentCourseRecord.course_id,
                func.count(StudentCourseRecord.record_id).label("total_attempts"),
                func.sum(func.cast(StudentCourseRecord.is_passed, Integer)).label("passed_attempts")
            )
            .group_by(StudentCourseRecord.course_id)
        ).all()
        
        # 建立通過率對照表
        pass_rate_map = {}
        for stat in peer_stats:
            rate = (stat.passed_attempts / stat.total_attempts) if stat.total_attempts > 0 else 0
            pass_rate_map[stat.course_id] = round(rate, 2)

        # 5. 撈出符合缺漏類別，且學生尚未通過的候選課程
        candidate_courses = self.db.execute(
            select(Course, CourseCategoryMapping.category_id)
            .join(CourseCategoryMapping, CourseCategoryMapping.course_id == Course.course_id)
            .where(
                CourseCategoryMapping.category_id.in_(missing_categories),
                Course.course_id.not_in(already_passed_subquery)
            )
        ).all()

        # 6. 計算最終推薦權重並排序
        recommendations = []
        seen_ids = set(required_ids)  # 缺修必修已單列於最前，避免重複
        for course, category_id in candidate_courses:
            if course.course_id in seen_ids:
                continue
            seen_ids.add(course.course_id)

            peer_rate = pass_rate_map.get(course.course_id, 0.5) # 若無人修過，預設給予 0.5

            # 將通過率轉換為 1 (爽課) 或 0 (硬課)
            score = self._calculate_weight(peer_rate)

            recommendations.append(
                RecommendedCourse(
                    course_id=course.course_id,
                    course_name=course.course_name,
                    category_id=category_id,
                    credits=course.credits,
                    peer_pass_rate=peer_rate,
                    recommendation_score=score
                )
            )

        # 雙重條件排序：
        # 條件一：-x.recommendation_score (把 1 變成 -1, 0 變成 0。-1 排在 0 前面，確保爽課在上)
        # 條件二：x.course_id (若同為爽課或同為硬課，則依照課號 A-Z 或數字由小到大排列)
        recommendations.sort(key=lambda x: (-x.recommendation_score, x.course_id))

        # 缺修必修排最前，其後接缺漏類別（含專業選修）的推薦
        return required_recs + recommendations

    def _get_course_pass_rate(self, course_id: str) -> float:
        row = self.db.execute(
            select(
                func.count(StudentCourseRecord.record_id).label("total_attempts"),
                func.sum(func.cast(StudentCourseRecord.is_passed, Integer)).label("passed_attempts")
            )
            .where(StudentCourseRecord.course_id == course_id)
        ).first()
        if not row or not row.total_attempts:
            return 0.5
        return round((row.passed_attempts or 0) / row.total_attempts, 2)

    def _calculate_weight(self, pass_rate: float) -> float:
        """
        獨立的權重計算模組：
        若通過率 >= 60% (0.6)，判定為爽課 (1)
        若通過率 < 60%，判定為硬課 (0)
        """
        return 1.0 if pass_rate >= 0.6 else 0.0
