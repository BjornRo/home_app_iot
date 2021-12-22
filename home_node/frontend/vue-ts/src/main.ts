import 'bootstrap/dist/css/bootstrap.css';
import axios from 'axios';
import Vue from 'vue';

import App from './App.vue';
import router from './router.vue';
// import store from './store';

axios.defaults.withCredentials = true;
axios.defaults.baseURL = `${location.origin}:8000/`;  // the FastAPI backend
