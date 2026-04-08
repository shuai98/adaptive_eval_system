<script setup>
const { computed, nextTick, onBeforeUnmount, onMounted, reactive, ref } = Vue;
const { formatPercent, formatScore } = window.AppModules.utils;
const { useTaskPoller, useWorkspaceShell } = window.AppModules.composables;

const { setRoleShell, resetRoleShell } = useWorkspaceShell();
const { pollTask } = useTaskPoller();

const user = ref(window.AppSession.getUser(["teacher", "admin"]) || {});
const currentPanel = ref("overview");
const teacherDetailBody = ref(null);
const docFileInput = ref(null);
const selectedDocFile = ref(null);

const docs = ref([]);
const records = ref([]);
const classInsights = ref(null);
const studentProfiles = ref([]);
const selectedStudentId = ref(null);
const selectedProfile = ref(null);
const selectedRecord = ref(null);
const docTaskStates = reactive({});
const uploadRules = reactive({
    maxUploadSizeMb: 25,
    allowedExtensions: [".pdf", ".txt"],
});

const loading = reactive({
    docs: false,
    upload: false,
    dashboard: false,
    profile: false,
    record: false,
});

const toast = reactive({
    tone: "info",
    title: "",
    message: "",
});

const panelTabs = [
    { id: "overview", label: "教学总览", title: "班级教学总览", copy: "先看班级整体状态，再决定今天优先处理哪一块。" },
    { id: "docs", label: "资料库", title: "我的资料库", copy: "单独查看教师资料，不和学生数据混在一起。" },
    { id: "profiles", label: "学生画像", title: "学生画像工作台", copy: "左侧选学生，右侧连续查看画像和掌握度。" },
    { id: "records", label: "历史记录", title: "历史记录详情", copy: "左侧看记录列表，右侧专门看具体题目情况。" },
];

const currentPanelMeta = computed(() => panelTabs.find((item) => item.id === currentPanel.value) || panelTabs[0]);
const classOverview = computed(() => classInsights.value?.class_overview || {});
const weakKeywords = computed(() => classInsights.value?.weak_keywords || []);
const selectedStudentSnapshot = computed(() => (
    studentProfiles.value.find((item) => item.student_id === selectedStudentId.value) || null
));

const summaryCards = computed(() => ([
    { label: "学生人数", value: `${classOverview.value.student_count || studentProfiles.value.length || 0}`, hint: "当前纳入分析的学生", accent: "blue" },
    { label: "答题总量", value: `${classOverview.value.total_attempts || records.value.length || 0}`, hint: "系统最近统计结果", accent: "sky" },
    { label: "平均得分", value: `${classOverview.value.avg_score || 0}`, hint: "班级整体表现", accent: "amber" },
    { label: "风险知识点", value: `${weakKeywords.value.length}`, hint: "建议优先回看的薄弱项", accent: "rose" },
]));

const masteryChartItems = computed(() => (
    (selectedProfile.value?.student_keyword_mastery || []).slice(0, 6).map((item) => ({
        label: item.keyword,
        value: Number(item.mastery_score || 0),
        level: item.level || "",
    }))
));

const showRadarChart = computed(() => masteryChartItems.value.length >= 3);
const showMasteryFallback = computed(() => masteryChartItems.value.length > 0 && masteryChartItems.value.length < 3);
const allowedExtensionsText = computed(() => (
    uploadRules.allowedExtensions.map((item) => item.replace(".", "").toUpperCase()).join(" / ")
));

function showToast(message, tone = "info", title = "") {
    toast.message = message;
    toast.tone = tone;
    toast.title = title;
    window.clearTimeout(showToast.timer);
    showToast.timer = window.setTimeout(() => {
        toast.message = "";
    }, 2600);
}

