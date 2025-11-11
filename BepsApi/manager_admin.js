// Global variables
var contentHierarchy = null;

// Helper function to get base API URL
function getBaseApiUrl() {
    const url = typeof baseUrl !== "undefined" ? baseUrl : "http://172.16.8.208:20000";
    return url.endsWith('/') ? url.slice(0, -1) : url;
}

// Shared function to load name options for any select element
function loadNamesForSelect(selectElement, company, department, position) {
    if (!selectElement || !company || !department || !position) {
        if (selectElement) {
            selectElement.innerHTML = '<option value="">이름</option>';
        }
        return Promise.resolve([]);
    }

    return fetch(`${getBaseApiUrl()}/user/names?company=${encodeURIComponent(company)}&department=${encodeURIComponent(department)}&position=${encodeURIComponent(position)}`, {
        method: 'GET',
        credentials: 'include',
        headers: {
            'Content-Type': 'application/json',
            'Accept': 'application/json'
        }
    })
    .then(response => {
        if (!response.ok) {
            throw new Error('Failed to fetch name options');
        }
        return response.json();
    })
    .then(data => {
        // Clear existing options except the first placeholder
        selectElement.innerHTML = '<option value="">이름</option>';
        
        // Add new options
        if (Array.isArray(data)) {
            data.forEach(user => {
                const option = document.createElement('option');
                option.value = user.id;
                option.textContent = user.name;
                selectElement.appendChild(option);
            });
        }
        return data;
    })
    .catch(error => {
        console.error('Error loading name options:', error);
        selectElement.innerHTML = '<option value="">이름</option>';
        throw error;
    });
}

// Helper function to get path for a file or folder for display in permissions table
function getPathInHierarchy(type, id) {
    if (!contentHierarchy) return '';
    
    if (type === 'channel') {
        // Find channel by ID
        const channel = contentHierarchy.channels.find(c => c.id == id);
        return channel ? channel.name : '';
    } else if (type === 'folder') {
        // Find folder by ID and build path
        let folderPath = '';
        let folder = null;
        
        // Search for the folder in each channel
        for (const channel of contentHierarchy.channels) {
            folder = findFolderById(channel.folders, id);
            if (folder) {
                // If found, create path: Channel > Folder(s)
                folderPath = `${channel.name}/${getFolderPathFromHierarchy(channel.folders, id)}`;
                break;
            }
        }
        
        return folderPath;
    } else if (type === 'file') {
        // Find file by ID and build path
        let filePath = '';
        let foundFile = false;
        
        // Search for the file in each channel's folder structure
        for (const channel of contentHierarchy.channels) {
            for (const folder of channel.folders || []) {
                const result = findFileInFolder(folder, id);
                if (result.found) {
                    // If found, create path: Channel > Folder(s) > File
                    filePath = `${channel.name}/${result.path}`;
                    foundFile = true;
                    break;
                }
            }
            if (foundFile) break;
        }
        
        return filePath;
    }
    
    return '';
}

// Helper function to find a file's path in a folder structure
function findFileInFolder(folder, fileId, currentPath = '') {
    const path = currentPath ? `${currentPath}/${folder.name}` : folder.name;
    
    // Check if the file is in this folder
    if (folder.pages) {
        for (const page of folder.pages) {
            if (page.id == fileId) {
                return { found: true, path: `${path}/${page.name}`, folderId: folder.id, fileName: page.name };
            }
        }
    }
    
    // Check subfolders
    if (folder.subfolders) {
        for (const subfolder of folder.subfolders) {
            const result = findFileInFolder(subfolder, fileId, path);
            if (result.found) {
                return result;
            }
        }
    }
    
    return { found: false, path: '', folderId: null, fileName: '' };
}

// Helper function to build a folder's path in the hierarchy
function getFolderPathFromHierarchy(folders, folderId, currentPath = '') {
    for (const folder of folders) {
        if (folder.id == folderId) {
            return currentPath ? `${currentPath}/${folder.name}` : folder.name;
        }
        
        if (folder.subfolders && folder.subfolders.length > 0) {
            const newPath = currentPath ? `${currentPath}/${folder.name}` : folder.name;
            const found = getFolderPathFromHierarchy(folder.subfolders, folderId, newPath);
            if (found) return found;
        }
    }
    
    return '';
}

// Helper function to recursively find a folder by ID
function findFolderById(folders, folderId) {
    if (!folders || !Array.isArray(folders)) {
        return null;
    }
    
    for (const folder of folders) {
        if (folder.id == folderId) {
            // Log folder structure for debugging
            console.log(`Found folder ${folderId}: ${folder.name}`, {
                hasSubfolders: folder.subfolders && folder.subfolders.length > 0,
                subfoldersCount: folder.subfolders ? folder.subfolders.length : 0,
                hasPages: folder.pages && folder.pages.length > 0,
                pagesCount: folder.pages ? folder.pages.length : 0
            });
            return folder;
        }
        
        if (folder.subfolders && folder.subfolders.length > 0) {
            const found = findFolderById(folder.subfolders, folderId);
            if (found) return found;
        }
    }
    
    return null;
}

