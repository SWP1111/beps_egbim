/**
 * Content Manager Admin - Unified Interface
 * Combines content management and manager assignment
 */

// Global state
let hierarchyData = null;
let currentUserRole = null;
let currentUserId = null;
let jwtToken = null;

// Initialize on DOM load
document.addEventListener('DOMContentLoaded', function() {
    // Get user info from sessionStorage (same as main.js)
    const userInfo = JSON.parse(sessionStorage.getItem("loggedInUser") || "{}");
    console.log("User info from sessionStorage:", userInfo);

    currentUserRole = userInfo && userInfo.user ? userInfo.user.role_id : null;
    currentUserId = userInfo && userInfo.user ? userInfo.user.id : null;
    jwtToken = userInfo.token;

    console.log("Current user role:", currentUserRole);
    console.log("Current user ID:", currentUserId);
    console.log("JWT token exists:", !!jwtToken);

    if (!jwtToken) {
        console.error("No JWT token found in sessionStorage");
        alert('로그인이 필요합니다.');
        window.top.location.href = '/login.html';
        return;
    }

    // Check admin access
    if (currentUserRole !== 1 && currentUserRole !== 2 && currentUserRole !== 999) {
        document.body.innerHTML = `
            <div style="text-align: center; margin-top: 50px; color: #f44336;">
                <h1>접근 권한이 없습니다</h1>
                <p style="font-size: 1.5rem;">이 페이지는 관리자 권한이 필요합니다.</p>
            </div>
        `;
        return;
    }

    // Initialize the page
    initializePage();
});

/**
 * Initialize page - load data and setup event handlers
 */
async function initializePage() {
    try {
        // Load hierarchy data with managers
        await loadHierarchyWithManagers();

        // Populate dropdowns
        populateChannelDropdown();

        // Setup event handlers
        setupEventHandlers();

        // Load content table
        await loadContentTable();

        // Load user combobox options
        loadCompanyOptions();

    } catch (error) {
        console.error('Error initializing page:', error);
        showError('페이지 초기화 중 오류가 발생했습니다.');
    }
}

/**
 * Load company options for user selection
 */
async function loadCompanyOptions() {
    const companySelect = document.getElementById('company-select');

    try {
        const response = await authenticatedFetch('/user/companies');

        if (!response.ok) {
            throw new Error('Failed to load company options');
        }

        const data = await response.json();

        // Clear existing options except the first placeholder
        companySelect.innerHTML = '<option value="">회사명</option>';

        // Add new options
        if (Array.isArray(data)) {
            data.forEach(company => {
                const option = document.createElement('option');
                option.value = company;
                option.textContent = company;
                companySelect.appendChild(option);
            });
        }

    } catch (error) {
        console.error('Error loading company options:', error);
        companySelect.innerHTML = '<option value="">회사명</option>';
    }
}

/**
 * Load department options based on selected company
 */
async function loadDepartmentOptions(company) {
    const departmentSelect = document.getElementById('department-select');

    try {
        const response = await authenticatedFetch(`/user/departments?company=${encodeURIComponent(company)}`);

        if (!response.ok) {
            throw new Error('Failed to load department options');
        }

        const data = await response.json();

        // Clear existing options except the first placeholder
        departmentSelect.innerHTML = '<option value="">부서</option>';

        // Add new options
        if (Array.isArray(data)) {
            data.forEach(department => {
                const option = document.createElement('option');
                option.value = department;
                option.textContent = department;
                departmentSelect.appendChild(option);
            });
        }

    } catch (error) {
        console.error('Error loading department options:', error);
        departmentSelect.innerHTML = '<option value="">부서</option>';
    }
}

/**
 * Load position options based on selected company and department
 */
async function loadPositionOptions(company, department) {
    const positionSelect = document.getElementById('position-select');

    try {
        const response = await authenticatedFetch(`/user/positions?company=${encodeURIComponent(company)}&department=${encodeURIComponent(department)}`);

        if (!response.ok) {
            throw new Error('Failed to load position options');
        }

        const data = await response.json();

        // Clear existing options except the first placeholder
        positionSelect.innerHTML = '<option value="">직책</option>';

        // Add new options
        if (Array.isArray(data)) {
            data.forEach(position => {
                const option = document.createElement('option');
                option.value = position;
                option.textContent = position;
                positionSelect.appendChild(option);
            });
        }

    } catch (error) {
        console.error('Error loading position options:', error);
        positionSelect.innerHTML = '<option value="">직책</option>';
    }
}

/**
 * Load name options based on selected company, department, and position
 */
async function loadNameOptions(company, department, position) {
    const nameSelect = document.getElementById('name-select');

    if (!company || !department || !position) {
        nameSelect.innerHTML = '<option value="">이름</option>';
        return;
    }

    try {
        const response = await authenticatedFetch(`/user/names?company=${encodeURIComponent(company)}&department=${encodeURIComponent(department)}&position=${encodeURIComponent(position)}`);

        if (!response.ok) {
            throw new Error('Failed to load name options');
        }

        const data = await response.json();

        // Clear existing options except the first placeholder
        nameSelect.innerHTML = '<option value="">이름</option>';

        // Add new options
        if (Array.isArray(data)) {
            data.forEach(user => {
                const option = document.createElement('option');
                option.value = user.id;
                option.textContent = user.name;
                nameSelect.appendChild(option);
            });
        }

    } catch (error) {
        console.error('Error loading name options:', error);
        nameSelect.innerHTML = '<option value="">이름</option>';
    }
}