function normalizeRecord(item = {}) {
    return {
        ...item,
        student: item.student || item.username || item.student_name || "学生",
        keyword: item.keyword || item.knowledge_point || "",
        difficulty: item.difficulty || item.level || "",
        question: item.question || item.question_text || item.prompt || "",
        student_answer: item.student_answer || item.answer || item.user_answer || "",
        comment: item.comment || item.feedback || item.ai_comment || "",
    };
}

function setDocTaskState(docId, patch = {}) {
    if (!docId) return;
    docTaskStates[docId] = {
        ...(docTaskStates[docId] || {}),
        ...patch,
    };
}

function clearDocTaskState(docId) {
    if (!docId || !docTaskStates[docId]) return;
    delete docTaskStates[docId];
}

function formatFileSize(size = 0) {
    const numericSize = Number(size || 0);
    if (!Number.isFinite(numericSize) || numericSize <= 0) {
        return "0 B";
    }
    const units = ["B", "KB", "MB", "GB"];
    let value = numericSize;
    let unitIndex = 0;
    while (value >= 1024 && unitIndex < units.length - 1) {
        value /= 1024;
        unitIndex += 1;
    }
    const displayValue = value >= 10 || unitIndex === 0 ? Math.round(value) : value.toFixed(1);
    return `${displayValue} ${units[unitIndex]}`;
}

function resolveDocStatus(doc = {}) {
    return docTaskStates[doc.id]?.uiStatus || doc.status || "uploaded";
}

function resolveDocStatusLabel(doc = {}) {
    return {
        indexing: "解析中",
        indexed: "已可用",
        failed: "失败",
        uploaded: "已上传",
    }[resolveDocStatus(doc)] || (doc.status || "uploaded");
}

function formatDocMeta(doc = {}) {
    const base = `${doc.time} · ${formatFileSize(doc.size || 0)} · 版本 ${doc.version || 1}`;
    const taskState = docTaskStates[doc.id];
    if (taskState?.detail && ["indexing", "failed"].includes(taskState.uiStatus || "")) {
        return `${base} · ${taskState.detail}`;
    }
    if (doc.indexed_at) {
        return `${base} · 可用时间 ${doc.indexed_at}`;
    }
    return base;
}

function getSelectedFileExtension(fileName = "") {
    const parts = String(fileName).toLowerCase().split(".");
    return parts.length > 1 ? `.${parts.pop()}` : "";
}

function validateDocFile(file) {
    if (!file) {
        return "请先选择要上传的资料文件";
    }
    const extension = getSelectedFileExtension(file.name);
    if (uploadRules.allowedExtensions.length && !uploadRules.allowedExtensions.includes(extension)) {
        return `当前仅支持 ${allowedExtensionsText.value} 文件`;
    }
    const maxBytes = Number(uploadRules.maxUploadSizeMb || 0) * 1024 * 1024;
    if (maxBytes > 0 && Number(file.size || 0) > maxBytes) {
        return `文件超过 ${uploadRules.maxUploadSizeMb}MB 限制`;
    }
    return "";
}

function triggerDocPicker() {
    docFileInput.value?.click();
}

function clearSelectedDoc() {
    selectedDocFile.value = null;
    if (docFileInput.value) {
        docFileInput.value.value = "";
    }
}

function handleDocSelection(event) {
    const [file] = event?.target?.files || [];
    const validationMessage = validateDocFile(file);
    if (validationMessage) {
        clearSelectedDoc();
        showToast(validationMessage, "danger", "文件不符合要求");
        return;
    }
    selectedDocFile.value = file || null;
}

async function resetDetailScroll() {
    await nextTick();
    if (teacherDetailBody.value) {
        teacherDetailBody.value.scrollTop = 0;
    }
}