document.addEventListener('DOMContentLoaded', function() {
    // DOM elements
    const folderCols = document.querySelectorAll('.folder-col');
    const fileCol = document.querySelector('.file-col');
    const channelSelect = document.getElementById('channel-select');
    const folder1Select = document.getElementById('folder1-select');
    const folder2Select = document.getElementById('folder2-select');
    const folder3Select = document.getElementById('folder3-select');
    const fileSelect = document.getElementById('file-select');
    const managerInput = document.getElementById('manager-input');
    const addBtn = document.getElementById('add-btn');
    const errorMessage = document.getElementById('error-message');
    const permissionsListBody = document.getElementById('permissions-list-body');
    
    // New UI elements
    const companySelect = document.getElementById('company-select');
    const departmentSelect = document.getElementById('department-select');
    const positionSelect = document.getElementById('position-select');
    const nameSelect = document.getElementById('name-select');
    const validationMessage = document.getElementById('validation-message');

    // Base API URL from config
    const url = typeof baseUrl !== "undefined" ? baseUrl : "http://172.16.8.208:20000";
    
    // Ensure url doesn't end with a slash
    const baseApiUrl = url.endsWith('/') ? url.slice(0, -1) : url;
    
    console.log('Using API base URL:', baseApiUrl);
    
    // Fetch the complete content hierarchy once
    function fetchContentHierarchy() {
        console.log('Fetching content hierarchy...');
        
        // First try main API endpoint
        fetch(`${baseApiUrl}/contents/hierarchy`, {
            method: 'GET',
            credentials: 'include',
            headers: {
                'Content-Type': 'application/json',
                'Accept': 'application/json'
            }
        })
        .then(response => {
            if (!response.ok) {
                console.warn(`Main API endpoint failed: ${response.status}. Trying fallback...`);
                throw new Error('Main API endpoint failed');
            }
            console.log('Main API endpoint succeeded');
            return response.json();
        })
        .then(data => {
            processHierarchyData(data);
        })
        .catch(error => {
            console.warn('Trying fallback endpoint...', error);
            
            // Try fallback endpoint
            fetch(`${baseApiUrl}/hierarchy`, {
                method: 'GET',
                credentials: 'include',
                headers: {
                    'Content-Type': 'application/json',
                    'Accept': 'application/json'
                }
            })
            .then(response => {
                if (!response.ok) {
                    console.error(`Fallback endpoint failed: ${response.status}`);
                    throw new Error('Fallback endpoint failed');
                }
                console.log('Fallback API endpoint succeeded');
                return response.json();
            })
            .then(data => {
                processHierarchyData(data);
            })
            .catch(fallbackError => {
                console.error('All API endpoints failed:', fallbackError);
                errorMessage.textContent = '콘텐츠 구조를 불러오는데 실패했습니다. 샘플 데이터를 사용합니다.';
                
                // Initialize with sample data when all API calls fail
                initializeWithSampleData();
            });
        });
    }
    
    // Process hierarchy data once it's fetched
    function processHierarchyData(data) {
        console.log('Content hierarchy loaded successfully');
        
        // Log raw data structure to debug
        console.log('Raw hierarchy data sample:', JSON.stringify(data).substring(0, 300) + '...');
        
        // Validate hierarchy structure
        if (!data.channels || !Array.isArray(data.channels)) {
            console.error('Invalid hierarchy structure - channels missing or not an array', data);
            // Initialize with sample data if the structure is invalid
            initializeWithSampleData();
            return;
        }
        
        console.log(`Loaded ${data.channels.length} channels`);
        
        // Debug log the structure
        let folderCount = 0;
        let pageCount = 0;
        
        data.channels.forEach(channel => {
            if (channel.folders && Array.isArray(channel.folders)) {
                folderCount += channel.folders.length;
                channel.folders.forEach(folder => {
                    countFolderContents(folder, stats => {
                        folderCount += stats.folders;
                        pageCount += stats.pages;
                    });
                });
            }
        });
        
        console.log(`Hierarchy contains ${folderCount} folders and ${pageCount} pages`);
        
        // Normalize the hierarchy data structure
        data = normalizeHierarchyData(data);
        
        // Store the hierarchy data both locally and globally
        contentHierarchy = data;
        
        // Load channel options from the hierarchy
        loadChannelOptions();
        
        // Now that hierarchy is loaded, we can safely load permissions
        loadPermissions();
    }

    // Helper function to count folders and pages in a folder structure
    function countFolderContents(folder, callback) {
        let stats = { folders: 0, pages: 0 };
        
        if (folder.subfolders && Array.isArray(folder.subfolders)) {
            stats.folders += folder.subfolders.length;
            folder.subfolders.forEach(subfolder => {
                countFolderContents(subfolder, subStats => {
                    stats.folders += subStats.folders;
                    stats.pages += subStats.pages;
                });
            });
        }
        
        if (folder.pages && Array.isArray(folder.pages)) {
            stats.pages += folder.pages.length;
        }
        
        callback(stats);
    }

    // Initialize with sample data for testing when API fails
    function initializeWithSampleData() {
        console.log('Initializing with sample data');
        const sampleData = {
            channels: [
                {
                    id: 1,
                    name: "샘플 채널",
                    type: "channel",
                    folders: [
                        {
                            id: 2,
                            name: "샘플 폴더1",
                            type: "folder",
                            subfolders: [],
                            pages: [
                                {
                                    id: 3,
                                    name: "샘플 파일1",
                                    type: "page"
                                },
                                {
                                    id: 4,
                                    name: "샘플 파일2",
                                    type: "page"
                                }
                            ]
                        },
                        {
                            id: 5,
                            name: "샘플 폴더2",
                            type: "folder",
                            subfolders: [
                                {
                                    id: 6,
                                    name: "샘플 하위폴더",
                                    type: "folder",
                                    subfolders: [],
                                    pages: [
                                        {
                                            id: 7,
                                            name: "샘플 하위 파일",
                                            type: "page"
                                        }
                                    ]
                                }
                            ],
                            pages: []
                        }
                    ]
                },
                {
                    id: 8,
                    name: "샘플 채널2",
                    type: "channel",
                    folders: []
                }
            ],
            timestamp: new Date().toISOString()
        };
        
        // Store the sample data in both local and global variables
        contentHierarchy = sampleData;
        
        // Load channel options from the sample data
        loadChannelOptions();
        
        // Now that hierarchy is loaded, we can safely load permissions
        loadPermissions();
    }

    // Load channel options from the content hierarchy
    function loadChannelOptions() {
        // Clear existing options except the first placeholder
        channelSelect.innerHTML = '<option value="">선택</option>';
        
        // Add channel options from the hierarchy
        if (contentHierarchy && contentHierarchy.channels && Array.isArray(contentHierarchy.channels)) {
            // Sort channels by name
            const sortedChannels = [...contentHierarchy.channels].sort((a, b) => {
                return a.name.localeCompare(b.name, 'ko');
            });
            
            sortedChannels.forEach(channel => {
                const option = document.createElement('option');
                option.value = channel.id;
                option.textContent = channel.name;
                channelSelect.appendChild(option);
            });
            
            console.log(`Loaded ${sortedChannels.length} channels into dropdown`);
        } else {
            console.warn('No channels available to load');
        }
    }

    // Load folder options based on selected channel
    function loadFolderOptions(parentType, parentId, selectElement, level) {
        // Clear the current select and all dependent selects
        selectElement.innerHTML = '<option value="">선택</option>';
        
        if (level === 1) {
            // Top level folders - from channel
            folder2Select.innerHTML = '<option value="">선택</option>';
            folder3Select.innerHTML = '<option value="">선택</option>';
            fileSelect.innerHTML = '<option value="">선택</option>';
            
            if (!contentHierarchy) return;
            
            // Find the selected channel
            const selectedChannel = contentHierarchy.channels.find(channel => channel.id == parentId);
            if (!selectedChannel || !selectedChannel.folders) return;
            
            // Sort folders by name
            const sortedFolders = [...selectedChannel.folders].sort((a, b) => {
                return a.name.localeCompare(b.name, 'ko');
            });
            
            // Add folder options from selected channel
            sortedFolders.forEach(folder => {
                const option = document.createElement('option');
                option.value = folder.id;
                option.textContent = folder.name;
                selectElement.appendChild(option);
            });
        } 
        else if (level === 2 || level === 3) {
            // Find the parent folder and its subfolders
            let parentFolder = null;
            
            if (!contentHierarchy) return;
            
            // Loop through channels to find the target folder
            for (const channel of contentHierarchy.channels) {
                parentFolder = findFolderById(channel.folders, parentId);
                if (parentFolder) break;
            }
            
            if (!parentFolder || !parentFolder.subfolders) return;
            
            // Clear dependent selects
            if (level === 2) {
                folder3Select.innerHTML = '<option value="">선택</option>';
                fileSelect.innerHTML = '<option value="">선택</option>';
            } else if (level === 3) {
                fileSelect.innerHTML = '<option value="">선택</option>';
            }
            
            // Sort subfolders by name
            const sortedSubfolders = [...parentFolder.subfolders].sort((a, b) => {
                return a.name.localeCompare(b.name, 'ko');
            });
            
            // Add subfolder options
            sortedSubfolders.forEach(subfolder => {
                const option = document.createElement('option');
                option.value = subfolder.id;
                option.textContent = subfolder.name;
                selectElement.appendChild(option);
            });
        }
    }

    // Load file options based on selected folder
    function loadFileOptions(folderId) {
        // Clear existing options
        fileSelect.innerHTML = '<option value="">선택</option>';
        
        console.log(`Loading files for folder ID: ${folderId}`);
        
        // First try the main API endpoint
        fetch(`${baseApiUrl}/contents/folder/children?folder_id=${folderId}`, {
            method: 'GET',
            credentials: 'include',
            headers: {
                'Content-Type': 'application/json',
                'Accept': 'application/json'
            }
        })
        .then(response => {
            if (!response.ok) {
                console.warn(`Main folder children API failed: ${response.status}. Trying fallback...`);
                // Try fallback endpoint
                return fetch(`${baseApiUrl}/folder/children?folder_id=${folderId}`, {
                    method: 'GET',
                    credentials: 'include',
                    headers: {
                        'Content-Type': 'application/json',
                        'Accept': 'application/json'
                    }
                });
            }
            return response;
        })
        .then(response => {
            if (!response.ok) {
                console.error(`All folder children APIs failed: ${response.status}`);
                
                // If we have hierarchy data, try to use it
                if (contentHierarchy) {
                    console.log('Using hierarchy data as fallback');
                    const folder = findSelectedFolder(folderId);
                    if (folder && folder.pages && folder.pages.length > 0) {
                        // Sort pages by name
                        const sortedPages = [...folder.pages].sort((a, b) => {
                            return a.name.localeCompare(b.name, 'ko');
                        });
                        
                        // Add to select
                        sortedPages.forEach(page => {
                            const option = document.createElement('option');
                            option.value = page.id;
                            option.textContent = page.name;
                            fileSelect.appendChild(option);
                        });
                        
                        console.log(`Added ${sortedPages.length} pages from hierarchy data`);
                        return null; // Skip further processing
                    }
                }
                
                throw new Error(`Failed to fetch folder children: ${response.status}`);
            }
            return response.json();
        })
        .then(data => {
            if (!data) return; // Skip if we already populated from hierarchy
            
            console.log('Folder children API response:', data);
            
            // Check if this is a leaf folder with pages
            if (data.is_leaf_folder && data.page_ids && data.page_ids.length > 0) {
                // Get all the page IDs
                const pageIds = data.page_ids;
                console.log(`Found ${pageIds.length} page IDs:`, pageIds);
                
                // For simplicity, first display IDs 
                const sortedPageIds = [...pageIds].sort();
                sortedPageIds.forEach(pageId => {
                    const option = document.createElement('option');
                    option.value = pageId;
                    option.textContent = `Page ${pageId}`;
                    fileSelect.appendChild(option);
                });
                
                console.log(`Added ${sortedPageIds.length} pages to file select`);
                
                // Then try to get names by fetching details for each page
                pageIds.forEach(pageId => {
                    fetch(`${baseApiUrl}/contents/file/get_detailed_path?file_id=${pageId}`, {
                        method: 'GET',
                        credentials: 'include',
                        headers: {
                            'Content-Type': 'application/json',
                            'Accept': 'application/json'
                        }
                    })
                    .then(response => {
                        if (!response.ok) {
                            // Try fallback
                            return fetch(`${baseApiUrl}/file/get_detailed_path?file_id=${pageId}`, {
                                method: 'GET',
                                credentials: 'include',
                                headers: {
                                    'Content-Type': 'application/json',
                                    'Accept': 'application/json'
                                }
                            });
                        }
                        return response;
                    })
                    .then(response => {
                        if (!response.ok) {
                            console.warn(`Failed to get name for page ${pageId}`);
                            return null;
                        }
                        return response.json();
                    })
                    .then(detailData => {
                        if (detailData && detailData.detailed_path) {
                            console.log(`Got name for page ${pageId}:`, detailData);
                            // Find the option with this ID and update its text
                            const pathParts = detailData.detailed_path.split('/');
                            const fileName = pathParts[pathParts.length - 1];
                            
                            // Find and update the option element
                            const option = Array.from(fileSelect.options).find(opt => opt.value == pageId);
                            if (option) {
                                option.textContent = fileName;
                            }
                        }
                    })
                    .catch(err => {
                        console.error(`Error getting name for page ${pageId}:`, err);
                    });
                });
            } else {
                console.log(`Folder ${folderId} is not a leaf folder or has no pages`);
            }
        })
        .catch(error => {
            console.error('Error loading files for folder:', error);
            errorMessage.textContent = '파일 목록을 불러오는데 실패했습니다.';
        });
    }

    // Sort permissions by hierarchy (channel, folder1, folder2, folder3, file)
    function sortPermissionsByHierarchy(permissions) {
        return permissions.sort((a, b) => {
            // Get hierarchy info for both permissions
            const aInfo = getHierarchyInfo(a);
            const bInfo = getHierarchyInfo(b);
            
            // Compare each level of hierarchy
            for (let i = 0; i < 4; i++) {
                const aValue = aInfo.folderParts[i] || '';
                const bValue = bInfo.folderParts[i] || '';
                
                if (aValue !== bValue) {
                    return aValue.localeCompare(bValue, 'ko');
                }
            }
            
            // If all folder parts are equal, compare file names
            const aFile = aInfo.fileName || '';
            const bFile = bInfo.fileName || '';
            return aFile.localeCompare(bFile, 'ko');
        });
    }

    // Load existing permissions
    function loadPermissions() {
        console.log('Loading permissions from API:', `${baseApiUrl}/contents/content_manager`);
        
        // Exit early if hierarchy isn't loaded yet
        if (!contentHierarchy || !contentHierarchy.channels) {
            console.warn('Cannot load permissions - content hierarchy not available yet');
            errorMessage.textContent = '콘텐츠 구조 정보를 기다리는 중입니다...';
            return;
        }
        
        // Clear error message if it was previously set
        errorMessage.textContent = '';
        
        fetch(`${baseApiUrl}/contents/content_manager`, {
            method: 'GET',
            credentials: 'include',
            headers: {
                'Content-Type': 'application/json',
                'Accept': 'application/json'
            }
        })
        .then(response => {
            if (!response.ok) {
                console.error(`Failed to fetch permissions: ${response.status} ${response.statusText}`);
                throw new Error(`Failed to fetch permissions: ${response.status}`);
            }
            
            // Check if the response is JSON
            const contentType = response.headers.get('content-type');
            if (!contentType || !contentType.includes('application/json')) {
                console.error('Response is not JSON:', contentType);
                throw new Error('Response is not JSON');
            }
            
            return response.json();
        })
        .then(async data => {
            console.log('Permissions loaded:', data);
            
            // Clear existing rows
            permissionsListBody.innerHTML = '';
            
            // Add each permission to the table
            if (Array.isArray(data)) {
                // Sort permissions by hierarchy before displaying
                const sortedPermissions = sortPermissionsByHierarchy(data);

                for (const permission of sortedPermissions) {
                    await addPermissionToTable(permission);
                }

                if (data.length === 0) {
                    console.log('No permissions found');
                }
            } else {
                console.error('Permissions data is not an array:', data);
            }
        })
        .catch(error => {
            console.error('Error loading permissions:', error);
            errorMessage.textContent = '권한 정보를 불러오는데 실패했습니다: ' + error.message;
        });
    }

    // Verify user exists
    function verifyUser(userId) {
        return fetch(`${baseApiUrl}/user/user_info?id=${userId}`, {
            method: 'GET',
            credentials: 'include',
            headers: {
                'Content-Type': 'application/json',
                'Accept': 'application/json'
            }
        })
        .then(response => {
            if (!response.ok) {
                if (response.status === 404) {
                    throw new Error('사용자를 찾을 수 없습니다.');
                }
                throw new Error('사용자 확인에 실패했습니다.');
            }
            return response.json();
        });
    }

    // Fetch user details
    function fetchUserDetails(userId) {
        // Handle null, undefined, or empty user IDs
        if (!userId || userId === 'null' || userId === 'undefined') {
            return Promise.resolve({ exists: false });
        }
        
        return fetch(`${baseApiUrl}/user/user_info?id=${userId}`, {
            method: 'GET',
            credentials: 'include',
            headers: {
                'Content-Type': 'application/json',
                'Accept': 'application/json'
            }
        })
        .then(response => {
            if (!response.ok) {
                return { exists: false };
            }
            return response.json();
        })
        .then(userData => {
            // Transform the response to match expected format
            if (userData) {
                if (userData.hasOwnProperty("exists") && userData.exists === false)
                {
                    return { exists: false };
                }

                return {
                    exists: true,
                    user: userData
                };
            } else {
                return { exists: false };
            }
        })
        .catch(() => {
            return { exists: false };
        });
    }

    // Add permission
    function addPermission() {
        // Clear previous error message
        errorMessage.textContent = '';
        
        // Get selected values
        const channelId = channelSelect.value;
        const folder1Id = folder1Select.value;
        const folder2Id = folder2Select.value;
        const folder3Id = folder3Select.value;
        const fileId = fileSelect.value;
        const managerId = managerInput.value.trim();
        
        // Validate input
        if (!channelId) {
            errorMessage.textContent = '채널을 선택해주세요.';
            return;
        }
        
        if (!managerId) {
            errorMessage.textContent = '담당자 ID를 입력해주세요.';
            return;
        }
        
        // Determine permission scope based on selection pattern
        let permissionScope;
        if (fileId) {
            permissionScope = 'file';
        } else if (folder1Id || folder2Id || folder3Id) {
            permissionScope = 'folder';
        } else {
            permissionScope = 'channel';
        }
        
        // Verify user exists
        verifyUser(managerId)
            .then(userData => {
                // Prepare permission data
                let permissionData = {
                    user_id: managerId,
                    type: permissionScope
                };
                
                if (permissionScope === 'channel') {
                    permissionData.channel_id = channelId;
                } else if (permissionScope === 'folder') {
                    // Use the deepest selected folder
                    permissionData.folder_id = folder3Id || folder2Id || folder1Id;
                } else if (permissionScope === 'file') {
                    permissionData.file_id = fileId;
                }
                
                // Send permission data to API
                return fetch(`${baseApiUrl}/contents/content_manager`, {
                    method: 'POST',
                    credentials: 'include',
                    headers: {
                        'Content-Type': 'application/json',
                        'Accept': 'application/json'
                    },
                    body: JSON.stringify(permissionData)
                });
            })
            .then(response => {
                if (!response.ok) {
                    // Special handling for duplicate entry error
                    if (response.status === 409) {
                        return response.json().then(data => {
                            throw new Error(data.error || '이미 동일한 담당자 권한이 존재합니다.');
                        });
                    }
                    throw new Error('권한 추가에 실패했습니다.');
                }
                return response.json();
            })
            .then(data => {
                // Reload permissions list to maintain sorted order
                loadPermissions();
                
                // Clear form
                managerInput.value = '';
                validationMessage.textContent = '담당자 ID를 입력하거나 소속 정보를 통해 선택하세요';
                validationMessage.className = 'validation-message';
                
                // Clear user selection comboboxes
                resetUserSelectionComboboxes();
                
                // Success message
                alert('담당자 권한이 추가되었습니다.');
            })
            .catch(error => {
                errorMessage.textContent = error.message;
            });
    }

    // Add permission to table
    async function addPermissionToTable(permission) {
        const row = document.createElement('tr');
        
        // Get hierarchy information for this permission
        const { folderParts, fileName } = getHierarchyInfo(permission);
        
        // Get detailed user information - handle null assignee
        let userData = { exists: false };
        if (permission.assignee && permission.assignee.user_id) {
            userData = await fetchUserDetails(permission.assignee.user_id);
        }
        
        try{    
            // Get user details
            let company = '';
            let department = '';
            let position = '';
            let name = '';
            let userId = '';
            
            if (userData && userData.exists && userData.user) {
                company = userData.user.company || '';
                department = userData.user.department || '';
                position = userData.user.position || '';
                name = userData.user.name || '';
                userId = userData.user.id || '';
            }
            else if (permission.assignee)
            {
                position = permission.assignee.position || '';
                name = permission.assignee.name || '';
                userId = permission.assignee.user_id || '';
            }

            // Translate permission type to Korean
            let permissionTypeKorean = '';
            switch(permission.type) {
                case 'channel':
                    permissionTypeKorean = '채널';
                    break;
                case 'folder':
                    permissionTypeKorean = '폴더';
                    break;
                case 'file':
                    permissionTypeKorean = '파일';
                    break;
                default:
                    permissionTypeKorean = permission.type;
            }
            
            // Add cells
            row.innerHTML = `
                <td class="permission-type-col">${permissionTypeKorean}</td>
                <td>${folderParts[0] || ''}</td>
                <td class="folder1-col">${folderParts[1] || ''}</td>
                <td class="folder2-col">${folderParts[2] || ''}</td>
                <td class="folder3-col">${folderParts[3] || ''}</td>
                <td class="file-col">${fileName || ''}</td>
                <td class="company-col">${company || '-'}</td>
                <td class="department-col">${department || '-'}</td>
                <td class="position-col">${position || '-'}</td>
                <td class="name-col">${name || '-'}</td>
                <td class="id-col">${userId || '-'}</td>
                <td class="action-col">
                    <button class="edit-btn" data-id="${permission.id}" data-type="${permission.type}" data-content-id="${permission.type === 'channel' ? permission.channel_id : permission.type === 'folder' ? permission.folder_id : permission.file_id}" data-current-user="${userId || ''}" data-current-name="${name || ''}" data-current-company="${company || ''}" data-current-department="${department || ''}" data-current-position="${position || ''}">수정</button>
                    <button class="delete-btn" data-id="${permission.id}">삭제</button>
                </td>
            `;
            
            // Add row to table
            permissionsListBody.appendChild(row);
            
            // Add event listener to edit button
            row.querySelector('.edit-btn').addEventListener('click', function() {
                openUpdateManagerModal(this.dataset);
            });
            
            // Add event listener to delete button
            row.querySelector('.delete-btn').addEventListener('click', function() {
                deletePermission(this.dataset.id, row);
            });
        }
        catch(error) {
            console.error('Error adding permission to table:', error);
        }
    }

    // Fetch user name
    function fetchUserName(userId) {
        return fetch(`${baseApiUrl}/user/user_info?id=${userId}`, {
            method: 'GET',
            credentials: 'include',
            headers: {
                'Content-Type': 'application/json',
                'Accept': 'application/json'
            }
        })
        .then(response => {
            if (!response.ok) {
                return '';
            }
            return response.json();
        })
        .then(data => {
            return data.name || '';
        })
        .catch(() => {
            return '';
        });
    }

    // Delete permission
    function deletePermission(permissionId, row) {
        if (confirm('이 권한을 삭제하시겠습니까?')) {
            fetch(`${baseApiUrl}/contents/content_manager/${permissionId}`, {
                method: 'DELETE',
                credentials: 'include',
                headers: {
                    'Content-Type': 'application/json',
                    'Accept': 'application/json'
                }
            })
            .then(response => {
                if (!response.ok) {
                    throw new Error('권한 삭제에 실패했습니다.');
                }
                
                // Remove row from table
                row.remove();
                
                // Success message
                alert('권한이 삭제되었습니다.');
            })
            .catch(error => {
                console.error('Error deleting permission:', error);
                errorMessage.textContent = error.message;
            });
        }
    }

    // Load company options for user selection
    function loadCompanyOptions() {
        fetch(`${baseApiUrl}/user/companies`, {
            method: 'GET',
            credentials: 'include',
            headers: {
                'Content-Type': 'application/json',
                'Accept': 'application/json'
            }
        })
        .then(response => {
            if (!response.ok) {
                throw new Error('Failed to fetch company options');
            }
            return response.json();
        })
        .then(data => {
            // Clear existing options except the first placeholder
            companySelect.innerHTML = '<option value="">회사명</option>';
            
            // Add new options
            data.forEach(company => {
                const option = document.createElement('option');
                option.value = company;
                option.textContent = company;
                companySelect.appendChild(option);
            });
        })
        .catch(error => {
            console.error('Error loading company options:', error);
        });
    }

    // Load department options based on selected company
    function loadDepartmentOptions(company) {
        fetch(`${baseApiUrl}/user/departments?company=${encodeURIComponent(company)}`, {
            method: 'GET',
            credentials: 'include',
            headers: {
                'Content-Type': 'application/json',
                'Accept': 'application/json'
            }
        })
        .then(response => {
            if (!response.ok) {
                throw new Error('Failed to fetch department options');
            }
            return response.json();
        })
        .then(data => {
            // Clear existing options except the first placeholder
            departmentSelect.innerHTML = '<option value="">부서</option>';
            positionSelect.innerHTML = '<option value="">직책</option>';
            nameSelect.innerHTML = '<option value="">이름</option>';
            
            // Add new options
            data.forEach(department => {
                const option = document.createElement('option');
                option.value = department;
                option.textContent = department;
                departmentSelect.appendChild(option);
            });
        })
        .catch(error => {
            console.error('Error loading department options:', error);
        });
    }

    // Load position options based on selected company and department
    function loadPositionOptions(company, department) {
        fetch(`${baseApiUrl}/user/positions?company=${encodeURIComponent(company)}&department=${encodeURIComponent(department)}`, {
            method: 'GET',
            credentials: 'include',
            headers: {
                'Content-Type': 'application/json',
                'Accept': 'application/json'
            }
        })
        .then(response => {
            if (!response.ok) {
                throw new Error('Failed to fetch position options');
            }
            return response.json();
        })
        .then(data => {
            // Clear existing options except the first placeholder
            positionSelect.innerHTML = '<option value="">직책</option>';
            nameSelect.innerHTML = '<option value="">이름</option>';
            
            // Add new options
            data.forEach(position => {
                const option = document.createElement('option');
                option.value = position;
                option.textContent = position;
                positionSelect.appendChild(option);
            });
        })
        .catch(error => {
            console.error('Error loading position options:', error);
        });
    }

    // Load name options based on selected company, department, and position
    function loadNameOptions(company, department, position) {
        loadNamesForSelect(nameSelect, company, department, position);
    }

    // Reset user selection comboboxes
    function resetUserSelectionComboboxes() {
        companySelect.innerHTML = '<option value="">회사명</option>';
        departmentSelect.innerHTML = '<option value="">부서</option>';
        positionSelect.innerHTML = '<option value="">직책</option>';
        nameSelect.innerHTML = '<option value="">이름</option>';
        
        // Reload company options
        loadCompanyOptions();
    }

    // Validate user ID input
    function validateUserID(userId) {
        if (!userId) {
            validationMessage.textContent = '담당자 ID를 입력하거나 소속 정보를 통해 선택하세요';
            validationMessage.className = 'validation-message';
            return;
        }
        
        fetch(`${baseApiUrl}/user/verify?id=${encodeURIComponent(userId)}`, {
            method: 'GET',
            credentials: 'include',
            headers: {
                'Content-Type': 'application/json',
                'Accept': 'application/json'
            }
        })
        .then(response => {
            if (!response.ok) {
                validationMessage.textContent = 'ID 검증에 실패했습니다';
                validationMessage.className = 'validation-message error';
                throw new Error(`HTTP ${response.status}`);
            }
            return response.json();
        })
        .then(data => {
            if (data && data.exists) {
                const user = data.user;
                // Update the input field to use the database's casing
                if (managerInput.value.toLowerCase() === user.id.toLowerCase() && 
                    managerInput.value !== user.id) {
                    managerInput.value = user.id;
                }
                validationMessage.textContent = `${user.company || '-'} ${user.department || '-'} ${user.name || '-'} ${user.position || '-'}\n올바른 ID입니다.`;
                validationMessage.className = 'validation-message success';
            } else {
                validationMessage.textContent = 'ID를 찾을 수 없습니다';
                validationMessage.className = 'validation-message error';
            }
        })
        .catch(error => {
            console.error('Error validating user ID:', error);
            validationMessage.textContent = 'ID 검증에 실패했습니다';
            validationMessage.className = 'validation-message error';
        });
    }

    // Event listener for channel select
    channelSelect.addEventListener('change', function() {
        if (this.value) {
            // Load folders with depth 2 under the selected channel
            loadFolderOptions('channel', this.value, folder1Select, 1);
        }
    });

    // Event listener for folder1 select
    folder1Select.addEventListener('change', function() {
        if (this.value) {
            console.log(`Folder1 selected: ${this.value}`);
            
            // Load folders with depth 3 under the selected folder
            loadFolderOptions('folder', this.value, folder2Select, 2);
            
            // Try to load files immediately - if this is a leaf folder, it will get files
            try {
                loadFileOptions(this.value);
            } catch (error) {
                console.error("Error loading files for folder1:", error);
            }
        } else {
            // Clear dependent selects
            folder2Select.innerHTML = '<option value="">선택</option>';
            folder3Select.innerHTML = '<option value="">선택</option>';
            fileSelect.innerHTML = '<option value="">선택</option>';
        }
    });

    // Event listener for folder2 select
    folder2Select.addEventListener('change', function() {
        if (this.value) {
            console.log(`Folder2 selected: ${this.value}`);
            
            // Load folders with depth 4 under the selected folder
            loadFolderOptions('folder', this.value, folder3Select, 3);
            
            // Try to load files immediately - if this is a leaf folder, it will get files
            try {
                loadFileOptions(this.value);
            } catch (error) {
                console.error("Error loading files for folder2:", error);
            }
        } else {
            // Clear dependent selects
            folder3Select.innerHTML = '<option value="">선택</option>';
            fileSelect.innerHTML = '<option value="">선택</option>';
        }
    });

    // Event listener for folder3 select
    folder3Select.addEventListener('change', function() {
        if (this.value) {
            console.log(`Folder3 selected: ${this.value}`);
            
            // Load files under the selected folder
            try {
                loadFileOptions(this.value);
            } catch (error) {
                console.error("Error loading files for folder3:", error);
            }
        } else {
            // Clear file select
            fileSelect.innerHTML = '<option value="">선택</option>';
        }
    });

    // Event listener for company select
    companySelect.addEventListener('change', function() {
        if (this.value) {
            loadDepartmentOptions(this.value);
        } else {
            departmentSelect.innerHTML = '<option value="">부서</option>';
            positionSelect.innerHTML = '<option value="">직책</option>';
            nameSelect.innerHTML = '<option value="">이름</option>';
        }
    });

    // Event listener for department select
    departmentSelect.addEventListener('change', function() {
        if (this.value && companySelect.value) {
            loadPositionOptions(companySelect.value, this.value);
        } else {
            positionSelect.innerHTML = '<option value="">직책</option>';
            nameSelect.innerHTML = '<option value="">이름</option>';
        }
    });

    // Event listener for position select
    positionSelect.addEventListener('change', function() {
        if (this.value && companySelect.value && departmentSelect.value) {
            loadNameOptions(companySelect.value, departmentSelect.value, this.value);
        } else {
            nameSelect.innerHTML = '<option value="">이름</option>';
        }
    });

    // Event listener for name select
    nameSelect.addEventListener('change', function() {
        if (this.value) {
            // Set the selected user's ID in the manager input field
            managerInput.value = this.value;
            validateUserID(this.value);
        }
    });

    // Event listener for manager input
    managerInput.addEventListener('input', function() {
        validateUserID(this.value.trim());
    });

    // Event listener for add button
    addBtn.addEventListener('click', function() {
        // Normal add mode only (edit functionality disabled)
        addPermission();
    });

    // Event listener for refresh button
    const refreshBtn = document.getElementById('refresh-btn');
    if (refreshBtn) {
        refreshBtn.addEventListener('click', function() {
            // Re-fetch content hierarchy and permissions
            fetchContentHierarchy();
        });
    }

    // Initialize view
    fetchContentHierarchy(); // This will load channel options and permissions after hierarchy is loaded
    loadCompanyOptions();
    
    // Update manager modal event listeners
    const updateManagerInput = document.getElementById('update-manager-input');
    const updateBtn = document.getElementById('update-btn');
    const updateModalCloseBtn = document.getElementById('update-modal-close-btn');
    const updateCancelBtn = document.getElementById('update-cancel-btn');
    
    if (updateManagerInput) {
        updateManagerInput.addEventListener('input', function() {
            validateUpdateUserID(this.value);
        });
    }
    
    if (updateBtn) {
        updateBtn.addEventListener('click', updateManager);
    }
    
    if (updateModalCloseBtn) {
        updateModalCloseBtn.addEventListener('click', closeUpdateManagerModal);
    }
    
    if (updateCancelBtn) {
        updateCancelBtn.addEventListener('click', closeUpdateManagerModal);
    }
    
    // Close update manager modal when clicking overlay
    const modalOverlay = document.getElementById('modal-overlay');
    if (modalOverlay) {
        modalOverlay.addEventListener('click', function(e) {
            if (e.target === modalOverlay) {
                // Check if update manager modal is open
                const updateModal = document.getElementById('update-manager-modal');
                if (updateModal && updateModal.style.display === 'block') {
                    closeUpdateManagerModal();
                }
            }
        });
    }
});

