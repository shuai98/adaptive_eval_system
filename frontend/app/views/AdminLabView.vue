<script setup>
const { computed, onBeforeUnmount, onMounted, reactive, ref, watch } = Vue;
const { formatCompactNumber, formatScore, latencyTone, parseDurationToMs } = window.AppModules.utils;
const { useWorkspaceShell } = window.AppModules.composables;
const { adminService } = window.AppModules.services;
const { setRoleShell, resetRoleShell } = useWorkspaceShell();

const currentPanel = ref("ragas");
const keyword = ref("");
const loading = ref(false);
const evaluating = ref(false);
const ragasScores = ref(null);
const experimentVersions = ref([]);
const stressHistory = ref([]);

const debugInfo = reactive({
    raw_docs: [],
    rerank_docs: [],
    raw_doc_details: [],
    rerank_doc_details: [],
    timing_log: "",
    timings: {},
    rerank_applied: false,
    rerank_reason: "",
});

const generatedContent = ref("");
const stressConfig = reactive({
    user_count: 20,
    spawn_rate: 5,
});
const stressStats = reactive({
    current_rps: 0,
    avg_rps: 0,
    total_rps: 0,
    current_p50_latency_ms: 0,
    current_p95_latency_ms: 0,
    current_response_time_percentile_95: 0,
    median_response_time: 0,
    avg_latency_ms: 0,
    request_count: 0,
    fail_ratio: 0,
    user_count: 0,
    state: "idle",
    auth_user: "",
    auth_source: "",
});
const stressChartMetric = ref("current_rps");

const toast = reactive({
    tone: "info",
    title: "",
    message: "",
});

let stressTimer = null;

const panelTabs = [
    {
        id: "debug",
        label: "链路调试",
        title: "检索链路调试",
        copy: "查看初步检索、语义精排和题目生成的完整链路。",
    },
    {
        id: "ragas",
        label: "RAGAS 评估",
        title: "RAGAS 评估",
        copy: "查看回答忠实度、检索精准度、初步检索和题目生成指标。",
    },
    {
        id: "stress",
        label: "压力测试",
        title: "压力测试",
        copy: "查看并发用户、RPS、P95 响应时延和运行状态。",
    },
];

const stressMetricTabs = [
    { id: "current_rps", label: "RPS 趋势", unit: "req/s", stroke: "#38BDF8", fill: "rgba(56, 189, 248, 0.16)", copy: "最近 12 次采样的当前吞吐。" },
    { id: "current_p50_latency_ms", label: "P50 时延", unit: "ms", stroke: "#22C55E", fill: "rgba(34, 197, 94, 0.16)", copy: "最近 12 次采样的中位响应时延。" },
    { id: "current_p95_latency_ms", label: "P95 时延", unit: "ms", stroke: "#FB7185", fill: "rgba(251, 113, 133, 0.16)", copy: "最近 12 次采样的长尾响应时延。" },
    { id: "user_count", label: "并发用户", unit: "人", stroke: "#F59E0B", fill: "rgba(245, 158, 11, 0.16)", copy: "最近 12 次采样的活跃并发用户数。" },
];

const showToast = (message, tone = "info", title = "") => {
    toast.message = message;
    toast.tone = tone;
    toast.title = title;
    window.clearTimeout(showToast.timer);
    showToast.timer = window.setTimeout(() => {
        toast.message = "";
    }, 2800);
};

const currentPanelMeta = computed(() => (
    panelTabs.find((item) => item.id === currentPanel.value) || panelTabs[0]
));

function startStressPolling() {
    if (stressTimer) return;
    stressTimer = window.setInterval(fetchStressStats, 3000);
}

function stopStressPolling() {
    if (!stressTimer) return;
    window.clearInterval(stressTimer);
    stressTimer = null;
}

const rawItems = computed(() => {
    if (debugInfo.raw_doc_details.length) return debugInfo.raw_doc_details;
    return debugInfo.raw_docs.map((text, index) => ({ text, recall_rank: index + 1 }));
});

const rerankItems = computed(() => {
    if (debugInfo.rerank_doc_details.length) return debugInfo.rerank_doc_details;
    return debugInfo.rerank_docs.map((text, index) => ({ text, rerank_rank: index + 1 }));
});

const estimatedTokens = computed(() => {
    const sourceLength = [
        ...debugInfo.raw_docs,
        ...debugInfo.rerank_docs,
        generatedContent.value,
    ].join(" ").length;
    return Math.max(0, Math.round(sourceLength / 2.6));
});

