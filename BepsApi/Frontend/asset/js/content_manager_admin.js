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
    // Get user info from localStorage
    const userInfo = JSON.parse(localStorage.getItem("loggedInUser") || "{}");
    currentUserRole = userInfo && userInfo.user ? userInfo.user.role_id : null;
    currentUserId = userInfo && userInfo.user ? userInfo.user.id : null;
    jwtToken = userInfo.token;

    if (!jwtToken) {
        alert('로그인이 필요합니다.');
        window.location.href = '/login.html';
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

    } catch (error) {
        console.error('Error initializing page:', error);
        showError('페이지 초기화 중 오류가 발생했습니다.');
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

    return fetch(url, {
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
        const response = await authenticatedFetch('/contents/assign-manager', {
            method: 'POST',
            body: JSON.stringify({
                folder_id: categoryId,
                manager_id: supervisorId,
                manager_type: 'supervisor'
            })
        });

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
        const response = await authenticatedFetch('/contents/assign-manager', {
            method: 'POST',
            body: JSON.stringify({
                file_id: pageId,
                manager_id: workerId,
                manager_type: 'worker'
            })
        });

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
    tbody.innerHTML = '<tr><td colspan="7" class="loading-message">컨텐츠 목록을 불러오는 중...</td></tr>';

    if (!hierarchyData || !hierarchyData.channels) {
        tbody.innerHTML = '<tr><td colspan="7" class="loading-message">표시할 데이터가 없습니다.</td></tr>';
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

                    // Additional content row (hidden by default)
                    const additionalRow = createAdditionalContentRow(page);
                    tbody.appendChild(additionalRow);

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

    // Expand arrow column (only for pages)
    const expandCell = document.createElement('td');
    if (page) {
        const arrow = document.createElement('span');
        arrow.className = 'expand-arrow';
        arrow.textContent = '▶';
        arrow.dataset.pageId = page.id;
        arrow.addEventListener('click', function() {
            toggleAdditionalContent(page.id, arrow);
        });
        expandCell.appendChild(arrow);
    }
    row.appendChild(expandCell);

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

    // Page column
    const pageCell = document.createElement('td');
    pageCell.textContent = page ? page.name : '-';
    if (page && page.has_pending) {
        const badge = document.createElement('span');
        badge.className = 'pending-badge';
        badge.textContent = 'NEW';
        pageCell.appendChild(badge);
    }
    row.appendChild(pageCell);

    // Supervisor column (책임자) - from category
    if (isFirstCategoryRow) {
        const supervisorCell = document.createElement('td');
        supervisorCell.rowSpan = categoryRowSpan;
        if (category.manager) {
            supervisorCell.appendChild(createManagerInfo(category.manager));
        } else {
            const emptyDiv = document.createElement('div');
            emptyDiv.className = 'manager-info empty';
            emptyDiv.textContent = '미지정';
            supervisorCell.appendChild(emptyDiv);
        }
        row.appendChild(supervisorCell);
    }

    // Worker column (실무자) - from page
    const workerCell = document.createElement('td');
    if (page && page.manager) {
        workerCell.appendChild(createManagerInfo(page.manager));
    } else {
        const emptyDiv = document.createElement('div');
        emptyDiv.className = 'manager-info empty';
        emptyDiv.textContent = page ? '미지정' : '-';
        workerCell.appendChild(emptyDiv);
    }
    row.appendChild(workerCell);

    // Action column
    const actionCell = document.createElement('td');
    actionCell.className = 'action-col';
    if (page || (category && !page)) {
        const btnContainer = document.createElement('div');
        btnContainer.className = 'action-buttons';

        // Edit button
        const editBtn = document.createElement('button');
        editBtn.className = 'edit-btn';
        editBtn.textContent = '수정';
        editBtn.addEventListener('click', () => {
            if (page) {
                editPageManager(page.id);
            } else {
                editCategoryManager(category.id);
            }
        });
        btnContainer.appendChild(editBtn);

        // Delete button
        const deleteBtn = document.createElement('button');
        deleteBtn.className = 'delete-btn';
        deleteBtn.textContent = '삭제';
        deleteBtn.addEventListener('click', () => {
            if (page) {
                deletePageManager(page.id);
            } else {
                deleteCategoryManager(category.id);
            }
        });
        btnContainer.appendChild(deleteBtn);

        actionCell.appendChild(btnContainer);
    }
    row.appendChild(actionCell);

    return row;
}

/**
 * Create manager info display
 */
function createManagerInfo(manager) {
    const div = document.createElement('div');
    div.className = 'manager-info';

    const nameSpan = document.createElement('span');
    nameSpan.className = 'name';
    nameSpan.textContent = manager.name || '-';
    div.appendChild(nameSpan);

    const positionSpan = document.createElement('span');
    positionSpan.className = 'position';
    positionSpan.textContent = manager.position || '-';
    div.appendChild(positionSpan);

    const idSpan = document.createElement('span');
    idSpan.className = 'id';
    idSpan.textContent = manager.user_id || '-';
    div.appendChild(idSpan);

    return div;
}

/**
 * Create additional content row (expandable section)
 */
function createAdditionalContentRow(page) {
    const row = document.createElement('tr');
    row.className = 'additional-content-row';
    row.id = `additional-content-${page.id}`;

    const cell = document.createElement('td');
    cell.colSpan = 7;
    cell.className = 'additional-content-cell';

    const container = document.createElement('div');
    container.className = 'additional-content-container';
    container.id = `additional-container-${page.id}`;

    // Header
    const header = document.createElement('div');
    header.className = 'additional-content-header';
    header.innerHTML = '<h4>페이지 이미지 및 추가 컨텐츠</h4>';
    container.appendChild(header);

    // Page image section
    const imageSection = document.createElement('div');
    imageSection.className = 'page-image-section';
    imageSection.innerHTML = `
        <div class="page-image-item">
            <div class="page-image-info">
                <span class="page-image-icon">🖼️</span>
                <span class="page-image-name">${page.name}.png</span>
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

    cell.appendChild(container);
    row.appendChild(cell);

    return row;
}

/**
 * Toggle additional content visibility
 */
async function toggleAdditionalContent(pageId, arrowElement) {
    const row = document.getElementById(`additional-content-${pageId}`);

    if (row.classList.contains('expanded')) {
        // Collapse
        row.classList.remove('expanded');
        arrowElement.classList.remove('expanded');
    } else {
        // Expand
        row.classList.add('expanded');
        arrowElement.classList.add('expanded');

        // Load additional content if not loaded yet
        const listContainer = document.getElementById(`additional-files-list-${pageId}`);
        if (listContainer.querySelector('.loading-message')) {
            await loadAdditionalContent(pageId);
        }
    }
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

/**
 * Edit/delete manager functions (placeholder - implement as needed)
 */
function editCategoryManager(categoryId) {
    alert(`Edit category manager: ${categoryId} (기능 준비 중)`);
}

function editPageManager(pageId) {
    alert(`Edit page manager: ${pageId} (기능 준비 중)`);
}

function deleteCategoryManager(categoryId) {
    if (confirm('이 카테고리의 책임자를 삭제하시겠습니까?')) {
        alert(`Delete category manager: ${categoryId} (기능 준비 중)`);
    }
}

function deletePageManager(pageId) {
    if (confirm('이 페이지의 실무자를 삭제하시겠습니까?')) {
        alert(`Delete page manager: ${pageId} (기능 준비 중)`);
    }
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
