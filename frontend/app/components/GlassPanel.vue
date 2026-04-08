<script setup>
const props = defineProps({
    padded: {
        type: Boolean,
        default: true,
    },
    tone: {
        type: String,
        default: "default",
    },
});
</script>

<template>
    <section :class="['glass-panel', `tone-${props.tone}`, props.padded ? 'is-padded' : '']">
        <slot />
    </section>
</template>
