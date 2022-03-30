class AuthHeader {
    get_token() {
        const data = localStorage.getItem("user");
        // console.log($cookies.get())
        // TODO Cookies?
        if (data !== null) {
            const user = JSON.parse(data);
            if (user.access_token) {
                return { Authorization: "Bearer " + user.access_token };
            }
        }
        return null;
    }
}
export default new AuthHeader();
