import './progress_user_summary.js';
import { configureContentsProgress} from './progress_user_status.js?v=202508131026';
import { getTopUserConnectionDuration, getTopDepartmentConnectionDuration, getTopCompanyConnectionDuration} from './progress_admin_active_user.js'

const userNames = document.querySelectorAll(".user-name");
const updateList = document.getElementById("update-list");

const updateContentsUnviewedCount = document.getElementById("update-contents-unviewed-count");
const pushMessageContainer = document.getElementById("push-message-container");
const pushMessageCount = document.getElementById("push-message-count");
const updateListBtn = document.getElementById('update-list-btn');
const latestLoginTime = document.getElementById("latest-login-time");
const emptyLearningDays = document.getElementById("empty-learning-days");

const lowerLearningChannelCount = document.getElementById("lower-learning-channel_count");
const lowerLearningChannels = document.getElementById("lower-learning-channels");

const firstCompany = document.getElementById("first-company");
const firstDepartment = document.getElementById("first-department");
const firstUser = document.getElementById("first-user");

let userInfoMemoValueCount;
let userInfoLevelValueLevel;
let userInfoRankValueRank;
let userInfoProgressValueProgress;

let updateContentsData = null; // 업데이트 콘텐츠 데이터를 저장할 전역 변수
let updateContentsWindow = null; // 업데이트 창 참조를 저장할 전역 변수

let pushMessageData = null;
let pushMessageWindow = null; // 푸시 메시지 창 참조를 저장할 전역 변수

let userLearningChannelData = null; // 사용자 학습 채널 데이터를 저장할 전역 변수 

const loggedInUser = JSON.parse(sessionStorage.getItem("loggedInUser"));

// 자식 창들을 닫는 공통 함수
function closeChildWindows() {
    if (pushMessageWindow && !pushMessageWindow.closed) {
        pushMessageWindow.close();
    }
    if (updateContentsWindow && !updateContentsWindow.closed) {
        updateContentsWindow.close();
    }
}

// 페이지 종료 시 자식 창들을 닫기
window.addEventListener('beforeunload', closeChildWindows);

pushMessageContainer.addEventListener("click", () => {
    // 데이터가 없으면 먼저 로드
    if (!pushMessageData || pushMessageData.length === 0) {
        //alert('메시지 데이터를 먼저 불러오고 있습니다. 잠시 후 다시 시도해주세요.');
        return;
    }
    
    // 이미 열린 창이 있고 닫히지 않았다면 포커스만 주고 데이터 업데이트
    if (pushMessageWindow && !pushMessageWindow.closed) {
        pushMessageWindow.focus();
        // 데이터 업데이트
        if (pushMessageWindow.setPushMessageData) {
            pushMessageWindow.setPushMessageData(pushMessageData);
        }
        return;
    }
    
    // 새 창 열기
    pushMessageWindow = window.open('push_message_list.html', 'pushMessageWindow', 'width=500,height=400,scrollbars=yes,resizable=yes');
    
    // 창이 성공적으로 열렸는지 확인
    if (!pushMessageWindow) {
        return;
    }
    
    // 새 창이 로드된 후 데이터 전달
    pushMessageWindow.addEventListener('load', function() {
        // 새 창의 전역 함수 호출하여 데이터 전달
        if (pushMessageWindow && pushMessageWindow.setPushMessageData) {
            pushMessageWindow.setPushMessageData(pushMessageData);
        }
    });
});

// 업데이트 리스트 버튼 클릭 이벤트 추가
if (updateListBtn) {
    updateListBtn.addEventListener('click', function() {
        // 데이터가 없으면 먼저 로드
        if (!updateContentsData) {
            alert('업데이트 데이터를 먼저 불러오고 있습니다. 잠시 후 다시 시도해주세요.');
            return;
        }
        
        // 이미 열린 창이 있고 닫히지 않았다면 포커스만 주고 데이터 업데이트
        if (updateContentsWindow && !updateContentsWindow.closed) {
            updateContentsWindow.focus();
            // 데이터 업데이트
            if (updateContentsWindow.setUpdateContentsData) {
                updateContentsWindow.setUpdateContentsData(updateContentsData);
            }
            return;
        }
        
        // 새 창 열기
        updateContentsWindow = window.open('update_contents_list.html', 'updateContentsWindow', 'width=500,height=435,scrollbars=yes,resizable=no');
        
        // 창이 성공적으로 열렸는지 확인
        if (!updateContentsWindow) {
            return;
        }
        
        // 새 창이 로드된 후 데이터 전달
        updateContentsWindow.addEventListener('load', function() {
            // 새 창의 전역 함수 호출하여 데이터 전달
            if (updateContentsWindow && updateContentsWindow.setUpdateContentsData) {
                updateContentsWindow.setUpdateContentsData(updateContentsData);
            }
        });
    });
}

