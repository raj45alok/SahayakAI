// src/services/api.ts

const CONTENT_API_BASE = process.env.REACT_APP_CONTENT_API_URL || 'https://4x4vw766tf.execute-api.us-east-1.amazonaws.com/prod';
const DOUBT_API_BASE = process.env.REACT_APP_DOUBT_API_URL || 'https://wfwgkepe4c.execute-api.us-east-1.amazonaws.com/prod';
// NEW: Auth API Base
const AUTH_API_BASE = process.env.REACT_APP_AUTH_API_URL || 'https://q72zzi8dw8.execute-api.us-east-1.amazonaws.com/Prod';

class SahayakAPI {
  private async request(baseUrl: string, endpoint: string, options: RequestInit = {}) {
    const url = `${baseUrl}${endpoint}`;
    
    const response = await fetch(url, {
      ...options,
      headers: {
        'Content-Type': 'application/json',
        ...options.headers,
      },
    });

    if (!response.ok) {
      const error = await response.json().catch(() => ({ error: 'Request failed' }));
      throw new Error(error.error || error.message || 'API request failed');
    }

    return response.json();
  }

  // ===== AUTHENTICATION API =====
  
  async getUserByFirebaseUid(firebaseUid: string) {
    return this.request(AUTH_API_BASE, '/auth/user', {
      method: 'POST',
      body: JSON.stringify({ firebaseUid }),
    });
  }

  async saveUser(firebaseUser: any, userType: 'student' | 'teacher', additionalData?: any) {
    return this.request(AUTH_API_BASE, '/auth/save-user', {
      method: 'POST',
      body: JSON.stringify({
        firebaseUser,
        userType,
        additionalData,
      }),
    });
  }

  async checkUserExists(firebaseUid: string) {
    return this.request(AUTH_API_BASE, '/auth/check-user', {
      method: 'POST',
      body: JSON.stringify({ firebaseUid }),
    });
  }

  // ===== CONTENT DELIVERY API =====
  
  async getUploadUrl(data: {
    teacherId: string;
    fileName: string;
    fileSize: number;
  }) {
    return this.request(CONTENT_API_BASE, '/content/get-upload-url', {
      method: 'POST',
      body: JSON.stringify(data),
    });
  }

  async uploadToS3(presignedUrl: string, file: File) {
    const response = await fetch(presignedUrl, {
      method: 'PUT',
      headers: {
        'Content-Type': 'application/pdf',
      },
      body: file,
    });

    if (!response.ok) {
      throw new Error('Failed to upload file to S3');
    }

    return response;
  }

  async processContent(data: {
    teacherId: string;
    classId: string;
    subject: string;
    numParts: number;
    pdfBase64?: string;
    s3Key?: string;
    textContent?: string;
    instructions?: string;
    language?: string;
  }) {
    return this.request(CONTENT_API_BASE, '/content/process', {
      method: 'POST',
      body: JSON.stringify(data),
    });
  }

  async getPreview(contentId: string) {
    return this.request(CONTENT_API_BASE, '/content/preview', {
      method: 'POST',
      body: JSON.stringify({ contentId }),
    });
  }

  async updateContent(data: {
    contentId: string;
    action: 'update';
    partNumber: string;
    updates: {
      enhancedContent?: string;
      videoLinks?: any[];
      practiceQuestions?: any[];
      summary?: string;
    };
  }) {
    return this.request(CONTENT_API_BASE, '/content/preview', {
      method: 'POST',
      body: JSON.stringify(data),
    });
  }

  async scheduleContent(data: {
    contentId: string;
    startDate: string;
    classId: string;
    deliveryTime?: string;
    intervalDays?: number;
  }) {
    return this.request(CONTENT_API_BASE, '/content/schedule', {
      method: 'POST',
      body: JSON.stringify(data),
    });
  }

  // NEW: Get scheduled content for teacher
  async getScheduledContent(data: {
    teacherId: string;
    classId?: string;
  }) {
    return this.request(CONTENT_API_BASE, '/content/scheduled', {
      method: 'POST',
      body: JSON.stringify(data),
    });
  }

  async getStudentContent(classId: string) {
    return this.request(CONTENT_API_BASE, '/content/student', {
      method: 'POST',
      body: JSON.stringify({ classId }),
    });
  }

  // ===== DOUBT SOLVER API =====
  
  async askDoubt(data: {
    studentId: string;
    subject: string;
    language: string;
    question: string;
  }) {
    return this.request(DOUBT_API_BASE, '/doubts', {
      method: 'POST',
      body: JSON.stringify(data),
    });
  }

  async flagDoubt(data: {
    doubtId: string;
    studentId: string;
    reason: string;
  }) {
    return this.request(DOUBT_API_BASE, '/doubts/flag', {
      method: 'POST',
      body: JSON.stringify(data),
    });
  }

  // NEW: Get student's own doubts history
  async getStudentDoubts(studentId: string) {
    return this.request(DOUBT_API_BASE, `/doubts/student?studentId=${studentId}`, {
      method: 'GET',
    });
  }

  async getFlaggedDoubts(teacherId: string) {
    return this.request(DOUBT_API_BASE, `/doubts/flagged?teacherId=${teacherId}`, {
      method: 'GET',
    });
  }

  async sendNow(data: {
    contentId: string;
    partNumber: string;
    teacherId: string;
  }) {
    return this.request(CONTENT_API_BASE, '/content/send-now', {
      method: 'POST',
      body: JSON.stringify(data),
    });
  }

  async resolveDoubt(data: {
    doubtId: string;
    studentId: string;
    teacherId: string;
    teacherResponse: string;
  }) {
    return this.request(DOUBT_API_BASE, '/doubts/resolve', {
      method: 'POST',
      body: JSON.stringify(data),
    });
  }
}

export const api = new SahayakAPI();

// Backward compatibility exports (temporary - replace these in actual components)
export const authAPI = {
  login: async (email: string, password: string) => {
    // TODO: Implement actual auth
    return Promise.resolve({ token: 'demo', user: { id: 'TCH-001', type: 'teacher' } });
  },
  register: async (data: any) => {
    // TODO: Implement actual registration
    return Promise.resolve({ success: true });
  },
  logout: async () => {
    // TODO: Implement actual logout
    return Promise.resolve({ success: true });
  },
};

export const teacherAPI = {
  getDashboard: () => Promise.reject('Use api.getPreview() instead'),
  getDashboardData: async () => {
    // Demo data until you implement real dashboard API
    return {
      data: {
        totalStudents: 45,
        activeClasses: 3,
        scheduledContent: 5,
        pendingDoubts: 8,
      }
    };
  },
  generateWorksheet: async (data: any) => {
    // TODO: Implement worksheet generation
    return {
      data: {
        id: 'WS-' + Date.now(),
        content: 'Generated worksheet content',
        questions: [],
      }
    };
  },
};

export const studentAPI = {
  getContent: (classId: string) => api.getStudentContent(classId),
  flagDoubt: (data: any) => api.flagDoubt(data),
  askDoubt: (data: any) => api.askDoubt(data),
  getStudentDoubts: (studentId: string) => api.getStudentDoubts(studentId),
  getDashboardData: async () => {
    // Demo data until you implement real dashboard API
    return {
      data: {
        todayContent: null,
        recentContent: [],
        completedLessons: 12,
        questionsSolved: 45,
        avgScore: 78,
      }
    };
  },
  joinClass: async (classId: string) => {
    // TODO: Implement join class
    return Promise.resolve({ success: true, classId });
  },
};