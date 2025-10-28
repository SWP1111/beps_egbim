async function checkLoginStatus() {
    try{
        const url = `${baseUrl}user/token_check`;
        const response = await fetch(url, {
            method: "GET",
            credentials: "include",
        })

        if(response.ok){
            const data = await response.json();
            console.log("checkLoginStatus: ", data);
            sessionStorage.setItem("username", data.user);    

            const params = new URLSearchParams(window.location.search);

            if(window.location.pathname.endsWith("main.html") == false){      
                const id = params.get("id");
                const token = params.get("token");
                if(id && token){
                    console.log("Redirecting to main.html with id and token");
                    window.location.href = "main.html?content=opinion";
                }
                else{
                    console.log("Redirecting to main.html without id and token");
                    window.location.href = "main.html";     
                }
            }
        }
        else
        {
            if(window.location.pathname.endsWith("login.html") == false)
                window.location.href = "login.html";
        }
        
    }catch(error){
        console.error(error);
        if(window.location.pathname.endsWith("login.html") == false)
            window.location.href = "login.html";
    }
}