if(loggedInUser !== null)
    userNames.forEach(userName => {
        userName.textContent = loggedInUser.user.name;
    });

(async() =>
{
    await configureUserLearningStatus(); 
    await getUpdateContents();

    await loadPushMessage();

    await getLatestLoginTime();

    const {count, channels} = await compareLearningRateWithTotalAvg();
    lowerLearningChannelCount.textContent = `${count}개 콘텐츠`;
    lowerLearningChannels.textContent = `(${channels.join(", ")})`;


    const topCompanyInfo = await getTopCompanyConnectionDuration('day', `2025-01-01~${new Date().toLocaleDateString('sv-SE')}`); // 현재 날짜를 'yyyy-MM-dd' 형식으로 변환하여 사용
    firstCompany.textContent = `${topCompanyInfo?.data?.top?.[0]?.[0] ?? '없음'}`;
    const topDepartmentInfo = await getTopDepartmentConnectionDuration('day', `2025-01-01~${new Date().toLocaleDateString('sv-SE')}`); // 현재 날짜를 'yyyy-MM-dd' 형식으로 변환하여 사용
    firstDepartment.textContent = `${topDepartmentInfo?.data?.top?.[0]?.[1] ?? '없음'}`;
    const topUserInfo = await getTopUserConnectionDuration('day', `2025-01-01~${new Date().toLocaleDateString('sv-SE')}`); // 현재 날짜를 'yyyy-MM-dd' 형식으로 변환하여 사용
    firstUser.textContent = `${topUserInfo?.data?.top?.[0]?.[1] ?? '없음'}`;

    await configureContentsProgress(userLearningChannelData);

    setupPushNotification();
    // let isLoading = false;
    // setInterval(async() => {
    //     if(isLoading) return;
    //     isLoading = true;
    //     await loadPushMessage()
    //     isLoading = false;
    // }, 60000); // 1분마다 푸시 메시지 새로고침



    setInterval(async() => {
        await getLatestLoginTime();
    }, 900000); // 15분마다 마지막 접속 기록 갱신

})();

function setupPushNotification() {
    const eventSource = new EventSource(`${window.baseUrl}leaning/push/events`);
    eventSource.onmessage = async function(event) {
        console.log('Push notification received:', event.data);
        // 서버로부터 새로운 푸시 메시지가 있다는 알림을 받았습니다.
        // 메시지 목록을 다시 로드합니다.
        await loadPushMessage();
    };

    eventSource.onerror = function(event) {
        console.error("EventSource error:", event);
        eventSource.close(); // 오류 발생 시 연결 종료
    }
}

/**
 * 사용자 학습 상태 정보 구성(의견서 개수, 레벨 등등)
 */