/**
 * Authenticated fetch wrapper
 */
async function authenticatedFetch(url, options = {}) {
    const headers = {
        'Authorization': `Bearer ${jwtToken}`,
        ...options.headers
    };

    // Only add Content-Type if not uploading FormData
    if (!(options.body instanceof FormData)) {
        headers['Content-Type'] = 'application/json';
    }

    // Construct full URL using baseUrl from config.js
    const fullUrl = url.startsWith('http') ? url : `${window.baseUrl}${url.replace(/^\//, '')}`;

    return fetch(fullUrl, {
        credentials: 'include',
        ...options,
        headers
    });
}

/**
 * Load hierarchy data with manager information
 */
async function loadHierarchyWithManagers() {
    try {
        const response = await authenticatedFetch('/contents/hierarchy-with-managers');

        if (!response.ok) {
            throw new Error(`Failed to load hierarchy: ${response.status}`);
        }

        hierarchyData = await response.json();
        console.log('Hierarchy data loaded:', hierarchyData);

    } catch (error) {
        console.error('Error loading hierarchy:', error);
        throw error;
    }
}

/**
 * Populate channel dropdown
 */
function populateChannelDropdown() {
    const channelSelect = document.getElementById('channel-select');
    channelSelect.innerHTML = '<option value="">선택</option>';

    if (!hierarchyData || !hierarchyData.channels) return;

    hierarchyData.channels.forEach(channel => {
        const option = document.createElement('option');
        option.value = channel.id;
        option.textContent = channel.name;
        channelSelect.appendChild(option);
    });
}

/**
 * Populate category dropdown based on selected channel
 */
function populateCategoryDropdown(channelId) {
    const categorySelect = document.getElementById('category-select');
    categorySelect.innerHTML = '<option value="">선택</option>';

    // Reset page dropdown
    const pageSelect = document.getElementById('page-select');
    pageSelect.innerHTML = '<option value="">선택 (선택사항)</option>';

    if (!channelId || !hierarchyData) return;

    const channel = hierarchyData.channels.find(ch => ch.id == channelId);
    if (!channel || !channel.categories) return;

    channel.categories.forEach(category => {
        const option = document.createElement('option');
        option.value = category.id;
        option.textContent = category.name;
        categorySelect.appendChild(option);
    });
}

/**
 * Populate page dropdown based on selected category
 */
function populatePageDropdown(channelId, categoryId) {
    const pageSelect = document.getElementById('page-select');
    pageSelect.innerHTML = '<option value="">선택 (선택사항)</option>';

    if (!categoryId || !hierarchyData) return;

    const channel = hierarchyData.channels.find(ch => ch.id == channelId);
    if (!channel || !channel.categories) return;

    const category = channel.categories.find(cat => cat.id == categoryId);
    if (!category || !category.pages) return;

    category.pages.forEach(page => {
        const option = document.createElement('option');
        option.value = page.id;
        option.textContent = page.name;
        pageSelect.appendChild(option);
    });
}

/**
 * Setup event handlers
 */
