let map, ipMarker, redIcon;

const mapCompanies = [
  {
    ip:"61.98.",
    name: "한맥빌딩",
    location: "서울 송파구 오금로 554",
    lat: 37.492527, 
    lng: 127.150405,
  }
];

export async function initMap() {
    map = L.map('map').setView([37.5665, 126.9780], 17);
              
    L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
      maxZoom: 19,
    }).addTo(map);

    // 빨간 마커 아이콘 설정 (Leaflet 기본 모양 + 빨간색)
    redIcon = new L.Icon({
      iconUrl: 'https://raw.githubusercontent.com/pointhi/leaflet-color-markers/master/img/marker-icon-red.png',
      shadowUrl: 'https://unpkg.com/leaflet@1.9.4/dist/images/marker-shadow.png',
      iconSize: [25, 41],
      iconAnchor: [12, 41],
      popupAnchor: [1, -34],
      shadowSize: [41, 41]
    });

    ipMarker = null
}

export async function lookupIP() {
    const ip = document.getElementById("ipInput").value.trim();
    if (!ip) return alert("IP 주소를 입력하세요.");

    const matchedCompany = findCompanyByIP(ip);
    if (matchedCompany) {
        if (ipMarker) map.removeLayer(ipMarker);
        ipMarker = L.marker([matchedCompany.lat, matchedCompany.lng], { icon: redIcon }).addTo(map);
        ipMarker.bindPopup(matchedCompany.name).openPopup();
        map.setView([matchedCompany.lat, matchedCompany.lng], 17);
        return;
    }

    // ipinfo를 사용해서 IP 주소를 조회합니다.
    let res = await fetch(`${window.baseUrl}user/ip_location?ip=${ip}`);
    let data = await res.json();

    if (data.error)
    {
        lookupIPSub(ip);
        return;
    }
    
    if (!data.loc) {
      alert("위치를 찾을 수 없습니다.");
      return;
    }
    const [ latitude, longitude ] = data.loc.split(",").map(Number);

    if (ipMarker) map.removeLayer(ipMarker);

    ipMarker = L.marker([latitude, longitude], { icon: redIcon }).addTo(map);
    map.setView([latitude, longitude], 17);
  }


  // ipwho를 사용해서 IP 주소를 조회합니다.
  async function lookupIPSub(ip)
  {
    const res = await fetch(`https://ipwho.is/${ip}`);
    const data = await res.json();
    
    if (!data.success) {
      alert("위치를 찾을 수 없습니다.");
      return;
    }

    const { latitude, longitude } = data;
    if (ipMarker) map.removeLayer(ipMarker);

    ipMarker = L.marker([latitude, longitude], { icon: redIcon }).addTo(map);
    map.setView([latitude, longitude], 17);

  }

  // IP 주소로 회사 정보를 찾는 함수
  function findCompanyByIP(ip) {
    return mapCompanies.find(company => ip.startsWith(company.ip));
  }