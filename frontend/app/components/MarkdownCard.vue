<script setup>
const { computed } = Vue;
const { renderMarkdown } = window.AppModules.utils;

const props = defineProps({
    content: {
        type: String,
        default: "",
    },
});

const html = computed(() => renderMarkdown(props.content));

const copyCode = async (event) => {
    const button = event.target.closest(".markdown-copy-button");
    if (!button) return;
    const shell = button.closest(".markdown-code-shell");
    const code = shell?.querySelector("code");
    if (!code) return;
    await navigator.clipboard.writeText(code.innerText);
    button.textContent = "已复制";
    window.setTimeout(() => {
        button.textContent = "复制";
    }, 1200);
};
</script>

<template>
    <div class="markdown-card markdown-body" v-html="html" @click="copyCode" />
</template>
