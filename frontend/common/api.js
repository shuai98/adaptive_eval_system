(function () {
    const API_BASE = window.location.protocol === "file:" ? "http://127.0.0.1:8088" : "";

    function buildHeaders(options) {
        const headers = { ...(options.headers || {}) };
        const token = window.AppSession?.getToken?.();
        if (token && !headers.Authorization) {
            headers.Authorization = `Bearer ${token}`;
        }
        if (!headers["Content-Type"] && options.body && !(options.body instanceof FormData)) {
            headers["Content-Type"] = "application/json";
        }
        return headers;
    }

    async function request(path, options = {}) {
        const response = await fetch(`${API_BASE}${path}`, {
            ...options,
            headers: buildHeaders(options),
        });
        if (response.status === 401 || response.status === 403) {
            window.AppSession?.clearAuth?.();
            if (window.location.pathname !== "/static/login.html") {
                window.location.replace("/static/login.html");
            }
        }
        return response;
    }

    async function requestJson(path, options = {}) {
        const response = await request(path, options);
        let payload = null;
        try {
            payload = await response.json();
        } catch (error) {
            payload = null;
        }
        if (!response.ok) {
            throw new Error(payload?.detail || payload?.message || `HTTP ${response.status}`);
        }
        return payload;
    }

    window.AppApi = {
        API_BASE,
        request,
        requestJson,
    };
})();

