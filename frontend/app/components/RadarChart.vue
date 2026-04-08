<script setup>
const { computed } = Vue;
const { clamp } = window.AppModules.utils;

const props = defineProps({
    items: {
        type: Array,
        default: () => [],
    },
    maxValue: {
        type: Number,
        default: 100,
    },
    size: {
        type: Number,
        default: 300,
    },
    stroke: {
        type: String,
        default: "#3B82F6",
    },
    fill: {
        type: String,
        default: "rgba(59, 130, 246, 0.18)",
    },
});

const center = computed(() => props.size / 2);
const radius = computed(() => props.size / 2 - 42);
const isPolygonal = computed(() => props.items.length >= 3);

const rings = computed(() => [0.25, 0.5, 0.75, 1].map((ratio) => polygonPoints(ratio)));

const spokes = computed(() => {
    return props.items.map((_, index) => pointAt(index, 1));
});

const dataPolygon = computed(() => {
    if (!props.items.length) return "";
    return props.items
        .map((item, index) => {
            const ratio = clamp(Number(item.value || 0), 0, props.maxValue) / props.maxValue;
            const point = pointAt(index, ratio);
            return `${point.x},${point.y}`;
        })
        .join(" ");
});

function angleAt(index) {
    return (-Math.PI / 2) + (Math.PI * 2 * index) / Math.max(props.items.length, 1);
}

function pointAt(index, ratio) {
    const angle = angleAt(index);
    const r = radius.value * ratio;
    return {
        x: center.value + Math.cos(angle) * r,
        y: center.value + Math.sin(angle) * r,
    };
}

function polygonPoints(ratio) {
    return props.items
        .map((_, index) => {
            const point = pointAt(index, ratio);
            return `${point.x},${point.y}`;
        })
        .join(" ");
}
</script>

<template>
    <svg class="radar-chart" :viewBox="`0 0 ${props.size} ${props.size}`">
        <polygon
            v-if="isPolygonal"
            v-for="ring in rings"
            :key="ring"
            :points="ring"
            class="radar-chart__ring"
        />
        <line
            v-for="(point, index) in spokes"
            :key="`${point.x}-${index}`"
            :x1="center"
            :y1="center"
            :x2="point.x"
            :y2="point.y"
            class="radar-chart__spoke"
        />
        <polygon
            v-if="isPolygonal"
            :points="dataPolygon"
            :fill="props.fill"
            :stroke="props.stroke"
            class="radar-chart__area"
        />
        <text
            v-for="(item, index) in props.items"
            :key="item.label"
            :x="pointAt(index, 1.16).x"
            :y="pointAt(index, 1.16).y"
            text-anchor="middle"
            class="radar-chart__label"
        >
            {{ item.label }}
        </text>
    </svg>
</template>
