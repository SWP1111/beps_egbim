/**
 * 관리자 권한 설정 모달 관리 클래스
 */
class AdminPermissionModal {
    constructor() {
        this.selectedEmployee = null;
        this.isModalInitialized = false;
        this.initializeEventListeners();
    }

    /**
     * 이벤트 리스너 초기화
     */
    initializeEventListeners() {
        // 모달 열기 버튼
        const openBtn = document.getElementById('admin-permission-btn');
        if (openBtn) {
            openBtn.addEventListener('click', () => this.openModal());
        }

        // 모달 닫기 버튼들
        const closeBtn = document.getElementById('modal-close-btn');
        const cancelBtn = document.getElementById('cancel-btn');
        
        if (closeBtn) closeBtn.addEventListener('click', () => this.closeModal());
        if (cancelBtn) cancelBtn.addEventListener('click', () => this.closeModal());

        // 오버레이 클릭으로 모달 닫기
        const overlay = document.getElementById('modal-overlay');
        if (overlay) {
            overlay.addEventListener('click', () => this.closeModal());
        }

        // ESC 키로 모달 닫기
        document.addEventListener('keydown', (e) => {
            if (e.key === 'Escape' && this.isModalOpen()) {
                this.closeModal();
            }
        });

        // 검색 기능
        const searchBtn = document.getElementById('employee-search-btn');
        const searchInput = document.getElementById('employee-search-input');
        
        if (searchBtn) {
            searchBtn.addEventListener('click', () => this.searchEmployees());
        }
        
        if (searchInput) {
            searchInput.addEventListener('keypress', (e) => {
                if (e.key === 'Enter') {
                    this.searchEmployees();
                }
            });
        }

        // 권한 부여 버튼
        const assignBtn = document.getElementById('assign-permission-btn');
        if (assignBtn) {
            assignBtn.addEventListener('click', () => this.assignPermission());
        }

        // 권한 선택 변경 시 버튼 활성화 체크
        const permissionSelect = document.getElementById('admin-permission-select');
        if (permissionSelect) {
            permissionSelect.addEventListener('change', () => this.updateAssignButton());
        }

        // 관리자 목록 새로고침
        const refreshAdminBtn = document.getElementById('refresh-admin-btn');
        if (refreshAdminBtn) {
            refreshAdminBtn.addEventListener('click', () => this.loadAdminList());
        }

        // 권한 필터 변경
        const permissionFilter = document.getElementById('permission-filter');
        if (permissionFilter) {
            permissionFilter.addEventListener('change', () => this.loadAdminList());
        }
    }

    /**
     * 모달 열기
     */
    openModal() {
        const modal = document.getElementById('admin-permission-modal');
        const overlay = document.getElementById('modal-overlay');
        
        if (modal && overlay) {
            overlay.style.display = 'block';
            modal.style.display = 'flex';
            document.body.style.overflow = 'hidden'; // 배경 스크롤 방지
            
            // 검색 입력 필드에 포커스
            setTimeout(() => {
                const searchInput = document.getElementById('employee-search-input');
                if (searchInput) searchInput.focus();
            }, 100);

            // 관리자 목록 로드
            this.loadAdminList();
        }
    }

    /**
     * 모달 닫기
     */
    closeModal() {
        const modal = document.getElementById('admin-permission-modal');
        const overlay = document.getElementById('modal-overlay');
        
        if (modal && overlay) {
            overlay.style.display = 'none';
            modal.style.display = 'none';
            document.body.style.overflow = ''; // 배경 스크롤 복원
            
            this.resetModal();
        }
    }

    /**
     * 모달이 열려있는지 확인
     */
    isModalOpen() {
        const modal = document.getElementById('admin-permission-modal');
        return modal && modal.style.display === 'flex';
    }

