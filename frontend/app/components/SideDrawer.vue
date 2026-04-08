<script setup>
const props = defineProps({
    open: {
        type: Boolean,
        default: false,
    },
    title: {
        type: String,
        default: "",
    },
    subtitle: {
        type: String,
        default: "",
    },
});

const emit = defineEmits(["close"]);
</script>

<template>
    <transition name="drawer-fade">
        <div v-if="props.open" class="drawer-mask" @click.self="emit('close')">
            <aside class="side-drawer">
                <header class="side-drawer__header">
                    <div>
                        <p class="eyebrow">个性化能力雷达图</p>
                        <h3>{{ props.title }}</h3>
                        <p class="side-drawer__subtitle">{{ props.subtitle }}</p>
                    </div>
                    <button class="ghost-button" type="button" @click="emit('close')">关闭</button>
                </header>
                <div class="side-drawer__body">
                    <slot />
                </div>
            </aside>
        </div>
    </transition>
</template>
