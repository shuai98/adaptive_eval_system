export function formatPercent(value, digits = 0) {
    const numeric = Number(value || 0);
    return `${numeric.toFixed(digits)}%`;
}

export function formatScore(value, digits = 1) {
    const numeric = Number(value || 0);
    return Number.isFinite(numeric) ? numeric.toFixed(digits) : "0.0";
}

export function formatCompactNumber(value) {
    const numeric = Number(value || 0);
    if (!Number.isFinite(numeric)) return "0";
    return new Intl.NumberFormat("zh-CN", { notation: "compact" }).format(numeric);
}

export function parseDurationToMs(input) {
    if (typeof input === "number") return input;
    if (!input) return 0;
    const text = String(input).trim().toLowerCase();
    if (text.endsWith("ms")) return Number(text.replace("ms", "")) || 0;
    if (text.endsWith("s")) return (Number(text.replace("s", "")) || 0) * 1000;
    return Number(text) || 0;
}

export function latencyTone(value) {
    const ms = parseDurationToMs(value);
    if (ms < 500) return "good";
    if (ms > 2000) return "danger";
    return "warn";
}

export function clamp(value, min = 0, max = 100) {
    return Math.min(max, Math.max(min, value));
}

export function escapeHtml(value) {
    return String(value || "")
        .replaceAll("&", "&amp;")
        .replaceAll("<", "&lt;")
        .replaceAll(">", "&gt;")
        .replaceAll('"', "&quot;")
        .replaceAll("'", "&#39;");
}