function setupEventHandlers() {
    // Channel selection
    document.getElementById('channel-select').addEventListener('change', function(e) {
        const channelId = e.target.value;
        populateCategoryDropdown(channelId);
    });

    // Category selection
    document.getElementById('category-select').addEventListener('change', function(e) {
        const channelId = document.getElementById('channel-select').value;
        const categoryId = e.target.value;
        populatePageDropdown(channelId, categoryId);
    });

    // Add supervisor button
    document.getElementById('add-supervisor-btn').addEventListener('click', addSupervisor);

    // Add worker button
    document.getElementById('add-worker-btn').addEventListener('click', addWorker);

    // Refresh button
    document.getElementById('refresh-btn').addEventListener('click', refreshContentTable);

    // Modal close buttons
    document.querySelectorAll('.modal-close').forEach(btn => {
        btn.addEventListener('click', closeModals);
    });

    document.querySelectorAll('.cancel-btn').forEach(btn => {
        btn.addEventListener('click', closeModals);
    });

    // Image modal specific
    document.getElementById('image-modal-close-footer').addEventListener('click', closeImageModal);

    // User combobox cascading event handlers
    const companySelect = document.getElementById('company-select');
    const departmentSelect = document.getElementById('department-select');
    const positionSelect = document.getElementById('position-select');
    const nameSelect = document.getElementById('name-select');

    // Company change - load departments and clear downstream
    companySelect.addEventListener('change', function() {
        departmentSelect.innerHTML = '<option value="">부서</option>';
        positionSelect.innerHTML = '<option value="">직책</option>';
        nameSelect.innerHTML = '<option value="">이름</option>';

        if (this.value) {
            loadDepartmentOptions(this.value);
        }
    });

    // Department change - load positions and clear downstream
    departmentSelect.addEventListener('change', function() {
        positionSelect.innerHTML = '<option value="">직책</option>';
        nameSelect.innerHTML = '<option value="">이름</option>';

        if (this.value && companySelect.value) {
            loadPositionOptions(companySelect.value, this.value);
        }
    });

    // Position change - load names
    positionSelect.addEventListener('change', function() {
        nameSelect.innerHTML = '<option value="">이름</option>';

        if (this.value && companySelect.value && departmentSelect.value) {
            loadNameOptions(companySelect.value, departmentSelect.value, this.value);
        }
    });

    // Name select - update the input fields with the selected user ID
    nameSelect.addEventListener('change', function() {
        const selectedUserId = this.value;
        console.log('Name selected, user ID:', selectedUserId);

        if (selectedUserId) {
            // Determine which input to populate based on current selection
            const categoryId = document.getElementById('category-select').value;
            const pageId = document.getElementById('page-select').value;

            console.log('Category ID:', categoryId, 'Page ID:', pageId);

            if (pageId) {
                // If page is selected, populate worker input and clear supervisor
                console.log('Filling worker-input with:', selectedUserId);
                document.getElementById('worker-input').value = selectedUserId;
                document.getElementById('supervisor-input').value = '';
            } else if (categoryId) {
                // If only category is selected, populate supervisor input and clear worker
                console.log('Filling supervisor-input with:', selectedUserId);
                document.getElementById('supervisor-input').value = selectedUserId;
                document.getElementById('worker-input').value = '';
            } else {
                // No selection - could fill both or neither, let's fill both
                console.log('No category/page selected, filling both inputs');
                document.getElementById('supervisor-input').value = selectedUserId;
                document.getElementById('worker-input').value = selectedUserId;
            }
        } else {
            // Clear both inputs when name is deselected
            document.getElementById('supervisor-input').value = '';
            document.getElementById('worker-input').value = '';
        }
    });
}

/**
 * Add supervisor (책임자) to category
 */
async function addSupervisor() {
    const categoryId = document.getElementById('category-select').value;
    const supervisorId = document.getElementById('supervisor-input').value.trim();

    if (!categoryId) {
        showError('카테고리를 선택해주세요.');
        return;
    }

    if (!supervisorId) {
        showError('책임자 ID를 입력해주세요.');
        return;
    }

    try {
        const response = await authenticatedFetch('/contents/content_manager', {
            method: 'POST',
            body: JSON.stringify({
                user_id: supervisorId,
                type: 'folder',
                folder_id: parseInt(categoryId)
            })
        });

        if (response.status === 409) {
            // Conflict - manager already exists, show replacement modal
            const existingManager = await getExistingManager('folder', categoryId);
            const newManager = await getUserInfo(supervisorId);

            if (existingManager) {
                showReplaceManagerModal(existingManager, newManager, async () => {
                    // User confirmed replacement, update the manager
                    try {
                        const updateResponse = await authenticatedFetch(`/contents/content_manager/${existingManager.id}`, {
                            method: 'PUT',
                            body: JSON.stringify({
                                user_id: supervisorId,
                                type: 'folder',
                                folder_id: parseInt(categoryId)
                            })
                        });

                        if (!updateResponse.ok) {
                            const errorData = await updateResponse.json();
                            throw new Error(errorData.error || '책임자 변경 실패');
                        }

                        alert('책임자가 성공적으로 변경되었습니다.');

                        // Clear input
                        document.getElementById('supervisor-input').value = '';

                        // Reload data
                        await loadHierarchyWithManagers();
                        await loadContentTable();

                    } catch (error) {
                        console.error('Error updating supervisor:', error);
                        showError(error.message);
                    }
                });
            } else {
                showError('기존 담당자 정보를 가져올 수 없습니다.');
            }
            return;
        }

        if (!response.ok) {
            const errorData = await response.json();
            throw new Error(errorData.error || '책임자 추가 실패');
        }

        alert('책임자가 성공적으로 추가되었습니다.');

        // Clear input
        document.getElementById('supervisor-input').value = '';

        // Reload data
        await loadHierarchyWithManagers();
        await loadContentTable();

    } catch (error) {
        console.error('Error adding supervisor:', error);
        showError(error.message);
    }
}

/**
 * Add worker (실무자) to page
 */
