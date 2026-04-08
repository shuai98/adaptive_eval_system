<script setup>
const props = defineProps({
    stages: {
        type: Array,
        default: () => [],
    },
});
</script>

<template>
    <div class="flow-rail">
        <div
            v-for="(stage, index) in props.stages"
            :key="stage.title"
            class="flow-rail__stage"
        >
            <div :class="['flow-rail__node', `accent-${stage.accent || 'blue'}`]">
                <small>{{ stage.kicker }}</small>
                <strong>{{ stage.title }}</strong>
                <span>{{ stage.copy }}</span>
            </div>
            <div v-if="index < props.stages.length - 1" class="flow-rail__arrow">→</div>
        </div>
    </div>
</template>