async function loadDocs() {
    loading.docs = true;
    try {
        const payload = await window.AppApi.requestJson("/teacher/my_docs");
        uploadRules.maxUploadSizeMb = Number(payload.meta?.max_upload_size_mb || uploadRules.maxUploadSizeMb || 25);
        uploadRules.allowedExtensions = Array.isArray(payload.meta?.allowed_extensions) && payload.meta.allowed_extensions.length
            ? payload.meta.allowed_extensions
            : uploadRules.allowedExtensions;
        docs.value = payload.data || [];
        Object.keys(docTaskStates).forEach((rawId) => {
            const docId = Number(rawId);
            const currentDoc = docs.value.find((item) => item.id === docId);
            if (!currentDoc) {
                clearDocTaskState(docId);
                return;
            }
            if (currentDoc.status === "indexed") {
                clearDocTaskState(docId);
                return;
            }
            if (currentDoc.status === "failed") {
                setDocTaskState(docId, { uiStatus: "failed" });
            }
        });
    } finally {
        loading.docs = false;
    }
}

async function loadDashboard() {
    loading.dashboard = true;
    try {
        const [dashboardPayload, insightsPayload, profilesPayload] = await Promise.all([
            window.AppApi.requestJson("/teacher/dashboard_stats"),
            window.AppApi.requestJson("/teacher/class_insights"),
            window.AppApi.requestJson("/teacher/student_profiles"),
        ]);
        records.value = (dashboardPayload.data || []).map(normalizeRecord);
        classInsights.value = insightsPayload.data || null;
        studentProfiles.value = profilesPayload.data || [];
    } finally {
        loading.dashboard = false;
    }
}

async function uploadSelectedDoc() {
    if (!selectedDocFile.value || loading.upload) return;
    const validationMessage = validateDocFile(selectedDocFile.value);
    if (validationMessage) {
        showToast(validationMessage, "danger", "文件不符合要求");
        return;
    }

    const formData = new FormData();
    formData.append("file", selectedDocFile.value);

    loading.upload = true;
    try {
        const payload = await window.AppApi.requestJson("/teacher/upload_doc", {
            method: "POST",
            body: formData,
        });
        clearSelectedDoc();
        await loadDocs();
        if (payload.data?.id) {
            setDocTaskState(payload.data.id, {
                taskId: payload.task_id,
                uiStatus: "indexing",
                detail: "后台任务已启动",
            });
        }
        if (payload.task_id && payload.data?.id) {
            void startDocTaskPolling(payload.data.id, payload.task_id);
        }
        showToast(payload.message || "资料上传成功，正在后台解析入库", "success", "上传成功");
    } catch (error) {
        showToast(error.message || "资料上传失败", "danger", "上传失败");
    } finally {
        loading.upload = false;
    }
}

async function startDocTaskPolling(docId, taskId) {
    try {
        await pollTask({
            scope: "teacher",
            taskId,
            interval: 1200,
            onProgress(task) {
                setDocTaskState(docId, {
                    taskId,
                    uiStatus: ["failed", "cancelled", "timeout"].includes(task.status) ? "failed" : "indexing",
                    detail: task.detail || "后台解析中",
                });
            },
            async onSuccess(result) {
                setDocTaskState(docId, {
                    taskId,
                    uiStatus: "indexed",
                    detail: result?.message || "资料已可用",
                });
                await loadDocs();
                clearDocTaskState(docId);
                showToast("资料已完成解析并可用于检索与出题", "success", "已可用");
            },
        });
    } catch (error) {
        setDocTaskState(docId, {
            taskId,
            uiStatus: "failed",
            detail: error.message || "后台索引失败",
        });
        await loadDocs();
        showToast(error.message || "资料索引失败", "danger", "索引失败");
    }
}

async function openStudentProfile(studentId, options = {}) {
    if (!studentId) return;
    if (options.switchPanel !== false) {
        currentPanel.value = "profiles";
    }
    loading.profile = true;
    selectedStudentId.value = studentId;
    try {
        const payload = await window.AppApi.requestJson(`/teacher/student_profile/${studentId}`);
        selectedProfile.value = payload.data || null;
        await resetDetailScroll();
    } catch (error) {
        showToast(error.message || "学生画像加载失败", "danger", "加载失败");
    } finally {
        loading.profile = false;
    }
}

