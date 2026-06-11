import axios from 'axios';
import { CourseRecord, GradRule, RecommendedCourse, ClassroomTransit, StudentDashboard } from '../types';
import {
  initialClassroomTransits,
  initialUploadHistory
} from '../mock/data';

const runtimeApiUrl = window.__APP_CONFIG__?.VITE_API_URL?.trim();
const railwayBackendUrl = window.location.hostname.endsWith('.up.railway.app')
  ? 'https://backend-production-fe197.up.railway.app'
  : '';

// Create the real Axios instance pointing to the FastAPI backend
export const apiClient = axios.create({
  baseURL: runtimeApiUrl || import.meta.env.VITE_API_URL || railwayBackendUrl || '/api',
  headers: {
    'Content-Type': 'application/json',
  },
});

// Axios Request Interceptor to automatically append JWT Bearer Token if available
apiClient.interceptors.request.use((config) => {
  const token = localStorage.getItem('token');
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
}, (error) => {
  return Promise.reject(error);
});

// Axios Response Interceptor to handle 401 Unauthorized and redirect to login
apiClient.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response && error.response.status === 401) {
      localStorage.removeItem('token');
      localStorage.removeItem('student_id');
      localStorage.removeItem('student_dashboard');
      localStorage.removeItem('isLoggedIn');
      window.location.hash = '/login';
    }
    return Promise.reject(error);
  }
);

// Helper to initialize LocalStorage with frontend-only configs if empty
const initLocalStorage = () => {
  if (!localStorage.getItem('upload_history')) {
    localStorage.setItem('upload_history', JSON.stringify(initialUploadHistory));
  }
};

initLocalStorage();

// Cache maps for course metadata to prevent redundant API lookups
let courseDetailsMap: Map<string, { name: string, credits: number, type: 'required' | 'elective' | 'general' | 'pe' | 'english' }> = new Map();
let simulatedCourseRecords: CourseRecord[] = [];

// Broadcast whenever the student's course records change (add/delete/import)
// so mounted pages (Dashboard / GraduationCheck) can re-fetch credit progress live.
export const COURSE_RECORDS_CHANGED_EVENT = 'course-records-changed';
const notifyCourseRecordsChanged = () => {
  if (typeof window !== 'undefined') {
    window.dispatchEvent(new Event(COURSE_RECORDS_CHANGED_EVENT));
  }
};

const resolveCourseDetails = async () => {
  if (courseDetailsMap.size > 0) return courseDetailsMap;

  try {
    const [coursesRes, categoriesRes, mappingsRes] = await Promise.all([
      apiClient.get('/courses/'),
      apiClient.get('/course-categories/'),
      apiClient.get('/course-category-mappings/')
    ]);

    const courses = coursesRes.data;
    const categories = new Map<number, string>(categoriesRes.data.map((c: any) => [c.category_id, c.sub_type || c.main_type]));
    const mappings = mappingsRes.data;

    const courseCatMap = new Map<string, string>(
      mappings.map((m: any) => [m.course_id, categories.get(m.category_id) || ''])
    );

    courses.forEach((c: any) => {
      const backendType = courseCatMap.get(c.course_id) || '選修';
      let type: 'required' | 'elective' | 'general' | 'pe' | 'english' = 'elective';
      
      if (backendType.includes('必修') || backendType === 'required') type = 'required';
      else if (backendType.includes('選修') || backendType === 'elective') type = 'elective';
      else if (backendType.includes('通識') || backendType === 'general') type = 'general';
      else if (backendType.includes('體育') || backendType === 'pe') type = 'pe';
      else if (backendType.includes('英文') || backendType === 'english') type = 'english';

      courseDetailsMap.set(c.course_id, {
        name: c.course_name,
        credits: c.credits,
        type
      });
    });
  } catch (e) {
    console.error("Error resolving course details:", e);
  }

  return courseDetailsMap;
};

