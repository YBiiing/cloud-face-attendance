// Phones keep their native camera intent; desktop browsers use live video.
export function isMobileDevice(){
  return navigator.userAgentData?.mobile===true||/Android|iPhone|iPad|iPod/i.test(navigator.userAgent)||
    (navigator.platform==='MacIntel'&&navigator.maxTouchPoints>1);
}

let opened=false;
export function takeDesktopPhoto(){
  if(opened)return Promise.resolve(null);
  opened=true;
  return new Promise(resolve=>{
    const dialog=document.createElement('dialog');dialog.className='camera-dialog';dialog.setAttribute('aria-labelledby','camera-title');
    const title=document.createElement('h2');title.id='camera-title';title.textContent='拍摄照片';
    const hint=document.createElement('p');hint.textContent='正对摄像头，确保画面中只有本人。拍摄后确认照片，才会放入上传表单。';
    const status=document.createElement('p');status.className='hint';status.setAttribute('role','status');status.textContent='正在请求摄像头……';
    const video=document.createElement('video');video.autoplay=true;video.muted=true;video.playsInline=true;video.setAttribute('aria-label','摄像头实时画面');
    const shot=document.createElement('img');shot.alt='拍摄照片预览';shot.hidden=true;
    const actions=document.createElement('div');actions.className='camera-actions';
    const capture=document.createElement('button'),retry=document.createElement('button'),use=document.createElement('button'),cancel=document.createElement('button');
    for(const button of [capture,retry,use,cancel])button.type='button';
    capture.textContent='拍摄';capture.disabled=true;retry.textContent='重试摄像头';retry.hidden=true;retry.className='secondary';
    use.textContent='使用这张照片';use.hidden=true;cancel.textContent='取消';cancel.className='quiet';
    actions.append(capture,retry,use,cancel);dialog.append(title,hint,video,shot,status,actions);document.body.append(dialog);
    let stream=null,photo=null,photoURL=null,finished=false,generation=0;
    function stop(){if(stream){for(const track of stream.getTracks())track.stop();stream=null;}video.srcObject=null;}
    function clearShot(){if(photoURL)URL.revokeObjectURL(photoURL);photoURL=null;photo=null;shot.removeAttribute('src');shot.hidden=true;}
    function finish(file){
      if(finished)return;finished=true;generation++;stop();clearShot();
      document.removeEventListener('visibilitychange',visibility);window.removeEventListener('pagehide',leave);
      if(dialog.open)dialog.close();dialog.remove();opened=false;resolve(file);
    }
    const leave=()=>finish(null),visibility=()=>{if(document.visibilityState==='hidden')finish(null);};
    window.addEventListener('pagehide',leave);document.addEventListener('visibilitychange',visibility);
    dialog.addEventListener('cancel',event=>{event.preventDefault();finish(null);});
    dialog.addEventListener('close',()=>finish(null));cancel.onclick=()=>finish(null);
    function explain(error){
      const messages={NotAllowedError:'摄像头权限未允许，请在浏览器中允许摄像头后重试，或取消后选择照片文件。',
        NotFoundError:'未检测到摄像头，请连接摄像头后重试，或取消后选择照片文件。',
        NotReadableError:'摄像头暂时无法使用，可能被其他应用占用，请关闭占用程序后重试。',
        OverconstrainedError:'摄像头不支持当前取景设置，请更换设备或选择照片文件。'};
      status.textContent=messages[error?.name]||'无法打开摄像头，请重试或取消后选择照片文件。';
      status.classList.add('error');capture.disabled=true;retry.hidden=false;retry.textContent='重试摄像头';
    }
    async function start(){
      const current=++generation;stop();clearShot();video.hidden=false;use.hidden=true;retry.hidden=true;capture.hidden=false;capture.disabled=true;status.classList.remove('error');
      if(!window.isSecureContext){
        status.textContent='当前 HTTP 地址无法调用电脑摄像头。请使用 HTTPS；服务器在本机运行时可打开 localhost 地址，也可以取消后选择照片文件。';
        status.classList.add('error');return;
      }
      if(!navigator.mediaDevices?.getUserMedia){status.textContent='当前浏览器不支持摄像头取景，请更换浏览器或取消后选择照片文件。';status.classList.add('error');return;}
      status.textContent='正在请求摄像头，请在浏览器提示中选择是否允许……';
      try{
        const acquired=await navigator.mediaDevices.getUserMedia({audio:false,video:{facingMode:'user',width:{ideal:1280},height:{ideal:960}}});
        if(finished||current!==generation){for(const track of acquired.getTracks())track.stop();return;}
        stream=acquired;video.srcObject=stream;await video.play();
        if(finished||current!==generation)return;
        capture.disabled=video.videoWidth===0;status.textContent='摄像头已打开，请确认画面后点击“拍摄”。';
        video.onloadeddata=()=>{if(!finished&&stream)capture.disabled=video.videoWidth===0;};
        for(const track of stream.getVideoTracks())track.addEventListener('ended',()=>{if(!finished&&stream){stop();explain({name:'NotReadableError'});}});
      }catch(error){if(!finished&&current===generation){stop();explain(error);}}
    }
    capture.onclick=async()=>{
      if(finished||!stream||!video.videoWidth)return;
      capture.disabled=true;const current=generation;
      try{
        const canvas=document.createElement('canvas');canvas.width=video.videoWidth;canvas.height=video.videoHeight;
        canvas.getContext('2d').drawImage(video,0,0);
        const blob=await new Promise(done=>canvas.toBlob(done,'image/jpeg',.92));
        if(finished||current!==generation)return;
        if(!blob)throw new Error();photo=new File([blob],'camera-'+Date.now()+'.jpg',{type:'image/jpeg'});
        stop();photoURL=URL.createObjectURL(photo);shot.src=photoURL;shot.hidden=false;video.hidden=true;capture.hidden=true;
        use.hidden=false;retry.hidden=false;retry.textContent='重拍';status.textContent='请检查照片。点击“使用这张照片”后，再在表单中提交。';use.focus();
      }catch{if(!finished){status.textContent='照片保存失败，请重新拍摄。';status.classList.add('error');capture.disabled=false;}}
    };
    retry.onclick=start;use.onclick=()=>{if(photo)finish(photo);};dialog.showModal();start();
  });
}
