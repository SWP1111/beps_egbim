const dayIconContainer = document.getElementById("day-icon-container");
const chartContainer = document.getElementById("chart-container");

const summaryCalendarButton = document.getElementById("summary-calendar-button");

const myAvgLearningMinutes = document.querySelectorAll(".my-avg-learning-minutes");
const percentChangeValue = document.getElementById("percent-change-value");
const percentChangeText = document.getElementById("percent-change-text");
const allAvgLearningMinutes = document.getElementById("all-avg-learning-minutes");
const comparePercentValue = document.getElementById("compare-percent-value");
const comparePercentText = document.getElementById("compare-percent-text");

const [start, end] = getWeekRange(new Date());


let todayLearningTime = 0; // 오늘 학습 시간
let allUserAvgLearningTime = 0; // 전체 사용자 평균 학습 시간

const fpSummary = flatpickr("#summary-date", {
    mode: "range",
    dateFormat: "y-m-d",
    locale: "ko",
    defaultDate: [start, end],  // ✅ 이번 주 기본 선택
    onChange: function(selectedDates, dateStr, instance) {
        if (selectedDates.length === 1) {
            const [start, end] = getWeekRange(selectedDates[0]);

            // 프로그램적으로 range 선택
            instance.setDate([start, end], true);
             // 달력 닫기!
            instance.close();

            (async() => {
                const learningData = await getLearningTimeByWeek(start, end);
    
                // 지난 주 날짜 계산 (원본 날짜를 변경하지 않도록 새로운 Date 객체 생성)
                const lastWeekStart = new Date(start);
                lastWeekStart.setDate(start.getDate() - 7);
                const lastWeekEnd = new Date(end);
                lastWeekEnd.setDate(end.getDate() - 7);
                const lastLearningData = await getLearningTimeByWeek(lastWeekStart, lastWeekEnd);    // 지난 주간의 학습 시간 데이터

                await configureLearningDays(start, end, learningData);
                await configureLearningChart(learningData);
            })();
        }
    }
});

(async() =>
{
  // 오늘 날짜를 YYYY-MM-DD 형식으로 생성
    const today = new Date();
    const todayStr = formatDate(today);
    
    await configureContinuousLearningDays(todayStr);

    // 학습 데이터를 한 번만 가져와서 여러 함수에서 사용
    const learningData = await getLearningTimeByWeek(start, end);   //선택한 주간의 학습 시간 데이터
    
    // 지난 주 날짜 계산 (원본 날짜를 변경하지 않도록 새로운 Date 객체 생성)
    const lastWeekStart = new Date(start);
    lastWeekStart.setDate(start.getDate() - 7);
    const lastWeekEnd = new Date(end);
    lastWeekEnd.setDate(end.getDate() - 7);
    const lastLearningData = await getLearningTimeByWeek(lastWeekStart, lastWeekEnd);    // 지난 주간의 학습 시간 데이터
    
    await configureLearningDays(start, end, learningData);
    await configureLearningChart(learningData);
    updateLearningSummary(lastLearningData, learningData, start, end);

    setInterval(async() => {
        try {
            [todayLearningTime, allUserAvgLearningTime] = await getUserLearningTime();
            var start_date = fpSummary.selectedDates[0];
            var end_date = fpSummary.selectedDates[1];
            if((todayLearningTime || allUserAvgLearningTime) && start_date <= today && end_date >= today) {
                // 오늘 날짜가 선택된 주간 범위에 포함되어 있다면
                const todayData = learningData.user_daily_total.find(item => item.date === todayStr);
                if (todayData) {
                    todayData.total_duration_minutes = todayLearningTime;
                } else {
                    learningData.user_daily_total.push({
                        date: todayStr,
                        total_duration_minutes: todayLearningTime
                    });
                }

                const todayDatabyAll = learningData.all_users_daily_average.find(item => item.date === todayStr);
                if (todayDatabyAll) {
                    todayDatabyAll.avg_duration_minutes = allUserAvgLearningTime;
                } else {
                    learningData.all_users_daily_average.push({
                        date: todayStr,
                        avg_duration_minutes: allUserAvgLearningTime
                    });
                }

                configureContinuousLearningDays(todayStr);
                configureLearningDays(start_date, end_date, learningData);
                configureLearningChart(learningData);
                updateLearningSummary(lastLearningData, learningData, start, end);
            }
        }
        catch(e)
        {
            console.error("Error refreshing learning time:", e);
        }
    }, 1800000); // 30분마다 학습 시간 새로고침

})();