async function configureUserLearningStatus()
{
    const user = JSON.parse(sessionStorage.getItem("loggedInUser"));

    let memoCount = 0;
    let level = 0;
    let rank = 0;
    let progress = 0;

    if(user !== null) {
        const id = user.user.id;
        memoCount = await getCountOfMemo(id);
    }

    const items = [
        { icon: "memo", type: "count", value: memoCount, unit: "개", unitPosition:"after", label:"의견서"},
        { icon: "level", type: "level", value: level, unit:"LV.", unitPosition:"before", label:"레벨"},
        { icon: "rank", type: "rank", value: rank, unit:"위", unitPosition:"after", label:"랭킹"},
        { icon: "progress", type: "progress", value: progress, unit:"%", unitPosition:"after", label:"진도율" }
    ]

    items.forEach((item, index) => {
        const valueId = `user-${item.icon}-value-${item.type}`;
        let valueSpan = `<span id=${valueId} style="font-size: 25px; font-weight: bold; font-family:'Noto Sans KR'; color: #fff;">${item.value}</span>`;
        let unitSpan = `<span style="font-size: 10px; font-weight: bold; font-family:'Noto Sans KR'; color: #fff; align-self:flex-end; margin-bottom: 5px;" >${item.unit}</span>`;
        let valueBlock = "";

        if(item.unitPosition === "before") {
            valueBlock = `${unitSpan}${valueSpan}`;
        }
        else if(item.unitPosition === "after") {
            valueBlock = `${valueSpan}${unitSpan}`;
        }

        const html = `
            <div class="rectangle" style="margin-right: 1rem;">
                <div>
                    <div style="margin-top: 5px;">
                        <svg width="37" height="40">
                            <use href="asset/images/images.svg#${item.icon}" />
                        </svg>
                    </div>
                    <div style="flex-direction: row;">
                        ${valueBlock}
                    </div>
                    <div>
                        <span style="font-size: 15px; font-weight: bold; font-family:'Noto Sans KR'; color: #fff;">${item.label}</span>
                    </div>
                </div>
            </div>
        `;

        if(index < 2) {
            document.getElementById("user-info-rect-top").insertAdjacentHTML("beforeend", html);
        } else {
            document.getElementById("user-info-rect-bottom").insertAdjacentHTML("beforeend", html);
        }
        
    });

    userInfoMemoValueCount = document.getElementById("user-memo-value-count");
    userInfoLevelValueLevel = document.getElementById("user-level-value-level");
    userInfoRankValueRank = document.getElementById("user-rank-value-rank");
    userInfoProgressValueProgress = document.getElementById("user-progress-value-progress");

    var loggedInUser = JSON.parse(sessionStorage.getItem("loggedInUser"));
    if(loggedInUser) {
        userInfoMemoValueCount.textContent = await getCountOfMemo(loggedInUser.user.id);
        userInfoRankValueRank.textContent = await getUserRank();
        userInfoProgressValueProgress.textContent = await getUserLearningRate(loggedInUser.user.id);
    }
}

/**
 * 사용자의 의견서 개수를 가져오는 함수  
 * @param {string} userId - 사번
 * @returns {Promise<number>} - 의견서 개수
 * 0 if an error occurs.
 */
async function getCountOfMemo(userId) {
    try{
        const response = await fetch(`${window.baseUrl}memo/?user_id=${userId}`);
        const data = await response.json();
        if(response.ok) 
        {
            return data.length;
        }
    }
    catch(e) {
        console.error("Error fetching memo count:", e);
    }
    return 0;
}

/**
 * 사용자의 랭킹을 가져오는 함수
 * @returns {Promise<number>} - 사용자의 랭킹
 */
async function getUserRank() {
    try {
        const response = await fetch(`${window.baseUrl}leaning/my_learning_rank`);
        const data = await response.json();

        if(response.ok) {
            return data.rank;
        }
    }
    catch(e) {
        console.error("Error fetching user rank:", e);
    }
    return 0;
}

/**
 * 사용자 학습률을 가져오는 함수
 * @param {string} id - 사용자 ID
 * @returns {Promise<number>} - 사용자 학습률
 */
async function getUserLearningRate(id) {
    try {
        var period_type = 'day';
        var period_value = `2025-01-01 ~ ${formatDate(new Date())}`; // 현재 날짜까지의 범위
        const response = await fetch(`${window.baseUrl}leaning/completion-rate?filter_type=user&filter_value=${id}&period_type=${period_type}&period_value=${period_value}`);
        const data = await response.json();

        if(response.ok) {
            return data.completion_rate;
        }
    }
    catch(e) {
        console.error("Error fetching user learning rate:", e);
    }
    return 0;
}



/**
 * 최근 업데이트된 콘텐츠를 가져오는 함수
 * @param {number} daysAgo - 최근 업데이트된 콘텐츠를 가져올 기간 (일)
 */
