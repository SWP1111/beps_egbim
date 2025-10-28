import { attachCustomScrollbar } from "./custom_vscroll.js";

export const SELECTION_TYPE = {
  ALL: 'ALL',               // 전체
  COMPANY: 'COMPANY',       // 회사
  DEPARTMENT: 'DEPARTMENT', // 부서
  USER: 'USER'              // 직원
};

let data = {};
//  = {
//     '삼안': {
//       '기획팀': [
//           {id: 'b0001', name: '홍길동', position: '대리', progress: 0.15},
//           {id: 'b0002', name: '김철수', position: '사원', progress: 0.25},
//       ],
//       '설계팀': [
//           {id: 'b0003', name: '이영희', position: '대리', progress: 0.35},
//           {id: 'b0004', name: '박진수', position: '사원', progress: 0.45},
//       ]
//     },
//     '한맥': {
//       '개발팀': [
//           {id: 'b0004',name: '최유리', position: '대리', progress: 0.55},
//       ],
//       '운영팀': [
//           {id: 'b0005',name: '정해인', position: '사원', progress: 0.65},
//           {id: 'b0006',name: '박보검', position: '사원', progress: 0.75},
//       ]
//     },
//     '바론': {
//       '개발팀': [{id: 'b0007',name: '최유리', position: '대리', progress: 0.55},],
//       '운영팀': [ 
//           {id: 'b0008',name: '정해인', position: '사원', progress: 0.65},
//           {id: 'b0009',name: '박보검', position: '사원', progress: 0.75},
//       ]
//     },
//     '장헌': {
//       '개발팀': [{id: 'b0010',name: '최유리', position: '대리', progress: 0.55},],
//       '운영팀': [ {id: 'b0011',name: '정해인', position: '사원', progress: 0.65},
//           {id: 'b0012',name: '박보검', position: '사원', progress: 0.75},]
//     },
//     '한라': {
//       '개발팀': [{id: 'b0013',name: '최유리', position: '대리', progress: 0.55},],
//       '운영팀': [ {id: 'b0014',name: '정해인', position: '사원', progress: 0.65},
//           {id: 'b0015',name: '박보검', position: '사원', progress: 0.75},]
//     },
//     'PTC': {
//       '개발팀': [{id: 'b0016',name: '최유리', position: '대리', progress: 0.55},],
//       '운영팀': [ {id: 'b0017',name: '정해인', position: '사원', progress: 0.65},
//           {id: 'b0018',name: '박보검', position: '사원', progress: 0.75},]
//     },
//     '기술개발센터': {
//       '그래픽스 개발팀': [
//           {id: 'b23009',name: '정나래', position: '선임', progress: 0.65},
//           {id: 'b23042',name: '한성일', position: '책임', progress: 0.75},
//       ],
//       '기술기획팀': [
//           {id: 'b0019',name: '김혜인', position: '선임', progress: 0.65},
//           {id: 'b0020',name: '이태윤', position: '사원', progress: 0.75},
//       ],
//     },
//     '총괄기획실': {
//      '개발팀': [{id: 'b0021',name: '최유리', position: '대리', progress: 0.55},],
//       '운영팀': [ {id: 'b0022',name: '정해인', position: '사원', progress: 0.65},
//           {id: 'b0023',name: '박보검', position: '사원', progress: 0.75},]
//     },
//     '기타': {
//      '개발팀': [{id: 'b0024',name: '최유리', position: '대리', progress: 0.55},],
//       '운영팀': [ {id: 'b0025',name: '정해인', position: '사원', progress: 0.65},
//           {id: 'b0026',name: '박보검', position: '사원', progress: 0.75},]
//     },
//     'TEST': {
//      '기술개발센터': [{id: 'b0024',name: '최유리', position: '대리', progress: 0.55},],
//      '운영팀': [ {id: 'b0025',name: '정해인', position: '사원', progress: 0.65},
//           {id: 'b0026',name: '박보검', position: '사원', progress: 0.75},]
//     },
//   };

let onSelectCallback = null;

export function setOnSelectCallback(callback) {
    onSelectCallback = callback;
}

export function setData(newData) {
    data = newData;
}

