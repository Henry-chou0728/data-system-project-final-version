from app.repositories.credit_check_repository import CreditCheckRepository


CAT_REQUIRED_GENERAL = 1
CAT_REQUIRED_A = 2
CAT_REQUIRED_B = 3
CAT_REQUIRED_C = 4
CAT_ELECTIVE = 5
CAT_GE_CHINESE = 6
CAT_GE_NATURE = 7
CAT_GE_SOCIAL = 8
CAT_GE_HUMANITY = 9
CAT_GE_INFO = 10
CAT_GE_COLLEGE = 11
CAT_CORE_NATURE = 12
CAT_CORE_SOCIAL = 13
CAT_CORE_HUMANITY = 14
CAT_GE_ENGLISH = 15
CAT_PE = 16

GENERAL_REQUIRED_TARGET = 39
REQUIRED_TOTAL_TARGET = 51
ELECTIVE_TARGET = 49
GE_TOTAL_TARGET = 28
TOTAL_CREDIT_TARGET = 128
PE_REQUIRED_COURSES = 4

ELECTIVE_REQUIRED_A = {
    "703044001",
    "703045001",
    "703046001",
    "703047001",
}
ELECTIVE_REQUIRED_B = {
    "703038001",
    "703027001",
    "703039001",
    "703055001",
    "703025001",
    "703060001",
}
ELECTIVE_REQUIRED_C = {
    "703012001",
    "703013001",
    "703018001",
    "703021001",
    "703059001",
    "703053001",
    "703010001",
    "703042001",
}