async function getUpdateContents(daysAgo = 14) {
    try {
        const response = await fetch(`${window.baseUrl}leaning/get_updated_contents?days=${daysAgo}`);
        const data = await response.json();

        if(response.ok) {
            // 데이터 저장
            updateContentsData = data.contents || [];
            
            updateList.innerHTML = ""; // 기존 내용 초기화
            
            if (data.contents && data.contents.length > 0) {
                var unviewedCount = 0;
                data.contents.forEach(content => {
                    const tr = document.createElement("tr");
                    
                    // 업데이트 날짜 포맷팅 (월/일 형식)
                    const updateDate = new Date(content.updated_at);
                    const dateStr = `${updateDate.getMonth() + 1}/${updateDate.getDate()}`;
                    
                    // 파일 이름에서 000_ 형식의 접두사와 확장자 제거
                    const cleanedName = content.name.replace(/^\d+_/, '').replace(/\.[^/.]+$/, '');
                    
                    // 업데이트 확인 안한 건은 파란색 텍스트
                    const textColor = content.viewed_after_update ? "#000" : "#007bff";
                    unviewedCount += content.viewed_after_update ? 0 : 1;

                    // innerHTML은 XSS 공격에 취약하므로, textContent를 사용하여 안전하게 설정
                    // 제목(td) 생성
                    const titleCell = document.createElement('td');
                    titleCell.style.padding = "8px";
                    titleCell.style.fontSize = "13px";
                    titleCell.style.color = textColor;
                    titleCell.style.whiteSpace = "nowrap";
                    titleCell.style.overflow = "hidden";
                    titleCell.style.textOverflow = "ellipsis";
                    titleCell.title = cleanedName; // 툴팁에 전체 이름 표시
                    titleCell.textContent = cleanedName;
                    
                    // 날짜(td) 생성
                    const dateCell = document.createElement('td');
                    dateCell.style.padding = "8px";
                    dateCell.style.fontSize = "13px";
                    dateCell.style.color = textColor;
                    dateCell.style.textAlign = "center";
                    dateCell.textContent = dateStr;
                    
                    // tr에 td 추가
                    tr.appendChild(titleCell);
                    tr.appendChild(dateCell);
                    
                    updateList.appendChild(tr);

                    updateContentsUnviewedCount.textContent = unviewedCount || 0; // 업데이트 확인 안한 콘텐츠 개수 표시
                });
            } else {
                // 데이터가 없을 때
                const tr = document.createElement("tr");
                tr.innerHTML = `
                    <td colspan="2" style="text-align: center; padding: 20px; color: #888; font-size: 13px;">
                        최근 ${daysAgo}일 동안 업데이트된 콘텐츠가 없습니다.
                    </td>
                `;
                updateList.appendChild(tr);
            }
        }
    }
    catch(e) {
        console.error("Error fetching update contents:", e);
        updateContentsData = null;
        const tr = document.createElement("tr");
        tr.innerHTML = `
            <td colspan="2" style="text-align: center; padding: 20px; color: #dc3545; font-size: 13px;">
                업데이트 콘텐츠를 불러오는 중 오류가 발생했습니다.
            </td>
        `;
        updateList.appendChild(tr);
    }
}

/**
 * 푸시 메시지를 불러오는 함수
 * @returns {Promise<void>} 
 */
async function loadPushMessage() {
    const response = await fetch(`${window.baseUrl}leaning/push/load`);
    const data = await response.json();
    if (response.ok) {
        pushMessageCount.textContent = data.messages.length || 0; // 메시지 개수 표시
        pushMessageData = data.messages; // 메시지 데이터 저장
    } else {
        console.error("Failed to load push messages:", data.error);
    }
    
}

/**
 * 최신 로그인 시간을 가져오는 함수
 * @returns {Promise<void>}
 */