// Add event listener to open the manager admin popup from main page
if (window.opener) {
    // If this window was opened by another window (popup mode)
    document.title = '담당자 관리';
}

// Process and normalize the hierarchy data to ensure it has the expected format
function normalizeHierarchyData(data) {
    if (!data || !data.channels) {
        console.error('Invalid hierarchy data:', data);
        return data;
    }
    
    console.log('Normalizing hierarchy data structure');
    
    // Process each channel
    data.channels.forEach(channel => {
        console.log(`Processing channel ${channel.id}: ${channel.name}`);
        
        if (!channel.folders) {
            console.log(`Channel ${channel.id} has no folders array, creating empty array`);
            channel.folders = [];
        }
        
        // Process each folder
        channel.folders.forEach(folder => {
            normalizeFolder(folder);
        });
    });
    
    // Debug output
    let folderStats = [];
    data.channels.forEach(channel => {
        let channelStats = { 
            channelId: channel.id, 
            channelName: channel.name,
            folderCount: channel.folders ? channel.folders.length : 0,
            leafFolders: []
        };
        
        if (channel.folders && channel.folders.length > 0) {
            channel.folders.forEach(folder => {
                collectLeafFolders(folder, channelStats.leafFolders);
            });
        }
        
        folderStats.push(channelStats);
    });
    
    console.log('Hierarchy leaf folder stats:', folderStats);
    
    return data;
}