async function addWorker() {
    const pageId = document.getElementById('page-select').value;
    const workerId = document.getElementById('worker-input').value.trim();

    if (!pageId) {
        showError('페이지를 선택해주세요.');
        return;
    }

    if (!workerId) {
        showError('실무자 ID를 입력해주세요.');
        return;
    }

    try {
        const response = await authenticatedFetch('/contents/content_manager', {
            method: 'POST',
            body: JSON.stringify({
                user_id: workerId,
                type: 'file',
                file_id: parseInt(pageId)
            })
        });

        if (response.status === 409) {
            // Conflict - manager already exists, show replacement modal
            const existingManager = await getExistingManager('file', pageId);
            const newManager = await getUserInfo(workerId);

            if (existingManager) {
                showReplaceManagerModal(existingManager, newManager, async () => {
                    // User confirmed replacement, update the manager
                    try {
                        const updateResponse = await authenticatedFetch(`/contents/content_manager/${existingManager.id}`, {
                            method: 'PUT',
                            body: JSON.stringify({
                                user_id: workerId,
                                type: 'file',
                                file_id: parseInt(pageId)
                            })
                        });

                        if (!updateResponse.ok) {
                            const errorData = await updateResponse.json();
                            throw new Error(errorData.error || '실무자 변경 실패');
                        }

                        alert('실무자가 성공적으로 변경되었습니다.');

                        // Clear input
                        document.getElementById('worker-input').value = '';

                        // Reload data
                        await loadHierarchyWithManagers();
                        await loadContentTable();

                    } catch (error) {
                        console.error('Error updating worker:', error);
                        showError(error.message);
                    }
                });
            } else {
                showError('기존 담당자 정보를 가져올 수 없습니다.');
            }
            return;
        }

        if (!response.ok) {
            const errorData = await response.json();
            throw new Error(errorData.error || '실무자 추가 실패');
        }

        alert('실무자가 성공적으로 추가되었습니다.');

        // Clear input
        document.getElementById('worker-input').value = '';

        // Reload data
        await loadHierarchyWithManagers();
        await loadContentTable();

    } catch (error) {
        console.error('Error adding worker:', error);
        showError(error.message);
    }
}

/**
 * Load and render content table
 */
async function loadContentTable() {
    const tbody = document.getElementById('content-table-body');
    tbody.innerHTML = '<tr><td colspan="9" class="loading-message">컨텐츠 목록을 불러오는 중...</td></tr>';

    if (!hierarchyData || !hierarchyData.channels) {
        tbody.innerHTML = '<tr><td colspan="9" class="loading-message">표시할 데이터가 없습니다.</td></tr>';
        return;
    }

    tbody.innerHTML = '';

    // Render each channel
    hierarchyData.channels.forEach(channel => {
        if (!channel.categories || channel.categories.length === 0) return;

        let channelRowSpan = 0;

        // Calculate total rowspan for channel (categories + pages)
        channel.categories.forEach(category => {
            const pageCount = category.pages ? category.pages.length : 0;
            channelRowSpan += Math.max(pageCount, 1); // At least 1 row per category
        });

        let isFirstChannelRow = true;

        // Render each category in this channel
        channel.categories.forEach((category, categoryIndex) => {
            const pages = category.pages || [];
            const categoryRowSpan = Math.max(pages.length, 1);

            if (pages.length === 0) {
                // Category with no pages
                const row = createTableRow(
                    channel, category, null,
                    isFirstChannelRow, channelRowSpan,
                    true, categoryRowSpan
                );
                tbody.appendChild(row);
                isFirstChannelRow = false;
            } else {
                // Category with pages
                let isFirstCategoryRow = true;

                pages.forEach((page, pageIndex) => {
                    // Main page row
                    const row = createTableRow(
                        channel, category, page,
                        isFirstChannelRow, channelRowSpan,
                        isFirstCategoryRow, categoryRowSpan
                    );
                    tbody.appendChild(row);

                    isFirstChannelRow = false;
                    isFirstCategoryRow = false;
                });
            }
        });
    });
}

/**
 * Create table row for channel/category/page
 */
