/* ============================================================
   Lakehouse OSS Portal — Application Logic
   ============================================================ */

// ---------------------------------------------------------------------------
// 1. Service Registry — all services from system_access_report.md
// ---------------------------------------------------------------------------
const SERVICES = [
    // ── Database Systems ──
    {
        id: 'postgres',
        name: 'PostgreSQL',
        desc: 'Cơ sở dữ liệu chính (metastore). Hỗ trợ nhiều database: airflow, datahub, hue, metastore, openmetadata.',
        port: 15432,
        protocol: 'tcp',
        category: 'database',
        icon: '🐘',
        credentials: { user: 'admin', pass: 'admin' },
        uiUrl: null,
    },
    {
        id: 'clickhouse',
        name: 'ClickHouse',
        desc: 'Analytics database OLAP (HTTP interface). Cluster 1 shard, 2 replicas với ClickHouse Keeper.',
        port: 8123,
        category: 'database',
        icon: '🏠',
        credentials: { user: 'admin', pass: 'admin' },
        uiUrl: 'http://localhost:8123/play',
    },
    {
        id: 'hive-metastore',
        name: 'Hive Metastore',
        desc: 'Dịch vụ metadata trung tâm (Thrift). Quản lý schema cho Iceberg/Delta Lake tables.',
        port: 9083,
        protocol: 'thrift',
        category: 'database',
        icon: '🐝',
        credentials: { user: 'admin', pass: 'admin' },
        uiUrl: null,
    },
    {
        id: 'redis',
        name: 'Redis',
        desc: 'In-memory cache & message broker cho Airflow Celery và Superset.',
        port: 6379,
        protocol: 'tcp',
        category: 'database',
        icon: '⚡',
        credentials: null,
        uiUrl: null,
    },
    {
        id: 'elasticsearch',
        name: 'Elasticsearch',
        desc: 'Full-text search engine phục vụ Ranger audit log, DataHub search index.',
        port: 9200,
        category: 'database',
        icon: '🔍',
        credentials: null,
        uiUrl: `http://${window.location.hostname}:9200/`,
    },

    // ── IAM & Security ──
    {
        id: 'keycloak',
        name: 'Keycloak',
        desc: 'Identity & Access Management (SSO/OIDC). Cổng xác thực tập trung cho toàn nền tảng.',
        port: 8084,
        category: 'iam',
        icon: '🔐',
        credentials: { user: 'admin', pass: 'admin123' },
        uiUrl: `http://${window.location.hostname}:8084/`,
    },
    {
        id: 'vault',
        name: 'HashiCorp Vault',
        desc: 'Quản lý secret tập trung (KV v2). Tất cả credentials được inject từ Vault vào services.',
        port: 8200,
        category: 'iam',
        icon: '🔒',
        credentials: { user: 'Token', pass: 'dev-root-token' },
        uiUrl: `http://${window.location.hostname}:8200/`,
    },
    {
        id: 'ranger',
        name: 'Apache Ranger',
        desc: 'Quản lý bảo mật và phân quyền dữ liệu (Table/Column-level) cho Trino, Hive.',
        port: 6080,
        category: 'iam',
        icon: '🛡️',
        credentials: { user: 'admin', pass: 'Rangeradmin1' },
        uiUrl: `http://${window.location.hostname}:6080/`,
    },

    // ── Orchestration & Processing ──
    {
        id: 'airflow',
        name: 'Apache Airflow',
        desc: 'Workflow orchestration — quản lý DAGs, scheduling, monitoring pipelines.',
        port: 8085,
        category: 'orchestration',
        icon: '🌬️',
        credentials: { user: 'airflow', pass: 'airflow' },
        uiUrl: `http://${window.location.hostname}:8085/`,
    },
    {
        id: 'minio',
        name: 'MinIO Console',
        desc: 'Object Storage S3-compatible — Data Lake storage (Bronze/Silver/Gold layers).',
        port: 9001,
        category: 'orchestration',
        icon: '📦',
        credentials: { user: 'minio', pass: 'minio123' },
        uiUrl: `http://${window.location.hostname}:9001/`,
    },
    {
        id: 'spark-master',
        name: 'Spark Master',
        desc: 'Apache Spark Cluster Manager — xử lý batch/streaming data ở quy mô lớn.',
        port: 8088,
        category: 'orchestration',
        icon: '⚡',
        credentials: null,
        uiUrl: `http://${window.location.hostname}:8088/`,
    },
    {
        id: 'trino',
        name: 'Trino',
        desc: 'Distributed SQL Query Engine — truy vấn liên hợp trên nhiều nguồn dữ liệu.',
        port: 8080,
        category: 'orchestration',
        icon: '🔷',
        credentials: null,
        uiUrl: `http://${window.location.hostname}:8080/`,
    },
    {
        id: 'nifi',
        name: 'Apache NiFi',
        desc: 'Data flow automation — thiết kế luồng dữ liệu kéo-thả (ETL/ELT visual).',
        port: 8443,
        category: 'orchestration',
        icon: '🔀',
        credentials: { user: 'admin', pass: 'adminadminadmin' },
        uiUrl: `https://${window.location.hostname}:8443/nifi/`,
    },
    {
        id: 'spark-thriftserver',
        name: 'Spark Thrift Server',
        desc: 'JDBC/ODBC gateway đến Spark SQL — kết nối từ BI tools hoặc Hue.',
        port: 10000,
        protocol: 'jdbc',
        category: 'orchestration',
        icon: '🔌',
        credentials: null,
        uiUrl: null,
    },

    // ── Streaming ──
    {
        id: 'kafka',
        name: 'Apache Kafka',
        desc: 'Distributed event streaming platform — backbone cho CDC, real-time pipeline.',
        port: 9092,
        protocol: 'tcp',
        category: 'streaming',
        icon: '📡',
        credentials: null,
        uiUrl: null,
    },
    {
        id: 'kafka-ui',
        name: 'Kafka UI',
        desc: 'Giao diện quản lý Kafka — xem topics, consumer groups, schema registry.',
        port: 8082,
        category: 'streaming',
        icon: '📊',
        credentials: null,
        uiUrl: `http://${window.location.hostname}:8082/`,
    },
    {
        id: 'schema-registry',
        name: 'Schema Registry',
        desc: 'Confluent Schema Registry — quản lý Avro/JSON schemas cho Kafka topics.',
        port: 8081,
        category: 'streaming',
        icon: '📋',
        credentials: null,
        uiUrl: `http://${window.location.hostname}:8081/`,
    },
    {
        id: 'debezium',
        name: 'Debezium (Kafka Connect)',
        desc: 'Change Data Capture — bắt thay đổi từ PostgreSQL → Kafka topics theo real-time.',
        port: 8083,
        category: 'streaming',
        icon: '🔄',
        credentials: null,
        uiUrl: `http://${window.location.hostname}:8083/`,
    },
    {
        id: 'debezium-ui',
        name: 'Debezium UI',
        desc: 'Giao diện quản lý Debezium connectors — tạo, sửa, xóa connectors.',
        port: 8096,
        category: 'streaming',
        icon: '🖥️',
        credentials: null,
        uiUrl: `http://${window.location.hostname}:8096/`,
    },
    {
        id: 'flink',
        name: 'Apache Flink',
        desc: 'Stream processing engine — xử lý sự kiện real-time với stateful computing.',
        port: 8095,
        category: 'streaming',
        icon: '🌊',
        credentials: null,
        uiUrl: `http://${window.location.hostname}:8095/`,
    },

    // ── Monitoring & Visualization ──
    {
        id: 'grafana',
        name: 'Grafana',
        desc: 'Dashboards giám sát — hiển thị metrics từ Prometheus, Loki, ClickHouse.',
        port: 3000,
        category: 'monitoring',
        icon: '📈',
        credentials: { user: 'admin', pass: 'admin' },
        uiUrl: `http://${window.location.hostname}:3000/`,
    },
    {
        id: 'prometheus',
        name: 'Prometheus',
        desc: 'Metrics collection — thu thập metrics từ tất cả services trong platform.',
        port: 9090,
        category: 'monitoring',
        icon: '🔥',
        credentials: { user: 'admin', pass: 'admin123' },
        uiUrl: `http://${window.location.hostname}:9090/`,
    },

    // ── Explore & BI ──
    {
        id: 'superset',
        name: 'Apache Superset',
        desc: 'Business Intelligence — tạo biểu đồ, dashboard, khám phá dữ liệu trực quan.',
        port: 8089,
        category: 'explore',
        icon: '📊',
        credentials: { user: 'admin', pass: 'admin' },
        uiUrl: `http://${window.location.hostname}:8089/`,
    },
    {
        id: 'jupyterlab',
        name: 'JupyterLab',
        desc: 'Interactive notebooks — phân tích dữ liệu, chạy PySpark, trực quan hóa kết quả.',
        port: 8888,
        category: 'explore',
        icon: '📓',
        credentials: null,
        uiUrl: `http://${window.location.hostname}:8888/`,
    },
];

