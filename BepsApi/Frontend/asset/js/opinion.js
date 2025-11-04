console.log("opinion.js");

const { createApp, ref, reactive, computed, onMounted } = Vue;

const url = typeof baseUrl != "undefined" ? baseUrl : "http://172.16.40.192:20000/";

// User cache to avoid repeated API failures
const userCache = {};

createApp({
    setup() {
        const memoList = ref([]);
        const currentPage = ref(1);
        const totalPages = ref(1);
        const pageSize = 10;

        // Search filters
        const searchContent = ref('');
        const searchStartDate = ref('');
        const searchEndDate = ref('');
        
        // Sorting
        const sortType = ref('id'); // Default sort by ID in descending order
        
        // Period filters
        const selectedYear = ref(new Date().getFullYear());
        const isAnnualMode = ref(true);
        const selectedHalfYear = ref('');
        const selectedQuarter = ref('');
        const availableYears = ref([]);
        
        // URL params for file_id and folder_id
        const urlParams = new URLSearchParams(window.location.search);
        const fileId = urlParams.get('file_id');
        const folderId = urlParams.get('folder_id');
        const path = urlParams.get('path');

        // Current user data
        const currentUser = ref({});

        const isAdmin = computed(() => {
            const userInfo = JSON.parse(sessionStorage.getItem("loggedInUser"));
            return userInfo.user.role_id == 1;
        });

        const visiblePages = computed(() => {
            let pages = [];
        
            if (totalPages.value <= 7) {
                return Array.from({ length: totalPages.value }, (_, i) => i + 1);
            }
        
            let startPage, endPage;
        
            if (currentPage.value <= 4) {
                startPage = 1;
                endPage = 5;
            } else if (currentPage.value >= totalPages.value - 3) {
                startPage = totalPages.value - 4;
                endPage = totalPages.value;
            } else {
                startPage = currentPage.value - 2;
                endPage = currentPage.value + 2;
            }
        
            pages = Array.from({ length: endPage - startPage + 1 }, (_, i) => startPage + i);
        
            if (pages[0] !== 1) {
                pages.unshift(1);
                if (pages[1] !== 2) {
                    pages.splice(1, 0, "..."); 
                }
            }
        
            if (pages[pages.length - 1] !== totalPages.value) {
                if (pages[pages.length - 1] !== totalPages.value - 1) {
                    pages.push("...");
                }
                pages.push(totalPages.value);
            }
        
            return pages;
        });

        const formatStatus = (status) => {
            switch(status) {
                case 0: return '답변대기';
                case 1: return '답변완료';
                case 2: return '처리완료';
                default: return '알 수 없음';
            }
        };

        const formatMemoPath = (path) => {
            if (!path) return '';
            
            // Remove the first '/'
            let formatted = path.startsWith('/') ? path.substring(1) : path;
            
            // Remove all instances of '###_' patterns
            formatted = formatted.replace(/\d+_/g, '');
            
            // Remove file extensions
            formatted = formatted.replace(/\.[^/.]+$/, '');
            
            return formatted;
        };

        const formatDate = (dateString) => {
            if (!dateString) return '';
            const date = new Date(dateString);
            if (isNaN(date.getTime())) return '';
            return date.toLocaleString('ko-KR', {
                year: 'numeric',
                month: '2-digit',
                day: '2-digit',
                hour: '2-digit',
                minute: '2-digit'
            }).replace(/\./g, '-');
        };

        const sortMemoData = (data, type) => {
            if (type === 'date') {
                // Sort by registration date, latest first
                return data.sort((a, b) => {
                    const dateA = new Date(a.created_at || 0);
                    const dateB = new Date(b.created_at || 0);
                    return dateB - dateA; // Latest first
                });
            } else if (type === 'status') {
                // Sort by status (low status number first), then by date (latest first)
                return data.sort((a, b) => {
                    const statusA = a.status || 0;
                    const statusB = b.status || 0;
                    
                    if (statusA !== statusB) {
                        return statusA - statusB; // Low status first
                    }
                    
                    // Same status, sort by date (latest first)
                    const dateA = new Date( a.created_at || 0);
                    const dateB = new Date( b.created_at || 0);
                    return dateB - dateA;
                });
            } else if (type === 'id') {
                // Sort by ID in descending order (highest ID first)
                return data.sort((a, b) => {
                    const idA = parseInt(a.id) || 0;
                    const idB = parseInt(b.id) || 0;
                    return idB - idA; // Descending order
                });
            }
            return data;
        };

        const sortByDate = () => {
            sortType.value = 'date';
            if (memoList.value.length > 0) {
                memoList.value = sortMemoData([...memoList.value], 'date');
            }
        };

        const sortByStatus = () => {
            sortType.value = 'status';
            if (memoList.value.length > 0) {
                memoList.value = sortMemoData([...memoList.value], 'status');
            }
        };

        const sortById = () => {
            sortType.value = 'id';
            if (memoList.value.length > 0) {
                memoList.value = sortMemoData([...memoList.value], 'id');
            }
        };

        const extractAvailableYears = (memos) => {
            const years = new Set();
            memos.forEach(memo => {
                if ( memo.created_at) {
                    const date = new Date( memo.created_at);
                    if (!isNaN(date.getTime())) {
                        years.add(date.getFullYear());
                    }
                }
            });
            return Array.from(years).sort((a, b) => b - a); // Latest year first
        };

        const onYearChange = () => {
            sortType.value = 'id'; // Sort by ID when year changes
            loadMemoData(1);
        };

        const onAnnualChange = () => {
            if (isAnnualMode.value) {
                selectedHalfYear.value = '';
                selectedQuarter.value = '';
            }
            sortType.value = 'id'; // Sort by ID when annual mode changes
            loadMemoData(1);
        };

        const onHalfYearChange = () => {
            if (selectedHalfYear.value) {
                isAnnualMode.value = false;
                selectedQuarter.value = '';
            }
            sortType.value = 'id'; // Sort by ID when half-year changes
            loadMemoData(1);
        };

        const onQuarterChange = () => {
            if (selectedQuarter.value) {
                isAnnualMode.value = false;
                selectedHalfYear.value = '';
            }
            sortType.value = 'id'; // Sort by ID when quarter changes
            loadMemoData(1);
        };

        const filterByPeriod = (memos) => {
            if (!selectedYear.value) return memos;

            return memos.filter(memo => {
                const memoDate = new Date(memo.created_at);
                if (isNaN(memoDate.getTime())) return false;

                const memoYear = memoDate.getFullYear();
                if (memoYear !== selectedYear.value) return false;

                // If annual mode or no specific period selected
                if (isAnnualMode.value || (!selectedHalfYear.value && !selectedQuarter.value)) {
                    return true;
                }

                // Half-year filtering
                if (selectedHalfYear.value) {
                    const month = memoDate.getMonth() + 1; // 1-12
                    if (selectedHalfYear.value === '1') {
                        return month >= 1 && month <= 6; // 상반기
                    } else if (selectedHalfYear.value === '2') {
                        return month >= 7 && month <= 12; // 하반기
                    }
                }

                // Quarter filtering
                if (selectedQuarter.value) {
                    const month = memoDate.getMonth() + 1; // 1-12
                    const quarter = Math.ceil(month / 3);
                    return quarter === parseInt(selectedQuarter.value);
                }

                return true;
            });
        };

        const loadCurrentUser = () => {
            try {
                const loggedInUser = JSON.parse(sessionStorage.getItem("loggedInUser"));
                if (loggedInUser && loggedInUser.user) {
                    currentUser.value = {
                        id: loggedInUser.user.id,
                        name: loggedInUser.user.name || '',
                        position: loggedInUser.user.position || '',
                        company: loggedInUser.user.company || '',
                        department: loggedInUser.user.department || ''
                    };
                } else {
                    // Redirect to login if no user data found
                    window.top.location.href = "login.html";
                }
            } catch (error) {
                console.error("Error loading current user data:", error);
                window.top.location.href = "login.html";
            }
        };

        const loadMemoData = (page = 1) => {
            if (page < 1 || (page > totalPages.value && totalPages.value > 0)) {
                return;
            }
            
            currentPage.value = page;
            
            // Build URL with query parameters
            let fetchUrl = `${url}memo/`;
            let queryParams = [];
            
            if (fileId) {
                queryParams.push(`file_id=${fileId}`);
            }
            
            if (folderId) {
                queryParams.push(`folder_id=${folderId}`);
            }
            
            if (path) {
                queryParams.push(`path=${encodeURIComponent(path)}`);
            }
            
            if (queryParams.length > 0) {
                fetchUrl += `?${queryParams.join('&')}`;
            }
            
            fetch(fetchUrl, {
                method: "GET",
                credentials: "include",
                headers: {
                    "Accept": "application/json",
                    "Content-Type": "application/json"
                }
            })
            .then(response => {
                if (!response.ok) {
                    if (response.status === 401) {
                        // Redirect to login page if unauthorized
                        window.top.location.href = "login.html";
                        throw new Error('Unauthorized, redirecting to login');
                    }
                    throw new Error('Network response was not ok');
                }
                return response.json();
            })
            .then(data => {
                // Extract available years from all data
                const years = extractAvailableYears(data);
                if (years.length > 0 && availableYears.value.length === 0) {
                    availableYears.value = years;
                    // Set default year to the latest year with data
                    if (!selectedYear.value || !years.includes(selectedYear.value)) {
                        selectedYear.value = years[0];
                    }
                }
                
                // Apply filters if any
                let filteredData = data;
                
                // Apply period filter first
                filteredData = filterByPeriod(filteredData);
                
                if (searchContent.value) {
                    filteredData = filteredData.filter(memo => 
                        memo.content && memo.content.toLowerCase().includes(searchContent.value.toLowerCase())
                    );
                }
                
                if (searchStartDate.value) {
                    const startDate = new Date(searchStartDate.value);
                    filteredData = filteredData.filter(memo => 
                        memo.created_at && new Date(memo.created_at) >= startDate
                    );
                }
                
                if (searchEndDate.value) {
                    const endDate = new Date(searchEndDate.value);
                    endDate.setHours(23, 59, 59); // End of the day
                    filteredData = filteredData.filter(memo => 
                        memo.created_at && new Date(memo.created_at) <= endDate
                    );
                }
                
                // Apply sorting to the entire filtered dataset BEFORE pagination
                filteredData = sortMemoData([...filteredData], sortType.value);
                
                // Since the backend returns an array directly, we need to handle pagination on the client side
                totalPages.value = Math.ceil(filteredData.length / pageSize);
                
                const start = (page - 1) * pageSize;
                const end = start + pageSize;
                const paginatedData = filteredData.slice(start, end);

                // Add serial numbers if not present
                paginatedData.forEach((memo, index) => {
                    if (!memo.id) {
                        memo.id = start + index + 1;
                    }
                });

                // Get user information for each memo
                const promises = paginatedData.map(async memo => {
                    // Add status_text property - use backend's status_text if available, otherwise format it
                    if (!memo.status_text) {
                        memo.status_text = formatStatus(memo.status);
                    }
                    
                    // Fetch detailed path if file_id exists
                    if (memo.file_id) {
                        try {
                            const pathResponse = await fetch(`${url}contents/file/get_detailed_path?file_id=${memo.file_id}`, {
                                method: "GET",
                                credentials: "include",
                                headers: {
                                    "Accept": "application/json"
                                }
                            });
                            
                            if (pathResponse.ok) {
                                const pathData = await pathResponse.json();
                                memo.path = pathData.detailed_path || memo.path;
                            } else {
                                // Fallback to old path method if detailed path fails
                                if (!memo.path) {
                                    let pathParams = [];
                                    if (memo.file_id) pathParams.push(`file_id=${memo.file_id}`);
                                    if (memo.folder_id) pathParams.push(`folder_id=${memo.folder_id}`);
                                    
                                    if (pathParams.length > 0) {
                                        const oldPathResponse = await fetch(`${url}contents/file/get_path?${pathParams.join('&')}`, {
                                            method: "GET",
                                            credentials: "include",
                                            headers: {
                                                "Accept": "application/json"
                                            }
                                        });
                                        
                                        if (oldPathResponse.ok) {
                                            const oldPathData = await oldPathResponse.json();
                                            memo.path = oldPathData.file_path;
                                        }
                                    }
                                }
                            }
                        } catch (error) {
                            console.error(`Error fetching file path for memo ID ${memo.id}:`, error);
                            
                            // Fallback to old path method
                            if (!memo.path && (memo.file_id || memo.folder_id)) {
                                try {
                                    let pathParams = [];
                                    if (memo.file_id) pathParams.push(`file_id=${memo.file_id}`);
                                    if (memo.folder_id) pathParams.push(`folder_id=${memo.folder_id}`);
                                    
                                    if (pathParams.length > 0) {
                                        const oldPathResponse = await fetch(`${url}contents/file/get_path?${pathParams.join('&')}`, {
                                            method: "GET",
                                            credentials: "include",
                                            headers: {
                                                "Accept": "application/json"
                                            }
                                        });
                                        
                                        if (oldPathResponse.ok) {
                                            const oldPathData = await oldPathResponse.json();
                                            memo.path = oldPathData.file_path;
                                        }
                                    }
                                } catch (innerError) {
                                    console.error(`Error fetching fallback path for memo ID ${memo.id}:`, innerError);
                                }
                            }
                        }
                    } else if (!memo.path && memo.folder_id) {
                        // If we only have folder_id, use the old method
                        try {
                            const pathResponse = await fetch(`${url}contents/file/get_path?folder_id=${memo.folder_id}`, {
                                method: "GET",
                                credentials: "include",
                                headers: {
                                    "Accept": "application/json"
                                }
                            });
                            
                            if (pathResponse.ok) {
                                const pathData = await pathResponse.json();
                                memo.path = pathData.file_path;
                            }
                        } catch (error) {
                            console.error(`Error fetching file path for memo ID ${memo.id}:`, error);
                        }
                    }
                    
                    // Fetch user data if not already present
                    if (memo.user_id && !memo.user) {
                        try {
                            // Check userCache first
                            if (userCache[memo.user_id]) {
                                memo.user = userCache[memo.user_id];
                                return memo;
                            }
                            
                            // Check if it's the current user
                            const loggedInUser = JSON.parse(sessionStorage.getItem("loggedInUser"));
                            if (loggedInUser && loggedInUser.user && loggedInUser.user.id === memo.user_id) {
                                userCache[memo.user_id] = {
                                    company: loggedInUser.user.company || '-',
                                    department: loggedInUser.user.department || '-',
                                    name: loggedInUser.user.name || '-',
                                    position: loggedInUser.user.position || ''
                                };
                                memo.user = userCache[memo.user_id];
                                return memo;
                            }
                            
                            // Fetch from API if not in cache or current user
                            try {
                                const userResponse = await fetch(`${url}user/user_info?id=${memo.user_id}`, {
                                    method: "GET",
                                    credentials: "include",
                                    headers: {
                                        "Accept": "application/json"
                                    }
                                });
                                
                                if (userResponse.ok) {
                                    const userData = await userResponse.json();
                                    userCache[memo.user_id] = {
                                        company: userData.company || '-',
                                        department: userData.department || '-',
                                        name: userData.name || '-',
                                        position: userData.position || ''
                                    };
                                    memo.user = userCache[memo.user_id];
                                } else {
                                    console.warn(`Failed to fetch user ${memo.user_id}: ${userResponse.status} ${userResponse.statusText}`);
                                    // If API call fails, use placeholder
                                    userCache[memo.user_id] = {
                                        company: '-',
                                        department: '-',
                                        name: `사용자 ${memo.user_id}`,
                                        position: ''
                                    };
                                    memo.user = userCache[memo.user_id];
                                }
                            } catch (fetchError) {
                                console.warn(`Error fetching user ${memo.user_id}:`, fetchError.message);
                                // Use placeholder data if fetch completely fails
                                userCache[memo.user_id] = {
                                    company: '-',
                                    department: '-',
                                    name: `사용자 ${memo.user_id}`,
                                    position: ''
                                };
                                memo.user = userCache[memo.user_id];
                            }
                        } catch (error) {
                            console.error(`Error fetching user data for memo ID ${memo.id}:`, error);
                            // Cache the failed user to avoid repeated API calls
                            if (memo.user_id) {
                                userCache[memo.user_id] = {
                                    company: '-',
                                    department: '-',
                                    name: `사용자 ${memo.user_id}`,
                                    position: ''
                                };
                                memo.user = userCache[memo.user_id];
                            } else {
                                memo.user = {
                                    company: '-',
                                    department: '-',
                                    name: '-',
                                    position: ''
                                };
                            }
                        }
                    }
                    
                    return memo;
                });
                
                // Process all user data requests
                Promise.all(promises).then(updatedMemos => {
                    // Debug: log memo data to check created_at field
                    console.log('Updated memos with created_at check:', updatedMemos.map(m => ({
                        id: m.id,
                        title: m.title,
                        created_at: m.created_at,
                        modified_at: m.modified_at
                    })));
                    
                    // Memos are already sorted before pagination, just assign them
                    memoList.value = updatedMemos;
                });
            })
            .catch(error => {
                console.error("Error loading memo data:", error);
                alert("데이터 로드 실패: " + error.message);
            });
        };

        const replyToMemo = (memo) => {
            // Open a new popup window
            const width = 800;
            const height = 600;
            const left = (window.screen.width - width) / 2;
            const top = (window.screen.height - height) / 2;
            
            // Store the selected memo in localStorage for access from the popup
            localStorage.setItem('replyMemo', JSON.stringify(memo));
            
            // Open popup window
            const popupWindow = window.open(
                'memo_reply.html',
                'replyPopup',
                `width=${width},height=${height},left=${left},top=${top},resizable=yes,scrollbars=yes`
            );
            
            if (popupWindow) {
                popupWindow.focus();
            } else {
                alert('팝업 창이 차단되었습니다. 팝업 차단을 해제해주세요.');
            }
        };

        const showStatusUpdateNotification = (memoId, statusText) => {
            // Create a temporary notification element
            const notification = document.createElement('div');
            notification.innerHTML = `메모 #${memoId} 상태가 "${statusText}"로 변경되었습니다.`;
            notification.style.cssText = `
                position: fixed;
                top: 20px;
                right: 20px;
                background: #4CAF50;
                color: white;
                padding: 10px 20px;
                border-radius: 4px;
                box-shadow: 0 2px 10px rgba(0,0,0,0.2);
                z-index: 10000;
                font-size: 14px;
            `;
            
            document.body.appendChild(notification);
            
            // Remove after 3 seconds
            setTimeout(() => {
                if (notification.parentNode) {
                    notification.parentNode.removeChild(notification);
                }
            }, 3000);
        };

        // Test function for debugging status updates
        const testStatusUpdate = (memoId, newStatus, statusText) => {
            console.log(`Testing status update for memo ${memoId}`);
            
            // Simulate receiving a status update message
            window.dispatchEvent(new MessageEvent('message', {
                data: {
                    type: 'memoStatusUpdate',
                    memoId: memoId,
                    newStatus: newStatus,
                    statusText: statusText
                }
            }));
        };

        onMounted(() => {
            loadCurrentUser();
            loadMemoData();
            
            // Add listener for real-time status updates from popup windows
            window.addEventListener('message', (event) => {
                console.log('Received message:', event.data); // Debug all messages
                
                if (event.data && event.data.type === 'memoStatusUpdate') {
                    console.log('Processing memo status update:', event.data);
                    
                    // Find and update the memo in the current list
                    const memoIndex = memoList.value.findIndex(memo => memo.id === event.data.memoId);
                    if (memoIndex !== -1) {
                        const oldStatus = memoList.value[memoIndex].status;
                        const oldStatusText = memoList.value[memoIndex].status_text;
                        
                        // Update the memo status and status_text
                        memoList.value[memoIndex].status = event.data.newStatus;
                        memoList.value[memoIndex].status_text = event.data.statusText;
                        
                        console.log(`Updated memo ${event.data.memoId} status from ${oldStatus}(${oldStatusText}) to ${event.data.newStatus}(${event.data.statusText})`);
                        
                        // Add visual feedback - briefly highlight the updated row
                        const updatedRow = document.querySelector(`tr[data-memo-id="${event.data.memoId}"]`);
                        if (updatedRow) {
                            updatedRow.style.backgroundColor = '#e8f5e8';
                            setTimeout(() => {
                                updatedRow.style.backgroundColor = '';
                            }, 2000);
                        }
                        
                        // Show a brief notification
                        showStatusUpdateNotification(event.data.memoId, event.data.statusText);
                    } else {
                        console.warn(`Memo ${event.data.memoId} not found in current list`);
                    }
                }
            });
            
            // Make test function available globally for console debugging
            window.testStatusUpdate = testStatusUpdate;
            console.log('Debug function testStatusUpdate is now available in console');
        });

        return {
            memoList,
            currentPage,
            totalPages,
            visiblePages,
            isAdmin,
            searchContent,
            searchStartDate,
            searchEndDate,
            currentUser,
            sortType,
            selectedYear,
            isAnnualMode,
            selectedHalfYear,
            selectedQuarter,
            availableYears,
            loadMemoData,
            replyToMemo,
            formatStatus,
            formatDate,
            formatMemoPath,
            testStatusUpdate,
            sortByDate,
            sortByStatus,
            sortById,
            onYearChange,
            onAnnualChange,
            onHalfYearChange,
            onQuarterChange
        };
    }
}).mount("#app");