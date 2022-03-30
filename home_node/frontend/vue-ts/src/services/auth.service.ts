import axios, { AxiosError } from "axios";
import AuthHeader from "./auth-header";

const API_URL = process.env.VUE_APP_API + "/auth";

class AuthService {
    async login(user_data: FormData) {
        try {
            const response = await axios.post(API_URL + "/token", user_data);
            if (response.status < 300) {
                if (response.data.access_token) {
                    localStorage.setItem("user", JSON.stringify(response.data));
                }
                return response.data;
            }
        } catch (e) {
            return null;
        }
        return null;
    }

    logout() {
        localStorage.removeItem("user");
    }

    async me_info() {
        const token = AuthHeader.get_token();
        if (token !== null) {
            const headers = { headers: token };
            try {
                const response = await axios.get(API_URL + "/me", headers);
                if (response.status < 300) {
                    return response.data;
                }
            } catch (e) {
                const err = e as AxiosError;
                if (err.response?.status === 401) {
                    this.logout();
                }
            }
        }
        return null;
    }

    // register(user) {
    //     return axios.post(API_URL + "signup", {
    //         username: user.username,
    //         email: user.email,
    //         password: user.password
    //     });
    // }
}

export default new AuthService();