const totalLatency = computed(() => {
    const recall = parseDurationToMs(debugInfo.timings?.recall);
    const rerank = parseDurationToMs(debugInfo.timings?.rerank);
    const llmMatch = debugInfo.timing_log.match(/llm generation:\s*([\d.]+)(ms|s)/i);
    let llm = 0;
    if (llmMatch) {
        llm = llmMatch[2].toLowerCase() === "s" ? Number(llmMatch[1]) * 1000 : Number(llmMatch[1]);
    }
    return Math.round(recall + rerank + llm);
});

const latencyCards = computed(() => {
    return [
        {
            label: "响应时延",
            value: `${totalLatency.value} ms`,
            hint: "端到端链路估算值",
            accent: latencyTone(totalLatency.value) === "danger" ? "rose" : latencyTone(totalLatency.value) === "good" ? "emerald" : "amber",
        },
        {
            label: "初步检索",
            value: `${parseDurationToMs(debugInfo.timings?.recall)} ms`,
            hint: "FAISS 召回阶段",
            accent: "sky",
        },
        {
            label: "语义精排",
            value: `${parseDurationToMs(debugInfo.timings?.rerank)} ms`,
            hint: debugInfo.rerank_applied ? "已启用深度语义精排" : `跳过原因 ${debugInfo.rerank_reason || "暂无"}`,
            accent: debugInfo.rerank_applied ? "emerald" : "amber",
        },
        {
            label: "Token 消耗",
            value: `${formatCompactNumber(estimatedTokens.value)}`,
            hint: "基于上下文与生成内容的估算值",
            accent: "blue",
        },
    ];
});

const flowStages = computed(() => ([
    {
        kicker: "Step 1",
        title: "FAISS 初步检索",
        copy: "先做向量召回 保留更宽的候选上下文",
        accent: "blue",
    },
    {
        kicker: "Step 2",
        title: "语义精排",
        copy: "交叉编码器压缩噪音 只留下更强证据",
        accent: "emerald",
    },
    {
        kicker: "Step 3",
        title: "LLM 题目生成",
        copy: "带着高质量上下文完成最终生成",
        accent: "sky",
    },
]));

const evaluationCards = computed(() => {
    const report = normalizeReport(ragasScores.value);
    if (!report) return [];

    return ["V1", "V2", "V3"].map((versionId) => ({
        id: versionId,
        label: versionId,
        faithfulness: metricValue(report, versionId, "faithfulness"),
        precision: metricValue(report, versionId, "context_precision"),
        recall: metricValue(report, versionId, "context_recall"),
        generation: metricValue(report, versionId, "answer_relevancy"),
    }));
});

const stressLabels = computed(() => stressHistory.value.map((item) => item.time));
const stressChartMeta = computed(() => (
    stressMetricTabs.find((item) => item.id === stressChartMetric.value) || stressMetricTabs[0]
));
const stressPoints = computed(() => stressHistory.value.map((item) => Number(item[stressChartMetric.value] || 0)));
const stressCurrentMetricValue = computed(() => {
    if (stressChartMetric.value === "current_p50_latency_ms") {
        return Number(stressStats.current_p50_latency_ms ?? stressStats.median_response_time ?? 0);
    }
    if (stressChartMetric.value === "current_p95_latency_ms") {
        return Number(stressStats.current_p95_latency_ms ?? stressStats.current_response_time_percentile_95 ?? 0);
    }
    if (stressChartMetric.value === "user_count") {
        return Number(stressStats.user_count || 0);
    }
    return Number(stressStats.current_rps ?? stressStats.total_rps ?? 0);
});
const stressChartMax = computed(() => {
    const max = Math.max(0, ...stressPoints.value);
    if (stressChartMetric.value === "user_count") {
        return Math.max(5, Math.ceil(max + 2));
    }
    if (stressChartMetric.value === "current_rps") {
        return Math.max(10, Math.ceil(max * 1.2));
    }
    return Math.max(20, Math.ceil(max * 1.25));
});
const stressWarmup = computed(() => (
    ["spawning", "running"].includes(stressStats.state)
    && Number(stressStats.request_count || 0) === 0
    && Number(stressStats.current_rps || 0) === 0
));
const stressSnapshotCards = computed(() => ([
    {
        label: "P50",
        value: `${Math.round(stressStats.current_p50_latency_ms || 0)} ms`,
        tone: latencyTone(stressStats.current_p50_latency_ms),
    },
    {
        label: "P95",
        value: `${Math.round(stressStats.current_p95_latency_ms || 0)} ms`,
        tone: latencyTone(stressStats.current_p95_latency_ms),
    },
    {
        label: "当前 RPS",
        value: `${formatScore(stressStats.current_rps || 0, 1)}`,
        tone: "sky",
    },
    {
        label: "并发用户",
        value: `${stressStats.user_count || 0}`,
        tone: "emerald",
    },
    {
        label: "平均响应",
        value: `${Math.round(stressStats.avg_latency_ms || 0)} ms`,
        tone: latencyTone(stressStats.avg_latency_ms),
    },
    {
        label: "失败率",
        value: `${formatScore((stressStats.fail_ratio || 0) * 100, 2)}%`,
        tone: (stressStats.fail_ratio || 0) > 0.02 ? "danger" : "good",
    },
]));

