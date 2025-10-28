import { attachCustomScrollbar } from "./custom_vscroll.js";
import { updateTrafficGaugeValue } from "./progress_admin_traffic.js";

let currentUserMap = new Map();

export async function activeUser(period_type, period_value)
{
    const wrapper = document.querySelector(".listbox-container");
    const container = document.querySelector(".custom-listbox");
    const res = await fetch('custom_vscroll.html');
    const html = await res.text();
    wrapper.insertAdjacentHTML('beforeend', html);
    const scrollbar = wrapper.querySelector('.custom-scrollbar');
    const thumb = wrapper.querySelector('.custom-scrollbar-thumb');
    const {refresh} = attachCustomScrollbar(container, scrollbar, thumb);
    const user_count = document.getElementById("active-user-count");

    //let allTotalDuration = null;
    //let pendingUsers = [];        // 나중에 처리할 사용자들

    // getTopUserConnectionDuration(period_type, period_value)
    // .then(data =>
    // {
    //     allTotalDuration = data.data.top[0][2];

    //     for (const {userId, element, duration} of pendingUsers) {
    //         const percentage = ((duration / allTotalDuration) * 100).toFixed(2);
    //         const status = element.querySelector('.status');
    //         status.className = (percentage <= 20) ? "yellow-RedBorder" : "yellow";
    //     }
    // }
    // );

    let websocketUrl = `${window.websocketUrl}`;
    const socket = new WebSocket(websocketUrl);
 
    socket.onopen = () => {};
    socket.onmessage = async(event) =>
    {
        try{
            const data = JSON.parse(event.data);
            if(data.type == "user_count")
            {
                updateTrafficGaugeValue(data.count, data.max_users);
                if(user_count)
                    user_count.textContent = `현재접속인원 : ${data.count} 명`;

                const newUserIds = new Set(data.users.map(u => u.user_id));

                for (const [userId, element] of currentUserMap.entries()) {
                    if (!newUserIds.has(userId)){
                        container.removeChild(element);
                        currentUserMap.delete(userId);
                    }
                }

                const userInfos = await Promise.all(data.users
                    .filter(user => !currentUserMap.has(user.user_id))
                    .map(async user => {
                    const info = await getUserInfo(user);
                    const today = new Date().toLocaleDateString('sv-SE');
                    //const userDuration = await getUserConnectionDuration(period_type, period_value, 'user', user.user_id);
                    const completionRate = await getCompletionRate('day', `2025-01-01~${today}`, 'user', user.user_id);
                    //const userDurationSec = userDuration.total_duration;
                    return { user, info, completionRate};
                }));

                for (const {user, info, completionRate /*userDurationSec*/} of userInfos) {
                    
                    if(currentUserMap.has(user.user_id)) continue;

                    const item = document.createElement("div");
                    item.contentEditable = false;
                    item.className = "listbox-item";

                    const name = document.createElement("span");
                    name.contentEditable = false;
                    name.className = "user_text";
                    name.textContent = `${info.username}/${user.user_id}/${info.position}`;

                    const status = document.createElement("span");
                    status.className = "status";

                    item.appendChild(name);
                    item.appendChild(status);
                    container.appendChild(item);
                    currentUserMap.set(user.user_id, item);

                     if(completionRate <= 20)
                        status.className = "yellow-RedBorder";
                    else
                        status.className = "yellow";

                    // if(allTotalDuration)
                    // {
                    //     const userPercentage = (allTotalDuration > 0) 
                    //         ? parseFloat(((userDurationSec / allTotalDuration) * 100).toFixed(2))
                    //         : parseFloat("0.00");

                    //     if(userPercentage <= 20)
                    //         status.className = "yellow-RedBorder";
                    //     else
                    //         status.className = "yellow";
                    // }
                    // else
                    //     pendingUsers.push({userId: user.user_id, element: item, duration: userDurationSec});
                }

                refresh();
            }
        }
        catch(error){
            console.error("Error parsing JSON:", error);
        }
    };
}


async function getUserInfo(user) {

    const apiURL = `${window.baseUrl}user/user_info?id=${user.user_id}`;
    const response = await fetch(apiURL);
    const userData = await response.json();

    if(response.ok) {
        return {
            username: userData.name,
            position: userData.position
        };
    }
}

async function getCompletionRate(period_type='day', period_value, filter_type='user', filter_value) {
    let url = `${window.baseUrl}leaning/completion-rate?period_value=${period_value}`;
    if(period_type != null)
      url += `&period_type=${period_type}`;
    if(filter_type != null)
      url += `&filter_type=${filter_type}`;
    if(filter_value != null)
      url += `&filter_value=${encodeURIComponent(filter_value)}`;

    const response = await fetch(url);
    const data = await response.json();
    if(response.ok) {
        return data.completion_rate;        
    }
    else 
        return 0;
}

export async function getUserConnectionDuration(period_type=null, period_value, filter_type=null, filter_value=null) {
    let url = `${window.baseUrl}user/get_connection_duration?period_value=${period_value}`;

    if(period_type != null)
        url += `&period_type=${period_type}`;
    if(filter_type != null)
        url += `&filter_type=${filter_type}`;
    if(filter_value != null)
        url += `&filter_value=${encodeURIComponent(filter_value)}`;

    const response = await fetch(url);
    const getdurationInfo = await response.json();
    if(response.ok)
    {
        return {
            total_duration: getdurationInfo.total_duration,
            worktime_duration: getdurationInfo.worktime_duration,
            offhour_duration: getdurationInfo.offhour_duration,
            internal_count: getdurationInfo.internal_count,
            external_count: getdurationInfo.external_count,
        };
    }
    return 0;
}

export async function getTopUserConnectionDuration(period_type=null, period_value) {
    let url = `${window.baseUrl}user/get_top_user_duration?period_value=${period_value}`;
    if(period_type != null)
        url += `&period_type=${period_type}`;

    const response = await fetch(url);
    const getdurationInfo = await response.json();
    if(response.ok)
    {
        return getdurationInfo;
    }
    return 0;
}

export async function getTopDepartmentConnectionDuration(period_type=null, period_value) {
    let ulr = `${window.baseUrl}user/get_top_department_duration?period_value=${period_value}`;
    if(period_type != null)
        ulr += `&period_type=${period_type}`;

    const response = await fetch(ulr);
    const getdurationInfo = await response.json();
    if(response.ok)
    {
        return getdurationInfo;
    }
    return 0;
}

export async function getTopCompanyConnectionDuration(period_type=null, period_value) {    
    let url = `${window.baseUrl}user/get_top_company_duration?period_value=${period_value}`;
    if(period_type != null)
        url += `&period_type=${period_type}`;

    const response = await fetch(url);
    const getdurationInfo = await response.json();
    if(response.ok)
    {
        return getdurationInfo;
    }
    return 0;
}

function parseDurationToSeconds(durationStr) {
    if (durationStr == "0") return 0;

    const [hms, fractioanl = '0'] = durationStr.split('.');
    const [hours, minutes, seconds] = hms.split(':').map(Number);
    const fractionalSeconds = parseFloat(`0.${fractioanl}`);
    return (hours * 3600) + (minutes * 60) + seconds + fractionalSeconds;
}