class CreditCheckService:
    def __init__(self, repository: CreditCheckRepository):
        self.repository = repository

    def check_student_graduation(self, student_id: int):
        student = self.repository.get_student_by_id(student_id)

        if student is None:
            return None

        passed_records = self.repository.get_passed_records_by_student(
            student.student_id
        )
        passed_by_course = {}
        for record in passed_records:
            passed_by_course.setdefault(record.course_id, record)

        passed_course_ids = set(passed_by_course)

        categories_by_course = self._get_categories_by_course(student.student_id)

        required_course_check = self._check_required_courses(
            student.admission_year,
            passed_course_ids,
            passed_by_course,
            categories_by_course,
        )

        group_checks = [
            self._check_elective_group(
                rule_id=-201,
                group_name="群A",
                course_ids=ELECTIVE_REQUIRED_A,
                required_courses=2,
                required_credits=6,
                passed_by_course=passed_by_course,
            ),
            self._check_elective_group(
                rule_id=-202,
                group_name="群B",
                course_ids=ELECTIVE_REQUIRED_B,
                required_courses=1,
                required_credits=3,
                passed_by_course=passed_by_course,
            ),
            self._check_elective_group(
                rule_id=-203,
                group_name="群C",
                course_ids=ELECTIVE_REQUIRED_C,
                required_courses=1,
                required_credits=3,
                passed_by_course=passed_by_course,
            ),
        ]

        ge_checks, ge_effective_credits = self._check_general_education(
            passed_by_course,
            categories_by_course,
        )

        elective_credits = self._calculate_elective_credits(
            passed_by_course,
            categories_by_course,
            group_checks,
        )

        required_group_credits = sum(
            group["counted_required_credits"] for group in group_checks
        )
        required_effective_credits = min(
            required_course_check["earned_credits"], GENERAL_REQUIRED_TARGET
        ) + required_group_credits

        required_summary = self._build_rule_result(
            rule_id=-100,
            category_id=CAT_REQUIRED_GENERAL,
            main_type="規定必修",
            sub_type="一般必修與群修",
            required_courses=None,
            passed_courses=required_course_check["passed_required"],
            required_credits=REQUIRED_TOTAL_TARGET,
            earned_credits=required_effective_credits,
            is_passed=(
                required_course_check["is_passed"]
                and all(group["is_passed"] for group in group_checks)
                and required_effective_credits >= REQUIRED_TOTAL_TARGET
            ),
        )

        elective_check = self._build_rule_result(
            rule_id=-300,
            category_id=CAT_ELECTIVE,
            main_type="選修",
            sub_type=None,
            required_courses=None,
            passed_courses=0,
            required_credits=ELECTIVE_TARGET,
            earned_credits=elective_credits,
            is_passed=elective_credits >= ELECTIVE_TARGET,
        )

        total_credits = (
            required_effective_credits
            + elective_credits
            + ge_effective_credits
        )
        total_check = self._build_rule_result(
            rule_id=-400,
            category_id=0,
            main_type="最低畢業總學分",
            sub_type=None,
            required_courses=None,
            passed_courses=0,
            required_credits=TOTAL_CREDIT_TARGET,
            earned_credits=total_credits,
            is_passed=total_credits >= TOTAL_CREDIT_TARGET,
        )

        results = [
            required_summary,
            *group_checks,
            elective_check,
            *ge_checks,
            total_check,
        ]

        return {
            "student_id": student.student_id,
            "admission_year": student.admission_year,
            "required_course_check": required_course_check,
            "results": results,
            "credit_summary": {
                "required_credits": required_effective_credits,
                "elective_credits": elective_credits,
                "general_education_credits": ge_effective_credits,
                "total_credits": total_credits,
                "required_target": REQUIRED_TOTAL_TARGET,
                "elective_target": ELECTIVE_TARGET,
                "general_education_target": GE_TOTAL_TARGET,
                "total_target": TOTAL_CREDIT_TARGET,
                "is_graduation_ready": all(result["is_passed"] for result in results),
            },
        }

    def get_graduation_summary(self, student_id: int):
        check_result = self.check_student_graduation(student_id)

        if check_result is None:
            return None

        results = check_result["results"]
        total_rules = len(results)
        passed_rules = sum(1 for result in results if result["is_passed"])
        failed_rules = total_rules - passed_rules
        progress_percent = round((passed_rules / total_rules) * 100, 2)

        return {
            "student_id": check_result["student_id"],
            "total_rules": total_rules,
            "passed_rules": passed_rules,
            "failed_rules": failed_rules,
            "progress_percent": progress_percent,
            "is_graduation_ready": failed_rules == 0,
        }

    def _get_categories_by_course(self, student_id: str):
        categories_by_course = {}
        for category_id in [
            CAT_REQUIRED_GENERAL,
            CAT_ELECTIVE,
            CAT_GE_CHINESE,
            CAT_GE_NATURE,
            CAT_GE_SOCIAL,
            CAT_GE_HUMANITY,
            CAT_GE_INFO,
            CAT_GE_COLLEGE,
            CAT_CORE_NATURE,
            CAT_CORE_SOCIAL,
            CAT_CORE_HUMANITY,
            CAT_GE_ENGLISH,
            CAT_PE,
        ]:
            records = self.repository.get_passed_records_by_category(
                student_id=student_id,
                category_id=category_id,
            )
            for record in records:
                categories_by_course.setdefault(record.course_id, set()).add(
                    category_id
                )
        return categories_by_course

    def _check_required_courses(
        self,
        admission_year,
        passed_course_ids,
        passed_by_course,
        categories_by_course,
    ):
        required_courses = self.repository.get_required_courses_by_admission_year(
            admission_year
        )
        missing_courses = []
        earned_credits = 0

        for required_course in required_courses:
            course_id = required_course.course_id
            if course_id in passed_course_ids:
                earned_credits += required_course.course.credits
            else:
                missing_courses.append({
                    "course_id": required_course.course.course_id,
                    "course_name": required_course.course.course_name,
                    "credits": required_course.course.credits,
                })

        pe_records = [
            record for course_id, record in passed_by_course.items()
            if CAT_PE in categories_by_course.get(course_id, set())
        ]
        pe_missing = max(PE_REQUIRED_COURSES - len(pe_records), 0)
        if pe_missing > 0:
            missing_courses.append({
                "course_id": "PE_REQUIRED",
                "course_name": f"體育必修尚缺 {pe_missing} 門",
                "credits": 0,
            })

        required_total = len(required_courses) + PE_REQUIRED_COURSES
        passed_required = (
            len(required_courses)
            - sum(1 for course in required_courses if course.course_id not in passed_course_ids)
            + min(len(pe_records), PE_REQUIRED_COURSES)
        )

        return {
            "required_total": required_total,
            "passed_required": passed_required,
            "missing_required": required_total - passed_required,
            "is_passed": (
                len(missing_courses) == 0
                and earned_credits >= GENERAL_REQUIRED_TARGET
            ),
            "missing_courses": missing_courses,
            "earned_credits": earned_credits,
            "required_credits": GENERAL_REQUIRED_TARGET,
        }

    def _check_elective_group(
        self,
        rule_id,
        group_name,
        course_ids,
        required_courses,
        required_credits,
        passed_by_course,
    ):
        passed = [
            record for course_id, record in passed_by_course.items()
            if course_id in course_ids
        ]
        earned_credits = sum(record.course.credits for record in passed)
        counted_required_credits = min(earned_credits, required_credits)
        is_passed = (
            len(passed) >= required_courses
            and earned_credits >= required_credits
        )

        result = self._build_rule_result(
            rule_id=rule_id,
            category_id={
                "群A": CAT_REQUIRED_A,
                "群B": CAT_REQUIRED_B,
                "群C": CAT_REQUIRED_C,
            }[group_name],
            main_type="群修",
            sub_type=group_name,
            required_courses=required_courses,
            passed_courses=len(passed),
            required_credits=required_credits,
            earned_credits=counted_required_credits,
            is_passed=is_passed,
        )
        result["raw_earned_credits"] = earned_credits
        result["counted_required_credits"] = counted_required_credits
        result["overflow_elective_credits"] = max(
            earned_credits - required_credits,
            0,
        )
        return result

    def _check_general_education(self, passed_by_course, categories_by_course):
        ge_specs = [
            (CAT_GE_CHINESE, "通識", "中文通識", 1, 3, 3),
            (CAT_GE_INFO, "通識", "資訊通識", None, 2, 3),
            (CAT_GE_NATURE, "通識", "自然通識", 1, 3, 7),
            (CAT_GE_SOCIAL, "通識", "社會通識", 1, 3, 7),
            (CAT_GE_HUMANITY, "通識", "人文通識", 1, 3, 7),
            (CAT_GE_COLLEGE, "通識", "書院通識", None, 0, 3),
            (CAT_GE_ENGLISH, "通識", "大學英文", 2, 6, 6),
        ]

        checks = []
        effective_total = 0
        for category_id, main_type, sub_type, min_courses, min_credits, max_credits in ge_specs:
            records = self._records_for_category(
                passed_by_course,
                categories_by_course,
                category_id,
            )
            raw_credits = sum(record.course.credits for record in records)
            effective_credits = min(raw_credits, max_credits)
            is_passed = effective_credits >= min_credits
            if min_courses is not None:
                is_passed = is_passed and len(records) >= min_courses
            effective_total += effective_credits
            checks.append(self._build_rule_result(
                rule_id=-500 - category_id,
                category_id=category_id,
                main_type=main_type,
                sub_type=sub_type,
                required_courses=min_courses,
                passed_courses=len(records),
                required_credits=min_credits,
                earned_credits=effective_credits,
                is_passed=is_passed,
            ))

        core_categories = [
            CAT_CORE_NATURE,
            CAT_CORE_SOCIAL,
            CAT_CORE_HUMANITY,
        ]
        passed_core_fields = []
        seen_core_courses = set()
        for category_id in core_categories:
            records = self._records_for_category(
                passed_by_course,
                categories_by_course,
                category_id,
            )
            unique_records = [
                record for record in records
                if record.course_id not in seen_core_courses
            ]
            if unique_records:
                passed_core_fields.append(category_id)
                seen_core_courses.add(unique_records[0].course_id)

        checks.append(self._build_rule_result(
            rule_id=-600,
            category_id=CAT_CORE_NATURE,
            main_type="核心通識",
            sub_type="自然/社會/人文三選二",
            required_courses=2,
            passed_courses=len(passed_core_fields),
            required_credits=None,
            earned_credits=0,
            is_passed=len(passed_core_fields) >= 2,
        ))

        ge_total = min(effective_total, GE_TOTAL_TARGET)
        checks.append(self._build_rule_result(
            rule_id=-700,
            category_id=99,
            main_type="通識",
            sub_type="通識總學分",
            required_courses=None,
            passed_courses=0,
            required_credits=GE_TOTAL_TARGET,
            earned_credits=ge_total,
            is_passed=ge_total >= GE_TOTAL_TARGET,
        ))

        return checks, ge_total

    def _calculate_elective_credits(
        self,
        passed_by_course,
        categories_by_course,
        group_checks,
    ):
        elective_records = self._records_for_category(
            passed_by_course,
            categories_by_course,
            CAT_ELECTIVE,
        )
        elective_credits = sum(record.course.credits for record in elective_records)
        required_group_credits = sum(
            group["counted_required_credits"] for group in group_checks
        )
        return max(elective_credits - required_group_credits, 0)

    def _records_for_category(
        self,
        passed_by_course,
        categories_by_course,
        category_id,
    ):
        return [
            record for course_id, record in passed_by_course.items()
            if category_id in categories_by_course.get(course_id, set())
        ]

    def _build_rule_result(
        self,
        rule_id,
        category_id,
        main_type,
        sub_type,
        required_courses,
        passed_courses,
        required_credits,
        earned_credits,
        is_passed,
    ):
        missing_courses_count = None
        if required_courses is not None:
            missing_courses_count = max(required_courses - passed_courses, 0)

        missing_credits = None
        if required_credits is not None:
            missing_credits = max(required_credits - earned_credits, 0)

        return {
            "rule_id": rule_id,
            "category_id": category_id,
            "main_type": main_type,
            "sub_type": sub_type,
            "required_courses": required_courses,
            "passed_courses": passed_courses,
            "missing_courses_count": missing_courses_count,
            "required_credits": required_credits,
            "earned_credits": earned_credits,
            "missing_credits": missing_credits,
            "is_passed": is_passed,
        }
