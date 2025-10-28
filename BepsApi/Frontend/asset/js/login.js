console.log("login.js");
window.onload = checkLoginStatus;  // Check login status when page is loaded

document.addEventListener('DOMContentLoaded', async() => {
    const params = new URLSearchParams(window.location.search);
    const id = params.get('id');
    const token = params.get('token');

    console.log("search params: ", window.location.search);
    console.log("id: ", id);
    console.log("token: ", token);
    if(id && token){
        const response = await fetch(`${baseUrl}user/token_check`, {
            method: 'GET',
            headers: {
                'Authorization': `Bearer ${token}`
            }
        });
        
        if(response.ok)
        {
            console.log("Login From BEPs App: ", response);
            let responseUserInfo = await GetUserInfo(id);
            console.log("responseUserInfo: ", responseUserInfo);
            
            if(responseUserInfo.success)
            {
                localStorage.setItem("isLoggedIn", "true");
                localStorage.setItem("username", id);

                const userInfo = responseUserInfo.data;
                localStorage.setItem("loggedInUser", JSON.stringify(userInfo));

                window.location.href = "main.html?content=opinion";
            }

            return;
        }
    }

    const loginButton = document.getElementById('login-button');    // Get login button
    if(loginButton)
    {
        loginButton.addEventListener('click', handleLogin);    // Add event listener to login button        
    }

    const inputUser = document.getElementById('username');
    const inputPassword = document.getElementById('password');
    if(inputUser)
    {
        inputUser.addEventListener('keydown', function(event){
            if(event.key === "Tab")
            {
                event.preventDefault();
                if(inputPassword) inputPassword.focus();
            }
        });
    }
    if(inputPassword)
    {
        inputPassword.addEventListener('keypress', function(event){
            if(event.key === "Enter")
            {
                event.preventDefault();
                handleLogin(event);
            }
        });
    }

});

function encodeBase64(value) {
    return btoa(String.fromCharCode(...new TextEncoder().encode(value)));
}

function decodeBase64String(encodedString) {
    try {
        // Base64 문자열을 탭(`\t`)으로 분리
        const parts = encodedString.split("\t");

        // 각 부분을 개별적으로 디코딩
        const decodedParts = parts.map(part => {
            try {
                return new TextDecoder().decode(Uint8Array.from(atob(part), c => c.charCodeAt(0)));
            } catch (e) {
                console.error(`❌ Base64 디코딩 오류: ${part}`, e);
                return part; // 디코딩 실패 시 원본 값 반환
            }
        });

        return decodedParts;
    } catch (error) {
        console.error("❌ 전체 Base64 디코딩 오류:", error);
        return null;
    }
}

async function handleLogin(event) {
    event.preventDefault();    // Prevent default form submission

    const username = document.getElementById('username').value;    // Get username
    const password = document.getElementById('password').value;    // Get password

    Login(username, password);    // login
}

