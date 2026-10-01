async function checkService() {
  const status = document.getElementById("service-status");
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), 5000);
  try {
    const response = await fetch("/api/health/live", { signal: controller.signal });
    if (!response.ok) throw new Error("Service unavailable");
    const result = await response.json();
    if (result.status !== "ok") throw new Error("Unexpected response");
    status.textContent = "网站连接正常";
  } catch {
    status.textContent = "暂时无法连接服务，请稍后刷新页面。";
  } finally {
    clearTimeout(timer);
  }
}
checkService();
