from sqlalchemy.orm import Session

from app.models.student_course_record import StudentCourseRecord


DEMO_STUDENT_ID = "111001001"

DEMO_STUDENT_RECORDS = [
    ("111/1", "703001001", 88, True),
    ("111/1", "000713021", 75, True),
    ("111/2", "000713022", 72, True),
    ("111/2", "703049001", 85, True),
    ("112/1", "703050001", 90, True),
    ("112/1", "703002001", 78, True),
    ("112/1", "703009001", 82, True),
    ("112/2", "703008001", 76, True),
    ("112/2", "703017001", 70, True),
    ("112/2", "703007001", 68, True),
    ("112/2", "703000001", None, True),
    ("113/1", "703022001", 80, True),
    ("113/1", "703014001", 74, True),
    ("113/1", "703015001", 85, True),
    ("113/2", "703019001", 79, True),
    ("113/1", "703044001", 88, True),
    ("113/2", "703046001", 84, True),
    ("114/1", "703047001", 90, True),
    ("112/2", "703038001", 77, True),
    ("113/1", "703027001", 81, True),
    ("113/2", "703059001", 75, True),
    ("111/1", "032001011", 82, True),
    ("111/2", "032002011", 79, True),
    ("111/2", "031004011", 85, True),
    ("112/1", "046001001", 78, True),
    ("112/2", "043045001", 80, True),
    ("113/1", "043016001", 86, True),
    ("112/1", "042183001", 75, True),
    ("112/2", "042112091", 82, True),
    ("113/2", "042215001", 77, True),
    ("111/2", "041038001", 88, True),
    ("112/1", "041099041", 83, True),
    ("113/1", "041026011", 79, True),
    ("114/1", "045024011", 90, True),
    ("111/1", "002008011", 80, True),
    ("111/2", "002301001", 85, True),
    ("112/1", "002366001", 90, True),
    ("112/2", "002362001", 88, True),
    ("114/1", "043048001", 85, True),
    ("114/1", "043025001", 82, True),
    ("114/1", "042195001", 80, True),
    ("114/1", "042133001", 88, True),
    ("114/2", "041095001", 89, True),
    ("114/2", "041100001", 90, True),
    ("114/2", "045064001", 85, True),
    ("113/1", "703100001", 80, True),
    ("113/1", "703100002", 80, True),
    ("113/1", "703100003", 80, True),
    ("113/1", "703100004", 80, True),
    ("113/2", "703100005", 80, True),
    ("113/2", "703100006", 80, True),
    ("113/2", "703100007", 80, True),
    ("113/2", "703100008", 80, True),
    ("114/1", "703100009", 80, True),
    ("114/1", "703100010", 80, True),
    ("114/1", "703100011", 80, True),
    ("114/1", "703100012", 80, True),
    ("114/2", "703100013", 50, False),
    ("114/2", "703100014", 50, False),
]


def reset_demo_student_records(db: Session, student_id: str) -> bool:
    if student_id != DEMO_STUDENT_ID:
        return False

    db.query(StudentCourseRecord).filter(
        StudentCourseRecord.student_id == student_id
    ).delete(synchronize_session=False)

    db.add_all([
        StudentCourseRecord(
            student_id=student_id,
            semester=semester,
            course_id=course_id,
            grade=grade,
            is_passed=is_passed,
        )
        for semester, course_id, grade, is_passed in DEMO_STUDENT_RECORDS
    ])
    db.commit()
    return True
