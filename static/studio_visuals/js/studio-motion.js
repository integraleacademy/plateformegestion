const TAU=Math.PI*2;
export function motionPose(kind,phase){
  const s=Math.sin(phase*TAU),c=Math.cos(phase*TAU);
  if(kind==='spin')return {x:0,y:0,rotation:phase*TAU,scale:1};
  if(kind==='orbit')return {x:7*s,y:5*(c-1),rotation:.045*s,scale:1};
  if(kind==='pulse')return {x:0,y:0,rotation:0,scale:1+.025*s};
  if(kind==='rise')return {x:7*s,y:-9*s,rotation:.06*s,scale:1};
  if(kind==='bob')return {x:0,y:-7*s,rotation:.035*s,scale:1};
  return {x:0,y:-9*s,rotation:0,scale:1};
}

export function startStudioMotion(root,{playing=true}={}){
  const nodes=[...root.querySelectorAll('[data-motion]')];
  let frame=0,start=0,active=false;
  const reset=()=>nodes.forEach(node=>node.style.transform='');
  function tick(now){
    if(!active||!root.isConnected)return;
    if(!start)start=now;
    const phase=((now-start)%6000)/6000;
    nodes.forEach(node=>{const p=motionPose(node.dataset.motion,phase);node.style.transform=`translate(${p.x}px,${p.y}px) rotate(${p.rotation}rad) scale(${p.scale})`});
    frame=requestAnimationFrame(tick);
  }
  const controller={available:nodes.length>0,get playing(){return active},
    setPlaying(value){cancelAnimationFrame(frame);active=Boolean(value&&nodes.length);start=0;reset();root.dataset.motionPlaying=String(active);if(active)frame=requestAnimationFrame(tick)},
    stop(){controller.setPlaying(false)}
  };
  controller.setPlaying(playing);
  return controller;
}

export function supportedVideoType(recorder=globalThis.MediaRecorder){
  if(!recorder?.isTypeSupported)return null;
  return ['video/mp4','video/webm;codecs=vp9','video/webm;codecs=vp8','video/webm'].find(type=>recorder.isTypeSupported(type))||null;
}
async function loadFrame(url){const image=new Image();image.src=url;await image.decode();return image}

export async function recordStudioMotion(node,{width,height,duration=6,onStatus=()=>{},onProgress=()=>{}}){
  const type=supportedVideoType();
  if(!type)throw new Error('L’export vidéo n’est pas disponible dans ce navigateur. Ouvrez le studio dans Chrome ou Edge à jour.');
  const effects=[...node.querySelectorAll('[data-motion]')];
  if(!effects.length)throw new Error('Choisissez un modèle NEW2 portant la mention « Animé ».');
  let stream,recorder,frameId,watchdog;
  const bounds=node.getBoundingClientRect();
  const layers=[];
  const raster=()=>htmlToImage.toPng(node,{width,height,pixelRatio:1,cacheBust:false,style:{width:width+'px',height:height+'px',transform:'none',margin:'0'}});
  try{
    onStatus('Préparation des calques animés…');
    node.classList.add('studio-motion-base');
    const base=await loadFrame(await raster());
    node.classList.remove('studio-motion-base');
    node.classList.add('studio-motion-only');
    for(const effect of effects){
      const rect=effect.getBoundingClientRect();
      effect.dataset.motionCapture='true';
      const image=await loadFrame(await raster());
      delete effect.dataset.motionCapture;
      layers.push({image,kind:effect.dataset.motion,cx:rect.left-bounds.left+rect.width/2,cy:rect.top-bounds.top+rect.height/2});
    }
    node.classList.remove('studio-motion-only');
    const canvas=document.createElement('canvas');
    // H.264 encoders need even dimensions; paint the complete frame to the edge.
    canvas.width=width+width%2;canvas.height=height+height%2;
    const context=canvas.getContext('2d',{alpha:false});
    function draw(phase){
      context.save();context.scale(canvas.width/width,canvas.height/height);
      context.drawImage(base,0,0,width,height);
      for(const layer of layers){
        const p=motionPose(layer.kind,phase);context.save();
        context.translate(layer.cx+p.x,layer.cy+p.y);context.rotate(p.rotation);context.scale(p.scale,p.scale);context.translate(-layer.cx,-layer.cy);
        context.drawImage(layer.image,0,0,width,height);context.restore();
      }
      context.restore();
    }
    draw(0);stream=canvas.captureStream(30);
    recorder=new MediaRecorder(stream,{mimeType:type,videoBitsPerSecond:6000000});
    const chunks=[];
    const blob=await new Promise((resolve,reject)=>{
      recorder.ondataavailable=event=>{if(event.data.size)chunks.push(event.data)};
      recorder.onerror=event=>reject(event.error||new Error('L’enregistrement vidéo a échoué.'));
      recorder.onstop=()=>resolve(new Blob(chunks,{type:recorder.mimeType||type}));
      recorder.start(250);const start=performance.now();
      watchdog=setTimeout(()=>reject(new Error('L’export a été interrompu. Gardez cet onglet visible pendant les 6 secondes d’enregistrement.')),duration*1000+15000);
      const tick=now=>{
        const elapsed=Math.min(duration*1000,now-start);draw((elapsed%(duration*1000))/(duration*1000));
        const percent=Math.round(elapsed/(duration*1000)*100);onProgress(percent);onStatus(`Création de la vidéo… ${percent} %`);
        if(elapsed>=duration*1000){recorder.stop();return}frameId=requestAnimationFrame(tick);
      };
      frameId=requestAnimationFrame(tick);
    });
    if(blob.size<1000)throw new Error('La vidéo générée est vide. Relancez l’export.');
    return {blob,extension:type.startsWith('video/mp4')?'mp4':'webm',width:canvas.width,height:canvas.height,duration};
  }finally{
    cancelAnimationFrame(frameId);clearTimeout(watchdog);
    if(recorder?.state==='recording')recorder.stop();
    stream?.getTracks().forEach(track=>track.stop());
    node.classList.remove('studio-motion-base','studio-motion-only');
    effects.forEach(effect=>delete effect.dataset.motionCapture);
  }
}
