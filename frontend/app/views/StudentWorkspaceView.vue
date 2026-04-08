<script setup>
const { computed, nextTick, onBeforeUnmount, onMounted, reactive, ref, watch } = Vue;
const { useTaskPoller, useWorkspaceShell } = window.AppModules.composables;
const { formatPercent, formatScore } = window.AppModules.utils;
const { studentService } = window.AppModules.services;

const { pollTask } = useTaskPoller();
const { setRoleShell, resetRoleShell } = useWorkspaceShell();

const user = ref(window.AppSession.getUser(["student"]) || {});
const activeView = ref("quiz");
const historyRequested = ref(false);
const dashboard = ref(null);
const historyList = ref([]);
const selectedHistoryDetail = ref(null);
const historyDetailLoading = ref(false);
const historyDetailBody = ref(null);
const questionData = ref(null);
const questionResponseRaw = ref("");
const selectedOption = ref("");
const studentAnswer = ref("");
const questionLoading = ref(false);
const grading = ref(false);
const gradeResult = ref(null);

const setActiveView = (view) => {
    const normalizedView = view || "quiz";
    if (normalizedView !== "history") {
        historyRequested.value = false;
        activeView.value = normalizedView;
        return;
    }
    activeView.value = historyRequested.value ? "history" : "quiz";
};

const openHistoryView = () => {
    historyRequested.value = true;
    activeView.value = "history";
};

watch(activeView, (nextView) => {
    if (nextView === "history" && !historyRequested.value) {
        activeView.value = "quiz";
    }
});

const config = reactive({
    keyword: "",
    type: "choice",
    mode: "adaptive",
    manualDifficulty: "中等",
});

const currentQuestionMeta = reactive({
    keyword: "",
    type: "choice",
    difficulty: "",
    questionId: null,
});

const toast = reactive({
    tone: "info",
    title: "",
    message: "",
});

const streamState = reactive({
    active: false,
    detail: "",
    progress: 0,
});

const viewTabs = [
    { id: "quiz", label: "在线答题" },
    { id: "analysis", label: "学习分析" },
    { id: "history", label: "历史记录" },
];

const typeOptions = [
    { label: "选择", value: "choice" },
    { label: "简答", value: "subjective" },
    { label: "场景", value: "scenario" },
];

const difficultyOptions = ["简单", "中等", "困难"];

const showToast = (message, tone = "info", title = "") => {
    toast.message = message;
    toast.tone = tone;
    toast.title = title;
    window.clearTimeout(showToast.timer);
    showToast.timer = window.setTimeout(() => {
        toast.message = "";
    }, 2600);
};

const summaryCards = computed(() => {
    const overview = dashboard.value?.student_overview || {};
    const adaptive = dashboard.value?.adaptive_state || {};
    return [
        {
            label: "累计练习",
            value: `${overview.total_attempts || 0}`,
            hint: "已完成题目总数",
            accent: "blue",
        },
        {
            label: "平均得分",
            value: `${overview.avg_score || 0}`,
            hint: "当前整体表现",
            accent: "sky",
        },
        {
            label: "通过率",
            value: `${overview.pass_rate || 0}%`,
            hint: "60 分及以上占比",
            accent: "amber",
        },
        {
            label: "下一难度",
            value: adaptive.next_difficulty || "中等",
            hint: adaptive.focus_keyword || "系统会自动微调",
            accent: "rose",
        },
    ];
});

const questionOptions = computed(() => {
    const options = questionData.value?.options;
    if (!options) return [];
    if (Array.isArray(options)) {
        return options.map((value, index) => [String.fromCharCode(65 + index), value]);
    }
    return Object.entries(options);
});