// ---------------------------------------------------------------------------
// 2. Category metadata
// ---------------------------------------------------------------------------
const CATEGORIES = {
    database: { label: 'Databases', color: '#f97316' },
    iam: { label: 'IAM & Security', color: '#ef4444' },
    orchestration: { label: 'Orchestration', color: '#6366f1' },
    streaming: { label: 'Streaming', color: '#06b6d4' },
    monitoring: { label: 'Monitoring', color: '#22c55e' },
    explore: { label: 'Explore & BI', color: '#a855f7' },
};

// ---------------------------------------------------------------------------
// 3. Keycloak Configuration
// ---------------------------------------------------------------------------
const KEYCLOAK_CONFIG = {
    url: window.KEYCLOAK_URL || `http://${window.location.hostname}:8084`,
    realm: window.KEYCLOAK_REALM || 'data-platform',
    clientId: window.KEYCLOAK_CLIENT_ID || 'lakehouse-portal',
};

let keycloak = null;
let keycloakReady = false;

// ---------------------------------------------------------------------------
// 4. DOM references
// ---------------------------------------------------------------------------
const grid = document.getElementById('servicesGrid');
const searchInput = document.getElementById('searchInput');
const filtersWrap = document.getElementById('filters');
const userInfo = document.getElementById('userInfo');
const loginPrompt = document.getElementById('loginPrompt');
const loginBtn = document.getElementById('loginBtn');
const logoutBtn = document.getElementById('logoutBtn');
const userName = document.getElementById('userName');
const userAvatar = document.getElementById('userAvatar');
const totalEl = document.getElementById('totalServices');
const healthyEl = document.getElementById('healthyServices');
const downEl = document.getElementById('downServices');