function resetStressStats() {
    Object.assign(stressStats, {
        current_rps: 0,
        avg_rps: 0,
        total_rps: 0,
        current_p50_latency_ms: 0,
        current_p95_latency_ms: 0,
        current_response_time_percentile_95: 0,
        median_response_time: 0,
        avg_latency_ms: 0,
        request_count: 0,
        fail_ratio: 0,
        user_count: 0,
        state: "idle",
        auth_user: "",
        auth_source: "",
    });
}

function resetStressHistory() {
    stressHistory.value = [];
}

function normalizeReport(report) {
    if (!report) return null;
    if (report.versions) return report;
    const groups = report.groups || {};
    return {
        versions: {
            V1: { metrics: makeMetrics(groups.pypdf_no_rerank) },
            V2: { metrics: makeMetrics(groups.pypdf_with_rerank) },
            V3: { metrics: makeMetrics(groups.docling_with_rerank) },
        },
    };
}

function makeMetrics(group = {}) {
    return {
        faithfulness: { mean: Number(group.faithfulness || 0) },
        context_precision: { mean: Number(group.context_precision || 0) },
        context_recall: { mean: Number(group.context_recall || 0) },
        answer_relevancy: { mean: Number(group.answer_relevancy || 0) },
    };
}

function metricValue(report, versionId, key) {
    return formatScore(report?.versions?.[versionId]?.metrics?.[key]?.mean || 0, 3);
}

function debugDocMeta(item) {
    const parts = [];
    if (item.recall_rank) parts.push(`召回 #${item.recall_rank}`);
    if (item.rerank_rank) parts.push(`精排 #${item.rerank_rank}`);
    if (item.rerank_score !== undefined && item.rerank_score !== null) parts.push(`分数 ${formatScore(item.rerank_score, 3)}`);
    if (item.source) parts.push(item.source);
    if (item.page) parts.push(`页码 ${item.page}`);
    return parts.join(" · ");
}

async function fetchExperimentVersions() {
    try {
        const payload = await adminService.fetchExperimentVersions();
        experimentVersions.value = payload.data || [];
    } catch (error) {
        experimentVersions.value = [];
    }
}

async function runDebug() {
    if (!keyword.value.trim() || loading.value) {
        showToast("请输入要调试的知识点关键词", "danger", "无法执行");
        return;
    }

    loading.value = true;
    generatedContent.value = "";
    debugInfo.raw_docs = [];
    debugInfo.rerank_docs = [];
    debugInfo.raw_doc_details = [];
    debugInfo.rerank_doc_details = [];
    debugInfo.timing_log = "正在执行链路调试";
    debugInfo.timings = {};
    debugInfo.rerank_applied = false;
    debugInfo.rerank_reason = "";

    try {
        const response = await adminService.debugGenerationStream(keyword.value.trim());

        if (!response.ok || !response.body) {
            throw new Error(`调试接口不可用 HTTP ${response.status}`);
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

            for (const block of blocks) {
                const dataLine = block.split("\n").find((line) => line.startsWith("data: "));
                if (!dataLine) continue;
                const payload = JSON.parse(dataLine.slice(6));

                if (payload.type === "metadata") {
                    debugInfo.raw_docs = payload.raw_docs || [];
                    debugInfo.rerank_docs = payload.rerank_docs || [];
                    debugInfo.raw_doc_details = payload.raw_doc_details || [];
                    debugInfo.rerank_doc_details = payload.rerank_doc_details || [];
                    debugInfo.timings = payload.timings || {};
                    debugInfo.rerank_applied = payload.rerank_applied || false;
                    debugInfo.rerank_reason = payload.rerank_reason || "";
                }

                if (payload.type === "content") {
                    generatedContent.value += payload.content || "";
                }

                if (payload.type === "done") {
                    generatedContent.value = payload.full_content || generatedContent.value;
                    debugInfo.timing_log = payload.timing_log || debugInfo.timing_log;
                }
            }
        }

        showToast("调试链路已刷新 可以直接比对初步检索与语义精排", "success", "执行完成");
    } catch (error) {
        showToast(error.message || "调试执行失败", "danger", "执行失败");
    } finally {
        loading.value = false;
    }
}