function createTableRow(channel, category, page, isFirstChannelRow, channelRowSpan, isFirstCategoryRow, categoryRowSpan) {
    const row = document.createElement('tr');
    row.className = page ? 'page-row' : 'category-row';
    if (page) {
        row.dataset.pageId = page.id;
    }

    // Channel column (merged for all rows in channel)
    if (isFirstChannelRow) {
        const channelCell = document.createElement('td');
        channelCell.textContent = channel.name;
        channelCell.rowSpan = channelRowSpan;
        channelCell.className = 'merged-cell';
        row.appendChild(channelCell);
    }

    // Category column (merged for all pages in category)
    if (isFirstCategoryRow) {
        const categoryCell = document.createElement('td');
        categoryCell.textContent = category.name;
        categoryCell.rowSpan = categoryRowSpan;
        categoryCell.className = 'merged-cell';
        row.appendChild(categoryCell);
    }

    // Page column (with expand button at the end)
    const pageCell = document.createElement('td');
    pageCell.className = 'page-cell-wrapper';

    if (page) {
        // Remove file extension from page name
        const pageName = page.name.replace(/\.(png|jpg|jpeg|gif|bmp|svg)$/i, '');

        const nameSpan = document.createElement('span');
        nameSpan.textContent = pageName;
        pageCell.appendChild(nameSpan);

        if (page.has_pending) {
            const badge = document.createElement('span');
            badge.className = 'pending-badge';
            badge.textContent = 'NEW';
            pageCell.appendChild(badge);
        }

        // Expand arrow at the end
        const arrow = document.createElement('span');
        arrow.className = 'expand-arrow';
        arrow.textContent = '▶';
        arrow.dataset.pageId = page.id;
        arrow.addEventListener('click', function() {
            toggleAdditionalContent(page.id, arrow, row);
        });
        pageCell.appendChild(arrow);
    } else {
        pageCell.textContent = '-';
    }
    row.appendChild(pageCell);

    // Supervisor columns (책임자) - 3 separate columns (name, position, id) - from category
    if (isFirstCategoryRow) {
        const supervisorNameCell = document.createElement('td');
        supervisorNameCell.rowSpan = categoryRowSpan;
        supervisorNameCell.textContent = category.manager ? (category.manager.name || '-') : '미지정';
        row.appendChild(supervisorNameCell);

        const supervisorPositionCell = document.createElement('td');
        supervisorPositionCell.rowSpan = categoryRowSpan;
        supervisorPositionCell.textContent = category.manager ? (category.manager.position || '-') : '-';
        row.appendChild(supervisorPositionCell);

        const supervisorIdCell = document.createElement('td');
        supervisorIdCell.rowSpan = categoryRowSpan;
        supervisorIdCell.textContent = category.manager ? (category.manager.user_id || '-') : '-';
        row.appendChild(supervisorIdCell);
    }

    // Worker columns (실무자) - 3 separate columns (name, position, id) - from page
    const workerNameCell = document.createElement('td');
    workerNameCell.textContent = page && page.manager ? (page.manager.name || '-') : (page ? '미지정' : '-');
    row.appendChild(workerNameCell);

    const workerPositionCell = document.createElement('td');
    workerPositionCell.textContent = page && page.manager ? (page.manager.position || '-') : '-';
    row.appendChild(workerPositionCell);

    const workerIdCell = document.createElement('td');
    workerIdCell.textContent = page && page.manager ? (page.manager.user_id || '-') : '-';
    row.appendChild(workerIdCell);

    return row;
}

/**
 * Toggle additional content visibility
 */
async function toggleAdditionalContent(pageId, arrowElement, row) {
    const existingContainer = row.querySelector('.additional-content-wrapper');

    if (existingContainer) {
        // Collapse
        row.classList.remove('expanded');
        arrowElement.classList.remove('expanded');
        existingContainer.remove();
    } else {
        // Expand
        row.classList.add('expanded');
        arrowElement.classList.add('expanded');

        // Get page data
        const page = getPageById(pageId);
        if (!page) return;

        // Create wrapper that spans all columns
        const wrapper = document.createElement('div');
        wrapper.className = 'additional-content-wrapper';
        wrapper.id = `additional-content-${pageId}`;

        // Create container for the expanded content
        const container = document.createElement('div');
        container.className = 'additional-content-container';

        // Header
        const header = document.createElement('div');
        header.className = 'additional-content-header';
        header.innerHTML = '<h4>페이지 이미지 및 추가 컨텐츠</h4>';
        container.appendChild(header);

        // Page image section
        const imageSection = document.createElement('div');
        imageSection.className = 'page-image-section';
        // Remove double extension - page.name already has extension
        const pageFileName = page.name.replace(/\.(png|jpg|jpeg|gif|bmp|svg)$/i, '') + '.png';
        imageSection.innerHTML = `
            <div class="page-image-item">
                <div class="page-image-info">
                    <span class="page-image-icon">🖼️</span>
                    <span class="page-image-name">${pageFileName}</span>
                    <span class="pending-badge" id="page-pending-${page.id}" style="display: ${page.has_pending ? 'inline-block' : 'none'}">대기중</span>
                </div>
                <div class="page-image-actions">
                    <button class="icon-btn view-btn" onclick="viewPageImage(${page.id})">보기</button>
                    <button class="icon-btn upload-btn" onclick="uploadPageToPending(${page.id})">업로드</button>
                    <button class="icon-btn update-btn" id="approve-page-${page.id}" onclick="approvePageUpdate(${page.id})" style="display: ${page.has_pending ? 'inline-block' : 'none'}">업데이트</button>
                </div>
            </div>
        `;
        container.appendChild(imageSection);

        // Additional files section
        const filesSection = document.createElement('div');
        filesSection.className = 'additional-files-section';
        filesSection.id = `additional-files-${page.id}`;
        filesSection.innerHTML = `
            <div class="additional-content-header">
                <h4>추가 컨텐츠</h4>
                <button class="icon-btn add-btn" onclick="addAdditionalContent(${page.id})">+ 추가</button>
            </div>
            <div class="additional-files-list" id="additional-files-list-${page.id}">
                <div class="loading-message" style="padding: 20px;">불러오는 중...</div>
            </div>
        `;
        container.appendChild(filesSection);

        wrapper.appendChild(container);

        // Insert the wrapper at the end of the row
        row.appendChild(wrapper);

        // Load additional content
        await loadAdditionalContent(pageId);
    }
}

/**
 * Helper function to get page data by ID
 */
