// Direct comparison with measured material motion; supports older exports in pixels.
function refreshMarkerChoices(){
  const select=$('marker');select.replaceChildren();
  for(let m=0;m<trial.predicted[0].length;m++){
    if(trial.predicted[0][m].every(finite))select.add(new Option(`Dot ${m+1}`,m));
  }
  select.onchange=motionPlot;
  buildMeanChoices();
}
function motionPlot(){
  if(!trial)return;
  meanPlot();
  const m=+$('marker').value,reference=trial.predicted[0][m]?.[1];
  if(!finite(reference))return;
  const scale=finite(trial.px_per_mm)?trial.px_per_mm:1;
  $('motion-unit').textContent=`Vertical displacement / ${finite(trial.px_per_mm)?'mm':'pixels'} · downward positive`;
  const observed=trial.observed.map((p,i)=>trial.valid[i][m]&&finite(p[m][1])?(p[m][1]-reference)/scale:null);
  const predicted=trial.predicted.map(p=>finite(p[m][1])?(p[m][1]-reference)/scale:null);
  const [ctx,w,h]=surface('motion'),left=42,top=14,pw=w-left-16,ph=h-top-26;
  const values=[0,...observed,...predicted].filter(finite),low=Math.min(...values),high=Math.max(...values),span=Math.max(high-low,1),min=low-span*.08,max=high+span*.08;
  const x=i=>left+pw*i/(trial.frames.length-1),y=v=>top+ph*(1-(v-min)/(max-min));
  ctx.font='10px monospace';
  for(let j=0;j<=4;j++){const value=min+(max-min)*j/4;ctx.strokeStyle='#344038';ctx.beginPath();ctx.moveTo(left,y(value));ctx.lineTo(w-16,y(value));ctx.stroke();ctx.fillStyle='#a7b5a9';ctx.fillText(value.toFixed(1),1,y(value)+3);}
  ctx.strokeStyle='#ffb16c';ctx.lineWidth=1.5;ctx.beginPath();let connected=false;
  predicted.forEach((v,i)=>{if(!finite(v)){connected=false;return;}if(connected)ctx.lineTo(x(i),y(v));else ctx.moveTo(x(i),y(v));connected=true;});ctx.stroke();
  ctx.fillStyle='#b7ed93';observed.forEach((v,i)=>{if(finite(v)){ctx.beginPath();ctx.arc(x(i),y(v),2,0,Math.PI*2);ctx.fill();}});
  ctx.strokeStyle='#edf1e8';ctx.beginPath();ctx.moveTo(x(index),top);ctx.lineTo(x(index),top+ph);ctx.stroke();
  ctx.fillStyle='#a7b5a9';ctx.fillText('0 s',left,h-3);ctx.fillText(((trial.frames.at(-1)-trial.frames[0])/data.parameters.capture_fps).toFixed(2)+' s',w-60,h-3);
}

function selectedMeanSeries(source,ids){
  const scale=finite(source.px_per_mm)?source.px_per_mm:1;
  const refs=ids.map(m=>source.predicted[0][m]?.[1]);
  const result={observed:[],predicted:[],complete:0};
  for(let i=0;i<source.frames.length;i++){
    const known=ids.length>0&&refs.every(finite);
    const observedOK=known&&ids.every(m=>source.valid[i][m]&&source.observed[i][m].every(finite));
    const predictedOK=known&&ids.every(m=>source.predicted[i][m].every(finite));
    const mean=points=>ids.reduce((sum,m,j)=>sum+(points[m][1]-refs[j])/scale,0)/ids.length;
    result.observed.push(observedOK?mean(source.observed[i]):null);
    result.predicted.push(predictedOK?mean(source.predicted[i]):null);
    if(observedOK)result.complete++;
  }
  return result;
}

function buildMeanChoices(){
  const container=$('mean-choices');container.replaceChildren();
  for(let m=0;m<trial.predicted[0].length;m++){
    const initialized=trial.predicted[0][m].every(finite);
    const count=trial.valid.reduce((sum,row)=>sum+Number(Boolean(row[m])),0);
    const label=document.createElement('label'),box=document.createElement('input');
    box.type='checkbox';box.value=String(m);box.disabled=!initialized;box.onchange=meanPlot;
    label.append(box,document.createTextNode(`Dot ${m+1} · ${initialized?(100*count/trial.frames.length).toFixed(0)+'%':'no reference'}`));
    container.append(label);
  }
  $('mean-all').onclick=()=>{container.querySelectorAll('input:not(:disabled)').forEach(box=>box.checked=true);meanPlot();};
  $('mean-clear').onclick=()=>{container.querySelectorAll('input').forEach(box=>box.checked=false);meanPlot();};
}

function meanPlot(){
  if(!trial)return;
  const ids=Array.from($('mean-choices').querySelectorAll('input:checked')).map(box=>+box.value);
  const [ctx,w,h]=surface('mean-motion');
  $('mean-unit').textContent=`Vertical displacement / ${finite(trial.px_per_mm)?'mm':'pixels'} · downward positive`;
  if(!ids.length){
    $('mean-summary').textContent='No dots selected. Choose a fixed group above; selections reset when you change test press.';
    ctx.fillStyle='#a7b5a9';ctx.font='13px system-ui';ctx.fillText('Select dots to compare their mean displacement.',20,h/2);return;
  }
  const series=selectedMeanSeries(trial,ids);
  $('mean-summary').textContent=`Selected dots: ${ids.map(m=>m+1).join(', ')}. Complete observations: ${series.complete}/${trial.frames.length} frames (${(100*series.complete/trial.frames.length).toFixed(1)}%). ${series.complete?'':'No frame has every selected dot available.'}`;
  const left=42,top=14,pw=w-left-16,ph=h-top-26;
  const values=[0,...series.observed,...series.predicted].filter(finite),low=Math.min(...values),high=Math.max(...values),span=Math.max(high-low,1),min=low-span*.08,max=high+span*.08;
  const x=i=>left+pw*i/(trial.frames.length-1),y=v=>top+ph*(1-(v-min)/(max-min));
  ctx.font='10px monospace';
  for(let j=0;j<=4;j++){const value=min+(max-min)*j/4;ctx.strokeStyle='#344038';ctx.beginPath();ctx.moveTo(left,y(value));ctx.lineTo(w-16,y(value));ctx.stroke();ctx.fillStyle='#a7b5a9';ctx.fillText(value.toFixed(1),1,y(value)+3);}
  ctx.strokeStyle='#ffb16c';ctx.lineWidth=1.5;ctx.beginPath();let connected=false;
  series.predicted.forEach((v,i)=>{if(!finite(v)){connected=false;return;}if(connected)ctx.lineTo(x(i),y(v));else ctx.moveTo(x(i),y(v));connected=true;});ctx.stroke();
  ctx.fillStyle='#b7ed93';series.observed.forEach((v,i)=>{if(finite(v)){ctx.beginPath();ctx.arc(x(i),y(v),2,0,Math.PI*2);ctx.fill();}});
  ctx.strokeStyle='#edf1e8';ctx.beginPath();ctx.moveTo(x(index),top);ctx.lineTo(x(index),top+ph);ctx.stroke();
  ctx.fillStyle='#a7b5a9';ctx.fillText('0 s',left,h-3);ctx.fillText(((trial.frames.at(-1)-trial.frames[0])/data.parameters.capture_fps).toFixed(2)+' s',w-60,h-3);
}
