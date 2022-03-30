<template>
    <div class="auth" v-if="!token">
        <LoginModal @login="me_info" />
    </div>
    <div class="auth_info" v-else>{{ this.info }}</div>
</template>

<script>
import { Options, Vue } from "vue-class-component";
import LoginModal from "./LoginModal.vue";
import AuthHeader from "@/services/auth-header";
import AuthService from "@/services/auth.service";

@Options({
    components: { LoginModal, AuthHeader },
    props: {},
    emits: ["auth_event"],
})
export default class LoginStatus extends Vue {
    token = AuthHeader.get_token();
    info = null;

    async me_info() {
        const user_data = await AuthService.me_info();
        this.$emit("auth_event");
        if (user_data === null) {
            this.token = null;
            this.info = null;
            return;
        }
        this.token = AuthHeader.get_token();
        this.info = user_data;
    }

    mounted() {
        this.me_info();
    }
}
</script>
<style lang="scss" scoped>
.auth_info {
    float: right;
    width: 150px;
    font-size: 11px;
    height: auto;
    background-color: rgb(0, 0, 0);
    border: 1px solid red;
}
.auth {
    float: right;
    width: 150px;
    height: auto;
    background-color: rgb(0, 0, 0);
    border: 1px solid red;
}
</style>
