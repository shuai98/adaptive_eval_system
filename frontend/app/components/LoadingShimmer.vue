<script setup>
const props = defineProps({
    lines: {
        type: Number,
        default: 4,
    },
    compact: {
        type: Boolean,
        default: false,
    },
});
</script>

<template>
    <div :class="['loading-shimmer', props.compact ? 'is-compact' : '']">
        <span
            v-for="line in props.lines"
            :key="line"
            class="loading-shimmer__line"
            :style="{ width: `${line === props.lines ? 68 : 100 - (line % 3) * 10}%` }"
        />
    </div>
</template>
