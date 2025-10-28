let isLargeScreen = false;//window.matchMedia("(min-width: 3000px) and (min-height: 1800px)").matches;

const baseGaugeOption = {
  series: [
    {
      backgroundColor: 'red',
      type: 'gauge',
      startAngle: 180,
      endAngle: 0,
      center: ['50%', '50%'],
      radius: '90%',
      min: 0,
      max: 1,
      splitNumber: 8,
      axisLine: {
        lineStyle: {
          width: isLargeScreen? 10: 5,
          color: [
            [0.25, '#FF6E76'],
            [0.5, '#FDDD60'],
            [0.75, '#58D9F9'],
            [1, '#7CFFB2']
          ]
        }
      },
      pointer: {
        icon: 'path://M12.8,0.7l12,40.1H0.7L12.8,0.7z',
        length: '12%',
        width: isLargeScreen? 40:20,
        offsetCenter: [0, '-55%'],
        itemStyle: {
          color: 'auto'
        }
      },
      axisTick: {       
        distance: isLargeScreen? 10: 5,
        length: isLargeScreen? 20: 10,
        lineStyle: {
          color: 'auto',
          width: isLargeScreen? 2: 1
        }
      },
      splitLine: {
        distance: isLargeScreen? 10: 5,
        length: isLargeScreen? 30:15,
        lineStyle: {
          color: 'auto',
          width: isLargeScreen? 10:5
        }
      },
      axisLabel: {
        show: false
      },
      title: {
        offsetCenter: [0, '-5%'],
        fontSize: isLargeScreen? 30:15,
        fontWeight: 700
      },
      detail: {
        fontSize: isLargeScreen? 40:20,
        offsetCenter: [0, '-30%'],
        valueAnimation: true,
        formatter: function (value) {
          return Math.round(value * 100) + '';
        },
        color: 'inherit'
      },
      data: [
        {
          value: 0,
          name: 'Traffic'
        }
      ]
    }
  ]
};

let trafficChart = null;

export function initTrafficGaugeChart(value = 0) {
    const dom = document.getElementById('gaugeChart');
    if (!dom) return;
  
    trafficChart = echarts.init(dom, null, {
      renderer: 'canvas',
      useDirtyRect: false
    });
  
    // 깊은 복사 (series 안쪽까지)
    const option = JSON.parse(JSON.stringify(baseGaugeOption));
    option.series[0].data[0].value = value;
  
    trafficChart.setOption(option);
    window.addEventListener('resize', () =>
    {
      const oldval = isLargeScreen;
      isLargeScreen = window.matchMedia("(min-width: 1920px) and (min-height: 1800px)").matches;
      if (isLargeScreen !== oldval) {
        const old_option = trafficChart.getOption();
        const option = JSON.parse(JSON.stringify(baseGaugeOption));
        option.series[0].data[0].value = old_option.series[0].data[0].value;
        trafficChart.setOption(option);
      }

      trafficChart.resize();
    });
  }


  
export function updateTrafficGaugeValue(activeUser, maxUser = 100) {
  if (!trafficChart) return;  

  const raw = (activeUser / maxUser);
  const value = Math.round(raw * 10) / 10;
  const option = trafficChart.getOption();
  option.series[0].data[0].value = value;
  trafficChart.setOption(option);
}