summaryCalendarButton.addEventListener("click", () => {
    fpSummary.open();
});

/**
 * 연속 학습일 구성
 * @param {string} referenceData 
 */
async function configureContinuousLearningDays(referenceData) {
    try {
        const response = await fetch(`${window.baseUrl}leaning/continuous_learning_days?reference_date=${referenceData}`);
        const data = await response.json();
        
        if (response.ok) {
            // 성공시 연속 학습일 표시 업데이트
            const continueLearningDaysElement = document.getElementById("continue-learning-days");
            if (continueLearningDaysElement) {
                continueLearningDaysElement.textContent = `${data.continuous_days || 0}일`;
            }
            console.log(`Continuous learning days: ${data.continuous_days} (reference: ${referenceData})`);
        } else {
            console.error("Error fetching continuous learning days:", data.error);
            // 에러시 기본값으로 0일 표시
            const continueLearningDaysElement = document.getElementById("continue-learning-days");
            if (continueLearningDaysElement) {
                continueLearningDaysElement.textContent = "0일";
            }
        }
    } catch (e) {
        console.error("Error in configureContinuousLearningDays:", e);
        // 에러시 기본값으로 0일 표시
        const continueLearningDaysElement = document.getElementById("continue-learning-days");
        if (continueLearningDaysElement) {
            continueLearningDaysElement.textContent = "0일";
        }
    }
}

/**
 * 주간 전체 학습 평균과 사용자 학습 시간을 가져오는 함수
 * @param {Date} start_date - 시작 날짜
 * @param {Date} end_date - 종료 날짜
 * @returns {Promise<Object>} - 학습 데이터
 */
async function getLearningTimeByWeek(start_date, end_date) {
    try {
        
        const startDateStr = formatDate(start_date);
        const endDateStr = formatDate(end_date);

        const response = await fetch(`${window.baseUrl}leaning/learning_time_by_date_range?start_date=${startDateStr}&end_date=${endDateStr}`);
        const data = await response.json();

        if(response.ok) {
            return data;
        }
    }
    catch(e) {
        console.error("Error fetching learning time by week:", e);
    }
    return [];
}


/**
 * 사용자의 학습 요일 아이콘 구성
 */