// Recursively normalize folder structure
function normalizeFolder(folder) {
    if (!folder) return;
    
    console.log(`Processing folder ${folder.id}: ${folder.name}`);
    
    // Ensure subfolders array exists
    if (!folder.subfolders) {
        console.log(`Folder ${folder.id} has no subfolders array, creating empty array`);
        folder.subfolders = [];
    }
    
    // Ensure pages array exists
    if (!folder.pages) {
        console.log(`Folder ${folder.id} has no pages array, creating empty array`);
        folder.pages = [];
    } else {
        console.log(`Folder ${folder.id} has ${folder.pages.length} pages`);
    }
    
    // Process each subfolder recursively
    folder.subfolders.forEach(subfolder => {
        normalizeFolder(subfolder);
    });
}

// Helper function to collect leaf folders for debugging
function collectLeafFolders(folder, leafFolders) {
    if (!folder.subfolders || folder.subfolders.length === 0) {
        leafFolders.push({
            id: folder.id,
            name: folder.name,
            pageCount: folder.pages ? folder.pages.length : 0
        });
    } else {
        folder.subfolders.forEach(subfolder => {
            collectLeafFolders(subfolder, leafFolders);
        });
    }
}

// Helper function to find a folder by ID in the entire hierarchy
function findSelectedFolder(folderId) {
    // First ensure contentHierarchy is defined
    if (typeof contentHierarchy === 'undefined' || !contentHierarchy || !contentHierarchy.channels) {
        console.error('Content hierarchy is not available', typeof contentHierarchy);
        return null;
    }
    
    for (const channel of contentHierarchy.channels) {
        if (!channel.folders) continue;
        
        const folder = findFolderById(channel.folders, folderId);
        if (folder) return folder;
    }
    
    return null;
}