export async function setupUI(container) {
    
    const wrapper = document.querySelector('.search-container-wrapper');
    const res = await fetch('custom_vscroll.html');
    const html = await res.text();
    wrapper.insertAdjacentHTML('beforeend', html);
    const scrollbar = wrapper.querySelector('.custom-scrollbar');
    const thumb = wrapper.querySelector('.custom-scrollbar-thumb');
    const { refresh } = attachCustomScrollbar(container, scrollbar, thumb);

    attachCustomScrollbar(container, scrollbar, thumb);

    //#region 검색 기능
    const searchInput = document.getElementById('filter-search');
    const searchIcon = document.getElementById('filter-search-icon');
    
    await getOrganizations();
    
    function handleSearch() {
      const keyword = searchInput.value.trim().toLowerCase();

      if(keyword === '') {
        renderCompanyList();
      }
      else
        renderSearchResults(keyword);
    }

    async function renderSearchResults(keyword) {
      container.innerHTML = '';
    
      const allBtn = document.createElement('button');
      allBtn.innerText = '전체';
      allBtn.classList.add('dimmed');
      allBtn.onclick = () => renderCompanyList();
      container.appendChild(allBtn);
    
      const lowerKeyword = keyword.toLowerCase();
    
      const results = [];
    
      for (const company in data) {
        // 회사 이름에 keyword 포함
        if (company.toLowerCase().includes(lowerKeyword)) {
          results.push({ type: 'company', company });
        }
    
        for (const team in data[company]) {
          // 팀 이름에 keyword 포함
          if (team.toLowerCase().includes(lowerKeyword)) {
            results.push({ type: 'team', company, team });
          }
    
          data[company][team].forEach(user => {
            // 직원 이름에 keyword 포함
            if (user.name.toLowerCase().includes(lowerKeyword)) {
              results.push({ type: 'user', company, team, user });
            }
          });
        }
      }
    
      if (results.length === 0) {

        const url = `${window.baseUrl}/user/search?keyword=${keyword}`;
        const response = await fetch(url);
        const getData = await response.json();
        if (response.ok) {
         
          if(Object.keys(getData).length > 0){
            for(const company in getData) {

              if(!data[company]) data[company] = {};

              for (const department in getData[company]) {
                if(!data[company][department])
                  data[company][department] = getData[company][department];
                else
                  data[company][department].push(...getData[company][department]);
              }
            }         
            renderSearchResults(keyword);
            return;
          }
        }

        const empty = document.createElement('div');
        empty.innerText = '검색 결과가 없습니다.';
        container.appendChild(empty);
        return;
      }
    
      results.forEach(result => {
        const btn = document.createElement('button');
    
        if (result.type === 'company') {
          btn.innerText = result.company;
          btn.onclick = () => {
            selectedCompany = result.company;
            selectedTeam = null;
            selectedUserId = null;
            renderTeamList();
          };
        }
    
        if (result.type === 'team') {
          btn.innerText = `${result.company} / ${result.team}`;
          btn.onclick = () => {
            selectedCompany = result.company;
            selectedTeam = result.team;
            selectedUserId = null;
            renderUserList();
          };
        }
    
        if (result.type === 'user') {
          btn.innerText = `${result.company} / ${result.team} / ${result.user.name}`;
          btn.onclick = () => {
            selectedCompany = result.company;
            selectedTeam = result.team;
            selectedUserId = result.user.id;
            renderUserList();
          };
        }
    
        container.appendChild(btn);
      });
    
      refresh();
    }

    searchInput.addEventListener('keydown', (event) => {
      if (event.key === 'Enter') {
        handleSearch();
      }
    });

    searchIcon.addEventListener('click', handleSearch);
    //#endregion

    //#region 목록 구성
    let selectedUserId = null;
    let selectedCompany = null;
    let selectedTeam = null;
    
    const renderCompanyList = () => {
      selectedCompany = null;
      selectedTeam = null;
      selectedUserId = null;
      container.innerHTML = '';

      const allBtn = document.createElement('button');
      allBtn.innerText = '전체';
      allBtn.classList.add('selected');
      if(onSelectCallback){
        onSelectCallback({
          type: SELECTION_TYPE.ALL,
          company: null,
          department: null,
          userId: null,
          userName: null
        });
      };
      allBtn.onclick = () => renderCompanyList();
      container.appendChild(allBtn);

      Object.keys(data).forEach(company => {
        const btn = document.createElement('button');
        btn.innerText = company;
        btn.onclick = () => {
          selectedCompany = company;
          renderTeamList();
        };
        container.appendChild(btn);
      });

      insertSelectedDivider(allBtn);
      refresh();
    };

    const renderTeamList = () => {
        container.innerHTML = '';

        const allBtn = document.createElement('button');
        allBtn.innerText = '전체';
        allBtn.classList.add('dimmed');
        allBtn.onclick = () => renderCompanyList();
        container.appendChild(allBtn);

        const companyBtn = document.createElement('button');
        companyBtn.innerText = selectedCompany;
        companyBtn.classList.add('selected');
        if(onSelectCallback){
          onSelectCallback({
            type: SELECTION_TYPE.COMPANY,
            company: selectedCompany,
            department: null,
            userId: null,
            userName: null
          });
        };
        companyBtn.onclick = () => renderTeamList();
        container.appendChild(companyBtn);

        Object.keys(data[selectedCompany]).forEach(team => {
          const btn = document.createElement('button');
          btn.innerText = team;
          btn.onclick = async() => {
            selectedTeam = team;
            selectedUserId = null;
            await getUsers(selectedCompany, selectedTeam);
            renderUserList();
          };
          if (team === selectedTeam) {
            btn.classList.add('selected');
            if(onSelectCallback){
              onSelectCallback({
                type: SELECTION_TYPE.DEPARTMENT,
                company: selectedCompany,
                department: selectedTeam,
                userId: null,
                userName: null
              });
            };
          }
          container.appendChild(btn);
        });

        insertSelectedDivider(companyBtn);
        refresh();
      };

    const renderUserList = () => {
      container.innerHTML = '';

      const allBtn = document.createElement('button');
      allBtn.innerText = '전체';
      allBtn.classList.add('dimmed');
      allBtn.onclick = () => renderCompanyList();
      container.appendChild(allBtn);

      const companyBtn = document.createElement('button');
      companyBtn.innerText = selectedCompany;
      companyBtn.classList.add('dimmed');
      companyBtn.onclick = () => 
      {
        selectedTeam = null;
        selectedUserId = null;
        renderTeamList();
      }
      container.appendChild(companyBtn);

      const teamBtn = document.createElement('button');
      teamBtn.innerText = selectedTeam;
      teamBtn.classList.add('selected');
      if(onSelectCallback && selectedUserId == null){
        onSelectCallback({
          type: SELECTION_TYPE.DEPARTMENT,
          company: selectedCompany,
          department: selectedTeam,
          userId: null,
          userName: null
        });
      };
      teamBtn.onclick = async() => 
      {
        selectedUserId = null;
        renderTeamList();
        await getUsers(selectedCompany, selectedTeam);
        renderUserList();
      }
      container.appendChild(teamBtn);

      data[selectedCompany][selectedTeam].forEach(user => {
        const btn = document.createElement('button');
        btn.className='user-button';

        const text = document.createElement('span');
        text.className = 'text';
        text.innerText = `${user.name} ${user.position}`;
        btn.appendChild(text);

        if(user.progress <= 0.2)
        {
            const reddot = document.createElement('span');
            reddot.className = 'dot';
            btn.appendChild(reddot);
        }

        if (user.id === selectedUserId)
        {
            teamBtn.classList.add('dimmed');
            btn.classList.add('selected');
            if(onSelectCallback){
              onSelectCallback({
                type: SELECTION_TYPE.USER,
                company: selectedCompany,
                department: selectedTeam,
                user: {userId: user.id, userName: user.name, position: user.position},
              });
            };
        }
        btn.onclick = () => {
            selectedUserId = user.id;
          renderUserList();
        };
        container.appendChild(btn);
      });

      insertSelectedDivider(teamBtn);
      refresh();
    };
    //#endregion

    // 선택된 버튼 아래에 divider 추가(선 두 개, 전체/회사/팀)
    function insertSelectedDivider(afterElement) {
        // 기존 divider 다 제거
        const existing = document.querySelectorAll('.selected-divider');
        existing.forEach(div => div.remove());
      
        // 두 개의 선 생성
        for (let i = 0; i < 2; i++) {
          const divider = document.createElement('div');
          divider.className = 'selected-divider';
          afterElement.parentNode.insertBefore(divider, afterElement.nextSibling);
        }
      }

      renderCompanyList();
}

async function getOrganizations() {
  const url = `${window.baseUrl}/user/organizations`;
  const response = await fetch(url);
  const getData = await response.json();
  
  if(response.ok) {
    data = getData;
  }
}

async function getUsers(company, department) {
  const params = new URLSearchParams({
    company: company,
    department: department
  });
  const queryString = params.toString();
  const url = `${window.baseUrl}/user/user_by_org?${queryString}`;
  const response = await fetch(url);
  const getData = await response.json();
  
  if(response.ok) {
    data[company][department] = getData;
  }
}