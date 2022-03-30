<template>
    <NavBar />
    <router-view />
</template>

<script lang="ts">
import { Options, Vue } from "vue-class-component";
import NavBar from "./components/navbar/NavBar.vue";

@Options({
    name: "App",
    components: { NavBar },
    props: {},
})
export default class App extends Vue {}
</script>

<style lang="scss">
#app {
    font-family: Avenir, Arial, Arial, sans-serif;
    -webkit-font-smoothing: antialiased;
    -moz-osx-font-smoothing: grayscale;
    text-align: center;
    color: #2c3e50;
}

nav {
    padding: 30px;
    a {
        font-weight: bold;
        color: #2c3e50;

        &.router-link-exact-active {
            color: #42b983;
        }
    }
}
</style>
