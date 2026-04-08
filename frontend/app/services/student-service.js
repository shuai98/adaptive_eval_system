export const studentService = {
    async loadDashboard() {
        return window.AppApi.requestJson("/student/learning_dashboard");
    },

    async loadHistory() {
        return window.AppApi.requestJson("/student/history");
    },

    async loadHistoryDetail(recordId) {
        return window.AppApi.requestJson(`/student/history/${recordId}`);
    },

    async generateQuestionStream(payload) {
        return window.AppApi.request("/student/generate_question_stream", {
            method: "POST",
            body: JSON.stringify(payload),
        });
    },

    async createGradeAnswerTask(payload) {
        return window.AppApi.requestJson("/student/grade_answer_task", {
            method: "POST",
            body: JSON.stringify(payload),
        });
    },
};