// Edit permission
function editPermission(permission) {
    // Clear previous error message
    errorMessage.textContent = '';
    
    // Populate form with permission data
    if (permission.type === 'channel' && permission.channel_id) {
        // Set channel
        channelSelect.value = permission.channel_id;
        
        // Clear folder and file selections
        folder1Select.innerHTML = '<option value="">선택</option>';
        folder2Select.innerHTML = '<option value="">선택</option>';
        folder3Select.innerHTML = '<option value="">선택</option>';
        fileSelect.innerHTML = '<option value="">선택</option>';
    } else if (permission.type === 'folder' && permission.folder_id) {
        // We need to find the path to this folder
        let folderPath = findFolderPath(permission.folder_id);
        if (folderPath && folderPath.length > 0) {
            // Set channel
            channelSelect.value = folderPath[0].channelId;
            
            // Wait for channel change to take effect and load folder1
            setTimeout(() => {
                // Load folder1 options
                loadFolderOptions('channel', folderPath[0].channelId, folder1Select, 1);
                
                // Set folder1 if it exists in the path
                if (folderPath.length > 1) {
                    setTimeout(() => {
                        folder1Select.value = folderPath[1].folderId;
                        
                        // Load folder2 options
                        loadFolderOptions('folder', folderPath[1].folderId, folder2Select, 2);
                        
                        // Set folder2 if it exists in the path
                        if (folderPath.length > 2) {
                            setTimeout(() => {
                                folder2Select.value = folderPath[2].folderId;
                                
                                // Load folder3 options
                                loadFolderOptions('folder', folderPath[2].folderId, folder3Select, 3);
                                
                                // Set folder3 if it exists in the path
                                if (folderPath.length > 3) {
                                    setTimeout(() => {
                                        folder3Select.value = folderPath[3].folderId;
                                    }, 200);
                                }
                            }, 200);
                        }
                    }, 200);
                }
            }, 200);
        }
    } else if (permission.type === 'file' && permission.file_id) {
        // We need to find the folder that contains this file
        let fileInfo = findFileFolder(permission.file_id);
        if (fileInfo && fileInfo.folderId) {
            // First set up the folder path
            let folderPath = findFolderPath(fileInfo.folderId);
            if (folderPath && folderPath.length > 0) {
                // Set channel
                channelSelect.value = folderPath[0].channelId;
                
                // Chain of setTimeout calls to allow each select's change event to trigger
                // and load the options for the next select
                setTimeout(() => {
                    // Load folder1 options
                    loadFolderOptions('channel', folderPath[0].channelId, folder1Select, 1);
                    
                    // Set folder1 if it exists in the path
                    if (folderPath.length > 1) {
                        setTimeout(() => {
                            folder1Select.value = folderPath[1].folderId;
                            
                            // Load folder2 options
                            loadFolderOptions('folder', folderPath[1].folderId, folder2Select, 2);
                            
                            // Set folder2 if it exists in the path
                            if (folderPath.length > 2) {
                                setTimeout(() => {
                                    folder2Select.value = folderPath[2].folderId;
                                    
                                    // Load folder3 options
                                    loadFolderOptions('folder', folderPath[2].folderId, folder3Select, 3);
                                    
                                    // Set folder3 if it exists in the path
                                    if (folderPath.length > 3) {
                                        setTimeout(() => {
                                            folder3Select.value = folderPath[3].folderId;
                                            
                                            // Now load file options and set the file
                                            setTimeout(() => {
                                                loadFileOptions(folderPath[folderPath.length - 1].folderId);
                                                
                                                // Set the file
                                                setTimeout(() => {
                                                    fileSelect.value = permission.file_id;
                                                }, 300);
                                            }, 300);
                                        }, 200);
                                    } else {
                                        // Load file options and set the file
                                        setTimeout(() => {
                                            loadFileOptions(folderPath[folderPath.length - 1].folderId);
                                            
                                            // Set the file
                                            setTimeout(() => {
                                                fileSelect.value = permission.file_id;
                                            }, 300);
                                        }, 300);
                                    }
                                }, 200);
                            } else {
                                // Load file options and set the file
                                setTimeout(() => {
                                    loadFileOptions(folderPath[folderPath.length - 1].folderId);
                                    
                                    // Set the file
                                    setTimeout(() => {
                                        fileSelect.value = permission.file_id;
                                    }, 300);
                                }, 300);
                            }
                        }, 200);
                    }
                }, 200);
            }
        }
    }
    
    // Set user ID
    managerInput.value = permission.user_id;
    validateUserID(permission.user_id);
    
    // Change button text and functionality
    addBtn.textContent = '수정';
    addBtn.dataset.mode = 'edit';
    addBtn.dataset.id = permission.id;
    
    // Scroll to the top of the form
    document.querySelector('.input-table').scrollIntoView({ behavior: 'smooth' });
}

