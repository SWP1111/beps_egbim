import { getUserConnectionDuration } from "./progress_admin_active_user.js";

export async function setLoginData(period_type, period_value, filter_type, filter_value)
{
    const logintimeArea = document.getElementById("login-time-chart");
    logintimeArea.innerHTML ="";
    const loginCountArea = document.getElementById("login-count-chart");
    loginCountArea.innerHTML = "";

    const value = await getUserConnectionDuration(period_type, period_value, filter_type, filter_value);

    const total_duration = value.total_duration ?? 0;
    const worktime_duration_value = value.worktime_duration ?? 0;
    const offhour_duration_value = value.offhour_duration ?? 0;
    const internal_count_value = value.internal_count ?? 0;
    const external_count_value = value.external_count ?? 0;
    const total_login_count_value = internal_count_value + external_count_value;

    const loginTotalTimes = document.getElementById("login-total-times");
    loginTotalTimes.textContent = formatSecondsToHoursFloat(total_duration);
    const loginTotalCount = document.getElementById("login-total-count");
    loginTotalCount.textContent = total_login_count_value;

    echarts.dispose(logintimeArea);
    const pie_emphasis_style ={
      itemStyle: {
        shadowBlur: 10,
        shadowOffsetX: 0,
        shadowColor: 'rgba(0, 0, 0, 0.5)'
      }
    }
    const pie_series_radius = '60%';
    const pie_series_center = ['50%', '40%'];
    const pie_series_type = 'pie';

    const loginTimeChart = echarts.init(logintimeArea);
    const worktime_ratio = total_duration > 0 ? (worktime_duration_value/ total_duration) * 100 : 0;
    const offhour_ratio = total_duration > 0 ? 100 - worktime_ratio : 0;
    const loginTimeChartData = [
      createChartData("근무시간 내", worktime_ratio, formatSecondsToHoursFloat(worktime_duration_value)),
      createChartData("근무시간 외", offhour_ratio, formatSecondsToHoursFloat(offhour_duration_value))       
    ]

    const loginTimeChartOptions = {    
        color: ['#F1AAAA', '#799FFF'],  
        legend: getPieChartLegend(),
        series: [
          {
            name: 'Access From',
            type: pie_series_type,
            radius: pie_series_radius,
            center: pie_series_center,
            data: loginTimeChartData,
            emphasis: pie_emphasis_style
          }
        ]
    };
    loginTimeChart.setOption(loginTimeChartOptions);

    echarts.dispose(loginCountArea);
    const loginCountChart = echarts.init(loginCountArea);

    const internal_count_ratio =  total_login_count_value > 0 ? ((internal_count_value / total_login_count_value) * 100) : 0;
    const external_count_ratio =  total_login_count_value > 0 ? ((external_count_value / total_login_count_value) * 100) : 0;
    const loginCountChartData = [
      createChartData("내부 접속", internal_count_ratio, internal_count_value),
      createChartData("외부 접속", external_count_ratio, external_count_value)
    ]
    const loginCountChartOptions = {     
        color: ['#49A66B', '#EC9823'],   
        legend: getPieChartLegend(),
        series: [
          {
            name: 'Access From',
            type: pie_series_type,
            radius: pie_series_radius,
            center: pie_series_center,
            data: loginCountChartData,            
            emphasis: pie_emphasis_style
          }
        ]
    };
    loginCountChart.setOption(loginCountChartOptions);
}

export function formatSecondsToHHMMSS(seconds) {
    const hours = Math.floor(seconds / 3600);
    const minutes = Math.floor((seconds % 3600) / 60);
    const secondsRemainder = Math.floor(seconds % 60);

    return `${String(hours).padStart(2, '0')}:${String(minutes).padStart(2, '0')}:${String(secondsRemainder).padStart(2, '0')}`;
}

function formatSecondsToHoursFloat(seconds) {
    const hours = Math.round((seconds / 3600) * 10) / 10; // Round to 1 decimal place
    return hours;
}

function createChartData(name, rawValue, times) {
  const value = Number(rawValue);
  return {
    name: name,
    value: value,
    times: times,
    label: getPieChartLabel(value)
  }
}

function getPieChartLegend(){
  return {
    orient: 'vertical',
    bottom: 10,
    left: '35%',
    textStyle: {
      fontWeight: '700',
      fontFamily: 'Noto Sans KR'
    },
    formatter: function (name) {
      return '  ' + name;
    }
  }
}

function getPieChartLabel(value){
  return{
    formatter: function (params){
      return `${Number(params.value).toFixed(1)}\n(${params.data.times})`;
    },
    position: 'inside',
    fontSize: 12,
    fontFamily: 'Noto Sans KR',
    fontWeight: '700',
    show: value > 0
  }
}