    /**
     * 모달 초기화
     */
    resetModal() {
        // 폼 초기화
        const searchInput = document.getElementById('employee-search-input');
        const permissionSelect = document.getElementById('admin-permission-select');
        
        if (searchInput) searchInput.value = '';
        if (permissionSelect) permissionSelect.value = '';
        
        // 검색 결과 숨기기
        this.hideElement('search-results-section');
        this.hideElement('selected-employee-section');
        
        // 메시지 숨기기
        this.hideMessages();
        
        // 선택된 직원 정보 초기화
        this.selectedEmployee = null;
        this.updateAssignButton();
        
        // 관리자 목록 초기화 (다시 로드하지 않고 로딩 메시지만 표시)
        const adminTbody = document.getElementById('admin-table-tbody');
        if (adminTbody) {
            adminTbody.innerHTML = '<tr><td colspan="9" class="loading-message">관리자 목록을 불러오는 중...</td></tr>';
        }

        // 권한 필터 초기화
        const permissionFilter = document.getElementById('permission-filter');
        if (permissionFilter) {
            permissionFilter.value = '';
        }

        // 헤더 제목 초기화
        const headerTitle = document.querySelector('.admin-list-header h3');
        if (headerTitle) {
            headerTitle.textContent = '사용자 권한 목록';
        }
    }

    /**
     * 직원 검색
     */
    async searchEmployees() {
        const searchInput = document.getElementById('employee-search-input');
        if (!searchInput) return;

        const searchTerm = searchInput.value.trim();
        
        if (!searchTerm) {
            // 검색어가 없으면 검색 결과와 선택된 직원 정보 모두 초기화
            this.clearSearchResults();
            this.clearSelectedEmployee();
            this.showError('검색어를 입력해주세요.');
            return;
        }

        // 새로운 검색 시 이전 선택된 직원 정보 초기화
        this.clearSelectedEmployee();

        // 로딩 상태 표시
        const searchBtn = document.getElementById('employee-search-btn');
        if (searchBtn) {
            searchBtn.textContent = '검색 중...';
            searchBtn.disabled = true;
        }

        try {
            // API 호출 (실제 구현 시 적절한 엔드포인트로 변경)
            const response = await this.fetchEmployees(searchTerm);
            const employees = await response.json();
            
            this.displaySearchResults(employees);
        } catch (error) {
            console.error('직원 검색 오류:', error);
            this.showError('직원 검색 중 오류가 발생했습니다.');
        } finally {
            // 로딩 상태 해제
            if (searchBtn) {
                searchBtn.textContent = '검색';
                searchBtn.disabled = false;
            }
        }
    }