// Helper function to find a folder's path from the root
function findFolderPath(folderId) {
    if (!contentHierarchy || !folderId) return null;
    
    const path = [];
    
    // Check each channel
    for (const channel of contentHierarchy.channels) {
        const result = findFolderPathInChannel(channel, folderId, []);
        if (result) {
            // Add channel to the beginning of the path
            path.push({ level: 0, channelId: channel.id, name: channel.name });
            
            // Add each folder to the path
            result.forEach((folder, index) => {
                path.push({
                    level: index + 1,
                    folderId: folder.id,
                    name: folder.name
                });
            });
            
            return path;
        }
    }
    
    return null;
}

// Helper function to recursively find a folder's path in a channel
function findFolderPathInChannel(channel, targetFolderId, currentPath) {
    if (!channel.folders) return null;
    
    for (const folder of channel.folders) {
        // Check if this is the target folder
        if (folder.id == targetFolderId) {
            return [...currentPath, folder];
        }
        
        // Check subfolders
        if (folder.subfolders && folder.subfolders.length > 0) {
            const result = findFolderPathInSubfolders(folder.subfolders, targetFolderId, [...currentPath, folder]);
            if (result) {
                return result;
            }
        }
    }
    
    return null;
}

// Helper function to recursively find a folder's path in subfolders
function findFolderPathInSubfolders(subfolders, targetFolderId, currentPath) {
    for (const folder of subfolders) {
        // Check if this is the target folder
        if (folder.id == targetFolderId) {
            return [...currentPath, folder];
        }
        
        // Check subfolders
        if (folder.subfolders && folder.subfolders.length > 0) {
            const result = findFolderPathInSubfolders(folder.subfolders, targetFolderId, [...currentPath, folder]);
            if (result) {
                return result;
            }
        }
    }
    
    return null;
}