async function runRagas() {
    evaluating.value = true;
    try {
        const payload = await adminService.runRagas();
        ragasScores.value = payload.data || null;
        await fetchExperimentVersions();
        showToast("评测结果已更新", "success", "评测完成");
    } catch (error) {
        showToast(error.message || "评测执行失败", "danger", "执行失败");
    } finally {
        evaluating.value = false;
    }
}

function pushStressPoint(stats) {
    const hasSampleData = [
        stats.current_rps,
        stats.total_rps,
        stats.current_p50_latency_ms,
        stats.current_p95_latency_ms,
        stats.request_count,
        stats.user_count,
    ].some((value) => Number(value || 0) > 0);
    if (!hasSampleData) return;

    const nextPoint = {
        time: new Date().toLocaleTimeString("zh-CN", { hour12: false }),
        current_rps: Number(stats.current_rps ?? stats.total_rps ?? 0),
        current_p50_latency_ms: Number(stats.current_p50_latency_ms ?? stats.median_response_time ?? 0),
        current_p95_latency_ms: Number(stats.current_p95_latency_ms ?? stats.current_response_time_percentile_95 ?? 0),
        user_count: Number(stats.user_count || 0),
    };
    const last = stressHistory.value[stressHistory.value.length - 1];
    if (
        last?.time === nextPoint.time
        && last?.current_rps === nextPoint.current_rps
        && last?.current_p50_latency_ms === nextPoint.current_p50_latency_ms
        && last?.current_p95_latency_ms === nextPoint.current_p95_latency_ms
        && last?.user_count === nextPoint.user_count
    ) return;
    stressHistory.value = [...stressHistory.value, nextPoint].slice(-12);
}

async function fetchStressStats() {
    try {
        const payload = await adminService.fetchStressStats();
        if (payload.status !== "success") {
            resetStressStats();
            stopStressPolling();
            return;
        }
        Object.assign(stressStats, payload.data || {});
        pushStressPoint(payload.data || {});
        if (currentPanel.value === "stress" && ["running", "spawning"].includes((payload.data || {}).state)) {
            startStressPolling();
        } else {
            stopStressPolling();
        }
    } catch (error) {
        resetStressStats();
        stopStressPolling();
    }
}

async function startStress() {
    try {
        const payload = await adminService.startStress(stressConfig);
        resetStressHistory();
        resetStressStats();
        Object.assign(stressStats, {
            state: "spawning",
            auth_user: payload?.data?.auth_user || "",
            auth_source: payload?.data?.auth_source || "",
        });
        await fetchStressStats();
        startStressPolling();
        const authUser = payload?.data?.auth_user || stressStats.auth_user;
        const authSource = payload?.data?.auth_source === "database_auto" ? "自动匹配账号" : "环境变量账号";
        const message = authUser
            ? `压测已启动，当前使用 ${authUser}，来源：${authSource}`
            : "压测已启动，正在持续采样";
        showToast(message, "success", "启动成功");
    } catch (error) {
        showToast(error.message || "压测启动失败", "danger", "执行失败");
    }
}

async function stopStress() {
    try {
        await adminService.stopStress();
        stopStressPolling();
        await fetchStressStats();
        showToast("压测已停止", "info", "已结束");
    } catch (error) {
        showToast(error.message || "停止压测失败", "danger", "执行失败");
    }
}

onMounted(async () => {
    setRoleShell("admin", {
        title: "研发管理中心",
        copy: "把链路调试、RAGAS 评估和压力测试统一收进同一套研发工作栏。",
        navItems: panelTabs.map((item) => ({
            id: item.id,
            label: item.label,
            isActive: () => currentPanel.value === item.id,
            onClick: () => {
                currentPanel.value = item.id;
            },
            meta: () => item.title,
        })),
        summaryItems: [
            { label: "当前面板", value: () => currentPanelMeta.value.title },
            { label: "调试关键词", value: () => keyword.value || "未输入" },
            { label: "压测状态", value: () => stressStats.state || "idle" },
        ],
    });

    await Promise.all([fetchExperimentVersions(), fetchStressStats()]);
});