export const graduationService = {
  // Reset database state to mock initial (Cleared from localStorage side)
  async resetData(): Promise<void> {
    localStorage.removeItem('upload_history');
    localStorage.setItem('upload_history', JSON.stringify(initialUploadHistory));
  },

  // Auth Integration
  async login(studentId: string, password: string): Promise<{ success: boolean; token: string; student: StudentDashboard }> {
    if (!studentId) {
      throw new Error('請輸入學號');
    }
    if (!password) {
      throw new Error('請輸入密碼');
    }

    const params = new URLSearchParams();
    params.append('username', studentId);
    params.append('password', password);

    const response = await apiClient.post('/auth/login', params, {
      headers: {
        'Content-Type': 'application/x-www-form-urlencoded'
      }
    });

    const token = response.data.access_token;
    localStorage.setItem('token', token);
    localStorage.setItem('student_id', studentId);
    localStorage.removeItem('student_dashboard');
    simulatedCourseRecords = [];

    // Fetch the dashboard info for the student profile
    const dashboard = await this.getDashboardData();

    return {
      success: true,
      token: token,
      student: dashboard
    };
  },

  // Dashboard API
  async getDashboardData(): Promise<StudentDashboard> {
    const studentId = localStorage.getItem('student_id') || '111001001';

    const [studentRes, creditCheckRes, recordsRes, detailsMap] = await Promise.all([
      apiClient.get(`/students/${studentId}`),
      apiClient.get('/credit-check/me'),
      apiClient.get('/student-course-records/me'),
      resolveCourseDetails()
    ]);

    const student = studentRes.data;
    const creditCheck = creditCheckRes.data;
    const records = [
      ...recordsRes.data.map((r: any) => ({
        courseId: r.course_id,
        isPassed: r.is_passed,
        fallbackName: r.course_name,
        fallbackCredits: r.credits,
        fallbackType: undefined as CourseRecord['type'] | undefined
      })),
      ...simulatedCourseRecords.map((r) => ({
        courseId: r.courseId,
        isPassed: true,
        fallbackName: r.courseName,
        fallbackCredits: r.credits,
        fallbackType: r.type
      }))
    ];

    let completedRequired = 0;
    let completedElective = 0;
    let completedGeneral = 0;
    let completedPe = 0;
    let completedEnglish = 0;
    const failedElectiveCourses: string[] = [];

    records.forEach((r) => {
      const details = detailsMap.get(r.courseId);
      const credits = details?.credits ?? r.fallbackCredits ?? 0;
      const type = details?.type ?? r.fallbackType ?? 'elective';

      if (!r.isPassed) {
        if (type === 'elective') {
          failedElectiveCourses.push(details?.name || r.fallbackName || r.courseId);
        }
        return;
      }

      if (type === 'required') completedRequired += credits;
      else if (type === 'elective') completedElective += credits;
      else if (type === 'general') completedGeneral += credits;
      else if (type === 'pe') completedPe += 1;
      else if (type === 'english') {
        completedEnglish += credits;
      }
    });

    const simulatedTotals = simulatedCourseRecords.reduce(
      (totals, record) => {
        if (record.type === 'required') totals.required += record.credits;
        else if (record.type === 'elective') totals.elective += record.credits;
        else if (record.type === 'general') totals.general += record.credits;
        else if (record.type === 'english') totals.english += record.credits;
        else if (record.type === 'pe') totals.pe += 1;
        return totals;
      },
      { required: 0, elective: 0, general: 0, english: 0, pe: 0 }
    );

    const summary = creditCheck.credit_summary || {};
    const totalRequired = summary.total_target ?? 128;

    const requiredTarget = summary.required_target ?? 51;
    const requiredBase = summary.required_credits ?? (completedRequired - simulatedTotals.required);
    const requiredCompleted = requiredBase + simulatedTotals.required;
    const englishRule = creditCheck.results?.find((res: any) => res.category_id === 15);
    const englishTarget = englishRule?.required_credits ?? 6;
    const englishPassed = Boolean(englishRule?.is_passed) || simulatedTotals.english >= englishTarget;
    const generalTarget = summary.general_education_target ?? 28;
    const electiveTarget = summary.elective_target ?? 49;
    const electiveBase = summary.elective_credits ?? (completedElective - simulatedTotals.elective);
    const electiveCompleted = electiveBase + simulatedTotals.elective;
    const generalBase = summary.general_education_credits ?? Math.min(
      completedGeneral + completedEnglish - simulatedTotals.general - simulatedTotals.english,
      generalTarget
    );
    const generalCompleted = Math.min(
      generalTarget,
      generalBase + simulatedTotals.general + simulatedTotals.english
    );
    const totalCompleted = Math.min(
      totalRequired,
      requiredCompleted + electiveCompleted + generalCompleted
    );
    let peTarget = 4;

    const categoryProgress = {
      required: { completed: requiredCompleted, target: requiredTarget },
      elective: { completed: electiveCompleted, target: electiveTarget },
      general: { completed: generalCompleted, target: generalTarget },
      pe: { completed: completedPe, target: peTarget },
      english: { completed: englishPassed, target: englishTarget }
    };

    const missingCourses = creditCheck.required_course_check.missing_courses.map((c: any) => c.course_name);

    const dashboard = {
      studentName: student.name,
      studentId: student.student_id,
      department: student.department,
      currentSemester: "112 學年度第二學期",
      totalRequiredCredits: totalRequired,
      totalCompletedCredits: totalCompleted,
      missingCredits: Math.max(0, totalRequired - totalCompleted),
      missingRequiredCount: creditCheck.required_course_check.missing_required,
      missingRequiredCourses: missingCourses,
      missingElectiveCourses: failedElectiveCourses,
      categoryProgress
    };

    localStorage.setItem('student_dashboard', JSON.stringify(dashboard));
    return dashboard;
  },

  // Course Record API
  async getCourseRecords(): Promise<CourseRecord[]> {
    const [recordsRes, detailsMap] = await Promise.all([
      apiClient.get('/student-course-records/me'),
      resolveCourseDetails()
    ]);

    const backendRecords = recordsRes.data.map((r: any) => {
      const details = detailsMap.get(r.course_id);
      return {
        id: String(r.record_id),
        semester: r.semester,
        courseId: r.course_id,
        courseName: details?.name || "未定義課程",
        credits: details?.credits ?? 0,
        grade: r.grade !== null ? String(r.grade) : (r.is_passed ? "Pass" : "F"),
        type: details?.type ?? 'elective'
      };
    });

    return [...backendRecords, ...simulatedCourseRecords];
  },

  getSimulatedCourseRecordIds(): string[] {
    return simulatedCourseRecords.map((record) => record.courseId);
  },

  async addSimulatedCourseRecord(record: Omit<CourseRecord, 'id'>): Promise<CourseRecord> {
    const existing = simulatedCourseRecords.find((item) => item.courseId === record.courseId);
    if (existing) return existing;

    const simulatedRecord: CourseRecord = {
      ...record,
      id: `sim-${Date.now()}-${record.courseId}`
    };

    simulatedCourseRecords = [...simulatedCourseRecords, simulatedRecord];
    localStorage.removeItem('student_dashboard');
    notifyCourseRecordsChanged();
    return simulatedRecord;
  },

  async addCourseRecord(record: Omit<CourseRecord, 'id'>): Promise<CourseRecord> {
    const studentId = localStorage.getItem('student_id') || '111001001';

    // 1. Check if course exists
    let courseExists = false;
    try {
      await apiClient.get(`/courses/${record.courseId}`);
      courseExists = true;
    } catch (e) {
      courseExists = false;
    }

    if (!courseExists) {
      // Create Course
      await apiClient.post('/courses/', {
        course_id: record.courseId,
        course_name: record.courseName,
        credits: record.credits,
        taught_by: null
      });

      // Keep frontend-added course mappings aligned with backend category IDs.
      let categoryId = 5; // Default elective
      if (record.type === 'required') categoryId = 1;
      else if (record.type === 'elective') categoryId = 5;
      else if (record.type === 'general') categoryId = 6;
      else if (record.type === 'pe') categoryId = 16;
      else if (record.type === 'english') categoryId = 15;

      // Create Mapping
      await apiClient.post('/course-category-mappings/', {
        course_id: record.courseId,
        category_id: categoryId
      });
    }

    // 2. Parse grade to integer
    const numericGrade = parseInt(record.grade);
    const isPassed = !isNaN(numericGrade) ? numericGrade >= 60 : (
      record.grade.toLowerCase() === 'pass' || 
      ['A+', 'A', 'A-', 'B+', 'B', 'B-', 'C+', 'C', 'C-'].includes(record.grade.toUpperCase())
    );

    const response = await apiClient.post('/student-course-records/', {
      student_id: studentId,
      course_id: record.courseId,
      semester: record.semester,
      grade: isNaN(numericGrade) ? null : numericGrade,
      is_passed: isPassed
    });

    // Clear local cache to force refresh in subsequent calls
    courseDetailsMap.clear();
    notifyCourseRecordsChanged();

    return {
      id: String(response.data.record_id),
      semester: record.semester,
      courseId: record.courseId,
      courseName: record.courseName,
      credits: record.credits,
      grade: record.grade,
      type: record.type
    };
  },

  async deleteCourseRecord(id: string): Promise<void> {
    if (id.startsWith('sim-')) {
      simulatedCourseRecords = simulatedCourseRecords.filter((record) => record.id !== id);
      localStorage.removeItem('student_dashboard');
      notifyCourseRecordsChanged();
      return;
    }

    await apiClient.delete(`/student-course-records/${parseInt(id)}`);
    courseDetailsMap.clear();
    notifyCourseRecordsChanged();
  },

  // Graduation Check Rules API
  async getGraduationRules(): Promise<GradRule[]> {
    const [creditCheckRes, dashboard] = await Promise.all([
      apiClient.get('/credit-check/me'),
      this.getDashboardData()
    ]);

    const creditCheck = creditCheckRes.data;
    const rules: GradRule[] = [];

    // 1. General Required Course Rule
    const reqCheck = creditCheck.required_course_check;
    const missingCompulsoryNames = reqCheck.missing_courses.map((c: any) => `【${c.course_name}】`).join('、');
    rules.push({
      id: "r1",
      name: "系定必修",
      type: "Major Required",
      required: `${reqCheck.required_total} 門`,
      completed: `${reqCheck.passed_required} 門`,
      progress: Math.min(100, Math.round((reqCheck.passed_required / reqCheck.required_total) * 100)) || 0,
      status: reqCheck.is_passed ? "completed" : "failed",
      details: reqCheck.is_passed
        ? "已修畢所有系定必修"
        : `缺課：${missingCompulsoryNames} 等`
    });

    // 2. Dynamic Rules from Backend
    if (creditCheck.results) {
      creditCheck.results.forEach((res: any, idx: number) => {
        let name = res.sub_type ? `${res.main_type} - ${res.sub_type}` : res.main_type;
        let mainType = res.main_type;

        if (res.category_id === 5) {
            mainType = "專業選修";
            name = "專業選修學分門檻";
        }

        if (mainType === '群修') {
            mainType = "系選修";
            name = `系選修 - ${res.sub_type}`;
        }

        let requiredStr = "";
        let completedStr = "";
        let progress = 0;
        let details = "";

        if (res.required_credits !== null && res.required_courses !== null) {
           requiredStr = `>= ${res.required_courses} 門 / ${res.required_credits} 學分`;
           completedStr = `${res.passed_courses} 門 / ${res.earned_credits} 學分`;
           const courseProgress = res.required_courses === 0 ? 100 : Math.round((res.passed_courses / res.required_courses) * 100);
           const creditProgress = res.required_credits === 0 ? 100 : Math.round((res.earned_credits / res.required_credits) * 100);
           progress = Math.min(100, Math.min(courseProgress, creditProgress)) || 0;
           details = res.is_passed ? "門數與學分皆達標" : `缺 ${res.missing_courses_count ?? 0} 門 / ${res.missing_credits ?? 0} 學分`;
        } else if (res.required_credits !== null) {
           requiredStr = `>= ${res.required_credits} 學分`;
           completedStr = `${res.earned_credits} 學分`;
           progress = res.required_credits === 0 ? 100 : Math.min(100, Math.round((res.earned_credits / res.required_credits) * 100)) || 0;
           details = res.is_passed ? "學分達標" : `缺 ${res.missing_credits} 學分`;
        } else if (res.required_courses !== null) {
           requiredStr = `>= ${res.required_courses} 門`;
           completedStr = `${res.passed_courses} 門`;
           progress = res.required_courses === 0 ? 100 : Math.min(100, Math.round((res.passed_courses / res.required_courses) * 100)) || 0;
           details = res.is_passed ? "修課數達標" : `缺 ${res.missing_courses_count} 門`;
        }

        rules.push({
          id: `db_r${res.rule_id || idx}`,
          name: name,
          type: mainType,
          required: requiredStr,
          completed: completedStr,
          progress: progress,
          status: res.is_passed ? "completed" : "failed",
          details: details
        });
      });
    }

    return rules;
  },

  async getRecommendedCourses(): Promise<RecommendedCourse[]> {
    const studentId = localStorage.getItem('student_id') || '111001001';
    const response = await apiClient.get(`/recommendations/${studentId}`);

    return response.data.map((item: any) => {
      const categoryId = Number(item.category_id);
      let category = "其他修課建議";
      if (categoryId === 1) category = "核心必修（補修）";
      else if ([2, 3, 4].includes(categoryId)) category = "群修課程補修";
      else if (categoryId === 5) category = "專業選修推薦";
      else if ([6, 7, 8, 9, 10, 11, 12, 13, 14, 15].includes(categoryId)) category = "通識課程補修";
      else if (categoryId === 16) category = "體育課程補修";

      let difficulty: 'Easy' | 'Medium' | 'Hard' = 'Medium';
      if (item.peer_pass_rate >= 0.95) difficulty = 'Easy';
      else if (item.peer_pass_rate < 0.8) difficulty = 'Hard';

      return {
        courseId: item.course_id,
        courseName: item.course_name,
        categoryId,
        category: category,
        credits: item.credits,
        passRate: Math.round(item.peer_pass_rate * 100),
        difficulty: difficulty,
        semester: "113學年度第一學期 (秋季)"
      };
    });
  },

  // Classroom Warnings API (Kept local since geo-coordinates and schedules are not DB-modeled)
  async getClassroomTransits(): Promise<ClassroomTransit[]> {
    return initialClassroomTransits;
  },

  // Upload History API (Kept local in LocalStorage)
  async getUploadHistory(): Promise<any[]> {
    return JSON.parse(localStorage.getItem('upload_history') || '[]');
  },

  // Parse CSV and append to system records
  async parseAndImportCSV(csvText: string, filename: string): Promise<{ success: boolean; importedCount: number }> {
    const lines = csvText.split('\n').filter(line => line.trim().length > 0);
    if (lines.length < 2) {
      throw new Error("CSV 格式不正確：請確保有標題行與資料行");
    }

    const importedRecords: Omit<CourseRecord, 'id'>[] = [];
    
    for (let i = 1; i < lines.length; i++) {
      const parts = lines[i].split(',').map(s => s.trim().replace(/^["']|["']$/g, ''));
      if (parts.length >= 5) {
        const semester = parts[0] || "112學年度第二學期";
        const courseId = parts[1] || `703${Math.floor(Math.random() * 1000000)}`;
        const courseName = parts[2] || "未命名課程";
        const credits = parseFloat(parts[3]) || 3;
        const grade = parts[4] || "A";
        
        let type: 'required' | 'elective' | 'general' | 'pe' | 'english' = 'elective';
        const typeField = parts[5]?.toLowerCase() || '';
        
        if (typeField.includes('必修') || typeField.includes('required')) {
          type = 'required';
        } else if (typeField.includes('通識') || typeField.includes('general')) {
          type = 'general';
        } else if (typeField.includes('體育') || typeField.includes('pe')) {
          type = 'pe';
        } else if (typeField.includes('英文') || typeField.includes('english')) {
          type = 'english';
        } else {
          if (courseName.includes('通識') || courseName.includes('科學與') || courseName.includes('跨領域')) {
            type = 'general';
          } else if (courseName.includes('體育')) {
            type = 'pe';
          } else if (courseName.includes('英文')) {
            type = 'english';
          } else if (['計算機', '演算法', '資料結構', '微積分', '線性代數', '作業系統', '軟體工程', '系統程式'].some(k => courseName.includes(k))) {
            type = 'required';
          }
        }

        importedRecords.push({
          semester,
          courseId,
          courseName,
          credits,
          grade,
          type
        });
      }
    }

    if (importedRecords.length === 0) {
      throw new Error("無法解析任何有效的修課學期紀錄。請檢查欄位順序！");
    }

    // Sequentially upload each record to the FastAPI backend
    for (const rec of importedRecords) {
      await this.addCourseRecord(rec);
    }

    // Update upload history locally
    const history = JSON.parse(localStorage.getItem('upload_history') || '[]');
    const newHistory = {
      id: `h_${Date.now()}`,
      filename,
      uploadAt: new Date().toISOString().replace('T', ' ').substring(0, 16),
      fileSize: `${(csvText.length / 1024).toFixed(1)} KB`,
      status: "解析成功",
      recordsCount: importedRecords.length
    };
    history.unshift(newHistory);
    localStorage.setItem('upload_history', JSON.stringify(history));

    return {
      success: true,
      importedCount: importedRecords.length
    };
  }
};
