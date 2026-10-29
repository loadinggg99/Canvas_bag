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
                <td>${p.product_code}</td>
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
async function loadAnalytics() {
    const data = await request("/api/analytics");

    const sortByLabel = FIELD_LABELS[data.sort_by] || data.sort_by;

    $("analytics-summary").innerHTML = `
        <div class="card"><div class="value">${data.total}</div><div class="label">商品总数</div></div>
        <div class="card"><div class="value">${sortByLabel}</div><div class="label">排序字段</div></div>`;

    const tbody = $("analytics-tbody");
    tbody.innerHTML = "";
    if (!data.items || data.items.length === 0) {
        tbody.innerHTML = '<tr><td colspan="5" class="empty">暂无数据，请先导入</td></tr>';
    } else {
        data.items.forEach((it) => {
            const tr = document.createElement("tr");
            const anomaly = it.anomalies && it.anomalies.length > 0
                ? it.anomalies.map((a) => `<span class="badge ${a.severity}">${a.message}</span>`).join(" ")
                : '<span class="badge ok">正常</span>';
            tr.innerHTML = `
                <td>${it.product_code}</td>
                <td>${fmtMoney(it.pdd_sale_price)}</td>
                <td>${fmtMoney(it.pdd_profit)}</td>
                <td>${fmtPercent(it.profit_margin)}</td>
                <td>${anomaly}</td>`;
            tbody.appendChild(tr);
        });
    }
}

$("btn-analytics").addEventListener("click", loadAnalytics);

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
        .map((v) => `<li>${v.message}</li>`)
        .join("");

    $("simulation-result").innerHTML = `
        <div class="sim-card">
            <div class="sim-head">货号：${data.product_code}</div>
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
    $("simulation-result").innerHTML = `<div class="sim-card"><div class="sim-status bad">${msg}</div></div>`;
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

// ============ 初始化 ============
loadFiles();
loadProducts();
