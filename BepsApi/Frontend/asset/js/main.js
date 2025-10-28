console.log("search params: ", window.location.search);
window.onload = checkLoginStatus;    // Check login status when page is loaded

document.addEventListener("DOMContentLoaded", () => {

    const loggedInUser = sessionStorage.getItem("username");
    if(loggedInUser)
        document.getElementById("user_name").textContent = loggedInUser;
    else
        window.location.href = "login.html";

    const userInfo = JSON.parse(sessionStorage.getItem("loggedInUser"));
    const user_role = userInfo && userInfo.user ? userInfo.user.role_id : null;

    const buttons = document.querySelectorAll(".nav-button");
    const contentArea = document.getElementById("content-area");

    if(user_role != 2 && user_role != 999) { //기획 요청으로 숨김(2025-07-14) 개발자만 표시
    //(user_role == 5 || user_role == 6 || user_role == null) { // 일반사용자 또는 외부사용자
        document.getElementById("contents-button").style.display = "none"; // 학습 버튼 숨김
        //document.getElementById("opinion-button").style.display = "none"; // 의견 버튼 숨김
    }

    // 담당자 관리 버튼은 role_id가 1, 2, 999일 때만 표시
    console.log("User role:", user_role);
    if(!(user_role === 1 || user_role === 2 || user_role === 999)) {
        console.log("Hiding manager admin button for role:", user_role);
        document.getElementById("manager-admin-button").style.display = "none";
    } else {
        console.log("Showing manager admin button for role:", user_role);
    }

    if(!(user_role === 1 || user_role ===2 || user_role === 999)){ // 통합관리자 또는 개발관리자가 아닐 때
     document.getElementById("learning-admin-button").style.display = "none"; // 관리자 버튼 숨김
    }

    const params = new URLSearchParams(window.location.search);
    console.log("search params: ", window.location.search);
    const content = params.get("content");
    if(content === "opinion") {
        buttons.forEach(button =>{
            button.classList.remove("active");
            if(button.id == "opinion-button") 
                button.classList.add("active");
        }); 
        loadContent("opinion.html");
    }
    else
        loadContent("progress_user.html");

    buttons.forEach(button => {
        button.addEventListener("click", () => {
            // 모든 버튼에서 'active' 클래스 제거
            buttons.forEach(btn => btn.classList.remove("active"));

            // 클릭한 버튼에 'active' 클래스 추가
            button.classList.add("active");
            
            loadContent(button.dataset.content);
        });
    });

    const logoutButton = document.getElementById("logout-button");
    if(logoutButton)
    {
        logoutButton.addEventListener("click", logout);
    } 
    
    const managerAdminButton = document.getElementById("manager-admin-button");
    if(managerAdminButton) {
        managerAdminButton.addEventListener("click", openManagerAdmin);
        console.log("Manager admin button found and event listener added");
    } else {
        console.error("Manager admin button not found!");
    }
});

function openManagerAdmin() {
    console.log("Opening manager admin page");
    // Remove active class from all nav buttons
    const navButtons = document.querySelectorAll(".nav-button");
    navButtons.forEach(btn => btn.classList.remove("active"));
    
    // Add active class to manager admin button
    const managerAdminButton = document.getElementById("manager-admin-button");
    if(managerAdminButton) {
        managerAdminButton.classList.add("active");
    }
    
    // Load manager admin page in the content frame
    loadContent("manager_admin.html");
}

async function logout(){
    try{
        
        // 로그아웃 요청
        const url = `${baseUrl}user/logout`;
        const response = await fetch(url, {
            method: "GET",
            credentials: "include",
            headers: {
                "Content-Type": "application/json",
            },
        });

        // sessionStorage 초기화
        sessionStorage.removeItem("username");
        sessionStorage.removeItem("loggedInUser");
        sessionStorage.removeItem("isLoggedIn");

        // 쿠키 삭제
        document.cookie.split(";").forEach(cookie => {
            document.cookie = 
            cookie.replace(/^ +/, "").replace(/=.*/, `=;expires=Thu, 01 Jun 1970 00:00:00 GMP; path=/`);
        });

        // //descope SDK 로그아웃
        // const sdk = Descope({
        //     projectId: 'P2wON5fy1K6kyia269VpeIzYP8oP',
        //     baseUrl: 'https://api.descope.com',
        //     persistTokens: true,
        //     autoRefresh: true,
        // });
        // await sdk.logout();

        localStorage.clear(); // localStorage 초기화
        sessionStorage.clear(); // sessionStorage 초기화

        // 로그인 페이지로 이동
        window.location.href = "login.html";

    }catch(error){
        console.error(error);
    }
}


function loadContent(page) {
    if(page != undefined){
    
        fetch(page)
        .then(response => response.text())
        .then(data => {
            //document.getElementById("content-frame").src = page;
            const iframe = document.getElementById("content-frame");
            iframe.style.height = window.innerHeight + 'px';
            iframe.src = page;
            console.log("page: ", page);
            iframe.onload = () => {
                 if (window.location.search) {
                     history.replaceState(null, "", "main.html"); // URL에서 content 파라미터 제거
                 }
            }
        })
        .catch(error => {
            contentArea.innerHTML = "페이지를 불러오는 중 오류가 발생했습니다.";
            console.error(error);
        });
    }
    else
    {
        document.getElementById("content-frame").src = "about:blank";
    }
}
