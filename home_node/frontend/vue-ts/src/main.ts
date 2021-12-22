import axios from 'axios';
import * as Vue from 'vue';

import App from './App.vue';
import router from './router';

axios.defaults.withCredentials = true;
axios.defaults.baseURL = `${location.origin}:8000/`;  // the FastAPI backend

Vue.createApp(App)
  .use(router)
  .mount('#app')