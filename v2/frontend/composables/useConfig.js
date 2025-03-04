import { ref } from "vue";

const baseUrl = ref("localhost:8000");

export const useConfig = () => {
    return { baseUrl };
};
