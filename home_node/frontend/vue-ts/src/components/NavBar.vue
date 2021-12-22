<template>
  <nav class="navbar navbar-expand-md navbar-dark bg-dark">
    <div class="container">
      <a class="navbar-brand" href="/">FastAPI + Vue</a>
      <button
        class="navbar-toggler"
        type="button"
        data-bs-toggle="collapse"
        data-bs-target="#navbarCollapse"
        aria-controls="navbarCollapse"
        aria-expanded="false"
        aria-label="Toggle navigation"
      >
        <span class="navbar-toggler-icon"></span>
      </button>
      <div class="collapse navbar-collapse" id="navbarCollapse">
        <ul v-if="isLoggedIn" class="navbar-nav me-auto mb-2 mb-md-0">
          <li class="nav-item">
            <router-link class="nav-link" to="/">Home</router-link>
          </li>
          <li class="nav-item">
            <router-link class="nav-link" to="/profile">My Profile</router-link>
          </li>
          <li class="nav-item">
            <a class="nav-link" @click="logout">Log Out</a>
          </li>
        </ul>
        <ul v-else class="navbar-nav me-auto mb-2 mb-md-0">
          <li class="nav-item">
            <router-link class="nav-link" to="/">Home</router-link>
          </li>
          <li class="nav-item">
            <a class="nav-link" href="#" @click="toggleModal">Log in</a>
          </li>
        </ul>
      </div>
    </div>
  </nav>

  <LoginModal @close="toggleModal" :modalActive="modalActive">
    <div class="log-modal-content">
      <h1>Modal header</h1>
      <p>message modal</p>
    </div>
  </LoginModal>
</template>

<script>
import LoginModal from "@/components/LoginModal";
import { ref } from "vue";
export default {
  name: "NavBar",
  components: { LoginModal },
  setup() {
    const modalActive = ref(false);

    const toggleModal = () => {
      modalActive.value = !modalActive.value;
    };

    return { modalActive, toggleModal };
  },
  //   computed: {
  //     isLoggedIn: function() {
  //       return this.$store.getters.isAuthenticated;
  //     }
  //   },
  //   methods: {
  //     async logout () {
  //       await this.$store.dispatch('logOut');
  //       this.$router.push('/login');
  //     }
  //   },
};
</script>

<style scoped>
a {
  cursor: pointer;
}
</style>