function getPageById(pageId) {
    if (!hierarchyData || !hierarchyData.channels) return null;

    for (const channel of hierarchyData.channels) {
        if (!channel.categories) continue;
        for (const category of channel.categories) {
            if (!category.pages) continue;
            const page = category.pages.find(p => p.id == pageId);
            if (page) return page;
        }
    }
    return null;
}

/**
 * Load additional content for a page
 */
async function loadAdditionalContent(pageId) {
    const listContainer = document.getElementById(`additional-files-list-${pageId}`);

    try {
        const response = await authenticatedFetch(`/contents/page/${pageId}/additionals`);

        if (!response.ok) {
            throw new Error('Failed to load additional content');
        }

        const data = await response.json();
        listContainer.innerHTML = '';

        if (!data.additionals || data.additionals.length === 0) {
            listContainer.innerHTML = '<div class="loading-message" style="padding: 20px;">추가 컨텐츠가 없습니다.</div>';
            return;
        }

        // Render each additional file
        data.additionals.forEach(additional => {
            const item = createAdditionalFileItem(additional);
            listContainer.appendChild(item);
        });

    } catch (error) {
        console.error('Error loading additional content:', error);
        listContainer.innerHTML = '<div class="loading-message" style="padding: 20px; color: #f44336;">불러오기 실패</div>';
    }
}

/**
 * Create additional file item element
 */
function createAdditionalFileItem(additional) {
    const item = document.createElement('div');
    item.className = 'additional-file-item';

    // File info
    const info = document.createElement('div');
    info.className = 'additional-file-info';

    const icon = document.createElement('span');
    icon.className = 'file-icon';
    icon.textContent = getFileIcon(additional.file_extension);
    info.appendChild(icon);

    const details = document.createElement('div');
    details.className = 'file-details';
    details.innerHTML = `
        <div class="file-name">
            ${additional.filename}
            ${additional.has_pending ? '<span class="pending-badge">대기중</span>' : ''}
        </div>
        <div class="file-meta">${formatFileSize(additional.file_size)} • ${additional.file_extension}</div>
    `;
    info.appendChild(details);
    item.appendChild(info);

    // File actions
    const actions = document.createElement('div');
    actions.className = 'file-actions';

    const downloadBtn = document.createElement('button');
    downloadBtn.className = 'icon-btn view-btn';
    downloadBtn.textContent = '다운로드';
    downloadBtn.onclick = () => downloadAdditional(additional.id);
    actions.appendChild(downloadBtn);

    const uploadBtn = document.createElement('button');
    uploadBtn.className = 'icon-btn upload-btn';
    uploadBtn.textContent = '업로드';
    uploadBtn.onclick = () => uploadAdditionalToPending(additional.id);
    actions.appendChild(uploadBtn);

    if (additional.has_pending) {
        const updateBtn = document.createElement('button');
        updateBtn.className = 'icon-btn update-btn';
        updateBtn.textContent = '업데이트';
        updateBtn.onclick = () => approveAdditionalUpdate(additional.id);
        actions.appendChild(updateBtn);
    }

    const deleteBtn = document.createElement('button');
    deleteBtn.className = 'icon-btn delete-btn';
    deleteBtn.textContent = '삭제';
    deleteBtn.onclick = () => deleteAdditional(additional.id);
    actions.appendChild(deleteBtn);

    item.appendChild(actions);

    return item;
}

/**
 * View page image
 */
async function viewPageImage(pageId) {
    try {
        const response = await authenticatedFetch(`/contents/page/${pageId}/image-url`);

        if (!response.ok) {
            throw new Error('Failed to get image URL');
        }

        const data = await response.json();
        showImageModal(data.signed_url, `Page ${pageId} Image`);

    } catch (error) {
        console.error('Error viewing page image:', error);
        alert('이미지를 불러올 수 없습니다.');
    }
}

/**
 * Upload page to pending
 */
async function uploadPageToPending(pageId) {
    const fileInput = document.createElement('input');
    fileInput.type = 'file';
    fileInput.accept = '.png';

    fileInput.onchange = async function() {
        if (!fileInput.files || fileInput.files.length === 0) return;

        const file = fileInput.files[0];

        try {
            const formData = new FormData();
            formData.append('file', file);

            const response = await authenticatedFetch(`/contents/page/${pageId}/upload-pending`, {
                method: 'POST',
                body: formData
            });

            if (!response.ok) {
                const errorData = await response.json();
                throw new Error(errorData.error || 'Upload failed');
            }

            alert('페이지가 대기 상태로 업로드되었습니다.');

            // Update UI
            document.getElementById(`page-pending-${pageId}`).style.display = 'inline-block';
            document.getElementById(`approve-page-${pageId}`).style.display = 'inline-block';

            // Reload data
            await loadHierarchyWithManagers();
            await loadContentTable();

        } catch (error) {
            console.error('Error uploading page:', error);
            alert(error.message);
        }
    };

    fileInput.click();
}

/**
 * Approve page update (책임자 only)
 */
