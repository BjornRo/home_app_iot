<template>
    <div class="access"></div>
</template>

<script lang="ts">
import { Vue } from "vue-class-component";
import AuthHeader from "@/services/auth-header";

// TODO Make paths in backend with auth.

export default class DashView extends Vue {
    token = AuthHeader.get_token();
}
</script>
