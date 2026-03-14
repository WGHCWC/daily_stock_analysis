// 生产环境使用相对路径（同源），开发环境也建议使用相对路径通过 Vite 代理访问后端
export const API_BASE_URL = import.meta.env.VITE_API_URL || '';
