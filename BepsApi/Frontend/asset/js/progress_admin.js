import { setupUI } from "./progress_admin_search.js";
import { activeUser, getTopUserConnectionDuration, getTopDepartmentConnectionDuration, getTopCompanyConnectionDuration } from "./progress_admin_active_user.js";
import { initMap, lookupIP } from "./progress_admin_map.js";
import { initTrafficGaugeChart} from "./progress_admin_traffic.js";
import { initPeriod, setOnSelectPeriodCallback, setOnSelectFilterCallback } from "./progress_admin_period.js";
import { setLoginData, formatSecondsToHHMMSS } from "./progress_admin_login.js";

document.addEventListener('DOMContentLoaded', async() => {
  
  const yearStart = new Date().getFullYear();
  const today = new Date().toLocaleDateString('sv-SE'); // YYYY-MM-DD 형식으로 변환

  let period_type = "year";
  let period_value = `${yearStart}`;
  let filter_type = "all";
  let filter_value = "all";

  let loginUserRank;
  let loginDepartmentRank;
  let loginCompanyRank;
  let loginRankType = "top"; // 초기값은 top으로 설정

  const completionHorus = document.getElementById("completion-hours");
  const completionMH = document.getElementById("completion-mh");
  const completionZero = document.getElementById("completion-zero");
  const completionTotalPages = document.getElementsByClassName("completion-total-pages");
  const completionRateElement = document.getElementById("completion-rate");
  const completionLearnedAvgPages = document.getElementById("completion-learned-avg-pages");

  const loginRankPrev = document.getElementById("login-rank-prev");
  const loginRankNext = document.getElementById("login-rank-next");
  const loginRankTitile = document.getElementById("login-rank-title");

  const loginRankTopFirst = document.getElementById("login-rank-top-first");
  const loginRankTopSecond = document.getElementById("login-rank-top-second");
  const loginRankTopThird = document.getElementById("login-rank-top-third");

  const exportBtn = document.getElementById("export-button");
  const pushMessageButton = document.getElementById("push-message-button");
  const loginExternalButton = document.getElementById("login-external-button");

  const pointer = document.getElementById("learning-pointer");
  const learningPointerContent = document.getElementById("learning-pointer-content");
  const learningPointerPercent = document.getElementById("learning-pointer-percent");
  const MAX_LEFT = learningPointerContent.offsetWidth; 

  const typeAllDiv = document.getElementById("type-all-div");
  const typeDepartmentDiv = document.getElementById("type-department-div");
  const typeUserDiv = document.getElementById("type-user-div");
  const departmentSpan = document.getElementById("department-span");
  const userSpan = document.getElementById("user-span");
  const userPointSpan = document.getElementById("user-point-span");
  const unitAvgSpan = document.querySelectorAll(".unit-avg-span");

  //기간 설정 Init
  initPeriod();

  // 검색 영역 Init
  const container = document.getElementById('container');
  setupUI(container);

  // 동시 접속 영역 Init
  activeUser(period_type, period_value);

  // 지도 영역 Init
  initMap();
  document.getElementById("ipInput").addEventListener("keydown", (event) => {
    if(event.key === "Enter") {
      const ip = document.getElementById("ipInput").value.trim();
      if (!ip) return alert("IP 주소를 입력하세요.");
      lookupIP(ip);
    }     
  });
  document.getElementById("ipInput-icon").addEventListener("click", () => {
    const ip = document.getElementById("ipInput").value.trim();
    if (!ip) return alert("IP 주소를 입력하세요.");
    lookupIP(ip);
  });

  // 트래픽 게이지 차트 Init
  initTrafficGaugeChart(0);
  
  const topUpdated = document.getElementById("top-updated");
  if(topUpdated) {
    topUpdated.addEventListener("click", () => {
      getUpdatedContentsRank();
      topUpdated.classList.add("active");
      bottomUpdated.classList.remove("active");
    });
  }
  const bottomUpdated = document.getElementById("bottom-updated");
  if(bottomUpdated) {
    bottomUpdated.addEventListener("click", () => {
      getUpdatedContentsRank(false);
      bottomUpdated.classList.add("active");
      topUpdated.classList.remove("active");
    });
  }

  getUpdatedContentsRank();

  if(loginRankPrev) {
    loginRankPrev.addEventListener("click", () => {
      const title = loginRankTitile.textContent;
      let type;
      if(title === "개인 순위")
      {
        loginRankTitile.textContent = "회사 순위";
        type = "company";
      }
      else if(title === "팀 순위")
      { 
        loginRankTitile.textContent = "개인 순위";
        type = "user";
      }
      else if(title === "회사 순위")
      {
        loginRankTitile.textContent = "팀 순위";
        type = "team";
      }
      
      displayRankbyType(loginRankTitile.textContent, loginRankType === "top");
      setActiveLoginRankBottomButton(type);
    });
  }

  if(loginRankNext) {
    loginRankNext.addEventListener("click", () => {
      const title = loginRankTitile.textContent;
      let type;
      if(title === "개인 순위")
      {
        loginRankTitile.textContent = "팀 순위";
        type = "team";
      }
      else if(title === "팀 순위")
      { 
        loginRankTitile.textContent = "회사 순위";
        type = "company";
      }
      else if(title === "회사 순위")
      {
        loginRankTitile.textContent = "개인 순위";
        type = "user";
      }
      displayRankbyType(loginRankTitile.textContent, loginRankType === "top");
      setActiveLoginRankBottomButton(type);
    });
  }

  document.querySelectorAll('[data-group="login-rank"]').forEach((element) => {
    element.addEventListener("click", (event) => {
      const group = element.dataset.group;
      document.querySelectorAll(`[data-group="${group}"]`).forEach(b => b.classList.remove('active'));
      element.classList.add('active');
      
      loginRankType = element.dataset.value;
      displayRankbyType(loginRankTitile.textContent, loginRankType === "top");
    });
  });

  document.querySelectorAll('[data-group="login-type"]').forEach((element) => {
    element.addEventListener("click", (event) => {
      const group = element.dataset.group;
      document.querySelectorAll(`[data-group="${group}"]`).forEach(b => b.classList.remove('active'));
      element.classList.add('active');

      const value = element.dataset.value;
      if(value === "user") {
        loginRankTitile.textContent = "개인 순위";
      }
      else if(value === "team") {
        loginRankTitile.textContent = "팀 순위";
      }
      else if(value === "company") {
        loginRankTitile.textContent = "회사 순위";
      }
      displayRankbyType(loginRankTitile.textContent, loginRankType === "top");

    });
  });

  getTopUserConnectionDuration(period_type='day', period_value=`2025-01-01~${today}`)
  .then(data => {
      loginUserRank = data;
      displayRankbyType(loginRankTitile.textContent, true);
  });

  getTopDepartmentConnectionDuration(period_type='day', period_value=`2025-01-01~${today}`)
  .then(data => {
    loginDepartmentRank = data;
  });

  getTopCompanyConnectionDuration(period_type='day', period_value=`2025-01-01~${today}`)
  .then(data => {
    loginCompanyRank = data;
  });
  
  setInterval(() => {
    getTopUserConnectionDuration(period_type='day', period_value=`2025-01-01~${today}`)
    .then(data => {
      loginUserRank = data;
    });

    getTopDepartmentConnectionDuration(period_type='day', period_value=`2025-01-01~${today}`)
    .then(data => {
      loginDepartmentRank = data;
    });

    getTopCompanyConnectionDuration(period_type='day', period_value=`2025-01-01~${today}`)
    .then(data => {
      loginCompanyRank = data;
    });

  }, 60*60*1000); // 1시간마다 업데이트


  exportBtn.addEventListener("click", () => {
    getStatisticsPreview();
  });

  if(pushMessageButton) {
    pushMessageButton.addEventListener("click", async() => {
      const pointValue = learningPointerPercent.value;

      let title = "";  
      let message = `학습진도율 ${pointValue}% 미만 학습자에게 보내는 메시지입니다.`;
        
      //const csrfToken = await getCookie();
      const url = `${window.baseUrl}leaning/push/send`;
      const response = await fetch(url,{
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          //"X-CSRF-Token": csrfToken,
        },
        body: JSON.stringify({
          filter_type,
          filter_value,
          title,
          message,
          pointValue
        })
      });

      const data = await response.json();
      console.log(data);
  });
  }

  async function getCookie() {
    const url = `${window.baseUrl}user/csrf_token`;
    const response =  await fetch(url)
    const data = await response.json();
    if(response.ok){
      return data.csrf_token;
    }
    else{
      return '';
    }
  }

  if(loginExternalButton) {
    loginExternalButton.addEventListener("click", async() => {
      const params = new URLSearchParams({
        period_value: period_value,
        period_type: period_type,
        filter_type: filter_type,
        filter_value: filter_value
      });

      const url = `external_ip_list.html?${params.toString()}`;
      window.open(url, 'ExternalIPList', 'width=800,height=600,scrollbars=yes,resizable=yes');
    });
  } 
  
  if(pointer) {
    let isDragging = false;
    let startX;
    let startLeft;

    pointer.addEventListener("dragstart", (e) => {
      e.preventDefault();
    });

    pointer.addEventListener("mousedown", (e) => {
      if(filter_type !== "all") return; // 전체가 아닐 경우 드래그 비활성화
      isDragging = true;
      startX = e.clientX;
      startLeft = pointer.offsetLeft;
      pointer.style.cursor = "grabbing";
    });

    document.addEventListener("mousemove", (e) => {
      if (!isDragging) return;
      const dx = e.clientX - startX;
      let newLeft = startLeft + dx;

      // 범위 제한 (0px ~ earning-rate-progress의 너비 - 21px)
      const maxLeft = document.getElementsByClassName("learning-rate-progress")[0].offsetWidth - 21;
      newLeft = Math.max(0, Math.min(newLeft, maxLeft));
      console.log(`newLeft: ${newLeft}, offsetWidth: ${learningPointerContent.offsetWidth}, parentWidth: ${learningPointerContent.parentElement.offsetWidth}`);
      
      if(learningPointerContent.style.marginLeft === "0px" && parseInt(pointer.style.marginLeft) >= newLeft) {
       
        pointer.style.marginLeft = "0px";
      }
      else if(newLeft + learningPointerContent.offsetWidth < learningPointerContent.parentElement.offsetWidth) {
        learningPointerContent.style.marginLeft = `${newLeft}px`;
      }
      else {
        pointer.style.marginLeft = `${newLeft - (learningPointerContent.parentElement.offsetWidth- learningPointerContent.offsetWidth)}px`;
      }

      learningPointerPercent.value = `${Math.round((1 - newLeft / maxLeft) * 100)}`;
    });

    document.addEventListener("mouseup", () => {
      isDragging = false;
      pointer.style.cursor = "grab";
    });
  }

  setOnSelectPeriodCallback(async() =>
  {
    period_type = sessionStorage.getItem("period_type");
    period_value = sessionStorage.getItem("period_value");

    activeUser(period_type, period_value);

    setLoginData(period_type, period_value, filter_type, filter_value);

    // getTopUserConnectionDuration(period_type, period_value)
    // .then(data => {
    //   loginUserRank = data;
    // });

    getTopDepartmentConnectionDuration(period_type, period_value)
    .then(data => {
      loginDepartmentRank = data;
    });

    getTopCompanyConnectionDuration(period_type, period_value)
    .then(data => {
      loginCompanyRank = data;
    });


    // getTotalPoint();
    //getRankPoint();
    getCategoryLearingRate();
    getTopViewdPages();
    getMemoRank();
    getCompletionRate();
  });

  setOnSelectFilterCallback(async({type, company, department, user}) =>
  {
    filter_type = type;
    filter_value = (type === "user") ? user.userId : (type === "department") ? `${company}||${department}` : company;
    setLoginData(period_type, period_value, filter_type, filter_value);

    typeAllDiv.style.display = "none";
    typeDepartmentDiv.style.display = "none";
    typeUserDiv.style.display = "none";

    if(filter_type === "all") {
      typeAllDiv.style.display = "block";
      learningPointerPercent.style.color = "blue";
      learningPointerPercent.style.borderBottom = "2px solid blue";
    }
    else if(filter_type === "company" || filter_type === "department") {
      typeDepartmentDiv.style.display = "block";
      if(filter_type === "company")
      {
        departmentSpan.textContent = `${company}`;
        departmentSpan.title = `${company}`;
      }
      else if(filter_type === "department")
      {
        departmentSpan.textContent = `${department}`;
        departmentSpan.title = `${department}`;
      }
      learningPointerPercent.style.color = "#285B4A";
      learningPointerPercent.style.borderBottom = "none";
    }
    else if(filter_type === "user") {
      typeUserDiv.style.display = "block";
      userSpan.textContent = `${user.userName}`;
      userPointSpan.textContent = `${user.position}`;
      learningPointerPercent.style.color = "#285B4A";
      learningPointerPercent.style.borderBottom = "none";
    }

    // getTotalPoint();
    //getRankPoint();
    getCategoryLearingRate();
    getTopViewdPages();
    getMemoRank();
    getCompletionRate();
  });


  async function getTotalPoint()
  {
    const totalPoint = document.getElementById("total-point");
    let url = `${window.baseUrl}leaning/point?period_value=${period_value}`
    if(period_type != null)
      url += `&period_type=${period_type}`;
    if(filter_type != null)
      url += `&filter_type=${filter_type}`;
    if(filter_value != null)
      url += `&filter_value=${encodeURIComponent(filter_value)}`
    const response = await fetch(url);
    const getPoint = await response.json();
    if(response.ok)
    {
      totalPoint.innerHTML = `총 포인트 : ${getPoint.total_points} P <br> 평균 포인트: ${Number(getPoint.average_points).toFixed(2)} P`;
    }
  }

  async function getRankPoint()
  {
    const TopPoint = document.getElementById("top-point");
    const BottomPoint = document.getElementById("bottom-point");
    let url = `${window.baseUrl}leaning/point/rank?period_value=${period_value}`
    if(period_type != null)
      url += `&period_type=${period_type}`;
    if(filter_type != null)
      url += `&filter_type=all`; // filter_type은 all로 고정(department, company 사용 가능, user는 사용 불가)

    const response = await fetch(url);
    const getResult = await response.json();
    if(response.ok)
    {
      if(getResult.top != null && getResult.top.length > 0)
      {
        TopPoint.textContent = `최상위 포인트(전직원 기준) : ${getResult.top[0].total_points} P (${getResult.top[0].name}`;
        if(getResult.top.length > 1)
          TopPoint.textContent += `외 ${getResult.top.length - 1}명)`;
        else
          TopPoint.textContent += `)`;
      }

      if(getResult.bottom != null && getResult.bottom.length > 0)
      {
        BottomPoint.textContent = `전체 최하위 포인트(전직원 기준) : ${getResult.bottom[0].total_points} P (${getResult.bottom[0].name}`;
        if(getResult.bottom.length > 1)
          BottomPoint.textContent += `외 ${getResult.bottom.length - 1}명)`;
        else
          BottomPoint.textContent += `)`;
      }
    }
  }

  async function getCategoryLearingRate() {
    const categorArea = document.getElementById("category-chart");
    categorArea.innerHTML = ""; // Clear previous content

    let url = `${window.baseUrl}leaning/category_progress?period_value=${period_value}`;
    if(period_type != null)
      url += `&period_type=${period_type}`;
    if(filter_type != null)
      url += `&filter_type=${filter_type}`;
    if(filter_value != null)
      url += `&filter_value=${encodeURIComponent(filter_value)}`;

    const response = await fetch(url);
    const getCategory = await response.json();
    
    if(response.ok)
    {
      echarts.dispose(categorArea); // 이전 인스턴스 제거 (optional but safe)
      const myChart = echarts.init(categorArea);
      const chartData = getCategory.progress.map((item, index) => {      
        const prefix = String.fromCharCode(65 + index); // A, B, C, ...
        const isSamll = item.percentage < 5;

        return {
          name: `${prefix}_${item.channel_name.replace(/^\d+_/, '')}`,
          value: item.percentage,
          time: item.duration,
          label: {
            show: item.percentage === 0? false : true,
            formatter: `${item.percentage}`,
            fontSize: 12,
            position: isSamll ? 'outside' : 'inside',
            fontFamily: 'Noto Sans KR',
            fontWeight: '700',
          },
          labelLine: {
            show: item.percentage > 0 && isSamll,
          }
        }       
      })

      const mediaQuery = window.matchMedia("(min-width: 2000px)");

      const channelsOption = {
        color: [
          '#B7F362', '#FFA778', '#806FBC', '#170068', '#80CEC8', '#FFB0B0', '#FF6565',
          '#F3DE62', '#4D66E7', '#A59684', '#DA8EC7', '#BFABCC', '#FF4567', '#65ABCD', '#123456'
        ],
        legend: {
          orient: 'vertical',
          right: 13,
          top: 'top',
          textStyle: {
            fontWeight: '700',
            fontFamily: 'Noto Sans KR'
          },
          formatter: function (name) {
            return '  ' + name;
          }
        },
        series: [
          {
            name: 'Access From',
            type: 'pie',
            radius: mediaQuery.matches? '70%' : '55%',
            center: ['33%', '45%'],
            data: chartData,
            emphasis: {
              itemStyle: {
                shadowBlur: 10,
                shadowOffsetX: 0,
                shadowColor: 'rgba(0, 0, 0, 0.5)'
              }
            }
          }
        ]
      };
      myChart.setOption(channelsOption);

    }
  }

  /**
   * 주어진 data-group에 해당하는 목록의 막대(bar) 너비를 동적으로 조정합니다.
   * - 0% 값(0)은 50px, 100% 값(최댓값)은 296px에 매핑하여 그 사이를 선형적으로 계산합니다.
   * - 값이 0이면 배경을 투명하게 처리하고 텍스트를 숨깁니다.
   * @param {string} dataGroupSelector - 너비를 조정할 항목들의 data-group 셀렉터 (예: '[data-group="top-viewed-page"]')
   */
  function adjustBarWidths(dataGroupSelector) {
    // '가장 많이 본 페이지'의 각 항목을 모두 선택합니다.
    const pageItems = document.querySelectorAll(dataGroupSelector);
    const classSuffixes = ['first','second','third','fourth','fifth'];
    
    const itemsData = Array.from(pageItems).map(item => {
      const index = parseInt(item.dataset.index, 10);
      if (isNaN(index) || index >= classSuffixes.length) return null;

      // data-index를 기반으로 정확한 클래스명을 만들어 막대 요소를 선택합니다.
      const barSelector = `.top-viewed-${classSuffixes[index]}-item`;
      const bar = item.querySelector(barSelector);

      const countElement = bar ? bar.querySelector('.top-viewed-item-count') : null;
      const count = countElement ? parseInt(countElement.textContent) || 0 : 0;

      return { bar, count, countElement };
    }).filter(Boolean); // 혹시 모를 null 값 제거

    const maxCount = Math.max(...itemsData.map(d => d.count), 0);

    const minWidth = 50;
    const widthRange = 296 - minWidth;

    itemsData.forEach(item => {
      if(item.bar) {
        // 1. 너비 계산 (이 로직은 항상 실행)
        let finalWidth = minWidth;
        if (maxCount > 0) {
          const ratio = item.count / maxCount;
          finalWidth += widthRange * ratio;
        }
        item.bar.style.width = finalWidth + 'px';

        // 2. 값이 0인지에 따라 배경/텍스트 가시성 처리
        if (item.count === 0 )
        {
          item.bar.style.backgroundColor = 'transparent';
          if (item.countElement) {
            item.countElement.style.visibility = 'hidden';
          }
        } else {
          item.bar.style.backgroundColor = '';  // CSS에 지정된 원래 배경색으로 복원
          if(item.countElement) {
            item.countElement.style.visibility = 'visible';
          }
        }
      }
    })
  }

  /**
   * "Competition Rank" 방식, 그 중에서도 동점자는 가장 낮은 순위로 처리하는 규칙으로
   * 순위를 매겨 CSS 클래스를 할당합니다.
   * 값이 0이면 배경을 투명하게 만듭니다.
   * @param {string} dataGroupSelector - 처리할 항목들의 data-group 셀렉터
   */
  function adjustWidthsByRank(dataGroupSelector) {
    const items = document.querySelectorAll(dataGroupSelector);
    const rankClasses = [
      'top-viewed-first-item',
      'top-viewed-second-item',
      'top-viewed-third-item',
      'top-viewed-fourth-item',
      'top-viewed-fifth-item'
    ];
    // '.top-viewed-first-item, .top-viewed-second-item, ...' 형태의 정확한 셀렉터를 만듭니다.
    const barSelector = rankClasses.map(cls => `.${cls}`).join(', ');

    const itemsData = Array.from(items).map(item => {
      const bar = item.querySelector(barSelector);
      const countElement = bar ? bar.querySelector('.top-viewed-item-count') : null;
      const count = countElement ? parseInt(countElement.textContent) || 0 : 0;
      return { bar, count, countElement };
    }).filter(data => data.bar);

    // 1. 값(count)을 기준으로 내림차순 정렬합니다.
    const sortedItems = [...itemsData].sort((a,b) => b.count - a.count);

    // 2. 각 항목에 순위(rank)를 할당합니다.
    const finalRanks = new Map(); // 각 bar 요소에 최종 순위(클래스)를 매핑
    let i = 0;
    while (i < sortedItems.length) {
      const currentCount = sortedItems[i].count;
      if (currentCount === 0) {
        i++;
        continue;
      }

      // 현재 값과 동일한 값을 가진 동점자 그룹의 마지막 인덱스를 찾습니다.
      let endIndex = i;
      while (endIndex + 1 < sortedItems.length && sortedItems[endIndex + 1].count === currentCount) {
        endIndex++;
      }

      // 동점자 그룹의 순위는 그룹의 마지막 인덱스(가장 낮은 순위)로 결정됩니다.
      const rank = endIndex;
      const rankClass = rank < rankClasses.length ? rankClasses[rank] : null;

      // 그룹 내 모든 항목에 동일한 순위 클래스를 할당합니다.
      if (rankClass) {
        for (let k = i; k <= endIndex; k++) {
          finalRanks.set(sortedItems[k].bar, rankClass);
        }
      }

      // 다음 검사를 위해 인덱스를 동점자 그룹 다음으로 이동시킵니다.
      i = endIndex + 1;
    }
    
    // 3. 모든 항목을 순회하며 최종적으로 클래스를 적용합니다.
    itemsData.forEach(item => {
      //초기화
      item.bar.classList.remove(...rankClasses);
      item.bar.style.backgroundColor = ''; 
      item.bar.style.width = '';

      // 값이 0일 경우
      if (item.count == 0) {
        item.bar.style.backgroundColor = 'transparent';
        item.bar.style.width = '0px';
        if (item.countElement) {
          item.countElement.style.visibility = 'hidden';
        }
      }
      // 값이 1 이상일 경우
      else {
        if (item.countElement) {
          item.countElement.style.visibility = 'visible';
        }
        const newClass = finalRanks.get(item.bar);
        if (newClass) {
          item.bar.classList.add(newClass);
        }
      }
    })
  }

  async function getTopViewdPages() {

    let url= `${window.baseUrl}leaning/top_viewed_pages?period_value=${period_value}`;
    if(period_type != null)
      url += `&period_type=${period_type}`;
    if(filter_type != null)
      url += `&filter_type=${filter_type}`;
    if(filter_value != null)
      url += `&filter_value=${encodeURIComponent(filter_value)}`;

    const response = await fetch(url);
    const getTopViewdPages = await response.json();

    document.querySelectorAll(`[data-group="top-viewed-page"]`).forEach((element) => {
      const index = parseInt(element.dataset.index || "0");

      const span = element.querySelector("span");
      const div = element.querySelector("div");
      const [dateSpan, countSpan] = div.querySelectorAll("span");

      span.textContent = `${index + 1}. `;
      countSpan.textContent = "0회";
      dateSpan.style.display = "none";
      dateSpan.textContent = "";

      if(response.ok === false) return;
      const data = getTopViewdPages.top_viewd_pages;
      if(index >= data.length) return;

      const page = data[index];
      span.textContent = `${index + 1}. ${page.file_name.replace(/^\d+_/, '').replace(/\.[^.]+$/, '')}`;
      countSpan.textContent = `${page.view_count}회`;
      element.title = `${page.channel_name.replace(/^\d+_/, '')} _ ${page.folder_name.replace(/^\d+_/, '')} _ ${page.file_name.replace(/^\d+_/, '').replace(/\.[^.]+$/, '')}`;
      dateSpan.textContent = `마지막 업데이트: ${formatUTCtoLocalDate(page.updated_at)}`;

      div.addEventListener("mouseover", () => {
        dateSpan.style.display = "inline";
      });

      div.addEventListener("mouseleave", () => {
        dateSpan.style.display = "none";
      });
    });

    // 데이터 업데이트 후, data-group 셀렉터를 인자로 넘겨 너비 조정 함수 호출
    adjustBarWidths('[data-group="top-viewed-page"]');
    //adjustWidthsByRank('[data-group="top-viewed-page"]');
  }

  async function getMemoRank() {
    let url = `${window.baseUrl}memo/memo_rank?period_value=${period_value}`;
    if(period_type != null)
      url += `&period_type=${period_type}`;
    if(filter_type != null)
      url += `&filter_type=${filter_type}`;
    if(filter_value != null)
      url += `&filter_value=${encodeURIComponent(filter_value)}`;

    const response = await fetch(url);
    const getMemoRank = await response.json();    

    document.querySelectorAll('[data-group="top-viewed-memo"]').forEach((element) => {
      const index = parseInt(element.dataset.index || "0");

      const span = element.querySelector("span");
      const div = element.querySelector("div");
      const [dateSpan, countSpan] = div.querySelectorAll("span");

      span.textContent = `${index + 1}. `;
      countSpan.textContent = "0개";
      dateSpan.style.display = "none";
      dateSpan.textContent = "";
    
      if(response.ok === false) return;

      const data = getMemoRank.data;
      if(index >= data.length) return;

      const memo = data[index];
      span.textContent = `${index + 1}. ${memo.name.split("/").pop().replace(/^\d+_/, '').replace(/\.[^.]+$/, '')}`;
      countSpan.textContent = `${memo.cnt}개`;
      element.title = `${memo.channel_name.split("/").pop().replace(/^\d+_/, '')} _ ${memo.folder_name.split("/").pop().replace(/^\d+_/, '')} _ ${memo.name.split("/").pop().replace(/^\d+_/, '').replace(/\.[^.]+$/, '')}`;
      dateSpan.textContent = `마지막 업데이트: ${formatUTCtoLocalDate(memo.modified_at)}`;

      div.addEventListener("mouseover", () => {
        dateSpan.style.display = "inline";          
      });
      div.addEventListener("mouseleave", () => {
        dateSpan.style.display = "none";
      });
    });

    //데이터 업데이트 후, data-group 셀렉터를 인자로 넘겨 너비 조정 함수 호출
    adjustBarWidths('[data-group="top-viewed-memo"]');
    //adjustWidthsByRank('[data-group="top-viewed-memo"]');
  }

  async function getUpdatedContentsRank(isTop = true) {
    let url = `${window.baseUrl}leaning/rank-update-contents`;
    const response = await fetch(url);
    const getUpdatedContentsRank = await response.json();

    if(response.ok)
    {
       document.querySelectorAll('[data-group^="updated-page"]').forEach((element) => {
        const value = element.dataset.value;
        const index = parseInt(element.dataset.index || "0");

        let content;
        if(isTop)
          content = getUpdatedContentsRank.top[index];
        else
          content = getUpdatedContentsRank.bottom[index];

        if(!content) return;

        console.log(`content: ${JSON.stringify(content)}`);

        if(value === "name")
        {
          element.textContent = `${index+1}. ${content.name.replace(/^\d+_/, '').replace(/\.[^/.]+$/, '')}`
          element.title = content.name.replace(/^\d+_/, '').replace(/\.[^/.]+$/, '');
        }
        else if(value === "updated-at")
        {
          element.textContent = content.updated_at.split("T")[0];
        }
        else if(value === "manager")
        {
          element.textContent = content.manager_name;
        }
      });
    }
  }

  async function callGetCompletionRateAPI(filtertype="all") {
    let url = `${window.baseUrl}leaning/completion-rate?period_value=${period_value}`;
    if(period_type != null)
      url += `&period_type=${period_type}`;
    if(filtertype != null)
      url += `&filter_type=${filtertype}`;
    if(filter_value != null)
      url += `&filter_value=${encodeURIComponent(filter_value)}`;

    const response = await fetch(url);
    return response;
  }

  async function getCompletionRate() {
    let isAll = false;

    if(filter_type === "all")
      isAll = true;

    let response = await callGetCompletionRateAPI();
    let data = await response.json();
    if(response.ok)
    {            
      completionRateElement.innerHTML = `평균: ${data.completion_rate}% <br>`;
      completionLearnedAvgPages.textContent = `${(data.completed_pages / data.count_users).toFixed(2)}`;

      const learningRateAvgArrow = document.getElementById("learning-rate-avg-arrow");

      for (const span of completionTotalPages) {
        span.textContent = `${data.total_pages}`;
      }

      const maxLeft = document.getElementsByClassName("learning-rate-progress")[0].offsetWidth - 21;
      let leftValue = (maxLeft * (1 - data.completion_rate / 100));
      learningRateAvgArrow.style.marginLeft = leftValue + "px";

      if(isAll === false)
      {
        response = await callGetCompletionRateAPI(filter_type);
        data = await response.json();
        leftValue = (maxLeft * (1 - data.completion_rate / 100));

        unitAvgSpan.forEach((span) => {
          span.textContent = `${(data.completed_pages / data.count_users).toFixed(2)}`;
        });
      }

      if(response.ok) {        
        if(leftValue + learningPointerContent.offsetWidth < learningPointerContent.parentElement.offsetWidth) {
          learningPointerContent.style.marginLeft = `${leftValue}px`;
          pointer.style.marginLeft = "0px";
        }
        else {
          learningPointerContent.style.marginLeft = `${learningPointerContent.parentElement.offsetWidth - learningPointerContent.offsetWidth}px`;
          pointer.style.marginLeft = `${leftValue - (learningPointerContent.parentElement.offsetWidth- learningPointerContent.offsetWidth)}px`;
        }

        learningPointerPercent.value = `${Math.round((1 - leftValue / maxLeft) * 100)}`;
      }
      
    }
  }

  let statisticsPopup = null;
  async function getStatisticsPreview() {
    let url = `progress_admin_statistics_preview.html?period_value=${period_value}`;
    if(period_type != null)
      url += `&period_type=${period_type}`;
    if(filter_type != null)
      url += `&filter_type=${filter_type}`;
    if(filter_value != null)
      url += `&filter_value=${encodeURIComponent(filter_value)}`;

    if(statisticsPopup == null || statisticsPopup.closed){
      const width = screen.availWidth;
      const height = screen.availHeight;

      statisticsPopup = window.open(url, `통계미리보기`,`width=${width},height=${height},resizable=yes,scrollbars=yes`);
    }
    else{
      statisticsPopup.location.href = url;
      statisticsPopup.focus();
    }
  }

  window.parent.postMessage({
    type: 'resize',
    height: document.body.scrollHeight,
    width: document.body.scrollWidth
  }, '*');

  function formatMinutesToTime(totalMinutes) {
    let hours = Math.floor(totalMinutes / 60);
    let remainingMinutes = totalMinutes % 60;

    let minutes = Math.floor(remainingMinutes);
    let seconds = Math.round((remainingMinutes - minutes) * 60);

    // 60초 = 1분 보정
    if (seconds === 60) {
      seconds = 0;
      minutes += 1;
    }

    return {
      hours: String(hours).padStart(2, '0'),
      minutes: String(minutes).padStart(2, '0'),
      seconds: String(seconds).padStart(2, '0')
    }
  }

  function displayRankbyType(rankTitle, topRank) {
    if(topRank === true){
      if(rankTitle === "개인 순위")
        {        
          loginRankTopFirst.textContent = `${loginUserRank.data.top[0][1]}`;
          loginRankTopFirst.title = `${loginUserRank.data.top[0][1]}`;
          loginRankTopSecond.textContent = `${loginUserRank.data.top[1][1]}`;
          loginRankTopSecond.title = `${loginUserRank.data.top[1][1]}`;
          loginRankTopThird.textContent = `${loginUserRank.data.top[2][1]}`;
          loginRankTopThird.title = `${loginUserRank.data.top[2][1]}`;

        }
        else if(rankTitle === "팀 순위")
        {      
          loginRankTopFirst.textContent = `${loginDepartmentRank.data.top[0][1]}`;
          loginRankTopFirst.title = `${loginDepartmentRank.data.top[0][1]}`;
          loginRankTopSecond.textContent = `${loginDepartmentRank.data.top[1][1]}`;
          loginRankTopSecond.title = `${loginDepartmentRank.data.top[1][1]}`;
          loginRankTopThird.textContent = `${loginDepartmentRank.data.top[2][1]}`;
          loginRankTopThird.title = `${loginDepartmentRank.data.top[2][1]}`;

        }
        else if(rankTitle === "회사 순위")
        { 
          loginRankTopFirst.textContent = `${loginCompanyRank.data.top[0][0]}`;
          loginRankTopFirst.title = `${loginCompanyRank.data.top[0][0]}`;
          loginRankTopSecond.textContent = `${loginCompanyRank.data.top[1][0]}`;
          loginRankTopSecond.title = `${loginCompanyRank.data.top[1][0]}`;
          loginRankTopThird.textContent = `${loginCompanyRank.data.top[2][0]}`;
          loginRankTopThird.title = `${loginCompanyRank.data.top[2][0]}`;
        }
    }
    else
    {
      if(rankTitle === "개인 순위")
        {        
          loginRankTopFirst.textContent = `${loginUserRank.data.bottom[0][1]}`;
          loginRankTopFirst.title = `${loginUserRank.data.bottom[0][1]}`;
          loginRankTopSecond.textContent = `${loginUserRank.data.bottom[1][1]}`;
          loginRankTopSecond.title = `${loginUserRank.data.bottom[1][1]}`;
          loginRankTopThird.textContent = `${loginUserRank.data.bottom[2][1]}`;
          loginRankTopThird.title = `${loginUserRank.data.bottom[2][1]}`;

        }
        else if(rankTitle === "팀 순위")
        {      
          loginRankTopFirst.textContent = `${loginDepartmentRank.data.bottom[0][1]}`;
          loginRankTopFirst.title = `${loginDepartmentRank.data.bottom[0][1]}`;
          loginRankTopSecond.textContent = `${loginDepartmentRank.data.bottom[1][1]}`;
          loginRankTopSecond.title = `${loginDepartmentRank.data.bottom[1][1]}`;
          loginRankTopThird.textContent = `${loginDepartmentRank.data.bottom[2][1]}`;
          loginRankTopThird.title = `${loginDepartmentRank.data.bottom[2][1]}`;

        }
        else if(rankTitle === "회사 순위")
        { 
          loginRankTopFirst.textContent = `${loginCompanyRank.data.bottom[0][0]}`;
          loginRankTopFirst.title = `${loginCompanyRank.data.bottom[0][0]}`;
          loginRankTopSecond.textContent = `${loginCompanyRank.data.bottom[1][0]}`;
          loginRankTopSecond.title = `${loginCompanyRank.data.bottom[1][0]}`;
          loginRankTopThird.textContent = `${loginCompanyRank.data.bottom[2][0]}`;
          loginRankTopThird.title = `${loginCompanyRank.data.bottom[2][0]}`;
        }
    }
  }

  function setActiveLoginRankBottomButton(type){
    document.querySelectorAll('[data-group="login-type"]').forEach((element) => {
        const group = element.dataset.group;      
        const bottomType = element.dataset.value;
        if(bottomType === type) {
            document.querySelectorAll(`[data-group="${group}"]`).forEach(b => b.classList.remove('active'));
            element.classList.add('active');
        }   
      });
  }

  function formatUTCtoLocal(utcString) {
    const date = new Date(utcString + "Z"); // ISO 8601을 파싱함
    const year = date.getFullYear();
    const month = String(date.getMonth() + 1).padStart(2, "0");
    const day = String(date.getDate()).padStart(2, "0");
    const hours = String(date.getHours()).padStart(2, "0");
    const minutes = String(date.getMinutes()).padStart(2, "0");
    const seconds = String(date.getSeconds()).padStart(2, "0");

    return `${year}-${month}-${day} ${hours}:${minutes}:${seconds}`;
  }

function formatUTCtoLocalDate(utcString) {
  const hasTimezone = /([+-]\d{2}:\d{2}|Z)$/.test(utcString);  // 시간대 정보 있는지 체크
  const normalized = hasTimezone ? utcString : utcString + "Z"; // 시간대 정보가 없으면 Z를 추가

  const date = new Date(normalized); // ISO 8601을 파싱함
  const year = date.getFullYear();
  const month = String(date.getMonth() + 1).padStart(2, "0");
  const day = String(date.getDate()).padStart(2, "0");

  return `${year}-${month}-${day}`;
}

});





  
  