async function openRecordDetail(recordId) {
    if (!recordId) return;
    currentPanel.value = "records";
    loading.record = true;
    try {
        const payload = await window.AppApi.requestJson(`/teacher/record_detail/${recordId}`);
        selectedRecord.value = normalizeRecord(payload.data || {});
        if (selectedRecord.value?.student_id && selectedRecord.value.student_id !== selectedStudentId.value) {
            await openStudentProfile(selectedRecord.value.student_id, { switchPanel: false });
        } else {
            await resetDetailScroll();
        }
    } catch (error) {
        showToast(error.message || "答题详情加载失败", "danger", "加载失败");
    } finally {
        loading.record = false;
    }
}

function selectPanel(panelId) {
    currentPanel.value = panelId;
}

onMounted(async () => {
    setRoleShell("teacher", {
        title: "教师控制台",
        copy: "左侧保留功能切换，中间只展示当前选择的工作面板。",
        navItems: panelTabs.map((item) => ({
            id: item.id,
            label: item.label,
            meta: () => item.title,
            isActive: () => currentPanel.value === item.id,
            onClick: () => selectPanel(item.id),
        })),
        summaryItems: [
            { label: "当前面板", value: () => currentPanelMeta.value.title },
            { label: "资料数量", value: () => `${docs.value.length}` },
            { label: "学生数量", value: () => `${studentProfiles.value.length}` },
        ],
    });

    try {
        await Promise.all([loadDocs(), loadDashboard()]);
        if (studentProfiles.value.length) {
            await openStudentProfile(studentProfiles.value[0].student_id, { switchPanel: false });
        }
        if (records.value.length) {
            await openRecordDetail(records.value[0].id);
            currentPanel.value = "overview";
        }
    } catch (error) {
        showToast(error.message || "教师控制台初始化失败", "danger", "初始化失败");
    }
});

onBeforeUnmount(() => {
    resetRoleShell("teacher");
});
</script>