const recommendations = computed(() => dashboard.value?.learning_path?.today_focus || []);
const masteryList = computed(() => dashboard.value?.mastery_by_keyword || []);
const recentHistory = computed(() => historyList.value.slice(0, 12));
const selectedTypeLabel = computed(() => typeOptions.find((item) => item.value === currentQuestionMeta.type)?.label || "选择");
const currentDifficultyLabel = computed(() => currentQuestionMeta.difficulty || (config.mode === "manual" ? config.manualDifficulty : "自适应"));
const isChoiceQuestion = computed(() => currentQuestionMeta.type === "choice");
const hasParsedQuestion = computed(() => Boolean(questionData.value?.question));
const streamPreview = computed(() => buildStreamPreview(questionResponseRaw.value));
const shouldShowTextAnswer = computed(() => hasParsedQuestion.value && !isChoiceQuestion.value);
const choiceOptionMissing = computed(() => hasParsedQuestion.value && isChoiceQuestion.value && !questionOptions.value.length);
const canSubmitAnswer = computed(() => {
    if (!hasParsedQuestion.value || questionLoading.value || grading.value) return false;
    if (isChoiceQuestion.value) return Boolean(selectedOption.value) && !choiceOptionMissing.value;
    return Boolean(studentAnswer.value.trim());
});
const isAnswerCorrect = computed(() => {
    if (!gradeResult.value) return false;
    return Number(gradeResult.value.score || 0) >= (isChoiceQuestion.value ? 100 : 60);
});

const resultSummary = computed(() => {
    if (!gradeResult.value) return "";
    if (isChoiceQuestion.value) {
        return isAnswerCorrect.value
            ? "本题回答正确，系统已按标准答案完成判分。"
            : "本题回答有误，系统已按标准答案完成判分。";
    }
    return gradeResult.value.reason || "评分已完成。";
});

const studentAnswerDisplay = computed(() => {
    if (isChoiceQuestion.value) {
        return selectedOption.value || "未作答";
    }
    return studentAnswer.value.trim() || "未作答";
});

const loadDashboard = async () => {
    const payload = await studentService.loadDashboard();
    dashboard.value = payload.data || null;
};

const loadHistory = async () => {
    const payload = await studentService.loadHistory();
    historyList.value = payload.data || [];
    if (!historyList.value.length) {
        selectedHistoryDetail.value = null;
        return;
    }

    const hasSelected = historyList.value.some((item) => item.id === selectedHistoryDetail.value?.id);
    const preferredId = hasSelected ? selectedHistoryDetail.value.id : historyList.value[0].id;
    await refreshHistoryDetail(preferredId);
};

const refreshHistoryDetail = async (recordId) => {
    historyDetailLoading.value = true;
    try {
        const payload = await studentService.loadHistoryDetail(recordId);
        selectedHistoryDetail.value = payload.data || null;
        await nextTick();
        if (historyDetailBody.value) {
            historyDetailBody.value.scrollTop = 0;
        }
    } finally {
        historyDetailLoading.value = false;
    }
};

const showHistoryDetail = async (recordId) => {
    await refreshHistoryDetail(recordId);
    openHistoryView();
};

const resetQuestionState = () => {
    questionData.value = null;
    questionResponseRaw.value = "";
    selectedOption.value = "";
    studentAnswer.value = "";
    grading.value = false;
    gradeResult.value = null;
    currentQuestionMeta.keyword = "";
    currentQuestionMeta.type = config.type;
    currentQuestionMeta.difficulty = "";
    currentQuestionMeta.questionId = null;
};

