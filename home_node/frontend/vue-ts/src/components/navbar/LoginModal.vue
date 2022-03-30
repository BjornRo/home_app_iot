<template>
    <transition name="fade" appear>
        <div class="modal-overlay" v-if="visible" v-on:click="toggleModal" />
    </transition>
    <div class="modal" v-if="visible">
        <form @submit.prevent="submit">
            <div class="form_div">
                <div class="input-group">
                    <div class="input-group-icon"><i class="gg-user"></i></div>
                    <BaseInput
                        v-model="this.username"
                        class="input-group-area field"
                        type="text"
                        placeholder="Username"
                        label="Username"
                        required
                    />
                </div>
                <div class="input-group">
                    <div class="input-group-icon"><i class="gg-lock"></i></div>
                    <BaseInput
                        v-model="this.password"
                        class="input-group-area field"
                        type="password"
                        placeholder="********"
                        label="Password"
                        required
                    />
                </div>
            </div>
            <div class="btn_grp">
                <a class="button bg-deny" v-on:click="setModal(false)" text="Cancel" />
                <button class="button bg-accept">Login</button>
            </div>
        </form>
        <a v-on:click="setModal(false)" text="Login" />
    </div>
    <a class="button openmodal" v-on:click="setModal(true)">Login</a>
</template>

<script lang="ts">
import { Options, Vue } from "vue-class-component";
import AuthService from "@/services/auth.service";
import BaseInput from "../BaseInput.vue";
import AuthHeader from "@/services/auth-header";

@Options({
    components: { AuthHeader, BaseInput },
    emits: ["login"],
})
export default class LoginModal extends Vue {
    visible = false;
    username = "";
    password = "";

    async submit() {
        let formdata = new FormData();
        formdata.append("username", this.username);
        formdata.append("password", this.password);
        const resp = await AuthService.login(formdata);
        if (resp === null) {
            alert("Login failed");
            return false;
        }
        this.setModal(false);
        this.$emit("login");
        return true;
    }

    toggleModal() {
        this.visible = !this.visible;
    }
    setModal(b: boolean) {
        this.visible = b;
    }
}
</script>

<style lang="scss" scoped>
.openmodal {
    outline: 0;
    border: 1px solid green;
    position: relative;
    top: 16px;
}
.form_div {
    position: absolute;
    width: 300px;
    right: 50%;
    transform: translate(48%);
}
.input-group {
    display: table;
    margin-top: 4px;
    border-collapse: collapse;
    text-align: center;
}
.input-group > div {
    display: table-cell;
    vertical-align: middle; /* needed for Safari */
}
.input-group-icon {
    background: rgb(199, 199, 199);
    color: rgb(134, 134, 134);
    padding: 0 12px;
}
.input-group-area {
    font-size: 18pt;
}
.input-group input {
    border: 0;
    background-color: rgb(230, 230, 230);
    display: block;
    width: 100%;
    padding: 8px;
}
.btn_grp {
    position: absolute;
    bottom: 12px;
    left: 50%;
    width: 100%;
    transform: translate(-50%);
}
.button {
    appearance: none;
    outline: none;
    cursor: pointer;

    padding: 8px 14px;
    border-radius: 10px;
    font-size: 24px;
    margin-left: 6px;
    margin-right: 6px;
    color: rgb(92, 92, 92);
}
.modal-overlay {
    position: absolute;
    top: 0;
    left: 0;
    right: 0;
    bottom: 0;
    z-index: 1000;

    background-color: rgba(0, 0, 0, 0.6);
}
.modal {
    border: 3px solid rgb(66, 66, 66);
    position: fixed;
    top: 50%;
    left: 50%;
    transform: translate(-50%, -50%);
    z-index: 1001;

    width: 100%;
    max-width: 300px;
    height: 100%;
    max-height: 160px;
    background-color: rgb(255, 255, 255);
    border-radius: 24px;

    padding: 25px;
}
.bg-deny {
    border: 2px solid red;
    background-color: rgba(255, 87, 87, 0.746);
}
.bg-accept {
    border: 2px solid green;
    background-color: rgb(104, 207, 138);
}
.bg-accept:hover {
    background-color: rgb(0, 156, 55);
}
.bg-deny:hover {
    background-color: rgba(255, 20, 20, 0.746);
}
.fade-enter-active,
.fade-leave-active {
    transition: opacity 0.6s;
}
.fade-enter-from,
.fade-leave-to {
    opacity: 0;
}
.gg-user {
    display: block;
    transform: scale(var(--ggs, 1));
    box-sizing: border-box;
    width: 12px;
    height: 18px;
}
.gg-user::after,
.gg-user::before {
    content: "";
    display: block;
    box-sizing: border-box;
    position: absolute;
    border: 2px solid;
}
.gg-user::before {
    width: 8px;
    height: 8px;
    border-radius: 30px;
    top: 0;
    left: 2px;
}
.gg-user::after {
    width: 12px;
    height: 9px;
    border-bottom: 0;
    border-top-left-radius: 3px;
    border-top-right-radius: 3px;
    top: 9px;
}
.gg-lock {
    box-sizing: border-box;
    position: relative;
    display: block;
    transform: scale(var(--ggs, 1));
    width: 12px;
    height: 11px;
    border: 2px solid;
    border-top-right-radius: 50%;
    border-top-left-radius: 50%;
    border-bottom: transparent;
    margin-top: -12px;
}
.gg-lock::after {
    content: "";
    display: block;
    box-sizing: border-box;
    position: absolute;
    width: 16px;
    height: 10px;
    border-radius: 2px;
    border: 2px solid transparent;
    box-shadow: 0 0 0 2px;
    left: -4px;
    top: 9px;
}
</style>