// ---------------------------------------------------------------------------
// 5. Render service cards
// ---------------------------------------------------------------------------
function renderCards(services) {
    grid.innerHTML = '';
    services.forEach(svc => {
        const cat = CATEGORIES[svc.category] || {};
        const card = document.createElement('div');
        card.className = 'service-card';
        card.dataset.category = svc.category;
        card.dataset.id = svc.id;
        card.style.setProperty('--card-accent', cat.color);
        card.style.setProperty('--icon-bg', hexToRgba(cat.color, 0.12));
        card.style.setProperty('--icon-color', cat.color);

        const credHtml = svc.credentials
            ? `<span title="User: ${svc.credentials.user} / Pass: ${svc.credentials.pass}" style="cursor:help;">🔑</span>`
            : '';

        const linkHtml = svc.uiUrl
            ? `<a class="service-card__link" href="${svc.uiUrl}" target="_blank" rel="noopener">
           Mở <svg viewBox="0 0 20 20" fill="currentColor"><path d="M11 3a1 1 0 100 2h2.586l-6.293 6.293a1 1 0 101.414 1.414L15 6.414V9a1 1 0 102 0V4a1 1 0 00-1-1h-5z"/><path d="M5 5a2 2 0 00-2 2v8a2 2 0 002 2h8a2 2 0 002-2v-3a1 1 0 10-2 0v3H5V7h3a1 1 0 000-2H5z"/></svg>
         </a>`
            : `<span class="service-card__link" style="opacity:.3;cursor:default;">No UI</span>`;

        card.innerHTML = `
      <div class="service-card__header">
        <div class="service-card__icon">${svc.icon}</div>
        <div>
          <div class="service-card__name">${svc.name}</div>
          <div class="service-card__category">${cat.label || svc.category}</div>
        </div>
      </div>
      <p class="service-card__desc">${svc.desc}</p>
      <div class="service-card__footer">
        <span class="service-card__port">:${svc.port} ${credHtml}</span>
        <div class="service-card__status" id="status-${svc.id}">
          <span class="status-dot status-dot--unknown"></span>
          <span>Checking…</span>
        </div>
        ${linkHtml}
      </div>
    `;
        grid.appendChild(card);
    });
    totalEl.textContent = services.length;
}

// ---------------------------------------------------------------------------
// 6. Filtering & Search
// ---------------------------------------------------------------------------
let activeCategory = 'all';

filtersWrap.addEventListener('click', (e) => {
    const chip = e.target.closest('.filter-chip');
    if (!chip) return;
    filtersWrap.querySelectorAll('.filter-chip').forEach(c => c.classList.remove('active'));
    chip.classList.add('active');
    activeCategory = chip.dataset.category;
    applyFilters();
});

searchInput.addEventListener('input', () => applyFilters());

function applyFilters() {
    const q = searchInput.value.toLowerCase().trim();
    document.querySelectorAll('.service-card').forEach(card => {
        const matchCat = activeCategory === 'all' || card.dataset.category === activeCategory;
        const text = card.textContent.toLowerCase();
        const matchSearch = !q || text.includes(q);
        card.classList.toggle('hidden', !(matchCat && matchSearch));
    });
}

