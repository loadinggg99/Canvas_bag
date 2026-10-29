// app/frontend/js/app.js —— 页面逻辑（原生 JS + fetch，无框架）
//
// 结构：标签页切换、导入、商品列表、利润分析、定价模拟。

// 请求封装：非 2xx 时抛出带 detail 的错误
async function request(url, options = {}) {
    const resp = await fetch(url, options);
    if (!resp.ok) {
        let detail = `HTTP ${resp.status}`;
        try {
            const body = await resp.json();
            detail = body.detail || detail;
        } catch (_) { /* 非 JSON 响应 */ }
        throw new Error(detail);
    }
    return resp.json();
}

function fmtMoney(value) {
    const n = Number(value);
    return Number.isNaN(n) ? "-" : n.toLocaleString("zh-CN", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
}

function fmtPercent(value) {
    const n = Number(value);
    return Number.isNaN(n) ? "-" : (n * 100).toFixed(2) + "%";
}

function showResult(el, data) {
    el.textContent = JSON.stringify(data, null, 2);
    el.hidden = false;
}

const $ = (id) => document.getElementById(id);

function showFrontendError(message) {
    const status = $("analytics-status");
    if (status) status.textContent = message;
}

// 页面脚本或请求出现未处理异常时，至少给出可见提示，避免“点了没反应”
window.addEventListener("error", () => {
    showFrontendError("页面脚本异常，请强制刷新（Cmd+Shift+R）后重试");
});
window.addEventListener("unhandledrejection", () => {
    showFrontendError("请求异常，请强制刷新（Cmd+Shift+R）后重试");
});

// 先转义再拼接 HTML，避免商品数据或模型输出被当成标签执行
function escapeHtml(value) {
    return String(value ?? "")
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;")
        .replace(/"/g, "&quot;")
        .replace(/'/g, "&#039;");
}

function inlineMarkdown(text) {
    let html = escapeHtml(text);
    html = html.replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>");
    html = html.replace(/`([^`]+)`/g, "<code>$1</code>");
    return html;
}

function splitTableRow(line) {
    return line.trim()
        .replace(/^\|/, "")
        .replace(/\|$/, "")
        .split("|")
        .map((cell) => inlineMarkdown(cell.trim()));
}

function isTableSeparator(line) {
    return line.includes("-") && /^[|:\-\s]+$/.test(line.trim());
}

// 只支持 AI 常用的 Markdown：标题、粗体、列表、表格。
// 不引入第三方库，也不允许模型输出原始 HTML。
function renderMarkdown(markdown) {
    const lines = String(markdown || "").replace(/\r\n/g, "\n").split("\n");
    const html = [];
    let listType = null;

    const closeList = () => {
        if (listType) {
            html.push(`</${listType}>`);
            listType = null;
        }
    };

    for (let i = 0; i < lines.length; i++) {
        const line = lines[i].trim();
        if (!line) {
            closeList();
            continue;
        }

        if (/^-{3,}$/.test(line)) {
            closeList();
            html.push("<hr>");
            continue;
        }

        const quote = line.match(/^>\s?(.*)$/);
        if (quote) {
            closeList();
            html.push(`<blockquote>${inlineMarkdown(quote[1])}</blockquote>`);
            continue;
        }

        // 表格：表头 + |---|---| 分隔行
        if (line.includes("|") && i + 1 < lines.length && isTableSeparator(lines[i + 1])) {
            closeList();
            const headers = splitTableRow(line);
            i += 1;

            const rows = [];
            while (i + 1 < lines.length && lines[i + 1].includes("|") && !isTableSeparator(lines[i + 1])) {
                i += 1;
                rows.push(splitTableRow(lines[i]));
            }

            html.push("<table><thead><tr>");
            headers.forEach((header) => html.push(`<th>${header}</th>`));
            html.push("</tr></thead><tbody>");
            rows.forEach((row) => {
                html.push("<tr>");
                headers.forEach((_, index) => html.push(`<td>${row[index] || ""}</td>`));
                html.push("</tr>");
            });
            html.push("</tbody></table>");
            continue;
        }

        const heading = line.match(/^(#{1,4})\s+(.*)$/);
        if (heading) {
            closeList();
            const level = Math.min(6, heading[1].length + 1);
            html.push(`<h${level}>${inlineMarkdown(heading[2])}</h${level}>`);
            continue;
        }

        const bullet = line.match(/^[-*]\s+(.*)$/);
        if (bullet) {
            if (listType !== "ul") {
                closeList();
                html.push("<ul>");
                listType = "ul";
            }
            html.push(`<li>${inlineMarkdown(bullet[1])}</li>`);
            continue;
        }

        const ordered = line.match(/^\d+\.\s+(.*)$/);
        if (ordered) {
            if (listType !== "ol") {
                closeList();
                html.push("<ol>");
                listType = "ol";
            }
            html.push(`<li>${inlineMarkdown(ordered[1])}</li>`);
            continue;
        }

        closeList();
        html.push(`<p>${inlineMarkdown(line)}</p>`);
    }

    closeList();
    return html.join("");
}

// 接口里的排序字段是英文标识，展示时换成与表格一致的中文列名
const FIELD_LABELS = {
    product_code: "货号",
    pdd_sale_price: "拼多多售价",
    pdd_profit: "PDD毛利",
    profit_margin: "毛利率",
};

// ============ 标签页切换 ============
const tabs = document.querySelectorAll(".tab");
const panels = document.querySelectorAll(".panel");

tabs.forEach((tab) => {
    tab.addEventListener("click", () => {
        tabs.forEach((t) => t.classList.remove("active"));
        tab.classList.add("active");
        const name = tab.dataset.tab;
        panels.forEach((p) => p.classList.remove("active"));
        $("tab-" + name).classList.add("active");
        if (name === "products") loadProducts();
        if (name === "analytics") loadAnalytics();
    });
});

// ============ 导入数据 ============
async function loadFiles() {
    const files = await request("/api/files");
    const select = $("file-select");
    select.innerHTML = "";
    files.forEach((f) => {
        const opt = document.createElement("option");
        opt.value = f.filename;
        opt.textContent = `${f.filename}（${(f.size_bytes / 1024).toFixed(1)} KB）`;
        select.appendChild(opt);
    });
    if (files.length === 0) select.innerHTML = '<option value="">没有可用文件</option>';
}

$("btn-import").addEventListener("click", async () => {
    const filename = $("file-select").value;
    if (!filename) return;
    const btn = $("btn-import");
    btn.disabled = true;
    btn.textContent = "导入中……";
    try {
        const result = await request("/api/import", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ filename }),
        });
        showResult($("import-result"), { 状态: "成功", ...result });
    } catch (err) {
        showResult($("import-result"), { 状态: "失败", 错误: err.message });
    } finally {
        btn.disabled = false;
        btn.textContent = "开始导入";
    }
});

// ============ 商品列表 ============
const PAGE_SIZE = 20;
let productPage = 1;

async function loadProducts() {
    const search = $("product-search").value.trim();
    const url = new URL("/api/products", location.origin);
    if (search) url.searchParams.set("search", search);
    url.searchParams.set("page", productPage);
    url.searchParams.set("page_size", PAGE_SIZE);

    const data = await request(url);
    const total = data.total;

    const tbody = $("product-tbody");
    tbody.innerHTML = "";
    if (data.items.length === 0) {
        tbody.innerHTML = '<tr><td colspan="10" class="empty">没有匹配的商品</td></tr>';
    } else {
        data.items.forEach((p) => {
            const tr = document.createElement("tr");
            tr.innerHTML = `
                <td>${escapeHtml(p.product_code)}</td>
                <td>${fmtMoney(p.tag_price)}</td>
                <td>${fmtMoney(p.settlement_price)}</td>
                <td>${fmtMoney(p.fee)}</td>
                <td>${fmtMoney(p.pdd_sale_price)}</td>
                <td>${fmtMoney(p.pdd_gross_profit)}</td>
                <td>${fmtMoney(p.agent_settlement_price)}</td>
                <td>${p.agent_discount}</td>
                <td>${fmtMoney(p.agent_profit)}</td>
                <td>${fmtMoney(p.own_profit)}</td>`;
            tbody.appendChild(tr);
        });
    }

    const maxPage = Math.max(1, Math.ceil(total / PAGE_SIZE));
    $("page-info").textContent = `第 ${productPage} / ${maxPage} 页，共 ${total} 条`;
    $("btn-prev").disabled = productPage <= 1;
    $("btn-next").disabled = productPage >= maxPage;
}

$("btn-search").addEventListener("click", () => { productPage = 1; loadProducts(); });
$("product-search").addEventListener("keydown", (e) => { if (e.key === "Enter") { productPage = 1; loadProducts(); } });
$("btn-prev").addEventListener("click", () => { if (productPage > 1) { productPage--; loadProducts(); } });
$("btn-next").addEventListener("click", () => { productPage++; loadProducts(); });

// ============ 利润分析 ============
function renderAnalytics(data) {
    const sortByLabel = FIELD_LABELS[data.sort_by] || data.sort_by;

    $("analytics-summary").innerHTML = `
        <div class="card"><div class="value">${data.total}</div><div class="label">商品总数</div></div>
        <div class="card"><div class="value">${escapeHtml(sortByLabel)}</div><div class="label">排序字段</div></div>`;

    const tbody = $("analytics-tbody");
    tbody.innerHTML = "";
    if (!data.items || data.items.length === 0) {
        tbody.innerHTML = '<tr><td colspan="5" class="empty">暂无数据，请先导入</td></tr>';
    } else {
        data.items.forEach((it) => {
            const tr = document.createElement("tr");
            const anomaly = it.anomalies && it.anomalies.length > 0
                ? it.anomalies.map((a) => `<span class="badge ${escapeHtml(a.severity)}">${escapeHtml(a.message)}</span>`).join(" ")
                : '<span class="badge ok">正常</span>';
            tr.innerHTML = `
                <td>${escapeHtml(it.product_code)}</td>
                <td>${fmtMoney(it.pdd_sale_price)}</td>
                <td>${fmtMoney(it.pdd_profit)}</td>
                <td>${fmtPercent(it.profit_margin)}</td>
                <td>${anomaly}</td>`;
            tbody.appendChild(tr);
        });
    }
}

function renderAnalyticsError(message) {
    $("analytics-summary").innerHTML = "";
    $("analytics-tbody").innerHTML =
        `<tr><td colspan="5" class="empty">数据加载失败：${escapeHtml(message)}</td></tr>`;
}

async function loadAnalytics() {
    try {
        const data = await request("/api/analytics");
        renderAnalytics(data);
    } catch (err) {
        renderAnalyticsError(err.message);
    }
}

// 点击“分析”时交给 Agent 的固定任务
const ANALYTICS_AI_PROMPT = `请对当前数据库中的全部商品做一次整体利润分析，并生成中文报告。
要求：
1. 先给整体结论；
2. 说明商品总数、平均毛利、最高毛利、最低毛利和负毛利数量；
3. 分析毛利最高和最低的重点商品；
4. 指出负毛利或低毛利风险；
5. 最后给出可执行的经营建议。
只使用工具返回的数据，不要编造；金额保留两位小数，毛利率用百分比表示。`;

function renderAgentAnalysis(data) {
    const card = $("analytics-ai");
    const tools = $("analytics-ai-tools");
    const content = $("analytics-ai-content");

    if (!card || !tools || !content) {
        showFrontendError("页面版本过旧，请强制刷新（Cmd+Shift+R）后重试");
        return;
    }

    tools.textContent = data.used_tools && data.used_tools.length > 0
        ? `本轮工具：${data.used_tools.join("、")}`
        : "本轮未调用工具";
    content.innerHTML = renderMarkdown(data.reply || "");
    card.hidden = false;
}

function renderAgentAnalysisError(message) {
    const card = $("analytics-ai");
    const tools = $("analytics-ai-tools");
    const content = $("analytics-ai-content");

    if (!card || !tools || !content) {
        showFrontendError("页面版本过旧，请强制刷新（Cmd+Shift+R）后重试");
        return;
    }

    tools.textContent = "";
    content.innerHTML =
        `<p class="ai-error">AI 分析失败：${escapeHtml(message)}</p>`;
    card.hidden = false;
}

async function runAnalyticsWithAI() {
    const btn = $("btn-analytics");
    const status = $("analytics-status");

    btn.disabled = true;
    btn.textContent = "分析中……";
    status.textContent = "正在加载数据并调用模型分析，请稍候……";
    const aiCard = $("analytics-ai");
    if (aiCard) aiCard.hidden = true;

    try {
        // 两个请求并行；表格先返回就先渲染，AI 结果到了再单独更新
        const analyticsTask = request("/api/analytics")
            .then((data) => renderAnalytics(data))
            .catch((err) => renderAnalyticsError(err?.message || "未知错误"));

        const agentTask = request("/api/agent/chat", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ message: ANALYTICS_AI_PROMPT }),
        })
            .then((data) => renderAgentAnalysis(data))
            .catch((err) => renderAgentAnalysisError(err?.message || "未知错误"));

        await Promise.all([analyticsTask, agentTask]);
    } finally {
        btn.disabled = false;
        btn.textContent = "分析";
        status.textContent = "";
    }
}

$("btn-analytics").addEventListener("click", runAnalyticsWithAI);

// ============ 定价模拟 ============
function optionalNumber(value) {
    const v = value.trim();
    return v === "" ? null : Number(v);
}

// 把定价模拟结果渲染成卡片，而不是吐 JSON
function renderSimulation(data) {
    const change = Number(data.profit_change);
    const changeClass = change >= 0 ? "up" : "down";
    const changeText = (change >= 0 ? "+" : "") + fmtMoney(change);
    const violations = (data.violations || [])
        .map((v) => `<li>${escapeHtml(v.message)}</li>`)
        .join("");

    $("simulation-result").innerHTML = `
        <div class="sim-card">
            <div class="sim-head">货号：${escapeHtml(data.product_code)}</div>
            <div class="sim-grid">
                <div class="sim-item"><span class="sim-label">原售价</span><span class="sim-value">${fmtMoney(data.original_price)}</span></div>
                <div class="sim-item"><span class="sim-label">模拟售价</span><span class="sim-value strong">${fmtMoney(data.target_price)}</span></div>
                <div class="sim-item"><span class="sim-label">原毛利</span><span class="sim-value">${fmtMoney(data.original_profit)}</span></div>
                <div class="sim-item"><span class="sim-label">模拟后毛利</span><span class="sim-value strong">${fmtMoney(data.simulated_profit)}</span></div>
                <div class="sim-item"><span class="sim-label">毛利变化</span><span class="sim-value ${changeClass}">${changeText}</span></div>
                <div class="sim-item"><span class="sim-label">毛利率</span><span class="sim-value">${fmtPercent(data.profit_margin)}</span></div>
            </div>
            <div class="sim-status ${data.feasible ? "ok" : "bad"}">${data.feasible ? "✓ 可行" : "✗ 不可行"}</div>
            ${violations ? `<ul class="sim-violations">${violations}</ul>` : ""}
        </div>`;
    $("simulation-result").hidden = false;
}

function renderSimulationError(msg) {
    $("simulation-result").innerHTML = `<div class="sim-card"><div class="sim-status bad">${escapeHtml(msg)}</div></div>`;
    $("simulation-result").hidden = false;
}

$("btn-simulate").addEventListener("click", async () => {
    const payload = {
        product_code: $("sim-code").value.trim(),
        target_price: Number($("sim-price").value),
        target_margin: optionalNumber($("sim-margin").value),
        min_price: optionalNumber($("sim-min").value),
        max_price: optionalNumber($("sim-max").value),
    };

    if (!payload.product_code || Number.isNaN(payload.target_price)) {
        renderSimulationError("请填写货号和模拟售价");
        return;
    }

    try {
        const data = await request("/api/simulations", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(payload),
        });
        renderSimulation(data);
    } catch (err) {
        renderSimulationError("失败：" + err.message);
    }
});

// ============ AI 对话侧边栏 ============
const chatMessages = $("chat-messages");
const chatInput = $("chat-input");
const chatSend = $("chat-send");

let chatThreadId = null;
let chatSending = false;

function appendChatMessage(role, text, { html = false, tools = [] } = {}) {
    const wrapper = document.createElement("div");
    wrapper.className = `chat-message ${role}`;

    const bubble = document.createElement("div");
    bubble.className = "chat-bubble";
    if (html) {
        bubble.classList.add("ai-content");
        bubble.innerHTML = text;
    } else {
        bubble.textContent = text;
    }
    wrapper.appendChild(bubble);

    if (tools.length > 0) {
        const meta = document.createElement("div");
        meta.className = "chat-meta";
        meta.textContent = `本轮工具：${tools.join("、")}`;
        wrapper.appendChild(meta);
    }

    chatMessages.appendChild(wrapper);
    chatMessages.scrollTop = chatMessages.scrollHeight;
    return wrapper;
}

function appendChatTyping() {
    const wrapper = document.createElement("div");
    wrapper.className = "chat-message assistant";

    const bubble = document.createElement("div");
    bubble.className = "chat-bubble chat-typing";
    bubble.textContent = "正在思考……";
    wrapper.appendChild(bubble);

    chatMessages.appendChild(wrapper);
    chatMessages.scrollTop = chatMessages.scrollHeight;
    return wrapper;
}

function setChatSending(sending) {
    chatSending = sending;
    chatSend.disabled = sending;
    chatSend.textContent = sending ? "思考中……" : "发送";
}

async function sendChatMessage() {
    const message = chatInput.value.trim();
    if (!message || chatSending) return;

    appendChatMessage("user", message);
    chatInput.value = "";
    chatInput.style.height = "";

    const typing = appendChatTyping();
    setChatSending(true);

    const payload = { message };
    if (chatThreadId) payload.thread_id = chatThreadId;

    try {
        const data = await request("/api/agent/chat", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(payload),
        });
        typing.remove();
        chatThreadId = data.thread_id || chatThreadId;
        appendChatMessage("assistant", renderMarkdown(data.reply || ""), {
            html: true,
            tools: data.used_tools || [],
        });
    } catch (err) {
        typing.remove();
        appendChatMessage("assistant", `请求失败：${err.message || "未知错误"}`);
    } finally {
        setChatSending(false);
        chatInput.focus();
    }
}

function openChat() {
    $("chat-sidebar").classList.add("open");
    $("chat-sidebar").setAttribute("aria-hidden", "false");
    $("chat-toggle").setAttribute("aria-expanded", "true");
    $("chat-backdrop").hidden = false;
    document.body.classList.add("chat-open");
    chatInput.focus();
}

function closeChat() {
    $("chat-sidebar").classList.remove("open");
    $("chat-sidebar").setAttribute("aria-hidden", "true");
    $("chat-toggle").setAttribute("aria-expanded", "false");
    $("chat-backdrop").hidden = true;
    document.body.classList.remove("chat-open");
}

$("chat-toggle").addEventListener("click", openChat);
$("chat-close").addEventListener("click", closeChat);
$("chat-backdrop").addEventListener("click", closeChat);

document.addEventListener("keydown", (event) => {
    if (event.key === "Escape") closeChat();
});

$("chat-form").addEventListener("submit", (event) => {
    event.preventDefault();
    sendChatMessage();
});

chatInput.addEventListener("keydown", (event) => {
    if (event.key === "Enter" && !event.shiftKey) {
        event.preventDefault();
        sendChatMessage();
    }
});

chatInput.addEventListener("input", () => {
    chatInput.style.height = "auto";
    chatInput.style.height = Math.min(chatInput.scrollHeight, 140) + "px";
});

// ============ 初始化 ============
loadFiles();
loadProducts();
