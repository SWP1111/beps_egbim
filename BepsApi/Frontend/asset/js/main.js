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

    // 컨텐츠/담당자 관리 버튼은 role_id가 1, 2, 999일 때만 표시
    console.log("User role:", user_role);
    if(!(user_role === 1 || user_role === 2 || user_role === 999)) {
        console.log("Hiding content manager admin button for role:", user_role);
        const contentManagerAdminButton = document.getElementById("content-manager-admin-button");
        if(contentManagerAdminButton) {
            contentManagerAdminButton.style.display = "none";
        }
    } else {
        console.log("Showing content manager admin button for role:", user_role);
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

    const contentManagerAdminButton = document.getElementById("content-manager-admin-button");
    if(contentManagerAdminButton) {
        contentManagerAdminButton.addEventListener("click", openContentManagerAdmin);
        console.log("Content Manager Admin button found and event listener added");
    } else {
        console.error("Content Manager Admin button not found!");
    }
});

function openContentManagerAdmin() {
    console.log("Opening Content Manager Admin page");
    // Remove active class from all nav buttons
    const navButtons = document.querySelectorAll(".nav-button");
    navButtons.forEach(btn => btn.classList.remove("active"));

    // Add active class to content manager admin button
    const contentManagerAdminButton = document.getElementById("content-manager-admin-button");
    if(contentManagerAdminButton) {
        contentManagerAdminButton.classList.add("active");
    }

    // Load unified content manager admin page in the content frame
    loadContent("content_manager_admin.html");
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
    console.log("loadContent called with page:", page);
    if(page != undefined){

        fetch(page)
        .then(response => {
            console.log("Fetch response for", page, "status:", response.status);
            if (!response.ok) {
                throw new Error(`HTTP ${response.status}: ${response.statusText}`);
            }
            return response.text();
        })
        .then(data => {
            console.log("Fetch succeeded, loading page:", page);
            const iframe = document.getElementById("content-frame");
            iframe.style.height = window.innerHeight + 'px';
            iframe.src = page;
            console.log("iframe.src set to:", page);
            iframe.onload = () => {
                console.log("iframe loaded successfully:", page);
                if (window.location.search) {
                    history.replaceState(null, "", "main.html"); // URL에서 content 파라미터 제거
                }
            }
            iframe.onerror = () => {
                console.error("iframe failed to load:", page);
                alert("페이지 로드 실패: " + page);
            }
        })
        .catch(error => {
            console.error("Error loading page:", page, error);
            alert("페이지를 불러오는 중 오류가 발생했습니다: " + page + "\n" + error.message);
            const contentAreaEl = document.getElementById("content-area");
            if (contentAreaEl) {
                contentAreaEl.innerHTML = "페이지를 불러오는 중 오류가 발생했습니다.";
            }
        });
    }
    else
    {
        console.log("page is undefined, setting iframe to about:blank");
        document.getElementById("content-frame").src = "about:blank";
    }
}
