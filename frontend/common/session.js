(function () {
    const STORAGE_KEY = "adaptive_auth_state";
    const LEGACY_USER_KEY = "user_info";
    const ROLE_PREFIX = "adaptive_auth_state:";

    function storage() {
        return window.sessionStorage;
    }

    function currentPageRole() {
        const path = window.location.pathname || "";
        if (path.includes("/admin/")) return "admin";
        if (path.includes("/teacher/")) return "teacher";
        if (path.includes("/student/")) return "student";
        return null;
    }

    function roleStorageKey(role) {
        return `${ROLE_PREFIX}${role}`;
    }

    function parseAuth(raw) {
        if (!raw) return null;
        try {
            const parsed = JSON.parse(raw);
            if (!parsed || !parsed.access_token || !parsed.user || !parsed.user.role) {
                return null;
            }
            return parsed;
        } catch (error) {
            return null;
        }
    }

    function rememberInSession(payload) {
        storage().setItem(STORAGE_KEY, JSON.stringify(payload));
        storage().setItem(LEGACY_USER_KEY, JSON.stringify(payload.user || null));
    }

    function migrateLegacyAuth(preferredRoles = []) {
        const legacyGlobal = parseAuth(localStorage.getItem(STORAGE_KEY));
        if (legacyGlobal && (!preferredRoles.length || preferredRoles.includes(legacyGlobal.user.role))) {
            localStorage.setItem(roleStorageKey(legacyGlobal.user.role), JSON.stringify(legacyGlobal));
            localStorage.removeItem(STORAGE_KEY);
            rememberInSession(legacyGlobal);
            return legacyGlobal;
        }

        const roleCandidates = preferredRoles.length ? preferredRoles : [currentPageRole()].filter(Boolean);
        for (const role of roleCandidates) {
            const payload = parseAuth(localStorage.getItem(roleStorageKey(role)));
            if (payload) {
                rememberInSession(payload);
                return payload;
            }
        }
        return null;
    }

    function loadAuth(preferredRoles = []) {
        const sessionPayload = parseAuth(storage().getItem(STORAGE_KEY));
        if (sessionPayload && (!preferredRoles.length || preferredRoles.includes(sessionPayload.user.role))) {
            return sessionPayload;
        }
        return migrateLegacyAuth(preferredRoles);
    }

    function saveAuth(payload) {
        if (!payload || !payload.user || !payload.user.role) return;
        rememberInSession(payload);
        localStorage.setItem(roleStorageKey(payload.user.role), JSON.stringify(payload));
        localStorage.removeItem(STORAGE_KEY);
        localStorage.removeItem(LEGACY_USER_KEY);
    }

    function clearAuth(role = null) {
        const activeRole = role || currentPageRole() || loadAuth()?.user?.role || null;
        storage().removeItem(STORAGE_KEY);
        storage().removeItem(LEGACY_USER_KEY);
        localStorage.removeItem(STORAGE_KEY);
        localStorage.removeItem(LEGACY_USER_KEY);
        if (activeRole) {
            localStorage.removeItem(roleStorageKey(activeRole));
        }
    }

    function getUser(preferredRoles = []) {
        return loadAuth(preferredRoles)?.user || null;
    }

    function getToken(preferredRoles = []) {
        return loadAuth(preferredRoles)?.access_token || "";
    }

    function ensureRole(roles) {
        const auth = loadAuth(roles || []);
        if (!auth || !auth.user || !roles.includes(auth.user.role)) {
            clearAuth(currentPageRole());
            window.location.href = "/static/login.html";
            return null;
        }
        rememberInSession(auth);
        return auth;
    }

    window.AppSession = {
        STORAGE_KEY,
        loadAuth,
        saveAuth,
        clearAuth,
        getUser,
        getToken,
        ensureRole,
        currentPageRole,
        roleStorageKey,
    };
})();
