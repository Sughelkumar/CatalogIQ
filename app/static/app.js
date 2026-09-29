let currentPage = 1;
let currentJobId = null;
let pollInterval = null;
let searchTimeout = null;

document.addEventListener('DOMContentLoaded', () => {
    fetchMetrics();
    fetchProducts();

    document.getElementById('upload-btn').addEventListener('click', handleUpload);
    document.getElementById('category-filter').addEventListener('change', () => { currentPage = 1; fetchProducts(); });
    
    // Debounce typing search
    document.getElementById('search-input').addEventListener('input', () => {
        clearTimeout(searchTimeout);
        searchTimeout = setTimeout(() => {
            currentPage = 1;
            fetchProducts();
        }, 300);
    });

    document.getElementById('prev-page').addEventListener('click', () => { if (currentPage > 1) { currentPage--; fetchProducts(); } });
    document.getElementById('next-page').addEventListener('click', () => { currentPage++; fetchProducts(); });
    document.getElementById('close-modal-btn').addEventListener('click', closeModal);
    document.getElementById('save-approve-btn').addEventListener('click', saveProduct);
});

async function fetchMetrics() {
    try {
        const res = await fetch('/api/metrics');
        const data = await res.json();
        document.getElementById('metric-calls').innerText = data.llm_calls_total;
        document.getElementById('metric-errors').innerText = data.llm_errors_total;
        document.getElementById('metric-concurrency').innerText = data.max_concurrent_llm_calls;
    } catch (e) { console.error("Metrics fetch failed", e); }
}

async function handleUpload() {
    const fileInput = document.getElementById('csv-file');
    if (!fileInput.files.length) return alert('Select a CSV file');

    const text = await fileInput.files[0].text();
    const lines = text.split('\n').map(l => l.trim()).filter(l => l);
    if (lines.length < 2) return alert('CSV must have a header and at least 1 item');

    const headers = lines[0].split(',').map(h => h.trim().toLowerCase());
    const skuIdx = headers.indexOf('sku');
    const titleIdx = headers.indexOf('raw_title');
    const descIdx = headers.indexOf('raw_description');

    if (skuIdx === -1 || titleIdx === -1) return alert('CSV missing "sku" or "raw_title" header');

    const products = [];
    for (let i = 1; i < lines.length; i++) {
        const parts = lines[i].split(',').map(p => p.trim());
        if (parts[skuIdx] && parts[titleIdx]) {
            products.push({
                sku: parts[skuIdx],
                raw_title: parts[titleIdx],
                raw_description: descIdx !== -1 ? parts[descIdx] : null
            });
        }
    }

    const res = await fetch('/api/jobs', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ products })
    });

    if (res.status === 202) {
        const job = await res.json();
        currentJobId = job.id;
        document.getElementById('job-progress-container').classList.remove('hidden');
        document.getElementById('job-id').innerText = job.id;
        startPolling();
    } else {
        alert('Upload failed');
    }
}

function startPolling() {
    if (pollInterval) clearInterval(pollInterval);
    pollInterval = setInterval(async () => {
        if (!currentJobId) return;
        const res = await fetch(`/api/jobs/${currentJobId}`);
        const job = await res.json();

        const pct = Math.round(((job.done + job.failed) / job.total) * 100);
        document.getElementById('progress-bar-fill').style.width = `${pct}%`;
        document.getElementById('job-done').innerText = job.done;
        document.getElementById('job-failed').innerText = job.failed;
        document.getElementById('job-cache').innerText = job.cache_hits;
        document.getElementById('job-total').innerText = job.total;

        fetchMetrics();
        fetchProducts();

        if (job.status === 'completed') {
            clearInterval(pollInterval);
        }
    }, 1000);
}

async function fetchProducts() {
    const cat = document.getElementById('category-filter').value;
    const q = document.getElementById('search-input').value;
    
    let url = `/api/products?page=${currentPage}&page_size=10`;
    if (cat) url += `&category=${encodeURIComponent(cat)}`;
    if (q) url += `&q=${encodeURIComponent(q)}`;

    const res = await fetch(url);
    const data = await res.json();

    const tbody = document.getElementById('products-list');
    tbody.innerHTML = '';

    data.items.forEach(p => {
        const tr = document.createElement('tr');
        tr.innerHTML = `
            <td>${p.sku}</td>
            <td>${p.clean_title || p.raw_title}</td>
            <td>${p.category || '-'}</td>
            <td>${p.brand || '-'}</td>
            <td><strong>${p.status}</strong></td>
            <td><button onclick="openEditModal('${p.sku}')">Review</button></td>
        `;
        tbody.appendChild(tr);
    });

    document.getElementById('page-info').innerText = `Page ${data.page} of ${Math.ceil(data.total / 10) || 1}`;
    document.getElementById('prev-page').disabled = data.page <= 1;
    document.getElementById('next-page').disabled = data.page * 10 >= data.total;
}

let activeEditingSku = null;

async function openEditModal(sku) {
    activeEditingSku = sku;
    const res = await fetch(`/api/products/${sku}`);
    const p = await res.json();

    document.getElementById('modal-sku').innerText = p.sku;
    document.getElementById('modal-raw-title').innerText = p.raw_title;
    document.getElementById('modal-raw-desc').innerText = p.raw_description || '-';
    
    document.getElementById('modal-clean-title').value = p.clean_title || p.raw_title;
    document.getElementById('modal-category').value = p.category || 'Other';
    document.getElementById('modal-tags').value = (p.tags || []).join(', ');

    const errBox = document.getElementById('modal-error-box');
    if (p.error) {
        errBox.innerText = `Error: ${p.error}`;
        errBox.classList.remove('hidden');
    } else {
        errBox.classList.add('hidden');
    }

    document.getElementById('edit-modal').classList.remove('hidden');
}

function closeModal() {
    document.getElementById('edit-modal').classList.add('hidden');
}

async function saveProduct() {
    const clean_title = document.getElementById('modal-clean-title').value;
    const category = document.getElementById('modal-category').value;
    const tags = document.getElementById('modal-tags').value.split(',').map(t => t.trim()).filter(t => t);

    const res = await fetch(`/api/products/${activeEditingSku}`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ clean_title, category, tags })
    });

    if (res.ok) {
        closeModal();
        fetchProducts();
    } else {
        const err = await res.json();
        alert(`Failed: ${err.detail ? err.detail.message : 'Invalid input'}`);
    }
}