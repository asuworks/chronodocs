import json
import socketserver
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from queue import Queue
from typing import Optional
from urllib.parse import parse_qs, urlparse

from .reporter import Reporter

# -------------------------------------------------------------------------
# Modern Developer-Centric UI Template with Diff Viewer & Themes
# -------------------------------------------------------------------------
HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="en" data-theme="dark">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>ChronoDocs</title>
  
  <!-- Typography -->
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link href="https://fonts.googleapis.com/css2?family=Fira+Code:wght@400;500&family=IBM+Plex+Sans:wght@400;500;600&family=JetBrains+Mono:wght@500;600&display=swap" rel="stylesheet">

  <style>
    :root {
      /* --- DARK THEME (Default) --- */
      --bg-deep: #0a0e27;
      --bg-slate: #1a1d2e;
      --surface: #1e2139;
      --surface-hover: #2d3348;
      
      --primary: #21808d;
      --primary-glow: rgba(33, 128, 141, 0.4);
      --accent-cyan: #64ffda;
      
      --text-main: #e4e7eb;
      --text-muted: #94a3b8;
      --text-dim: #64748b;
      
      --border: rgba(100, 255, 218, 0.15);
      --border-subtle: rgba(255, 255, 255, 0.05);

      /* Status Colors */
      --status-new-bg: rgba(16, 185, 129, 0.15);
      --status-new-border: #10b981;
      --status-new-text: #6ee7b7;

      --status-mod-bg: rgba(245, 158, 11, 0.15);
      --status-mod-border: #f59e0b;
      --status-mod-text: #fbbf24;

      --status-staged-bg: rgba(14, 165, 233, 0.15);
      --status-staged-border: #0ea5e9;
      --status-staged-text: #38bdf8;

      --status-del-bg: rgba(244, 63, 94, 0.15);
      --status-del-border: #f43f5e;
      --status-del-text: #fb7185;

      --status-com-bg: rgba(100, 116, 139, 0.15);
      --status-com-border: #64748b;
      --status-com-text: #94a3b8;

      /* Diff Colors */
      --diff-bg: #0d1117;
      --diff-add-bg: rgba(46, 160, 67, 0.15);
      --diff-add-text: #3fb950;
      --diff-del-bg: rgba(248, 81, 73, 0.15);
      --diff-del-text: #f85149;
      --diff-hunk-text: #8b949e;
      --diff-meta: #484f58;
      
      --grid-overlay: rgba(255, 255, 255, 0.02);
      --header-shadow: rgba(0,0,0,0.2);
    }

    [data-theme="light"] {
      /* --- LIGHT THEME OVERRIDES --- */
      --bg-deep: #f1f5f9;
      --bg-slate: #ffffff;
      --surface: #ffffff;
      --surface-hover: #f8fafc;
      
      --primary: #0f766e;
      --primary-glow: rgba(15, 118, 110, 0.15);
      --accent-cyan: #0d9488;
      
      --text-main: #0f172a;
      --text-muted: #475569;
      --text-dim: #94a3b8;
      
      --border: #e2e8f0;
      --border-subtle: #f1f5f9;

      /* Status Colors (Adjusted for light bg) */
      --status-new-bg: #d1fae5;
      --status-new-border: #10b981;
      --status-new-text: #065f46;

      --status-mod-bg: #fef3c7;
      --status-mod-border: #f59e0b;
      --status-mod-text: #92400e;

      --status-staged-bg: #e0f2fe;
      --status-staged-border: #0ea5e9;
      --status-staged-text: #075985;

      --status-del-bg: #ffe4e6;
      --status-del-border: #f43f5e;
      --status-del-text: #9f1239;

      --status-com-bg: #f1f5f9;
      --status-com-border: #cbd5e1;
      --status-com-text: #475569;

      /* Diff Colors (GitHub Light style) */
      --diff-bg: #ffffff;
      --diff-add-bg: #e6ffec;
      --diff-add-text: #22863a;
      --diff-del-bg: #ffebe9;
      --diff-del-text: #cf222e;
      --diff-hunk-text: #57606a;
      --diff-meta: #6e7781;
      
      --grid-overlay: rgba(0, 0, 0, 0.03);
      --header-shadow: rgba(0,0,0,0.05);
    }

    * { box-sizing: border-box; }

    body {
      margin: 0;
      font-family: 'IBM Plex Sans', sans-serif;
      background-color: var(--bg-deep);
      background-image: 
        radial-gradient(circle at 0% 0%, var(--primary-glow), transparent 40%),
        linear-gradient(to bottom, var(--bg-deep), var(--bg-slate));
      background-attachment: fixed;
      color: var(--text-main);
      min-height: 100vh;
      -webkit-font-smoothing: antialiased;
      transition: background-color 0.3s, color 0.3s;
    }

    /* Grid Overlay */
    body::before {
      content: "";
      position: fixed;
      top: 0; left: 0; right: 0; bottom: 0;
      background-image: 
        linear-gradient(var(--grid-overlay) 1px, transparent 1px),
        linear-gradient(90deg, var(--grid-overlay) 1px, transparent 1px);
      background-size: 40px 40px;
      pointer-events: none;
      z-index: 0;
    }

    /* Layout */
    .app-layout {
      position: relative;
      z-index: 1;
      max-width: 1400px;
      margin: 0 auto;
      padding: 0 1.5rem 2rem;
    }

    /* Header */
    header {
      display: flex;
      justify-content: space-between;
      align-items: center;
      padding: 1.5rem 0;
      border-bottom: 2px solid var(--primary);
      margin-bottom: 2rem;
      animation: slideDown 0.6s cubic-bezier(0.16, 1, 0.3, 1);
    }

    .brand {
      display: flex;
      align-items: center;
      gap: 0.75rem;
    }
    
    .header-right {
        display: flex;
        align-items: center;
        gap: 1rem;
    }

    h1 {
      margin: 0;
      font-family: 'JetBrains Mono', monospace;
      font-size: 1.5rem;
      font-weight: 700;
      letter-spacing: -0.5px;
      color: var(--text-main);
    }

    .status-pill {
      display: flex;
      align-items: center;
      gap: 0.75rem;
      background: var(--surface);
      padding: 0.5rem 1rem;
      border-radius: 99px;
      border: 1px solid var(--border);
      font-family: 'JetBrains Mono', monospace;
      font-size: 0.8rem;
      color: var(--text-muted);
      box-shadow: 0 2px 4px var(--header-shadow);
    }

    .live-indicator {
      width: 8px;
      height: 8px;
      background-color: var(--accent-cyan);
      border-radius: 50%;
      box-shadow: 0 0 8px var(--accent-cyan);
      animation: pulse 2s infinite;
    }

    .meta-divider { color: var(--primary); }

    /* Theme Toggle */
    .theme-toggle {
        background: var(--surface);
        border: 1px solid var(--border);
        color: var(--text-muted);
        cursor: pointer;
        width: 36px;
        height: 36px;
        border-radius: 50%;
        display: flex;
        align-items: center;
        justify-content: center;
        transition: all 0.2s;
        box-shadow: 0 2px 4px var(--header-shadow);
    }
    
    .theme-toggle:hover {
        color: var(--primary);
        border-color: var(--primary);
        transform: translateY(-1px);
    }

    .theme-icon {
        width: 18px;
        height: 18px;
        fill: none;
        stroke: currentColor;
        stroke-width: 2;
        stroke-linecap: round;
        stroke-linejoin: round;
    }
    
    [data-theme="dark"] .icon-sun { display: block; }
    [data-theme="dark"] .icon-moon { display: none; }
    [data-theme="light"] .icon-sun { display: none; }
    [data-theme="light"] .icon-moon { display: block; }

    /* Filters */
    .controls {
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
      gap: 1rem;
      margin-bottom: 1.5rem;
      animation: fadeIn 0.8s cubic-bezier(0.16, 1, 0.3, 1) 0.1s backwards;
    }

    .control-group {
      background: var(--surface);
      border: 1px solid var(--border);
      padding: 1rem;
      border-radius: 6px;
      display: flex;
      flex-direction: column;
      gap: 0.5rem;
      box-shadow: 0 4px 6px -1px var(--header-shadow);
    }

    .control-group label {
      text-transform: uppercase;
      font-size: 0.7rem;
      font-weight: 600;
      letter-spacing: 0.5px;
      color: var(--primary);
      font-family: 'JetBrains Mono', monospace;
    }

    input, select, button.action-btn {
      background: var(--surface-hover);
      border: 1px solid var(--border);
      color: var(--text-main);
      padding: 0.6rem;
      border-radius: 4px;
      font-family: 'IBM Plex Sans', sans-serif;
      font-size: 0.9rem;
      width: 100%;
      transition: all 0.2s ease;
    }

    input:focus, select:focus, button.action-btn:focus {
      outline: none;
      border-color: var(--primary);
      box-shadow: 0 0 0 2px var(--primary-glow);
    }
    
    ::placeholder { color: var(--text-muted); opacity: 0.5; }

    button#toggle-all {
      background: transparent;
      border: 1px dashed var(--text-dim);
      color: var(--text-muted);
      cursor: pointer;
      font-family: 'JetBrains Mono', monospace;
      font-size: 0.8rem;
      text-align: center;
      margin-top: auto;
      padding: 0.6rem;
      border-radius: 4px;
      transition: all 0.2s;
    }
    
    button#toggle-all:hover {
      border-color: var(--primary);
      color: var(--primary);
      background: var(--primary-glow);
    }

    /* Table */
    .table-wrapper {
      background: var(--surface);
      border-radius: 8px;
      border: 1px solid var(--border);
      box-shadow: 0 10px 15px -3px var(--header-shadow);
      overflow: hidden;
      animation: slideUp 0.8s cubic-bezier(0.16, 1, 0.3, 1) 0.2s backwards;
    }

    table {
      width: 100%;
      border-collapse: collapse;
      table-layout: fixed;
    }

    thead th {
      background: var(--surface); /* Fallback */
      background: color-mix(in srgb, var(--surface), var(--bg-deep) 20%);
      backdrop-filter: blur(8px);
      position: sticky;
      top: 0;
      text-align: left;
      padding: 1rem 1.5rem;
      font-family: 'JetBrains Mono', monospace;
      font-size: 0.8rem;
      font-weight: 600;
      color: var(--text-muted);
      border-bottom: 1px solid var(--border);
      z-index: 10;
    }

    tbody tr {
      transition: background 0.1s;
    }

    .file-row {
      border-bottom: 1px solid var(--border-subtle);
    }
    
    .file-row:nth-child(even) { background: rgba(125,125,125,0.02); }
    .file-row:hover { background: var(--surface-hover); }

    td {
      padding: 0.75rem 1.5rem;
      font-size: 0.9rem;
      vertical-align: middle;
      color: var(--text-muted);
      overflow: hidden;
      text-overflow: ellipsis;
      white-space: nowrap;
    }

    /* Filenames & Paths */
    .filename-cell {
      font-family: 'Fira Code', monospace;
      padding-left: 3rem; /* Indentation for files under groups */
    }
    
    .file-link {
      color: var(--text-main);
      font-weight: 500;
      text-decoration: none;
      position: relative;
      cursor: pointer;
      transition: color 0.2s;
      display: inline-flex;
      align-items: center;
    }
    
    .file-link:hover { color: var(--accent-cyan); }
    
    .toggle-icon {
        display: inline-block;
        margin-right: 0.5rem;
        transition: transform 0.2s;
        font-size: 0.7em;
        color: var(--primary);
    }
    
    .file-row.expanded .toggle-icon {
        transform: rotate(90deg);
    }
    
    /* Hover underline on filename text only */
    .filename-text {
        position: relative;
    }
    
    .filename-text::after {
        content: '';
        position: absolute;
        width: 100%;
        transform: scaleX(0);
        height: 1px;
        bottom: -1px;
        left: 0;
        background-color: var(--accent-cyan);
        transform-origin: bottom right;
        transition: transform 0.25s ease-out;
    }
    
    .file-link:hover .filename-text::after {
        transform: scaleX(1);
        transform-origin: bottom left;
    }
    
    .folder-meta {
      font-size: 0.8em;
      color: var(--text-dim);
      font-style: italic;
      margin-left: 0.5rem;
    }

    /* Group Headers */
    .group-header-row td {
      background: color-mix(in srgb, var(--surface), var(--bg-deep) 50%);
      padding: 0;
      border-bottom: 1px solid var(--border);
    }

    .group-header {
      display: flex;
      align-items: center;
      padding: 0.75rem 1.5rem;
      cursor: pointer;
      font-family: 'JetBrains Mono', monospace;
      font-weight: 600;
      color: var(--text-main);
      font-size: 0.85rem;
      border-left: 3px solid var(--primary);
      transition: background 0.2s;
    }

    .group-header:hover { background: var(--surface-hover); }

    .group-icon {
      margin-right: 0.75rem;
      color: var(--primary);
      font-size: 1.1rem;
      line-height: 1;
      display: inline-block;
      width: 1em;
      text-align: center;
      font-weight: bold;
    }
    
    /* Icons: Minus when open, Plus when collapsed */
    .group-icon::before { content: '−'; }
    .group-collapsed .group-icon::before { content: '+'; }

    .group-count {
      margin-left: auto;
      background: var(--surface);
      border: 1px solid var(--border-subtle);
      padding: 2px 8px;
      border-radius: 4px;
      font-size: 0.75rem;
      color: var(--text-dim);
    }

    .group-collapsed .file-row { display: none; }
    .group-collapsed .diff-row { display: none; }

    /* Badges */
    .badge {
      display: inline-flex;
      align-items: center;
      padding: 0.25rem 0.6rem;
      border-radius: 4px;
      font-family: 'JetBrains Mono', monospace;
      font-size: 0.75rem;
      text-transform: uppercase;
      letter-spacing: 0.05em;
      border: 1px solid transparent;
      box-shadow: 0 0 5px rgba(0,0,0,0.05);
    }

    .status-new { background: var(--status-new-bg); border-color: var(--status-new-border); color: var(--status-new-text); }
    .status-modified { background: var(--status-mod-bg); border-color: var(--status-mod-border); color: var(--status-mod-text); }
    .status-staged { background: var(--status-staged-bg); border-color: var(--status-staged-border); color: var(--status-staged-text); }
    .status-deleted { background: var(--status-del-bg); border-color: var(--status-del-border); color: var(--status-del-text); }
    .status-committed { background: var(--status-com-bg); border-color: var(--status-com-border); color: var(--status-com-text); }
    
    @keyframes badgePulse {
      0% { box-shadow: 0 0 0 0 var(--primary-glow); }
      70% { box-shadow: 0 0 0 4px rgba(0,0,0,0); }
      100% { box-shadow: 0 0 0 0 rgba(0,0,0,0); }
    }
    
    .status-new { animation: badgePulse 2s infinite; }

    /* Timestamps */
    .ts-cell {
      font-family: 'JetBrains Mono', monospace;
      font-size: 0.8rem;
      color: var(--text-dim);
    }

    /* Diff View */
    .diff-row {
        background: var(--bg-slate);
        display: none; /* Toggled via JS */
    }
    
    .diff-row.visible {
        display: table-row;
    }

    .diff-cell {
        padding: 0;
        border-bottom: 1px solid var(--border);
    }

    .diff-container {
        padding: 1rem;
        background: rgba(0,0,0,0.05);
        box-shadow: inset 0 4px 6px -4px rgba(0,0,0,0.1);
    }

    .diff-view {
        background: var(--diff-bg);
        border-radius: 6px;
        font-family: 'Fira Code', monospace;
        font-size: 0.85rem;
        line-height: 1.5;
        overflow-x: auto;
        color: var(--text-main);
        border: 1px solid var(--border);
        padding: 0.5rem 0;
    }

    .diff-line {
        display: block;
        padding: 0 1rem;
        white-space: pre-wrap;
    }

    .diff-add {
        background-color: var(--diff-add-bg);
        color: var(--diff-add-text);
    }

    .diff-del {
        background-color: var(--diff-del-bg);
        color: var(--diff-del-text);
        text-decoration: line-through; /* Optional preference */
        text-decoration-color: rgba(248, 81, 73, 0.4);
        text-decoration: none;
    }

    .diff-hunk {
        background-color: var(--surface-hover);
        color: var(--diff-hunk-text);
        padding-top: 0.5rem;
        padding-bottom: 0.5rem;
        border-top: 1px solid var(--border-subtle);
        border-bottom: 1px solid var(--border-subtle);
        font-style: italic;
    }
    
    .loading-diff {
        padding: 1rem;
        text-align: center;
        color: var(--text-dim);
        font-style: italic;
    }

    /* Empty State */
    .empty-state {
      padding: 4rem 2rem;
      text-align: center;
      color: var(--text-dim);
      display: flex;
      flex-direction: column;
      align-items: center;
      gap: 1rem;
    }
    .empty-icon { font-size: 3rem; opacity: 0.5; filter: grayscale(100%); }
    .empty-text { font-size: 1.1rem; }
    
    /* Animations */
    @keyframes slideDown { from { transform: translateY(-20px); opacity: 0; } to { transform: translateY(0); opacity: 1; } }
    @keyframes fadeIn { from { opacity: 0; transform: translateX(-10px); } to { opacity: 1; transform: translateX(0); } }
    @keyframes slideUp { from { transform: translateY(20px); opacity: 0; } to { transform: translateY(0); opacity: 1; } }
    @keyframes pulse { 0% { opacity: 1; transform: scale(1); } 50% { opacity: 0.5; transform: scale(0.8); } 100% { opacity: 1; transform: scale(1); } }

    /* Responsive */
    @media (max-width: 768px) {
      .controls { grid-template-columns: 1fr; }
      header { flex-direction: column; align-items: flex-start; gap: 1rem; }
      .header-right { width: 100%; justify-content: space-between; }
      .status-pill { flex-grow: 1; }
    }
  </style>
