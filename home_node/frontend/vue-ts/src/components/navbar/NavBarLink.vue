<template>
    <router-link :to="to" class="link" :class="{ active: isActive }">
        <slot />
    </router-link>
</template>

<script lang="ts">
import { computed, defineComponent } from "vue";
import { useRoute } from "vue-router";

export default defineComponent({
    name: "Navbar_links",
    props: { to: { type: String, required: true } },
    setup(props) {
        const route = useRoute();
        const isActive = computed(() => route.path === props.to);
        return { isActive };
    },
});
</script>

<style lang="scss" scoped>
.link {
    color: rgb(250, 250, 250);
    background-color: var(--navbar-item-inactive);

    float: left;
    text-align: center;
    padding: 14px 16px;
    margin: 4px;
    border-radius: 10px;
    border: 1px solid rgba(46, 102, 255, 0.397);
    text-decoration: none;
}
.link:hover {
    background-color: var(--navbar-item-hover);
}
.link:active {
    background-color: var(--navbar-item-active);
}
</style>