async function configureLearningDays(start, end, learningData)
{
    const today = new Date();
    today.setHours(0, 0, 0, 0); // 시간 초기화

    // 오늘 날짜를 YYYY-MM-DD 형식으로 생성
    const todayStr = formatDate(today);

    let todayIndex = null;
    if (today >= start && today <= end) {
        const day = today.getDay();
        todayIndex = day === 0 ? 6 : day - 1; // 일요일(0)이면 6, 그 외는 (day - 1)
    }

    // 사용자의 학습한 날짜들을 Set으로 저장
    const learningDates = new Set();
    if (learningData && learningData.user_daily_total) {
        learningData.user_daily_total.forEach(item => {
            if (item.total_duration_minutes > 0) {
                learningDates.add(item.date);
            }
        });
    }

    const days = [
        { day: "월", active: false },
        { day: "화", active: false },
        { day: "수", active: false },
        { day: "목", active: false },
        { day: "금", active: false },
        { day: "토", active: false },
        { day: "일", active: false }
    ];

    // 주간 날짜별로 학습 여부 확인하여 active 설정
    console.log('Week range:', start, 'to', end);
    console.log('Learning dates found:', Array.from(learningDates));
    for (let i = 0; i < 7; i++) {
        const currentDate = new Date(start);
        currentDate.setDate(start.getDate() + i);
        // 로컬 날짜 문자열 사용 (UTC 변환 방지)
        const dateStr = formatDate(currentDate);
        
        console.log(`Day ${i} (${['월','화','수','목','금','토','일'][i]}): ${dateStr}, has learning: ${learningDates.has(dateStr)}`);
        
        if (learningDates.has(dateStr)) {
            days[i].active = true;
            
            if(dateStr === todayStr){
                const todayLearningTime = learningData.user_daily_total.find(item => item.date === dateStr)?.total_duration_minutes || 0;
                document.getElementById("learning-time-today").textContent = Math.round(todayLearningTime);
            }
        }
    }

    dayIconContainer.innerHTML = ""; // 기존 아이콘 제거
    
    days.forEach((day, index) => {
        const wrapper = document.createElement("div");
        wrapper.style.display = "flex";
        wrapper.style.flexDirection = "column";
        wrapper.style.alignItems = "center";
        wrapper.style.position = "relative";

        const svg = document.createElementNS("http://www.w3.org/2000/svg", "svg");
        svg.setAttribute("width", "44");
        svg.setAttribute("height", "44");

        const use = document.createElementNS("http://www.w3.org/2000/svg", "use");
        const symbolId = day.active ? "enabled-fire" : "disabled-fire";
        use.setAttributeNS("http://www.w3.org/1999/xlink", "xlink:href", `asset/images/images.svg#${symbolId}`);
        svg.appendChild(use);

        const label = document.createElement("span");
        label.textContent = day.day;
        label.style.fontSize = "12px";
        label.style.color = index === todayIndex ? "#FF7700" : "#000";

        if(todayIndex !== null && index === todayIndex) {
            const svgCircle = document.createElementNS("http://www.w3.org/2000/svg", "svg");
            svgCircle.setAttribute("width", "7");
            svgCircle.setAttribute("height", "7");
            svgCircle.style.position = "absolute";
            svgCircle.style.top = "0";
            svgCircle.style.left = "85%";

            const circle = document.createElementNS("http://www.w3.org/2000/svg", "circle");
            circle.setAttribute("cx", "3.5");
            circle.setAttribute("cy", "3.5");
            circle.setAttribute("r", "3.5");
            circle.style.fill = "#FF7700";

            svgCircle.appendChild(circle);
            wrapper.appendChild(svgCircle);
        }
        wrapper.appendChild(svg);
        wrapper.appendChild(label);

        dayIconContainer.appendChild(wrapper);
    });
}


/**
 * 학습 차트 구성
 */
