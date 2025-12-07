let viewer;

window.onload = () => {
  new QWebChannel(qt.webChannelTransport, (ch) => {
    viewer = ch.objects.viewer;
    document.getElementById('info').textContent = '就绪';
  });
};

async function openMrc() {
  if (!viewer) {
    alert("通信未建立");
    return;
  }
  console.log("🚀 开始加载 MRC");
  const res = await new Promise(resolve => {
    viewer.load_mrc_file(resolve);
  });
  console.log("📦 收到响应:", res); 
  const data = JSON.parse(res);
  if (data.success) {
    document.getElementById('info').textContent = 
      `📄 ${data.msg}`;
    
    // 更新滑块范围
    const [nz, ny, nx] = data.shape;
    document.getElementById('slider-z').max = nz - 1;
    document.getElementById('slider-y').max = ny - 1;
    document.getElementById('slider-x').max = nx - 1;
    document.getElementById('slider-z').value = nz >> 1;
    document.getElementById('slider-y').value = ny >> 1;
    document.getElementById('slider-x').value = nx >> 1;

    // 初始刷新
    updateSlices(nz >> 1, ny >> 1, nx >> 1);
  } else {
    showError(data.msg);
  }
}

async function updateSlices(z, y, x) {
  if (!viewer) return;

  const res = await new Promise(resolve => {
    viewer.get_slices(z, y, x, resolve);
  });
  console.log("📦 收到 JSON 长度:", res.length);
  const data = JSON.parse(res);
  if (!data.success || !data.xy) return;

  drawImageFromBase64('xy-canvas', data.xy.data, data.xy.width, data.xy.height);
  drawImageFromBase64('yz-canvas', data.yz.data, data.yz.width, data.yz.height);
  drawImageFromBase64('zx-canvas', data.zx.data, data.zx.width, data.zx.height);

  document.getElementById('z-value').textContent = data.indices.z;
  document.getElementById('y-value').textContent = data.indices.y;
  document.getElementById('x-value').textContent = data.indices.x;
  
}

function drawImageFromBase64(canvasId, b64Data, width, height) {
  const canvas = document.getElementById(canvasId);
  const ctx = canvas.getContext('2d');
  canvas.width = width;
  canvas.height = height;

  const img = new Image();
  img.onload = () => ctx.drawImage(img, 0, 0, width, height);
  img.src = 'data:image/png;base64,' + b64Data;
}

function onSliderChange() {
  const z = parseInt(document.getElementById('slider-z').value);
  const y = parseInt(document.getElementById('slider-y').value);
  const x = parseInt(document.getElementById('slider-x').value);
  updateSlices(z, y, x);
}

function showError(msg) {
  const el = document.createElement('div');
  el.textContent = msg;
  el.style.cssText = `
    position: fixed; top: 10px; right: 10px;
    background: red; color: white; padding: 10px;
    border-radius: 6px; z-index: 1000;
  `;
  document.body.appendChild(el);
  setTimeout(() => el.remove(), 3000);
}

function drawTestImage() {
    const canvas = document.getElementById('xy-canvas');
    const ctx = canvas.getContext('2d');
  
    // 设置尺寸
    canvas.width = 500;
    canvas.height = 500;
  
    // 清空并画红方块
    ctx.fillStyle = 'red';
    ctx.fillRect(0, 0, 500, 500);
  
    // 写文字
    ctx.fillStyle = 'white';
    ctx.font = 'bold 48px Arial';
    ctx.fillText('TEST', 100, 250);
  
    console.log("✅ 测试图已绘制");
  }