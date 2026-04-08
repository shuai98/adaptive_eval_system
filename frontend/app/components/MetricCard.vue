<script setup>
const props = defineProps({
    label: {
        type: String,
        required: true,
    },
    value: {
        type: String,
        required: true,
    },
    hint: {
        type: String,
        default: "",
    },
    accent: {
        type: String,
        default: "blue",
    },
    delta: {
        type: String,
        default: "",
    },
});
</script>

<template>
    <GlassPanel class="metric-card" :class="`accent-${props.accent}`">
        <div class="metric-card__top">
            <div class="metric-card__icon">
                <slot name="icon">
                    <span>{{ props.label.slice(0, 1) }}</span>
                </slot>
            </div>
            <span v-if="props.delta" class="metric-card__delta">{{ props.delta }}</span>
        </div>
        <div class="metric-card__label">{{ props.label }}</div>
        <div class="metric-card__value">{{ props.value }}</div>
        <div class="metric-card__hint">{{ props.hint }}</div>
    </GlassPanel>
</template>