<template>
    <div class="page-shell teacher-console-shell">
        <header class="page-hero page-hero--light">
            <div>
                <p class="eyebrow">Teacher Console</p>
                <h2>{{ currentPanelMeta.title }}</h2>
                <p>{{ currentPanelMeta.copy }}</p>
            </div>
            <span class="headline-note">当前账号 {{ user.username || "teacher" }}</span>
        </header>

        <section v-if="currentPanel === 'overview'" class="teacher-panel-stack">
            <section class="metrics-grid teacher-metrics">
                <MetricCard
                    v-for="card in summaryCards"
                    :key="card.label"
                    :label="card.label"
                    :value="card.value"
                    :hint="card.hint"
                    :accent="card.accent"
                />
            </section>

            <section class="teacher-overview-grid">
                <GlassPanel class="teacher-panel-stack">
                    <div class="panel-headline">
                        <div>
                            <span class="eyebrow">Weak Areas</span>
                            <h3>班级薄弱知识点</h3>
                        </div>
                        <span class="headline-note">来自 `/teacher/class_insights`</span>
                    </div>

                    <div class="student-list-stack">
                        <article
                            v-for="item in weakKeywords.slice(0, 8)"
                            :key="item.keyword"
                            class="student-list-card"
                        >
                            <div>
                                <strong>{{ item.keyword }}</strong>
                                <span>平均分 {{ formatScore(item.avg_score || 0) }}</span>
                            </div>
                            <em>{{ item.level || "需关注" }}</em>
                        </article>
                        <div v-if="!weakKeywords.length" class="empty-hint">当前没有薄弱知识点数据。</div>
                    </div>
                </GlassPanel>

                <GlassPanel class="teacher-quick-panel">
                    <div class="panel-headline">
                        <div>
                            <span class="eyebrow">Workspace</span>
                            <h3>进入工作区</h3>
                        </div>
                    </div>
                    <div class="teacher-action-list">
                        <button class="teacher-action-card" type="button" @click="selectPanel('docs')">
                            <strong>上传与管理资料</strong>
                            <span>进入资料库后可选择 PDF 或 TXT 上传，并查看版本记录。</span>
                        </button>
                        <button class="teacher-action-card" type="button" @click="selectPanel('profiles')">
                            <strong>查看学生画像</strong>
                            <span>左侧选学生，右侧连续查看能力概况和掌握度。</span>
                        </button>
                        <button class="teacher-action-card" type="button" @click="selectPanel('records')">
                            <strong>查看历史记录</strong>
                            <span>左边记录列表，右边专门看题目详情与作答。</span>
                        </button>
                    </div>
                </GlassPanel>
            </section>
        </section>

        <section v-else-if="currentPanel === 'docs'" class="teacher-panel-stack">
            <GlassPanel class="teacher-panel-stack">
                <div class="panel-headline">
                    <div>
                        <span class="eyebrow">Documents</span>
                        <h3>我的资料库</h3>
                    </div>
                    <span class="headline-note">{{ loading.upload ? "上传中..." : loading.docs ? "加载中..." : `${docs.length} 份资料` }}</span>
                </div>

                <div class="teacher-doc-upload">
                    <input
                        ref="docFileInput"
                        class="hidden-input"
                        type="file"
                        accept=".pdf,.txt"
                        @change="handleDocSelection"
                    >

                    <button class="teacher-upload-dropzone" type="button" @click="triggerDocPicker">
                        <div>
                            <strong>{{ selectedDocFile ? selectedDocFile.name : "选择要上传的资料文件" }}</strong>
                            <span>
                                {{ selectedDocFile
                                    ? `文件大小 ${formatFileSize(selectedDocFile.size)} · 支持 ${allowedExtensionsText} · 最大 ${uploadRules.maxUploadSizeMb}MB`
                                    : `支持 ${allowedExtensionsText}，单个文件最大 ${uploadRules.maxUploadSizeMb}MB，上传成功后会自动进入后台解析。` }}
                            </span>
                        </div>
                        <em>{{ selectedDocFile ? "已选中文件" : "点击选择" }}</em>
                    </button>

                    <div class="teacher-inline-actions">
                        <button class="secondary-button" type="button" @click="triggerDocPicker">选择文件</button>
                        <button
                            v-if="selectedDocFile"
                            class="ghost-button"
                            type="button"
                            :disabled="loading.upload"
                            @click="clearSelectedDoc"
                        >
                            清空
                        </button>
                        <button
                            class="primary-button"
                            type="button"
                            :disabled="!selectedDocFile || loading.upload"
                            @click="uploadSelectedDoc"
                        >
                            {{ loading.upload ? "上传中..." : "上传资料" }}
                        </button>
                    </div>

                    <div class="teacher-subtle-banner">
                        重新上传同名文件会自动累加版本号，方便教师持续迭代讲义与题库资料。
                    </div>
                </div>

                <div class="student-list-stack">
                    <article v-for="doc in docs" :key="doc.id" class="student-list-card">
                        <div>
                            <strong>{{ doc.name }}</strong>
                            <span>{{ formatDocMeta(doc) }}</span>
                        </div>
                        <em class="teacher-doc-status">{{ resolveDocStatusLabel(doc) }}</em>
                    </article>
                    <div v-if="!docs.length && !loading.docs" class="empty-hint">还没有可展示的资料。</div>
                </div>
            </GlassPanel>
        </section>

        <section v-else-if="currentPanel === 'profiles'" class="teacher-workspace">
            <GlassPanel class="teacher-workspace__list">
                <div class="panel-headline">
                    <div>
                        <span class="eyebrow">Students</span>
                        <h3>学生画像列表</h3>
                    </div>
                    <span class="headline-note">{{ loading.profile ? "载入中..." : `${studentProfiles.length} 位学生` }}</span>
                </div>

                <div class="teacher-workspace__body">
                    <div class="student-roster teacher-scroll-body">
                        <button
                            v-for="item in studentProfiles"
                            :key="item.student_id || item.id || item.username"
                            type="button"
                            :class="['student-roster__item', selectedStudentId === (item.student_id || item.id) ? 'is-active' : '']"
                            @click="openStudentProfile(item.student_id || item.id)"
                        >
                            <div>
                                <strong>{{ item.username || item.student_name || `学生 ${item.student_id || item.id}` }}</strong>
                                <span>{{ item.weakest_keyword || "暂无明显薄弱项" }}</span>
                            </div>
                            <em>{{ formatScore(item.avg_score || item.student_overview?.avg_score || 0) }} 分</em>
                        </button>
                    </div>
                </div>
            </GlassPanel>

            <GlassPanel class="teacher-workspace__detail">
                <div class="panel-headline">
                    <div>
                        <span class="eyebrow">Profile Detail</span>
                        <h3>{{ selectedProfile?.student_overview?.username || selectedStudentSnapshot?.username || "选择一名学生" }}</h3>
                    </div>
                    <span class="headline-note">
                        {{ selectedProfile ? `平均分 ${formatScore(selectedProfile.student_overview?.avg_score || 0)} · 通过率 ${formatPercent(selectedProfile.student_overview?.pass_rate || 0)}` : "点击左侧学生查看画像详情" }}
                    </span>
                </div>

                <div ref="teacherDetailBody" class="teacher-workspace__body teacher-scroll-body">
                    <div v-if="selectedProfile" class="drawer-profile teacher-detail-stack">
                        <div class="drawer-profile__summary">
                            <article>
                                <span>当前建议</span>
                                <strong>{{ selectedProfile.adaptive_state?.next_difficulty || "中等" }}</strong>
                            </article>
                            <article>
                                <span>最薄弱知识点</span>
                                <strong>{{ selectedProfile.student_overview?.weakest_keyword || "暂无" }}</strong>
                            </article>
                            <article>
                                <span>最强知识点</span>
                                <strong>{{ selectedProfile.student_overview?.strongest_keyword || "暂无" }}</strong>
                            </article>
                        </div>

                        <section class="teacher-chart-section">
                            <div class="teacher-section-heading">
                                <div>
                                    <h4>知识点能力概览</h4>
                                    <p>维度少于 3 个时自动切换成对比条，避免雷达图只剩一条线。</p>
                                </div>
                            </div>

                            <RadarChart v-if="showRadarChart" :items="masteryChartItems" />

                            <div v-else-if="showMasteryFallback" class="mastery-bars">
                                <div class="teacher-inline-note">
                                    当前仅积累 {{ masteryChartItems.length }} 个知识点，满 3 个后展示雷达图。
                                </div>
                                <div
                                    v-for="item in masteryChartItems"
                                    :key="item.label"
                                    class="mastery-bars__item teacher-mastery-preview"
                                >
                                    <div class="mastery-bars__top">
                                        <strong>{{ item.label }}</strong>
                                        <span>{{ item.level || "待评估" }}</span>
                                        <em>{{ item.value }}</em>
                                    </div>
                                    <div class="mastery-bars__track">
                                        <span :style="{ width: `${Math.round(item.value)}%` }"></span>
                                    </div>
                                </div>
                            </div>

                            <div v-else class="empty-hint">当前还没有足够的知识点掌握度数据。</div>
                        </section>

                        <div class="drawer-section">
                            <h4>知识点掌握度</h4>
                            <div class="mastery-list">
                                <div
                                    v-for="item in selectedProfile.student_keyword_mastery || []"
                                    :key="item.keyword"
                                    class="mastery-list__item"
                                >
                                    <div>
                                        <strong>{{ item.keyword }}</strong>
                                        <span>{{ item.level }}</span>
                                    </div>
                                    <em>{{ item.mastery_score }}</em>
                                </div>
                            </div>
                        </div>

                        <div class="drawer-section">
                            <h4>教师干预建议</h4>
                            <ul class="drawer-bullet-list">
                                <li v-for="item in selectedProfile.intervention_suggestions || []" :key="item">{{ item }}</li>
                            </ul>
                        </div>
                    </div>

                    <div v-else class="empty-hint">先从左侧选择一名学生。</div>
                </div>
            </GlassPanel>
        </section>

        <section v-else class="teacher-history-layout">
            <GlassPanel class="teacher-workspace__list teacher-history-panel">
                <div class="student-section-heading">
                    <strong>历史记录</strong>
                    <span>{{ loading.dashboard ? "加载中..." : `最近 ${records.length} 条` }}</span>
                </div>

                <div class="teacher-scroll-body teacher-record-stack">
                    <button
                        v-for="item in records"
                        :key="item.id"
                        type="button"
                        :class="['history-record-card', selectedRecord?.id === item.id ? 'is-active' : '']"
                        @click="openRecordDetail(item.id)"
                    >
                        <div class="history-record-card__head">
                            <div>
                                <strong>{{ item.student }}</strong>
                                <span>{{ item.time }}</span>
                            </div>
                            <span
                                class="score-chip"
                                :class="item.score < 60 ? 'is-danger' : item.score < 80 ? 'is-warn' : 'is-good'"
                            >
                                {{ formatScore(item.score) }}
                            </span>
                        </div>

                        <div class="teacher-record-row">
                            <span>{{ item.keyword || "未标注知识点" }}</span>
                            <small>{{ item.difficulty || "未标注难度" }}</small>
                        </div>

                        <p>{{ item.question }}</p>
                    </button>
                    <div v-if="!records.length && !loading.dashboard" class="empty-hint">当前还没有历史记录。</div>
                </div>
            </GlassPanel>

            <GlassPanel class="teacher-workspace__detail teacher-history-panel">
                <div class="panel-headline">
                    <div>
                        <span class="eyebrow">History Detail</span>
                        <h3>{{ selectedRecord?.keyword || "当前记录详情" }}</h3>
                    </div>
                    <span class="headline-note">
                        {{ selectedRecord ? `${selectedRecord.student} · ${selectedRecord.time} · 难度 ${selectedRecord.difficulty || "未标注"}` : "点击左侧记录查看具体题目内容" }}
                    </span>
                </div>

                <div ref="teacherDetailBody" class="teacher-scroll-body">
                    <div v-if="selectedRecord" class="teacher-detail-stack">
                        <div class="record-detail-grid">
                            <article class="is-wide">
                                <span>题目内容</span>
                                <div class="student-history-detail__question">
                                    <MarkdownCard :content="selectedRecord.question || '暂无题目内容'" />
                                </div>
                            </article>

                            <article>
                                <span>知识点</span>
                                <strong>{{ selectedRecord.keyword || "未标注" }}</strong>
                            </article>

                            <article>
                                <span>得分</span>
                                <strong>{{ formatScore(selectedRecord.score) }}</strong>
                            </article>

                            <article>
                                <span>难度</span>
                                <strong>{{ selectedRecord.difficulty || "未标注" }}</strong>
                            </article>

                            <article>
                                <span>所属学生</span>
                                <strong>{{ selectedRecord.student }}</strong>
                            </article>

                            <article class="is-wide">
                                <span>学生作答</span>
                                <p>{{ selectedRecord.student_answer || "暂无作答内容" }}</p>
                            </article>

                            <article class="is-wide">
                                <span>AI 评语</span>
                                <div class="student-history-detail__question">
                                    <MarkdownCard :content="selectedRecord.comment || '暂无评语'" />
                                </div>
                            </article>
                        </div>
                    </div>

                    <div v-else class="empty-hint">点击左侧任意一条历史记录，即可查看完整题目内容、学生作答和 AI 评语。</div>
                </div>
            </GlassPanel>
        </section>

        <StatusToast :tone="toast.tone" :title="toast.title" :message="toast.message" />
    </div>
</template>