// Helper function to find which folder contains a specific file
function findFileFolder(fileId) {
    if (!contentHierarchy || !fileId) return null;
    
    // Check each channel
    for (const channel of contentHierarchy.channels) {
        if (!channel.folders) continue;
        
        for (const folder of channel.folders) {
            const result = findFileInFolder(folder, fileId);
            if (result.found) {
                return {
                    folderId: result.folderId,
                    fileName: result.fileName
                };
            }
        }
    }
    
    return null;
}

// Update permission
function updatePermission(permissionId) {
    // Clear previous error message
    errorMessage.textContent = '';
    
    // Get selected values
    const channelId = channelSelect.value;
    const folder1Id = folder1Select.value;
    const folder2Id = folder2Select.value;
    const folder3Id = folder3Select.value;
    const fileId = fileSelect.value;
    const managerId = managerInput.value.trim();
    
    // Validate input
    if (!channelId) {
        errorMessage.textContent = '채널을 선택해주세요.';
        return;
    }
    
    if (!managerId) {
        errorMessage.textContent = '담당자 ID를 입력해주세요.';
        return;
    }
    
    // Determine permission scope based on selection pattern
    let permissionScope;
    if (fileId) {
        permissionScope = 'file';
    } else if (folder1Id || folder2Id || folder3Id) {
        permissionScope = 'folder';
    } else {
        permissionScope = 'channel';
    }
    
    // Verify user exists
    verifyUser(managerId)
        .then(userData => {
            // Prepare permission data
            let permissionData = {
                user_id: managerId,
                type: permissionScope
            };
            
            if (permissionScope === 'channel') {
                permissionData.channel_id = channelId;
            } else if (permissionScope === 'folder') {
                // Use the deepest selected folder
                permissionData.folder_id = folder3Id || folder2Id || folder1Id;
            } else if (permissionScope === 'file') {
                permissionData.file_id = fileId;
            }
            
            // Send permission data to API to update
            return fetch(`${baseApiUrl}/contents/content_manager/${permissionId}`, {
                method: 'PUT',
                credentials: 'include',
                headers: {
                    'Content-Type': 'application/json',
                    'Accept': 'application/json'
                },
                body: JSON.stringify(permissionData)
            });
        })
        .then(response => {
            if (!response.ok) {
                // Special handling for duplicate entry error
                if (response.status === 409) {
                    return response.json().then(data => {
                        throw new Error(data.error || '이미 동일한 담당자 권한이 존재합니다.');
                    });
                }
                throw new Error('권한 수정에 실패했습니다.');
            }
            return response.json();
        })
        .then(data => {
            // Reload permissions list to maintain sorted order
            loadPermissions();
            
            // Clear form
            managerInput.value = '';
            validationMessage.textContent = '담당자 ID를 입력하거나 소속 정보를 통해 선택하세요';
            validationMessage.className = 'validation-message';
            
            // Clear user selection comboboxes
            resetUserSelectionComboboxes();
            
            // Reset the add button
            addBtn.textContent = '추가';
            delete addBtn.dataset.mode;
            delete addBtn.dataset.id;
            
            // Success message
            alert('담당자 권한이 수정되었습니다.');
        })
        .catch(error => {
            errorMessage.textContent = error.message;
        });
}

// Helper function to get better hierarchy information for permissions
function getHierarchyInfo(permission) {
    if (!contentHierarchy || !contentHierarchy.channels || !Array.isArray(contentHierarchy.channels)) {
        console.warn('Content hierarchy not loaded correctly when getting hierarchy info');
        return { folderParts: ['', '', '', ''], fileName: '' };
    }
    
    let folderParts = ['', '', '', ''];
    let fileName = '';
    
    try {
        if (permission.type === 'channel' && permission.channel_id) {
            // For channel permissions, just show the channel name
            const channel = contentHierarchy.channels.find(c => c.id == permission.channel_id);
            if (channel) {
                folderParts[0] = channel.name;
            } else {
                console.warn(`Channel not found for id: ${permission.channel_id}`);
            }
        } else if (permission.type === 'folder' && permission.folder_id) {
            // For folder permissions, find the folder path using our helper function
            const folderPath = findFolderPath(permission.folder_id);
            if (folderPath && folderPath.length > 0) {
                // Extract names from the path
                folderPath.forEach((item, index) => {
                    if (index < 4) {
                        folderParts[index] = item.name;
                    }
                });
            } else {
                console.warn(`Folder path not found for id: ${permission.folder_id}`);
            }
        } else if (permission.type === 'file' && permission.file_id) {
            // For file permissions, first find the folder that contains this file
            const fileInfo = findFileFolder(permission.file_id);
            if (fileInfo && fileInfo.folderId) {
                // Then get the folder path
                const folderPath = findFolderPath(fileInfo.folderId);
                if (folderPath && folderPath.length > 0) {
                    // Extract names from the path
                    folderPath.forEach((item, index) => {
                        if (index < 4) {
                            folderParts[index] = item.name;
                        }
                    });
                    
                    // Set the file name
                    fileName = fileInfo.fileName;
                } else {
                    console.warn(`Folder path not found for file folder id: ${fileInfo.folderId}`);
                }
            } else {
                console.warn(`File folder not found for file id: ${permission.file_id}`);
            }
        } else {
            console.warn(`Unhandled permission type or missing ID: ${permission.type}`);
        }
    } catch (error) {
        console.error('Error getting hierarchy info:', error);
    }
    
    return { folderParts, fileName };
}

// Update Manager Modal functionality
let currentUpdateManagerId = null;

function openUpdateManagerModal(dataset) {
    const modal = document.getElementById('update-manager-modal');
    const overlay = document.getElementById('modal-overlay');
    const targetContentInfo = document.getElementById('target-content-info');
    const currentManagerInfo = document.getElementById('current-manager-info');
    
    // Store the permission ID for updating
    currentUpdateManagerId = dataset.id;
    
    // Get content information based on type
    const contentType = dataset.type;
    const contentId = dataset.contentId;
    let contentPath = '';
    let contentName = '';
    
    try {
        if (contentType === 'channel') {
            const channel = contentHierarchy?.channels?.find(c => c.id == contentId);
            contentName = channel ? channel.name : `채널 ID: ${contentId}`;
            contentPath = `채널: ${contentName}`;
        } else if (contentType === 'folder') {
            contentPath = getPathInHierarchy(contentType, contentId);
            contentName = contentPath.split('/').pop() || `폴더 ID: ${contentId}`;
            contentPath = `폴더: ${contentPath}`;
        } else if (contentType === 'file') {
            contentPath = getPathInHierarchy(contentType, contentId);
            contentName = contentPath.split('/').pop() || `파일 ID: ${contentId}`;
            contentPath = `페이지: ${contentPath}`;
        }
    } catch (error) {
        console.error('Error getting content information:', error);
        contentPath = `${contentType} ID: ${contentId}`;
    }
    
    // Display target content information
    targetContentInfo.innerHTML = `
        <div class="target-content-details">
            <p><strong>권한 범위:</strong> ${contentType === 'channel' ? '채널' : contentType === 'folder' ? '폴더' : '페이지'}</p>
            <p><strong>대상 콘텐츠:</strong> ${contentPath}</p>
        </div>
    `;
    
    // Display current manager information
    currentManagerInfo.innerHTML = `
        <div class="current-manager-details">
            <p><strong>현재 담당자:</strong> ${dataset.currentName || '-'}</p>
            <p><strong>사번:</strong> ${dataset.currentUser || '-'}</p>
            <p><strong>회사:</strong> ${dataset.currentCompany || '-'}</p>
            <p><strong>부서:</strong> ${dataset.currentDepartment || '-'}</p>
            <p><strong>직책:</strong> ${dataset.currentPosition || '-'}</p>
        </div>
    `;
    
    // Reset form
    resetUpdateManagerForm();
    
    // Load user data for comboboxes
    loadUpdateUserComboboxes();
    
    // Show modal
    modal.style.display = 'block';
    overlay.style.display = 'block';
}

