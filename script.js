// Determine API Base URL dynamically
const isLocal = window.location.hostname === '127.0.0.1' || window.location.hostname === 'localhost';
const isFile = window.location.protocol === 'file:';
// Always point to backend port 8000 for local development (covers Live Server @ 5500, File, etc.)
const API_BASE = (isLocal || isFile) ? 'http://127.0.0.1:8000/api/v1' : '/api/v1';

console.log(`Using API Base: ${API_BASE}`);

const urlInput = document.getElementById('media-url');
const analyzeBtn = document.getElementById('analyze-btn');
const resultsSection = document.getElementById('results-section');
const skeletonSection = document.getElementById('skeleton-section');
const timerDisplay = document.getElementById('analysis-timer');
const previewModal = document.getElementById('preview-modal');
const playerContainer = document.getElementById('player-container');

const historySidebar = document.getElementById('history-sidebar');
const historyList = document.getElementById('history-list');
const historyBtn = document.getElementById('history-btn');
const closeSidebarBtn = document.querySelector('.close-sidebar');
const clearHistoryBtn = document.getElementById('clear-history');

let timerId = null;
let currentAnalysisData = null;

analyzeBtn.addEventListener('click', () => {
    const url = urlInput.value.trim();
    if (!url) return showToast('Please paste a link first', 'error');
    startAnalysis(url);
});

// History Event Listeners
historyBtn.addEventListener('click', (e) => {
    e.preventDefault();
    toggleHistory();
});

closeSidebarBtn.addEventListener('click', () => {
    historySidebar.classList.remove('active');
});

clearHistoryBtn.addEventListener('click', () => {
    localStorage.removeItem('mediaHistory');
    renderHistory();
    showToast('History cleared', 'success');
});

// Close sidebar on click outside
document.addEventListener('click', (e) => {
    if (historySidebar.classList.contains('active') &&
        !historySidebar.contains(e.target) &&
        e.target !== historyBtn) {
        historySidebar.classList.remove('active');
    }
});

async function startAnalysis(url) {
    // Show loading state
    resultsSection.classList.add('hidden');
    skeletonSection.classList.remove('hidden');
    resultsSection.innerHTML = '';

    // Start countdown timer
    resetTimer();

    try {
        const response = await fetch(`${API_BASE}/analyze`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ url })
        });

        const result = await response.json();
        stopTimer();

        if (result.success) {
            currentAnalysisData = result.data;
            addToHistory(result.data);
            displayResults(result.data);
        } else {
            showToast(result.error || 'Analysis failed. Try a different platform.', 'error');
            skeletonSection.classList.add('hidden');
        }
    } catch (err) {
        stopTimer();
        console.error('Analysis Error:', err);
        showToast('Server unavailable. Ensure backend is running.', 'error');
        skeletonSection.classList.add('hidden');
    }
}

function displayResults(data) {
    skeletonSection.classList.add('hidden');
    resultsSection.classList.remove('hidden');

    // Filter formats to show useful ones (prioritize those with resolution or quality label)
    const videoFormats = data.formats.filter(f => f.resolution || f.quality_label);
    const bestFormat = videoFormats[0] || data.formats[0] || { format_id: 'best' };
    const isImage = data.formats.some(f => ['jpg', 'jpeg', 'png', 'gif', 'webp'].includes(f.extension.toLowerCase())) || data.id === 'base64-img';

    // Group formats by resolution to avoid duplicates if necessary, or just show top ones
    const uniqueFormats = [];
    const seenRes = new Set();

    videoFormats.forEach(f => {
        const key = `${f.resolution}-${f.extension}`;
        if (!seenRes.has(key)) {
            uniqueFormats.push(f);
            seenRes.add(key);
        }
    });

    // If no video formats with resolution found, use whatever is available
    const displayFormats = uniqueFormats.length > 0 ? uniqueFormats : data.formats.slice(0, 6);

    resultsSection.innerHTML = `
        <div class="media-card glass-card">
            <img src="${data.thumbnail || 'https://via.placeholder.com/350x200'}" class="media-thumb">
            <div class="info-content">
                <span class="platform-tag">${data.platform.toUpperCase()}</span>
                <h2>${data.title}</h2>
                <div class="action-buttons">
                    <button class="action-btn preview-btn" onclick="openPreview('${bestFormat.format_id}', ${isImage})">
                        <i class="fas fa-${isImage ? 'eye' : 'play'}"></i>
                        <span>${isImage ? 'View Image' : 'Preview Video'}</span>
                    </button>
                    <button class="action-btn download-btn" onclick="downloadVideo('${bestFormat.format_id}')">
                        <i class="fas fa-download"></i>
                        <span>${isImage ? 'Download' : 'Download Best'}</span>
                    </button>
                </div>
                
                ${isImage ? '' : `
                <div class="quality-selector">
                    <h3>Available Qualities</h3>
                    <div class="formats-grid">
                        ${displayFormats.map(f => `
                            <div class="format-btn" onclick="downloadVideo('${f.format_id}')" title="Download in ${f.resolution || f.quality_label}">
                                <span>${f.resolution || f.quality_label || 'Audio Only'}</span>
                                <small>${f.extension.toUpperCase()} • ${formatBytes(f.filesize)}</small>
                            </div>
                        `).join('')}
                    </div>
                </div>
                `}
            </div>
        </div>
    `;
}

function addToHistory(data) {
    if (!data || !data.title) return;
    let history = JSON.parse(localStorage.getItem('mediaHistory') || '[]');
    // Avoid duplicates
    history = history.filter(item => item.url !== data.original_url);
    // Add to start
    history.unshift({
        id: data.id,
        title: data.title,
        thumbnail: data.thumbnail,
        url: data.original_url,
        platform: data.platform,
        timestamp: new Date().getTime()
    });
    // Keep last 20
    localStorage.setItem('mediaHistory', JSON.stringify(history.slice(0, 20)));
    renderHistory();
}