</head>
<body>

  <div class="app-layout">
    <header>
      <div class="brand">
        <h1>🕰️ ChronoDocs</h1>
      </div>
      <div class="header-right">
        <div class="status-pill">
            <span id="connection-status">
                <span class="live-indicator"></span> Live
            </span>
            <span class="meta-divider">•</span>
            <span id="meta-phase">Init</span>
            <span class="meta-divider">•</span>
            <span id="meta-files">0 Files</span>
        </div>
        
        <button class="theme-toggle" onclick="toggleTheme()" title="Switch Theme">
            <!-- Sun Icon -->
            <svg class="theme-icon icon-sun" viewBox="0 0 24 24">
                <circle cx="12" cy="12" r="5"></circle>
                <line x1="12" y1="1" x2="12" y2="3"></line>
                <line x1="12" y1="21" x2="12" y2="23"></line>
                <line x1="4.22" y1="4.22" x2="5.64" y2="5.64"></line>
                <line x1="18.36" y1="18.36" x2="19.78" y2="19.78"></line>
                <line x1="1" y1="12" x2="3" y2="12"></line>
                <line x1="21" y1="12" x2="23" y2="12"></line>
                <line x1="4.22" y1="19.78" x2="5.64" y2="18.36"></line>
                <line x1="18.36" y1="5.64" x2="19.78" y2="4.22"></line>
            </svg>
            <!-- Moon Icon -->
            <svg class="theme-icon icon-moon" viewBox="0 0 24 24">
                <path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z"></path>
            </svg>
        </button>
      </div>
    </header>
    
    <div class="controls">
      <div class="control-group">
        <label for="filter-regex">Search (Regex)</label>
        <input id="filter-regex" type="text" placeholder="e.g. \.py$ or src/" autocomplete="off" spellcheck="false">
      </div>
      
      <div class="control-group">
        <label for="filter-status">Status</label>
        <select id="filter-status">
          <option value="">All Statuses</option>
          <option value="new">New</option>
          <option value="modified">Modified</option>
          <option value="staged">Staged</option>
          <option value="deleted">Deleted</option>
        </select>
      </div>

      <div class="control-group">
        <label for="filter-folder">Folder</label>
        <select id="filter-folder">
          <option value="">All Folders</option>
        </select>
      </div>

      <div class="control-group">
        <label for="sort-by">Sort</label>
        <select id="sort-by">
          <option value="updated-desc">Recent Updates</option>
          <option value="updated-asc">Oldest Updates</option>
          <option value="created-desc">Newest Files</option>
          <option value="filename">Filename (A-Z)</option>
        </select>
      </div>

      <div class="control-group">
        <label for="group-by">Group</label>
        <select id="group-by">
          <option value="updated-day">Day Modified</option>
          <option value="status">Git Status</option>
          <option value="folder">Folder Structure</option>
          <option value="none">Flat List</option>
        </select>
      </div>
      
      <button id="toggle-all" onclick="toggleAllGroups()">Collapse All</button>
    </div>
    
    <div class="table-wrapper">
      <table id="log-table">
        <!-- JS Populated -->
      </table>
    </div>
  </div>
  
  <script>
    let logData = [];
    let areGroupsCollapsed = false;
    
    // --- Theme Logic ---
    function initTheme() {
        const saved = localStorage.getItem('theme');
        if (saved) {
            document.documentElement.setAttribute('data-theme', saved);
        } else if (window.matchMedia && window.matchMedia('(prefers-color-scheme: light)').matches) {
            document.documentElement.setAttribute('data-theme', 'light');
        }
    }
    
    function toggleTheme() {
        const html = document.documentElement;
        const current = html.getAttribute('data-theme');
        const next = current === 'light' ? 'dark' : 'light';
        html.setAttribute('data-theme', next);
        localStorage.setItem('theme', next);
    }
    
    initTheme();
    
    // Initial Render Wrapper
    const tableEl = document.getElementById('log-table');

    function updateMeta(meta) {
        if (!meta) return;
        document.getElementById('meta-phase').textContent = meta.phase.toUpperCase();
        document.getElementById('meta-files').textContent = `${meta.total_files} Files`;
    }

    function populateFolders(files) {
        const select = document.getElementById('filter-folder');
        const currentVal = select.value;
        const folders = new Set(files.map(f => f.folder));
        
        select.innerHTML = '<option value="">All Folders</option>';
        
        Array.from(folders).sort().forEach(folder => {
            const option = document.createElement('option');
            option.value = folder;
            option.textContent = folder === '.' ? './ (root)' : folder;
            select.appendChild(option);
        });
        
        select.value = currentVal;
    }
    
    function formatDate(isoString) {
        const d = new Date(isoString);
        return d.toLocaleTimeString('en-US', { hour12: false, hour: '2-digit', minute: '2-digit', second: '2-digit' }) + 
               ' <span style="opacity:0.5">' + d.toLocaleDateString() + '</span>';
    }
    
    // --- Diff Viewer Logic ---
    
    async function toggleDiff(rowId, filePath) {
        const diffRow = document.getElementById(`diff-${rowId}`);
        const fileRow = document.getElementById(`row-${rowId}`);
        
        if (!diffRow || !fileRow) return;

        // Check if we need to close or open
        const isVisible = diffRow.classList.contains('visible');
        
        if (isVisible) {
            diffRow.classList.remove('visible');
            fileRow.classList.remove('expanded');
        } else {
            diffRow.classList.add('visible');
            fileRow.classList.add('expanded');
            
            // Fetch content if empty
            const contentDiv = diffRow.querySelector('.diff-container');
            if (contentDiv.dataset.loaded !== "true") {
                contentDiv.innerHTML = '<div class="loading-diff">Fetching changes...</div>';
                try {
                    const res = await fetch(`/api/diff?file=${encodeURIComponent(filePath)}`);
                    const data = await res.json();
                    
                    if (data.diff && data.diff.trim().length > 0) {
                        contentDiv.innerHTML = renderDiffHtml(data.diff);
                    } else {
                        contentDiv.innerHTML = '<div class="loading-diff">No changes detected or binary file.</div>';
                    }
                    contentDiv.dataset.loaded = "true";
                } catch (e) {
                    contentDiv.innerHTML = `<div class="loading-diff" style="color:var(--status-del-border)">Error loading diff: ${e.message}</div>`;
                }
            }
        }
    }
    
    function renderDiffHtml(diffText) {
        const lines = diffText.split('\\n');
        let html = '<div class="diff-view">';
        
        lines.forEach(line => {
            let className = 'diff-line';
            if (line.startsWith('+') && !line.startsWith('+++')) className += ' diff-add';
            else if (line.startsWith('-') && !line.startsWith('---')) className += ' diff-del';
            else if (line.startsWith('@@')) className += ' diff-hunk';
            
            // Escape HTML just in case
            const escaped = line
                .replace(/&/g, "&amp;")
                .replace(/</g, "&lt;")
                .replace(/>/g, "&gt;")
                .replace(/"/g, "&quot;")
                .replace(/'/g, "&#039;");
                
            html += `<span class="${className}">${escaped}</span>`;
        });
        
        html += '</div>';
        return html;
    }

    // --- Data Fetching ---

    fetch('/api/log')
      .then(r => r.json())
      .then(data => {
        logData = data.files;
        updateMeta(data.meta);
        populateFolders(data.files);
        render();
      })
      .catch(err => console.error("Fetch error", err));
    
    const evtSource = new EventSource('/events');
    
    evtSource.onopen = () => {
        const statusEl = document.getElementById('connection-status');
        statusEl.innerHTML = '<span class="live-indicator"></span> Live';
        statusEl.style.color = 'var(--text-main)';
    };
    
    evtSource.onmessage = (e) => {
      const update = JSON.parse(e.data);
      if (update.type === 'update') {
          logData = update.files.files;
          updateMeta(update.files.meta);
          if (document.getElementById('filter-folder').options.length <= 1) {
              populateFolders(logData);
          }
          // Note: Full re-render kills open diffs. 
          // A smarter implementation would patch the DOM, but for simplicity we re-render.
          render();
      }
    };
    
    evtSource.onerror = (err) => {
        const statusEl = document.getElementById('connection-status');
        statusEl.innerHTML = '<span class="live-indicator" style="background:var(--status-del-border); animation:none"></span> Offline';
        statusEl.style.color = 'var(--status-del-border)';
    };

    // --- Interaction Logic ---

    async function toggleAllGroups() {
        areGroupsCollapsed = !areGroupsCollapsed;
        const btn = document.getElementById('toggle-all');
        btn.textContent = areGroupsCollapsed ? "Expand All" : "Collapse All";
        
        // Toggle Groups
        const tbodies = document.querySelectorAll('.group-tbody');
        tbodies.forEach(tbody => {
            if (areGroupsCollapsed) tbody.classList.add('group-collapsed');
            else tbody.classList.remove('group-collapsed');
        });

        // When collapsing folders, we also want to reset the state of open diffs
        // so that re-expanding the folder starts fresh.
        if (areGroupsCollapsed) {
             const visibleDiffs = document.querySelectorAll('.diff-row.visible');
             visibleDiffs.forEach(el => el.classList.remove('visible'));
             
             const expandedFiles = document.querySelectorAll('.file-row.expanded');
             expandedFiles.forEach(el => el.classList.remove('expanded'));
        }
    }

    window.toggleGroup = function(header) {
        const tbody = header.closest('tbody');
        
        // Check if we are collapsing
        const isCollapsing = !tbody.classList.contains('group-collapsed');
        
        tbody.classList.toggle('group-collapsed');
        
        if (isCollapsing) {
            // Reset visible diffs inside this specific group
            const visibleDiffs = tbody.querySelectorAll('.diff-row.visible');
            visibleDiffs.forEach(el => el.classList.remove('visible'));
            
            // Reset expanded file indicators
            const expandedFiles = tbody.querySelectorAll('.file-row.expanded');
            expandedFiles.forEach(el => el.classList.remove('expanded'));
        }
    }

    // --- Core Render Logic ---

    function render() {
      const regexRaw = document.getElementById('filter-regex').value;
      const status = document.getElementById('filter-status').value;
      const folder = document.getElementById('filter-folder').value;
      const sortBy = document.getElementById('sort-by').value;
      const groupBy = document.getElementById('group-by').value;
      
      // 1. Filter
      let filtered = logData.filter(f => {
        if (regexRaw) {
            try {
                if (!new RegExp(regexRaw, 'i').test(f.filename)) return false;
            } catch (e) { /* ignore invalid regex */ }
        }
        if (status && f.status !== status) return false;
        if (folder && f.folder !== folder) return false;
        return true;
      });
      
      // 2. Sort
      filtered.sort((a, b) => {
        const dateA = new Date(a.updated);
        const dateB = new Date(b.updated);
        
        if (sortBy === 'updated-desc') return dateB - dateA;
        if (sortBy === 'updated-asc') return dateA - dateB;
        if (sortBy === 'created-desc') return new Date(b.created) - new Date(a.created);
        if (sortBy === 'filename') return a.filename.localeCompare(b.filename);
      });
      
      // 3. Group
      let grouped = {};
      if (groupBy === 'status') {
        filtered.forEach(f => {
          grouped[f.status] = grouped[f.status] || [];
          grouped[f.status].push(f);
        });
      } else if (groupBy === 'folder') {
        filtered.forEach(f => {
          const folderName = f.folder === '.' ? './' : f.folder;
          grouped[folderName] = grouped[folderName] || [];
          grouped[folderName].push(f);
        });
      } else if (groupBy === 'updated-day') {
          filtered.forEach(f => {
              const day = new Date(f.updated).toLocaleDateString(undefined, { weekday: 'short', month: 'short', day: 'numeric' });
              grouped[day] = grouped[day] || [];
              grouped[day].push(f);
          });
      } else {
        grouped['All Files'] = filtered;
      }
      
      // 4. Build HTML
      let html = `
        <thead>
            <tr>
                <th style="width: 40%">File</th>
                <th style="width: 15%">Status</th>
                <th style="width: 20%">Created</th>
                <th style="width: 25%">Updated</th>
            </tr>
        </thead>
      `;
      
      if (filtered.length === 0) {
          tableEl.innerHTML = html + `<tbody><tr><td colspan="4"><div class="empty-state"><div class="empty-icon">📊</div><div class="empty-text">No files match your filters</div></div></td></tr></tbody>`;
          return;
      }
      
      let rowCounter = 0;
      
      for (const [group, files] of Object.entries(grouped)) {
        if (files.length === 0) continue;

        const isCollapsed = areGroupsCollapsed && groupBy !== 'none';
        const collapsedClass = isCollapsed ? 'group-collapsed' : '';
        
        html += `<tbody class="group-tbody ${collapsedClass}">`;
        
        if (groupBy !== 'none') {
            html += `
              <tr class="group-header-row">
                <td colspan="4">
                  <div class="group-header" onclick="toggleGroup(this)">
                    <span class="group-icon"></span>
                    ${group}
                    <span class="group-count">${files.length}</span>
                  </div>
                </td>
              </tr>`;
        }
        
        files.forEach(f => {
          rowCounter++;
          html += `
            <tr class="file-row" id="row-${rowCounter}" data-filepath="${f.path}">
              <td class="filename-cell">
                <a class="file-link" title="${f.path}" onclick="toggleDiff(${rowCounter}, '${f.path}')">
                    <span class="toggle-icon">▶</span>
                    <span class="filename-text">${f.filename}</span>
                </a> 
                <span class="folder-meta">${f.folder === '.' ? '' : f.folder}</span>
              </td>
              <td><span class="badge status-${f.status}">${f.status}</span></td>
              <td class="ts-cell">${formatDate(f.created)}</td>
              <td class="ts-cell">${formatDate(f.updated)}</td>
            </tr>
            <tr class="diff-row" id="diff-${rowCounter}">
                <td colspan="4" class="diff-cell">
                    <div class="diff-container" data-loaded="false"></div>
                </td>
            </tr>
          `;
        });
        
        html += `</tbody>`;
      }
      
      tableEl.innerHTML = html;
    }
    
    // Inputs Listener
    ['filter-regex', 'filter-status', 'filter-folder', 'sort-by', 'group-by']
      .forEach(id => document.getElementById(id).addEventListener('input', render));
  </script>
</body>
</html>
"""


class ChangeLogHandler(BaseHTTPRequestHandler):
    """Serves HTML + SSE updates"""

    update_queue: Queue = Queue()
    reporter: Optional[Reporter] = None

    def log_message(self, format, *args):
        pass

    def do_GET(self):
        parsed_path = urlparse(self.path)
        path = parsed_path.path

        if path == "/":
            self.serve_html()
        elif path == "/events":
            self.serve_sse()
        elif path == "/api/log":
            self.serve_json()
        elif path == "/api/diff":
            self.serve_diff(parse_qs(parsed_path.query))
        else:
            self.send_error(404)

    def serve_html(self):
        self.send_response(200)
        self.send_header("Content-Type", "text/html")
        self.end_headers()
        self.wfile.write(HTML_TEMPLATE.encode("utf-8"))

    def serve_sse(self):
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream")
        self.send_header("Cache-Control", "no-cache")
        self.send_header("Connection", "keep-alive")
        self.end_headers()

        try:
            self.wfile.write(b": ping\n\n")
            self.wfile.flush()
        except (BrokenPipeError, ConnectionResetError):
            return

        my_queue = Queue()
        self.server.subscribers.append(my_queue)

        try:
            while True:
                event = my_queue.get()
                msg = f"data: {json.dumps(event)}\n\n"
                self.wfile.write(msg.encode("utf-8"))
                self.wfile.flush()
        except (BrokenPipeError, ConnectionResetError):
            pass
        finally:
            if my_queue in self.server.subscribers:
                self.server.subscribers.remove(my_queue)

    def serve_json(self):
        if self.reporter:
            data = self.reporter.get_structured_data()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps(data).encode("utf-8"))
        else:
            self.send_error(500, "Reporter not initialized")

    def serve_diff(self, query_params):
        """Serve the diff for a specific file"""
        if not self.reporter:
            self.send_error(500, "Reporter not initialized")
            return

        file_path = query_params.get("file", [None])[0]
        if not file_path:
            self.send_error(400, "Missing 'file' parameter")
            return

        diff_content = self.reporter.get_file_diff(file_path)

        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps({"diff": diff_content}).encode("utf-8"))


class ThreadedHTTPServer(socketserver.ThreadingMixIn, HTTPServer):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.daemon_threads = True
        self.subscribers = []


def start_webserver(host: str, port: int, reporter: Reporter, watcher):
    ChangeLogHandler.reporter = reporter
    server = ThreadedHTTPServer((host, port), ChangeLogHandler)

    def broadcast_update(data):
        event = {"type": "update", "files": data}
        for q in server.subscribers:
            q.put(event)

    watcher.webserver_callback = broadcast_update

    watcher_thread = threading.Thread(target=watcher.run, daemon=True)
    watcher_thread.start()

    print(f"🌐 Web log viewer running at http://{host}:{port}")
    print(f"📊 Watching phase: {reporter.phase}")
    print("Press Ctrl+C to stop")

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
        watcher.stop()