function closeUpdateManagerModal() {
    const modal = document.getElementById('update-manager-modal');
    const overlay = document.getElementById('modal-overlay');
    
    modal.style.display = 'none';
    overlay.style.display = 'none';
    currentUpdateManagerId = null;
    resetUpdateManagerForm();
}

function resetUpdateManagerForm() {
    document.getElementById('update-manager-input').value = '';
    document.getElementById('update-validation-message').textContent = '새 담당자 ID를 입력하거나 소속 정보를 통해 선택하세요';
    document.getElementById('update-validation-message').className = 'validation-message';
    
    // Clear error/success messages
    document.getElementById('update-error-message').style.display = 'none';
    document.getElementById('update-success-message').style.display = 'none';
}

function loadUpdateUserComboboxes() {
    const updateCompanySelect = document.getElementById('update-company-select');
    const updateDepartmentSelect = document.getElementById('update-department-select');
    const updatePositionSelect = document.getElementById('update-position-select');
    const updateNameSelect = document.getElementById('update-name-select');
    
    // Reset all selects
    updateCompanySelect.innerHTML = '<option value="">회사명</option>';
    updateDepartmentSelect.innerHTML = '<option value="">부서</option>';
    updatePositionSelect.innerHTML = '<option value="">직책</option>';
    updateNameSelect.innerHTML = '<option value="">이름</option>';
    
    // Load company options
    fetch(`${getBaseApiUrl()}/user/companies`, {
        method: 'GET',
        credentials: 'include',
        headers: {
            'Content-Type': 'application/json',
            'Accept': 'application/json'
        }
    })
    .then(response => response.json())
    .then(data => {
        if (Array.isArray(data)) {
            data.forEach(company => {
                const option = document.createElement('option');
                option.value = company;
                option.textContent = company;
                updateCompanySelect.appendChild(option);
            });
        }
    })
    .catch(error => {
        console.error('Error loading company options:', error);
    });
    
    // Add event listeners for update comboboxes
    updateCompanySelect.addEventListener('change', () => loadUpdateDepartmentOptions(updateCompanySelect.value));
    updateDepartmentSelect.addEventListener('change', () => loadUpdatePositionOptions(updateCompanySelect.value, updateDepartmentSelect.value));
    updatePositionSelect.addEventListener('change', () => loadUpdateNameOptions(updateCompanySelect.value, updateDepartmentSelect.value, updatePositionSelect.value));
    updateNameSelect.addEventListener('change', () => {
        if (updateNameSelect.value) {
            // Set the selected user's ID in the manager input field (same logic as main table)
            document.getElementById('update-manager-input').value = updateNameSelect.value;
            validateUpdateUserID(updateNameSelect.value);
        }
    });
}

function loadUpdateDepartmentOptions(company) {
    const updateDepartmentSelect = document.getElementById('update-department-select');
    updateDepartmentSelect.innerHTML = '<option value="">부서</option>';
    
    if (!company) return;
    
    fetch(`${getBaseApiUrl()}/user/departments?company=${encodeURIComponent(company)}`, {
        method: 'GET',
        credentials: 'include',
        headers: {
            'Content-Type': 'application/json',
            'Accept': 'application/json'
        }
    })
    .then(response => response.json())
    .then(data => {
        if (Array.isArray(data)) {
            data.forEach(department => {
                const option = document.createElement('option');
                option.value = department;
                option.textContent = department;
                updateDepartmentSelect.appendChild(option);
            });
        }
    })
    .catch(error => {
        console.error('Error loading department options:', error);
    });
}

function loadUpdatePositionOptions(company, department) {
    const updatePositionSelect = document.getElementById('update-position-select');
    updatePositionSelect.innerHTML = '<option value="">직책</option>';
    
    if (!company || !department) return;
    
    fetch(`${getBaseApiUrl()}/user/positions?company=${encodeURIComponent(company)}&department=${encodeURIComponent(department)}`, {
        method: 'GET',
        credentials: 'include',
        headers: {
            'Content-Type': 'application/json',
            'Accept': 'application/json'
        }
    })
    .then(response => response.json())
    .then(data => {
        if (Array.isArray(data)) {
            data.forEach(position => {
                const option = document.createElement('option');
                option.value = position;
                option.textContent = position;
                updatePositionSelect.appendChild(option);
            });
        }
    })
    .catch(error => {
        console.error('Error loading position options:', error);
    });
}

function loadUpdateNameOptions(company, department, position) {
    const updateNameSelect = document.getElementById('update-name-select');
    loadNamesForSelect(updateNameSelect, company, department, position);
}

function validateUpdateUserID(userId) {
    const updateValidationMessage = document.getElementById('update-validation-message');
    const updateManagerInput = document.getElementById('update-manager-input');
    
    if (!userId) {
        updateValidationMessage.textContent = '새 담당자 ID를 입력하거나 소속 정보를 통해 선택하세요';
        updateValidationMessage.className = 'validation-message';
        return;
    }
    
    fetch(`${getBaseApiUrl()}/user/verify?id=${encodeURIComponent(userId)}`, {
        method: 'GET',
        credentials: 'include',
        headers: {
            'Content-Type': 'application/json',
            'Accept': 'application/json'
        }
    })
    .then(response => {
        if (!response.ok) {
            updateValidationMessage.textContent = 'ID 검증에 실패했습니다';
            updateValidationMessage.className = 'validation-message error';
            throw new Error(`HTTP ${response.status}`);
        }
        return response.json();
    })
    .then(data => {
        if (data && data.exists) {
            const user = data.user;
            // Update the input field to use the database's casing
            if (updateManagerInput.value.toLowerCase() === user.id.toLowerCase() && 
                updateManagerInput.value !== user.id) {
                updateManagerInput.value = user.id;
            }
            updateValidationMessage.textContent = `${user.company || '-'} ${user.department || '-'} ${user.name || '-'} ${user.position || '-'}\n올바른 ID입니다.`;
            updateValidationMessage.className = 'validation-message success';
        } else {
            updateValidationMessage.textContent = 'ID를 찾을 수 없습니다';
            updateValidationMessage.className = 'validation-message error';
        }
    })
    .catch(error => {
        console.error('Error validating user ID:', error);
        updateValidationMessage.textContent = 'ID 검증에 실패했습니다';
        updateValidationMessage.className = 'validation-message error';
    });
}

function updateManager() {
    const updateManagerInput = document.getElementById('update-manager-input');
    const updateErrorMessage = document.getElementById('update-error-message');
    const updateSuccessMessage = document.getElementById('update-success-message');
    
    const newUserId = updateManagerInput.value.trim();
    
    if (!newUserId) {
        updateErrorMessage.textContent = '새 담당자 ID를 입력해주세요.';
        updateErrorMessage.style.display = 'block';
        updateSuccessMessage.style.display = 'none';
        return;
    }
    
    // Prepare the update data
    const updateData = {
        user_id: newUserId
    };
    
    fetch(`${getBaseApiUrl()}/contents/content_manager/${currentUpdateManagerId}`, {
        method: 'PUT',
        credentials: 'include',
        headers: {
            'Content-Type': 'application/json',
            'Accept': 'application/json'
        },
        body: JSON.stringify(updateData)
    })
    .then(response => {
        if (!response.ok) {
            return response.json().then(errorData => {
                throw new Error(errorData.error || '담당자 변경에 실패했습니다.');
            });
        }
        return response.json();
    })
    .then(data => {
        updateSuccessMessage.textContent = '담당자가 성공적으로 변경되었습니다.';
        updateSuccessMessage.style.display = 'block';
        updateErrorMessage.style.display = 'none';
        
        // Refresh the permissions list by triggering refresh button
        setTimeout(() => {
            closeUpdateManagerModal();
            
            // Trigger refresh to reload permissions
            const refreshBtn = document.getElementById('refresh-btn');
            if (refreshBtn) {
                refreshBtn.click();
            } else {
                // Fallback: try to reload the page if refresh button not found
                console.warn('Refresh button not found, attempting manual reload');
                window.location.reload();
            }
        }, 1500);
    })
    .catch(error => {
        console.error('Error updating manager:', error);
        updateErrorMessage.textContent = error.message;
        updateErrorMessage.style.display = 'block';
        updateSuccessMessage.style.display = 'none';
    });
} 