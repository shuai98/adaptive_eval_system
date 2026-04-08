<script setup>
const { computed, reactive, ref } = Vue;
const { useRoute, useRouter } = VueRouter;
const { useAuth } = window.AppModules.composables;

const router = useRouter();
const route = useRoute();
const { handleLoginSuccess } = useAuth();

const mode = ref("login");
const verified = ref(false);
const loading = ref(false);
const errorMessage = ref("");
const successMessage = ref("");

const form = reactive({
    username: "",
    password: "",
    role: "student",
});

const modeTitle = computed(() => mode.value === "login" ? "欢迎进入自适应评测系统" : "创建新的学习身份");
const submitLabel = computed(() => {
    if (loading.value) return mode.value === "login" ? "正在登录..." : "正在创建账号...";
    return mode.value === "login" ? "进入系统" : "完成注册";
});

const handleSubmit = async () => {
    errorMessage.value = "";
    successMessage.value = "";

    if (!form.username.trim() || !form.password.trim()) {
        errorMessage.value = "请输入完整的用户名和密码";
        return;
    }

    if (form.role === "admin" && form.username.trim() !== "root") {
        errorMessage.value = "研发界面仅允许 root 账号登录";
        return;
    }

    if (!verified.value) {
        errorMessage.value = "请先确认当前身份";
        return;
    }

    loading.value = true;
    try {
        const endpoint = mode.value === "login" ? "/login" : "/register";
        const payload = await window.AppApi.requestJson(endpoint, {
            method: "POST",
            body: JSON.stringify(form),
        });

        if (mode.value === "register") {
            successMessage.value = "注册成功 请直接登录";
            mode.value = "login";
            verified.value = false;
            return;
        }

        const redirect = handleLoginSuccess(payload);
        router.push(route.query.redirect || redirect);
    } catch (error) {
        errorMessage.value = error.message || "请求失败 请稍后重试";
        verified.value = false;
    } finally {
        loading.value = false;
    }
};
</script>

<template>
    <div class="login-page">
        <section class="login-hero">
            <span class="eyebrow">Modern Learning Interface</span>
            <h1>{{ modeTitle }}</h1>
            <p>
                面向学生 教师与研发人员的统一前端入口 登录后会自动进入对应的现代化单页面工作区
                交互 图表 任务状态与数据视图全部共用同一套前端设计系统
            </p>
            <div class="login-hero__chips">
                <span>学生端 沉浸式导学空间</span>
                <span>教师端 教学数据驾驶舱</span>
                <span>研发端 RAG 算法实验室</span>
            </div>
        </section>

        <section class="login-card-panel">
            <div class="login-mode-toggle">
                <button
                    type="button"
                    :class="['segmented-button', mode === 'login' ? 'is-active' : '']"
                    @click="mode = 'login'"
                >
                    登录
                </button>
                <button
                    type="button"
                    :class="['segmented-button', mode === 'register' ? 'is-active' : '']"
                    @click="mode = 'register'"
                >
                    注册
                </button>
            </div>

            <div class="form-stack">
                <label class="form-field">
                    <span>用户名</span>
                    <input v-model="form.username" type="text" placeholder="请输入用户名">
                </label>

                <label class="form-field">
                    <span>密码</span>
                    <input v-model="form.password" type="password" placeholder="请输入密码">
                </label>

                <div class="form-field">
                    <span>身份角色</span>
                    <div class="role-pills">
                        <button
                            v-for="item in [
                                { label: '学生', value: 'student' },
                                { label: '教师', value: 'teacher' },
                                { label: '管理员', value: 'admin' }
                            ]"
                            :key="item.value"
                            type="button"
                            :class="['role-pill', form.role === item.value ? 'is-active' : '']"
                            @click="form.role = item.value"
                        >
                            {{ item.label }}
                        </button>
                    </div>
                    <div v-if="form.role === 'admin'" class="inline-banner">
                        研发界面仅开放给 root 账号，其他账号不会进入该界面。
                    </div>
                </div>

                <label class="verify-check">
                    <input v-model="verified" type="checkbox">
                    <span>我已确认当前登录身份 并允许系统按角色跳转</span>
                </label>

                <div v-if="errorMessage" class="inline-banner tone-danger">{{ errorMessage }}</div>
                <div v-if="successMessage" class="inline-banner tone-success">{{ successMessage }}</div>

                <button class="primary-button login-submit" type="button" @click="handleSubmit">
                    {{ submitLabel }}
                </button>
            </div>
        </section>
    </div>
</template>