function toggleHistory() {
    renderHistory();
    historySidebar.classList.toggle('active');
}

function renderHistory() {
    const history = JSON.parse(localStorage.getItem('mediaHistory') || '[]');
    if (history.length === 0) {
        historyList.innerHTML = '<div style="text-align:center;color:var(--text-dim);margin-top:2rem;">No history yet</div>';
        return;
    }

    historyList.innerHTML = history.map(item => `
        <div class="history-item" onclick="loadFromHistory('${item.url}')">
            <img src="${item.thumbnail || 'https://via.placeholder.com/80x60'}" class="history-thumb">
            <div class="history-info">
                <h4>${item.title}</h4>
                <p>${item.platform} • ${new Date(item.timestamp).toLocaleDateString()}</p>
            </div>
        </div>
    `).join('');
}

function loadFromHistory(url) {
    if (!url) return;
    urlInput.value = url;
    historySidebar.classList.remove('active');
    startAnalysis(url);
}

function openPreview(format_id, isImage = false) {
    if (!currentAnalysisData) return;
    const format = currentAnalysisData.formats.find(f => f.format_id === format_id) || currentAnalysisData.formats[0];
    const streamUrl = `${API_BASE}/stream?url=${encodeURIComponent(format.url)}`;

    let content = '';

    if (currentAnalysisData.id === 'base64-img') {
        const thumb = document.querySelector('.media-thumb').src;
        content = `<img src="${thumb}" style="width: 100%; border-radius: 18px; box-shadow: 0 40px 100px rgba(0,0,0,0.9);">`;
    } else if (isImage) {
        content = `<img src="${streamUrl}" style="width: 100%; border-radius: 18px; box-shadow: 0 40px 100px rgba(0,0,0,0.9);">`;
    } else {
        content = `
            <div class="video-wrapper">
                <video id="preview-video" controls autoplay playsinline preload="metadata">
                    <source src="${streamUrl}" type="video/mp4">
                    Your browser does not support the video tag.
                </video>
                <button class="fullscreen-toggle" onclick="toggleFullscreen()">
                    <i class="fas fa-expand"></i>
                </button>
            </div>
        `;
    }

    playerContainer.innerHTML = content;
    previewModal.classList.remove('hidden');

    const video = document.getElementById('preview-video');
    if (video) video.load();
}

function toggleFullscreen() {
    const video = document.getElementById('preview-video');
    if (!video) return;

    if (!document.fullscreenElement) {
        if (video.requestFullscreen) {
            video.requestFullscreen();
        } else if (video.webkitRequestFullscreen) {
            video.webkitRequestFullscreen();
        } else if (video.msRequestFullscreen) {
            video.msRequestFullscreen();
        }
    } else {
        if (document.exitFullscreen) {
            document.exitFullscreen();
        }
    }
}

// Global listener for escape or fullscreen change
document.addEventListener('fullscreenchange', () => {
    const video = document.getElementById('preview-video');
    if (!document.fullscreenElement && video) {
        // Optional: take any action when user exits fullscreen manually
    }
});

// Close modal on backdrop click
previewModal.addEventListener('click', (e) => {
    if (e.target === previewModal) {
        closePreview();
    }
});

function closePreview() {
    // Also exit fullscreen if closing modal
    if (document.fullscreenElement) {
        document.exitFullscreen().catch(() => { });
    }
    previewModal.classList.add('hidden');
    playerContainer.innerHTML = '';
}

function downloadVideo(formatId) {
    if (!currentAnalysisData) return;
    const format = currentAnalysisData.formats.find(f => f.format_id === formatId) || currentAnalysisData.formats[0];
    const filename = `MediaFlow_${currentAnalysisData.id}.${format.extension || 'mp4'}`;
    const downloadUrl = `${API_BASE}/stream?url=${encodeURIComponent(format.url)}&filename=${encodeURIComponent(filename)}`;

    const a = document.createElement('a');
    a.href = downloadUrl;
    a.download = filename;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    showToast('Download started...', 'success');
}

function resetTimer() {
    clearInterval(timerId);
    let dots = 0;
    updateTimerText(dots);
    timerId = setInterval(() => {
        dots = (dots + 1) % 4;
        updateTimerText(dots);
    }, 500);
}

function stopTimer() {
    clearInterval(timerId);
}

function updateTimerText(dots) {
    const dotStr = '.'.repeat(dots);
    timerDisplay.textContent = `Analyzing media${dotStr} Please wait, this may take a moment`;
}

function formatBytes(bytes) {
    if (!bytes) return 'N/A';
    const s = ['B', 'KB', 'MB', 'GB'];
    const e = Math.floor(Math.log(bytes) / Math.log(1024));
    return (bytes / Math.pow(1024, e)).toFixed(1) + ' ' + s[e];
}

function showToast(msg, type) {
    const toast = document.createElement('div');
    toast.className = 'toast';
    toast.style.cssText = `position:fixed;bottom:2rem;right:2rem;background:${type == 'error' ? '#ef4444' : '#22c55e'};color:#fff;padding:1rem 2rem;border-radius:14px;z-index:9999;box-shadow:0 10px 30px rgba(0,0,0,0.5);animation:fadeIn 0.3s ease;`;
    toast.textContent = msg;
    document.body.appendChild(toast);
    setTimeout(() => toast.remove(), 4000);
}

// Initialize history on load
renderHistory();
