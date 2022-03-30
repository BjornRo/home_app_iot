<template>
    <div class="navbar">
        <div class="links">
            <NavBarLink to="/">Home</NavBarLink>
            <NavBarLink to="/error">Error</NavBarLink>
        </div>
        <div class="links" v-if="authed !== null">
            <NavBarLink to="/dash">Dashboard</NavBarLink>
        </div>
        <div class="spacer"></div>
        <LoginStatus @auth_event="on_auth_event" />
    </div>
</template>

<script>
import { Options, Vue } from "vue-class-component";
import NavBarLink from "./NavBarLink.vue";
import LoginStatus from "./LoginStatus.vue";
import AuthHeader from "@/services/auth-header";

// TODO find some way to update navbar/navbar items in logged in without refresh. How to handle tokens, expired?
@Options({ components: { NavBarLink, LoginStatus }, props: {} })
export default class NavBar extends Vue {
    authed = AuthHeader.get_token();

    on_auth_event() {
        this.authed = AuthHeader.get_token();
    }
}
</script>

<style lang="scss" scoped>
.navbar {
    color: rgb(204, 204, 204);
    background-color: var(--navbar-bg-color);
    display: flex;

    flex-direction: row;
    padding: 2px;
    text-decoration: none;
    font-size: 24px;
    overflow: auto;
}
.links {
    float: left;
}

.spacer {
    flex: 1;
    border: 1px solid green;
}
</style>

<style lang="scss">
:root {
    --navbar-bg-color: #35aeff;
    --navbar-item-hover: #60bfff;
    --navbar-item-active: #15a1ff;
    --navbar-item-inactive: #2aaaff;
}
</style>