const stripCodeFence = (rawText) => String(rawText || "")
    .replace(/^```json\s*/i, "")
    .replace(/^```\s*/i, "")
    .replace(/\s*```$/i, "")
    .trim();

const appendSectionText = (target, line) => {
    if (!line) return target;
    return target ? `${target}\n${line}` : line;
};

function parsePlainTextQuestion(rawText) {
    const lines = stripCodeFence(rawText).split(/\r?\n/);
    const parsed = {
        question: "",
        options: {},
        answer: "",
        analysis: "",
    };

    let currentSection = "question";

    for (const rawLine of lines) {
        const line = rawLine.trim();
        if (!line) continue;

        const questionMatch = line.match(/^题目[：:]\s*(.*)$/);
        const optionMatch = line.match(/^([A-H])[\.．、:：]\s*(.+)$/i);
        const answerMatch = line.match(/^答案[：:]\s*(.*)$/);
        const analysisMatch = line.match(/^解析[：:]\s*(.*)$/);

        if (questionMatch) {
            currentSection = "question";
            parsed.question = appendSectionText(parsed.question, questionMatch[1]);
            continue;
        }

        if (optionMatch) {
            currentSection = "options";
            parsed.options[optionMatch[1].toUpperCase()] = optionMatch[2];
            continue;
        }

        if (answerMatch) {
            currentSection = "answer";
            parsed.answer = appendSectionText(parsed.answer, answerMatch[1]);
            continue;
        }

        if (analysisMatch) {
            currentSection = "analysis";
            parsed.analysis = appendSectionText(parsed.analysis, analysisMatch[1]);
            continue;
        }

        if (currentSection === "question") {
            parsed.question = appendSectionText(parsed.question, line);
        } else if (currentSection === "answer") {
            parsed.answer = appendSectionText(parsed.answer, line);
        } else if (currentSection === "analysis") {
            parsed.analysis = appendSectionText(parsed.analysis, line);
        }
    }

    return {
        question: parsed.question.trim(),
        options: Object.keys(parsed.options).length ? parsed.options : null,
        answer: parsed.answer.trim(),
        analysis: parsed.analysis.trim(),
    };
}

const parseQuestionPayload = (rawText) => {
    const cleaned = stripCodeFence(rawText);

    try {
        const parsed = JSON.parse(cleaned);
        return {
            question: String(parsed.question || "").trim(),
            options: parsed.options || null,
            answer: String(parsed.answer || "").trim(),
            analysis: String(parsed.analysis || "").trim(),
        };
    } catch (error) {
        const parsed = parsePlainTextQuestion(cleaned);
        if (parsed.question) return parsed;
        return {
            question: cleaned,
            options: null,
            answer: "",
            analysis: "",
        };
    }
};

const normalizeQuestionPayload = (payload) => {
    if (!payload) {
        return parseQuestionPayload(questionResponseRaw.value);
    }

    if (typeof payload === "string") {
        return parseQuestionPayload(payload);
    }

    const normalized = {
        question: String(payload.question || "").trim(),
        options: payload.options || null,
        answer: String(payload.answer || "").trim(),
        analysis: String(payload.analysis || "").trim(),
    };

    if (normalized.options || normalized.answer || normalized.analysis) {
        return normalized;
    }

    return parseQuestionPayload(normalized.question || questionResponseRaw.value);
};

const buildStreamPreview = (rawText) => {
    const cleaned = stripCodeFence(rawText);
    if (!cleaned) return "";

    const lines = cleaned.split(/\r?\n/);
    const previewLines = [];

    for (const rawLine of lines) {
        const line = rawLine.trimEnd();
        const trimmed = line.trim();
        if (/^答案[：:]/.test(trimmed) || /^解析[：:]/.test(trimmed)) {
            break;
        }
        previewLines.push(line);
    }

    return previewLines.join("\n").trim();
};

const buildQuestionText = () => {
    if (!questionData.value) return "";
    let content = questionData.value.question || "";
    if (questionOptions.value.length) {
        content += "\n\n选项：\n";
        for (const [key, value] of questionOptions.value) {
            content += `${key}. ${value}\n`;
        }
    }
    return content.trim();
};

const handleStreamBlock = (block) => {
    const dataLine = block.split("\n").find((line) => line.startsWith("data: "));
    if (!dataLine) return;

    const payload = JSON.parse(dataLine.slice(6));

    if (payload.type === "metadata") {
        currentQuestionMeta.difficulty = payload.difficulty || "";
        currentQuestionMeta.questionId = payload.question_id || null;
        streamState.detail = "正在生成题目";
        streamState.progress = 0.42;
        return;
    }

    if (payload.type === "content") {
        questionResponseRaw.value += payload.content || "";
        streamState.detail = "正在流式输出题面";
        streamState.progress = Math.min(0.92, streamState.progress + 0.04);
        return;
    }

    if (payload.type === "done") {
        questionResponseRaw.value = payload.full_content || questionResponseRaw.value;
        questionData.value = normalizeQuestionPayload(payload.parsed_content || questionResponseRaw.value);
        streamState.detail = "题目生成完成";
        streamState.progress = 1;
    }
};

const generateQuestion = async () => {
    if (!config.keyword.trim()) {
        showToast("请先输入想练习的知识点", "danger", "无法生成");
        return;
    }

    resetQuestionState();
    setActiveView("quiz");
    questionLoading.value = true;
    currentQuestionMeta.keyword = config.keyword.trim();
    currentQuestionMeta.type = config.type;
    streamState.active = true;
    streamState.detail = "正在准备题目上下文";
    streamState.progress = 0.2;

    try {
        const response = await studentService.generateQuestionStream({
            keyword: config.keyword.trim(),
            mode: config.mode,
            manual_difficulty: config.manualDifficulty,
            question_type: config.type,
        });

        if (!response.ok || !response.body) {
            throw new Error(`题目生成失败 HTTP ${response.status}`);
        }

        const reader = response.body.getReader();
        const decoder = new TextDecoder("utf-8");
        let buffer = "";

        while (true) {
            const { value, done } = await reader.read();
            if (done) break;

            buffer += decoder.decode(value, { stream: true });
            const blocks = buffer.split("\n\n");
            buffer = blocks.pop() || "";
            blocks.forEach(handleStreamBlock);
        }

        if (buffer.trim()) {
            handleStreamBlock(buffer);
        }

        if (!questionData.value && questionResponseRaw.value.trim()) {
            questionData.value = parseQuestionPayload(questionResponseRaw.value);
        }

        if (!questionData.value?.question) {
            throw new Error("题目内容解析失败，请重新生成");
        }

        showToast("题目已生成，请直接作答", "success", "生成完成");
    } catch (error) {
        questionData.value = null;
        questionResponseRaw.value = "";
        showToast(error.message || "题目生成失败", "danger", "生成失败");
    } finally {
        questionLoading.value = false;
        streamState.active = false;
        streamState.detail = "";
        streamState.progress = 0;
    }
};

const submitAnswer = async () => {
    if (!questionData.value) return;

    if (isChoiceQuestion.value && !questionOptions.value.length) {
        showToast("这道选择题的选项识别失败，请重新生成", "danger", "无法提交");
        return;
    }

    let payloadAnswer = studentAnswer.value.trim();
    let directScore = 0;

    if (isChoiceQuestion.value) {
        if (!selectedOption.value) {
            showToast("请选择一个答案后再提交", "danger", "还未作答");
            return;
        }
        payloadAnswer = selectedOption.value;
        directScore = selectedOption.value === questionData.value.answer ? 100 : 0;
    } else if (!payloadAnswer) {
        showToast("请输入你的作答内容", "danger", "还未作答");
        return;
    }

    grading.value = true;
    setActiveView("quiz");
    try {
        const payload = await studentService.createGradeAnswerTask({
                question: buildQuestionText(),
                standard_answer: questionData.value.answer,
                student_answer: payloadAnswer,
                difficulty: currentQuestionMeta.difficulty || "中等",
                question_type: currentQuestionMeta.type,
                question_id: currentQuestionMeta.questionId,
                direct_score: directScore,
                analysis: questionData.value.analysis || "",
        });

        await pollTask({
            scope: "student",
            taskId: payload.task_id,
            onProgress(task) {
                streamState.active = true;
                streamState.detail = task.detail || "正在评分";
                streamState.progress = task.progress || 0.4;
            },
            async onSuccess(result) {
                streamState.active = false;
                gradeResult.value = result?.data || null;
                setActiveView("quiz");
                await Promise.all([loadDashboard(), loadHistory()]);
                setActiveView("quiz");
                showToast("评分已完成，学习画像已更新", "success", "作答完成");
            },
        });
    } catch (error) {
        showToast(error.message || "评分失败", "danger", "执行失败");
    } finally {
        grading.value = false;
        streamState.active = false;
        streamState.detail = "";
        streamState.progress = 0;
    }
};

const practiceRecommended = async (item) => {
    config.keyword = item.keyword;
    config.mode = "manual";
    config.manualDifficulty = item.target_difficulty || "中等";
    await generateQuestion();
};

onMounted(async () => {
    setActiveView("quiz");
    setRoleShell("student", {
        title: "学生工作台",
        copy: "在线答题、学习分析与历史记录统一收进同一套学生工作栏。",
        navItems: viewTabs.map((item) => ({
            id: item.id,
            label: item.label,
            isActive: () => activeView.value === item.id,
            onClick: () => {
                if (item.id === "history") {
                    openHistoryView();
                    return;
                }
                setActiveView(item.id);
            },
        })),
        controls: {
            config,
            typeOptions,
            difficultyOptions,
            generating: () => questionLoading.value,
            onGenerate: generateQuestion,
        },
        summaryItems: [
            { label: "当前知识点", value: () => currentQuestionMeta.keyword || config.keyword || "未设置" },
            { label: "当前题型", value: () => selectedTypeLabel.value },
            { label: "当前难度", value: () => currentDifficultyLabel.value },
        ],
    });

    try {
        await Promise.all([loadDashboard(), loadHistory()]);
        setActiveView("quiz");
    } catch (error) {
        showToast("学生画像加载失败，请刷新页面", "danger", "初始化失败");
    }
});

onBeforeUnmount(() => {
    resetRoleShell("student");
});
</script>

<template>
    <div class="page-shell student-quiz-shell">
        <GlassPanel class="student-quiz-header">
            <div class="student-quiz-header__title">
                <h2>在线答题系统</h2>
                <p>聚焦当前题目、即时作答与提交后的结果反馈。</p>
            </div>

            <div class="student-quiz-header__user student-quiz-header__user--compact">
                <span>当前学生</span>
                <strong>{{ user.username || "student" }}</strong>
            </div>
        </GlassPanel>

        <section class="student-quiz-layout student-quiz-layout--single">
            <div class="student-quiz-content student-quiz-content--full">
                <section v-if="activeView === 'quiz'" class="student-view-stack">
                    <GlassPanel class="student-quiz-card">
                        <div class="student-quiz-card__top">
                            <div class="student-pill-row">
                                <span class="student-tag">{{ selectedTypeLabel }}</span>
                                <span class="student-tag student-tag--muted">难度：{{ currentDifficultyLabel }}</span>
                            </div>
                            <span class="student-keyword-chip">{{ currentQuestionMeta.keyword || config.keyword || "等待题目生成" }}</span>
                        </div>

                        <div v-if="streamState.active" class="task-inline task-inline--student">
                            <div>
                                <strong>{{ streamState.detail }}</strong>
                                <span>系统正在准备当前题目</span>
                            </div>
                            <div class="task-inline__bar">
                                <span :style="{ width: `${Math.round(streamState.progress * 100)}%` }"></span>
                            </div>
                        </div>

                        <div class="student-question-body">
                            <div v-if="questionLoading && streamPreview" class="student-loading-card">
                                <div class="student-loading-card__head">
                                    <span>题面预览</span>
                                    <strong>{{ currentQuestionMeta.keyword || "当前知识点" }}</strong>
                                </div>
                                <pre class="question-stream-preview">{{ streamPreview }}</pre>
                            </div>

                            <div v-else-if="questionLoading" class="student-loading-card">
                                <LoadingShimmer :lines="6" />
                            </div>

                            <div v-else-if="hasParsedQuestion" class="student-question-card">
                                <div class="student-question-card__meta">
                                    <span>{{ selectedTypeLabel }}</span>
                                    <strong>{{ currentQuestionMeta.keyword }}</strong>
                                </div>

                                <div class="student-question-card__stem">
                                    <MarkdownCard :content="questionData.question" />
                                </div>

                                <div v-if="questionOptions.length" class="student-option-list">
                                    <button
                                        v-for="[optionKey, optionText] in questionOptions"
                                        :key="optionKey"
                                        type="button"
                                        :class="['student-option-card', selectedOption === optionKey ? 'is-selected' : '']"
                                        @click="selectedOption = optionKey"
                                    >
                                        <span class="student-option-card__key">{{ optionKey }}</span>
                                        <span class="student-option-card__text">{{ optionText }}</span>
                                    </button>
                                </div>

                                <div v-else-if="choiceOptionMissing" class="inline-banner tone-danger">
                                    这道选择题的选项没有正确识别，请重新生成题目。
                                </div>

                                <textarea
                                    v-if="shouldShowTextAnswer"
                                    v-model="studentAnswer"
                                    rows="7"
                                    class="answer-box student-answer-box"
                                    placeholder="请输入你的答案"
                                />

                                <div class="student-answer-actions">
                                    <span>提交前不会展示标准答案与解析</span>
                                    <button class="primary-button" type="button" :disabled="!canSubmitAnswer" @click="submitAnswer">
                                        {{ grading ? "评分中..." : "提交答案" }}
                                    </button>
                                </div>
                            </div>

                            <div v-else class="empty-hint student-empty-state">
                                先在左侧输入知识点并点击“生成题目”，右侧会显示当前题目。
                            </div>
                        </div>
                    </GlassPanel>

                    <GlassPanel v-if="gradeResult" :class="['student-feedback-panel', isAnswerCorrect ? 'is-correct' : 'is-incorrect']">
                        <div class="student-feedback-panel__head">
                            <div>
                                <span class="student-feedback-badge">{{ isAnswerCorrect ? "回答正确" : "回答错误" }}</span>
                                <h3>{{ isAnswerCorrect ? "本题已通过" : "本题需要复盘" }}</h3>
                            </div>
                            <span class="score-chip" :class="isAnswerCorrect ? 'is-good' : 'is-danger'">
                                {{ formatScore(gradeResult.score) }}
                            </span>
                        </div>

                        <div class="student-feedback-grid">
                            <article>
                                <strong>评分说明</strong>
                                <p>{{ resultSummary }}</p>
                            </article>
                            <article>
                                <strong>你的答案</strong>
                                <p>{{ studentAnswerDisplay }}</p>
                            </article>
                            <article v-if="questionData?.answer">
                                <strong>参考答案</strong>
                                <p>{{ questionData.answer }}</p>
                            </article>
                            <article v-if="gradeResult.mastery_update">
                                <strong>掌握度更新</strong>
                                <p>{{ gradeResult.mastery_update.keyword }} · {{ gradeResult.mastery_update.mastery_score }} 分 · {{ gradeResult.mastery_update.level }}</p>
                            </article>
                            <article v-if="gradeResult.feedback_dimensions">
                                <strong>结构化反馈</strong>
                                <p>
                                    准确性 {{ gradeResult.feedback_dimensions.accuracy }} /
                                    完整性 {{ gradeResult.feedback_dimensions.completeness }} /
                                    表达 {{ gradeResult.feedback_dimensions.expression }}
                                </p>
                            </article>
                            <article v-if="gradeResult.suggestion && !isChoiceQuestion">
                                <strong>改进建议</strong>
                                <p>{{ gradeResult.suggestion }}</p>
                            </article>
                        </div>

                        <div v-if="questionData?.analysis" class="student-analysis-card">
                            <div class="student-section-heading">
                                <strong>解析</strong>
                                <span>{{ currentQuestionMeta.keyword }}</span>
                            </div>
                            <MarkdownCard :content="questionData.analysis" />
                        </div>
                    </GlassPanel>
                </section>

                <section v-else-if="activeView === 'analysis'" class="student-view-stack">
                    <section class="metrics-grid student-metrics">
                        <MetricCard
                            v-for="card in summaryCards"
                            :key="card.label"
                            :label="card.label"
                            :value="card.value"
                            :hint="card.hint"
                            :accent="card.accent"
                        />
                    </section>

                    <div class="student-analysis-grid">
                        <GlassPanel class="student-list-panel">
                            <div class="student-section-heading">
                                <strong>今日建议</strong>
                                <span>{{ dashboard?.learning_path?.expected_difficulty || "自适应" }}</span>
                            </div>

                            <div class="student-list-stack">
                                <button
                                    v-for="item in recommendations"
                                    :key="item.keyword"
                                    type="button"
                                    class="student-list-card"
                                    @click="practiceRecommended(item)"
                                >
                                    <div>
                                        <strong>{{ item.keyword }}</strong>
                                        <span>{{ item.reason || item.action }}</span>
                                    </div>
                                    <em>{{ item.target_difficulty || "中等" }}</em>
                                </button>
                                <div v-if="!recommendations.length" class="empty-hint">当前还没有学习建议。</div>
                            </div>
                        </GlassPanel>

                        <GlassPanel class="student-list-panel">
                            <div class="student-section-heading">
                                <strong>知识点掌握度</strong>
                                <span>{{ masteryList.length }} 个知识点</span>
                            </div>

                            <div class="mastery-bars">
                                <div
                                    v-for="item in masteryList.slice(0, 8)"
                                    :key="item.keyword"
                                    class="mastery-bars__item student-mastery-item"
                                >
                                    <div class="mastery-bars__top">
                                        <strong>{{ item.keyword }}</strong>
                                        <span>{{ item.mastery_score }} 分</span>
                                    </div>
                                    <div class="mastery-bars__track">
                                        <span :style="{ width: `${item.mastery_score}%` }"></span>
                                    </div>
                                    <small>通过率 {{ formatPercent(item.pass_rate) }} · {{ item.level }}</small>
                                </div>
                            </div>
                        </GlassPanel>
                    </div>
                </section>

                <section v-else-if="activeView === 'history'" class="student-view-stack">
                    <section class="student-history-layout">
                        <GlassPanel class="student-list-panel">
                            <div class="student-section-heading">
                                <strong>历史记录</strong>
                                <span>最近 {{ historyList.length }} 条</span>
                            </div>

                            <div class="student-history-scroll student-history-scroll--list">
                                <div class="student-history-stack">
                                    <button
                                        v-for="item in recentHistory"
                                        :key="item.id"
                                        type="button"
                                        :class="['history-record-card', selectedHistoryDetail?.id === item.id ? 'is-active' : '']"
                                        @click="showHistoryDetail(item.id)"
                                    >
                                        <div class="history-record-card__head">
                                            <div>
                                                <strong>{{ item.keyword || "未标注知识点" }}</strong>
                                                <span>{{ item.time || "暂无时间" }}</span>
                                            </div>
                                            <span class="score-chip" :class="Number(item.score || 0) >= 60 ? 'is-good' : 'is-danger'">
                                                {{ formatScore(item.score) }}
                                            </span>
                                        </div>

                                        <p>{{ item.question || item.question_preview || "该记录暂无题干摘要。" }}</p>
                                    </button>

                                    <div v-if="!recentHistory.length" class="empty-hint">
                                        当前还没有历史作答记录。
                                    </div>
                                </div>
                            </div>
                        </GlassPanel>

                        <GlassPanel class="student-history-detail-panel">
                            <div class="panel-headline">
                                <div>
                                    <span class="eyebrow">History Detail</span>
                                    <h3>{{ selectedHistoryDetail?.keyword || "题目详情" }}</h3>
                                </div>
                                <span class="headline-note">
                                    {{ selectedHistoryDetail ? `${selectedHistoryDetail.time} · 难度 ${selectedHistoryDetail.difficulty || "未标注"}` : "点击左侧历史记录查看题目正文与作答详情" }}
                                </span>
                            </div>

                            <div ref="historyDetailBody" class="student-history-scroll student-history-scroll--detail">
                                <div v-if="historyDetailLoading" class="loading-shimmer">
                                    <span class="loading-shimmer__line"></span>
                                    <span class="loading-shimmer__line"></span>
                                    <span class="loading-shimmer__line"></span>
                                </div>

                                <div v-else-if="selectedHistoryDetail" class="student-history-detail-stack">
                                    <div class="record-detail-grid">
                                        <article class="is-wide">
                                            <span>题目内容</span>
                                            <div class="student-history-detail__question">
                                                <MarkdownCard :content="selectedHistoryDetail.question || '暂无题目内容'" />
                                            </div>
                                        </article>
                                        <article>
                                            <span>知识点</span>
                                            <strong>{{ selectedHistoryDetail.keyword || "未标注" }}</strong>
                                        </article>
                                        <article>
                                            <span>得分</span>
                                            <strong>{{ formatScore(selectedHistoryDetail.score) }}</strong>
                                        </article>
                                        <article class="is-wide">
                                            <span>我的作答</span>
                                            <p>{{ selectedHistoryDetail.student_answer || "暂无作答内容" }}</p>
                                        </article>
                                        <article class="is-wide">
                                            <span>AI 评语</span>
                                            <p>{{ selectedHistoryDetail.comment || "暂无评语" }}</p>
                                        </article>
                                    </div>
                                </div>

                                <div v-else class="empty-hint">
                                    点击左侧任意一条历史记录，即可查看这道题的完整内容和当时的作答情况。
                                </div>
                            </div>
                        </GlassPanel>
                    </section>
                </section>

                <section v-else class="student-view-stack">
                    <GlassPanel class="student-quiz-card">
                        <div class="empty-hint student-empty-state">
                            当前页面状态异常，已回退到答题视图。请重新生成题目或继续作答。
                        </div>
                    </GlassPanel>
                </section>
            </div>
        </section>

        <StatusToast :tone="toast.tone" :title="toast.title" :message="toast.message" />
    </div>
</template>
