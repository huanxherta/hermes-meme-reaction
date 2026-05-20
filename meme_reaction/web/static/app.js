/**
 * Hermes Meme Reaction Web Dashboard Logic
 * SPA Routing, State Management, and Tactile Micro-Interactions
 */

document.addEventListener('DOMContentLoaded', () => {
    // --- Global State ---
    const state = {
        config: {},
        status: {},
        memes: [],
        libraries: [],
        history: [],
        libraryFilter: {
            query: '',
            tag: '',
            library: '',
            enabled: '',
            page: 1,
            limit: 12
        },
        pagination: {
            page: 1,
            limit: 12,
            total: 0,
            pages: 1
        },
        activeEditMeme: null
    };

    // --- DOM Elements ---
    const el = {
        // Tab Nav
        navItems: document.querySelectorAll('.nav-item'),
        tabPanes: document.querySelectorAll('.tab-pane'),
        pageTitle: document.getElementById('page-title'),
        pageSubtitle: document.getElementById('page-subtitle'),

        // Global Stats & Status
        globalStatusIndicator: document.getElementById('global-status-indicator'),
        globalStatusText: document.getElementById('global-status-text'),
        headerStatMemes: document.getElementById('header-stat-memes'),
        headerStatActive: document.getElementById('header-stat-active'),
        infoIndexPath: document.getElementById('info-index-path'),
        infoRoutesPath: document.getElementById('info-routes-path'),
        infoHistoryPath: document.getElementById('info-history-path'),

        // Sidebar Actions
        btnImportSidebar: document.getElementById('btn-import-sidebar'),

        // Dashboard Tab
        switchPluginEnabled: document.getElementById('switch-plugin-enabled'),
        lblStatusToggle: document.getElementById('lbl-status-toggle'),
        switchDryRun: document.getElementById('switch-dry-run'),
        lblDryrunToggle: document.getElementById('lbl-dryrun-toggle'),
        inputCooldown: document.getElementById('input-cooldown'),
        rangeTriggerWeight: document.getElementById('range-trigger-weight'),
        rangeThreshold: document.getElementById('range-threshold'),
        textTriggerWeight: document.getElementById('text-trigger-weight'),
        textThreshold: document.getElementById('text-threshold'),
        valTriggerWeight: document.getElementById('val-trigger-weight'),
        valThreshold: document.getElementById('val-threshold'),
        markerTrigger: document.getElementById('marker-trigger'),
        markerThreshold: document.getElementById('marker-threshold'),
        barTriggerWeight: document.getElementById('bar-trigger-weight'),
        barThreshold: document.getElementById('bar-threshold'),
        btnSaveDashboardCfg: document.getElementById('btn-save-dashboard-cfg'),
        btnRunImportDashboard: document.getElementById('btn-run-import-dashboard'),
        btnNavLibrary: document.getElementById('btn-nav-library'),

        // Library Tab
        searchLibraryInput: document.getElementById('search-library-input'),
        filterLibrarySelect: document.getElementById('filter-library-select'),
        filterStatusSelect: document.getElementById('filter-status-select'),
        btnClearFilters: document.getElementById('btn-clear-filters'),
        memeGrid: document.getElementById('meme-grid-element'),
        memeEmptyState: document.getElementById('meme-empty-state'),
        memeLoadingState: document.getElementById('meme-loading-state'),
        btnEmptyImport: document.getElementById('btn-empty-import'),
        paginationElement: document.getElementById('pagination-element'),
        pageNumbersContainer: document.getElementById('page-numbers-container'),
        btnPrevPage: document.getElementById('btn-prev-page'),
        btnNextPage: document.getElementById('btn-next-page'),

        // History Tab
        historyTbody: document.getElementById('history-tbody'),
        historyEmptyState: document.getElementById('history-empty-state'),
        btnRefreshHistory: document.getElementById('btn-refresh-history'),

        // Settings Tab
        setSelectTopk: document.getElementById('set-select-topk'),
        setSelectPenalty: document.getElementById('set-select-penalty'),
        setSelectMaxrecent: document.getElementById('set-select-maxrecent'),
        setAllowGif: document.getElementById('set-allow-gif'),
        setAllowWebp: document.getElementById('set-allow-webp'),
        setAllowStatic: document.getElementById('set-allow-static'),
        setLlmEnabled: document.getElementById('set-llm-enabled'),
        setLlmTimeout: document.getElementById('set-llm-timeout'),
        setLlmProvider: document.getElementById('set-llm-provider'),
        setLlmModel: document.getElementById('set-llm-model'),
        librarySettingsRows: document.getElementById('library-settings-rows'),
        btnAddLibraryRow: document.getElementById('btn-add-library-row'),
        btnResetSettings: document.getElementById('btn-reset-settings'),
        btnSaveAllSettings: document.getElementById('btn-save-all-settings'),

        // Meme Detail Modal
        memeEditorModal: document.getElementById('meme-editor-modal'),
        btnCloseMemeModal: document.getElementById('btn-close-meme-modal'),
        btnCancelMemeModal: document.getElementById('btn-cancel-meme-modal'),
        btnSaveMemeModal: document.getElementById('btn-save-meme-modal'),
        modalMemeImg: document.getElementById('modal-meme-img'),
        modalMemePath: document.getElementById('modal-meme-path'),
        modalMemeSize: document.getElementById('modal-meme-size'),
        modalMemeLibrary: document.getElementById('modal-meme-library'),
        modalMemeEnabled: document.getElementById('modal-meme-enabled'),
        modalMemeCaption: document.getElementById('modal-meme-caption'),
        modalMemeIntensity: document.getElementById('modal-meme-intensity'),
        modalMemeIntensityText: document.getElementById('modal-meme-intensity-text'),

        // History Context Modal
        historyDetailModal: document.getElementById('history-detail-modal'),
        btnCloseHistoryModal: document.getElementById('btn-close-history-modal'),
        btnClosedHistoryDetail: document.getElementById('btn-close-history-detail'),
        historyDetailReason: document.getElementById('history-detail-reason'),
        historyDetailChat: document.getElementById('history-detail-chat'),
        historyDetailMemeImg: document.getElementById('history-detail-meme-img'),
        historyDetailMemeName: document.getElementById('history-detail-meme-name'),
        historyDetailMemeTags: document.getElementById('history-detail-meme-tags'),
        historyDetailMemePath: document.getElementById('history-detail-meme-path'),

        // Toast
        toastContainer: document.getElementById('toast-container')
    };

    // --- API Service Functions ---
    const API = {
        async getStatus() {
            const res = await fetch('/api/status');
            return res.json();
        },
        async getConfig() {
            const res = await fetch('/api/config');
            return res.json();
        },
        async saveConfig(configData) {
            const res = await fetch('/api/config', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(configData)
            });
            return res.json();
        },
        async getMemes(filters) {
            const params = new URLSearchParams();
            if (filters.query) params.append('query', filters.query);
            if (filters.tag) params.append('tag', filters.tag);
            if (filters.library) params.append('library', filters.library);
            if (filters.enabled) params.append('enabled', filters.enabled);
            params.append('page', filters.page);
            params.append('limit', filters.limit);

            const res = await fetch(`/api/memes?${params.toString()}`);
            return res.json();
        },
        async updateMeme(memeData) {
            const res = await fetch('/api/memes', {
                method: 'PUT',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(memeData)
            });
            return res.json();
        },
        async runImport() {
            const res = await fetch('/api/import', { method: 'POST' });
            return res.json();
        },
        async getHistory(limit = 50) {
            const res = await fetch(`/api/history?limit=${limit}`);
            return res.json();
        }
    };

    // --- Toast System ---
    function showToast(title, message, type = 'success') {
        const toast = document.createElement('div');
        toast.className = `toast ${type}`;
        
        let icon = 'fa-circle-check';
        if (type === 'error') icon = 'fa-circle-xmark';
        if (type === 'info') icon = 'fa-circle-info';

        toast.innerHTML = `
            <div class="toast-icon">
                <i class="fa-solid ${icon}"></i>
            </div>
            <div class="toast-content">
                <p class="toast-title">${title}</p>
                <p class="toast-message">${message}</p>
            </div>
        `;
        
        el.toastContainer.appendChild(toast);
        
        setTimeout(() => {
            toast.style.transform = 'translateX(50px)';
            toast.style.opacity = '0';
            setTimeout(() => toast.remove(), 300);
        }, 4000);
    }

    // --- SPA Navigation Router ---
    function initRouter() {
        el.navItems.forEach(btn => {
            btn.addEventListener('click', () => {
                const targetTab = btn.getAttribute('data-tab');
                switchTab(targetTab);
            });
        });

        // Shortcuts
        el.btnNavLibrary.addEventListener('click', () => switchTab('library'));
    }

    function switchTab(tabId) {
        // Update navigation classes
        el.navItems.forEach(btn => {
            if (btn.getAttribute('data-tab') === tabId) {
                btn.classList.add('active');
            } else {
                btn.classList.remove('active');
            }
        });

        // Update tab panels display
        el.tabPanes.forEach(pane => {
            if (pane.id === `tab-${tabId}`) {
                pane.classList.add('active');
            } else {
                pane.classList.remove('active');
            }
        });

        // Header headers updating
        if (tabId === 'dashboard') {
            el.pageTitle.textContent = '系统控制台';
            el.pageSubtitle.textContent = '监控、配置和检索表情包自动回复状态';
            loadDashboardData();
        } else if (tabId === 'library') {
            el.pageTitle.textContent = '表情包元数据库';
            el.pageSubtitle.textContent = '查看已索引表情，检索内容标签与情绪标签，微调大模型匹配权重';
            loadLibraryData();
        } else if (tabId === 'history') {
            el.pageTitle.textContent = '自动回复历史日志';
            el.pageSubtitle.textContent = '查看大模型情绪判定依据、上下文、以及表情匹配评分';
            loadHistoryData();
        } else if (tabId === 'settings') {
            el.pageTitle.textContent = '网关高级配置';
            el.pageSubtitle.textContent = '微调网关拦截范围，配置表情包目录，设定 LLM 参数';
            loadSettingsData();
        }
    }

    // --- Tab 1: Dashboard Logic ---
    async function loadDashboardData() {
        try {
            const status = await API.getStatus();
            state.status = status;

            // Header labels
            el.headerStatMemes.textContent = status.total_memes;
            el.headerStatActive.textContent = status.enabled_memes;

            // Global Status Info
            if (status.enabled) {
                el.globalStatusIndicator.className = 'status-indicator active';
                el.globalStatusText.textContent = '已启用自动回复';
            } else {
                el.globalStatusIndicator.className = 'status-indicator';
                el.globalStatusText.textContent = '未启用自动回复';
            }

            // Path information
            el.infoIndexPath.textContent = status.index_path;
            el.infoRoutesPath.textContent = status.routes_path;
            el.infoHistoryPath.textContent = status.history_path;

            // Switch buttons status
            el.switchPluginEnabled.checked = status.enabled;
            el.lblStatusToggle.textContent = status.enabled ? '已开启' : '已关闭';

            el.switchDryRun.checked = status.dry_run;
            el.lblDryrunToggle.textContent = status.dry_run ? '已启用 (测试模式)' : '未启用 (线上模式)';

            el.inputCooldown.value = status.cooldown_seconds;

            // Sync sliders & bar track gauges
            syncDashboardSliders(status.trigger_weight, status.threshold);

        } catch (e) {
            console.error('Failed to load dashboard data:', e);
            showToast('数据拉取失败', '无法连接到网关本地管理服务。', 'error');
        }
    }

    function syncDashboardSliders(trigger, threshold) {
        // Input controls
        el.rangeTriggerWeight.value = trigger;
        el.rangeThreshold.value = threshold;

        // Numeric text indicators
        el.textTriggerWeight.textContent = trigger.toFixed(2);
        el.textThreshold.textContent = threshold.toFixed(2);

        el.valTriggerWeight.textContent = trigger.toFixed(2);
        el.valThreshold.textContent = threshold.toFixed(2);

        // Position sliders markers on the visualize bar gauge
        const triggerPct = trigger * 100;
        const thresholdPct = threshold * 100;

        el.markerTrigger.style.left = `${triggerPct}%`;
        el.markerThreshold.style.left = `${thresholdPct}%`;

        // Bar gauges filling width
        el.barTriggerWeight.style.width = `${triggerPct}%`;
        el.barThreshold.style.width = `${thresholdPct}%`;
    }

    function initDashboardEventListeners() {
        // Slide updates
        el.rangeTriggerWeight.addEventListener('input', (e) => {
            const trigger = parseFloat(e.target.value);
            const threshold = parseFloat(el.rangeThreshold.value);
            syncDashboardSliders(trigger, threshold);
        });

        el.rangeThreshold.addEventListener('input', (e) => {
            const trigger = parseFloat(el.rangeTriggerWeight.value);
            const threshold = parseFloat(e.target.value);
            syncDashboardSliders(trigger, threshold);
        });

        // Dynamic status toggles text feedback
        el.switchPluginEnabled.addEventListener('change', (e) => {
            el.lblStatusToggle.textContent = e.target.checked ? '已开启' : '已关闭';
        });

        el.switchDryRun.addEventListener('change', (e) => {
            el.lblDryrunToggle.textContent = e.target.checked ? '已启用 (测试模式)' : '未启用 (线上模式)';
        });

        // Save Dashboard configurations
        el.btnSaveDashboardCfg.addEventListener('click', async () => {
            try {
                // Fetch loaded configs first
                const configData = await API.getConfig();
                
                // Update modified values
                configData.enabled = el.switchPluginEnabled.checked;
                configData.dry_run = el.switchDryRun.checked;
                configData.cooldown_seconds = parseInt(el.inputCooldown.value) || 0;
                configData.trigger_weight = parseFloat(el.rangeTriggerWeight.value);
                configData.threshold = parseFloat(el.rangeThreshold.value);

                // Save back to backend server (re-writes config.yaml)
                const res = await API.saveConfig(configData);
                if (res.success) {
                    showToast('保存成功', '决策算法参数及总开关已同步至网关配置。', 'success');
                    loadDashboardData();
                } else {
                    showToast('保存失败', res.message || '未知错误', 'error');
                }
            } catch (e) {
                console.error(e);
                showToast('接口请求错误', '保存配置失败，请检查服务日志。', 'error');
            }
        });

        // Immediately trigger scans
        const runImportAction = async () => {
            showToast('开始扫描', '正在搜索本地表情包库文件夹，这需要几秒钟...', 'info');
            try {
                const res = await API.runImport();
                if (res.success) {
                    showToast('重新扫描完成', `成功检索并同步表情包 ${res.count} 张。`, 'success');
                    loadDashboardData();
                    // If library is open, refresh too
                    if (document.getElementById('tab-library').classList.contains('active')) {
                        loadLibraryData();
                    }
                }
            } catch (e) {
                console.error(e);
                showToast('扫描失败', '扫描并重建表情包索引发生异常错误。', 'error');
            }
        };

        el.btnRunImportDashboard.addEventListener('click', runImportAction);
        el.btnImportSidebar.addEventListener('click', runImportAction);
        el.btnEmptyImport.addEventListener('click', runImportAction);
    }

    // --- Tab 2: Meme Library Logic ---
    async function loadLibraryData() {
        el.memeGrid.innerHTML = '';
        el.memeEmptyState.classList.add('hidden');
        el.memeLoadingState.classList.remove('hidden');
        el.paginationElement.classList.add('hidden');

        try {
            // Load status/config to fill filters lists once if empty
            if (state.libraries.length === 0) {
                const config = await API.getConfig();
                state.libraries = config.libraries || [];
                
                // Populate library dropdown filter
                el.filterLibrarySelect.innerHTML = '<option value="">所有表情库</option>';
                state.libraries.forEach(lib => {
                    const opt = document.createElement('option');
                    opt.value = lib.name;
                    opt.textContent = `${lib.name} (${lib.path})`;
                    el.filterLibrarySelect.appendChild(opt);
                });
            }

            const data = await API.getMemes(state.libraryFilter);
            state.memes = data.items || [];
            
            // Sync pagination
            state.pagination = {
                page: data.page,
                limit: data.limit,
                total: data.total,
                pages: data.pages
            };

            el.memeLoadingState.classList.add('hidden');

            if (state.memes.length === 0) {
                el.memeEmptyState.classList.remove('hidden');
                return;
            }

            // Render cards
            state.memes.forEach(meme => {
                const card = createMemeCard(meme);
                el.memeGrid.appendChild(card);
            });

            // Render paginated numbers
            el.paginationElement.classList.remove('hidden');
            renderPaginationControls();

        } catch (e) {
            console.error(e);
            el.memeLoadingState.classList.add('hidden');
            showToast('拉取表情库失败', '元数据服务请求遇到问题，请重试。', 'error');
        }
    }

    function createMemeCard(meme) {
        const card = document.createElement('div');
        card.className = `meme-card ${meme.enabled ? '' : 'disabled'}`;
        card.id = `meme-card-${meme.id}`;

        // Local filesystem image stream path
        const imgSrc = `/api/memes/raw?path=${encodeURIComponent(meme.path)}`;

        card.innerHTML = `
            <div class="meme-card-thumb">
                <img src="${imgSrc}" alt="${meme.caption || 'Meme'}" onerror="this.src='data:image/svg+xml;utf8,<svg xmlns=%22http://www.w3.org/2000/svg%22 width=%22100%22 height=%22100%22 viewBox=%220 0 100 100%22><rect width=%22100%22 height=%22100%22 fill=%22%23222%22/><text x=%2250%25%22 y=%2250%25%22 dominant-baseline=%22middle%22 text-anchor=%22middle%22 font-family=%22sans-serif%22 font-size=%2212%22 fill=%22%23555%22>载入失败</text></svg>'">
                <div class="badge-status ${meme.enabled ? 'active' : 'inactive'}">
                    ${meme.enabled ? '已激活' : '已封锁'}
                </div>
                <div class="meme-card-actions">
                    <button class="btn-card-action btn-edit-meme" title="修改属性">
                        <i class="fa-solid fa-pen-to-square"></i>
                    </button>
                    <button class="btn-card-action btn-toggle-meme" title="${meme.enabled ? '封锁该图' : '启用该图'}">
                        <i class="fa-solid ${meme.enabled ? 'fa-eye-slash' : 'fa-eye'}"></i>
                    </button>
                </div>
            </div>
            <div class="meme-card-info">
                <div>
                    <h4 class="meme-title" title="${meme.caption || meme.relpath}">${meme.caption || meme.relpath}</h4>
                    <span class="meme-library-tag"><i class="fa-solid fa-bookmark"></i> ${meme.library}</span>
                    <div class="meme-tags-list">
                        ${meme.tags.slice(0, 5).map(t => `<span class="meme-tag-chip clickable-tag">${t}</span>`).join('')}
                        ${meme.tags.length > 5 ? `<span class="meme-tag-chip">+${meme.tags.length - 5}</span>` : ''}
                    </div>
                </div>
                <div class="meme-card-footer">
                    <div class="meme-intensity">
                        激烈度: <span>${meme.intensity.toFixed(2)}</span>
                    </div>
                    <span class="text-xs opacity-50 font-semibold">${(meme.size / 1024).toFixed(1)} KB</span>
                </div>
            </div>
        `;

        // Event listener: clicking content tags instantly searches by tag
        card.querySelectorAll('.clickable-tag').forEach(tagEl => {
            tagEl.addEventListener('click', (e) => {
                e.stopPropagation();
                el.searchLibraryInput.value = '';
                state.libraryFilter.query = '';
                state.libraryFilter.tag = tagEl.textContent;
                state.libraryFilter.page = 1;
                loadLibraryData();
            });
        });

        // Event listener: Edit modal opening
        card.querySelector('.btn-edit-meme').addEventListener('click', (e) => {
            e.stopPropagation();
            openMemeEditorModal(meme);
        });

        // Event listener: Toggle active/inactive
        card.querySelector('.btn-toggle-meme').addEventListener('click', async (e) => {
            e.stopPropagation();
            try {
                const targetState = !meme.enabled;
                const res = await API.updateMeme({ id: meme.id, enabled: targetState });
                if (res.success) {
                    showToast(
                        targetState ? '表情包已启用' : '表情包已禁用', 
                        `${meme.relpath} 的启用属性已保存。`, 
                        'success'
                    );
                    loadLibraryData();
                } else {
                    showToast('操作失败', res.message, 'error');
                }
            } catch (ex) {
                console.error(ex);
                showToast('接口连接错误', '修改表情启用状态失败。', 'error');
            }
        });

        return card;
    }

    function renderPaginationControls() {
        el.pageNumbersContainer.innerHTML = '';
        el.btnPrevPage.disabled = state.pagination.page === 1;
        el.btnNextPage.disabled = state.pagination.page === state.pagination.pages;

        const maxVisible = 5;
        let start = Math.max(1, state.pagination.page - Math.floor(maxVisible / 2));
        let end = Math.min(state.pagination.pages, start + maxVisible - 1);

        if (end - start + 1 < maxVisible) {
            start = Math.max(1, end - maxVisible + 1);
        }

        for (let i = start; i <= end; i++) {
            const pageBtn = document.createElement('button');
            pageBtn.className = `btn-page ${i === state.pagination.page ? 'active' : ''}`;
            pageBtn.textContent = i;
            pageBtn.addEventListener('click', () => {
                if (i !== state.pagination.page) {
                    state.libraryFilter.page = i;
                    loadLibraryData();
                }
            });
            el.pageNumbersContainer.appendChild(pageBtn);
        }
    }

    function initLibraryFilters() {
        // Text keyword search search with debounce
        let searchTimeout;
        el.searchLibraryInput.addEventListener('input', (e) => {
            clearTimeout(searchTimeout);
            searchTimeout = setTimeout(() => {
                state.libraryFilter.query = e.target.value;
                state.libraryFilter.tag = ''; // reset tag chips searching
                state.libraryFilter.page = 1;
                loadLibraryData();
            }, 350);
        });

        // Dropdown selection filters
        el.filterLibrarySelect.addEventListener('change', (e) => {
            state.libraryFilter.library = e.target.value;
            state.libraryFilter.page = 1;
            loadLibraryData();
        });

        el.filterStatusSelect.addEventListener('change', (e) => {
            state.libraryFilter.enabled = e.target.value;
            state.libraryFilter.page = 1;
            loadLibraryData();
        });

        // Clear button
        el.btnClearFilters.addEventListener('click', () => {
            el.searchLibraryInput.value = '';
            el.filterLibrarySelect.value = '';
            el.filterStatusSelect.value = '';
            
            state.libraryFilter = {
                query: '',
                tag: '',
                library: '',
                enabled: '',
                page: 1,
                limit: 12
            };
            loadLibraryData();
        });

        // Prev & Next pagination buttons
        el.btnPrevPage.addEventListener('click', () => {
            if (state.pagination.page > 1) {
                state.libraryFilter.page = state.pagination.page - 1;
                loadLibraryData();
            }
        });

        el.btnNextPage.addEventListener('click', () => {
            if (state.pagination.page < state.pagination.pages) {
                state.libraryFilter.page = state.pagination.page + 1;
                loadLibraryData();
            }
        });
    }

    // --- Tab 3: History Logs Logic ---
    async function loadHistoryData() {
        el.historyTbody.innerHTML = '<tr><td colspan="6" class="text-center opacity-50"><div class="spinner" style="margin: 2rem auto;"></div>正在检索发送记录...</td></tr>';
        el.historyEmptyState.classList.add('hidden');

        try {
            const data = await API.getHistory();
            state.history = data || [];

            el.historyTbody.innerHTML = '';

            if (state.history.length === 0) {
                el.historyEmptyState.classList.remove('hidden');
                return;
            }

            state.history.forEach((log, index) => {
                const tr = document.createElement('tr');

                // Timestamp human formatting
                const timeStr = formatTimestamp(log.ts);

                // Meme preview stream endpoint
                const imgSrc = `/api/memes/raw?path=${encodeURIComponent(log.path)}`;

                // Decision score threshold checks
                const score = log.decision ? parseFloat(log.decision.score || 0) : 0;
                const finalScore = log.decision ? parseFloat(log.decision.final_score || 0) : 0;

                const scoreTextClass = finalScore >= 0.5 ? 'success' : 'fail';
                const scoreIndicator = `<span class="score-text ${scoreTextClass}">${finalScore.toFixed(2)}</span>`;

                // Badge display: dry-run or fully sent
                let badgeClass = 'success';
                let badgeText = '自动发送';
                if (log.dry_run) {
                    badgeClass = 'dry-run';
                    badgeText = '调试模式';
                }

                const badgeHtml = `<span class="badge-decision ${badgeClass}"><i class="fa-solid ${log.dry_run ? 'fa-eye' : 'fa-paper-plane'}"></i> ${badgeText}</span>`;

                tr.innerHTML = `
                    <td class="font-bold opacity-80">${timeStr}</td>
                    <td>
                        <div class="history-meme-thumb">
                            <img src="${imgSrc}" alt="Meme" onerror="this.src='data:image/svg+xml;utf8,<svg xmlns=%22http://www.w3.org/2000/svg%22 width=%2250%22 height=%2250%22 viewBox=%220 0 100 100%22><rect width=%22100%22 height=%22100%22 fill=%22%23222%22/><text x=%2250%25%22 y=%2250%25%22 dominant-baseline=%22middle%22 text-anchor=%22middle%22 font-family=%22sans-serif%22 font-size=%2212%22 fill=%22%23555%22>载入失败</text></svg>'">
                        </div>
                    </td>
                    <td class="font-semibold text-accent">${log.target || '未知通道'}</td>
                    <td>${scoreIndicator} <span class="text-xs opacity-50">(基础:${score.toFixed(2)})</span></td>
                    <td>${badgeHtml}</td>
                    <td>
                        <button class="btn btn-secondary btn-sm btn-view-context" data-index="${index}">
                            <i class="fa-regular fa-comments"></i> 决策细节
                        </button>
                    </td>
                `;

                tr.querySelector('.btn-view-context').addEventListener('click', () => {
                    openHistoryDetailModal(log);
                });

                el.historyTbody.appendChild(tr);
            });

        } catch (e) {
            console.error(e);
            el.historyTbody.innerHTML = '<tr><td colspan="6" class="text-center text-danger">数据请求发生致命错误。</td></tr>';
            showToast('加载历史失败', '无法拉取后台任务运行历史流水。', 'error');
        }
    }

    function formatTimestamp(unixTs) {
        if (!unixTs) return '-';
        const date = new Date(unixTs * 1000);
        const y = date.getFullYear();
        const m = String(date.getMonth() + 1).padStart(2, '0');
        const d = String(date.getDate()).padStart(2, '0');
        const h = String(date.getHours()).padStart(2, '0');
        const min = String(date.getMinutes()).padStart(2, '0');
        const s = String(date.getSeconds()).padStart(2, '0');
        return `${m}-${d} ${h}:${min}:${s}`;
    }

    function initHistoryEventListeners() {
        el.btnRefreshHistory.addEventListener('click', loadHistoryData);
    }

    // --- Tab 4: Settings Config Logic ---
    async function loadSettingsData() {
        try {
            const config = await API.getConfig();
            state.config = config;

            // Fill algorithm selection fields
            el.setSelectTopk.value = config.selection.top_k;
            el.setSelectPenalty.value = config.selection.repeat_penalty;
            el.setSelectMaxrecent.value = config.selection.max_same_tag_recent;

            el.setAllowGif.checked = config.selection.allow_gif;
            el.setAllowWebp.checked = config.selection.allow_webp;
            el.setAllowStatic.checked = config.selection.allow_static_image;

            // LLM fields
            el.setLlmEnabled.checked = config.llm.enabled;
            el.setLlmTimeout.value = config.llm.timeout_seconds;
            el.setLlmProvider.value = config.llm.provider;
            el.setLlmModel.value = config.llm.model;

            // Filter chips editor
            initChipsEditor('editor-platforms-allow', config.allowed_platforms);
            initChipsEditor('editor-platforms-deny', config.denied_platforms);
            initChipsEditor('editor-targets-allow', config.allowed_targets);
            initChipsEditor('editor-targets-deny', config.denied_targets);

            // Populate Library list rows
            renderLibrarySettingsRows(config.libraries);

        } catch (e) {
            console.error(e);
            showToast('加载配置失败', '拉取网关的高级参数信息出错。', 'error');
        }
    }

    function renderLibrarySettingsRows(libraries = []) {
        el.librarySettingsRows.innerHTML = '';
        libraries.forEach((lib, index) => {
            addLibraryRowElement(lib.name, lib.path, lib.recursive, lib.enabled);
        });

        if (libraries.length === 0) {
            // Default blank row
            addLibraryRowElement('default', '~/.hermes/memes', true, true);
        }
    }

    function addLibraryRowElement(name = 'library', path = '', recursive = true, enabled = true) {
        const row = document.createElement('div');
        row.className = 'library-row';
        row.innerHTML = `
            <input type="text" class="lib-name-input" placeholder="别名" value="${name}">
            <input type="text" class="lib-path-input" placeholder="文件夹本地路径" value="${path}">
            <label class="checkbox-item justify-center">
                <input type="checkbox" class="lib-recursive-input" ${recursive ? 'checked' : ''}>
                <span class="text-xs">递归</span>
            </label>
            <button class="btn-remove-lib" title="删除"><i class="fa-solid fa-trash-can"></i></button>
        `;

        row.querySelector('.btn-remove-lib').addEventListener('click', () => {
            row.remove();
        });

        el.librarySettingsRows.appendChild(row);
    }

    function initSettingsEventListeners() {
        // Add library row action
        el.btnAddLibraryRow.addEventListener('click', () => {
            addLibraryRowElement('', '', true, true);
        });

        // Reset inputs to saved configuration
        el.btnResetSettings.addEventListener('click', () => {
            loadSettingsData();
            showToast('重置修改', '所有表单修改已恢复为网关当前储存的有效值。', 'info');
        });

        // Save all advanced settings
        el.btnSaveAllSettings.addEventListener('click', async () => {
            try {
                const configData = await API.getConfig();

                // 1. Core configs
                configData.selection = {
                    top_k: parseInt(el.setSelectTopk.value) || 8,
                    repeat_penalty: parseFloat(el.setSelectPenalty.value) || 0.8,
                    max_same_tag_recent: parseInt(el.setSelectMaxrecent.value) || 3,
                    allow_gif: el.setAllowGif.checked,
                    allow_webp: el.setAllowWebp.checked,
                    allow_static_image: el.setAllowStatic.checked
                };

                configData.llm = {
                    enabled: el.setLlmEnabled.checked,
                    timeout_seconds: parseFloat(el.setLlmTimeout.value) || 4,
                    provider: el.setLlmProvider.value.trim() || "",
                    model: el.setLlmModel.value.trim() || ""
                };

                // 2. Allowed lists from chips editors
                configData.allowed_platforms = getChipsListValues('editor-platforms-allow');
                configData.denied_platforms = getChipsListValues('editor-platforms-deny');
                configData.allowed_targets = getChipsListValues('editor-targets-allow');
                configData.denied_targets = getChipsListValues('editor-targets-deny');

                // 3. Extract libraries table rows
                const libRows = el.librarySettingsRows.querySelectorAll('.library-row');
                const libraries = [];
                libRows.forEach(row => {
                    const name = row.querySelector('.lib-name-input').value.trim();
                    const path = row.querySelector('.lib-path-input').value.trim();
                    const recursive = row.querySelector('.lib-recursive-input').checked;
                    if (path) {
                        libraries.push({
                            name: name || 'library',
                            path: path,
                            recursive: recursive,
                            enabled: true // Always true by default
                        });
                    }
                });
                configData.libraries = libraries;

                // POST API to update config.yaml
                const res = await API.saveConfig(configData);
                if (res.success) {
                    showToast('全局配置已保存', '全部通道过滤规则与表情库参数已保存并同步。', 'success');
                    // Invalidate state lists to force fetch next time
                    state.libraries = []; 
                    loadSettingsData();
                } else {
                    showToast('保存设置失败', res.message, 'error');
                }

            } catch (e) {
                console.error(e);
                showToast('API错误', '保存配置到服务器失败。', 'error');
            }
        });
    }

    // --- Chips Editor Utilities ---
    function initChipsEditor(containerId, initialValues = []) {
        const container = document.getElementById(containerId);
        if (!container) return;

        const list = container.querySelector('.chips-list');
        const input = container.querySelector('input');

        list.innerHTML = '';
        initialValues.forEach(val => {
            if (val) addChipElement(list, val.trim());
        });

        // Remove listener to prevent duplicate binds
        const cloneInput = input.cloneNode(true);
        input.parentNode.replaceChild(cloneInput, input);

        cloneInput.addEventListener('keydown', (e) => {
            if (e.key === 'Enter') {
                e.preventDefault();
                const val = cloneInput.value.trim();
                if (val) {
                    const currentValues = Array.from(list.querySelectorAll('.chip-text')).map(c => c.textContent.trim().toLowerCase());
                    if (!currentValues.includes(val.toLowerCase())) {
                        addChipElement(list, val);
                        cloneInput.value = '';
                    }
                }
            }
        });
    }

    function addChipElement(listContainer, value) {
        const chip = document.createElement('div');
        chip.className = 'chip';
        chip.innerHTML = `
            <span class="chip-text">${value}</span>
            <button class="chip-btn-remove"><i class="fa-solid fa-xmark"></i></button>
        `;
        
        chip.querySelector('.chip-btn-remove').addEventListener('click', () => {
            chip.remove();
        });

        listContainer.appendChild(chip);
    }

    function getChipsListValues(containerId) {
        const container = document.getElementById(containerId);
        if (!container) return [];
        const textElements = container.querySelectorAll('.chip-text');
        return Array.from(textElements).map(el => el.textContent.trim());
    }

    // --- Modal 1: Meme Metadata Detail Editor ---
    function openMemeEditorModal(meme) {
        state.activeEditMeme = meme;

        // Image stream path and texts
        el.modalMemeImg.src = `/api/memes/raw?path=${encodeURIComponent(meme.path)}`;
        el.modalMemePath.textContent = meme.path;
        el.modalMemeSize.textContent = `${(meme.size / 1024).toFixed(1)} KB`;
        el.modalMemeLibrary.textContent = `表情库: ${meme.library}`;
        
        el.modalMemeEnabled.checked = meme.enabled;
        el.modalMemeCaption.value = meme.caption || '';
        
        // Dynamic intensity
        el.modalMemeIntensity.value = meme.intensity;
        el.modalMemeIntensityText.textContent = meme.intensity.toFixed(2);

        // Subtags lists chips editors
        initChipsEditor('modal-meme-tags-editor', meme.tags);
        initChipsEditor('modal-meme-moods-editor', meme.moods);
        initChipsEditor('modal-meme-safefor-editor', meme.safe_for || []);
        initChipsEditor('modal-meme-avoidfor-editor', meme.avoid_for || []);

        // Display Modal overlay
        el.memeEditorModal.classList.remove('hidden');
    }

    function initMemeEditorModalEvents() {
        // Intensity slider live texts
        el.modalMemeIntensity.addEventListener('input', (e) => {
            el.modalMemeIntensityText.textContent = parseFloat(e.target.value).toFixed(2);
        });

        // Close functions
        const closeModal = () => {
            el.memeEditorModal.classList.add('hidden');
            state.activeEditMeme = null;
        };

        el.btnCloseMemeModal.addEventListener('click', closeModal);
        el.btnCancelMemeModal.addEventListener('click', closeModal);
        el.memeEditorModal.addEventListener('click', (e) => {
            if (e.target === el.memeEditorModal) closeModal();
        });

        // Save modifications
        el.btnSaveMemeModal.addEventListener('click', async () => {
            if (!state.activeEditMeme) return;

            try {
                const updatedPayload = {
                    id: state.activeEditMeme.id,
                    enabled: el.modalMemeEnabled.checked,
                    caption: el.modalMemeCaption.value.trim(),
                    intensity: parseFloat(el.modalMemeIntensity.value),
                    tags: getChipsListValues('modal-meme-tags-editor'),
                    moods: getChipsListValues('modal-meme-moods-editor'),
                    safe_for: getChipsListValues('modal-meme-safefor-editor'),
                    avoid_for: getChipsListValues('modal-meme-avoidfor-editor')
                };

                const res = await API.updateMeme(updatedPayload);
                if (res.success) {
                    showToast('保存属性成功', `表情包 [${state.activeEditMeme.relpath}] 元数据修改已应用。`, 'success');
                    closeModal();
                    loadLibraryData(); // refresh grid
                } else {
                    showToast('保存失败', res.message, 'error');
                }
            } catch (e) {
                console.error(e);
                showToast('错误', '更新表情属性遇到API异常。', 'error');
            }
        });
    }

    // --- Modal 2: History Conversation Chat Detail ---
    function openHistoryDetailModal(log) {
        // 1. Set model reasoning
        el.historyDetailReason.textContent = log.decision ? log.decision.reason : '未找到判断决策元数据。';

        // 2. Render dialogue context bubbles
        el.historyDetailChat.innerHTML = '';
        
        // Fetch values
        const userMsg = log.user_message;
        const assistMsg = log.assistant_response;

        if (userMsg) {
            const userBubble = document.createElement('div');
            userBubble.className = 'chat-bubble user';
            userBubble.innerHTML = `
                <span class="bubble-sender">用户 (User)</span>
                <p class="bubble-content">${escapeHTML(userMsg)}</p>
            `;
            el.historyDetailChat.appendChild(userBubble);
        }

        if (assistMsg) {
            const assistBubble = document.createElement('div');
            assistBubble.className = 'chat-bubble assistant';
            assistBubble.innerHTML = `
                <span class="bubble-sender">Hermes 助手回复</span>
                <p class="bubble-content">${escapeHTML(assistMsg)}</p>
            `;
            el.historyDetailChat.appendChild(assistBubble);
        }

        if (!userMsg && !assistMsg) {
            el.historyDetailChat.innerHTML = '<p class="text-xs opacity-50 text-center py-4">未找到本次触发的对话上下文快照。</p>';
        }

        // 3. Render sent meme details
        el.historyDetailMemeImg.src = `/api/memes/raw?path=${encodeURIComponent(log.path)}`;
        el.historyDetailMemeName.textContent = log.filename || '表情包';
        el.historyDetailMemePath.textContent = log.path;

        el.historyDetailMemeTags.innerHTML = '';
        const allTags = [].concat(log.tags || [], log.moods || []);
        allTags.forEach(tag => {
            const span = document.createElement('span');
            span.className = 'meme-tag-chip';
            span.textContent = tag;
            el.historyDetailMemeTags.appendChild(span);
        });

        // Show Modal
        el.historyDetailModal.classList.remove('hidden');
    }

    function initHistoryContextModalEvents() {
        const closeModal = () => {
            el.historyDetailModal.classList.add('hidden');
        };

        el.btnCloseHistoryModal.addEventListener('click', closeModal);
        el.btnClosedHistoryDetail.addEventListener('click', closeModal);
        el.historyDetailModal.addEventListener('click', (e) => {
            if (e.target === el.historyDetailModal) closeModal();
        });
    }

    // --- Day/Light Mode Theme Toggle ---
    function initThemeToggle() {
        const btnThemeToggle = document.getElementById('btn-theme-toggle');
        if (!btnThemeToggle) return;

        const updateThemeUI = (isLight) => {
            const icon = btnThemeToggle.querySelector('i');
            const label = btnThemeToggle.querySelector('span');
            if (isLight) {
                icon.className = 'fa-solid fa-moon';
                label.textContent = '深色模式';
            } else {
                icon.className = 'fa-solid fa-sun';
                label.textContent = '日间模式';
            }
        };

        // Load saved theme
        const savedTheme = localStorage.getItem('theme');
        const isLightInitial = savedTheme === 'light';
        if (isLightInitial) {
            document.body.classList.add('light-theme');
        }
        updateThemeUI(isLightInitial);

        // Click listener
        btnThemeToggle.addEventListener('click', () => {
            const isLightActive = document.body.classList.toggle('light-theme');
            localStorage.setItem('theme', isLightActive ? 'light' : 'dark');
            updateThemeUI(isLightActive);
            showToast(
                isLightActive ? '已切换至日间模式' : '已切换至深色模式',
                isLightActive ? '亮色主题视觉已应用。' : '黑曜石深色调视觉已应用。',
                'info'
            );
        });
    }

    // --- General Utility Helpers ---
    function escapeHTML(str) {
        if (!str) return '';
        return str
            .replace(/&/g, '&amp;')
            .replace(/</g, '&lt;')
            .replace(/>/g, '&gt;')
            .replace(/"/g, '&quot;')
            .replace(/'/g, '&#039;');
    }

    // --- Init App ---
    function init() {
        initThemeToggle();
        initRouter();
        initDashboardEventListeners();
        initLibraryFilters();
        initHistoryEventListeners();
        initSettingsEventListeners();
        initMemeEditorModalEvents();
        initHistoryContextModalEvents();

        // Load dashboard on initial start
        switchTab('dashboard');
    }

    init();
});
