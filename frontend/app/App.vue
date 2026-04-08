<script setup>
const { computed } = Vue;
const { useRoute } = VueRouter;

const route = useRoute();
const showNavigation = computed(() => route.name !== "login");
const themeClass = computed(() => route.meta.theme === "dark" ? "theme-dark" : "theme-light");
</script>

<template>
    <div :class="['app-root', themeClass]">
        <div class="app-background">
            <div class="app-background__orb orb-a"></div>
            <div class="app-background__orb orb-b"></div>
            <div class="app-background__grid"></div>
        </div>

        <div v-if="showNavigation" class="app-frame">
            <AppNavigation />
            <main class="app-content">
                <RouterView />
            </main>
        </div>

        <RouterView v-else />
    </div>
</template>
