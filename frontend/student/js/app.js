const { createApp, ref, reactive, onMounted, nextTick } = Vue;
// const API_BASE = 'http://127.0.0.1:8088'; // 原始值
const API_BASE = ''; // 相对路径，自动适配当前域名/端口

createApp({
    setup() {
        const user = ref({});
        const viewMode = ref('quiz'); // 'quiz' | 'stats' | 'history'
        const config = reactive({ keyword: '', type: 'choice', mode: 'adaptive', manualDifficulty: '中等' });
        const loading = ref(false);
        const question = ref(null);
        const questionId = ref(null); // 新增：保存题目 ID
        const difficulty = ref('');
        const selectedOption = ref(null);
        const studentAnswer = ref('');
        const showResult = ref(false);
        const isCorrect = ref(false);
        const gradeResult = ref(null);
        const historyList = ref([]);
        const streamingText = ref(''); // 流式输出的文本
        const isStreaming = ref(false); // 是否正在流式输出
        const showDetailModal = ref(false); // 是否显示详情弹窗
        const detailData = ref(null); // 详情数据
        
        // 新增：学习分析相关
        const statsData = ref(null);
        const statsLoading = ref(false);
        const trendChart = ref(null);
        let chartInstance = null;

        onMounted(() => {
            const stored = localStorage.getItem('user_info');
            if (!stored) window.location.href = '/static/login.html';
            user.value = JSON.parse(stored);
        });

        const loadHistory = async () => {
            viewMode.value = 'history';
            try {
                const res = await fetch(`${API_BASE}/student/history?student_id=${user.value.id}`);
                const data = await res.json();
                historyList.value = data.data;
            } catch (e) { }
        };

        // 新增：加载学习分析数据
        const loadStats = async () => {
            viewMode.value = 'stats';
            statsLoading.value = true;
            statsData.value = null;
            
            try {
                const keyword = config.keyword || undefined;
                const url = keyword 
                    ? `${API_BASE}/student/adaptive_stats?student_id=${user.value.id}&keyword=${keyword}`
                    : `${API_BASE}/student/adaptive_stats?student_id=${user.value.id}`;
                
                const res = await fetch(url);
                const data = await res.json();
                
                if (data.status === 'success') {
                    statsData.value = data.data;
                    
                    // 等待 DOM 更新后绘制图表
                    await nextTick();
                    drawChart();
                }
            } catch (e) {
                console.error('加载统计数据失败:', e);
            } finally {
                statsLoading.value = false;
            }
        };

        // 绘制趋势图表
        const drawChart = () => {
            if (!statsData.value || !statsData.value.recent_trend.length) return;
            
            const canvas = document.getElementById('trendChart');
            if (!canvas) return;
            
            // 销毁旧图表
            if (chartInstance) {
                chartInstance.destroy();
            }
            
            const ctx = canvas.getContext('2d');
            const trendData = statsData.value.recent_trend;
            
            // 难度映射为数值
            const difficultyMap = { '简单': 1, '中等': 2, '困难': 3 };
            
            chartInstance = new Chart(ctx, {
                type: 'line',
                data: {
                    labels: trendData.map(d => d.time),
                    datasets: [
                        {
                            label: '得分',
                            data: trendData.map(d => d.score),
                            borderColor: '#2563eb',
                            backgroundColor: 'rgba(37, 99, 235, 0.1)',
                            tension: 0.3,
                            fill: true,
                            yAxisID: 'y'
                        },
                        {
                            label: '难度',
                            data: trendData.map(d => difficultyMap[d.difficulty]),
                            borderColor: '#f59e0b',
                            backgroundColor: 'rgba(245, 158, 11, 0.1)',
                            tension: 0.3,
                            fill: false,
                            yAxisID: 'y1'
                        }
                    ]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    interaction: {
                        mode: 'index',
                        intersect: false
                    },
                    plugins: {
                        legend: {
                            display: true,
                            position: 'top'
                        },
                        tooltip: {
                            callbacks: {
                                afterLabel: function(context) {
                                    if (context.datasetIndex === 0) {
                                        const index = context.dataIndex;
                                        return '知识点: ' + trendData[index].keyword;
                                    }
                                    return '';
                                }
                            }
                        }
                    },
                    scales: {
                        y: {
                            type: 'linear',
                            display: true,
                            position: 'left',
                            min: 0,
                            max: 100,
                            title: {
                                display: true,
                                text: '得分'
                            }
                        },
                        y1: {
                            type: 'linear',
                            display: true,
                            position: 'right',
                            min: 0,
                            max: 4,
                            ticks: {
                                stepSize: 1,
                                callback: function(value) {
                                    const labels = ['', '简单', '中等', '困难'];
                                    return labels[value] || '';
                                }
                            },
                            title: {
                                display: true,
                                text: '难度'
                            },
                            grid: {
                                drawOnChartArea: false
                            }
                        }
                    }
                }
            });
        };

        // 辅助函数：获取分数颜色
        const getScoreColor = (score) => {
            if (score >= 85) return '#22c55e';
            if (score >= 70) return '#3b82f6';
            if (score >= 60) return '#f59e0b';
            return '#ef4444';
        };

        // 辅助函数：获取难度样式类
        const getDifficultyClass = (diff) => {
            const map = {
                '简单': 'diff-easy',
                '中等': 'diff-medium',
                '困难': 'diff-hard'
            };
            return map[diff] || '';
        };

        // 辅助函数：获取掌握等级样式类
        const getLevelClass = (level) => {
            const map = {
                '熟练掌握': 'level-master',
                '基本掌握': 'level-good',
                '需要练习': 'level-practice',
                '未掌握': 'level-weak'
            };
            return map[level] || '';
        };

        // 辅助函数：获取进度条颜色
        const getProgressColor = (score) => {
            if (score >= 85) return 'linear-gradient(90deg, #22c55e, #16a34a)';
            if (score >= 70) return 'linear-gradient(90deg, #3b82f6, #2563eb)';
            if (score >= 60) return 'linear-gradient(90deg, #f59e0b, #d97706)';
            return 'linear-gradient(90deg, #ef4444, #dc2626)';
        };

        const generate = async () => {
            if (!config.keyword) return alert('请输入知识点');
            loading.value = true;
            question.value = null;
            showResult.value = false;
            selectedOption.value = null;
            studentAnswer.value = '';
            gradeResult.value = null;
            streamingText.value = '';

            try {
                const res = await fetch(`${API_BASE}/student/generate_question`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        keyword: config.keyword,
                        student_id: user.value.id,
                        mode: config.mode,
                        manual_difficulty: config.manualDifficulty,
                        question_type: config.type
                    })
                });
                const data = await res.json();
                if (data.status === 'success') {
                    question.value = typeof data.data === 'string' ? JSON.parse(data.data) : data.data;
                    difficulty.value = data.difficulty;
                    questionId.value = data.question_id; // 保存题目 ID
                } else { alert(data.detail); }
            } catch (e) { alert('生成失败'); }
            finally { loading.value = false; }
        };

        //流式生成函数
        const generateStream = async () => {
            if (!config.keyword) return alert('请输入知识点');
            loading.value = true;
            isStreaming.value = true;
            question.value = null;
            showResult.value = false;
            selectedOption.value = null;
            studentAnswer.value = '';
            gradeResult.value = null;
            streamingText.value = '';

            try {
                const response = await fetch(`${API_BASE}/student/generate_question_stream`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        keyword: config.keyword,
                        student_id: user.value.id,
                        mode: config.mode,
                        manual_difficulty: config.manualDifficulty,
                        question_type: config.type
                    })
                });

                const reader = response.body.getReader();
                const decoder = new TextDecoder();
                let fullText = '';
                let displayText = ''; // 用于显示的文本（不包含答案和解析）
                let metadata = null;
                let reachedAnswer = false; // 标记是否已到达答案部分

                while (true) {
                    const { done, value } = await reader.read();
                    if (done) break;

                    const chunk = decoder.decode(value, { stream: true });
                    //处理可能被分割的 JSON 数据包
                    // 将新的 chunk 追加到 buffer 中
                    let buffer = chunk;
                    const lines = buffer.split('\n');

                    for (const line of lines) {
                        const trimmedLine = line.trim();
                        if (!trimmedLine || !trimmedLine.startsWith('data: ')) continue;

                        try {
                            const jsonStr = trimmedLine.substring(6);
                            const jsonData = JSON.parse(jsonStr);

                            if (jsonData.type === 'metadata') {
                                // 接收元数据
                                difficulty.value = jsonData.difficulty;
                                questionId.value = jsonData.question_id; // 保存题目 ID
                                streamingText.value = `RAG 检索完成 (${jsonData.rag_time})，AI 正在生成题目...`;
                            } else if (jsonData.type === 'content') {
                                // 逐字接收内容
                                fullText += jsonData.content;

                                // 检查是否到达"答案："部分
                                if (!reachedAnswer && fullText.includes('答案：')) {
                                    reachedAnswer = true;
                                    // 只显示答案之前的部分
                                    const answerIndex = fullText.indexOf('答案：');
                                    displayText = fullText.substring(0, answerIndex);
                                    streamingText.value = displayText;
                                } else if (!reachedAnswer) {
                                    // 还没到答案部分，正常显示
                                    displayText = fullText;
                                    streamingText.value = displayText;
                                }
                                // 如果已经到达答案部分，就不再更新显示
                            } else if (jsonData.type === 'done') {
                                // 生成完成，解析题目
                                parseStreamedQuestion(fullText);
                                streamingText.value = '';
                                loading.value = false;
                                isStreaming.value = false;
                            } else if (jsonData.type === 'error') {
                                alert('生成出错: ' + jsonData.message);
                                loading.value = false;
                                isStreaming.value = false;
                            }
                        } catch (e) {
                            console.error('解析 SSE 数据失败:', e, line);
                        }
                    }
                }
            } catch (e) {
                alert('流式生成失败: ' + e.message);
                loading.value = false;
                isStreaming.value = false;
            }
        };

        // 解析流式生成的题目文本
        const parseStreamedQuestion = (text) => {
            try {
                // 简单解析（根据固定格式）
                const lines = text.split('\n').map(l => l.trim()).filter(l => l);
                const result = { question: '', options: null, answer: '', analysis: '' };

                let currentSection = '';
                let optionsObj = {};

                for (const line of lines) {
                    if (line.startsWith('题目：')) {
                        currentSection = 'question';
                        result.question = line.substring(3);
                    } else if (line.match(/^[A-D]\./)) {
                        // 选项
                        const key = line[0];
                        const value = line.substring(2).trim();
                        optionsObj[key] = value;
                    } else if (line.startsWith('答案：')) {
                        currentSection = 'answer';
                        result.answer = line.substring(3).trim();
                    } else if (line.startsWith('解析：')) {
                        currentSection = 'analysis';
                        result.analysis = line.substring(3);
                    } else {
                        // 续行
                        if (currentSection === 'question') {
                            result.question += '\n' + line;
                        } else if (currentSection === 'analysis') {
                            result.analysis += '\n' + line;
                        }
                    }
                }

                // 如果有选项，添加到结果
                if (Object.keys(optionsObj).length > 0) {
                    result.options = optionsObj;
                }

                question.value = result;
            } catch (e) {
                console.error('解析题目失败:', e);
                alert('题目解析失败，请重试');
            }
        };

        const submit = async () => {
            showResult.value = true;
            // 构建完整的题目内容（包括选项和解析）
            let fullQuestion = question.value.question;
            if (config.type === 'choice' && question.value.options) {
                fullQuestion += '\n\n选项：\n';
                for (let [key, value] of Object.entries(question.value.options)) {
                    fullQuestion += `${key}. ${value}\n`;
                }
            }

            let payload = {
                question: fullQuestion,
                standard_answer: question.value.answer,
                student_id: user.value.id,
                question_id: questionId.value, // 新增：传回题目 ID
                difficulty: difficulty.value,
                question_type: config.type,
                student_answer: '',
                direct_score: 0,
                analysis: question.value.analysis || ''  // 添加解析
            };

            if (config.type === 'choice') {
                if (!selectedOption.value) return alert('请选择');
                isCorrect.value = selectedOption.value === question.value.answer;
                payload.student_answer = selectedOption.value;
                payload.direct_score = isCorrect.value ? 100 : 0;
            } else {
                if (!studentAnswer.value) return alert('请输入');
                payload.student_answer = studentAnswer.value;
            }

            try {
                const res = await fetch(`${API_BASE}/student/grade_answer`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(payload)
                });
                const data = await res.json();
                if (config.type !== 'choice') gradeResult.value = data.data;
            } catch (e) { console.error(e); }
        };

        const logout = () => {
            localStorage.removeItem('user_info');
            window.location.href = '/static/login.html';
        };

        const renderMarkdown = (t) => marked.parse(t || '');

        const showDetail = async (recordId) => {
            try {
                const res = await fetch(`${API_BASE}/student/history/${recordId}`);
                const data = await res.json();
                if (data.status === 'success') {
                    detailData.value = data.data;
                    showDetailModal.value = true;
                } else {
                    alert('获取详情失败');
                }
            } catch (e) {
                alert('网络错误');
            }
        };

        return {
            user, viewMode, config, loading, question, questionId, difficulty,
            selectedOption, studentAnswer, showResult, isCorrect,
            gradeResult, historyList, streamingText, isStreaming,
            showDetailModal, detailData,
            statsData, statsLoading, trendChart,
            loadHistory, loadStats, generate, generateStream, submit, logout, renderMarkdown, showDetail,
            getScoreColor, getDifficultyClass, getLevelClass, getProgressColor
        };
    }
}).mount('#app');
