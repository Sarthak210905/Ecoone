import axios from "axios";

const baseURL = import.meta.env.VITE_API_BASE || "http://127.0.0.1:8000";

const client = axios.create({
  baseURL,
  timeout: 10000,
  headers: {
    "X-Requested-With": "XMLHttpRequest",
  },
});

export default client;
