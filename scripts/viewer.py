"""Export frozen predictions (no fitting), then serve the comparison webpage."""
import argparse
import functools
import http.server
import json
import math
import shutil
from pathlib import Path
import cv2
import numpy as np
from displacement import PROJECT, load_observations, prepare_trials, predict, evaluate_trials, digest

VIEWER=PROJECT/'viewer'
MODEL=PROJECT/'data/processed/displacement/marked_foam_train/parameters.json'
CONFIG=PROJECT/'data/annotations/marked_foam_test.json'

def clean(value):
    if isinstance(value,np.ndarray):return clean(value.tolist())
    if isinstance(value,dict):return {k:clean(v) for k,v in value.items()}
    if isinstance(value,(list,tuple)):return [clean(v) for v in value]
    if isinstance(value,(float,np.floating)) and not math.isfinite(value):return None
    if isinstance(value,np.generic):return value.item()
    return value

def export(config_path,model_path,max_book_gap):
    config,video,processed,_,observations=load_observations(config_path)
    params=json.loads(model_path.read_text())
    metadata=json.loads((model_path.parent/'tracking_metadata.json').read_text())
    if Path(metadata['config']['video']).resolve()==video.resolve():
        raise ValueError('Viewer export expects a separate test video, not the training video.')
    if params['config_hash']!=metadata['config_hash'] or params['observations_hash']!=digest(model_path.parent/'observations.npz'):
        raise ValueError('Frozen training model is stale relative to its training inputs.')
    if not np.allclose(params['dimensions_mm'],config['dimensions_mm']):
        raise ValueError('Test object dimensions differ from the frozen model.')
    trials=prepare_trials(config,observations,max_book_gap)
    metrics=evaluate_trials(trials,config,params['recovery_time_s'])
    cap=cv2.VideoCapture(str(video))
    fps=cap.get(cv2.CAP_PROP_FPS);width=cap.get(cv2.CAP_PROP_FRAME_WIDTH);height=cap.get(cv2.CAP_PROP_FRAME_HEIGHT)
    cap.release()
    if fps<=0:raise ValueError('Cannot read video playback rate.')
    exported=[]
    for trial,metric in zip(trials,metrics):
        h,contact,markers=predict(trial,config,params['recovery_time_s'])
        valid=trial['valid_marker_mask']
        residual=(markers[:,:,1]-trial['markers'][:,:,1])/trial['px_per_mm']
        baseline_h=np.minimum(config['dimensions_mm'][2],trial['book_height_mm'])
        from displacement_model import project_markers
        baseline=project_markers(trial['reference'],baseline_h,trial['table_y'],config['dimensions_mm'][2])
        baseline_residual=(baseline[:,:,1]-trial['markers'][:,:,1])/trial['px_per_mm']
        def frame_rmse(errors):
            return [float(np.sqrt(np.mean(row[mask]**2))) if mask.any() else None for row,mask in zip(errors,valid)]
        exported.append(dict(id=trial['id'],role=trial['role'],frames=trial['frames'],
            px_per_mm=trial['px_per_mm'],reference=trial['reference'],
            heights=h,contact=contact,book=trial['book_height_mm'],estimated=trial['book_input_estimated'],
            observed=trial['markers'],predicted=markers,valid=valid,baseline_heights=baseline_h,
            rmse=frame_rmse(residual),baseline_rmse=frame_rmse(baseline_residual),
            metrics=metric,repairs=trial['book_input_repairs']))
    data=dict(parameters=params,trials=exported,video=dict(src='video.mp4',fps=fps,width=width,height=height),
        provenance=dict(model_sha256=digest(model_path),config_sha256=digest(config_path),
            observations_sha256=digest(processed/'observations.npz'),max_book_gap=max_book_gap),
        metric_definition='Vertical material-marker RMSE in mm, on the same valid observations for both models. Recovery uses observed book/marker gap >1 mm and marker-height proxy <H-0.3 mm.')
    dist=VIEWER/'dist';dist.mkdir(parents=True,exist_ok=True)
    (dist/'results.json').write_text(json.dumps(clean(data),allow_nan=False),encoding='utf-8')
    destination=dist/'video.mp4'
    if not destination.exists() or destination.stat().st_size!=video.stat().st_size or digest(destination)!=digest(video):
        shutil.copy2(video,destination)
    (dist/'parameters.json').write_text(json.dumps(params,indent=2),encoding='utf-8')
    (dist/'metrics.json').write_text(json.dumps(metrics,indent=2),encoding='utf-8')
    print(json.dumps(metrics,indent=2))
    print('Exported frozen predictions and original test video to',dist)
    print('No fitting or parameter changes performed. Run: python viewer.py serve')

class RangeHandler(http.server.SimpleHTTPRequestHandler):
    """Support video seeking without loading the whole video into browser memory."""
    def send_head(self):
        requested=self.headers.get('Range')
        path=Path(self.translate_path(self.path))
        if not requested or not path.is_file():return super().send_head()
        import re
        match=re.fullmatch(r'bytes=(\d*)-(\d*)',requested)
        size=path.stat().st_size
        if not match:return super().send_head()
        first,last=match.groups()
        start=int(first) if first else max(0,size-int(last or size))
        end=min(int(last) if last and first else size-1,size-1)
        if start>=size or end<start:
            self.send_response(416);self.send_header('Content-Range',f'bytes */{size}');self.end_headers();return None
        stream=path.open('rb');stream.seek(start);self.remaining=end-start+1
        self.send_response(206)
        self.send_header('Content-Type',self.guess_type(str(path)))
        self.send_header('Content-Length',str(self.remaining))
        self.send_header('Content-Range',f'bytes {start}-{end}/{size}')
        self.send_header('Accept-Ranges','bytes');self.end_headers()
        return stream
    def copyfile(self,source,outputfile):
        remaining=getattr(self,'remaining',None)
        if remaining is None:return super().copyfile(source,outputfile)
        try:
            while remaining:
                block=source.read(min(65536,remaining))
                if not block:break
                outputfile.write(block);remaining-=len(block)
        except (BrokenPipeError,ConnectionResetError):pass
        finally:del self.remaining

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    sub=parser.add_subparsers(dest='command',required=True)
    exp=sub.add_parser('export');exp.add_argument('--config',type=Path,default=CONFIG)
    exp.add_argument('--model',type=Path,default=MODEL)
    exp.add_argument('--max-book-gap',type=int,default=8)
    serve=sub.add_parser('serve');serve.add_argument('--port',type=int,default=8000)
    args=parser.parse_args()
    if args.command=='export':export(args.config,args.model,args.max_book_gap)
    else:
        if not (VIEWER/'dist/results.json').exists():parser.error('Run python viewer.py export first.')
        server=http.server.ThreadingHTTPServer(('127.0.0.1',args.port),functools.partial(RangeHandler,directory=str(VIEWER/'dist')))
        print(f'Foam viewer: http://localhost:{args.port}  (Ctrl+C to stop)',flush=True)
        try:server.serve_forever()
        except KeyboardInterrupt:pass
        finally:server.server_close()

if __name__=='__main__':main()
