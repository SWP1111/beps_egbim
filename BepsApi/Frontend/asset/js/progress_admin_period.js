import { setOnSelectCallback, SELECTION_TYPE } from "./progress_admin_search.js";

let onSelectPeriodCallback = null;
let onSelectFilterCallback = null;

let selectedDispfilter = '';
let selectedDispPeriod = '';
export function setOnSelectPeriodCallback(callback) {
    onSelectPeriodCallback = callback;
}

export function setOnSelectFilterCallback(callback) {
    onSelectFilterCallback = callback;
}

export function initPeriod()
{
    const currentYear = new Date().getFullYear();
    const yearStart = `${new Date().getFullYear()}-01-01`;
    let today = new Date().toLocaleDateString('sv-SE');

    let period_type = "year";
    let period_value = `${currentYear}`;
    const selectedPeriod = document.getElementById("selected-period");
     if (period_type == "year")
        selectedDispPeriod = `${period_value}년`;
    else if (period_type == "half")
        selectedDispPeriod = `${period_value.replace("-H1", " 상반기").replace("-H2", " 하반기")}`;
    else if (period_type == "quarter")
        selectedDispPeriod = `${period_value.replace("-Q1", " 1분기").replace("-Q2", " 2분기").replace("-Q3", " 3분기").replace("-Q4", " 4분기")}`;
    else if (period_type == "day")
        selectedDispPeriod = `${period_value.replace("~", " ~ ").replace(/-/g, ".")}`;

    //적용
    const applyBtn = document.getElementById("apply-button");
    applyBtn.addEventListener("click", (e) => {
        
        sessionStorage.setItem("period_type", period_type);
        sessionStorage.setItem("period_value", period_value);
        
        if (period_type == "year")
            selectedDispPeriod = `${period_value}년`;
        else if (period_type == "half")
            selectedDispPeriod = `${period_value.replace("-H1", " 상반기").replace("-H2", " 하반기")}`;
        else if (period_type == "quarter")
            selectedDispPeriod = `${period_value.replace("-Q1", " 1분기").replace("-Q2", " 2분기").replace("-Q3", " 3분기").replace("-Q4", " 4분기")}`;
        else if (period_type == "day")
            selectedDispPeriod = `${period_value.replace("~", " ~ ").replace(/-/g, ".")}`;
        selectedPeriod.textContent = `${selectedDispfilter} (${selectedDispPeriod})`;

        onSelectPeriodCallback();

    });

    // 기간 선택_날짜 지정
    const fp = flatpickr("#date-range", {
        mode: "range",
        dateFormat: "Y-m-d",
        locale: "ko",
        //clickOpens: false, // 💥 input 클릭 시 달력 열리지 않도록       
        // plugins: [        // 💥 shortcut-buttons-flatpickr 이용해서 플러그인 추가: Today 버튼 추가
        //     ShortcutButtonsPlugin({
        //     button: [    
        //         {
        //             label: "Today"
        //         }
        //     ],
        //     onClick: (index, fp) => {
        //         let date;
        //         switch (index) {
        //             case 0:
        //                 date = new Date();
        //                 break;
        //         }
        //         fp.setDate(date);
        //     }
        //     })
        // ],
        onClose: function(selectedDates, dateStr, instance) {
            if (selectedDates.length === 2) {
            const format = (date) => {
                const yy = String(date.getFullYear()).slice(-2);
                const mm = String(date.getMonth() + 1).padStart(2, '0');
                const dd = String(date.getDate()).padStart(2, '0');
                return `${yy}-${mm}-${dd}`;
            };

            // period_value용: YYYY-MM-DD
            const fullFormat = (date) => {
                const yyyy = date.getFullYear();
                const mm = String(date.getMonth() + 1).padStart(2, '0');
                const dd = String(date.getDate()).padStart(2, '0');
                return `${yyyy}-${mm}-${dd}`;
            };

            instance.input.value = `${format(selectedDates[0])} ~ ${format(selectedDates[1])}`;

            period_type = "day";
            period_value = `${fullFormat(selectedDates[0])}~${fullFormat(selectedDates[1])}`;

            }
        }
    });

    // 버튼 클릭 시 달력 열기
    document.getElementById("calendar-btn").addEventListener("click", () => {
    fp.open();
    });

    // 기간 선택 드롭다운 동작_연간
    const dropdownBtnYear = document.getElementById("year");
    const dropdownMenuYear = document.getElementById("year-list");
    const dropdownLabelYear = document.getElementById("year-label");
    const btnYear = document.getElementById("year-button");

    for (let year = 2025; year <= currentYear; year++) {
        const div = document.createElement("div");
        const dropdownItem = document.createElement("button");
        dropdownItem.className = "dropdown-item";
        dropdownItem.textContent = `${year}`;
        div.appendChild(dropdownItem);
        dropdownMenuYear.appendChild(div);
    }
    
    dropdownLabelYear.textContent = `${currentYear}년도`;
    btnYear.classList.add("active");
    period_type = "year";
    period_value = dropdownLabelYear.textContent.replace("년도", "").trim();
    selectedPeriod.textContent = `전체 (${period_value}년)`;
    const startDate = new Date(parseInt(period_value), 0, 1); //1월 1일
    const endDate = new Date(parseInt(period_value), 11, 31);   //12월 31일
    fp.setDate([startDate, endDate]);
    fp.input.value = `${period_value.substring(2)}-01-01 ~ ${period_value.substring(2)}-12-31`;

    sessionStorage.setItem("period_type", period_type);
    sessionStorage.setItem("period_value", period_value);

    btnYear.addEventListener("click", (e) => {
        btnYear.classList.add("active");

        period_type = "year";
        period_value = dropdownLabelYear.textContent.replace("년도","").trim();

        const startDate = new Date(parseInt(period_value), 0, 1);   // 1월 1일
        const endDate = new Date(parseInt(period_value), 11, 31);   // 12월 31일
        fp.setDate([startDate, endDate]);
        fp.input.value = `${period_value.substring(2)}-01-01 ~ ${period_value.substring(2)}-12-31`;

        dropdownBtn.classList.remove("active");
        dropdownLabel.textContent = "반기";
        dropdownBtnQuarter.classList.remove("active");
        dropdownLabelQuarter.textContent = "분기";
    });

    dropdownBtnYear.addEventListener("click", (e) => {
        dropdownMenuYear.classList.toggle("show");
    });

    dropdownMenuYear.addEventListener("click", (e) => {   
        if(e.target.classList.contains("dropdown-item")) {
        dropdownLabelYear.textContent = `${e.target.textContent}년도`;
        dropdownMenuYear.classList.remove("show");
        } 
    });

    // 기간 선택 드롭다운 동작_반기
    const dropdownBtn = document.getElementById("half-year");
    const dropdownMenu = document.getElementById("half-year-list");
    const dropdownLabel = document.getElementById("half-year-label");

    dropdownBtn.addEventListener("click", (e) => {
        dropdownMenu.classList.toggle("show");
    });

    dropdownMenu.addEventListener("click", (e) => {
        if(e.target.classList.contains("dropdown-item")) {
            dropdownLabel.textContent = e.target.textContent;
            dropdownMenu.classList.remove("show");
            dropdownBtn.classList.add("active");

            const selectedYear = dropdownLabelYear.textContent.replace("년도","").trim();

            period_type = "half";
            period_value = selectedYear;

            if(dropdownLabel.textContent === "상반기")
            {
                period_value += '-H1';

                const startDate = new Date(parseInt(selectedYear), 0, 1);   // 1월 1일
                const endDate = new Date(parseInt(selectedYear), 5, 30);    // 6월 30일
                fp.setDate([startDate, endDate]);
                fp.input.value = `${selectedYear.substring(2)}-01-01 ~ ${selectedYear.substring(2)}-06-30`;
            }
            else if(dropdownLabel.textContent === "하반기")
            {
                period_value += '-H2';

                const startDate = new Date(parseInt(selectedYear), 6, 1);   // 7월 1일
                const endDate = new Date(parseInt(selectedYear), 11, 31);   // 12월 31일
                fp.setDate([startDate, endDate]);
                fp.input.value = `${selectedYear.substring(2)}-07-01 ~ ${selectedYear.substring(2)}-12-31`;
            }

            dropdownBtnQuarter.classList.remove("active");
            dropdownLabelQuarter.textContent = "분기";
            btnYear.classList.remove("active");
        }
    });

    // 기간 선택 드롭다운 동작_분기
    const dropdownBtnQuarter = document.getElementById("quarter");
    const dropdownMenuQuarter = document.getElementById("quarter-list");
    const dropdownLabelQuarter = document.getElementById("quarter-label");

    dropdownBtnQuarter.addEventListener("click", (e) => {
        dropdownMenuQuarter.classList.toggle("show");
    });

    dropdownMenuQuarter.addEventListener("click", (e) => {
        if(e.target.classList.contains("dropdown-item")) {
            dropdownLabelQuarter.textContent = e.target.textContent;
            dropdownMenuQuarter.classList.remove("show");
            dropdownBtnQuarter.classList.add("active");

            const selectedYear = dropdownLabelYear.textContent.replace("년도","").trim();

            period_type = "quarter";
            period_value = selectedYear;

            if(dropdownLabelQuarter.textContent === "1분기") {
                period_value += '-Q1';

                const startDate = new Date(parseInt(selectedYear), 0, 1);   // 1월 1일
                const endDate = new Date(parseInt(selectedYear), 2, 31);   // 3월 31일
                fp.setDate([startDate, endDate]);   
                fp.input.value = `${selectedYear.substring(2)}-01-01 ~ ${selectedYear.substring(2)}-03-31`;
            }
            else if(dropdownLabelQuarter.textContent === "2분기") {
                period_value += '-Q2';

                const startDate = new Date(parseInt(selectedYear), 3, 1);   // 4월 1일
                const endDate = new Date(parseInt(selectedYear), 5, 30);   // 6월 30일
                fp.setDate([startDate, endDate]);
                fp.input.value = `${selectedYear.substring(2)}-04-01 ~ ${selectedYear.substring(2)}-06-30`;
            }
            else if(dropdownLabelQuarter.textContent === "3분기") {
                period_value += '-Q3';

                const startDate = new Date(parseInt(selectedYear), 6, 1);   // 7월 1일
                const endDate = new Date(parseInt(selectedYear), 8, 30);   // 9월 30일
                fp.setDate([startDate, endDate]);
                fp.input.value = `${selectedYear.substring(2)}-07-01 ~ ${selectedYear.substring(2)}-09-30`;
            }
            else if(dropdownLabelQuarter.textContent === "4분기") {
                period_value += '-Q4';

                const startDate = new Date(parseInt(selectedYear), 9, 1);   // 10월 1일
                const endDate = new Date(parseInt(selectedYear), 11, 31);   // 12월 31일
                fp.setDate([startDate, endDate]);
                fp.input.value = `${selectedYear.substring(2)}-10-01 ~ ${selectedYear.substring(2)}-12-31`;
            }

            dropdownBtn.classList.remove("active");
            dropdownLabel.textContent = "반기";
            btnYear.classList.remove("active");
        }
    });

    // 클릭 이벤트
    document.addEventListener("click", (event) => {
        if(!dropdownBtn.contains(event.target) && !dropdownMenu.contains(event.target)) {
            dropdownMenu.classList.remove("show");
        }
        if(!dropdownBtnQuarter.contains(event.target) && !dropdownMenuQuarter.contains(event.target)) {
            dropdownMenuQuarter.classList.remove("show");
        }
        if(!dropdownBtnYear.contains(event.target) && !dropdownMenuYear.contains(event.target)) {
            dropdownMenuYear.classList.remove("show");
        }
    });
        
    // 키보드 입력 이벤트
    document.addEventListener("keydown", (event) => {
        if(event.key === "Escape") {
            dropdownMenu.classList.remove("show");
            dropdownMenuQuarter.classList.remove("show");
            dropdownMenuYear.classList.remove("show");
        }
    });


    setOnSelectCallback(({type, company, department, user}) => {
        switch(type){
            case SELECTION_TYPE.ALL:
                selectedDispfilter = "전체";
                selectedPeriod.textContent = `전체 (${selectedDispPeriod})`;
                break;
            case SELECTION_TYPE.COMPANY:
                selectedDispfilter = `${company}`;
                selectedPeriod.textContent = `${company} (${selectedDispPeriod})`;
                break;
            case SELECTION_TYPE.DEPARTMENT:
                selectedDispfilter = `${department}`;
                selectedPeriod.textContent = `${department} (${selectedDispPeriod})`;
                break;
            case SELECTION_TYPE.USER:
                selectedDispfilter = `${user.userName} ${user.position}`;
                selectedPeriod.textContent = `${user.userName} ${user.position} (${selectedDispPeriod})`;
                break;
            default:
                break;
        }

        onSelectFilterCallback({
            type: type.toLowerCase(),
            company: company,
            department: department,
            user: user
        });
  });

}