// ---------------------------------------------------------------------------
// 7. Health Check via Nginx proxy (avoids CORS)
// ---------------------------------------------------------------------------
const HEALTH_PROXY_MAP = {
    'airflow':         '/api/health/airflow',
    'minio':           '/api/health/minio',
    'clickhouse':      '/api/health/clickhouse',
    'trino':           '/api/health/trino',
    'superset':        '/api/health/superset',
    'grafana':         '/api/health/grafana',
    'prometheus':      '/api/health/prometheus',
    'vault':           '/api/health/vault',
    'kafka-ui':        '/api/health/kafka-ui',
    'schema-registry': '/api/health/schema-registry',
    'debezium':        '/api/health/debezium',
    'elasticsearch':   '/api/health/elasticsearch',
    'flink':           '/api/health/flink',
    'spark-master':    '/api/health/spark-master',
    'jupyterlab':      '/api/health/jupyterlab',
    'nifi':            '/api/health/nifi',
    'keycloak':        '/api/health/keycloak',
    'ranger':          '/api/health/ranger',
};

async function checkHealth(svc) {
    const el = document.getElementById(`status-${svc.id}`);
    if (!el) return 'unknown';

    const proxyPath = HEALTH_PROXY_MAP[svc.id];
    if (!proxyPath) {
        el.innerHTML = `<span class="status-dot status-dot--unknown"></span><span style="color:var(--yellow)">N/A</span>`;
        return 'unknown';
    }

    try {
        const controller = new AbortController();
        setTimeout(() => controller.abort(), 5000);
        const resp = await fetch(proxyPath, { signal: controller.signal });
        if (resp.ok || resp.status === 200) {
            el.innerHTML = `<span class="status-dot status-dot--ok"></span><span style="color:var(--green)">OK</span>`;
            return 'ok';
        } else {
            el.innerHTML = `<span class="status-dot status-dot--down"></span><span style="color:var(--red)">Down</span>`;
            return 'down';
        }
    } catch {
        el.innerHTML = `<span class="status-dot status-dot--down"></span><span style="color:var(--red)">Down</span>`;
        return 'down';
    }
}

async function runHealthChecks() {
    const results = await Promise.allSettled(SERVICES.map(s => checkHealth(s)));
    let ok = 0, down = 0;
    results.forEach(r => {
        if (r.status === 'fulfilled') {
            if (r.value === 'ok') ok++;
            else if (r.value === 'down') down++;
        }
    });
    healthyEl.textContent = ok;
    downEl.textContent = down;
}

// ---------------------------------------------------------------------------
// 8. Auth — reads user info from OAuth2 Proxy (no client-side Keycloak needed)
// ---------------------------------------------------------------------------
async function initAuth() {
    try {
        const resp = await fetch('/oauth2/userinfo', { credentials: 'include' });
        if (resp.ok) {
            const info = await resp.json();
            showUserInfo(info);
        } else {
            // Not authenticated — OAuth2 Proxy should have redirected already,
            // but show login prompt as a fallback.
            showLoginPrompt();
        }
    } catch (err) {
        console.warn('[Portal] Could not reach /oauth2/userinfo:', err);
        showLoginPrompt();
    }
}

function showUserInfo(token) {
    // OAuth2 Proxy returns 'user' or 'preferred_username', Keycloak returns 'preferred_username'
    const name = token?.preferred_username || token?.user || token?.name || token?.email || 'User';
    userName.textContent = name;
    userAvatar.textContent = name.charAt(0).toUpperCase();
    userInfo.style.display = 'flex';
    loginPrompt.style.display = 'none';
}

function showLoginPrompt() {
    userInfo.style.display = 'none';
    loginPrompt.style.display = 'block';
}

loginBtn.addEventListener('click', () => {
    window.location.href = '/oauth2/sign_in';
});

logoutBtn.addEventListener('click', () => {
    window.location.href = '/oauth2/sign_out';
});

// ---------------------------------------------------------------------------
// 9. Utilities
// ---------------------------------------------------------------------------
function hexToRgba(hex, alpha) {
    const r = parseInt(hex.slice(1, 3), 16);
    const g = parseInt(hex.slice(3, 5), 16);
    const b = parseInt(hex.slice(5, 7), 16);
    return `rgba(${r},${g},${b},${alpha})`;
}

function loadScript(src) {
    return new Promise((resolve, reject) => {
        const s = document.createElement('script');
        s.src = src;
        s.onload = resolve;
        s.onerror = reject;
        document.head.appendChild(s);
    });
}

// ---------------------------------------------------------------------------
// 10. Bootstrap
// ---------------------------------------------------------------------------
(function main() {
    renderCards(SERVICES);
    initAuth();
    // Health-check every 30s
    runHealthChecks();
    setInterval(runHealthChecks, 30000);
})();
