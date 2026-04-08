export const adminService = {
    async fetchExperimentVersions() {
        return window.AppApi.requestJson("/admin/experiment_versions?scene=ragas_eval&limit=4");
    },

    async debugGenerationStream(keyword) {
        return window.AppApi.request("/admin/debug_generation_stream", {
            method: "POST",
            body: JSON.stringify({ keyword }),
        });
    },

    async runRagas() {
        return window.AppApi.requestJson("/admin/run_ragas_eval", {
            method: "POST",
        });
    },

    async fetchStressStats() {
        return window.AppApi.requestJson("/admin/stress/stats");
    },

    async startStress(config) {
        return window.AppApi.requestJson("/admin/stress/start", {
            method: "POST",
            body: JSON.stringify(config),
        });
    },

    async stopStress() {
        return window.AppApi.requestJson("/admin/stress/stop", { method: "POST" });
    },
};
