import * as THREE from './vendor/three.module.js';
import {OrbitControls} from './vendor/OrbitControls.js';
const V=(x=0,y=0,z=0)=>new THREE.Vector3(x,y,z);
const palette={white:0xe3e5da,green:0x567659,pcb:0x214f42,gold:0xd9b971,black:0x222c2b,silver:0xa8b8b6,orange:0xe47742};
const mat=(color,extra={})=>new THREE.MeshStandardMaterial({color:palette[color]??color,roughness:.43,metalness:.12,...extra});
const box=(x,y,z)=>new THREE.BoxGeometry(x,y,z);
const sphere=(r)=>new THREE.SphereGeometry(r,40,28);
function pill(w,r,top){ // Hollow capsule surface, split at horizontal seam, long axis X.
 const vertices=[],indices=[],nx=64,na=32,len=w/2-r;
 for(let i=0;i<=nx;i++){const x=-w/2+w*i/nx;const radius=Math.sqrt(Math.max(0,r*r-Math.max(0,Math.abs(x)-len)**2));
 for(let j=0;j<=na;j++){let a=j/na*Math.PI+(top?0:Math.PI);vertices.push(x,Math.sin(a)*radius,Math.cos(a)*radius);}}
 for(let i=0;i<nx;i++)for(let j=0;j<na;j++){let a=i*(na+1)+j,b=a+na+1;indices.push(a,b,a+1,b,b+1,a+1);}
 const g=new THREE.BufferGeometry();g.setAttribute('position',new THREE.Float32BufferAttribute(vertices,3));g.setIndex(indices);g.computeVertexNormals();return g;
}
function makeViewer(id){
 const el=document.getElementById(id),view=el.querySelector('.viewport');let renderer;
 try{renderer=new THREE.WebGLRenderer({antialias:true,alpha:true});}catch(e){view.querySelector('.loading').textContent='无法启动 WebGL，请使用支持 3D 的浏览器。';return null;}
 renderer.setPixelRatio(Math.min(devicePixelRatio,2));renderer.outputColorSpace=THREE.SRGBColorSpace;renderer.setClearColor(0,0);view.prepend(renderer.domElement);view.querySelector('.loading').remove();
 const scene=new THREE.Scene(),camera=new THREE.PerspectiveCamera(36,1,.1,100);camera.position.set(6,5,9);
 const controls=new OrbitControls(camera,renderer.domElement);controls.enableDamping=true;controls.enablePan=false;controls.minDistance=5;controls.maxDistance=22;controls.target.set(0,.35,0);controls.update();controls.saveState();
 scene.add(new THREE.HemisphereLight(0xf2ffe5,0x35494b,2.6));for(const [p,intensity]of [[[3,7,5],3],[[-6,2,-3],2]]){let l=new THREE.DirectionalLight(0xffffff,intensity);l.position.set(...p);scene.add(l);}
 const root=new THREE.Group();scene.add(root);const entries=[];let selected=null;
 const list=el.querySelector('.parts');
 function part(name,desc,pos,offset,geometry,material,scale){
  const mesh=new THREE.Mesh(geometry,material);if(scale)mesh.scale.set(...scale);mesh.position.set(...pos);root.add(mesh);
  const p={name,desc,mesh,base:mesh.position.clone(),offset:V(...offset)};mesh.userData.part=p;entries.push(p);
  const b=document.createElement('button');b.textContent=name;b.setAttribute('aria-pressed','false');b.onclick=()=>select(p);list.append(b);p.button=b;return mesh;
 }
 function select(p){if(selected){selected.mesh.material.emissive?.setHex(0);selected.button.setAttribute('aria-pressed','false');}selected=p;p.mesh.material.emissive?.setHex(0x324d20);p.button.setAttribute('aria-pressed','true');el.querySelector('.detail h3').textContent=p.name;el.querySelector('.detail p').textContent=p.desc;}
 function child(parent,geometry,material,pos,scale){let m=new THREE.Mesh(geometry,material);m.position.set(...pos);if(scale)m.scale.set(...scale);parent.add(m);return m;}
 const range=el.querySelector('input');function update(){let t=Number(range.value)/100;el.querySelector('output').textContent=`${range.value}%`;entries.forEach(p=>p.mesh.position.copy(p.base).addScaledVector(p.offset,t));}
 range.oninput=update;el.querySelector('.assemble').onclick=()=>{range.value=0;update();};el.querySelector('.explode').onclick=()=>{range.value=100;update();};
 const ray=new THREE.Raycaster(),pointer=new THREE.Vector2();let down;
 renderer.domElement.addEventListener('pointerdown',e=>{down=[e.clientX,e.clientY];});renderer.domElement.addEventListener('pointerup',e=>{if(!down||Math.hypot(e.clientX-down[0],e.clientY-down[1])>6)return;const rect=view.getBoundingClientRect();pointer.set((e.clientX-rect.left)/rect.width*2-1,-(e.clientY-rect.top)/rect.height*2+1);ray.setFromCamera(pointer,camera);const hits=ray.intersectObjects(entries.map(p=>p.mesh),true);if(hits.length){let m=hits[0].object;while(!m.userData.part&&m.parent)m=m.parent;if(m.userData.part)select(m.userData.part);}});
 const resize=()=>{const w=view.clientWidth,h=view.clientHeight;renderer.setSize(w,h);camera.aspect=w/h;camera.fov=w<260?60:36;camera.updateProjectionMatrix();};new ResizeObserver(resize).observe(view);resize();
 return {part,child,update,entries,reset:()=>controls.reset(),frame:()=>{controls.update();renderer.render(scene,camera);}};
}
function buildCase(v){const {part:p,child:c}=v;
 const top=p('透明胶囊外壳','透明双拼外壳保护座舱，并保留胶囊形轮廓。',[0,0,0],[0,2.8,0],pill(5.6,1.22,true),mat('white',{transparent:true,opacity:.3,side:THREE.DoubleSide,depthWrite:false}));
 const colors=[];const positions=top.geometry.attributes.position;
 for(let i=0;i<positions.count;i++){const color=new THREE.Color(positions.getX(i)>0?palette.orange:palette.white);colors.push(color.r,color.g,color.b);}
 top.geometry.setAttribute('color',new THREE.Float32BufferAttribute(colors,3));top.material.vertexColors=true;top.material.color.setHex(0xffffff);top.material.opacity=.42;
 const lower=p('胶囊底壳','胶囊底壳容纳内部供电结构，并与外罩共同围护座舱。',[0,0,0],[0,-1.9,0],pill(5.6,1.22,false),mat('green',{side:THREE.DoubleSide}));
 const tray=p('旋转座舱与盖板','旋转座舱承托耳机，转动后露出取放空间。',[0,.35,0],[0,1.4,0],box(4.6,.16,1.65),mat('white'));
 for(const x of [-1.35,1.35]){c(tray,sphere(.64),mat('black'),[x,.02,0],[1,.15,.9]);}
 const knob=p('侧边旋钮','侧边旋钮带动座舱旋转，便于取放耳机。',[2.63,0,0],[.8,0,0],new THREE.CylinderGeometry(.45,.45,.2,40),mat('orange'));knob.rotation.z=Math.PI/2;
 p('300mAh 电池 · ST 702027','3.7V 软包锂电池储存电能，为耳机补充续航。',[0,-.5,0],[-.4,-.7,0],box(1.7,.43,1.3),mat('silver'));
 const board=p('充电仓主板','主板连接电池、输入小板与充电触点，承载电源管理电路。',[0,-.05,0],[0,.25,0],box(3.7,.08,1.2),mat('pcb'));
 for(let i=0;i<9;i++)c(board,box(.17,.045,.09),mat(i%2?'gold':'silver'),[-1.45+i*.33,.07,-.36]);
 p('英集芯 IP5516','充电盒管理 SoC 负责电池充电、升压输出与整机电源控制。',[.25,.06,0],[.25,.8,.8],box(.48,.09,.48),mat('black'));
 const usb=p('Type-C 输入小板','Type-C 输入小板接入外部 5V 电源，为充电仓充电。',[0,-.22,.92],[0,-.7,1.2],box(.85,.08,.42),mat('pcb'));
 c(usb,box(.57,.25,.3),mat('silver'),[0,.12,.18]);c(usb,box(.43,.12,.01),mat('black'),[0,.12,.335]);
 const pins=p('充电顶针 · Pogo pin','弹簧顶针接触耳机充电触点，将仓内电能传输给耳机。',[0,.15,0],[0,1.1,1],box(.01,.01,.01),mat('gold'));
 for(const x of [-1.45,-1.15,1.15,1.45])c(pins,new THREE.CylinderGeometry(.065,.065,.26,16),mat('gold'),[x,.1,0]);
 const magnets=p('定位与吸附磁铁','磁铁用于旋转开关定位，并将耳机吸附在座舱内。',[0,0,0],[-.2,0,1.9],box(.01,.01,.01),mat('silver'));
 for(const x of [-2.05,2.05,-1.3,1.3])c(magnets,box(.23,.13,.28),mat('silver'),[x,0,.4]);
}
function buildEar(v){const {part:p,child:c}=v;
 // Front acoustic sphere at left; battery and electronics occupy the larger rear pod at right.
 const hemi=(front)=>new THREE.SphereGeometry(1,40,24,front?0:Math.PI,Math.PI);
 p('前音腔外壳','球形前音腔容纳动圈单元，并以出音孔向耳廓传声。',[-1.25,0,0],[-.7,0,1.8],hemi(true),mat('white'),[.8,.8,.68]);
 p('音腔后壳','后腔与调音孔共同构成声学空间，调节空气流通。',[-1.25,0,0],[-.7,0,-1.1],hemi(false),mat('white'),[.8,.8,.68]);
 const grille=p('出音金属盖板','金属盖板保护前腔振膜，并保留出音通道。',[-1.25,0,.62],[-.7,0,2.45],new THREE.CylinderGeometry(.49,.49,.025,40),mat('silver'));grille.rotation.x=Math.PI/2;
 for(let x=-3;x<=3;x++)for(let y=-3;y<=3;y++)if(x*x+y*y<11)c(grille,new THREE.CylinderGeometry(.018,.018,.028,6),mat('black'),[x*.11,0,y*.11]);
 const driver=p('13mm 动圈喇叭','13mm 动圈单元将电信号转化为声音。',[-1.25,0,.15],[-.7,0,.8],new THREE.CylinderGeometry(.61,.61,.22,48),mat('gold'));driver.rotation.x=Math.PI/2;
 c(driver,new THREE.CylinderGeometry(.53,.53,.012,48),mat('black'),[0,.12,0]);c(driver,sphere(.29),mat('silver'),[0,.13,0],[1,.18,1]);
 const curve=new THREE.CatmullRomCurve3([V(-1.2,.4,-.25),V(-1.05,1.13,-.35),V(0,1.45,-.4),V(1.1,1.1,-.35),V(1.3,.5,-.2)]);
 p('C 桥 · TPU 与钛合金丝','TPU 包裹记忆钛合金丝形成弹性 C 桥，夹持耳廓并连接两端腔体。',[0,0,0],[0,1.05,-.6],new THREE.TubeGeometry(curve,64,.13,12,false),mat('white'));
 p('后端腔体外壳','后端腔体容纳电池与主板，外侧兼作触摸控制区域。',[1.23,0,0],[.6,0,-1.1],hemi(false),mat('white'),[.88,1.05,.6]);
 p('后端内侧盖板','内侧盖板封闭电池腔，并提供与充电仓接触的结构表面。',[1.23,0,0],[.8,0,2.4],hemi(true),mat('white'),[.88,1.05,.6]);
 p('40mAh 电池 · ST 501012','3.7V 软包锂电池为单只耳机的无线连接和发声供电。',[1.23,0,.13],[.7,0,1.45],box(.65,.8,.3),mat('silver'));
 const pcb=p('耳机主板','耳机主板连接电池与扬声器，承载蓝牙与音频电路。',[1.23,0,-.12],[.3,0,.2],box(1.15,1.48,.06),mat('pcb'));
 for(let i=0;i<5;i++)c(pcb,box(.12,.08,.06),mat('gold'),[-.42+i*.2,-.51,.065]);
 p('中科蓝讯 BT8932F','蓝牙 6.0 音频 SoC 负责无线连接、音频处理与通话降噪运算。',[1.2,.12,-.03],[1.35,.6,.8],box(.43,.43,.09),mat('black'));
 const mic=p('MEMS 麦克风 · 敏芯 MG52','MEMS 麦克风拾取语音，为通话功能提供声音信号。',[1.65,-.45,-.02],[1.25,-.6,1.15],box(.24,.3,.13),mat('gold'));c(mic,sphere(.038),mat('black'),[0,0,.065],[1,1,.2]);
 p('陶瓷蓝牙天线','陶瓷蓝牙天线负责无线信号收发。',[1.6,.52,-.02],[1.2,1,.35],box(.18,.36,.13),mat('white'));
 p('顺络叠层陶瓷电感','SDCL0603Q 系列电感配合蓝牙 SoC 的外围电路工作。',[.88,.45,-.02],[-.1,1.3,.7],box(.16,.09,.08),mat('silver'));
 p('触摸导电布','导电布连接主板，将触摸操作传递给控制电路。',[1.23,0,-.49],[.4,-1.65,-.7],box(.65,.8,.025),mat('black'));
}
const viewers=[];
for(const [id,build]of [['case',buildCase],['ear',buildEar]]){try{const v=makeViewer(id);if(v){build(v);v.update();viewers.push(v);}}catch(e){console.error(e);document.querySelector(`#${id} .detail p`).textContent='模型初始化失败，请刷新后重试。';}}
document.getElementById('reset').onclick=()=>viewers.forEach(v=>v.reset());
function frame(){requestAnimationFrame(frame);if(!document.hidden)viewers.forEach(v=>v.frame());}frame();
// Read-only diagnostics for browser verification, without changing the UI.
window.pill3d={viewers};