async function configureLearningChart(learningData = null)
{
    var myChart = echarts.init(chartContainer, null, {
      renderer: 'canvas',
      useDirtyRect: false
    });

    // 기본값 설정 (데이터가 없을 때)
    let myData = [0, 0, 0, 0, 0, 0, 0];
    let averageData = [0, 0, 0, 0, 0, 0, 0];

    // 학습 데이터가 있을 때 차트 데이터 구성
    if (learningData) {
        console.log('Learning data received:', learningData);
        
        // 데이터 초기화
        myData = [0, 0, 0, 0, 0, 0, 0];
        averageData = [0, 0, 0, 0, 0, 0, 0];

        // 현재 선택된 주간 범위 가져오기
        const startDate = fpSummary.selectedDates[0];
        const endDate = fpSummary.selectedDates[1];
        
        if (startDate && endDate) {
            // 사용자 데이터를 날짜별로 매핑
            const userDataMap = {};
            if (learningData.user_daily_total) {
                console.log('Raw user_daily_total:', learningData.user_daily_total);
                learningData.user_daily_total.forEach(item => {
                    console.log('Processing user item:', item);
                    userDataMap[item.date] = item.total_duration_minutes || 0;
                });
            }
            
            // 전체 사용자 평균 데이터를 날짜별로 매핑
            const avgDataMap = {};
            if (learningData.all_users_daily_average) {
                console.log('Raw all_users_daily_average:', learningData.all_users_daily_average);
                learningData.all_users_daily_average.forEach(item => {
                    console.log('Processing avg item:', item);
                    avgDataMap[item.date] = item.avg_duration_minutes || 0;
                });
            }
            
            console.log('=== CHART DATA MAPPING DEBUG ===');
            console.log('Selected week range:', 
                       formatDate(startDate), 
                       'to', 
                       formatDate(endDate));
            console.log('User data map:', userDataMap);
            console.log('Average data map:', avgDataMap);
            
            // 주간 범위의 각 날짜를 요일별로 매핑
            for (let i = 0; i < 7; i++) {
                const currentDate = new Date(startDate);
                currentDate.setDate(startDate.getDate() + i);
                const dateStr = formatDate(currentDate);
                
                const userValue = userDataMap[dateStr] || 0;
                const avgValue = avgDataMap[dateStr] || 0;
                
                myData[i] = Math.round(userValue);
                averageData[i] = Math.round(avgValue);
                
                console.log(`Chart Day ${i} (${['월','화','수','목','금','토','일'][i]}): ${dateStr} -> User: ${userValue}, Avg: ${avgValue}`);
            }
        }
        
        console.log('Chart myData:', myData);
        console.log('Chart averageData:', averageData);
    }

    // 동적 Y축 최대값 계산
    const allData = [...myData, ...averageData];
    const maxValue = Math.max(...allData);
    const dynamicMax = Math.max(60, Math.ceil(maxValue / 10) * 10); // 최소 60, 10의 배수로 올림
    console.log('Chart dynamic max:', dynamicMax, 'from max data:', maxValue);

    var option = {
        grid: {
            top: 30,
            bottom: 50,
        },
        xAxis: {
            type: 'category',
            data: ['월', '화', '수', '목', '금', '토', '일']
        },
        yAxis: {
            type: 'value',
            interval: 10,
            min: 0,
            max: dynamicMax  // 동적 최대값
        },
        legend: {
            data: ['나의 학습시간', '전체 학습자 평균 학습시간'],
            bottom: 0,  // 💡 아래쪽에 고정
            icon: 'circle',
            left: '8%',
        },
        series: [
            {
                name: '나의 학습시간',
                data: myData,
                barWidth: 30,
                type: 'bar',
                itemStyle: {
                    color: '#3CB043',
                    barBorderRadius:[40,40,40,40]
                },
                label: {
                    show: true,
                    position: 'inside',
                    fontWeight: 'bold',
                    formatter: function(params) {
                        return params.value === 0? '' : params.value;
                    }
                }
            },
            {
                name: '전체 학습자 평균 학습시간',
                data: averageData,
                type: 'bar',
                barWidth: 30,
                itemStyle: {
                    color: '#FFCC66',
                    barBorderRadius:[40,40,40,40]
                },
                label: {
                    show: true,
                    position: 'inside',
                    fontWeight: 'bold',
                    formatter: function(params) {
                        return params.value === 0? '' : params.value;
                    }
                }
            }
        ]
    };

    myChart.setOption(option);

    window.addEventListener('resize', function() {
        myChart.resize();
    });
}

/**
 * 학습 통계 요약 업데이트 함수
 */