async function approvePageUpdate(pageId) {
    if (!confirm('대기 중인 페이지를 승인하고 현재 페이지를 교체하시겠습니까?')) {
        return;
    }

    try {
        const response = await authenticatedFetch(`/contents/page/${pageId}/approve-update`, {
            method: 'POST'
        });

        if (!response.ok) {
            const errorData = await response.json();
            throw new Error(errorData.error || 'Approval failed');
        }

        alert('페이지가 성공적으로 업데이트되었습니다.');

        // Update UI
        document.getElementById(`page-pending-${pageId}`).style.display = 'none';
        document.getElementById(`approve-page-${pageId}`).style.display = 'none';

        // Reload data
        await loadHierarchyWithManagers();
        await loadContentTable();

    } catch (error) {
        console.error('Error approving page update:', error);
        alert(error.message);
    }
}

/**
 * Add additional content to page
 */
async function addAdditionalContent(pageId) {
    const fileInput = document.createElement('input');
    fileInput.type = 'file';
    fileInput.accept = '.pdf,.mp4,.webm,.mov,.avi,.wmv';

    fileInput.onchange = async function() {
        if (!fileInput.files || fileInput.files.length === 0) return;

        const file = fileInput.files[0];

        try {
            const formData = new FormData();
            formData.append('file', file);

            const response = await authenticatedFetch(`/contents/page/${pageId}/additional`, {
                method: 'POST',
                body: formData
            });

            if (!response.ok) {
                const errorData = await response.json();
                throw new Error(errorData.error || 'Failed to add additional content');
            }

            alert('추가 컨텐츠가 추가되었습니다.');

            // Reload additional content list
            await loadAdditionalContent(pageId);

        } catch (error) {
            console.error('Error adding additional content:', error);
            alert(error.message);
        }
    };

    fileInput.click();
}

/**
 * Upload additional content to pending
 */
async function uploadAdditionalToPending(additionalId) {
    const fileInput = document.createElement('input');
    fileInput.type = 'file';

    fileInput.onchange = async function() {
        if (!fileInput.files || fileInput.files.length === 0) return;

        const file = fileInput.files[0];

        try {
            const formData = new FormData();
            formData.append('file', file);

            const response = await authenticatedFetch(`/contents/additional/${additionalId}/upload-pending`, {
                method: 'POST',
                body: formData
            });

            if (!response.ok) {
                const errorData = await response.json();
                throw new Error(errorData.error || 'Upload failed');
            }

            alert('추가 컨텐츠가 대기 상태로 업로드되었습니다.');

            // Reload additional content list
            const pageId = getCurrentPageId();
            if (pageId) {
                await loadAdditionalContent(pageId);
            }

        } catch (error) {
            console.error('Error uploading additional content:', error);
            alert(error.message);
        }
    };

    fileInput.click();
}

/**
 * Approve additional content update (책임자 only)
 */
async function approveAdditionalUpdate(additionalId) {
    if (!confirm('대기 중인 컨텐츠를 승인하고 현재 컨텐츠를 교체하시겠습니까?')) {
        return;
    }

    try {
        const response = await authenticatedFetch(`/contents/additional/${additionalId}/approve-update`, {
            method: 'POST'
        });

        if (!response.ok) {
            const errorData = await response.json();
            throw new Error(errorData.error || 'Approval failed');
        }

        alert('추가 컨텐츠가 성공적으로 업데이트되었습니다.');

        // Reload additional content list
        const pageId = getCurrentPageId();
        if (pageId) {
            await loadAdditionalContent(pageId);
        }

    } catch (error) {
        console.error('Error approving additional update:', error);
        alert(error.message);
    }
}

/**
 * Download additional content
 */
async function downloadAdditional(additionalId) {
    try {
        const response = await authenticatedFetch(`/contents/additional/${additionalId}/download`);

        if (!response.ok) {
            throw new Error('Download failed');
        }

        const blob = await response.blob();
        const url = window.URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `additional_${additionalId}`;
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        window.URL.revokeObjectURL(url);

    } catch (error) {
        console.error('Error downloading additional content:', error);
        alert('다운로드 실패');
    }
}

/**
 * Delete additional content
 */
async function deleteAdditional(additionalId) {
    if (!confirm('이 추가 컨텐츠를 삭제하시겠습니까?')) {
        return;
    }

    try {
        const response = await authenticatedFetch(`/contents/additional/${additionalId}`, {
            method: 'DELETE'
        });

        if (!response.ok) {
            throw new Error('Delete failed');
        }

        alert('추가 컨텐츠가 삭제되었습니다.');

        // Reload additional content list
        const pageId = getCurrentPageId();
        if (pageId) {
            await loadAdditionalContent(pageId);
        }

    } catch (error) {
        console.error('Error deleting additional content:', error);
        alert('삭제 실패');
    }
}

/**
 * Show image modal
 */
function showImageModal(imageUrl, title) {
    const modal = document.getElementById('image-modal');
    const modalImg = document.getElementById('image-modal-img');
    const modalTitle = document.getElementById('image-modal-title');

    modalTitle.textContent = title || '이미지 보기';
    modalImg.src = imageUrl;

    modal.classList.add('show');
    document.getElementById('modal-overlay').classList.add('show');
}