async function getLatestLoginTime() {
    const response = await fetch(`${window.baseUrl}user/get_latest_login_time`);
    const data = await response.json();
    if (response.ok) {
        const date = new Date(data.latest_login_time);
        const today = new Date();

        const year = date.getFullYear();
        const month = String(date.getMonth() + 1).padStart(2, '0'); // 월은 0부터 시작하므로 +1
        const day = String(date.getDate()).padStart(2, '0');
        const hours = String(date.getHours()).padStart(2, '0');
        const minutes = String(date.getMinutes()).padStart(2, '0');
        const seconds = String(date.getSeconds()).padStart(2, '0');

        latestLoginTime.textContent = `${year}.${month}.${day} ${hours}시${minutes}분${seconds}초로` || "정보 없음으로"; // 최신 로그인 시간 표시

        // 오늘 날짜와 비교하여 학습하지 않은 날 수 계산(날짜 비교_시간제외)
        today.setHours(0, 0, 0, 0);
        date.setHours(0, 0, 0, 0);
        const diff = today.getTime() - date.getTime();
        const diffDays = Math.floor(diff / (1000 * 60 * 60 * 24));

        emptyLearningDays.textContent = diffDays || 0;

    } else {
        console.error("Failed to load latest login time:", data.error);
        emptyLearningDays.textContent = "0";
        latestLoginTime.textContent = "없습니다.";
    }
}

/**
 * 사용자의 학습률을 전체 평균 학습률과 비교하여, 전체 평균보다 낮은 사용자 학습률을 가진 채널 목록을 반환하는 함수
 * @returns {Promise<{count: number, channels: string[]}>} - 전체 평균 학습률보다 낮은 사용자 학습률을 가진 채널 목록
 */
async function compareLearningRateWithTotalAvg() {
    try {
        const totalAvgData = await getLearningRatePerCategory('all'); // 전체 평균 학습률 가져오기
        userLearningChannelData = await getLearningRatePerCategory('user'); // 사용자별 학습률 가져오기

        if(!totalAvgData || totalAvgData.length === 0 || !userLearningChannelData)
        {
            return {count: 0, channels: []}; // 전체 평균 데이터가 없으면 빈 배열 반환
        }

        const userMap = new Map(userLearningChannelData.map(item => [item.channel_id, Number(item.progress_rate) || 0])); // 사용자 학습률을 Map으로 변환

        const lowerChannels = totalAvgData.filter(avgItem =>
        {
            const userRate = userMap.get(avgItem.channel_id) ?? 0; // 사용자 학습률이 없으면 0으로 처리
            return userRate < avgItem.progress_rate; // 사용자 학습률이 전체 평균보다 낮은 경우
        }).map(avgItem => avgItem.channel_name); // 채널 이름만 추출

        return {
            count: lowerChannels.length, // 전체 평균보다 낮은 학습률을 가진 채널 개수
            channels: convertChannelNames(lowerChannels) // 채널 이름 배열
        }
       
    } catch (error) {
        console.error("Error comparing learning rate with total average:", error);
    }

    return {count: 0, channels: []}; // 오류 발생 시 빈 배열 반환
}

/**
 * 사용자의 학습률을 카테고리별로 가져오는 함수
 * @param {string} type 
 * @returns 
 */
async function getLearningRatePerCategory(type = 'user') {
    try {
        const response = await fetch(`${window.baseUrl}leaning/get_learning_rate_per_category?type=${type}`);
        const data = await response.json();
        if (response.ok) {
            // 데이터 처리
            return data;
        } else {
            console.error("Failed to load learning rate per category:", data.error);
        }
    } catch (error) {
        console.error("Error fetching learning rate per category:", error);
    }

    return null; // 오류 발생 시 null 반환
}

/* * 채널 이름을 변환하는 함수
 * @param {string[]} channels - 채널 이름 배열
 * @returns {string[]} - 변환된 채널 이름 배열
 */
function convertChannelNames(channels) {
    return channels.map(name =>{
        const match = name.match(/^(\d{3})_(.+)$/);
        if (!match) return name;

        const num = parseInt(match[1], 10);
        if (num < 1 || num > 26) return name; // A~Z까지만
        const letter = String.fromCharCode(64 + num); // 1 → A, 2 → B ...

        return `${letter}.${match[2]}`;
    });
}

/**
 * 날짜를 YYYY-MM-DD 형식으로 포맷팅
 * @param {Date} date - 포맷팅할 날짜 객체
 * @returns {string} - YYYY-MM-DD 형식의 문자열
 */
function formatDate(date) {
    return date.getFullYear() + '-' + 
           String(date.getMonth() + 1).padStart(2, '0') + '-' + 
           String(date.getDate()).padStart(2, '0');
}
