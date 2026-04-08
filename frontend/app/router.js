const ALL_ROLES = ["student", "teacher", "admin"];

function roleHome(userOrRole) {
    const role = typeof userOrRole === "string" ? userOrRole : userOrRole?.role;
    const username = typeof userOrRole === "string" ? "" : userOrRole?.username;
    return {
        student: "/student",
        teacher: "/teacher",
        admin: username === "root" ? "/lab" : "/login",
    }[role] || "/login";
}

function loadView(name) {
    return () => window.AppLoaders.loadVueModule(`/static/app/views/${name}.vue`);
}

export default function createAppRouter() {
    const router = window.VueRouter.createRouter({
        history: window.VueRouter.createWebHashHistory(),
        routes: [
            {
                path: "/",
                redirect: "/login",
            },
            {
                path: "/login",
                name: "login",
                component: loadView("LoginView"),
                meta: { public: true, theme: "light" },
            },
            {
                path: "/student",
                name: "student",
                component: loadView("StudentWorkspaceView"),
                meta: { roles: ["student"], theme: "light", title: "学生工作台" },
            },
            {
                path: "/teacher",
                name: "teacher",
                component: loadView("TeacherConsoleView"),
                meta: { roles: ["teacher"], theme: "light", title: "教师控制台" },
            },
            {
                path: "/lab",
                name: "lab",
                component: loadView("AdminLabView"),
                meta: { roles: ["admin"], usernames: ["root"], theme: "dark", title: "研发管理中心" },
            },
            {
                path: "/:pathMatch(.*)*",
                redirect: "/login",
            },
        ],
    });

    router.beforeEach((to) => {
        const auth = window.AppSession.loadAuth(ALL_ROLES);

        if (to.meta.public) {
            return true;
        }

        if (!to.meta.roles?.length) {
            return true;
        }

        const ensured = window.AppSession.ensureRole(to.meta.roles);
        if (!ensured) {
            return false;
        }

        if (!to.meta.roles.includes(ensured.user.role)) {
            return roleHome(ensured.user);
        }

        if (to.meta.usernames?.length && !to.meta.usernames.includes(ensured.user.username)) {
            return "/login";
        }

        return true;
    });

    router.afterEach((to) => {
        document.title = to.meta.title ? `${to.meta.title} - 自适应评测系统` : "自适应评测系统";
    });

    return router;
}
