
<template>
  <transition name="log-modal-animation">
    <div v-show="modalActive" class="log-modal">
      <transition name="log-modal-animation-inner">
        <div v-show="modalActive" class="log-modal-inner">
          <a @click="toggle" href="#" class="close" />
          <form @submit.prevent="onSubmit" class="m-2" @submit="checkForm">
            <div class="input-group">
              <div class="input-group-text"><i class="gg-user"></i></div>
              <input
                id="user"
                v-model="user"
                class="form-control"
                placeholder="Email or login"
                type="email"
              />
            </div>
            <div class="input-group boxwidth">
              <div class="input-group-text"><i class="gg-lock"></i></div>
              <input
                id="pass"
                v-model="pass"
                class="form-control"
                placeholder="******"
                type="password"
              />
            </div>
            <button
              id="submit_data"
              type="submit"
              class="btn btn-primary btn-block mt-2"
            >
              Submit
            </button>
          </form>
        </div>
      </transition>
    </div>
  </transition>
</template>

<script>
import axios from "axios";
export default {
  name: "LoginModal",
  props: {
    modalActive: Boolean,
  },
  data() {

  },
  setup(props, { emit }) {
    const toggle = () => {
      emit("toggle");
    };
    return { toggle };
  },
};
</script>


<style scoped>
.boxwidth {
    width: 320px;
}

.close {
  position: absolute;
  right: 32px;
  top: 64px;
  width: 32px;
  height: 32px;
  opacity: 0.3;
}
.close:hover {
  opacity: 1;
}
.close:before,
.close:after {
  position: absolute;
  left: 15px;
  content: " ";
  height: 33px;
  width: 2px;
  background-color: #333;
}
.close:before {
  transform: rotate(45deg);
}
.close:after {
  transform: rotate(-45deg);
}
.root {
  position: relative;
}

.log-modal {
  position: absolute;
  top: 0;
  left: 0;
  background-color: rgba(0, 0, 0, 0.1);
  width: 100%;
  height: 100%;
  display: flex;
  justify-content: center;
  align-items: center;
}

.log-modal > div {
  background-color: #fff;
  padding: 24px;
  border-radius: 10px;
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

</style>