    /**
     * 직원 검색 API 호출
     */
    async fetchEmployees(searchTerm) {
        try {
            // 기존 user/search API 사용
            const response = await fetch(`${window.baseUrl}user/search?keyword=${encodeURIComponent(searchTerm)}`, {
                method: 'GET',
                credentials: 'include', // 쿠키 포함
                headers: {
                    'Content-Type': 'application/json',
                }
            });

            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }

            return response;
        } catch (error) {
            console.error('직원 검색 실패:', error);
            throw error;
        }
    }

    /**
     * 검색 결과 표시
     */
    displaySearchResults(searchResult) {
        const resultsSection = document.getElementById('search-results-section');
        const resultsCount = document.getElementById('results-count');
        const tbody = document.getElementById('search-results-tbody');

        if (!resultsSection || !resultsCount || !tbody) return;

        // /user/search API는 { company: { department: [users] } } 형태로 응답
        const employees = [];
        
        // 중첩된 객체에서 사용자 정보 추출
        Object.keys(searchResult).forEach(company => {
            Object.keys(searchResult[company]).forEach(department => {
                if (Array.isArray(searchResult[company][department])) {
                    employees.push(...searchResult[company][department]);
                }
            });
        });

        if (employees.length === 0) {
            this.showError('검색 결과가 없습니다.');
            resultsSection.style.display = 'none';
            return;
        }

        resultsCount.textContent = `${employees.length}명 찾음`;
        tbody.innerHTML = '';

        employees.forEach((employee) => {
            const row = this.createEmployeeRow(employee);
            tbody.appendChild(row);
        });

        resultsSection.style.display = 'block';
        this.hideMessages();
    }

    /**
     * 직원 행 생성
     */
    createEmployeeRow(employee) {
        const row = document.createElement('tr');
        
        // role_id를 권한 레이블로 변환
        const currentPermission = employee.role_id ? 
            this.getPermissionLabel(this.getRoleIdPermission(employee.role_id)) : '일반사용자(사내)';
            
        row.innerHTML = `
            <td><input type="radio" name="employee-select" value="${employee.id || ''}"></td>
            <td>${this.escapeHtml(employee.id || '')}</td>
            <td>${this.escapeHtml(employee.company || '')}</td>
            <td>${this.escapeHtml(employee.department || '')}</td>
            <td>${this.escapeHtml(employee.name || '')}</td>
            <td>${this.escapeHtml(employee.position || '')}</td>
            <td>${this.escapeHtml(employee.email || '-')}</td>
            <td>${this.escapeHtml(currentPermission)}</td>
        `;

        const radio = row.querySelector('input[type="radio"]');
        if (radio) {
            radio.addEventListener('change', () => {
                if (radio.checked) {
                    this.selectEmployee(employee);
                    // 다른 행의 선택 표시 제거 후 현재 행 선택 표시
                    this.updateRowSelection(row);
                }
            });
        }

        return row;
    }

    /**
     * 행 선택 상태 업데이트
     */
    updateRowSelection(selectedRow) {
        const allRows = document.querySelectorAll('.results-table tbody tr');
        allRows.forEach(row => row.classList.remove('selected'));
        selectedRow.classList.add('selected');
    }

    /**
     * 직원 선택
     */
    selectEmployee(employee) {
        this.selectedEmployee = employee;
        this.displaySelectedEmployee(employee);
        this.updateAssignButton();
    }

    /**
     * 선택된 직원 정보 표시
     */
    displaySelectedEmployee(employee) {
        const elements = {
            'selected-name': `이름: ${employee.name || ''}`,
            'selected-id': `사번: ${employee.id || ''}`,
            'selected-email': `메일: ${employee.email || '-'}`,
            'selected-company': `회사: ${employee.company || ''}`,
            'selected-department': `부서: ${employee.department || ''}`,
            'selected-position': `직급: ${employee.position || ''}`
        };

        Object.entries(elements).forEach(([id, text]) => {
            const element = document.getElementById(id);
            if (element) element.textContent = text;
        });
        
        this.showElement('selected-employee-section');
    }

    /**
     * 권한 부여 버튼 상태 업데이트
     */
    updateAssignButton() {
        const assignBtn = document.getElementById('assign-permission-btn');
        const permissionSelect = document.getElementById('admin-permission-select');
        
        if (assignBtn && permissionSelect) {
            const hasEmployee = !!this.selectedEmployee;
            const hasPermission = !!permissionSelect.value;
            
            assignBtn.disabled = !hasEmployee || !hasPermission;
        }
    }

    /**
     * 권한 부여
     */
    async assignPermission() {
        if (!this.selectedEmployee) {
            this.showError('직원을 선택해주세요.');
            return;
        }

        const permissionSelect = document.getElementById('admin-permission-select');
        if (!permissionSelect) return;

        const permission = permissionSelect.value;
        if (!permission) {
            this.showError('권한을 선택해주세요.');
            return;
        }

        // 로딩 상태 표시
        const assignBtn = document.getElementById('assign-permission-btn');
        if (assignBtn) {
            assignBtn.textContent = '처리 중...';
            assignBtn.disabled = true;
        }

        try {
            const response = await this.assignEmployeePermission(this.selectedEmployee.id, permission);
            
            if (response.ok) {
                this.showSuccess(`${this.selectedEmployee.name}님에게 ${this.getPermissionLabel(permission)} 권한이 부여되었습니다.`);
                
                // 관리자 목록 새로고침
                this.loadAdminList();
                
                // 폼 초기화 (모달은 열어둠)
                this.resetSearchForm();
            } else {
                const errorData = await response.json().catch(() => ({}));
                this.showError(errorData.message || '권한 부여 중 오류가 발생했습니다.');
            }
        } catch (error) {
            console.error('권한 부여 오류:', error);
            this.showError('권한 부여 중 오류가 발생했습니다.');
        } finally {
            // 로딩 상태 해제
            if (assignBtn) {
                assignBtn.textContent = '권한 부여';
                this.updateAssignButton();
            }
        }
    }

    /**
     * 권한 부여 API 호출
     */
    async assignEmployeePermission(employeeId, permission) {
        try {
            // 권한을 role_id로 변환
            const roleId = this.getPermissionRoleId(permission);
            if (!roleId) {
                throw new Error('Invalid permission');
            }
            
            const response = await fetch(`${window.baseUrl}user/update_permission`, {
                method: 'POST',
                credentials: 'include', // 쿠키 포함
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    user_id: employeeId,
                    role_id: roleId
                })
            });
            
            return response;
        } catch (error) {
            console.error('권한 부여 API 호출 실패:', error);
            throw error;
        }
    }

    /**
     * 관리자 목록 로드
     */
    async loadAdminList() {
        const tbody = document.getElementById('admin-table-tbody');
        const refreshBtn = document.getElementById('refresh-admin-btn');
        const permissionFilter = document.getElementById('permission-filter');
        
        if (!tbody) return;

        // 현재 선택된 필터 값 가져오기
        const selectedPermission = permissionFilter ? permissionFilter.value : '';

        // 로딩 상태 표시
        tbody.innerHTML = '<tr><td colspan="9" class="loading-message">관리자 목록을 불러오는 중...</td></tr>';
        
        if (refreshBtn) {
            refreshBtn.textContent = '새로고침 중...';
            refreshBtn.disabled = true;
        }

        try {
            const response = await this.fetchAdminList(selectedPermission);
            const data = await response.json();
            
            // API 응답에서 users 배열 추출
            const admins = data.users || [];
            this.displayAdminList(admins, data);
        } catch (error) {
            console.error('관리자 목록 로드 오류:', error);
            tbody.innerHTML = '<tr><td colspan="7" class="no-data-message">관리자 목록을 불러오는데 실패했습니다.</td></tr>';
        } finally {
            // 로딩 상태 해제
            if (refreshBtn) {
                refreshBtn.textContent = '새로고침';
                refreshBtn.disabled = false;
            }
        }
    }

    /**
     * 관리자 목록 API 호출
     */
    async fetchAdminList(permissionFilter = '') {
        try {
            // 권한 필터가 있으면 해당 role_id로 요청, 없으면 전체 조회
            let url = `${window.baseUrl}user/users_by_role`;
            
            // 권한 필터가 있으면 role_id로 변환해서 쿼리 파라미터로 추가
            if (permissionFilter) {
                const roleId = this.getPermissionRoleId(permissionFilter);
                if (roleId) {
                    url += `?role_id=${roleId}`;
                }
            }
            
            const response = await fetch(url, {
                method: 'GET',
                credentials: 'include', // 쿠키 포함
                headers: {
                    'Content-Type': 'application/json',
                }
            });
            
            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }
            
            return response;
        } catch (error) {
            console.error('관리자 목록 조회 실패:', error);
            throw error;
        }
    }

    /**
     * 관리자 목록 표시
     */
    displayAdminList(admins, apiData = null) {
        const tbody = document.getElementById('admin-table-tbody');
        const permissionFilter = document.getElementById('permission-filter');
        
        if (!tbody) return;

        if (!admins || admins.length === 0) {
            const filterText = permissionFilter && permissionFilter.value ? 
                `'${this.getPermissionLabel(permissionFilter.value)}' 권한을 가진 직원이 없습니다.` : 
                '등록된 직원이 없습니다.';
            tbody.innerHTML = `<tr><td colspan="7" class="no-data-message">${filterText}</td></tr>`;
            
            // 헤더 제목 초기화
            const headerTitle = document.querySelector('.admin-list-header h3');
            if (headerTitle) {
                headerTitle.textContent = '사용자 권한 목록';
            }
            
            return;
        }

        tbody.innerHTML = '';

        admins.forEach((admin) => {
            const row = this.createAdminRow(admin);
            tbody.appendChild(row);
        });

        // 필터 적용 상태 표시
        this.updateFilterStatus(admins.length, apiData);
    }

    /**
     * 필터 상태 업데이트
     */
    updateFilterStatus(count, apiData = null) {
        const permissionFilter = document.getElementById('permission-filter');
        const headerTitle = document.querySelector('.admin-list-header h3');
        
        if (!headerTitle || !permissionFilter) return;

        if (apiData && apiData.role_name) {
            headerTitle.textContent = `사용자 권한 목록 (${apiData.role_name}: ${count}명)`;
        } else if (permissionFilter.value) {
            const permissionLabel = this.getPermissionLabel(permissionFilter.value);
            headerTitle.textContent = `사용자 권한 목록 (${permissionLabel}: ${count}명)`;
        } else {
            headerTitle.textContent = `사용자 권한 목록 (전체: ${count}명)`;
        }
    }

    /**
     * 관리자 행 생성
     */
    createAdminRow(admin) {
        const row = document.createElement('tr');
        
        // role_id를 permission 키로 변환
        const permission = this.getRoleIdPermission(admin.role_id);
        
        row.innerHTML = `
            <td>${this.escapeHtml(admin.id || admin.employee_id || '')}</td>
            <td>${this.escapeHtml(admin.company || '')}</td>
            <td>${this.escapeHtml(admin.department || '')}</td>
            <td>${this.escapeHtml(admin.name || '')}</td>
            <td>${this.escapeHtml(admin.position || '')}</td>
            <td>${this.escapeHtml(admin.email || '')}</td>
            <td><span class="permission-badge">${this.escapeHtml(this.getPermissionLabel(permission) || '')}</span></td>
        `;

        // 권한 배지에 색상 적용
        const badge = row.querySelector('.permission-badge');
        if (badge && permission) {
            this.applyPermissionBadgeStyle(badge, permission);
        }

        return row;
    }

    /**
     * 권한 배지 스타일 적용
     */
    applyPermissionBadgeStyle(badge, permission) {
        const permissionStyles = {
            'integrated_admin': { background: '#dc3545', color: 'white' },
            'dev_admin': { background: '#fd7e14', color: 'white' },
            'content_admin': { background: '#20c997', color: 'white' },
            'content_worker': { background: '#17a2b8', color: 'white' },
            'internal_user': { background: '#6f42c1', color: 'white' },
            'external_user': { background: '#6c757d', color: 'white' }
        };

        const style = permissionStyles[permission];
        if (style) {
            badge.style.backgroundColor = style.background;
            badge.style.color = style.color;
        } else {
            // 기본 스타일
            badge.style.backgroundColor = '#6c757d';
            badge.style.color = 'white';
        }
    }

    /**
     * 관리자 권한 해제
     */
    async revokeAdminPermission(adminId, adminName) {
        if (!confirm(`${adminName}님의 관리자 권한을 해제하시겠습니까?`)) {
            return;
        }

        const revokeBtn = document.querySelector(`[data-admin-id="${adminId}"]`);
        
        // 로딩 상태 표시
        if (revokeBtn) {
            revokeBtn.textContent = '처리 중...';
            revokeBtn.disabled = true;
        }

        try {
            const response = await this.revokePermissionAPI(adminId);
            
            if (response.ok) {
                this.showSuccess(`${adminName}님의 관리자 권한이 해제되었습니다.`);
                
                // 관리자 목록 새로고침
                this.loadAdminList();
            } else {
                const errorData = await response.json().catch(() => ({}));
                this.showError(errorData.message || '권한 해제 중 오류가 발생했습니다.');
            }
        } catch (error) {
            console.error('권한 해제 오류:', error);
            this.showError('권한 해제 중 오류가 발생했습니다.');
        } finally {
            // 로딩 상태 해제
            if (revokeBtn) {
                revokeBtn.textContent = '권한 해제';
                revokeBtn.disabled = false;
            }
        }
    }

    /**
     * 권한 해제 API 호출 (실제 구현 시 수정 필요)
     */
    async revokePermissionAPI(adminId) {
        // 실제 API 엔드포인트로 변경 필요
        return await fetch(`/api/admin/permissions/${adminId}`, {
            method: 'DELETE',
            headers: {
                'Content-Type': 'application/json',
                // 인증 헤더 등 필요한 헤더 추가
            }
        });
    }

    /**
     * 선택된 직원 정보만 초기화
     */
    clearSelectedEmployee() {
        // 선택된 직원 정보 초기화
        this.selectedEmployee = null;
        
        // 선택된 직원 섹션 숨기기
        this.hideElement('selected-employee-section');
        
        // 권한 부여 버튼 상태 업데이트
        this.updateAssignButton();
    }

    /**
     * 검색 결과만 초기화
     */
    clearSearchResults() {
        // 검색 결과 섹션 숨기기
        this.hideElement('search-results-section');
        
        // 검색 결과 테이블 초기화
        const resultsTableBody = document.getElementById('search-results-tbody');
        if (resultsTableBody) {
            resultsTableBody.innerHTML = '';
        }
        
        // 결과 카운트 초기화
        const resultsCount = document.getElementById('results-count');
        if (resultsCount) {
            resultsCount.textContent = '';
        }
    }

    /**
     * 검색 폼만 초기화 (관리자 목록은 유지)
     */
    resetSearchForm() {
        // 검색 폼 초기화
        const searchInput = document.getElementById('employee-search-input');
        const permissionSelect = document.getElementById('admin-permission-select');
        
        if (searchInput) searchInput.value = '';
        if (permissionSelect) permissionSelect.value = '';
        
        // 검색 결과 숨기기
        this.hideElement('search-results-section');
        this.hideElement('selected-employee-section');
        
        // 선택된 직원 정보 초기화
        this.selectedEmployee = null;
        this.updateAssignButton();
    }

    /**
     * 권한 레이블 반환
     */
    getPermissionLabel(permission) {
        const labels = {
            'integrated_admin': '통합관리자',
            'dev_admin': '개발관리자',
            // 'content_admin': 'Content_관리자',
            // 'content_worker': 'Content_실무자',
            'internal_user': '일반사용자(사내)',
            'external_user': '일반사용자(사외)'
        };
        return labels[permission] || permission;
    }

    /**
     * 권한을 role_id로 변환
     */
    getPermissionRoleId(permission) {
        const roleMapping = {
            'integrated_admin': 1,
            'dev_admin': 2,
            // 'content_admin': 3,
            // 'content_worker': 4,
            'internal_user': 5,
            'external_user': 6
        };
        return roleMapping[permission] || null;
    }

    /**
     * role_id를 권한 키로 변환
     */
    getRoleIdPermission(roleId) {
        const permissionMapping = {
            1: 'integrated_admin',
            2: 'dev_admin',
            // 3: 'content_admin',
            // 4: 'content_worker',
            5: 'internal_user',
            6: 'external_user'
        };
        return permissionMapping[roleId] || 'internal_user'; // 기본값은 일반사용자(사내)
    }

    /**
     * 에러 메시지 표시
     */
    showError(message) {
        const errorDiv = document.getElementById('modal-error-message');
        if (errorDiv) {
            errorDiv.textContent = message;
            errorDiv.style.display = 'block';
        }
        this.hideElement('modal-success-message');
    }

    /**
     * 성공 메시지 표시
     */
    showSuccess(message) {
        const successDiv = document.getElementById('modal-success-message');
        if (successDiv) {
            successDiv.textContent = message;
            successDiv.style.display = 'block';
        }
        this.hideElement('modal-error-message');
    }

    /**
     * 메시지 숨기기
     */
    hideMessages() {
        this.hideElement('modal-error-message');
        this.hideElement('modal-success-message');
    }

    /**
     * 요소 숨기기
     */
    hideElement(elementId) {
        const element = document.getElementById(elementId);
        if (element) element.style.display = 'none';
    }

    /**
     * 요소 보이기
     */
    showElement(elementId) {
        const element = document.getElementById(elementId);
        if (element) element.style.display = 'block';
    }

    /**
     * HTML 이스케이프
     */
    escapeHtml(text) {
        const map = {
            '&': '&amp;',
            '<': '&lt;',
            '>': '&gt;',
            '"': '&quot;',
            "'": '&#039;'
        };
        return text.toString().replace(/[&<>"']/g, function(m) { return map[m]; });
    }
}

// 페이지 로드 시 초기화
document.addEventListener('DOMContentLoaded', () => {
    // 관리자 권한 모달 초기화
    new AdminPermissionModal();
});

// 전역에서 접근 가능하도록 설정 (필요한 경우)
window.AdminPermissionModal = AdminPermissionModal;
