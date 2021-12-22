
<template>
  <transition name="log-modal-animation">
    <div v-show="modalActive" class="log-modal">
      <transition name="log-modal-animation-inner">
        <div v-show="modalActive" class="log-modal-inner">
          <a @click="close" href="#" class="close" />
          <!-- Modal content -->
          <slot />
          <button @click="close" type="button">Close</button>
        </div>
      </transition>
    </div>
  </transition>
</template>

<script>
export default {
  name: "LoginModal",
  props: {
    modalActive: Boolean,
  },
  setup(props, { emit }) {
    const close = () => {
      emit("close");
    };
    return { close };
  },
};
</script>


<style>
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
  padding: 50px;
  border-radius: 10px;
}
</style>