<script setup>
const { computed } = Vue;

const props = defineProps({
    points: {
        type: Array,
        default: () => [],
    },
    labels: {
        type: Array,
        default: () => [],
    },
    stroke: {
        type: String,
        default: "#3B82F6",
    },
    fill: {
        type: String,
        default: "rgba(59, 130, 246, 0.18)",
    },
    height: {
        type: Number,
        default: 240,
    },
    min: {
        type: Number,
        default: 0,
    },
    max: {
        type: Number,
        default: 100,
    },
    yAxisUnit: {
        type: String,
        default: "",
    },
});

const width = 720;
const padding = { top: 24, right: 18, bottom: 34, left: 58 };

function formatAxisValue(value) {
    const numeric = Number(value || 0);
    if (numeric >= 1000) {
        return `${Math.round(numeric)}`;
    }
    if (numeric >= 100) {
        return `${Math.round(numeric)}`;
    }
    if (numeric >= 10) {
        return `${numeric.toFixed(1).replace(/\.0$/, "")}`;
    }
    return `${numeric.toFixed(1)}`;
}

const normalizedPoints = computed(() => {
    if (!props.points.length) return [];
    const range = Math.max(1, props.max - props.min);
    const innerWidth = width - padding.left - padding.right;
    const innerHeight = props.height - padding.top - padding.bottom;

    return props.points.map((value, index) => {
        const x = padding.left + (innerWidth / Math.max(1, props.points.length - 1)) * index;
        const ratio = (Number(value || 0) - props.min) / range;
        const y = padding.top + innerHeight - ratio * innerHeight;
        return { x, y, value };
    });
});

const linePath = computed(() => {
    if (!normalizedPoints.value.length) return "";
    return normalizedPoints.value
        .map((point, index) => `${index === 0 ? "M" : "L"} ${point.x.toFixed(2)} ${point.y.toFixed(2)}`)
        .join(" ");
});

const areaPath = computed(() => {
    if (!normalizedPoints.value.length) return "";
    const first = normalizedPoints.value[0];
    const last = normalizedPoints.value[normalizedPoints.value.length - 1];
    return `${linePath.value} L ${last.x.toFixed(2)} ${props.height - padding.bottom} L ${first.x.toFixed(2)} ${props.height - padding.bottom} Z`;
});

const gridLines = computed(() => {
    const innerHeight = props.height - padding.top - padding.bottom;
    return Array.from({ length: 4 }, (_, index) => padding.top + (innerHeight / 3) * index);
});

const yAxisTicks = computed(() => {
    const range = Math.max(1, props.max - props.min);
    return gridLines.value.map((line, index) => {
        const ratio = 1 - (index / Math.max(1, gridLines.value.length - 1));
        const value = props.min + range * ratio;
        return {
            y: line,
            value,
            label: `${formatAxisValue(value)}${props.yAxisUnit ? ` ${props.yAxisUnit}` : ""}`,
        };
    });
});
</script>

<template>
    <svg class="line-chart" :viewBox="`0 0 ${width} ${props.height}`" preserveAspectRatio="none">
        <line
            :x1="padding.left"
            :x2="padding.left"
            :y1="padding.top"
            :y2="props.height - padding.bottom"
            class="line-chart__axis"
        />
        <line
            :x1="padding.left"
            :x2="width - padding.right"
            :y1="props.height - padding.bottom"
            :y2="props.height - padding.bottom"
            class="line-chart__axis"
        />
        <line
            v-for="line in gridLines"
            :key="line"
            :x1="padding.left"
            :x2="width - padding.right"
            :y1="line"
            :y2="line"
            class="line-chart__grid"
        />
        <text
            v-for="tick in yAxisTicks"
            :key="`tick-${tick.y}`"
            :x="padding.left - 10"
            :y="tick.y + 4"
            text-anchor="end"
            class="line-chart__axis-label"
        >
            {{ tick.label }}
        </text>
        <path :d="areaPath" :fill="props.fill" />
        <path :d="linePath" :stroke="props.stroke" class="line-chart__path" />
        <circle
            v-for="point in normalizedPoints"
            :key="`${point.x}-${point.y}`"
            :cx="point.x"
            :cy="point.y"
            r="4.5"
            :fill="props.stroke"
            class="line-chart__dot"
        />
        <text
            v-for="(label, index) in props.labels"
            :key="`${label}-${index}`"
            :x="normalizedPoints[index]?.x || padding.left"
            :y="props.height - 10"
            text-anchor="middle"
            class="line-chart__label"
        >
            {{ label }}
        </text>
    </svg>
</template>
