const { computed, ref } = window.Vue;

const ALL_ROLES = ["student", "teacher", "admin"];
const APP_ENTRY = "/static/app/index.html?v=20260408u7";

const roleMeta = {
    student: {
        label: "学生端",
        home: "/student",
        subtitle: "学生工作台",
    },
    teacher: {
        label: "教师端",
        home: "/teacher",
        subtitle: "教学数据驾驶舱",
    },
    admin: {
        label: "研发端",
        home: "/lab",
        subtitle: "RAG 算法实验室",
    },
};

const authState = ref(window.AppSession.loadAuth(ALL_ROLES));

export function useAuth() {
    const user = computed(() => authState.value?.user || null);
    const currentRole = computed(() => user.value?.role || "");
    const currentMeta = computed(() => roleMeta[currentRole.value] || null);

    const refreshAuth = (roles = ALL_ROLES) => {
        authState.value = window.AppSession.loadAuth(roles);
        return authState.value;
    };

    const handleLoginSuccess = (payload) => {
        window.AppSession.saveAuth(payload);
        authState.value = window.AppSession.loadAuth(ALL_ROLES);
        if (payload.user.role === "admin" && payload.user.username !== "root") {
            return "/login";
        }
        return roleMeta[payload.user.role]?.home || "/login";
    };

    const logout = (router) => {
        const role = authState.value?.user?.role || null;
        window.AppSession.clearAuth(role);
        authState.value = null;
        if (router) {
            router.push("/login");
        } else {
            window.location.href = `${APP_ENTRY}#/login`;
        }
    };

    return {
        authState,
        user,
        currentRole,
        currentMeta,
        roleMeta,
        refreshAuth,
        handleLoginSuccess,
        logout,
    };
}