watch(currentPanel, async (panelId) => {
    if (panelId === "stress") {
        await fetchStressStats();
        return;
    }
    stopStressPolling();
});

onBeforeUnmount(() => {
    resetRoleShell("admin");
    stopStressPolling();
});
</script>

<template>
    <div class="page-shell page-shell--dark">
        <header class="page-hero page-hero--dark">
            <div>
                <p class="eyebrow">Research Runtime Center</p>
                <h2>{{ currentPanelMeta.title }}</h2>
                <p>{{ currentPanelMeta.copy }} 切换面板后已加载的数据会保留，返回时可以继续查看。</p>
            </div>
            <span class="headline-note">左侧工作栏负责切换测试面板，右侧保留当前结果。</span>
        </header>

        <section v-show="currentPanel === 'debug'" class="lab-single-panel">
            <FlowRail :stages="flowStages" />
            <GlassPanel tone="dark">
                <div class="panel-headline panel-headline--dark">
                    <div>
                        <span class="eyebrow">Pipeline Debug</span>
                        <h3>检索链路调试</h3>
                    </div>
                    <span class="headline-note">FAISS → 语义精排 → LLM</span>
                </div>

                <div class="lab-input-row">
                    <input v-model="keyword" class="dark-input" type="text" placeholder="输入测试关键词，例如 装饰器、生成器、Session">
                    <button class="primary-button" type="button" @click="runDebug">
                        {{ loading ? "执行中..." : "开始调试" }}
                    </button>
                </div>

                <section class="metrics-grid lab-metrics">
                    <MetricCard
                        v-for="card in latencyCards"
                        :key="card.label"
                        :label="card.label"
                        :value="card.value"
                        :hint="card.hint"
                        :accent="card.accent"
                    />
                </section>

                <div class="lab-columns">
                    <article class="lab-column">
                        <div class="lab-column__head">
                            <h4>初步检索</h4>
                            <span>向量召回候选结果</span>
                        </div>
                        <div class="lab-doc-list">
                            <article v-for="(item, index) in rawItems" :key="`raw-${index}`" class="lab-doc-item">
                                <strong>{{ item.title || `候选 ${index + 1}` }}</strong>
                                <small>{{ debugDocMeta(item) || "来自向量召回" }}</small>
                                <p>{{ item.text || item }}</p>
                            </article>
                            <div v-if="!rawItems.length" class="empty-hint empty-hint--dark">还没有初步检索结果</div>
                        </div>
                    </article>

                    <article class="lab-column">
                        <div class="lab-column__head">
                            <h4>语义精排</h4>
                            <span>精排后的高可信上下文</span>
                        </div>
                        <div class="lab-doc-list">
                            <article v-for="(item, index) in rerankItems" :key="`rerank-${index}`" class="lab-doc-item">
                                <strong>{{ item.title || `结果 ${index + 1}` }}</strong>
                                <small>{{ debugDocMeta(item) || "来自语义精排" }}</small>
                                <p>{{ item.text || item }}</p>
                            </article>
                            <div v-if="!rerankItems.length" class="empty-hint empty-hint--dark">还没有语义精排结果</div>
                        </div>
                    </article>
                </div>

                <div class="generated-panel">
                    <div class="generated-panel__head">
                        <h4>题目生成预览</h4>
                        <span class="mono-text">{{ debugInfo.timing_log || "等待生成结果" }}</span>
                    </div>
                    <pre class="generated-panel__content">{{ generatedContent || "执行调试后 这里会展示题目生成结果" }}</pre>
                </div>
            </GlassPanel>
        </section>

        <section v-show="currentPanel === 'ragas'" class="lab-single-panel">
            <GlassPanel tone="dark">
                <div class="panel-headline panel-headline--dark">
                    <div>
                        <span class="eyebrow">Quality Bench</span>
                        <h3>RAGAS 评测结果</h3>
                    </div>
                    <div class="lab-inline-actions">
                        <span class="headline-note">Faithfulness / Precision / Recall / Generation</span>
                        <button class="primary-button" type="button" @click="runRagas">
                            {{ evaluating ? "评估中..." : "开始 RAGAS 评估" }}
                        </button>
                    </div>
                </div>

                <div class="evaluation-grid">
                    <article v-for="card in evaluationCards" :key="card.id" class="evaluation-card">
                        <div class="evaluation-card__top">
                            <strong>{{ card.label }}</strong>
                            <span>{{ card.id === 'V3' ? '候选方案' : '对照版本' }}</span>
                        </div>
                        <div class="evaluation-card__metric">
                            <span>回答忠实度</span>
                            <strong>{{ card.faithfulness }}</strong>
                        </div>
                        <div class="evaluation-card__metric">
                            <span>检索精准度</span>
                            <strong>{{ card.precision }}</strong>
                        </div>
                        <div class="evaluation-card__metric">
                            <span>初步检索</span>
                            <strong>{{ card.recall }}</strong>
                        </div>
                        <div class="evaluation-card__metric">
                            <span>题目生成</span>
                            <strong>{{ card.generation }}</strong>
                        </div>
                    </article>
                    <div v-if="!evaluationCards.length" class="empty-hint empty-hint--dark lab-empty-cta">
                        <p>点击下方按钮开始 RAGAS 评估，结果会显示在这里。</p>
                        <button class="primary-button" type="button" @click="runRagas">
                            {{ evaluating ? "RAGAS 评估中..." : "开始 RAGAS 评估" }}
                        </button>
                    </div>
                </div>

                <div class="version-stack">
                    <article v-for="item in experimentVersions" :key="item.id" class="version-stack__item">
                        <strong>{{ item.version_key || "实验记录" }}</strong>
                        <span>{{ item.dataset_name || "-" }} · {{ item.parser_mode || "-" }} · {{ item.rerank_mode || "-" }}</span>
                    </article>
                </div>
            </GlassPanel>
        </section>

        <section v-show="currentPanel === 'stress'" class="lab-single-panel">
            <GlassPanel tone="dark">
                <div class="panel-headline panel-headline--dark">
                    <div>
                        <span class="eyebrow">Stress Watch</span>
                        <h3>性能监控</h3>
                    </div>
                    <span class="headline-note">RPS P50 P95 并发用户持续采样</span>
                </div>

                <div class="stress-controls">
                    <label class="form-field form-field--dark">
                        <span>并发用户数</span>
                        <input v-model.number="stressConfig.user_count" class="dark-input" type="number" min="1">
                    </label>
                    <label class="form-field form-field--dark">
                        <span>每秒启动数</span>
                        <input v-model.number="stressConfig.spawn_rate" class="dark-input" type="number" min="1">
                    </label>
                </div>

                <div class="stress-actions">
                    <button class="primary-button" type="button" @click="startStress">开始压测</button>
                    <button class="secondary-button" type="button" @click="stopStress">停止压测</button>
                </div>

                <div class="stress-badges">
                    <span
                        v-for="card in stressSnapshotCards"
                        :key="card.label"
                        :class="['latency-pill', `tone-${card.tone}`]"
                    >
                        {{ card.label }} {{ card.value }}
                    </span>
                </div>

                <div v-if="stressStats.auth_user" class="empty-hint empty-hint--dark">
                    当前压测账号：{{ stressStats.auth_user }}
                    · {{ stressStats.auth_source === "database_auto" ? "自动匹配" : "环境变量" }}
                </div>

                <div class="stress-chart-head">
                    <div>
                        <strong>{{ stressChartMeta.label }}</strong>
                        <p>
                            {{ stressWarmup ? "压测正在预热，首批请求进入采样窗口后才会出现有效 RPS。" : stressChartMeta.copy }}
                            当前共记录 {{ stressHistory.length }} 个采样点。
                        </p>
                    </div>
                    <div class="stress-chart-switch">
                        <button
                            v-for="item in stressMetricTabs"
                            :key="item.id"
                            :class="['segmented-button', { 'is-active': stressChartMetric === item.id }]"
                            type="button"
                            @click="stressChartMetric = item.id"
                        >
                            {{ item.label }}
                        </button>
                    </div>
                </div>

                <div class="stress-chart-meta">
                    <span>当前值 {{ formatScore(stressCurrentMetricValue, 1) }} {{ stressChartMeta.unit }}</span>
                    <span>总请求 {{ stressStats.request_count || 0 }}</span>
                    <span>平均 RPS {{ formatScore(stressStats.avg_rps || 0, 1) }}</span>
                </div>

                <LineAreaChart
                    :points="stressPoints"
                    :labels="stressLabels"
                    :stroke="stressChartMeta.stroke"
                    :fill="stressChartMeta.fill"
                    :max="stressChartMax"
                    :y-axis-unit="stressChartMeta.unit"
                />
            </GlassPanel>
        </section>

        <StatusToast :tone="toast.tone" :title="toast.title" :message="toast.message" />
    </div>
</template>
