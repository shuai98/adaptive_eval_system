<script setup>
const { computed } = Vue;
const { useRoute, useRouter } = VueRouter;
const { useAuth, useWorkspaceShell } = window.AppModules.composables;

const route = useRoute();
const router = useRouter();
const { user, currentMeta, logout } = useAuth();
const { getRoleShell } = useWorkspaceShell();

const roleShell = computed(() => getRoleShell(user.value?.role || ""));

const resolveValue = (value, fallback = "") => {
    if (typeof value === "function") {
        return value() || fallback;
    }
    return value ?? fallback;
};

const isItemActive = (item) => {
    if (typeof item?.isActive === "function") {
        return Boolean(item.isActive());
    }
    if (item?.path) {
        return route.path === item.path;
    }
    return false;
};

const handleItemClick = (item) => {
    if (typeof item?.onClick === "function") {
        item.onClick();
        return;
    }
    if (item?.path) {
        router.push(item.path);
    }
};

const role = computed(() => user.value?.role || "");
</script>

<template>
    <aside class="app-navigation app-navigation--workspace">
        <div class="app-navigation__brand app-navigation__brand--compact">
            <span class="eyebrow">Adaptive Learning</span>
            <h1>{{ resolveValue(roleShell.title, currentMeta?.subtitle || "系统总览") }}</h1>
            <p>{{ resolveValue(roleShell.copy, "统一入口") }}</p>
        </div>

        <nav v-if="roleShell.navItems?.length" class="app-navigation__menu app-navigation__menu--workspace">
            <button
                v-for="item in roleShell.navItems"
                :key="item.id || item.label || item.path"
                type="button"
                :class="['nav-button', isItemActive(item) ? 'is-active' : '']"
                @click="handleItemClick(item)"
            >
                <span>{{ item.label }}</span>
                <small v-if="item.meta">{{ resolveValue(item.meta) }}</small>
            </button>
        </nav>

        <section v-if="role === 'student' && roleShell.controls" class="workspace-panel">
            <div class="workspace-panel__head">
                <strong>答题控制</strong>
                <span>当前页面的核心输入</span>
            </div>

            <label class="form-field">
                <span>考核知识点</span>
                <input v-model="roleShell.controls.config.keyword" type="text" placeholder="例如 递归">
            </label>

            <div class="form-field">
                <span>题目类型</span>
                <div class="workspace-segmented-grid">
                    <button
                        v-for="item in roleShell.controls.typeOptions"
                        :key="item.value"
                        type="button"
                        :class="['role-pill', roleShell.controls.config.type === item.value ? 'is-active' : '']"
                        @click="roleShell.controls.config.type = item.value"
                    >
                        {{ item.label }}
                    </button>
                </div>
            </div>

            <label class="form-field">
                <span>难度模式</span>
                <select v-model="roleShell.controls.config.mode">
                    <option value="adaptive">自适应（推荐）</option>
                    <option value="manual">固定难度</option>
                </select>
            </label>

            <label v-if="roleShell.controls.config.mode === 'manual'" class="form-field">
                <span>固定难度</span>
                <select v-model="roleShell.controls.config.manualDifficulty">
                    <option
                        v-for="item in roleShell.controls.difficultyOptions"
                        :key="item"
                        :value="item"
                    >
                        {{ item }}
                    </option>
                </select>
            </label>

            <button
                class="primary-button workspace-panel__action"
                type="button"
                :disabled="Boolean(resolveValue(roleShell.controls.generating, false))"
                @click="roleShell.controls.onGenerate?.()"
            >
                {{ resolveValue(roleShell.controls.generating, false) ? "生成中..." : "生成题目" }}
            </button>
        </section>

        <section v-if="roleShell.summaryItems?.length" class="workspace-summary">
            <div class="workspace-panel__head">
                <strong>当前摘要</strong>
                <span>随页面状态实时更新</span>
            </div>

            <div class="workspace-summary__list">
                <article
                    v-for="item in roleShell.summaryItems"
                    :key="item.label"
                    class="workspace-summary__item"
                >
                    <span>{{ item.label }}</span>
                    <strong>{{ resolveValue(item.value, "-") }}</strong>
                </article>
            </div>
        </section>

        <div class="app-navigation__footer">
            <div class="identity-card">
                <span>{{ currentMeta?.label }}</span>
                <strong>{{ user?.username }}</strong>
            </div>
            <button class="ghost-button" type="button" @click="logout(router)">退出登录</button>
        </div>
    </aside>
</template>