/**
 * Close image modal
 */
function closeImageModal() {
    const modal = document.getElementById('image-modal');
    modal.classList.remove('show');
    document.getElementById('modal-overlay').classList.remove('show');
}

/**
 * Close all modals
 */
function closeModals() {
    document.querySelectorAll('.modal').forEach(modal => {
        modal.classList.remove('show');
    });
    document.getElementById('modal-overlay').classList.remove('show');
}

/**
 * Refresh content table
 */
async function refreshContentTable() {
    await loadHierarchyWithManagers();
    await loadContentTable();
}

/**
 * Show error message
 */
function showError(message) {
    const errorDiv = document.getElementById('error-message');
    errorDiv.textContent = message;
    errorDiv.style.display = 'block';

    setTimeout(() => {
        errorDiv.style.display = 'none';
    }, 5000);
}

/**
 * Get user info by user ID
 */
async function getUserInfo(userId) {
    try {
        const response = await authenticatedFetch(`/user/info?user_id=${encodeURIComponent(userId)}`);
        if (!response.ok) {
            throw new Error('Failed to fetch user info');
        }
        return await response.json();
    } catch (error) {
        console.error('Error fetching user info:', error);
        return { id: userId, name: '알 수 없음', position: '알 수 없음' };
    }
}

/**
 * Get existing manager for content
 */
async function getExistingManager(type, contentId) {
    try {
        const response = await authenticatedFetch('/contents/content_manager');
        if (!response.ok) {
            throw new Error('Failed to fetch managers');
        }

        const managers = await response.json();
        const idField = type === 'folder' ? 'folder_id' : 'file_id';

        const manager = managers.find(m => m.type === type && m[idField] == contentId);

        if (manager && manager.assignee) {
            return {
                id: manager.id,
                name: manager.assignee.name,
                position: manager.assignee.position,
                user_id: manager.assignee.user_id
            };
        }

        return null;
    } catch (error) {
        console.error('Error fetching existing manager:', error);
        return null;
    }
}

/**
 * Show replace manager confirmation modal
 */
function showReplaceManagerModal(existingManager, newManager, onConfirm) {
    const modal = document.getElementById('replace-manager-modal');
    const overlay = document.getElementById('modal-overlay');

    // Fill in existing manager info
    document.getElementById('existing-manager-name').textContent = existingManager.name || '-';
    document.getElementById('existing-manager-position').textContent = existingManager.position || '-';
    document.getElementById('existing-manager-id').textContent = existingManager.user_id || '-';

    // Fill in new manager info
    document.getElementById('new-manager-name').textContent = newManager.name || '-';
    document.getElementById('new-manager-position').textContent = newManager.position || '-';
    document.getElementById('new-manager-id').textContent = newManager.user_id || '-';

    // Show modal
    modal.classList.add('show');
    overlay.classList.add('show');

    // Setup event handlers
    const yesBtn = document.getElementById('replace-manager-yes-btn');
    const noBtn = document.getElementById('replace-manager-no-btn');
    const closeBtn = document.getElementById('replace-manager-close-btn');

    const handleYes = async () => {
        cleanup();
        await onConfirm();
    };

    const handleNo = () => {
        cleanup();
    };

    const cleanup = () => {
        modal.classList.remove('show');
        overlay.classList.remove('show');
        yesBtn.removeEventListener('click', handleYes);
        noBtn.removeEventListener('click', handleNo);
        closeBtn.removeEventListener('click', handleNo);
    };

    yesBtn.addEventListener('click', handleYes);
    noBtn.addEventListener('click', handleNo);
    closeBtn.addEventListener('click', handleNo);
}

/**
 * Helper functions
 */
function getFileIcon(extension) {
    const icons = {
        '.pdf': '📄',
        '.mp4': '🎬',
        '.webm': '🎬',
        '.mov': '🎬',
        '.avi': '🎬',
        '.wmv': '🎬'
    };
    return icons[extension.toLowerCase()] || '📎';
}

function formatFileSize(bytes) {
    if (!bytes) return '0 B';
    const k = 1024;
    const sizes = ['B', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return Math.round(bytes / Math.pow(k, i) * 100) / 100 + ' ' + sizes[i];
}

function getCurrentPageId() {
    // Helper to get current page ID from expanded row
    const expandedRows = document.querySelectorAll('.additional-content-row.expanded');
    if (expandedRows.length > 0) {
        const id = expandedRows[0].id.replace('additional-content-', '');
        return parseInt(id);
    }
    return null;
}

// Make functions globally accessible
window.viewPageImage = viewPageImage;
window.uploadPageToPending = uploadPageToPending;
window.approvePageUpdate = approvePageUpdate;
window.addAdditionalContent = addAdditionalContent;
window.uploadAdditionalToPending = uploadAdditionalToPending;
window.approveAdditionalUpdate = approveAdditionalUpdate;
window.downloadAdditional = downloadAdditional;
window.deleteAdditional = deleteAdditional;
