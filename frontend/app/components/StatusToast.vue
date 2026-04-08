<script setup>
const props = defineProps({
    tone: {
        type: String,
        default: "info",
    },
    title: {
        type: String,
        default: "",
    },
    message: {
        type: String,
        default: "",
    },
});
</script>

<template>
    <transition name="toast">
        <div v-if="props.message" :class="['status-toast', `tone-${props.tone}`]">
            <strong v-if="props.title">{{ props.title }}</strong>
            <span>{{ props.message }}</span>
        </div>
    </transition>
</template>