async function updateLearningSummary(lastWeekData, currentWeekData, start, end) {
    
    // 현재 주 나의 학습 데이터에서 하루 평균 학습시간 계산
    let totalMinutes = 0;
    let totalDays = 0;
    let totalAllAvgMinutes = 0;

    const today = new Date();
    today.setHours(0, 0, 0, 0);
    
    // 현재 주의 각 날짜를 확인하여 계산
    for (let i = 0; i < 7; i++) {
        const currentDate = new Date(start);
        currentDate.setDate(start.getDate() + i);
        
        // 오늘 이후의 날짜는 제외
        if (currentDate > today) {
            break;
        }
        
        totalDays++; // 실제 지나간 날 수 카운트
        
        const dateStr = formatDate(currentDate);
        
        // 해당 날짜의 학습 시간 찾기
        let dailyMinutes = 0;
        if (currentWeekData && currentWeekData.user_daily_total) {
            const dayData = currentWeekData.user_daily_total.find(item => item.date === dateStr);
            if (dayData && dayData.total_duration_minutes > 0) {
                dailyMinutes = dayData.total_duration_minutes;
            }
        }
        totalMinutes += dailyMinutes; // 학습시간이 0인 날도 0으로 포함

        let dailyAllAvgMinutes = 0;
        if (currentWeekData && currentWeekData.all_users_daily_average) {
            const dayAvgData = currentWeekData.all_users_daily_average.find(item => item.date === dateStr);
            if (dayAvgData && dayAvgData.avg_duration_minutes > 0) {
                dailyAllAvgMinutes = dayAvgData.avg_duration_minutes;
            }
        }
        totalAllAvgMinutes += dailyAllAvgMinutes; // 전체 평균 학습시간이 0인 날도 0으로 포함
    }
    
    // 하루 평균 학습시간 (분 단위) - 지나간 모든 날로 나누기
    const avgMinutesPerDay = totalDays > 0 ? Math.round(totalMinutes / totalDays) : 0;
    // 전체 평균 학습시간 (분 단위) - 지나간 모든 날로 나누기
    const avgAllAvgMinutesPerDay = totalDays > 0 ? Math.round(totalAllAvgMinutes / totalDays) : 0;

    var lastWeekMinutesTotal = 0; // 지난 주의 총 학습 시간
    lastWeekData.user_daily_total.forEach(item => {
        lastWeekMinutesTotal += item.total_duration_minutes || 0;
    });
    
    // 모든 .my-avg-learning-minutes 요소에 평균 학습시간 설정
    myAvgLearningMinutes.forEach(span => {
        span.textContent = avgMinutesPerDay.toString().padStart(2, '0');
    });

    // 지난주와 비교해서 이번주 학습시간 변화량 계산
    const diff = totalMinutes - lastWeekMinutesTotal;
    let percentChange;
    
    if (lastWeekMinutesTotal === 0) {
        percentChange = totalMinutes === 0 ? 0 : 100; // 지난주 학습시간이 0이면 이번주가 0이 아니면 100% 증가
    }
    else {
        percentChange = Math.round((diff / lastWeekMinutesTotal) * 100);
    }
    percentChangeValue.textContent = Math.abs(percentChange).toString().padStart(2, '0');
    percentChangeText.textContent = percentChange >= 0 ? "% 올랐습니다." : "% 내렸습니다.";       
    
    // 전체 평균과 사용자 학습시간 비교
    allAvgLearningMinutes.textContent = avgAllAvgMinutesPerDay.toString().padStart(2, '0');
    const currentDiff = avgMinutesPerDay - avgAllAvgMinutesPerDay;
    const comparePercent = avgAllAvgMinutesPerDay === 0? 100: Math.round((currentDiff / avgAllAvgMinutesPerDay) * 100);
    comparePercentValue.textContent = Math.abs(comparePercent).toString().padStart(2, '0');
    comparePercentText.textContent = comparePercent >= 0 ? "% 높습니다." : "% 낮습니다.";
}


/**
 * 오늘 학습한 시간 가져오는 함수(전체 평균, 사용자 학습 시간)
 * @returns {Promise<number>}
 */
async function getUserLearningTime() {
    try {
        // 오늘 날짜를 기준으로 학습 시간을 가져오기
        const today = new Date();
        today.setHours(0, 0, 0, 0); // 시간 초기화

        const response = await fetch(`${window.baseUrl}leaning/get_learning_time_date?date=${formatDate(today)}`);
        const data = await response.json();

        if(response.ok) {
            return [ data.total_learning_time_minutes || 0, 
                data.all_users_avg_learning_time_minutes || 0 ]; // 학습 시간 반환
        }
    }
    catch(e) {
        console.error("Error fetching user learning time:", e);
    }
    return [0, 0]; // 오류 발생 시 기본값 반환
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

// ✅ 공통 함수로 분리
function getWeekRange(date) {
    const start = new Date(date);
    start.setHours(0, 0, 0, 0); // 시간 초기화

    const day = start.getDay();
    const diff = (day === 0 ? -6 : 1) - day;
    start.setDate(start.getDate() + diff);

    const end = new Date(start);
    end.setHours(23, 59, 59, 999); // 시간 초기화
    end.setDate(start.getDate() + 6);

    return [start, end];
}