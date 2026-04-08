const VueSfcLoader = window["vue3-sfc-loader"];
const { loadModule } = VueSfcLoader || {};
const APP_VERSION = "20260408u7";

window.APP_VERSION = APP_VERSION;

function assetUrl(path) {
    return path.includes("?") ? path : `${path}?v=${APP_VERSION}`;
}

function renderBootError(error) {
    const message = error?.message || "未知错误";
    document.getElementById("app").innerHTML = `
        <div class="boot-error">
            <h1>界面启动失败</h1>
            <p>请刷新页面后重试。如果问题持续存在，请检查静态资源是否完整。</p>
            <pre class="boot-error__detail">${message}</pre>
        </div>
    `;
}

if (!window.Vue || !window.VueRouter || !VueSfcLoader || !window.marked) {
    renderBootError(new Error("前端运行依赖未加载，请检查 CDN 资源是否可访问。"));
    throw new Error("spa_runtime_dependency_missing");
}

const globalComponentPaths = {
    AppNavigation: "/static/app/components/AppNavigation.vue",
    GlassPanel: "/static/app/components/GlassPanel.vue",
    MetricCard: "/static/app/components/MetricCard.vue",
    StatusToast: "/static/app/components/StatusToast.vue",
    LineAreaChart: "/static/app/components/LineAreaChart.vue",
    RadarChart: "/static/app/components/RadarChart.vue",
    SideDrawer: "/static/app/components/SideDrawer.vue",
    LoadingShimmer: "/static/app/components/LoadingShimmer.vue",
    FlowRail: "/static/app/components/FlowRail.vue",
    MarkdownCard: "/static/app/components/MarkdownCard.vue",
};

window.marked.setOptions({
    gfm: true,
    breaks: true,
});

const loaderOptions = {
    moduleCache: {
        vue: window.Vue,
        "vue-router": window.VueRouter,
    },
    async getFile(url) {
        const response = await fetch(url);
        if (!response.ok) {
            throw new Error(`无法加载模块：${url}`);
        }
        return await response.text();
    },
    addStyle(textContent) {
        const style = document.createElement("style");
        style.textContent = textContent;
        document.head.appendChild(style);
    },
};

window.AppLoaders = {
    assetUrl,
    async loadVueModule(path) {
        const target = assetUrl(path);
        try {
            return await loadModule(target, loaderOptions);
        } catch (error) {
            throw new Error(`${path} 加载失败：${error?.message || String(error)}`);
        }
    },
};

const allRoles = ["student", "teacher", "admin"];
const hydratedAuth = window.AppSession.loadAuth(allRoles);
if (hydratedAuth) {
    window.AppSession.saveAuth(hydratedAuth);
}

const originalClearAuth = window.AppSession.clearAuth.bind(window.AppSession);
window.AppSession.clearAuth = (role = null) => {
    const detectedRole = role
        || window.AppSession.loadAuth(allRoles)?.user?.role
        || (window.location.hash.includes("/lab") ? "admin" : "")
        || (window.location.hash.includes("/teacher") ? "teacher" : "")
        || (window.location.hash.includes("/student") ? "student" : "");
    return originalClearAuth(detectedRole || null);
};

async function bootstrap() {
    const [
        { default: createAppRouter },
        { useAuth },
        { useTaskPoller },
        { useWorkspaceShell },
        formatUtils,
        markdownUtils,
        questionUtils,
        studentServices,
        adminServices,
    ] = await Promise.all([
        import(assetUrl("/static/app/router.js")),
        import(assetUrl("/static/app/composables/useAuth.js")),
        import(assetUrl("/static/app/composables/useTaskPoller.js")),
        import(assetUrl("/static/app/composables/useWorkspaceShell.js")),
        import(assetUrl("/static/app/utils/format.js")),
        import(assetUrl("/static/app/utils/markdown.js")),
        import(assetUrl("/static/app/utils/question.js")),
        import(assetUrl("/static/app/services/student-service.js")),
        import(assetUrl("/static/app/services/admin-service.js")),
    ]);

    window.AppModules = {
        composables: {
            useAuth,
            useTaskPoller,
            useWorkspaceShell,
        },
        utils: {
            ...formatUtils,
            ...markdownUtils,
            ...questionUtils,
        },
        services: {
            ...studentServices,
            ...adminServices,
        },
    };

    const componentEntries = Object.entries(globalComponentPaths);
    const [AppRoot, ...globalComponents] = await Promise.all([
        window.AppLoaders.loadVueModule("/static/app/App.vue"),
        ...componentEntries.map(([, path]) => window.AppLoaders.loadVueModule(path)),
    ]);

    const app = window.Vue.createApp(AppRoot);
    componentEntries.forEach(([name], index) => {
        app.component(name, globalComponents[index]);
    });
    app.use(createAppRouter());
    app.mount("#app");
}

bootstrap().catch((error) => {
    console.error("spa_bootstrap_failed", error);
    renderBootError(error);
});