async function Login(username, password) {
    const ulrLisence = "networklicense.hanmaceng.co.kr";
    const ulrLisense2 = "networklicense2.hanmaceng.co.kr";
    
    let url = `http://${ulrLisence}/NetworkLicense/sys/controller/network_controller.php`;    // API URL

    const ip = getClientIP();

    let params = "";
    params += `ActionMode=CheckLicense`;
    params += `&HardDisk=`;
    params += `&Application=${encodeBase64("BEPs")}`;
    params += `&UserID=${encodeBase64(username)}`;
    params += `&UserPassword=${encodeBase64(password)}`;
    params += `&QueryTime=`;
    params += `&LocalAddress=`;
    params += `&InstrumentOfPeriod=0`;

    try{

        let response = await sendERPLoginRequest(url, params);
        if(!response.success)
        {
            url = `http://${ulrLisense2}/networklicense/sys/controller/network_controller.php`;
            response = await sendERPLoginRequest(url, params);
        }
        
        if(response.success)
        {
           console.log("ERPLogin response: ", response);
           let responseUserInfo = await GetUserInfo(username);
           console.log("responseUserInfo: ", responseUserInfo);
           
           if(responseUserInfo.success)
           {
                localStorage.setItem("isLoggedIn", "true");
                localStorage.setItem("username", username);

                const userInfo = responseUserInfo.data;
                localStorage.setItem("loggedInUser", JSON.stringify(userInfo));

                window.location.href = "main.html";
           }

            //사용자 추가 또는 업데이트
            // console.log("사용자 추가 Id:", username, " Company: ", response.data.company, " Department: ", response.data.department, " Position: ", response.position, " Name: ", response.data.username);
            // const insertReponse = await InsertUser(username,response.data.company,response.data.department,response.data.position,response.data.username);
            // console.log("insertReponse: ", insertReponse);
            // if(insertReponse.success)
            // {
            //     responseUserInfo = await GetUserInfo(username);
            //     if(responseUserInfo.success)
            //     {            
            //             localStorage.setItem("isLoggedIn", "true");
            //             localStorage.setItem("username", username);

            //             const userInfo = responseUserInfo.data;
            //             localStorage.setItem("loggedInUser", JSON.stringify(userInfo));

            //             window.location.href = "main.html";
            //             console.log("로그인 최종 성공");
            //     }
            //     else
            //     {
            //         alert(responseUserInfo.message);
            //     }
            // }
            // else
            // {
            //     alert(insertReponse.message);
            // }      
        }
        else
        {
            alert(response.message);
        }

    }catch(error){
        console.error(error);
    }    
}

//EPR 로그인을 API를 통해서 요청청. CROS 정책으로 인해 로그인 안 된다고 하던데 확인 필요
async function sendERPLoginRequest(url, params) {
    try{
        let apiUrl = `${baseUrl}user/erp_login`;
        const response = await fetch(apiUrl, {
            method: "POST",
            headers: {
                "Content-Type": "application/json"
            },
            body: JSON.stringify({
                targetUrl: url,
                params: params
            })
        });
         
        if((await response).ok)
        {
            const responseJson = await response.json();
            console.log("sendERPLoginRequest 서버 응답(Json): ", responseJson);
    
            if(!responseJson.data) return {success: false, message: "ERP 로그인 실패 사용자 정보 없음"};

            const decodedText = decodeBase64String(responseJson.data);
            console.log("sendERPLoginRequest decodedText: ", decodedText);

            return {success: true, data: {
                company: decodedText[0],
                program: decodedText[1],
                userid: decodedText[2],
                username: decodedText[3],
                department: decodedText[4],
                position: decodedText[5]
            }};
        }
        else
        {
            return {success: false, message: "ERP 로그인 실패"};
        }

    }catch(error){
        console.error(error);
        return {success: false, message: "네트워크 오류"};
    }
}

// 서버에서 사용자 조회
async function GetUserInfo(username) {
    try{
        url = `${baseUrl}user/user`;
        const response = await fetch(url, {
            method: "POST",
            headers: {
                "Content-Type": "application/json"
            },
            body: JSON.stringify({
                id: username
            })
        });

        const responseJson = await response.json();
        console.log("GetUserInfo 서버 응답: ", responseJson);

        if((await response).ok)
        {
            return {success: true, data: responseJson}
        }
        else
        {
            return {success: false, message: "사용자 없음"};
        }
    }
    catch(error){
        console.error(error);
    }
}

async function InsertUser(id, company, department, position, name)
{
    try{

        url = `${baseUrl}user/update_user`;
        const response = await fetch(url, {
            method: "POST",
            headers: {
                "Content-Type": "application/json"
            },
            body: JSON.stringify({
                id: id,
                company : company,
                department : department,
                position : position,
                name : name
            })
        });

        const responseText = await response.text();
        console.log("InsertUser 서버 응답: ", responseText);

        if((await response).ok)
        {
            return {success: true, data: responseText}
        }
        else
        {
            return {success: false, message: "사용자 추가 실패"};
        }

    }catch(error){
        console.error(error);
    }
}

async function getClientIP() {
    try{
        const response = await fetch("https://api.ipify.org?format=json");
        const data = await response.json();
        console.log(data);
        return data.ip;
    }catch(error){
        console.error(error);
        return "unknown";
    }
}